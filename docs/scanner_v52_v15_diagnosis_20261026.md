# CHIO COIN SCANNER — V15 기준 V5.2 평가 0 원인 진단

2026-10-26 KST. **진단만 수행했다. 스캐너·UI·탐지 규칙·BAT·DB를 수정하지 않았다.** 사용자가 실행한 V15 프로세스를 종료하거나 재시작하지 않았고, 이번 진단의 신규 거래소 API/NTP 호출은 0회다.

## 결론

1. **V15와 V5.2는 서로 다른 탐지 전략이다.** 현재 V5.2 대시보드는 V15의 점수 탐지기를 실행하지 않고 V4의 30분 range/cluster 기록기를 실행한다. V15에서 신호가 보인다고 같은 시각 V5.2에서도 동일 신호가 나와야 하는 관계가 아니다.
2. 당시 전체 시장 V5.2의 `evaluated=0`에는 **독립적인 두 차단 조건**이 있었다. 최초 신호 격자 전에 종료했고, 미완료 초기 수집 job들 때문에 거래소별 공통 watermark도 6시간 전에서 멈췄다. **시간만 늘리는 설명으로는 부족하다.**
3. **엔진 호출 연결 누락은 코드와 저장 실데이터 재현에서 발견되지 않았다.** 동일 과거 입력에서 기존 V4 수집/평가 경로와 V5.2 평가 경로는 각각 신호 7개를 저장했고, 신호·feature·outcome·state·분봉 테이블의 행 수와 값 hash가 전부 같았다.
4. 작은 실제 V5.2 시험은 WS 분봉을 DB에 저장했으나 첫 신호 시각의 최근 30분 중 **21:24 봉 1개가 빠져 29/30**이었다. 전체 시험은 WS 확정 봉이 0개다. 이 전체 시험의 원시 WS frame·정확한 shard 구독 시각은 남아 있지 않아, **WS 확정 봉 0의 세부 원인을 독립적으로 확정할 수 없다.**
5. V15의 과거 1,761신호 DB, 현재 V4의 163신호 DB, 과거 V5.1 보고서의 215신호 DB는 구분해야 한다. 현재 163개 파일은 2026-10-08 보존본과 바이트 hash가 같고, 215개 보고서의 파일 hash와 다르다. **215→163으로 바뀐 외부 파일 선택/이동/복원 경위는 미확인**이다. 이번 조사에서 삭제나 복원은 하지 않았다.
6. **현재 사용자 V15의 신규 탐지·저장도 확인했다.** 조사 초반0개였던 archive DB가23:06:51 읽기 전용 확인에서 **5신호·가격 이력88개**로 증가했다. 사용자 스캐너를 그대로 둔 상태의 실제 기록이며 진단 코드가 만든 자료가 아니다.

## 1. 정상 작동 후보 V15가 실제 수행하는 일

기준 파일은 [archive/scanner_v15.py](../archive/scanner_v15.py)이다. 전체 모듈을 import하거나 재실행하지 않았다. 파일에는 top-level SQLite 연결, HTTP preload, thread 시작, 무한 loop가 있어 import도 실제 실행을 일으킨다.

| 단계 | 코드 위치·동작 | 확인된 범위 |
|---|---|---|
| DB | `DB_FILE` 58행, top-level connect 60행, `init_database()` 72행 | 상대 경로 `crypto_scanner.db`. SQLite 테이블 생성/업그레이드·commit |
| 시장 목록 | `get_markets()` 396행 | UPBIT/BITHUMB 공개 `/v1/market/all`, KRW 전체. `PRELOAD_COUNT=50`은 전체 WS 구독 수 제한이 아님 |
| 과거 자료 | `confirmed_preload_points()` 442행, `load_*_candles()` 472/538행, `preload()` 604행 | 각 거래소 성공한 최대 50시장에 최근 최대 120봉 preload. UTC 확정 봉의 종가·native KRW 거래대금, 공백 뒤 연속 tail만 사용 |
| WS | `*_open()` 2698/2841행, `*_message()` 2734/2877행, `run_*()` 2983/2999행 | 각 거래소 trade 스트림. 현재 가격과 `price × volume` 거래대금 갱신 |
| 분 단위 기록 | `finish_minute()` 724행 | 거래소 기준 새 분 메시지에서 가격·거래대금 deque 갱신. raw OHLCV 테이블을 저장하는 구조는 아님 |
| 급등 탐지 | `analyze()` 2335행, `calculate_score()` 1173행 | 5/15분 가격 상승, 거래대금 배수 각 ≥2, score ≥60, 거래소·시장별 30분 cooldown |
| 별도 전조 | `is_prepump_candidate()` 2136행, `evaluate_prepump()` 2321행 | `-3 < p15 <= 2`, r5≥20/r15≥20/r60≥10, 별도 PRE-PUMP 테이블·cooldown·추적 |
| 저장 | `save_signal()` 1352행, `save_price_history()` 1423행 | `signals` INSERT/commit, 후속 가격 이력. PRE-PUMP는 `prepump_events`/`prepump_tracking`에 별도 저장 |
| 메인 loop | 3104행 이후 | sleep 10초 → `analyze()` → 후속 신호·PRE-PUMP 추적. 기존 paper-trade 추적도 포함되지만 실제 주문 경로를 이번에 실행하지 않음 |

