# V15 관찰용 대시보드 — 실행 구조·DB 호환성 조사 및 설계

작성일: 2026-10-26 KST. 대상 저장소: `C:\dev\coin_api-1`.

## 1. 범위와 결론

**이 프로젝트는 기존 V15 실험 전략의 실행과 저장 결과를 관찰하는 웹 대시보드다. 새로운 탐지·연구 엔진 개발이나 전략 최적화 프로젝트가 아니다.** V15의 유효성은 아직 미검증이다. V10~V12의 성과 부진·폐기 이력은 사용자 제공 배경이며 이번 작업에서 별도 재검증하지 않았다.

이번 작업은 소스 조사, 읽기 전용 DB 조회, 메모리 DB에서 기존 함수 검증, 설계 문서 작성으로 끝낸다. 운영 코드·UI·BAT·V15 원본·탐지 규칙·기존 DB를 변경하지 않았다. V4/V5.2를 V15 대신 시작하거나 주력으로 연결하지 않았다. 스캐너·웹 서버 시작, 실제 API/NTP 호출, 최적화 실행은 모두 0회다.

결론은 다음과 같다.

1. V15는 두 거래소 수집, SURGE/PRE-PUMP 탐지, 신호 당시 지표 저장, 후속 가격 추적을 이미 구현한다. **이 기능들을 그대로 사용한다.**
2. 현재 웹 화면·HTTP 보안은 재사용 후보지만, 시작 버튼은 현재 V5.2를 실행한다. 지금 버튼으로 V15가 시작된다고 안내하면 안 된다.
3. 현재 분석기는 V4 DB 전용이다. V15에는 **기존 DB를 읽는 얇은 조회·통계 계층**이 필요하다. 새 탐지기나 V4 후속 평가 엔진을 연결할 필요는 없다.
4. 원본 DB 이전·통합·스키마 변경은 필요하지 않다. 데이터 출처를 고정 등록하고 읽기 전용으로 분리 조회한다. 캐시가 필요하면 별도 파생 DB만 사용한다.
5. DB에 값이 있다는 사실과 관측이 완전하다는 사실을 구별해야 한다. 특히 추적 지연·누락과 과거 데이터의 버전 출처가 성과 판단의 제한이다.
6. 현재 수동 실행 V15는 관찰 대상이며 대시보드 제어 소유권 밖에 둔다. 향후 시작·종료 기능은 별도 검증 전까지 연결하지 않는다.

이 문서에서 **사실**은 코드/DB/재현 근거가 있는 사항, **설계**는 아직 구현하지 않은 제안, **미검증/추정**은 증거가 부족한 사항이다.

## 2. V15에서 실제 구현된 기능

기준 파일은 [archive/scanner_v15.py](../archive/scanner_v15.py)다. 모듈 전체를 import하면 DB 연결과 시작 코드가 실행되므로 이번 검증에서는 전체 import/실행하지 않았다.

