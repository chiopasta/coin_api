# V4 실시간 forward observation recorder

## 범위와 고정 규칙

자동매매가 아닌 관찰 기록기다. 4% 외 threshold 옵션, 점수, ranking, 주문 API, TP/SL은 없다. V3 discovery/validation 파일과 정책은 수정하지 않는다.

1분봉은 매분 수집하고 **V3와 동일한 5분 달력 시점**에서만 판정한다. 따라서 "최초"는 처음 조건을 만족한 확정 5분 관측 시점이며 틱 단위/매분 최초 돌파가 아니다. 매분 신호로 변경하면 기존 연구와 다른 정책이 된다.

range=(최근 30개 실제 분의 high 최대 / low 최소 -1)*100 >=4. 최근 30분 중 없는 분봉은 채우지 않으며 filter를 NULL로 처리한다. DB ts는 UTC 봉 시작 초, signal_time/asof_time은 봉 확정 시각이다. 로그에는 KST를 표시한다.

기본 universe는 기존 manifest의 고정 50알트+BTC를 재사용한다. init 시 종목 목록을 V4 config에 동결하고 이후 재선정하지 않는다. BTC는 상대강도 계산용이며 signal을 만들지 않는다. 다른 고정 KRW 목록도 별도 DB의 init으로 사용할 수 있으나 전혀 다른 모집단임을 구분해야 한다.

## DB

- `scanner_config`: 동결 정책, 시장 목록, 최초 forward 시작 및 warmup 시작.
- `minute_candles`: 기존 V3와 같은 market/ts/open/high/low/close/trade_value. PK(market,ts). 원본 캔들 보존, 보간 없음.
- `signals`: signal_id, market, signal_time, signal_price, range_30m, cluster_id, detected_at, delay_seconds. market/time과 cluster 중복 금지.
- `signal_features`: asof_time, values_json, flags_json, observed_candidates_json. V3 수익률 5/15/30/60/120, range 15/30/60, MA5/20·비율·기울기, 거래대금 배율·가속, 60분 고점 대비 drawdown, 이전 고점 breakout, 알트/BTC 상대강도. 15/30 range 및 alt relative60은 관찰 후보로 별도 명시한다.
- `signal_outcomes`: signal_id/label별 행. status, max_return, first_target_time, observed_minutes, expected_minutes, evaluated_at. L1/L2 두 행으로 정규화했다. first_target_time은 최초 목표 도달 봉의 확정 시각이며 실제 체결 순간이 아니다.
- `scanner_state`: 시장별 verified_until, last_observation, active, cluster_id, last_error.
- `collection_jobs`: 중단된 요청 범위와 역방향 cursor.
- `collection_pages`: 정상 확인한 구간 증거. 수집 실패와 거래 없는 분을 구분하는 데 사용한다.

signal과 feature UPDATE, SUCCESS/FAILURE outcome UPDATE는 DB trigger로 금지한다. API 캔들이 기존 확정 값과 충돌하면 덮어쓰지 않고 오류를 표시한다.

## 상태 머신

초기 active는 UNKNOWN이다. 6시간 warmup을 replay하며 관측된 range<4를 보아야 ARMED가 된다. 이미 진행 중인 흐름을 새 signal로 세지 않는다.

- ARMED + range>=4 → ACTIVE + 최초 signal (본 시작 시점 이후만 저장)
- ACTIVE + range>=4 → 유지, 중복 signal 없음
- 관측된 range<4 → ARMED
- NULL range → 기존 상태 유지

전 시장(BTC 포함)의 확인 시각 중 최솟값까지 처리한다. 따라서 상대강도 계산 때 아직 수집하지 못한 동시 시장을 임의로 제외하지 않는다. 한 시장의 장기 오류는 전체 observation 진도를 멈춘다. 로그/통계의 collection_errors를 확인해야 하며 자동으로 해당 시장을 탈락시키지 않는다.

outcome은 PENDING으로 시작한다. L1은 (t,t+30m], L2는 (t,t+60m]의 high를 종가와 비교한다. 해당 구간 전체 분봉 및 수집 확인이 있어야 SUCCESS/FAILURE가 된다. 목표에 도달한 봉이 일부 보이더라도 구간이 불완전하면 확정하지 않는다.

마감+10분 grace 이후에도 불완전하면 UNKNOWN. 이후 원본 데이터가 실제로 확보되면 PENDING/UNKNOWN만 재평가할 수 있다. 없는 분봉을 만들어 채우거나 UNKNOWN을 실패로 계산하지 않는다. 일반 수집기는 정상 검증한 과거 무체결 구간을 반복 다운로드하지 않는다. SUCCESS/FAILURE는 다시 계산하지 않는다.