`is_real_surge_candidate()` 함수가 존재하지만 실제 `analyze()`는 자체 조건문을 사용한다. 점수 함수의 60분 배수는 선택적인 가산점이며, 일반 급등 신호에 120분 이력이 무조건 필요한 것은 아니다. PRE-PUMP는 r60을 요구한다. MA/골든크로스 값은 현재 코드에서 계산·출력하며 별도 필수 통과 조건으로 사용하지 않는다.

**실행 관찰과 저장 증거를 구분했다.** 조사 중 PID 28300/26448의 `python ... .\scanner_v15.py` 실행을 확인했고 종료/제어하지 않았다. 상대 명령행만으로 OS의 현재 작업 디렉터리까지 확정하지는 못했다. 새 `archive/crypto_scanner.db`는 조사 초반 `signals=0`이었지만 **23:06:51에는5신호·가격 이력88개**였다. 실제 신규 저장을 확인했다. BITHUMB ZRX22:39:08(score60), UPBIT BABY22:43:39(score60), BITHUMB BABY22:47:29(score65), SHIB22:56:00(score65), PCI23:02:01(score65)다. 이5개는 모두 r60=NULL인데도 일반 급등 조건을 통과했다. [현재 사용자 실행 저장 증거](../reports/scanner_v52_diagnosis_20261026/user_v15_live_storage.json). 진단 중 이 DB에 INSERT/UPDATE하지 않았다.

과거 `C:\dev\Coin_api\crypto_scanner.db`에는 실제 **1,761신호**, **305 paper rows**와 가격 이력이 있다. 마지막 신호는 2026-09-09 23:50:21 UPBIT KRW-LA, score 60이다. 현재 archive 공식으로 재계산 가능한 INTEGER score 382개는 저장값과 모두 같았다. 나머지 1,379개 score는 SQLite BLOB이므로 의미를 임의 해석하지 않았다. 과거 모든 행이 현재 파일 revision에서 생성됐다고 단정하지 않는다. [저장 증거](../reports/scanner_v52_diagnosis_20261026/legacy_storage_evidence.json), [score 대조](../reports/scanner_v52_diagnosis_20261026/legacy_score_check.json).

## 2. 실행 경로와 데이터 계약 비교