| 기능 | 실제 구현과 근거 | 해석상 제한 |
|---|---|---|
| 종목 목록 | `get_markets` L396: Upbit/Bithumb `/v1/market/all`에서 `KRW-` 전체 수집 | 시작 당시 목록. 현재 실행의 실제 목록 수/수신 수는 DB만으로 확인 불가 |
| 초기 과거 자료 | `load_upbit_candles` L472, `load_bithumb_candles` L538: REST 1분봉, HISTORY=120. `confirmed_preload_points` L442가 확정 시각·가격·거래대금을 검증 | `preload` L604는 거래소별 **성공 50종목**까지. WS 전체 감시를 50개로 제한하는 값이 아님. 실패가 있으면 요청 시도는 50보다 많을 수 있음 |
| 실시간 수집 | `run_upbit` L2983 / `run_bithumb` L2999, 각 daemon WS 스레드 1개. `upbit_open` L2698 / `bithumb_open` L2841이 목록 전체 trade 구독 | 등록·구독 요청·실제 수신·지표 준비 수는 서로 다름 |
| 입력 전달 | `upbit_message` L2734 / `bithumb_message` L2877 → `prices`, `current_volume`, `finish_minute` L724 → `data`, `minute_prices` → `analyze` L2335 | 거래대금은 `trade_price × trade_volume`. 매수량 지표가 아님 |
| SURGE | `analyze`: p5>0, p15>0, r5≥2, r15≥2, score≥60, 가격 존재, 거래소·종목별 30분 cooldown | 실제 함수의 조건을 기준으로 함. 별도 `is_real_surge_candidate`를 주 경로로 오인하지 않음 |
| PRE-PUMP | `evaluate_prepump` L2321: SURGE 필터와 독립. -3<p15≤2, r5≥20, r15≥20, r60≥10, 30분 cooldown | 일반 SURGE와 다른 테이블·지표·추적 지평 |
| PRE-PUMP 유형 | `save_prepump_event` L2149: 첫 WATCH, 72시간 내 재발 HOT, 직전보다 strength가 크면 STRONG | `strength=.45*r5+.40*r15+.15*r60`; SURGE 점수와 혼합 금지 |
| 신호 저장 | `save_signal` L1352: 발생 시각·거래소·종목·가격·점수·p1/p5/p15·r5/r15/r60·reason INSERT+commit | MA/golden cross는 계산·출력되지만 필수 필터가 아니며 신호 테이블에 해당 값 전체가 저장되지 않음 |
| SURGE 추적 | `save_price_history` L1423, `track_signals` L1821: 상대 분별 첫 관측 저장, 5/10/30/60분 결과 | tick/OHLC 전체 저장이 아님 |
| PRE-PUMP 추적 | `update_prepump_tracking` L2269: 약 10초 루프에서 관측 극값 갱신, 3/6/12/24/48/72h 결과 | 상세 장기 가격 시계열 테이블은 없음 |
| 재시작 복원 | `restore_active_signals` L1615, `restore_active_prepumps` L2229 | SURGE는 시작 후 60분 이내 미완료만, PRE-PUMP는 72시간+300초 이내 미완료만 복원. 중단 구간 실가격 복구 기능과는 다름 |
| 기존 가상매매 | `evaluate_v14_entries` L1534, `update_v14_paper_trades` L1569 | 기존 DIP/REBOUND paper 기록. 실제 주문/체결 성과가 아니며 이번에 변경·확장하지 않음 |

점수의 실제 가산 항목(`calculate_score` L1173): r5의 3/5/10배마다 +10, r15의 3/5배마다 +10, r60의 2/3배마다 +5, p1의 0.3/0.7%마다 +5, p5의 1/3%마다 +5, p15≥3% +5. p5<-2% -15, p15≥20% -15, ≥30% 추가 -15, 최종 0~100 clamp다. 이 표는 기존 규칙 설명이며 점수 조정 제안이 아니다.

API 경로는 Upbit `https://api.upbit.com/v1/...`, Bithumb `https://api.bithumb.com/v1/...`, WS는 각각 `wss://api.upbit.com/websocket/v1`, `wss://ws-api.bithumb.com/websocket/v1`이다. 이번에는 호출하지 않았다.

실행 구조: 파일 상단 `sqlite3.connect(DB_FILE, check_same_thread=False)` → `init_database` → 목록 → preload → 복원 → WS 스레드 2개 → 메인 루프에서 `sleep(10)` 후 analyze/track/update. 따라서 정확히 10초마다 실행되는 보장은 없고 처리 시간만큼 늘어난다. V4 manager/worker 구조와 다르다.

최소 입력 조건: `volume_ratio` L1047은 해당 period의 두 구간과 양수 분모/분자가 필요하다. r15는 30개, r60은 120개 거래대금 관측이 필요하고 p15는 15분 전과 비교할 충분한 종가가 필요하다. 일반 SURGE는 r60이 없어도 가능하나 PRE-PUMP는 r60 필수다. preload 성공 여부·거래 발생·분 갱신에 따라 준비 시간이 다르므로 **실행 시간 N분만으로 준비 완료를 보장하지 않는다**.

