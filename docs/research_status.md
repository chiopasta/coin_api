# 프로젝트 상태 — 새 작업의 첫 읽기 문서

최종 갱신: 2026-10-01. 현재 단계: **사용자가 시작한 V4 live 관찰의 중간 점검**. 매매 전략으로 승인된 상태가 아니다. 신규 요청 없이 장기 실행·대량 수집하지 않는다. 아래 이전 smoke 기록은 해당 시점의 이력이다.

## 최신 구현: LIVE/CATCHUP 분리 완료

- `signals.source` 추가. LIVE는 `0 <= detected_at-signal_time < 300초`, 정확히 300초부터 CATCHUP. 기존 5분 관측 주기 기반 운영 출처 분류이며 threshold/feature/label 최적화가 아니다. 연구 POLICY와 REST 수집은 유지했다.
- 원래 48건 evidence의 모든 기존 signal 값을 검증하여 LIVE 8 / CATCHUP 40 migration 완료. `data/forward_scanner_v4_before_source_1790866337414810500.db`에 백업. signals 기존 열, feature/outcome, candle/config/state/jobs/pages 값 hash가 전후 동일하다. 결과 `reports/forward_scanner_v4_source_migration.json`.
- 기본 통계는 LIVE only. 실행 출력에는 LIVE/CATCHUP/ALL을 구분하며 API `statistics(db,'ALL')`, CLI `--source ALL`을 명시해야 전체를 본다. 과거 replay 회귀검사는 ALL을 사용한다. catch-up은 삭제하지 않고 복구/결과 평가를 유지한다.
- session 시작/종료·restart/중단, cycle 시각·watermark·backlog·API 오류를 추가 저장한다. 과거 세션 이력은 복원할 수 없고 신규 실행부터 기록한다. 강제 종료 시 알 수 없는 종료 시각을 추정 기록하지 않는다.
- 이번 작업에서 migration/stats/tests만 실행하고 API 및 장기 scanner는 실행하지 않았다. 재개: `python -m coin_analysis.forward_scanner_v4 --mode run --db data/forward_scanner_v4.db` (init 재실행 금지).
- 수정 진입점: `forward_scanner_v4.py`, 새 `forward_scanner_v4_operations.py`. 자세한 운영 정책은 `docs/forward_scanner_v4.md`.
- 기존 114개 테스트 재확인 후, 새 분류 경계/기본 통계/세션 중단·재시작/API 오류/migration 보존·재실행·rollback/재시작 catch-up 테스트 8개를 추가했다. **전체 122개 통과**. 실제 네트워크 테스트는 이번에 실행하지 않았다.

## 최신 중간 점검 — 2026-10-01 23:37:11 KST

- `data/forward_scanner_v4.db`의 consistent memory snapshot을 read-only로 검사했다. 실행 중 scanner를 중단/재시작하지 않았으며 API 호출과 코드/정의 변경 없음.
- 48 signal / 14시장. L1 SUCCESS 3, FAILURE 38, PENDING 0, UNKNOWN 7 → 완결 3/41 **7.32%**. L2 SUCCESS 4, FAILURE 33, PENDING 0, UNKNOWN 11 → 4/37 **10.81%**.
- **48건 중 40건이 5분 초과 탐지 지연**, 중앙값 5시간 29분 43초, 최대 21시간 17분 13초. 과거 구간을 뒤늦게 복구한 관측이 많아 전체를 당시 실시간 포착된 신호로 간주할 수 없다. 지연 원인은 DB만으로 특정할 수 없다.
- L1 성공 ICX 2건/TRUMP 1건. L2 성공 4건 모두 ICX. 모든 feature 비교는 성공 표본 3~4건으로 INSUFFICIENT_SAMPLE. L1은 세 관찰 후보 성공군 중앙값이 높으나 L2 상대강도는 반대 방향.
- 중복 0, 현재 봉 기준 cluster 재구성 48건 일치, 저장 feature 재계산 일치, 완료 outcome/목표 시각/최대 수익률 일치. 두 snapshot 사이 feature 및 terminal outcome 변경 없음.
- 과거 전체 transition/feature hash 감사 이력은 없어서 전 생애 불변성·모든 재시작 과정 자체를 증명할 수 없다. 현재 상태와 trigger 및 재계산 일관성을 확인한 것이다.
- 본 기간 평균 coverage 65.03%, 없는 분봉 50,064분. 정상 API page 증거상 미확인 구간 0분. 미래 결측이 UNKNOWN과 일치. snapshot 시 수집 job 1건은 실행 중이며 last_error는 없었다.
- 상세: `reports/forward_scanner_v4_interim_20261001.md/.json`. 이번 단계에서 조건 탐색/최적화는 하지 않았다. 다음 운영 검토에서는 실시간 탐지와 지연 복구 표본을 혼동하지 말아야 한다.