| 항목 | 사용자 V15 직접 Python | 과거 V4/V4.3 CLI·BAT | 현재 V5.2 웹 시작 |
|---|---|---|---|
| 진입 | `python scanner_v15.py` | V4 `--mode run`, 또는 과거 BAT `_scanner → control.start → forward_scanner_v43` | 웹 POST → `Operations.request` → `desktop.start_scanner` → 별도 `_scanner` manager → `control.start` |
| manager/worker | 별도 manager 없음. 메인 loop+WS thread 2개 | V4는 자체 loop, V4.3는 supervisor와 worker | manager가 `forward_scanner_v52 --execute-live` supervisor 생성 → 같은 모듈 `--worker` 생성 |
| 탐지 | `analyze()`/`calculate_score()`/PRE-PUMP | `forward_scanner_v4.process_observations()` | `Bridge.evaluate()` → 동일 `process_observations()` |
| API | UPBIT/BITHUMB market/candle REST, public v1 trade WS | V4는 UPBIT REST, V4.3는 양 거래소 REST | 같은 양 거래소 공개 REST 목록/제한 candle + trade/ticker WS |
| 시장 | 받은 KRW 전체 WS, preload 성공 각 50시장 | 원본 DB manifest 51시장; V4.3 고정 각 BTC/ENA/ETH/FLOCK/SAND | 동적 전체 KRW, 당시 787쌍 등록, 공식 상태로 14쌍 제외 |
| 입력 | 메모리 종가 deque·거래대금 deque·현재 틱 가격·현재 분 거래대금 | SQLite `(market, ts UTC초, open, high, low, close, trade_value KRW)` | WS → 확정 OHLCV로 변환 → 동일 SQLite 계약 |
| 규칙 | 상승 방향+거래대금 배수+점수60+30분 cooldown | 30분 high/low range≥4%, 관측된 below4 후 최초 cluster | V4와 같음. V15 score를 호출하지 않음 |
| 주기 | 약10초마다 검사, 현재 분 거래대금 포함 가능 | 매분 수집, UTC5분 신호 관측 | 약2초마다 flush/evaluate 호출하되 신호 관측은 같은 UTC5분 격자 |
| 저장 DB | **프로세스 CWD** 아래 `crypto_scanner.db` | V4 `data/forward_scanner_v4.db`; V4.3 별도 runtime의 upbit/bithumb DB | `data/scanner_v43_live/console_<launch_id>/upbit.db`, `bithumb.db` |
| 기존 신호 조회 | legacy 스키마 signals, 별도 전조·paper 테이블 | V4 schema `signal_id`, `signal_time`, `source`, feature/outcome | 웹 catalog는 V4 archive와 최근 runtime DB. **V15 crypto_scanner.db는 조회 대상 아님** |

근거: [desktop 진입](../coin_analysis/scanner_desktop_v50.py) `main` 239/`start_scanner`129행, [manager](../coin_analysis/scanner_control_v410.py) `start`312/child347행, [웹](../coin_analysis/scanner_dashboard_v50.py) `Operations.request`424/`catalog`53행, [V4.3](../coin_analysis/forward_scanner_v43.py) `worker`230행. `start_scanner_only.bat`도 현재는 같은 V5.2 manager로 연결된다. 과거 V4.3 고정 cohort 직접 CLI는 별도로 남아 있다.

V15 직접 실행은 상대 DB 경로 때문에 `C:\dev\Coin_api`에서 실행하면 그 폴더의 DB, `C:\dev\coin_api-1\archive`에서 실행하면 archive의 DB를 연다. 파일명이 같아도 같은 DB가 아니다. 현재 BAT는 `pushd "%~dp0"`로 프로젝트 루트를 고정하며, V5.2의 DB는 코드의 `DATA_DIR`에서 정한 새 runtime이다.

## 3. V5.2의 WS → 탐지 연결 추적

실제 코드의 호출 흐름은 다음과 같다.

```text
Streams.receive (116행): recv → bounded queue MESSAGE
worker (443행): bridge.message(raw, local_receipt)
Bridge.message (215행): type/시각/ID/품질 검사 → 미확정 bars
worker (459행): bridge.flush(now)
Bridge.flush (282행): 확정 minute_candles + candle_receipts + ws_candles
worker (460행): bridge.evaluate(now)
Bridge.evaluate (325행): V4 process_observations → evaluate_outcomes → 기존 metrics
V4 process_observations (121행): range/cluster → signals INSERT(145행)
```

단순 ticker·snapshot 수신은 분봉·탐지 입력이 아니다. REALTIME trade, 온전한 연결 분, 기존 5초 settle, 중복·역순·늦은 데이터 검사를 통과해야 한다. 정지/제외 시장과 미완료 collection job의 watermark 처리를 따로 수행한다. **소켓 연결/ACTIVE와 탐지 평가 완료는 다른 단계다.**

작은 실제 runtime의 각 DB에서 `ws_candles=2`가 원천 `minute_candles`와 join된다. 실제 WS 종가는 UPBIT BTC 107,170,000/ETH 3,111,000, BITHUMB BTC 107,208,000/ETH 3,111,000이며 봉 시작은 21:25:00이다. 다만 최초 신호 격자 21:25가 쓰는 구간은 그 이전 봉이다. **이 WS 봉이 실제 운전 중 신호 feature에 사용됐다고까지 주장할 수 없다.** 다음 격자까지의 데이터가 없었다. [실제 입력 근거](../reports/scanner_v52_diagnosis_20261026/input_quality_evidence.json).