V15는 현재 분 거래대금도 사용할 수 있고(`get_volume_history` L1012), 거래소 단위 분 전환 시 무거래 종목에 마지막 가격/거래대금 0을 넣으며 여러 분의 공백을 시간 간격만큼 복원하지 않는다(`finish_minute`). 이 기존 입력 의미를 V5.2 확정 봉·중복 제거·결측 차단으로 교체하면 신호가 달라질 수 있다. 이 작업에서는 기존 동작을 유지한다. 저장 결과 분석에 미래 정보가 탐지 당시 특징으로 섞이지 않도록 하는 원칙도 유지한다.

## 3. DB 위치·스키마·실제 데이터

`DB_FILE="crypto_scanner.db"`(L58)는 **스크립트 위치가 아니라 CWD 기준**이다. `C:\dev\coin_api-1`에서 절대 스크립트 경로를 실행하면 루트 DB를 열 수 있고, archive에서 실행하면 archive DB를 연다. 향후 launcher는 실행 파일과 CWD·DB 절대 경로를 함께 고정·기록해야 한다. 자동으로 발견한 첫 DB를 고르면 안 된다.

| 테이블 | 원본 키/내용 | 화면에서 가능한 것 |
|---|---|---|
| `signals` | `id`, naive local `created_at`, exchange/market/score/price, 가격 변화율·거래대금 배율, 5/10/30/60m 결과·극값 | SURGE 목록, 탐지 당시 값, 저장 결과 조회 |
| `signal_price_history` | PK(signal_id,minute), observed_at, price, return_pct | 실제 저장된 상대 분 가격 선 차트, 누락·관측 시각 점검 |
| `prepump_events` | id, level/repeat_count, 가격·지표, strength, previous_event_id | PRE-PUMP 목록·기존 유형/반복 정보 |
| `prepump_tracking` | event_id, 극값·last_seen_at·completed, 3~72h 결과/mfe/mae | 저장 체크포인트·누적 관측 극값. 장기 분봉 차트 생성 불가 |
| `pullback_watch`, `pullback_paper_trades` | 기존 watch·진입·종료·가상 손익 | 원래 paper 결과를 별도 표시. SURGE 가격 변화와 합산하지 않음 |

스키마 목록과 실조회 결과는 [compatibility_results.json](../reports/v15_dashboard_design_20261026/compatibility_results.json)의 `sources`에 있다. 조회 시각/건수는 고정된 검증 증거이며 현재 값과 같을 필요가 없다. 실행 중 DB는 짧은 독립 SELECT들로 읽어 원자적 전체 스냅샷이라고 주장하지 않는다.

- 정적 보존본 `data/backups/v42_preflight_20261024/legacy.db`: SURGE 1,761 / 가격 이력 43,950 / PRE-PUMP 76 / paper 305(CLOSED 190, OPEN 115). 이전 [진단](scanner_v52_v15_diagnosis_20261026.md)에서 `C:\dev\Coin_api\crypto_scanner.db`와 테이블 값 동일을 확인했다. **과거 V14/V15 계열 혼합 가능성이 있으며 전체를 현재 파일이 만든 V15 성과로 귀속할 근거는 없다.**
- 실행 중 후보 DB `archive/crypto_scanner.db`: 최종 검증 시점 건수는 JSON 참조. 앞선 23:29:22 조회에서 SURGE 21 / 가격 이력 440 / PRE-PUMP 0 / paper 6(CLOSED 2, OPEN 4). 수동 실행 후 데이터가 계속 누적되는 증거다. PRE-PUMP 신규 동작과 72시간 성과가 검증되었다는 뜻은 아니다.
- 두 저장소 `C:\dev\Coin_api`, `C:\dev\coin_api-1`은 별도 디렉터리다. 현재 Git 저장소는 후자. 전자의 V15 파일과 archive 파일은 전체 바이트가 다르며 앞선 AST 대조에서 수집/preload 일부가 달랐다. 탐지·점수·저장 함수가 같아도 실행 버전 출처를 합치면 안 된다.
- V4 163개/과거 보고서 215개 문제는 다른 스키마·파일의 문제다. V15 1,761개와 동일 집합이 아니다. 해당 미확정 경위는 이전 진단을 유지하고 이번에 DB 선택·복원·이전하지 않았다.

