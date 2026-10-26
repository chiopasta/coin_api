# V15 대시보드 통합 및 최종 검증 — 2026-10-27

## 전체 판정

**PARTIAL — 핵심 V15 웹 실행·정상 STOP·DB 조회·기존 분석기 연결은 완료. 실제 브라우저 외관·모바일과 장기 추적은 미검증이다.** 실제 API 회귀 중 계획 외 준비 실행이 발생한 사실과 수정도 아래에 기록한다. V15 전략의 유효성/수익성 또는 24시간 무인 운영을 승인하는 결과가 아니다.

Git 루트는 `C:\dev\coin_api-1`, 시작 HEAD는 `b2e9dd3`이며 작업 시작 시 Git 변경은 없었다. `C:\dev\Coin_api`는 Git 저장소가 아닌 별도 구형 파일/DB 폴더다. CHIO BOT/KV Korea 프로젝트의 파일·프로세스를 변경하거나 종료하지 않았다.

검토 문서: [V15 호환성 설계](v15_dashboard_compatibility_design_20261026.md), [과거 V5.2 검증](scanner_v52_validation_20261026.md), [백업·이전 검증](v15_release_backup_20261026.md). 이전 설계의 ‘미구현’은 이번 연결로 일부 해소됐다. 이전 V5.2 보고서의 웹 START→V5.2 경로는 이제 과거 기록이다. V4/V5.2 자체 구현·연구 정책·DB는 그대로 보존한다.

## 1. 시작 시 사용자 V15와 DB 상태

- 기존 사용자 V15는 프로세스 조회에서 발견되지 않았다. 수동 실행의 종료 코드/종료 방식까지 확인할 수는 없다.
- 운영 DB: `C:\dev\coin_api-1\archive\crypto_scanner.db`. 시작 당시 SURGE43, 가격 이력1246, PRE-PUMP0, paper12. readonly integrity_check=ok.
- journal_mode=DELETE이고 WAL은 없었다. 12,824-byte journal 파일은 magic header가 0인 비활성 상태였다. 직접 삭제/복구/강제 checkpoint하지 않았다. DELETE 모드이므로 WAL checkpoint는 해당 없음이다.
- 통합 전 Online Backup 스냅샷을 먼저 만들었다. 미완료 추적과 OPEN paper를 삭제하거나 실패로 변환하지 않았다. 이후 추적 변경은 원래 V15 실행이 수행한 것뿐이다.

## 2. 실제 실행 경로와 STOP

기본 경로는 다음과 같다.

`start_coin_api.bat → scanner_desktop_v50 → scanner_dashboard_v50.Server(engine=V15) → Operations(lifecycle=v15_control) → v15_runtime → runpy.run_path(archive/scanner_v15.py, __main__)`

[v15_runtime.py](../coin_analysis/v15_runtime.py)는 원본을 그대로 실행하고 메타데이터/수명 관리만 연결한다. 원본 파일·점수·임계값·수집 함수·탐지/추적 함수 본문은 수정하지 않았다. AST로 복제한 엔진을 운영하지 않는다. CWD는 archive로 고정해 원래 상대 DB 경로가 운영 DB를 가리키게 한다. `time.sleep` 경계의 협조적 KeyboardInterrupt가 원래 V15 종료 경로에 도달하고, 마지막에 원래 DB 연결을 닫는다. SQLite transaction 중간에 강제 중단하지 않는다.

[v15_control.py](../coin_analysis/v15_control.py)는 기존의 OS writer lock, JSON 안전 교체, PID+생성 시각 확인을 재사용한다. START 전 전체 Python 목록 중 V15 직접 실행/관리 실행을 구별해 중복을 차단한다. 실행별 STOP 파일만 쓰고 PID kill/OS signal은 사용하지 않는다. 웹이 시작하지 않은 V15는 EXTERNAL_RUNNING으로 표시하고 START/STOP을 차단한다. 다른 프로젝트의 실행 중 V4 관측도 보호하며 대신 종료하지 않는다. 외부 수동 V15는 이 래퍼의 writer lock을 준수하지 않으므로, 확인 직후 사용자가 동시에 별도 실행하는 경쟁 상황까지 원자적으로 막을 수는 없다.