전 시장 실제 운전 로그에는 ENGINE 신호 emit 행이 없지만, 그 emit은 매 함수 호출을 기록하는 로그가 아니다. 대부분 알트 `last_observation`이 초기 15:25에서 15:30으로 전진한 DB 흔적과 오프라인 spy가 있으므로 **ENGINE 로그 0을 함수 호출 0으로 해석하면 안 된다.** 로그만으로 당시 정확한 호출 횟수를 소급 복원할 수는 없다.

## 4. 최소 시간·자료 조건

V4/V5.2의 핵심 게이트는 [forward_scanner_v4.py](../coin_analysis/forward_scanner_v4.py) 121~126행이다.

```python
watermark = MIN(scanner_state.verified_until)  # BTC 포함, 거래소 내 전체 시장
end = floor_to_5m(min(watermark, floor_to_minute(now)))
first = min(alt.last_observation) + 300
if first > end:
    return
```

- 실제 신호 저장은 `t >= scanner_config.start`에서만 허용한다. 새 dataset은 다음 UTC5분 격자를 start로 잡는다.
- 최근30분 **연속 실제 30봉**의 high/low가 있어야 range가 유효하다. 한 분이라도 없으면 `Series.high_low()`는 NULL을 반환한다. 가격·거래대금 0 또는 직전가로 메우지 않는다.
- range<4를 관측해 cluster가 비활성화된 뒤 처음 range≥4일 때 저장한다. 초기 active=NULL에서 이미 급등 중이면 억제한다. NULL range는 cluster reset이 아니다.
- 6시간은 `initialize()`의 **과거 조회/warmup 범위**다. REST로 과거 봉을 채우면 실제6시간을 기다릴 필요는 없다. 반대로 시간만 흘러도 자료·watermark가 준비되지 않으면 시작할 수 없다.
- cold WS만 사용한다면 최소30분 연속 봉과 이전 below4 관측이 필요하다. 첫 유효30분이 below4라면 다음5분 격자에서의 신호까지 적어도35분의 연속 자료가 필요할 수 있다. 이력 preload가 있으면 다르다.
- 일부 장기 feature가 NULL인 것은 별도 flags이며 모든 feature의 완전성이 신호의 추가 필수 필터는 아니다. L1/L2 미래30/60분 자료는 **신호 발생 조건이 아니라 후속 label 완성 조건**이다.

V15는 일반 급등에서 p5/p15, r5/r15와 점수를 요구한다. r15에는 거래대금 값 30개가 필요하며 `get_volume_history()`는 양수인 현재 분 거래대금도 포함한다. 약29개 확정값+현재 분 또는30개 확정값이 최소 입력이 될 수 있다. PRE-PUMP의 r60에는120개 값이 필요하다. preload가 된 종목은 새 실행에서 다시 그 시간을 기다리지 않는다. **다른 시장의 초기화 실패가 준비된 시장까지 막는 공통 watermark가 없다.**

## 5. 평가 0 원인별 판정·재현

| 원인 후보 | 판정 | 증거·재현 |
|---|---|---|
| 최초 관측 시각 미도달 | **확정** | 전체 worker 21:27:53.683~21:29:41.615. `signal_start=21:30:00`, 18.385초 먼저 종료 |
| 초기 수집/verified 입력 부족 | **확정** | UPBIT 미완료 job289/298, BITHUMB483/489. 양쪽 MIN verified=**15:30:00**, 당시 최신 신호 격자는21:25 |
| 시간만 늘리면 진행 | **반증** | 실제 DB의 메모리 복제본에서 원래 종료시각과 +1시간으로 `Bridge.evaluate`를 호출해도 watermark·state·평가0이 그대로. 연구 panel 로드도0회 |
| 한 미초기화 시장의 전체 정지 효과 | **재현 확인** | 실데이터가 누적돼 원천1,861봉이 있어도 SAND 초기 job1개를 남기면 1시간 동안 평가0/신호0. 실제 저장 페이지2개로 그 job을 완료한 뒤 평가4/신호1 |
| 작은 실제 시험의 range 입력 결측 | **확정** | 각 거래소 BTC/ETH의 최초 21:25 격자에서21:24 봉 부재,29/30. 평가 시도 각알트1쌍이나 유효30분0 |
| 엔진 호출/저장 연결 누락 | **발견되지 않음** | 명시적인 worker→Bridge→core 호출이 있고, 동일 실데이터 old/V52가 각각7신호·7feature·14outcome 저장. core5테이블 값 hash 동일 |
| 시계 실패/REST 오류가 이 시험 전체를 차단 | **근거 없음** | 해당 전체 시험 시계3gate PASS,45 HTTP 모두200, 종료 STOP_REQUESTED. 원천 last_error 없음. 이전 V5.1 시계 실패와 별개 |
| 전 시장 WS 확정 봉0의 정확한 세부 원인 | **미확정** | 저장0 자체는 확정. raw frame·정확한 구독 since가 없어 당시 aggregator를 그대로 재현할 수 없음. 아래 시간 증거의 한계 참조 |
| V15와 규칙/주기/입력이 달라 결과가 달라짐 | **확정** | 동일 저장 봉 투영에서 V15 점수신호1, V4/V52 range신호7. 규칙을 변경해 맞추지 않음 |