**실데이터 호환성 재현**: V7의 기존 `as_int/as_float`로 BLOB을 조회 메모리에서 해석한 뒤 V15의 원래 `calculate_score`를 호출했다. 정적 보존본 1,761개 전부 점수 일치, 현 후보 DB도 조회한 모든 신호 점수 일치였다. 과거 score 저장 타입은 BLOB 1,379개, INTEGER 382개다. BLOB을 그대로 SQL AVG/CASE에 넣는 분석을 신뢰하면 안 된다. 숫자 변환은 출처·형식·유한성·범위를 검증하고 원본 바이트는 보존한다. 점수 일치는 **저장된 지표와 공식의 일관성**이며 raw WS부터 같은 신호가 나온다는 완전 재현이나 수익성 증거가 아니다.

원본 재구축/이전은 필요 없다. 읽기 전용 등록 목록에 `dataset_id, 원본 절대경로, 파일/실행 버전, active/static, 시간대 근거`를 두고, 표시 키는 `(dataset_id, SURGE|PRE_PUMP, 원본 id)`로 한다. exchange/market도 보존한다. 같은 id/종목/시각의 서로 다른 DB 데이터를 임의 dedup·병합하지 않는다. 현 파일 해시는 현재 소스의 지문이며 과거 실행 당시 로드한 코드의 증명은 아니다.

## 4. 성과 해석에 필요한 제한 — 기존 코드 재현

[검증 스크립트](../reports/v15_dashboard_design_20261026/verify_compatibility.py)는 V15의 선택한 함수만 AST로 추출하고 모든 함수 쓰기를 `:memory:`에 제한했다. [실행 로그](../reports/v15_dashboard_design_20261026/compatibility_run.log)의 `DB 업그레이드`, `DATABASE READY`, `KRW-TEST`는 **메모리 fixture 출력**이다. 원본 DB 작업이 아니다.

| 구분 | 관측 사실/재현 | 대시보드 해석 설계 |
|---|---|---|
| SURGE 중간 누락 | `complete_checkpoint` L1765는 해당 minute의 가격 존재만 필수. 메모리에 minute0=100, minute5=110만 넣어도 5m return/MFE/MAE가 +10/+10/0으로 저장됨 | 저장 결과는 그대로 표시하되 관측 2/6, 중간 누락을 함께 표시. 완전한 극값으로 표현하지 않음 |
| SURGE 끝점 없음 | 같은 fixture의 minute10 끝점이 없으면 결과 None | 미도래와 기한 경과 후 누락을 구별. 누락을 손실/0%로 바꾸지 않음 |
| SURGE 늦은 60m | `track_signals` L1835가 minute를 60으로 clamp. 최초 추적을 65분 후에 호출한 메모리 재현에서 그때 가격이 minute60과 return60으로 저장됨 | `observed_at-created_at`을 함께 검증. 정확한 60분 결과라고 인증하지 않음. source 값을 교정하지 않음 |
| PRE-PUMP 지연 | 7시간 후 첫 관측을 입력하자 원래 `update_prepump_tracking`이 같은 현재 가격으로 return3h/6h를 함께 저장, 12h는 NULL | 저장 체크포인트임을 명시. 체크포인트별 관측 시각이 없어 과거의 정확한 시점·연속성은 검증 불가 |
| 오래된 SURGE 결과 | 정적 보존본의 saved return60m 1,294개 중 minute0~60 저장 가격이 일부 없는 것이 714개. 끝점과 비교 가능한 602개는 공식 불일치 0 | 레거시 결과 존재와 완전 추적 결과를 구별. 전체를 완전한 60분 MFE/MAE 표본으로 합산하지 않음 |
| 미복원/중단 | 복원 가능 시간 밖의 미완료 데이터는 현재 복원 함수가 다시 추적하지 않음. OPEN paper가 남을 수 있음 | 종료 실패/손실로 자동 변경하지 않음. 기존 상태와 추적 미완료를 나란히 표시 |

