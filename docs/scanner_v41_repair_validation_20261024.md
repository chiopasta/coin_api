# Scanner V4.1 핵심 결점 복구 및 재검증 — 2026-10-24

## SCANNER STATUS: PARTIAL

**데이터·상태·실행 기반의 확인된 결점을 수정했고, 기존 신호와 연구 수치를 보존했다.** 제한 REST 조회와 격리 재생은 통과했지만, 장시간 실제 운영·WebSocket 회복·급등 조기 탐지 성능은 이번에 확인하지 않았다. 따라서 READY로 올리지 않는다. 수익성·자동매매 적합성은 검증되지 않았다. 10/24 종합 점검의 급등 탐지 실효성 부족 결론도 유지한다.

기준은 [종합 점검 보고서](scanner_comprehensive_audit_20261024.md), 커밋 `c015fc8`이다. 시작 시 `main` 작업 트리는 깨끗했다. 기존 연구 threshold·label·5분 observation·결측 정책·universe·LIVE/CATCHUP 경계는 변경하지 않았다. 구현 버전만 `IMPLEMENTATION_VERSION='4.1'`로 구분하고 frozen `POLICY.version=4`를 유지했다.

최종 증거는 [검증 폴더](../reports/scanner_v41_validation_20261024/)에 분리했다. 우선 읽을 파일은 [최종 전후 비교](../reports/scanner_v41_validation_20261024/before_after_final.json), [OPEN 분리 장부](../reports/scanner_v41_validation_20261024/legacy_reconciliation.json), [최종 선별 테스트](../reports/scanner_v41_validation_20261024/selective_tests_v41_final.log), [원본 보존 확인](../reports/scanner_v41_validation_20261024/preservation_completion.json)이다.

## 코드·원본 재확인

| 항목 | 실제 확인 |
|---|---|
| 현재 V4 실행 | CLI → cycle → 업비트 collector.Client → fetch_market → V3 feature/cluster → outcomes. 현재 중지 상태 |
| 거래소 | V4는 **업비트만**. 빗썸은 보관 V15와 외부 `C:\dev\coin_API` 구형 V16 계보에 존재. 이번에 V4 빗썸 스캐너를 추가하지 않음 |
| 분봉 오류 위치 | 새 분 첫 체결을 이전 분 종가에 넣는 오류는 `archive/scanner_v15.py`에 재현. V4는 이미 UTC 확정1분봉을 사용 |
| 거래대금 오류 위치 | 구형 preload의 수량×종가. V4는 이미 거래소 `candle_acc_trade_price`를 사용 |
| OPEN 위치 | `C:\dev\coin_API\crypto_scanner.db`의 paper trades. V4에는 주문·가상거래 자체가 없음 |
| 마지막 정상 cycle | **2026-10-07 19:27:12 KST**, session 종료 **19:27:59 STOPPED**. 과거 세션의 상세 종료 사유는 없어서 중단 원인 소급 확정 불가 |
| 보존 데이터 | V4 371,708봉 / 163신호 / 326 outcome. 구형 1,761신호 / 305 paper trades. discovery·validation 및 기존 custody 증거 유지 |

외부 원본 코드·DB나 CHIO BOT 범용 연구 엔진은 수정하지 않았다. 보관 V15 파일도 실제 Scanner를 시작하지 않고 선택한 순수 함수만 AST로 추출해 검사했다. 기존 다른 프로젝트 작업을 중단하지 않았다.

## FIXED

### 1. 봉 마감·시간·오류 응답 검증

새 [scanner_candles.py](../coin_analysis/scanner_candles.py)는 기존 collector의 변환·페이지 검증을 재사용한다. V4 입력에서 시장, UTC/KST 일치, 분 격자, interval unit, 순서·중복, 완료 시각, 유한한 OHLC·거래대금을 검사한다. 잘못된 값이나 HTTP200 오류 본문은 정상 시장 데이터로 처리하지 않는다.