## 연구 흐름

### 2026-10-01 탐지 지연 원인 조사 (동작 변경 없음)

원래 48건은 catch-up batch 2개 각 20건과 t+12초 live-compatible 8건으로 구분됐다. batch 시각은 9/30 22:45:13 및 10/1 22:07:13 KST. 공통 51시장 page cutoff에 각각 21시간50분/21시간26분 공백이 존재하며, `last_observation`부터 과거 t 전체를 처리하는 현재 코드가 과거 signal을 생성한 직접 경로다. 초기 warmup(start 이전) 신호가 섞인 것은 아니다. 프로세스 중단/절전/HTTP 오류 중 근본 운영 원인은 session/page 수신 감사 로그 부재로 확정 불가. 정상 signal의 12초 지연으로 수십 시간 backlog를 설명할 수는 없다.

제안만 함: source_mode/session/backlog 경계와 운영 시각 로그 추가, live/catch-up 통계 구분 및 지속 운영 감시. 코드/DB/정책 변경과 API 호출/장기 실행 없음. 상세 `reports/forward_scanner_v4_delay_causes_20261001.md/.json`, 시장별 state `reports/forward_scanner_v4_delay_state_20261001.json`.

- 초기/V1: 거래대금·추세 조건으로 급등을 미리 찾는 접근의 성과가 부족하여, 이미 상승한 가격 사건의 직전 공통점을 조사하는 방식으로 전환했다. `archive/surge_event_miner_v1.py`는 과거 접근 참고용이다.
- V2: 가격만으로 A(+10%/60분), B(+20%/6시간) 사건을 정의하고 사전 feature와 matched control을 비교했다. 사후 저점 t0, 중복 episode, 관측 품질 대칭화와 최소 유효 표본을 개선했다. 약 446만 봉 기존 DB의 공백을 대규모 호출로 메우는 계획은 채택하지 않았다.
- 새 research dataset: 별도 `research_market_v1.db`에 50알트+BTC의 14일과 buffer를 수집. 거래수량이 아닌 **거래대금(trade value)** 을 사용하고 없는 분봉은 보간하지 않는다.
- V2 실제 결과: A quality-eligible matched 53쌍, B 15쌍. 최근 고저폭의 차이는 있었지만 FLOCK 25/53 쏠림과 사후 t0 편향이 존재했다.
- V3: 사후 t0 대신 5분 달력 observation, 미래 label을 분리했다. matched 비교 → 전체 observation 절대 발생률 → cluster 첫 signal 분석 → 독립 기간 validation을 진행했다. 30분 range >=4%를 동결했다. 더 이상의 과거 threshold/feature 탐색은 중단했다.
- V4: 동일 정책을 실시간으로 기록하는 forward 관찰기. 주문·점수·ranking은 없다.

## Discovery / validation 기준 결과

|지표|Discovery|Validation|
|---|---|---|
|본 기간 KST (종료 제외)|2026-09-01 ~ 09-15|2026-09-15 ~ 09-29|
|DB|data/research_market_v1.db|data/research_market_validation_v1.db|
|총 candles (buffer 포함)|691,421|724,694|
|range 유효 observation|30,305|43,170|
|4% signal cluster|522|455|
|L1 성공/유효|44/434 = 10.14%|29/373 = 7.77%|
|L1 baseline / cluster lift|3.22% / 3.15x|0.94% / 8.28x|
|L2 성공/유효|27/357 = 7.56%|13/313 = 4.15%|
|L2 baseline / cluster lift|1.59% / 4.76x|0.38% / 10.82x|

Validation 최종 **PARTIAL**: 두 label의 lift는 유지됐지만 L2 성공 13건은 동결된 20건 기준 미달이다. L2의 FLOCK+CPOOL 성공은 9/13(69.23%). FLOCK 제외 lift는 L1 9.52x/L2 10.74x, 시장 동일가중 lift는 2.65x/2.39x였다. 첫 6시간 제외 결과도 PARTIAL(L1 29/367, L2 13/312).