SURGE 극값은 저장된 분별 가격 기준이고 PRE-PUMP는 루프에서 관측한 최신 가격 기준이다. 거래소 전체 고가/저가 또는 신호 이후 모든 tick을 포착한 MFE/MAE가 아니다. `prices`의 마지막 값은 과거 체결값일 수 있고 DB 저장 시각이 그 체결 시각을 입증하지 않는다. 완전한 분 번호가 있어도 체결 신선도가 검증된 것은 아니다. PRE-PUMP `completed=1`도 모든 구간 연속 관측의 증명이 아니다.

naive local 시각은 현재 호스트 KST와 과거 실행 환경이 동일하다는 가정이 필요하다. 원문을 유지하고, 시간대 가정을 화면/메타데이터에 표시한다. PRE-PUMP는 체크포인트별 실제 기록 시각을 저장하지 않으므로 `last_seen_at` 하나로 3~72h 시각 정확성을 소급 인증할 수 없다.

## 5. 기존 Analyzer 재사용 판단

조사 범위는 현재 저장소 전체 Python과 `C:\dev\Coin_api` 하위다. **`analyzer_v6.py`는 이 범위에서 발견하지 못했다.** 다른 경로에 없다고 단정하지 않는다. 실제 발견한 분석기와 관련 모듈은 다음과 같다.

| 자산 | 기존 기능 | 이번 목표의 재사용 범위 |
|---|---|---|
| 외부 `db_analyzer_v7.py` | `schema_check` L66, `load_trades` L83, `load_histories` L106, `basic_stats` L160. paper 종료 손익 통계, 저과열 필터, 시간 분할, TP/SL grid | 숫자 해석·조회·기초 통계 원리 재사용 가능. 두 V15 DB의 메모리 투영에서 schema_check, 실제 paper/history 로딩 확인. **main 전체·grid_validation L274·automatic_readout L321·최적화 순위는 사용하지 않음** |
| 외부 `db_checker_v1.py` | schema/NULL·추적 결과·점수 구간·기초 성과 조회 | 점검 항목 참고. BLOB 정규화와 유한성/미완료 분모를 확인하지 않은 SQL 결과는 그대로 채택하지 않음 |
| `scanner_analysis_v51.py` | `evaluate` L28, `stats` L76, 별도 분석 캐시. 5/15/30/60m, V4 저장 분봉/verified_until에 의존 | 페이지 분할·오류 처리·분모 표기·별도 캐시 구조는 후보. **V15 계산에 evaluate/V4 엔진을 재사용하지 않음**. V15는 5/10/30/60m이므로 15m을 만들거나 10m을 15m으로 바꾸지 않음 |
| `legacy_open_reconciliation.py` | `classify` L44: OPEN/STALE_OPEN, 관측 시각/진입가/분 연속성 확인, candidate는 확정 손익에서 제외 | 미완료 구별 원리 재사용 가능. 자동 청산·pnl 복구·거래 상태 수정은 하지 않음 |
| `research_pattern_summary.py` | 저장 사건·대조군·사전 snapshot 통계 | V15의 신호 당시 p/r/score와 입력 구조가 다름. 자동 연결하지 않음 |
| `surge_event_research_v2*`, `forward_surge_research_v3`, collector·연구 모듈 | 별도 사건 정의/대조군/분봉 연구 | 기존 자료 보존. V15 대신 실행하거나 새 공통 특징·탐지·전략 개선 엔진으로 확장하지 않음 |

현재 `scanner_dashboard_v50.signal_view` L106은 `signal_id/signal_time/signal_price/detected_at/source`를 요구한다. V15 `signals`에는 해당 열들이 없고 `minute_candles`도 없다. 메모리 V15 구조를 직접 넣은 실제 호출에서 `IndexError: No item with that key`로 실패했다. 단순히 DB 경로만 바꾸는 통합은 불가하다.