### 요청 예산과 전체 초기화의 구조적 불일치

[V5.2 worker](../coin_analysis/forward_scanner_v52.py)에서 `Bridge.subscribed()`는 각 시장의 과거 범위 수집 job을 만든다. `Bridge.flush()` 311행은 **pending job이 없는 시장만** verified를 전진시킨다. core는 그 값의 전체 MIN을 사용한다. 데이터가 DB에 생긴 것과 조회 범위가 검증된 것은 별개다.

당시 적격773쌍을 모두 초기화하려면 극단적으로 시장마다1페이지만으로 끝나도 최소773회의 candle 요청이 필요하다. 목록 요청은 별도다. 원래6시간을 dense 200봉/page로 가져오면 보통2page/쌍이 더 필요하다. **50 HTTP 시험과 기본 scanner-only 180 HTTP는 최소1page/시장 계산에도 부족하다.** 해당 worker의 HTTP 예산은 도달 후 새로 지급되지 않고 V5.2 resume도 없다. 따라서 같은 새 전체 dataset·같은 예산에서 단순히 WS 실행 시간만 늘려 전 시장 평가가 반드시 시작된다고 설명할 수 없다. 연구 기준/한도를 이번에 완화하지 않았다.

실제 종료 DB 복제본 재현은 기존 입력과 state를 보존한 채 시각 인수만 +1시간으로 바꾼 실험이다. 이 재현의 시각은 시장 관측이 아니며 실제 운전 시간을 부풀리지 않는다. pending-job 실험도 private DB에서 실제 과거 봉·페이지로만 수행했고 운영 메타데이터를 우회 수정하지 않았다. [재현 원문](../reports/scanner_v52_diagnosis_20261026/reproduction_results.json)의 `runtime_causal_replay`, `pending_job_gate`.

### WS 0봉에 대한 이전 설명의 검증 한계

이전 보고서에는 “첫 완전 분이 닫히기 전에 STOP”이라고 기술돼 있다. 이번에는 미처리 초기 job의 end와 `closed_cutoff(since)`를 역대조했다. 8개 shard 모두 초기 end=21:27:00이므로 since는 **21:27:05 이상~21:28:05 미만** 범위다. 이 범위는 분 경계를 걸친다. 가능한 가장 이른 확정은21:29:05로, 실제 종료21:29:41보다 이르다. 따라서 **이 보존 자료만으로 이전 설명을 확정 사실로 재확인할 수 없다.** 실제 since가21:28:00을 넘었다면 이후에야 확정되는 경우와도 일치하지만 이는 조건부 설명이다.

WS raw frame·구독 시각 상세 기록이 없으므로 정확히 어느 조건에서 모든 분봉이 탈락했는지 미확인이다. 연결 누락이나 aggregator 정상 전체를 임의 확정하지 않는다. 작은 실제 WS 봉4개, 기존 합성 callback 테스트, 과거 실데이터의 core 연결 재현은 각각 그 범위의 증거다. [시간 범위 계산](../reports/scanner_v52_diagnosis_20261026/ws_timing_evidence.json).

## 6. 동일 저장 실데이터 비교

재현 원본은 `data/forward_scanner_v4.db`의 실제 저장 봉이다. `mode=ro&immutable=1`, `query_only=ON`으로 읽었다. 평가 구간은 **2026-10-02 00:00~10-03 00:00 KST**, BTC/ENA/ETH/FLOCK/SAND5시장, 원래6시간 warmup을 사용했다. REST 페이지는 저장 봉 값을 그대로 native 필드로 직렬화한 **오프라인 adapter**이며 외부 요청은 아니다.