Discovery future buffer가 validation 첫 6시간에 겹쳤고 동결일도 validation 시작 이후다. 따라서 완전한 전향 검증이라고 표현하지 않는다. 자세한 근거: `reports/forward_surge_v3_independent_validation.md/.json`. 원본 두 DB와 정책 해시는 해당 보고서에서 전후 동일 확인.

## 절대 변경하지 않을 연구 정의

- 확정 1분봉 기반, UTC **5분 간격** observation. API는 매분 polling하지만 매분 signal 정책이 아니다.
- 최근 30분 range = `(highest_high / lowest_low - 1) * 100`, **>=4%**.
- range<4가 관측된 뒤 최초 >=4에서 한 signal. 유지 중 중복 금지. NULL range는 reset으로 보지 않는다.
- L1: signal 확정 종가 대비 이후 30분 high +5% 이상.
- L2: signal 확정 종가 대비 이후 60분 high +10% 이상.
- 미래 구간이 완전해야 SUCCESS/FAILURE. 일부 hit가 보여도 미래가 불완전하면 제외한다. 분봉은 임의로 가격/거래대금 0 등으로 채우지 않는다.
- baseline과 cluster 성공률의 분모는 다르다. 서로의 lift를 혼동하지 않는다. 고가 도달률은 실제 체결 수익률이 아니다.

2차 관찰 후보는 **15분 range, 30분 range, 알트 대비 60분 상대강도** 세 개뿐이다. 성공군에서 더 높은 방향은 있었지만 L2 표본 부족 등으로 조건으로 채택하지 않았다. threshold/조합을 새로 탐색하지 않는다.

동결 파일: `docs/forward_surge_v3_validation_policy.json`, `docs/research_market_validation_v1_manifest.json`.

## V4 구현 위치와 상태

- `coin_analysis/forward_scanner_v4.py`: 주 관찰기. V3 feature와 collector Client/200봉 pagination/rate limit/retry 재사용.
- `docs/forward_scanner_v4.md`: schema, 상태 머신, 실행 명령 상세.
- DB 기본값 `data/forward_scanner_v4.db`. 기존 연구 DB를 입력/목적지로 혼용하지 않는다. 현재 작업에서 장기 DB를 초기화하거나 장기 scanner를 실행하지 않았다.
- 핵심 테이블 minute_candles/signals/signal_features/signal_outcomes/scanner_state. 추가 scanner_config/collection_jobs/collection_pages.
- JSON에 feature/flags와 세 관찰 후보를 고정 저장. signal 및 feature UPDATE 금지, SUCCESS/FAILURE UPDATE 금지.
- 6시간 warmup. 초기 진행 중인 cluster는 left-censored로 억제하고, 관측된 below4를 본 뒤부터 새 signal 허용.
- 신호/feature/state 한 transaction, page/cursor 한 transaction, OS single-writer lock. 재시작은 기존 config 그대로 이어간다.
- 마감 전 PENDING. 마감+10분에도 불완전하면 UNKNOWN. 나중에 실제 데이터가 들어올 때만 재평가 가능. 완료 결과 재계산 금지.
- 재시작으로 뒤늦게 발견한 signal은 detected_at/delay_seconds를 보존한다. 실제 당시 전달된 신호라고 취급하지 않는다.

## 테스트와 실제 smoke

작업 전 전체 자동 테스트 **111개 통과** 확인. smoke opt-in/시간 한도/시장 범위 테스트 3개 추가 후 **전체 114개 통과**. 기존 suite에 간헐적인 SQLite ResourceWarning이 있으나 실패는 없었다.

- V4 단위 테스트는 최초 cluster/reset/NULL/미래 변경·삭제 leakage/재시작/PENDING/UNKNOWN/중복/DB 보호/차단 중단을 포함한다.
- offline replay: BTC/CPOOL/FLOCK/NEAR/ENA, 2026-09-15 하루, 중간 DB 재연결. 18 signal 및 feature/outcome이 동일 소규모 V3와 일치. `reports/forward_scanner_v4_replay.json`.
- 실제 API smoke 전용: `coin_analysis/forward_scanner_v4_live_smoke.py --execute-live`. BTC/ETH/XRP만, 최대 **20회(재시도 포함)**, 부모 프로세스 hard limit **180초**. 실제 scanner의 장기 run 모드는 호출하지 않는다.
- smoke는 별도 `data/forward_scanner_v4_smoke_<시각>.db`에 기록. 실제 첫 page 후 DB를 닫고 다시 열어 cursor 재개, 같은 cutoff 재처리 무호출/행수 동일, 다음 분 수집, timestamp/중복/상태/종료를 확인한다.
- 실제 결과 원본은 **`reports/forward_scanner_v4_live_smoke.json`**. 호출별 Remaining-Req, 응답수, status, 지연과 재시도 수 포함. 아래 실행 결과 항목을 함께 확인한다.
- 자연 signal이 없으면 PENDING의 실제 생성/장기 outcome 완료는 검증하지 못한다. 인위적 signal을 live DB에 넣지 않는다. 이 경로는 합성 자동 테스트로 확인하며 live 성공으로 과장하지 않는다.