기존 START/STOP POST의 loopback·Host·Origin·Fetch-Metadata·CSRF·고정 `{}` 본문·CSP·경로 제한을 유지한다. HTTP 요청으로 엔진/파일 경로/명령을 바꿀 수 없다. V4/legacy Server 경로는 기존 코드·오프라인 회귀용으로 명시적으로 남겼지만 기본 BAT/웹은 V15이며 화면에서 엔진을 바꾸는 기능은 없다. V4 직접 CLI는 보존한다.

**NTP 차이:** V15는 원래 NTP gate가 없다. UI에 ‘미지원’으로 표시하고 heartbeat 카드를 사용한다. V4의 동결 시계/탐지 정책을 변경하거나 V15에 강제로 적용하지 않는다. HTTP/시간 한도는 실행 관리 경계에서 유지한다. 실패 시 다른 엔진으로 대체·자동 재시작하지 않는다.

## 3. 두 페이지와 실제 상태 근거

다크 테마·두 메뉴·카드·테이블·SVG 차트·반응형 CSS를 재사용했다. `style.css`는 바이트 동일하다. 기존 레이아웃을 새로 만들지 않고 데이터 의미/필요한 문구만 바꿨다.

실시간 페이지는 다음을 구별한다.

- 목록 등록 수: 원래 V15가 REST로 받은 목록.
- 구독 전송 수: 원래 open callback의 send가 끝난 뒤 기록한 수. ACK 보장이 아니다.
- 실제 수신 수/최근60초 수: 원래 callback 실행 후 가격·분 상태와 최근 event/receipt가 일치하는 종목. 전체 등록 수를 실제 감시 수로 표시하지 않는다.
- 실제 스캔 수: 원래 analyze에서 volume_ratio를 호출한 거래소·종목 쌍을 관찰한 수. 이는 지표 준비 완료/신호 후보 수와 다르다.
- heartbeat/last_analyze/거래소 last_received는 각각 별도 근거다. 외부 실행은 상세 수를 추정하지 않는다. STOPPED일 때 과거 heartbeat를 현재 수집 중으로 표시하지 않는다.

신호 목록은 현재/과거 DB 출처, SURGE/PRE-PUMP 유형, 원래 점수 또는 strength, 저장 탐지 시각/가격과 추적 상태를 표시한다. V15의 created_at은 local naive 값이므로 KST 가정임을 명시한다. 독립적인 거래소 신호 기준 시각은 저장돼 있지 않아 별도 기준 시각을 만들지 않는다. API의 signal_time은 기존 차트 계약용 저장 탐지 시각 별칭이며 별도 reference time을 인증하지 않는다.

## 4. 기존 분석기 연결과 지원 범위

[v15_dashboard.py](../coin_analysis/v15_dashboard.py)는 **조회/화면 변환 계층**이며 탐지·후속 평가·최적화 엔진이 아니다. 실제 기존 `C:\dev\Coin_api\db_analyzer_v7.py`를 import해 `schema_check`, `load_trades`, `as_int/as_float`, `basic_stats`를 호출한다. main/grid_validation/TP·SL 추천은 호출하지 않는다. 원본 분석기 SHA-256은 `9ab8f798b99992ec9149a0814cef91cf4749c074190482bd08d2a259d273b703`로 확인했다. 분석기 알고리즘을 복제한 새 프로그램을 만들지 않았다.

분석기가 없거나 내용이 다르면 명시적으로 연결 미지원이다. 다른 PC에서는 원래 파일을 보존하고 웹 시작 전에 `V15_ANALYZER_PATH`로 위치를 지정해야 한다. 검증되지 않은 분석기를 자동 발견/대체 실행하지 않는다. 기존 V7 파일을 이번 Git에 복사하지 않았다.