## 재시작/지연

캔들 저장과 collection job cursor 갱신은 한 transaction. 전체 요청 범위를 확인한 뒤 verified_until 갱신. signal/feature/outcome 초기 행과 observation state도 한 transaction. 강제 종료 후 같은 DB로 시작하면 마지막 정상 페이지/관측부터 이어간다. OS 파일 잠금으로 동일 DB의 동시 writer를 막는다.

중단 동안의 미처리 구간도 시간순으로 복구하되 `detected_at`과 `delay_seconds`를 기록한다. 이는 당시 실시간 전달된 신호라고 주장할 수 없다. 지연 신호는 차후 운영 통계에서 별도로 다룰 수 있도록 보존한다. 현재 누적 통계는 모든 기록의 개수와 관측 완결 성공률만 보여주며 성능 판정은 하지 않는다.

## 수집과 비용

기존 collector의 공개 candle Client, 200봉 검증, Remaining-Req, retry/backoff를 재사용한다. 매분 전체 시장을 순차 polling하고 미확인 범위를 역방향 200봉 페이지로 확인한다. 최신 진행 중 봉은 제외하고 5초 settle 지연을 둔다.

51시장 정상 운영 시 대략 분당 51회 = 시간당 3,060회 = 하루 73,440회. 최초 6시간 warmup은 활발한 시장 기준 약 102회(시장당 2페이지), 재시작 backlog·retry는 추가된다. 처리 지연이나 빈번한 장애 시 시간당 실제 요청 수와 관측 지연이 달라진다. 시장 목록 조회/재선정 호출은 없다. `--max-requests`는 retry를 포함한 전체 실행 요청 한도다.

공유 limiter는 최소 0.15초 요청 간격과 응답 헤더를 따른다. 418/block/budget는 중단, 429·5xx·timeout은 기존 backoff 처리. 실제 bounded API smoke는 2026-09-30 완료했으며 결과는 `docs/research_status.md`와 `reports/forward_scanner_v4_live_smoke.json`을 확인한다.

## 실행 — 명령 제시만, 장기 실행하지 않음

먼저 네트워크 호출 없이 새 DB를 초기화한다. start는 실행 시각 다음 5분 경계로 고정된다. 기존 DB를 재개할 때는 init을 반복하지 않는다.

```powershell
python -m coin_analysis.forward_scanner_v4 --mode init --db data/forward_scanner_v4.db --market-manifest docs/research_market_validation_v1_manifest.json
```

실제 장기 관찰 및 재시작:

```powershell
python -m coin_analysis.forward_scanner_v4 --mode run --db data/forward_scanner_v4.db
```

종료 후 통계:

```powershell
python -m coin_analysis.forward_scanner_v4 --mode stats --db data/forward_scanner_v4.db
```

실제 API 사용을 사용자가 원하는 경우의 bounded 실행(이번 작업에서는 미실행):

```powershell
python -m coin_analysis.forward_scanner_v4 --mode run --db data/forward_scanner_v4.db --max-cycles 2 --max-requests 180
```

통계 명령도 단일 writer 잠금을 사용하므로 장기 scanner 실행 중에는 해당 프로세스가 매 cycle 출력하는 통계를 본다.

## 검증

자동 테스트: 최초 신호, below4 reset, NULL 유지, 초기 진행 cluster 억제, future 삭제/변경 leakage, PENDING 재시작, UNKNOWN 회복, 완결 FAILURE, outcome 재계산 금지, DB 보호, mock 200봉 page resume/중복 방지.

초기 mock smoke는 5시장과 합성 7시간 범위, 1회 요청 후 강제 중단을 흉내 내고 재시작은 최대 20요청으로 제한했다. 이후 별도 real smoke에서 BTC/ETH/XRP, 33.37초, 9요청, 1,074봉 수집과 DB 재시작/중복 방지/다음 분 수집을 확인했다. signal 0건으로 live outcome 완결 및 장기 운영은 아직 미검증이다.

과거 replay는 validation DB의 BTC/CPOOL/FLOCK/NEAR/ENA만 사용해 2026-09-15 하루(전 6시간/후 1시간 buffer), 매 5분 순차 주입, 12시간 지점 DB 재연결을 수행했다. 18개 최초 signal과 모든 저장 feature/outcome이 동일 소규모 universe의 V3 계산과 일치했다(부동소수 합계 오차 허용). L1 valid10 success0 UNKNOWN8, L2 valid4 success1 UNKNOWN14. 이는 기능 검증이지 새로운 성과 연구가 아니다. 원본 DB 해시 동일. 결과는 `reports/forward_scanner_v4_replay.json`.