### 2026-09-30 실제 실행 결과

- KST 00:37:32 시작, 약 **33.37초**, **HTTP 9회**, retry 0, 모두 200 응답.
- BTC/ETH/XRP 각 358봉, 총 **1,074봉**. 다음 분 polling에서 3봉 추가.
- 실제 첫 page 중단 후 disk DB 재연결/cursor 재개 성공. 같은 cutoff 재처리는 호출/행 추가 없이 동일.
- timestamp 이상 0, 중복 0, SQLite integrity ok, 수집 오류/미완료 job 0.
- Remaining-Req sec 4~9 관측. 연속 요청 시작 간격 최소 약 0.150초. 실제 429/418은 발생하지 않았으며 차단/backoff 경로는 합성 테스트 범위다.
- signal 0건으로 정상. live PENDING 생성 및 30/60분 outcome 완료는 미검증. 소규모 수집 smoke 통과이지 장기 안정성 또는 성과 승인 아님.
- scanner worker 정상 종료 및 OS 프로세스 목록에서 잔여 V4 Python 프로세스 없음 확인. discovery/validation DB hash 동일.
- DB: `data/forward_scanner_v4_smoke_1790696252.db`. 보고서: `reports/forward_scanner_v4_live_smoke.json` 및 `.md`.
- 운영 판단: **감독하 제한 운영을 시작할 수 있는 수준**. 장기간 무인 운용 안정성은 아직 입증되지 않았다. 사용자의 실행 요청 전에는 시작하지 않는다.

## REST 장기 운영상 남은 위험 (개선 구현하지 않음)

1. 51시장 × 매분 = 약 **73,440 HTTP 요청/일**, 초기 warmup 약 102회 및 retry/backlog 추가. 매 요청 최대 200봉이므로 정상 운영에서는 최근 데이터 중 상당수를 반복 전송받는다.
2. 순차 polling·timeout/backoff로 관측 시점이 지연된다. 5분 관측 자체의 대기와 처리 지연도 존재한다. HTTP 429/418 미발생 smoke는 실제 차단 회복을 검증한 것이 아니다.
3. 한 시장의 수집 오류가 전 시장 watermark를 멈춘다. 재시작 후 뒤늦은 신호는 당시 실시간 관측과 구분해야 한다.
4. 무체결 분으로 feature/label이 NULL/UNKNOWN이 될 수 있다. 3시장 smoke에서는 알트 peer가 부족하여 alt relative strength NULL이 정상이다.
5. DB·page 기록이 계속 커지고, UNKNOWN outcome 재검사 비용도 누적된다. 장기간 디스크/시간/메모리 안정성은 아직 미검증이다.
6. stats 명령도 동일 single-writer lock을 요구한다. 실행 중 통계는 scanner가 출력하는 로그로 본다. 별도 원격 모니터링/자동 재시작 서비스 없음.

## 아직 하지 않은 것 / 다음 단계

하지 않음: 장기 forward 운용, WebSocket 전환, REST 최적화, 자동 재시작 배포, 신호 조건 추가, 자동 성능 판정, TP/SL, 주문/자동매수, ML/점수/ranking.

다음: 실제 smoke 결과와 위험을 사용자에게 보고 → **명시적 요청 후** 고정 universe/새 forward DB로 감독하에 제한 운영 시작 → 요청 수·지연·오류·디스크·UNKNOWN 비율 점검 → 충분한 forward 표본을 누적한 뒤 동결 규칙으로만 보고. 과거 결과에 맞춰 threshold를 바꾸지 않는다.

## 새 작업 시 절차

이 문서 → 해당 상세 문서 → git diff/현재 코드 순으로 확인한다. 기존 완료 작업을 재작성하지 않는다. `python -m unittest discover -s tests`로 검증하며 실제 네트워크 smoke는 자동 테스트 suite에서 절대 실행하지 않는다. 결과나 운영 상태가 달라지면 이 문서를 갱신한다.