| 항목 | 실제 연결 |
|---|---|
| 신호/유형별 발생 건수 | 두 DB의 원래 테이블 조회·집계. 현재43 SURGE, 과거1761 SURGE+76 PRE-PUMP |
| 점수 구간 | 기존 checker의 0~39/40~59/60~79/80+ 구간으로 저장 값만 집계. 최적 점수 추천 없음 |
| 평균 변화율·상승 비율 | 원래 저장 return을 유효 구간에 한해 기존 V7 basic_stats로 집계. 실제 투자 실현 수익/승률 아님 |
| 가상매매 승률 | 원래 CLOSED이고 유한한 pnl 기록만 기존 V7로 집계. OPEN 제외, 실제 체결 증거 없음 |
| MFE/MAE | 원래 V15에 저장된 관측 극값만 읽어 집계. 시장 전체 tick/OHLC 극값을 재구축하지 않음 |
| 상세 차트 | 저장 observed_at/price 선 차트. 신호 전 OHLC 생성·보간 없음. 분 번호가 빠지면 연결하지 않음 |
| PRE-PUMP | 저장 유형/strength/체크포인트 값은 조회 가능. 정확한 체크포인트 기록 시각·연속 관측·장기 상세 곡선은 미지원/미검증 |
| 공통 특징·전략 최적화 | 새 연구 기능 없음. 저장 당시 지표 조회만 가능 |

일반 SURGE는 기존 5/10/30/60분이다. 10분을 15분으로 바꾸지 않는다. minute0~지평 끝의 실제 저장 가격·상대 관측 시각·양수 유한 값·끝점의 저장 return 일치가 모두 확인된 구간만 유효 통계에 포함한다. 중간 누락·지연·끝점 불일치는 원래 저장 값을 보존하되 집계에서 제외한다. 미도래는 PENDING, 추적 누락/지연은 자료 부족으로 나눈다. PRE-PUMP의 기록 시각을 인증할 수 없어 검증된 성과 통계에 섞지 않는다.

이 검증은 체결 신선도까지 증명하지 못한다. prices의 마지막 값이 과거 체결값일 수 있다는 V15 원래 한계가 남는다. 현재/과거 DB는 자동 병합하지 않고 전체 보기에서도 평균 성과를 합산하지 않는다. 출처별 표를 비교한다. 원본은 read-only/query_only, 짧은 읽기 예산과 메모리 캐시만 쓰며 분석 테이블/인덱스/label을 원본에 만들지 않는다.

## 5. 실제 검증 결과와 수정 이력

### 원본 동등성·실데이터 분석

원본 직접 runpy 실행과 관리 래퍼 실행에 같은 모의 REST/trade 입력을 넣고 원래 V15가 생성한 DB 전 테이블이 같음을 확인했다. 이는 네트워크 없는 격리 DB 검증이며 직접 LIVE와 웹 LIVE를 동시에 운영한 비교가 아니다. 모의 입력은 원본 DB에 삽입하지 않았다. 현재·과거 실제 DB의 분석은 별도로 읽기 전용 검증했다.

[독립 SQL 대조](../reports/v15_dashboard_integration_20261027/analysis_sql_comparison.json)에서 30분 유효 표본은 현재21, 과거685였다. 평균 변화율·상승 비율·평균 MFE/MAE와 각각의 n이 화면 API와 일치했다. 이는 제한된 저장 자료의 기술 통계이며 V15 전략 우수성의 증거가 아니다. 신호 유형/점수별 발생 수, 누락·미완료·미도래·시각 이상 처리, 분석기 부재와 원본 보존도 검사했다.

### 실제 웹 START/STOP