- 기존 5초 settle 유지: 확정 cutoff는 `floor((now-5)/(분수*60))*(분수*60)`. 1·5·15분 각각 마감 직전·정각·정각+5초를 검사했다. 진행 중 봉은 확정 봉에 넣지 않는다.
- **5/15분은 입력 검증 및 실제 API 교차 검증 지원이다.** V4가 별도5/15분 캔들을 수집하거나 observation을 바꾼 것은 아니다. V4 feature는 기존대로 확정1분봉에서 계산한다.
- 빗썸 `to`는 KST의 timezone suffix 없는 문자열, 업비트는 UTC ISO 시각으로 별도 직렬화한다. 응답의 canonical 시각은 양쪽 모두 UTC다. 빗썸 요청 규약은 [공식 분봉 문서](https://apidocs.bithumb.com/reference/%EB%B6%84minute-%EC%BA%94%EB%93%A4-%EC%A1%B0%ED%9A%8C)와 실제 응답으로 확인했다.
- malformed 데이터·기존 확정 봉과 충돌한 데이터는 cursor·페이지 transaction을 확정하지 않고 cycle ERROR로 중단한다. 기존처럼 일반 네트워크 장애와 같은 취급으로 계속 돌지 않는다. 원본 값은 덮어쓰지 않는다.

구형 보관 V15에서는 양 거래소 callback 모두 **이전 가격으로 마감한 뒤 새 체결 가격을 반영**하도록 순서를 고쳤다. 이전 분보다 오래된 체결도 제외한다. 재현 입력 `이전 가격100 → 다음 분 첫110`에서 이전 분 종가는 수정 전110, 수정 후100이다. preload는 진행 중 봉 제외, UTC 정렬·중복 확인, 공백 뒤 최신 연속 구간만 유지하도록 수정했다. 이는 구형 WS 시스템 전체의 운영 승인이 아니다.

### 2. 거래대금·단위·중복·늦은 봉

- 구형 preload는 `candle_acc_trade_volume × trade_price` 대신 **원천 `candle_acc_trade_price`**를 저장한다. 수량2·종가200·실제 체결대금300인 예에서 잘못된400 대신300을 유지한다. 원천 필드가 없으면 임의 계산하지 않는다.
- KRW 시장만 허용하고 원화 환산을 더하지 않는다. 수량 필드가 있으면 `low×volume <= native_value <= high×volume`의 산술 정합성을 검사한다. 누적 거래대금은 봉별 값을 저장하며 같은 봉을 재수신했다고 다시 더하지 않는다.
- 값 비교 허용오차는 **`max(1 KRW, abs(native_value) × 1e-8)`**로 명시했다. 이는 데이터 반올림·합산 검증 허용오차이며 연구 조건이 아니다. 허용오차 밖의 값은 차단한다. 원천 필드를 복사해 저장한 차이가0이라는 사실만으로 거래소 원천의 진실성 전체를 입증하지 않는다.
- V4가 매분 새 구간만 선택하면서 직전 API에서 늦게 발표된 봉을 영구히 놓칠 수 있는 경로를 보완했다. 새 collection job의 시작을 **기존 verified_until 이전120초**까지 겹쳐 확인한다. 기존200봉 요청을 재사용하며, 통상 최신 polling은 같은 요청 수다. 페이지 경계·희소 거래 구간에서는 추가 페이지 가능성이 있어 장기 비용은 미검증이다.
- 이120초는 기존 두 번의1분 polling에 대한 수집 재확인 범위다. 신호 threshold·관측 간격·결측 보간 정책이 아니다. 실제 늦게 확보된 봉만 추가하며 첫 확인 시각을 새 `scanner_late_candles`에 기록한다. **과거 signal/feature·last_observation은 되감거나 재작성하지 않는다.** 기존 규칙대로 PENDING/UNKNOWN만 실제 데이터가 완전해진 경우 재평가하고 완료 outcome은 유지한다.

### 3. OPEN 가상거래 정합성

새 [legacy_open_reconciliation.py](../coin_analysis/legacy_open_reconciliation.py)는 source DB를 read-only로 열고 별도 JSON 장부만 만든다. 원래 status·entry/exit·pnl 등은 `original`에 보존한다. `effective_status`와 recovery 증거는 별도 필드다.

원인 경로를 실제 구형 코드에서 확인했다. `restore_active_signals`는 신호 발생 후60분이 지난 행을 복구 대상에서 제외한다. 프로세스가 중단된 동안 deadline을 넘긴 paper trade를 정산하는 별도 timeout sweep이 없어 OPEN이 남을 수 있다. `track_signals`도 해당 분 관측이 없으면 빠진 가격을 만들지 않으며, checkpoint가 누락이어도 추적을 종료할 수 있다. 행별 중단/실패 로그가 없어 **115건 모두의 단일 근본 원인을 특정한 것은 아니다.**

| 기준 시각 / 분류 | 결과 |
|---|---:|
| 구형 DB 마지막 관측인9/9 23:50:31 기준, 기존 보고서 | OPEN115 중 기한 경과104 |
| 이번 명시적 cutoff **10/24 00:00 KST** | 원본 CLOSED190 / 별도 **STALE_OPEN115** |
| 종료 증거 부족 | 115 / 115 |
| 검증된 복구 청산 / 신규 pnl | **0 / 0** |

종료 후보는 진입부터 최초 TP/SL 또는 deadline까지 연속된 관측과 시간 정합성이 있어야만 별도로 표시한다. 후보도 실제 마지막 체결 시각·독립 custody가 없으면 `CANDIDATE_ONLY_NOT_VERIFIED`로 남기고 청산 성과에 넣지 않는다. 실제115건에서는 그러한 연속 관측조차 부족했다. STALE_OPEN과 후보는 원본 종료 거래 통계에 포함하지 않는다. 원래 CLOSED190건의 기존 통계는 별도로 보존하며, 이를 새로 검증된 실제 체결 성과라고 부르지 않는다. 같은 출력 경로 재실행은 overwrite를 거부해 중복 복구 기록도 막는다.

### 4. 운영·상태·중단 사유

- 기존 API timeout·429/5xx 재시도/backoff·418/budget 중단, cursor 재개, 단일 writer OS lock을 유지하고 합성 단절→retry→재시작→중복 skip을 검사했다. V4는 REST이므로 WebSocket 재연결을 새로 구현하지 않았다.
- `detected_at`을 긴 처리 batch 시작 시각 하나로 기록하지 않고 **각 신호를 저장하는 실제 시각**으로 기록한다. 긴 처리 뒤에도 LIVE로 잘못 분류될 위험을 줄였다. 300초 경계는 그대로이며 synthetic 301초 지연은 CATCHUP으로 기록된다. canonical signal_time·feature는 변하지 않는다.
- 새 `scanner_runtime_events`에 시작·미완료 이전 세션 발견·종료 상태와 사유를 기록한다. 강제 종료의 알 수 없는 종료 시각을 만들어내지 않는다. 기존 session/cycle 로그도 보존한다.
- lock 파일을 매번 append하던 동작을 고쳐 크기가 계속 늘지 않게 했다. 별도 두 번째 Python 프로세스의 lock 거부를 실제 로컬 subprocess로 확인했다.
- 새 read-only `--mode health`는 마지막 cycle·watermark·지연·오류·저장된 세션 상태를 표시한다. DB의 RUNNING이나 최근 시각만으로 OS 프로세스 생존을 단정하지 않는다. 현재 원본에 실행한 결과는 STOPPED다. 이 명령은 writer lock 파일을 바꾸지 않는다.

```powershell
python -m coin_analysis.forward_scanner_v4 --mode health --db data/forward_scanner_v4.db
python -m coin_analysis.legacy_open_reconciliation --source C:/dev/coin_API/crypto_scanner.db --as-of 2026-10-24T00:00:00+09:00 --output reports/별도의_새_장부.json
```

원본 V4 DB에는 이번에 writable 연결이나 schema migration을 실행하지 않았다. **격리 복사본**에서 새 두 운영 테이블 추가를 검사했고, 기존12개 테이블의 모든 행 수·논리 값 hash가 전후 일치했다. [격리 schema 검증](../reports/scanner_v41_validation_20261024/schema_upgrade_final.json).

## BEFORE / AFTER

### 실제 저장 데이터의 격리 재생

원본371,708봉을 새 입력 검증기에 통과시켜 메모리 DB에서 동결 정책으로 재생했다. API·새 데이터 수집 없이 약7초의 제한 재생이며, 장시간 백테스트나 조건 탐색이 아니다.

| 항목 | BEFORE | AFTER |
|---|---:|---:|
| 입력 검증 | 기존 저장 봉 | 371,708개 허용, 불량0 |
| 재구성 신호 | 163 | **163, ID·시각·가격·range·cluster 불일치0** |
| label status / 최대 high / 첫 목표 시각 / 관측 분수 | 기존326개 | **불일치0** |
| feature·flag·관찰 후보 | 기존163개 | **기존 수치 허용오차 안에서 불일치0** |
| 5/15/30/60분 가격 변화·MFE·MAE | 기존 각 신호 | **불일치0** |
| 재처리·복원 | 중복 위험 점검 대상 | 동일 state 재처리 후 전체 논리값 hash 동일 |
| 기존 LIVE 집단 L1 | **0/24**, UNKNOWN8 | **0/24**, UNKNOWN8 |
| 기존 LIVE 집단 L2 | **0/20**, UNKNOWN12 | **0/20**, UNKNOWN12 |
| 원본 종료 DIP | N99, **-0.423361%** | N99, **-0.423361%** |
| 원본 종료 REBOUND | N66, **-0.340038%** | N66, **-0.340038%** |

**이 재생은 새 LIVE 운영이 아니다.** 기존 LIVE32개 ID를 cohort로 보존해 결과를 비교한 것이다. 오프라인 재생의 detected_at/source를 원래 실제 전달 시각으로 바꾸어 주장하지 않았다. 보관 V15의 수정된 신호·점수·매매를 원시 체결부터 다시 만들 성능은 **NOT_REPRODUCIBLE**이다. 원시 체결·당시 실행 버전·완전한 시각 증빙이 없으므로 기존 sampled 이력을 수정된 신호처럼 재사용하지 않았다.

전체 과거 구간을 한 번에 읽으면 기존 짧은 운영 구간별 누적합과 부동소수 덧셈 순서가 달라져 **120개 feature JSON 문자열**의 일부 숫자 표기가 달랐다. 최대 상대 차이는 약 **5.41e-12**, 최대 절대 차이는 약 **0.0001755**였다. 기존 진단 `near()`와 같은 relative1e-8 / absolute1e-7 기준을 사용했고 허용오차 밖의 의미 차이는0이었다. 최초 엄격한 문자열 비교 결과는 `before_after.json`에 남기고, 수치 비교·시각·flag 검증을 적용한 최종 결과는 `before_after_final.json`으로 분리했다. 원본 feature는 변경하지 않았다.

### 기존 LIVE cohort의 후속 경로

신호 확정 종가 기준, 각 horizon 전체 분봉이 있을 때만 계산한 비용 미반영 가격 변화다. MFE/MAE는 해당 미래 high/low의 signed 최대/최소 변화이며 실제 체결 수익이 아니다. BEFORE와 AFTER는 아래 모든 값이 같다.

| 분 | 완전 N | 평균 종가 변화 % | 평균 MFE % | 평균 MAE % |
|---|---:|---:|---:|---:|
| 5 | 31 | +0.501134 | +1.027901 | -0.551680 |
| 15 | 29 | +0.667648 | +1.622183 | -0.647097 |
| 30 | 24 | +0.159079 | +1.747288 | -1.188439 |
| 60 | 20 | **-0.262473** | +1.984545 | -2.004796 |

수정된 코드로 다시 읽었다고 독립 OOS가 생긴 것은 아니다. 기존 discovery/validation 판정과 OOS 한계는 그대로다. 구형 가상거래 숫자도 기존 종료 기록의 산술 재확인이지, 가격 출처와 체결 가능성을 새로 인증한 성과가 아니다.

### 제한 실제 API 검증

BTC 한정 최초 **6회**(양 거래소1/5/15분 각각1회), 이어 빗썸 요청 시각 서식 수정 후 **3회**만 추가했다. **합계9회, 자동 재시도0, 호출별 timeout4초, phase별 신규 호출 시작40초 / worker hard limit55초**, Scanner cycle·WS·주문은 실행하지 않았다. 각 정상 조회는 최근 확정1시간만 대상으로1분60개 / 5분12개 / 15분4개를 요청했다.

- 최초 업비트3회: 정상. 최초 빗썸3회: UTC offset 포함 to를 거부한 error body를 HTTP200으로 반환. 이 오류를 성공으로 집계하지 않았다. [최초 원본 응답](../reports/scanner_v41_validation_20261024/live_api.json).
- 공식 KST 요청 서식 수정 후 빗썸3회: 정상. [수정 후 빗썸 응답](../reports/scanner_v41_validation_20261024/live_bithumb_corrected.json).
- 정상 원천 봉은 양 거래소 각각76개, 총152개. 진행 중 봉·timestamp·시장·단위·OHLC×volume 범위·중복 검사를 통과했다. 원천 거래대금→정규화→격리 SQLite 저장의 최대 차이는 양쪽 모두0원이다.
- 완전한1분봉 합계와 native5/15분봉을 **거래소별16개씩, 총32개** 비교해 전부 허용오차 안에서 일치했다. 최대 절대 차이는 업비트 약2.98e-8원, 빗썸 약7.45e-9원이다. 실제 원시 체결 총합을 독립적으로 복원한 검증은 아니며 두 거래소의 서로 다른 원천 데이터를 서로 같다고 비교하지 않았다.

## REMAINING

1. V4의 4% range는 방향성을 구분하지 않는다. 이번에 상승 필터·새 점수·전략을 넣지 않았다. 기존 LIVE0회 성공과 시간·시장 집중은 남아 있다.
2. 5초 settle과 이전120초 재확인이 모든 API 발표 지연을 해결하지는 않는다. 더 늦은 봉·오래된 확정 봉 수정·무체결과 공급 지연의 완전한 구분은 미검증이다. 늦게 온 데이터로 과거 signal을 소급 수정하지 않는다.
3. 고정 universe의 한 시장이 오래 실패하면 전체 watermark가 멈춘다. frozen peer 구성과 결측 정책 때문에 자동 탈락·대체를 추가하지 않았다. health에서 확인할 수 있지만 자동 감시·재시작 서비스는 없다.
4. 구형 보관 V15는 거래소 전체 분 경계·stale 마지막 가격·WS 중복·장기 재연결·부분 현재분 지표 등 추가 한계가 있다. 작은 마감/preload 수정만 했으며 실제 재운영을 승인하지 않는다. 외부 원본 V16은 보존했으므로 그 파일에 수정이 반영된 것은 아니다.
5. CHIO BOT UI 연결, 장기 디스크/메모리·rate-limit 회복, 실시간 자연 신호 전송은 이번 범위 밖이다. 실제418/429나 회선 단절은 합성 테스트로만 확인했다.

## BLOCKED / NOT_REPRODUCIBLE

- **STALE_OPEN115개 검증 청산:** 기한까지의 연속 가격·정확한 마지막 체결 시각·독립 종료 증거 부족. 임의 exit/pnl 없음.
- **구형 수정 후 신호 시각·DIP/REBOUND 재생 성과:** 원시 체결·당시 config/version custody 부재. 기존 신호·원본 봉을 고쳐 추정하지 않음.
- **과거 중단 사유의 행별 소급 복원:** 당시 상세 종료/오류 감사 로그 부재. 새 이벤트는 이후 실행부터 기록.
- **독립 OOS·포트폴리오 MDD·실제 체결 수익·전체 시장 누락률:** 추가로 확보되지 않았다. 기존 동결 결과를 재사용해 새 성과로 포장하지 않음.

## 선별 검증 및 보존

- 명령: `python -m unittest tests.test_scanner_v41 tests.test_forward_scanner_v4 tests.test_forward_scanner_v4_operations -v`.
- **최종41개 통과, 약4.22초.** 경계/UTC·KST/거래대금/오류본문/늦은 봉/동시 프로세스/재시작/미래 변경·삭제 leakage/중복/OPEN 장부/원본 보존/WAL 등 이번 영향 범위만 검사했다. 전체 회귀 suite 미실행.
- Windows 테스트 fixture의 열린 SQLite 연결 때문에 초기 cleanup 오류가 있었고 fixture 연결을 닫아 최종 검증을 통과했다. 최종 근거는 `selective_tests_v41_final.log`다. 앞 단계 로그도 별도로 보존했다.
- 기존 DB·연구 보고서·정책 등 **86개 보호 입력**의 전후 SHA-256 일치를 확인했다. discovery/validation·기존 진단 증거·외부 구형 DB/코드를 포함한다. [입력 manifest](../reports/scanner_v41_validation_20261024/input_manifest.json).
- 원본 DB를 초기화·마이그레이션·청산하거나 장시간 LIVE를 시작하지 않았다. Windows 종료 없음. 변경 파일은 보관 코드의 작은 수정, V4 입력/운영 보강, 별도 OPEN 검증기, 선별 테스트와 문서·격리 증거다.

## NEXT — V4.2에서 검증할 것

고정 정책·별도 관측 DB·제한된 운영 한도를 먼저 정한 다음 실제 연속 노출을 확보해야 한다. LIVE 전송 지연·중단 시간·late-candle 빈도·UNKNOWN·시장별 관측 가능 분모를 함께 기록하고, 미리 정의한 상승 사건에서 실제 전달 기준 조기/추격/목표 도달 뒤/미탐지를 비교한다. 동일 자료로 threshold를 고른 성과를 독립 OOS로 주장하지 않는다. 방향을 구분하지 않는 range 관찰기가 추가 상승을 알려주는지부터 별도로 검증하며, 이 보고서는 그 실행을 시작하지 않았다.