## 6. 최소 변경 대시보드 설계 — 아직 구현하지 않음

경로는 **원래 V15 프로세스 → 원래 crypto DB → 읽기 전용 조회/기초 통계 → 기존 웹 화면**이다. 탐지 호출 경로에 웹 분석 결과를 되돌리는 연결은 두지 않는다. V4/V5.2 엔진·DB·연구 결과는 보존하되 V15 화면의 시작 버튼이나 기본 데이터 공급원으로 연결하지 않는다.

| 기존 V5.2 자산 | 호환성 | 최소 설계 |
|---|---|---|
| HTML/CSS·메인/분석 두 페이지 | 화면 틀 재사용 가능, 기존 JSON 계약은 V4 의미 | 디자인 유지. SURGE/PRE-PUMP의 실제 필드와 지평을 표시하는 조회 계약만 별도 정의 |
| 버튼/POST 인증 | `Server`의 loopback, Host/Origin/Fetch-Metadata, 수명별 token 재사용 후보 | 상태·분석 GET은 절대 스캐너 시작을 유발하지 않음. 파일 경로/명령을 요청으로 받지 않음 |
| 시작 로직 | `Operations.request` L424 → desktop.start_scanner L129 → control.start L312 → **forward_scanner_v52** L347 | 현재 연결은 부적합. 향후 고정된 기존 V15 파일을 독립 child로 실행하는 launcher만 검증. 새 엔진 구현/알고리즘 추출본을 만들지 않음 |
| 프로세스 관리 | launch token·PID+생성 시각·중복/경로 보호는 참고 가능 | 향후 자신이 시작한 V15만 제어. 외부 V15 발견 시 읽기 전용·시작 차단, 종료 대상 편입 금지 |
| 종료·저장 확인 | 기존 STOP marker/WAL/두 거래소 DB 규약은 V15에 없음 | 기존 V15의 KeyboardInterrupt 경로에 도달하는 독립 콘솔 제어의 가능성부터 격리 fixture에서 확인. PID 이름 일괄 종료/kill/강제 종료 사용 금지. 실패 시 종료 미확인으로 남김 |
| WS 수집 | V5.2의 확정 OHLC·중복 제거·지연 정리와 V15의 입력 의미가 다름 | V15의 기존 REST+WS를 그대로 사용. V5.2 WS를 V15 앞으로 붙이지 않음 |
| SQLite 보호 | read-only/query_only·경로 고정 원칙 재사용 가능 | active DB에 immutable=1 금지. 원본 journal_mode/checkpoint/schema/index를 바꾸지 않음. 장기 BEGIN/큰 JOIN/전체 backup을 active DB에 수행하지 않음 |
| 분석 DB | 현재 캐시는 V4 dataset/signal/horizon 구조 | 필요할 때만 V15 전용 파생 캐시. 원본 삭제/수정/새 label 저장 금지. 현재 V4 캐시와 혼합 금지 |

**메인 페이지 설계:** V15 실행 파일/DB 출처, 외부 실행 또는 향후 관리 실행 여부, 프로세스 생존, 마지막 신호·추적 저장 시각, 신규 SURGE와 실제 score, PRE-PUMP level/strength를 구별한다. DB의 종목 수는 ‘저장 신호가 있는 종목 수’다. 현재 감시/구독/수신/실제 스캔 수와 같다고 표시하지 않는다. 기존 로그나 상태 근거가 없으면 감시 수·WS 신선도·마지막 analyze 시각은 **확인 불가**다. 신호가 안 나오는 것만으로 중단/정상이라고 판정하지 않는다. 현재 사용자 실행은 종료 버튼 비활성 대상이다.

**분석 페이지 설계:** 데이터 출처와 SURGE/PRE-PUMP를 분리해 원래 신호·지표, 저장 가격 흐름, 지평별 return/MFE/MAE와 유효 표본 수, 미도래/누락/시각 검증 불가 수를 표시한다. SURGE는 선 차트이며 OHLC 봉으로 꾸미지 않는다. PRE-PUMP는 저장된 체크포인트 표/점만 제공하고 사이를 실제 가격 경로처럼 연결하지 않는다. paper 결과는 별도 집계한다.