첫 제한 실행: 150초/120HTTP 안에서 HTTP102, analyze3회, 양쪽 수신을 확인하고 약56.5초에 정상 종료했다. 원래 DB 연결도 닫혔지만, 중복 종료 확인의 두 번째 조회가 캐시된 자신의 종료 PID를 외부 실행으로 오인해 웹 결과가 FAILED로 표시됐다. 이 버그를 고치고 회귀 테스트를 추가했다. 첫 기록의 scanned_pairs는 당시 mutable 입력 집합 크기를 읽은 값이므로 정확한 analyze 처리 수로 사용하지 않는다.

수정 후 [최종 실제 검증](../reports/v15_dashboard_integration_20261027/live_final.json):

- START202 → 실제 OBSERVING 및 웹 SUCCEEDED → 중복 START409 → STOP202 → 최종 웹 SUCCEEDED.
- HTTP102, NTP0, 약32.28초 실행, analyze1회·실제 처리101 거래소/종목 쌍.
- 목록 UPBIT298 / BITHUMB489(고유493), 구독 전송298/489, 종료까지 유효 수신143/200쌍. 이 짧은 표본이 전 시장 수신/탐지 준비 완료의 증명은 아니다.
- 관리 프로세스 생성 시각·종료 확인, DB 연결 CLOSED, 종료 후 웹 API200, 별도 fixture Python 생존을 확인했다. 다른 PID에 signal/kill을 보내지 않았다.

### 회귀 실행 중 계획 초과 — 숨기지 않는 제한

초기 전체 회귀에서 기존 V4 테스트의 기본 Server/CLI mock 두 곳이 새 V15 기본값을 반영하지 못했다. 의도한 LIVE2회 외에 준비 실행3회가 발생했고 각각 HTTP13/40/0, analyze0으로 정상 종료됐다. **예정 밖 HTTP53, 전체 실제 HTTP257**이다. 이는 사전 계획의 240 상한을 초과했으며 준수했다고 보고하지 않는다. 원본에 인위적 신호/가격을 넣거나 강제 종료하지 않았다. [실행별 기록과 원인](../reports/v15_dashboard_integration_20261027/regression_execution_incident.json).

구형 회귀는 engine=V4를 명시하고 새 CLI 대상은 mock하도록 고쳤다. [최종 오프라인 runner](../reports/v15_dashboard_integration_20261027/run_tests.py)는 운영 V15 subprocess 생성을 audit 단계에서 차단한다. 이후 추가 운영 실행 없이 전체390 테스트 PASS(실패0/오류0)를 확인했다. 이 문제 때문에 초기 실패 기록을 최종 통과로 덮어 해석하지 않으며, 실제 API 합계를 별도로 남긴다.

### UI·보안

두 페이지/API와 실제 응답을 이용한 [Node VM DOM 렌더링](../reports/v15_dashboard_integration_20261027/ui_render.json), 신호 선택·상세 차트·점수/유형 표·현재 DB/과거 DB 구분을 확인했다. 기존 보안·에러 메시지·포트 충돌·원본 DB 보호와 V4 동결/누출 방지 테스트를 유지한다. [전체 테스트 결과](../reports/v15_dashboard_integration_20261027/all_tests.json), [로그](../reports/v15_dashboard_integration_20261027/all_tests.log).

실제 브라우저 도구의 앱/브라우저 목록이 비어 있었고 computer-use Node 런타임은 `failed to write kernel assets ... os error 3`로 초기화에 실패했다. 실제 브라우저 클릭/스크린샷·모바일 외관은 **미검증**이다. Node VM 결과를 실브라우저 QA로 보고하지 않는다. 반응형 CSS의 원본 바이트는 보존했다.

## 6. 데이터 보존·최종 Release

현재 DB는 최종 **43 SURGE·가격 이력1281·PRE-PUMP0·paper12**, integrity=ok, DELETE 모드다. [행 단위 보존](../reports/v15_dashboard_integration_20261027/data_retention.json)에서 기존43개 신호의 당시 가격/점수/지표/reason과 기존 가격 이력1246개를 모두 그대로 확인했다. 원래 V15 실행으로 가격 이력35개가 추가됐고 미완료 추적의 원래 checkpoint가 갱신될 수 있었다. 삭제·초기화·임의 마이그레이션·수동 데이터 조작은 없다.