| 항목 | 기존 V4 경로 | V5.2 경로 | V15 후보 |
|---|---:|---:|---:|
| 실행 함수 | `core.cycle`361회 | `fetch_market`+`Bridge.evaluate`361회 | AST로 추출한 원본 `analyze` |
| 입력 | 저장 확정 OHLCV | 같은 봉/페이지/검증 범위/시각 | 같은 봉의 종가·native 거래대금 연속 tail 투영 |
| 저장 신호 | **7** | **7** | **1**, SAND16:05:05, score75, price72.8 |
| 신호 feature |7|7|V15 스키마의 가격/배수 값|
| L1/L2 행 |14|14|같은 label 정의 없음|
| 신호/feature/outcome/state/분봉 값 hash | V52와 **모두 동일** | V4와 **모두 동일** | 비교 대상 정의가 다름 |

V4/V52의7개 signal ID·시장·시각·range는 원본 DB의 해당 구간/시장7개와도 일치했다. feature hash 동일성은 **두 재현 경로 사이**의 결과다. 원본은51시장 universe, 이번 재현은5시장이므로 원본 전체 peer-relative feature까지 같다고 주장하지 않는다. outcome14행도 두 경로의 동일 시점 결과이며 미래가 미완성인 행은 PENDING 그대로다.

V15는 import 대신 원본 함수 AST만 unchanged로 추출하고 메모리 SQLite에 원래 `save_signal()`/commit을 실행했다. 가격·거래대금은 실제 저장 자료이며 raw tick을 만들지 않았다. 공통5분 시점에서 현재 분 거래대금을0으로 두고 확정 봉 투영을 제공했다. **실제 V15의 10초·현재 틱·현재 분 실행 및 모든 과거1,761신호의 재현은 아니다.** 1대7을 정확도·수익성·성능 우열로 해석하지 않는다.

오프라인 재현 실행: 프로젝트 루트에서 `python -m reports.scanner_v52_diagnosis_20261026.reproduce`. 실제 측정 약23초, 네트워크 차단 guard 포함. [진단 전용 재현 코드](../reports/scanner_v52_diagnosis_20261026/reproduce.py), [결과](../reports/scanner_v52_diagnosis_20261026/reproduction_results.json). 기존 탐지/leakage 관련 테스트 **29개 통과**, [로그](../reports/scanner_v52_diagnosis_20261026/related_tests.log).

## 7. 두 프로젝트 경로·215/163 차이

두 디렉터리는 실제 별도 폴더이며 junction/symlink가 아니다. `git worktree list`에는 `C:\dev\coin_api-1`만 등록돼 있고 `C:\dev\Coin_api`에는 Git 메타데이터·현재 BAT·V5.1 보고서가 없다. 현재 디스크에서 Git 저장소는 coin_api-1, 다른 폴더는 구형 standalone 파일/DB 보관 형태다. 과거에 폴더가 언제 어떻게 이동했는지는 이 사실만으로 단정하지 않는다.

두 폴더의 V15 파일은 바이트 hash가 다르지만 함수 AST 비교상 변경은 preload 검증·loader·WS callback5개뿐이다. 점수·analyze·저장 로직은 같다. `C:\dev\Coin_api\crypto_scanner.db`와 저장소의 `data/backups/v42_preflight_20261024/legacy.db`는 물리 파일 hash가 다르지만 **모든 테이블의 행 값 hash가 같다.** 실제 동일한1,761신호 계보의 자료임을 확인했다. [파일 함수 비교](../reports/scanner_v52_diagnosis_20261026/v15_file_comparison.json), [테이블 값 비교](../reports/scanner_v52_diagnosis_20261026/legacy_logical_comparison.json).

| 자료 | 현재 증거 |
|---|---|
| standalone crypto_scanner | 과거1,761신호, 위 두 위치에서 테이블 값 동일. V4 schema와 다름 |
| 사용자 새 archive crypto_scanner | 조사 초반0 → 최종 확인5신호. 상대 CWD DB가 분리될 수 있음을 보여줌. 현재 사용자가 소유한 untracked 파일을 그대로 보존 |
| 현재 V4 archive |163신호 = LIVE32+CATCHUP131,371,708봉. SHA256 **376c66056b10a012bc917246a29972138106a1cef1c10e13463efc920c54d451** |
| 2026-10-08 V4 복구 보존본 |위 현재 SHA256과 동일,163신호.10/24·10/25 보고서도163을 기록 |
| V5.1 보고서의 archive |215신호 = LIVE44+CATCHUP171. 기록된 SHA256 **528ff08a037364839114369dc2af1385f3a89f61795352fcd544f7bd27d1c78e** |