**통계 정의:** 가격 변화율은 `(후속 저장가격/신호가격-1)*100`이며 체결 수익률이 아니다. 상승 비율은 유효한 해당 지평의 return>0 건수/유효 건수로 이름을 명시한다. paper 승률은 원래 CLOSED이고 유한한 pnl_pct가 있는 기록 중 양수 비율이며 OPEN/STALE_OPEN은 제외한다. 서로 다른 지평·유형·DB·시기·원본 버전의 분모를 혼합하지 않는다. 평균 return/MFE/MAE는 각각 유효 n을 표시한다. MAE는 기존 최소 변화율의 부호를 보존하고 최대 낙폭(peak-to-trough)과 혼동하지 않는다.

저장 결과와 관측 검증 통계는 따로 표시한다. 끝점이 있어도 중간 누락이 있으면 관측 MFE/MAE의 제한을 표시하고 완전 추적 통계에 넣지 않는다. 분 번호의 연속성·observed_at 시간 범위·양수 유한 가격을 확인해도 체결 신선도까지 인증된 것은 아님을 표시한다. 일시적 잠금이면 짧은 timeout 후 직전 캐시와 조회 시각/오류를 보여주며 재시도 폭주로 scanner 쓰기를 방해하지 않는다.

점수별 표가 필요하면 기존 저장 score의 정확한 값별 기술 통계부터 사용한다. 최적 점수·TP/SL·필터·임계값 추천, 자동 전략 개선, 성공 사례로부터 새 탐지 규칙 발굴은 범위 밖이다. 성공/실패 비교도 명시한 기존 결과의 부호·기존 paper 상태에 따른 기술적 비교만 가능하다. 미래 성과를 사전 특징으로 사용하지 않는다. 저장된 p/r/score의 단순 분포를 넘어 ‘급등 전 공통 특징이 검증됐다’고 주장하지 않는다. V15 DB만으로 비신호 대조군이나 사전 전체 분봉을 복원할 수 없다.

**프로세스 관리의 미검증 사항:** 원본에 main guard·관리 STOP·정기 heartbeat·명시적 종료 확인 프로토콜이 없다. 감시 수/scan 진행 로그의 신뢰 가능한 수집, Windows 독립 콘솔에 대한 정확한 종료 전달, 종료 후 SQLite 저장 확인은 아직 구현/실검증하지 않았다. 안전하게 증명할 수 없다면 시작·종료 통합을 보류하고 조회용 대시보드를 먼저 제공하는 것이 이번 범위에 맞다. 자동 재시작이나 다른 엔진으로 대체 실행하지 않는다.

## 7. 단계별 구현·검증 순서

아래는 **후속 작업 순서**이며 이번 작업에서 실행하거나 변경하지 않았다.