과거 DB는 1761 SURGE·가격 이력43950·PRE-PUMP76으로 별도 유지했다. [보존 검사](../reports/v15_dashboard_integration_20261027/preservation_after.json): 작업 시작 Git 파일495개 기준 비교, V15/V4/V5.2 원본과 V4 control/CSS 바이트 동일, 외부 V7 분석기 동일. 별도 과거 보존 기록의 정적 DB21개도 지문 일치(이 DB 기준 기록은 이번 작업보다 이전임을 명시). 기존 연구 결과와 미완료 데이터는 보존했다.

마지막 Release23신호 이후 중요한 신규 자료가 있으므로 **새 비공개 Release 한 개**를 만들었다.

- [v15-backup-20261026T153734Z-7b6409ea](https://github.com/chiopasta/coin-api-v15-backups/releases/tag/v15-backup-20261026T153734Z-7b6409ea) — 태그 시각은 UTC, KST2026-10-27 00:37:34 스냅샷.
- ZIP SHA-256: `b94dbff35785b45fab26de470e3ded972243b43d94c186a3b7c9fbda67d3076d`.
- 현재43신호/1281이력과 과거1761신호/43950이력을 별도 DB로 포함. Manifest·Online Backup·CRC·SHA·integrity/FK·건수·스키마·원격 재다운로드 검증 PASS.
- 이전 `v15-backup-20261026T144330Z-a5bdb121` 유지. 공개 코드 저장소에 DB/ZIP/registry/토큰을 올리지 않았다. 자동 병합/주기 업로드/삭제 없음. [새 Release 검증 영수증](../reports/v15_dashboard_integration_20261027/release_final.json).

## 7. 사용·남은 우선순위·Git

`start_coin_api.bat --check`로 DB·기존 분석기·websocket 의존성을 오프라인 확인한다. `start_coin_api.bat`는 웹만 연다. START로 V15, STOP으로 이 웹이 관리하는 V15만 종료한다. `stop_coin_api.bat`는 관리 V15와 이 웹을 닫고 외부 V15/V4/다른 Python을 종료하지 않는다. 스캐너 전용 BAT도 이제 같은 V15 관리 래퍼를 사용한다.

기본 웹 한도는 최대86400초/16000HTTP이고 V15 preload가 먼저 실행된다. 검증용 웹150초/120HTTP는 종료해 다음 사용자의 정상 BAT 실행에 시험 한도를 남기지 않는다. 작업 종료 시 스캐너·시험 웹은 STOPPED이며 자동 시작하지 않는다.

우선순위: (1) 사용자 환경에서 실제 브라우저·모바일 외관/클릭 확인, (2) 장시간 수신·단절·중단 이후 가격 추적을 원본 규칙 그대로 관찰, (3) 다른 PC의 기존 분석기 경로/지문 확인. PRE-PUMP72h 성과·전략 유효성·시장 전체 수신 보장·24시간 무인은 미검증이다. 새 최적화/연구 엔진 개발은 이번 범위에 포함하지 않는다.

이번 소스·테스트·문서·검증 메타데이터만 커밋하고 origin/main에 push한다. 실제 commit/원격 HEAD 대조 결과는 같은 폴더의 Git 검증 자료와 최종 응답에 기록한다. 원본 DB·개인정보·인증정보·백업 ZIP·기존 런타임 로그는 커밋에서 제외한다.


Implementation commit: [`e0a95c8`](https://github.com/chiopasta/coin_api/commit/e0a95c86357c64ce5dfaba70bfb5c0b55964d7fb). Push verified: local HEAD = origin/main = Git remote main = GitHub API main. [Verification receipt](../reports/v15_dashboard_integration_20261027/git_verification.json). The following documentation-only receipt commit leaves tested source unchanged.