이는 ALL/LIVE 필터나 거래소 합산으로 생긴 차이가 아니다. **물리 archive 파일 자체가 다르다.** 조사한 두 폴더의43개 `.db` 파일에서215신호 파일은 찾지 못했다. 215개 행 목록 실물이 없으므로 빠진52개 ID를 복원·특정할 수 없다. 파일 선택/복원/이동/다른 환경 원인은 UNKNOWN이다. DB는 `.gitignore` 대상이므로 Git 코드가 같다고 DB까지 같음을 보장하지 않는다.

현재 V5.2 writer는 새 runtime의 거래소 DB를 열고, dashboard archive는 read-only로 읽는다. 이번 V5.2 runtime이 원본163개를215개로 만들거나52개를 삭제하는 코드 경로는 확인되지 않았다. 앞선 V5.2 baseline도 작업 전부터 현재163개 파일 hash였다. 보고서 기록과 실제 파일의 차이를 숨기거나 현재 파일을 덮어써서 맞추지 않았다. [DB 전체 목록](../reports/scanner_v52_diagnosis_20261026/db_inventory.json), [V5.1 과거 보존 기록](../reports/scanner_v51_20261026/completion_checks.json), [10/8 기록](../reports/forward_scanner_v4_wal_repair.json).

## 8. V15 핵심 원리의 재사용 평가 — 이번 작업에서 적용하지 않음

| 원리 | 재사용 판단 |
|---|---|
| 전체 KRW 목록·양 거래소 WS 수집 | V5.2도 이미 사용. 전송 연결의 부재가 이번 core 평가0의 확정 원인은 아님 |
| 준비된 시장부터 독립 검사, 제한된 preload | 초기 준비 비용과 전체 진도 결합 문제를 분석할 참고가 됨. V4의 전체 peer/universe·verified 의미에 영향이 있어 그대로 복사하거나 watermark를 우회할 수 없음 |
| 점수·거래대금 배수·10초/현재 분 신호 | V4와 다른 전략. 규칙을 보존한 동일 기능 대체로 이식할 수 없음 |
| `finish_minute`의 직전가/0 거래대금 유지 | V15에서 덜 엄격하게 자료가 누적되는 차이. V4의 원천 부재=NULL 정책과 다르므로 이식 부적합 |
| legacy DB와 후속 paper 추적 | 현재 V4 분석 스키마와 별개. 과거 기록 보존 대상으로 유지. 연결 기능이나 paper/order 기능을 이번에 추가하지 않음 |

## 9. 보존·미검증 범위

진단 전 해시 기준을 만들고 기존 코드·UI·DB·기존 보고서의 변경을 대조했다. 조사 중 사용자 스캐너 PID28300/26448이 계속 존재함을 확인했다. 그 프로세스에 STOP 파일·신호·종료 명령을 보내지 않았다. 활동 중인 사용자 DB는 짧은 read-only 조회만 했으며, 자연 증가를 정적 파일 변경과 혼동하지 않는다.

새로 작성한 것은 이 보고서, 진단용 offline harness/JSON/log와 연구 상태 문서의 추가 항목뿐이다. 원본 V15·V4/V52 소스, UI, BAT, 정책·기존 DB는 그대로다. [보존 결과](../reports/scanner_v52_diagnosis_20261026/preservation.json). 별도 LIVE 시험·브라우저 조작·사용자 콘솔 개입·Git commit/push는 수행하지 않았다.

미확인: 전체 시험 raw WS 봉0의 정확한 원시 frame 경로, 과거215개 파일의 실물/이동 경위, 전 시장 초기화 완료 후의 장기 운전. 현재 사용자5신호의 raw tick/전체 원천 OHLC는 DB에 없으므로 이5건을 V4에 같은 틱으로 재입력하지 않았다. 과거 실제 저장 OHLCV 비교와 구분한다. 이 미확인 항목은 성공이나 결함으로 임의 판정하지 않았다.