1. **DB 출처 고정:** 원본 V15 파일 지문·실행 경로·CWD·기존 DB 경로·시간대 근거를 확정한다. 기존 수동 실행은 외부 소유로 고정하고 중복 시작을 차단한다. 모든 기존 자료 보존 목록을 만든다.
2. **읽기 전용 조회부터:** 정적 보존본으로 스키마·BLOB·NULL·빈 데이터·두 신호 유형·오류 표시를 검증한다. 원본 읽기 전용, 파생 캐시 분리. active DB에는 짧은 SELECT와 낮은 빈도·범위를 적용한다. 없음/불명 상태를 정상 값으로 꾸미지 않는다.
3. **기초 성과 표시:** 기존 return·관측 MFE/MAE와 가격 이력의 공식을 독립 SQL/기존 함수로 대조한다. 누락·늦은 60분·지연 PRE-PUMP·OPEN paper 사례를 포함한다. 캐시 유무와 무관하게 원본 값·상태를 보존한다. 미래 데이터가 탐지 당시 지표에 섞이지 않는지 확인한다.
4. **화면 계약 연결:** 현재 디자인 틀에 V15 조회 결과를 연결한다. 10m을 15m로 바꾸지 않음, PRE-PUMP에 SURGE 점수를 붙이지 않음, DB 종목 수를 감시 수로 표시하지 않음을 검증한다. V4 엔진 호출이 없고 GET으로 scanner가 시작되지 않음을 확인한다.
5. **제어 호환성만 격리 검증:** 네트워크 없는 child fixture에서 PID 재사용·중복·외부 실행·취소·정상 종료·SQLite commit·웹 유지·다른 프로세스 생존을 확인한다. 그 다음에도 현재 사용자 V15를 대상으로 시험하지 않는다. 원본 파일 수정 없이 안전한 제어가 불가능하면 읽기 전용 운영을 유지한다.
6. **추후 명시적으로 허용된 제한 실행:** 기존 사용자가 현재 실행을 스스로 끝낸 뒤 별도 요청이 있을 때만 범위·호출·시간 상한을 먼저 정하고 새 관리 실행을 검증한다. V15 자체에는 전체 API 예산 관리가 없으므로 V5.2의 상한이 자동 적용된다고 가정하지 않는다. 성과 판단은 충분한 추적 기간 이후에도 관측 한계와 함께 보고한다. 새 전략/최적화·주문 기능은 포함하지 않는다.

## 8. 검증 결과와 보호 확인

- 호환성 검증: [결과 JSON](../reports/v15_dashboard_design_20261026/compatibility_results.json), [실행 로그](../reports/v15_dashboard_design_20261026/compatibility_run.log). 기존 점수 공식 대조, V7 조회 함수의 private DB 호환, V4 화면 직접 연결 실패, SURGE/PRE-PUMP 누락·지연 재현을 포함한다. 실데이터 전체 WS replay나 전략 우열 검증은 아니다.
- 관련 오프라인 회귀: `python -m unittest tests.test_scanner_analysis_v51 tests.test_scanner_dashboard_v50 tests.test_scanner_v41` **59개 PASS**. [로그](../reports/v15_dashboard_design_20261026/related_tests.log). RuntimeError 문자열은 오류 처리 fixture 출력이며 최종 결과는 OK다. 첫 시도는 존재하지 않는 `tests.test_legacy_open_reconciliation` 모듈명을 지정해 loader 오류가 있었고, 실제 관련 테스트가 포함된 `test_scanner_v41`로 정정했다. 메모리 fixture 첫 시도의 NOT NULL 누락도 검증 스크립트에서만 보완했다.
- 현재 사용자 V15의 wrapper PID28300, 실제 Python PID26448과 생성 시각을 작업 중 확인했다. 최종 생존·파일 보존 대조는 [preservation_after.json](../reports/v15_dashboard_design_20261026/preservation_after.json)에 기록한다. `CommandLine`의 상대 파일명만으로 CWD/실행 당시 소스 바이트를 입증할 수는 없다. 사용자 설명과 archive DB의 새 기록은 해당 실행의 관찰 근거이며 강제 프로세스 부착으로 확인하지 않았다.
- 보호 목록은 [작업 기준 해시](../reports/v15_dashboard_design_20261026/preservation_before.json)에 있다. 기존 dirty `research_status.md` 내용은 유지하고 이번 결과를 앞에 추가했다. 기존 진단 문서·보고서·연구 DB·코드/UI/BAT도 보존 대상으로 대조했다. 실행 중 archive DB는 사용자가 계속 쓰므로 바이트 동일성을 주장하지 않는다. 이번 도구는 read-only/query_only로만 조회했다. 최종 관측 시각 간의 자연 증가를 데이터 손상/수정으로 판단하지 않는다.
- 이번 변경물은 이 보고서, 호환성 검증 자료, 상태 문서 갱신뿐이다. 운영 교체·기능 구현·원본 데이터 이전·commit/push는 수행하지 않았다. **최종 목표는 V15 전략을 객관적으로 평가할 수 있는 대시보드이며, 현재 전략의 수익성·안정 운영·웹 제어 호환성은 아직 미검증이다.**
