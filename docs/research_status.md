# 프로젝트 상태 — 새 작업의 첫 읽기 문서

## 2026-10-26 V15 DB 비공개 Release 백업·이전 검증

- [안전한 백업·다운로드·격리 복원 절차](v15_release_backup_20261026.md). 현재 코드 원격은 public이므로 사용자 동의로 별도 private `chiopasta/coin-api-v15-backups`를 생성했다. 새 [Release](https://github.com/chiopasta/coin-api-v15-backups/releases/tag/v15-backup-20261026T144330Z-a5bdb121)에 ZIP/체크섬을 올리고 재다운로드·CRC/SHA-256/DB integrity/schema/count 검증을 완료했다. 기존 tag/asset 덮어쓰기 없음.
- 23:43:30 KST Online Backup 스냅샷: 현재 archive DB 23신호·가격이력740, 과거 standalone DB 1761신호·가격이력43950. 두 DB integrity=ok·FK위반0. 원본은 mode=ro로 열고 64페이지 단계/20초 예산, 실제 backup 약0.086/0.034초. Manifest에 임의 PC/DB UUID·시각·스키마 지문·건수·SHA 기록, 인증정보와 실제 사용자/호스트 식별값은 넣지 않았다.
- 새로운 수동 도구 `v15_transfer`/`v15_release`만 추가했다. engine/UI/탐지 규칙·기존 DB·연구 자료 변경 없음. 자동 주기·삭제·자동 병합 없음. 두 출처의 실제 비교는 스키마 차이로 격리됐다. 다른 PC는 새 폴더에만 검증 복원하며 source lineage/정수ID 충돌·추적 갱신을 자동 판정하지 않는다.
- 신규12+기존59 **71테스트 PASS**, 원격 게시 후 별도 새 폴더 download 경로도 PASS. 실제 다른 PC·GB급 DB·장기 네트워크 장애는 미검증이다. 사용자 V15 종료/시그널0, 이후 수집 증가·프로세스 생존 확인. DB/ZIP/registry는 Git에서 제외하고 도구·문서·비밀정보 없는 검증 자료만 commit/push한다.

## 2026-10-26 V15 관찰용 대시보드 범위 확정·호환성 설계 — 구현 없음

- [실행 구조·DB 호환성·최소 통합 설계](v15_dashboard_compatibility_design_20261026.md). 새 탐지/연구 엔진·최적화가 아닌 **검증되지 않은 V15 실험 전략의 관찰 대시보드**로 범위를 고정한다. 원래 V15의 수집·탐지·저장·추적을 그대로 사용하고 V4/V5.2는 보존하되 대신 실행/주력 연결하지 않는다.
- 현재 웹 버튼은 여전히 V5.2를 실행하며 V4 전용 schema로 V15 DB를 직접 읽지 못한다. 이번에는 운영 코드/UI/BAT/DB를 변경하지 않았다. 원본 이전 없이 읽기 전용 조회·기초 통계를 연결하는 설계만 작성했다. V15 시작/종료·감시 수/실제 scan 상태는 별도 호환성 검증이 필요하며 현재 사용자 실행은 외부 소유·제어 제외다.
- 정적 legacy 1,761개와 현재 후보 DB 21개의 저장 지표를 원래 V15 점수 함수로 대조해 모두 일치했다. raw WS 완전 replay/성과 검증은 아니다. 23:30:33 후보 DB는 21 SURGE·가격 이력461·PRE-PUMP0이며 계속 누적 중이다. 과거 보존본 전체의 현재 V15 버전 귀속은 미확정이다.
- 메모리 DB로 SURGE 중간 누락 허용·65분 관측의 minute60 저장·PRE-PUMP 지연 시 여러 체크포인트 동일 현재값 저장을 재현했다. 원래 로직은 보존하고 관측 완전성과 저장 성과를 구별하도록 설계했다. 외부 V7 분석기의 조회/숫자 해석은 호환 가능하나 TP/SL grid·추천·최적화는 제외한다. analyzer_v6.py는 두 조사 루트에서 미발견이다.
- [호환성/보호 증거](../reports/v15_dashboard_design_20261026/compatibility_results.json), 관련 오프라인 **59테스트 PASS**. 실제 API/NTP·scanner 시작·프로세스 종료·최적화0회. 사용자 V15 PID28300/26448 보호, 기존 DB/연구자료 보존. 웹 제어·장시간 안정성·전략 유효성은 미검증이며 운영 교체·commit/push는 하지 않았다.

## 2026-10-26 V15 기준 V5.2 평가0 진단 — 운영 코드 변경 없음

- [원인별 증거·실데이터 재현·한계](scanner_v52_v15_diagnosis_20261026.md). V15는 점수/거래대금/10초·CWD 상대 crypto DB, 현재 V5.2는 V4 range/cluster/UTC5분·별도 runtime DB로 다른 정책이다. 현재 사용자 V15 프로세스는 제어/종료하지 않는다.
- 전체 V5.2 시험은21:30 최초 격자18.385초 전 종료와 **미완료job289+483·공통watermark15:30 정체**가 동시에 있었다. 시간만+1시간인 실제 DB 복제본도평가0. 실데이터가 누적돼도job1개가남으면평가0,실제저장2page로완료후평가4/신호1을재현했다. 기본180HTTP는적격773쌍최소1page초기화에도부족하므로단순대기만으로해결된다고보지않는다.
- 동일실데이터에서기존V4/V5.2경로각7신호·core5테이블행/값hash일치. V15확정봉투영은1신호(score75), 실제10초틱재현/우열비교가아니다. 작은WS시험은29/30분으로NULL. 전체WS0봉의정확한탈락원인은raw frame/since상세가없어미확정이며,이전‘첫완전분전종료’설명은확정재검증하지못했다.
- standalone과backup의1,761신호legacy테이블값동일. 현재V4의163신호hash는10/8보존본과같고215보고서hash와다르다.215파일실물/52개ID/외부선택경위미확인. 신규API/NTP0·관련29테스트PASS·기존코드/UI/BAT/DB/연구결과보존. 진단자료만추가하고운영수정·commit/push없음.
- 사용자V15실행은유지했고새archive crypto DB가초반0에서23:06:51 **5신호·가격이력88개**로증가함을read-only확인했다. 현재V15의신규탐지·저장실제작동증거이며진단자료를운영DB에삽입한것이아니다.

## 2026-10-26 V5.2 전체 KRW WebSocket 수집 — PARTIAL

- [개발·실제 검증·미완료 범위](scanner_v52_validation_20261026.md). 권위 있는 Git 경로는 현재 `C:\dev\coin_api-1`이다. 현재 BAT/웹 manager는 새 `forward_scanner_v52`를 실행한다. 기존 V4.2/V4.3의 5종목 dataset·직접 CLI와 연구 코어/정책은 그대로 보존한다.
- 실제 목록 UPBIT 298/BITHUMB 489, 공식 수신 상태 제외 2/12로 적격 **296+477=773쌍**. 8개 WS 연결에 787쌍 요청, 적격 773쌍 응답 확인, 최근60초 동시 ACTIVE 최대363쌍. 등록/요청/응답/신선 수신/평가를 분리한다. 전체 실행의 탐지 평가·30분 완전 자료는 **0쌍**, 자연 LIVE 신호0이다. 최초 signal_start21:30 이전 STOP이고 전체 초기화도 미완료, 전체 WS 확정 봉도0이다. 소규모 BTC/ETH 4쌍에서는 실제 WS 봉4개 저장·기존 탐지/분석 연결은 합성 시험으로 검증했다.
- 실제 시작2회·합계 **55 HTTP/80 상한·30 NTP/48 상한**, 모든 gate PASS·오차+불확실성 최대0.124531초. 정상 웹 STOP/SAVED·BAT 웹 종료·양쪽 DB 무결성/정상reap 통과. 시계/서비스 설정 변경0, 다른 Python/CHIO BOT3개 유지. 현재 추가 LIVE 실행 없음, 소유 스캐너/웹 종료 상태다.
- 현재 원본은 작업 전부터 **163신호**이고 이전 문서·요청의215와 다르다. 기존DB35개 바이트·현재163신호·기존 연구/분석 결과를 보존했다.215개 실물 보존은 입증 불가다. 최종 [테스트](../reports/scanner_v52_20261026/test_result.json), [보존 검사](../reports/scanner_v52_20261026/completion_checks.json).
- 목록은 매 실행/600초/단절 후 조회하되 membership 변경은 새 동결 dataset 필요로 BLOCKED한다. **동일 dataset의 신규 상장 자동 추가·V5.2 resume/세대 전환은 미구현**이다. 마지막 운영 보강은 오프라인 검증이며 추가 LIVE 재실행은 하지 않았다. 전체 WS/native REST 대조·전 시장 평가 완료·자연 신호 후속·브라우저 클릭/외관·장시간/절전/재부팅은 미검증이다. **24시간 무인 NOT_READY**.

## 2026-10-26 감시5개·전체KRW범위 점검

- [조사·표시 수정·예산](scanner_market_scope_20261026.md). 현재5개는BTC+알트4개의고정관측범위(거래소별5·10쌍/신호8쌍)이며집중선정수가아니다. V4.2문서/검증에명시된범위로누락된max_markets가아니다. 현재BAT CLI/웹은같은V4.3, 구형V15는전체KRW trade WebSocket·preload50제한으로경로/정책이다르다.
- 실제목록2HTTP만조회: 업비트298·빗썸489·합계787쌍/고유493종목. 주문가능/정지필드는미제공이라공개지원목록수로표시한다. 현재스캔·전체목록/시각·PENDING후속평가종목을분리하고CLI/웹같은snapshot을쓴다. 다음신규worker는기존2개목록응답을추가HTTP없이기록한다. 기존탐지/결측/시계/16000HTTP/86400초불변이다.
- 전체REST매분24시간계획값1134856요청·round간격하한196.5초로상한초과다. 준비후완전round18회/일정도라전체화하지않았다. WS확정분봉+제한REST복구의검증방안/추적8쌍시13096요청예시를보고했으며새WS/장기실행은없다.
- **170개중169통과·구형Python미설치1skip**, [테스트](../reports/scanner_market_scope_20261026/test_result.json). 사용자활성관측3개프로세스/launch/예산/종료표식보호·idle웹만교체,실제API/CLI/독립SQL/렌더5/493/후속0일치. 원본215신호·기존정적DB16개·연구결과보존([검사](../reports/scanner_market_scope_20261026/completion_checks.json)). 활성runtime/캐시는자연갱신으로별도대조한다. Windows Computer Use URL확인차단으로실브라우저외관/모바일은미검증. 기존사용자Scanner/웹은계속실행중이며이번작업이새로시작한scanner는0이다.

## 2026-10-26 SCANNER_CONTROL_FAILED 실제 재현·상태 파일 읽기 수정

- [시간순 조사·원인·수정·검증](scanner_start_diagnosis_20261026.md). 사용자 직전 실행은 NTP3단계PASS, 시작22.65초후 수동Stop이수집기시계검사중접수됐다. STOPPED/CANCELLED_BEFORE_COLLECTION만으로자동종료버그로판정하지않는다. 과거웹예외는미기록이라내부원인확정불가다.
- 진단추가후 **실제API202→STARTING에서같은SCANNER_CONTROL_FAILED재현**. 시작확인기의관리상태JSON `Path.open`이PermissionError(errno13/winerror없음)로실패해27.23초에fail-safe취소됐다.75초timeout/NTP/거래소/worker crash가아니다. 해당Windows읽기오류만0.5초재시도예산으로복구하고지속오류·JSON/크기제한은차단한다. 원시예외/토큰없이요청·단계·예외·Stop을기록한다. 실제HTTP_END/상세200을ERROR로표시하던연결상태불일치도수정했다.
- 수정후같은API에서읽기충돌3회복구, **OBSERVING·양쪽CONNECTED·2746봉저장→STOPPED/SAVED PASS**. worker21.02초·19HTTP모두200·신호0,종료후웹200,소유프로세스/listener종료. 실제시작총2회(재현1/수정후1),NTP40/48·HTTP19/80. 시계/전송/수집엔진해시는이전과동일하다.
- **164개중163통과·구형Python미설치1skip**,기존DB13개해시/전테이블건수·원본215신호·연구결과·사용자실행로그보존. [테스트](../reports/scanner_start_diagnosis_20261026/test_result.json), [보존](../reports/scanner_start_diagnosis_20261026/completion_checks.json). 기존4개문서/관리pointer외데이터·이전보고서변경없음. 장기/절전·공유주체상세추적·실브라우저외관은미검증,24시간무인NOT_READY다.

## 2026-10-26 V5.2 실제 스캐너 시작 경로 최종 검증

- [조사·변경·실제 검증](scanner_start_final_20261026.md). 단독/웹은 같은 시계 정책이며 웹은 관리·감독·수집의 새 gate3회다. 캐시/정확도 기준 차이가 아니라 Windows NTP 수신timeout을 확인했다. NTP child cwd/환경 고정, 제공자별 허용 필드 진단,1.5초 수신 대기·표본당최대2/전체2재시도·8요청/전체15초 상한, readiness75초를 적용했다. 필수6표본·1초 정확도/불확실성·0.5초 spread·신선도·Windows 안전 조건은 유지한다.
- 실제 시작API **2회 OBSERVING → STOPPED/SAVED PASS**. worker13.48/15.86초·각19 HTTP·신호0, 정상reap/forced0/close_errors없음. 중복409·외부Origin403·종료후웹200·실제PASS/오류해제 상태를 확인했다. 단독1회는Windows1/3표본으로안전BLOCKED였다. 전체NTP45/56·HTTP38/80, 기존10거래소/종목쌍을늘리지않았다.
- **157개 중156통과·구형Python미설치1skip**, 오류0. 원본215신호·기존DB6개해시/전테이블건수·연구결과보존, 작업manager/worker/listener종료. [테스트](../reports/scanner_start_v53_20261026/test_result.json), [보존](../reports/scanner_start_v53_20261026/completion_checks.json). 새자료는격리관측DB/보고서에추가했다. NTP응답누락은재발가능하며장시간·자연신호후속성과·실브라우저외관은미검증, **24시간무인NOT_READY**다.

## 2026-10-26 V5.2 Windows 루트 분산·직접 NTP 교차 검증

- [원인·변경·검증](scanner_clock_v52_cross_validation_20261026.md). 기록된 루트 거리7.7814858초의 독립 필수 조건 때문에 직접 측정이 정상이더라도 차단되던 경우를 재현했다. 초/밀리초·고정소수점 변환 오류는 없었다. Windows 동기화 건강 상태·신선도·네트워크 원본이 정상이고, 새 직접 두 제공자6표본·서로 다른 응답IP·각 오차+불확실성≤1초·spread≤0.5초·오차 구간 중첩·15초 신선도를 모두 만족하면 루트 분산 경고를 보존한 채 교차 검증한다. 지연 자체 초과·동기화 실패·오래된 자료·필수 NTP 누락은 계속 차단한다. 검사 우선순위에서 오래된 동기화가 큰 루트 분산에 가려지지 않게 했다.
- 과거 기록의 직접 측정 bound0.0871초는 당시 시각 재현에만 사용하며 현재 admission으로 재사용하지 않는다. 실제 현재 검사1회는 Windows 루트 거리0.3403초·NTP 오차약21~31ms로PASS(7시도/6유효/1timeout). 현재 Windows 원본은Google이며 이 작업은 시각·서비스·원본·레지스트리를 변경하지 않았다.
- 실제 시작API202 후 PRECHECK에서 종료API202를 요청했다. 이 검사에서는 Windows NTP1표본이 재시도 후에도 없어 **CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE / BLOCKED**(7시도/5유효/2timeout). manager종료·worker/관측DB/거래소HTTP0을 확인했다. 실제 NTP총14/사전상한24. 실제 정상LIVE시작은 미검증이며 좋은 결과가 나올 때까지 재시도하지 않았다.
- 회귀 **151개 중150통과·1구형Python미설치skip**, 실패/오류0. 실제 오류 코드·원인 메시지·마지막 검사 문구·교차 검증PASS 경고 및 오류 해제를 API/JS렌더로 확인했다. 실제 브라우저 시각QA·장시간·재부팅은 미검증이다. 원본DB·신호·연구 결과와 탐지/label/결측 정책은 보존한다. [테스트](../reports/scanner_clock_v52_20261026/test_result.json), [보존 검사](../reports/scanner_clock_v52_20261026/completion_checks.json). 24시간 무인운영은 계속NOT_READY다.
- 최종 기준313파일 중309개바이트동일·의도한문서2개/관리pointer2개만변경. 기존DB·연구결과해시동일, 원본신호215·DB6개quick_check=ok, manager/worker0·8765listener0을확인했다. 현재BLOCKED는NTP응답누락이력이며실행중Scanner는없다.

## 2026-10-26 웹 없는 스캐너 실행 BAT

- 루트 `start_scanner_only.bat` 추가. 더블클릭하면 기존 Python 선택 도우미의 `_scanner` 진입점으로 관측 엔진만 실행한다. 웹 서버·브라우저를 열지 않으며 기존 NTP·잠금·STOP·저장 로직을 재사용한다. 기본 최대600초/180 HTTP, 종료는 Ctrl+C 또는 기존 `stop_coin_api.bat`다. 기존 종료 BAT는 열려 있는 이 프로젝트 웹도 함께 종료한다.
- 실제 BAT `--check`, 스캐너 전용 디스패치, CMD/PowerShell의 한글·공백·구두점 경로 전달을 오프라인 검증했다. 기존 BAT 관련3개 검사 중2통과·1구형Python미설치skip. 점검 전후 data 파일 크기·수정 시각 동일. 실제 LIVE/NTP/API 호출은 하지 않았으며 새 BAT의 실제 수집·물리 더블클릭은 미검증이다. 탐지 규칙·DB·기존 웹 BAT 변경 없음.

## 2026-10-26 V5.1 웹 운영 버튼·급등 신호 분석실

- [사용 안내](scanner_v50_dashboard.md), [검증 보고서](scanner_v51_validation_20261026.md). 실시간 감시와 급등 신호 분석의 **두 페이지 구현**. BAT 기본은 웹만 열고 웹 버튼으로 기존 관측 엔진을 시작·정상 종료한다. 웹 종료 버튼은 대시보드를 유지한다. loopback·Origin/Host/Fetch-Metadata·수명별 토큰으로 제어를 보호한다. 지연 시작 취소·중복 차단·PID 생성 시각 확인·기존 STOP/저장 검증을 재사용한다.
- 기존 후속 평가 엔진을 메모리 복제본에 재사용하고 파생 결과만 별도 분석 DB에 저장한다. 원천 DB·feature·label·COMPLETE는 보존한다. 재시작 후 미완성 평가를 기존 저장 봉으로 재개한다. 5/15/30/60분 지평별 분모, 30분 상승 비율·평균 변화·MFE/MAE, 실제 저장 패턴·상세 차트를 제공한다. 연구/신규 관측 및 LIVE/CATCHUP을 구분하며 성능 우수 판정을 하지 않는다. 기존 신호 기준 시각과 실제 탐지 시각, 가격 변화와 거래 수익률을 구별한다.
- **136개 검사 중135통과·1환경skip**, 오류0. 실제 loopback 제어·인증 거부·BAT 웹 재시작·이전 토큰 거부·독립 SQL 통계 대조·빈 상태/페이지 분할 PASS. 격리한 실제 Python 프로세스 fixture에서 제어 API의 시작 확인·정상 저장 종료·다른 Python 생존·웹 유지 PASS. 실제 LIVE/NTP PASS 시험으로 간주하지 않는다. [테스트](../reports/scanner_v51_20261026/test_result.json), [DB 대조](../reports/scanner_v51_20261026/analysis_comparison.json).
- 실제 시작은 사전 고정120초/80HTTP·기존10시장 범위에서 **1회**. Windows 시간 서비스 미검증과 약+1.44~+1.45초 offset으로 **CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY / BLOCKED**. NTP7시도/6응답/1timeout, worker·관측DB·거래소HTTP·신규신호0. 기존1초 기준을 유지하고 추가 재시도·시계/서비스 변경 없음. 초기 웹 readiness 초과는 분석 준비를 백그라운드로 분리해 해결했다. [실제 제어](../reports/scanner_v51_20261026/final_http_checks.json).
- **운영 검증 PARTIAL /24시간 무인 NOT_READY**. Computer Use가 현재 Windows 브라우저 URL을 신뢰할 수 없다고 중단해 브라우저 클릭·차트/모바일 외관·물리 BAT 더블클릭은 미검증이다. 시계 PASS 후 실제 LIVE 정상 저장·자연 신규 신호30/60분·장시간/절전/재부팅도 미검증이다. 주문·최적화·Windows 자동 시작/종료 없음.
- 작업 시작 시 요청 경로는 없었고 현재 저장소는 `C:\dev\Coin_api`였다. 원본은 이미 **215신호(LIVE44/CATCHUP171)**였으며 과거163개로 맞추지 않고 현재 DB 전체 해시를 보존한다. 전체30분 유효174개·평균+0.27%·상승50.57%; 연구보관LIVE만35개·+0.37%·68.57%다. 보호86중실물75개(과거해시일치63·작업전차이12), 작업전부재11개를 구분한다. 현재 존재한 보호 입력은 모두 이번 기준 해시를 유지한다. STALE_OPEN115 조정 보고서는 보존하되 원천crypto_scanner.db 부재로115행 실물 재검증은 불가하다. [보존·종료 검사](../reports/scanner_v51_20261026/completion_checks.json).
- 최종 소유 manager/worker/웹/지연 시작 프로세스0·8765 listener0. 기존 DB5개 quick_check=ok, 보호 입력75개와 기존 파일279개를 대조해 의도한 문서 수정 외 변경0을 확인했다. 작업 전의 dirty 잠금 파일은 수정/커밋하지 않는다. 최종 Scanner BLOCKED는 보존한 시계 실패 이력이며 실행 중인 프로세스는 없다.

## 2026-10-26 V5.0 독립 localhost 웹 대시보드

- [사용 안내](scanner_v50_dashboard.md), [검증 보고서](scanner_v50_dashboard_validation_20261026.md). 대시보드·BAT **PASS**, 관측 인프라 **PARTIAL / 24시간 무인 운영 NOT_READY**. Python 표준 라이브러리·단일 다크 페이지, `http://127.0.0.1:8765`, CHIO BOT과 독립이다. 기존 BAT로 시작·상태·정상 종료하며 웹 RUNNING과 Scanner LIVE를 분리한다.
- 기존 163개 신호 목록·실제 저장 분봉 상세·차트·KST·5초 폴링·필터·새로고침 복원·모바일·빈/오류 상태를 실브라우저로 확인했다. 점수는 기존 엔진 미정의라 UNKNOWN. 원래 연구 평가를 유지하며 보관 DB의 화면용 후속 지표는 연속된 실제 원천봉만 사용한다. 실제 PUMP 결측은 84개 종가·6개 분리 구간, 15/30/60분 NO_DATA다. 원천 생성·보간·label/전략/임계값 변경 없음.
- 첫 제한 시작은 세 계층 시계 PASS 후 Windows 상태 JSON 교체 충돌로 안전 STOP됐다. worker 4.721초·거래소 HTTP0·신호0·정상 reap·forced0·close_errors 없음. 관리 JSON만 최대0.5초 재시도를 추가하고 실제 핸들 충돌·지속 오류 차단을 검증했다. 기존 venv 경로의 수직 탭도 수정했다. 두 번째 시작은 NTP 필수6표본 중5개로 **BLOCKED**, worker/관측 DB 미생성. 전체 NTP25시도/23응답/2timeout, 기존 1초/루트 거리/신선도/두 제공자/점프 안전 기준 불변이다. 추가 실제 시작 없음.
- **선별105개 PASS**, 전체 회귀·백테스트 없음. CMD/PowerShell·BAT shell association·한글/공백 실제 웹 실행·포트 충돌 거부·중복 웹 재사용·다른 Python 서버 생존·정상 종료/재실행 PASS. 물리 마우스 더블클릭·수정 후 NTP PASS 수집·자연 신규 신호와30/60분 완료·장시간/절전/재부팅은 미검증이다. 새 수집 완성도는 NO_DATA/분모 없음이다.
- 원본163·보호86·STALE_OPEN115·이전 증거169·V4.9 원시26·V4.10 증거/기존runtime101파일 해시 보존, DB quick_check=ok. 최종 소유 manager/worker/웹 프로세스0·8765 listener 종료. 최근 Scanner BLOCKED 기록은 NTP admission 이력이다. 주문·원본 덮어쓰기·자동 시작·장시간 관측·Windows 종료/재부팅 없음. [보존·종료 검사](../reports/scanner_v50_20261025/completion_checks.json).

## 2026-10-25 V4.10 Windows BAT 실행·종료·상태

- 루트 `start_coin_api.bat`·`stop_coin_api.bat`·`status_coin_api.bat` 추가. [사용 안내](scanner_v410_windows_launcher.md), [검증 보고서](scanner_v410_launcher_validation_20261025.md). 런처기능 PASS·인프라 **PARTIAL /24시간 NOT_READY**, 최종 **STOPPED/SAVED**다.
- 기존V4.3/V4.9 엔진·시계·탐지·정책 변경0. 새 관리 계층이 Python3.11+ 자동확인·전체시계검증·기존잠금/STOP을 재사용하고 매번별도DB를 만든다. 기본은 수동종료까지의감독실행이되 기존86400초/16000요청 상한과fail-safe를 유지하며 자동재시작하지 않는다. API키/.env/추가패키지 불필요다.
- PID+Windows 생성시각·고유launch경로로 소유권을검사하고 STOP만보낸다. 정상summary/reap·DB검사·빈WAL·로그flush 후SAVED, 미확인은UNKNOWN/BLOCKED다. 상태숫자는새DB/receipt/시계기록에서조회한다. 다른Python/CHIO BOT/수동기동을죽이지 않는다.
- 실제첫BAT Shell연결은NTP누락으로BLOCKED·DB/worker/API0. 두번째PowerShell BAT는전체시계PASS 후23:33:39.879~23:34:12.976 KST worker33.096초·29HTTP모두200·신호0, CMD상태/중복차단/종료와종료후PowerShell상태/종료를확인했다. 총NTP27패킷.2608봉은23:35이전warmup으로자연신호/후속성과표본은없다.
- **선별81개 PASS**, 전체회귀/백테스트없음. 실제CMD/PowerShell의한글·공백·구두점경로오프라인기동, 잘못된/구형Python, 오류pause, Windows잠금, 임시DB상태집계 및mock시계/PID재사용을검증했다. Shell BAT연결은확인했지만물리마우스더블클릭·한글경로LIVE·실제창X종료·24시간은미검증이다.
- 원본163신호·보호86입력·STALE_OPEN115·이전증거169파일·V4.9 원시26파일 hash유지. 원본/새DB quick_check=ok·활성Scanner0. 주문·키·자동실행등록·Windows설정/시각/종료/재부팅0. [완료 검증](../reports/scanner_v410_20261025/completion_checks.json).

## 2026-10-25 V4.9 NTP 제한 재시도·LIVE 재개 검증

- [V4.9 보고서](scanner_v49_ntp_recovery_20261025.md), 인프라 **PARTIAL / 제한 LIVE admission PASS·관측 완료 /24시간 NOT_READY**. 기존 NTP 검사2회 중1회 timeout을 재현했다(Windows5/6·Cloudflare6/6, 전체1/2 PASS). 근본 손실 지점은 UNKNOWN이며 서버/경로/방화벽 중 어느 원인인지 단정하지 않았다.
- 새 전송 계층은 probe 내 동일 제공자2초·전체0.5초 직렬 간격, 수신timeout만2초 backoff 후 논리 표본당1회·전체2회 재시도한다. 최대8시도/내부10.5초/child12초/전체15초이며 두 제공자 각각3개 유효 표본·1초 오차/불확실성·0.5초 spread·구간 중첩·15초/3600초 신선도는 그대로다. 패킷 계산과 탐지 구현은 재사용했고 검사 전체 시간 점프도 차단한다.
- 개선 비교2/2·새 검사 전체9/9 PASS, 새 전송54/56응답이다. 실제 최초supervisor 및resume worker에서 각각1개 Windows 수신timeout을 새 유효 표본으로 복구했다. 실패 시도는 보존됐으며 유효 표본 부족을 무시하지 않았다. 전체 검사 최대7.440초·표본 나이 최대7.236초다. 직접NTP 총68시도/128상한이다.
- 종료 후 Windows offset **+67.631~+70.436ms**(최대 불확실성14.443ms), Cloudflare **+69.438~+70.848ms**(70.335ms), 최대 offset+불확실성140.552ms다. Windows 루트 거리0.12161355초, W32Time Running/Automatic·Google·계층2·윤초0·오류0이며 시간/서비스/방화벽 설정 변경0이다.
- 별도 `episode_20261025_v49`에서 최초 **22:34:03.761~22:35:26.120 KST** STOP, 동일DB resume **22:35:33.421~22:48:07.919**, 합계836.844초·공백7.301초다. LIVE161회+API사전4회=165HTTP 모두200, 신규신호0, 수집오류/미완료job/중복0, 두 worker/supervisor 정상reap·forced0·close_errors={}다. 실행 중600초 재검증도PASS다.
- 신규 원천30분 완전4/24=16.67%, 원천/가격slot483/720=67.08%(격자 중첩 포함), SOURCE_ABSENT237slot·NOT_COLLECTED0·실시간NO_TRADE증거0이다. 미입증151·300초 초과86slot은 가격 평가 불가이며 UNKNOWN 유지다. 기존25%·사후98.75%는 별도 시점/분모 그대로 보존했다. 실제 신호30/60분 완료는N/A/미검증이다.
- **선별69개 통과**, 실제HTTP/UDP 금지·전체 회귀/백테스트 없음. 원본163신호·보호86입력·STALE_OPEN115·이전 증거138파일 hash 유지, 원본 및 이전V4.3 DB3개와 새두DB quick_check=ok다. RSS36.219MiB·CPU9.043%/한코어·새episode1.862MiB, 장기 자원/절전/재부팅은 미검증이다. 활성 Scanner0·주문/키/CHIO BOT통합/장기자동시작/Windows종료0. [실제 관측](../reports/scanner_v49_20261025/live_result.json), [보존 검증](../reports/scanner_v49_20261025/completion_checks.json).

## 2026-10-25 V4.8 Windows 루트 불확실성 분석

- [V4.8 보고서](scanner_v48_windows_uncertainty_20261025.md), 인프라 **PARTIAL / 전체 시계 FAIL·LIVE BLOCKED /24시간 NOT_READY**. Windows 루트 조건은 자연 수렴으로 해소됐지만 이후 두 번의 새 전체 검사에서 각1개 Windows NTP 표본 timeout으로 차단됐다. 실패 표본을 제외해 통과시키거나 허용 기준을 변경하지 않았다.
- 동일 Google 원본·1024초 자연 폴링에서 루트 분산 **7.7630189→3.8087560→1.8216905→0.8362296초**, 마지막 루트 거리 **0.8558684초**를 확인했다. 복구 후 초기 필터 수렴과 일치한다는 추론이며 비공개 Windows 내부 상태까지 입증하지는 않았다. 원본 직접 광고 분산은0.000091553~0.000122070초로 호스트 값과 구분된다.
- 최종 성공 표본은 Windows offset **+47.334~+48.517ms**(최대 불확실성12.845ms), Cloudflare **+50.841~+52.435ms**(71.952ms), 최대 offset+불확실성124.387ms다. 그러나 필수6표본 중1개 누락으로 전체 정확도/신선도는 FAIL/UNVERIFIED다. 원래1초·0.5초 spread·구간 중첩·15초/3600초 신선도 조건과 production 코드는 불변이다.
- W32Time 시작/종료 조회 모두 Running/Automatic, 윤초0·계층2·오류0이다. 읽기 전용 추세31회/1801.286초, 직접NTP24패킷 중22응답(Windows7/9·Cloudflare9/9·추가Google6/6). UDP timeout의 경로/서버/방화벽 원인은 UNKNOWN/BLOCKED이며 설정·레지스트리·시각·서비스·강제resync 변경0이다.
- **실제LIVE0회·resume0회·거래소HTTP0회·신규신호0개**, 새 관측DB 없음. 원천/가격 완성도·후속30/60분 예약/완료는N/A다. 기존25% 및 사후98.75% 결과와 NO_TRADE/UNKNOWN 정책은 유지한다. 실제 재부팅·절전·자연60분·24시간 자원/장애 운영은 미검증이다.
- **선별64개 통과**, 실제HTTP/UDP 금지·전체 회귀/백테스트 없음. 원본163신호·보호86입력·STALE_OPEN115·이전 증거113파일 hash 유지, 원본 및 이전V4.3 DB3개 quick_check=ok. 주문·키·CHIO BOT 통합·장기자동시작·Windows종료 없음. [최종 결정](../reports/scanner_v48_20261025/live_decision.json), [보존 검증](../reports/scanner_v48_20261025/completion_checks.json). 다음은 NTP 응답 누락 조사 후 기존 전체 gate를 통과한 새 episode의 제한 관측이다.

## 2026-10-25 V4.7 복구 시계 독립 검증·조건부 LIVE 준비

- [V4.7 보고서](scanner_v47_clock_validation_20261025.md), 인프라 **PARTIAL / 전체 LIVE admission BLOCKED /24시간 NOT_READY**. 사용자 복구 후 W32Time Running·Automatic, 계층2·윤초0·Google 원본·동기화 오류0을 확인했다. 이전4.39초 지연이 계속되는 상태는 아니다.
- 외부 Windows·Cloudflare 각3표본을2회 독립 측정했다. 최종 Windows offset **+9.274~+13.232ms**(최대 불확실성17.059ms), Cloudflare **+10.648~+11.159ms**(70.392ms), 최대 offset+불확실성81.550ms로 외부 정확도PASS다. 최종 가장 오래된 표본은약1.297초 전이다.
- 다만 Windows 루트 분산 **7.7630189초**, 지연0.0390809초, 루트 거리 **7.78255935초**로 기존1초 안전 조건을 충족하지 못했다. 원본 동기화는21:12:28, 최종 경과378.842초다. 작은 외부offset으로 큰 Windows 분산을 덮어쓰지 않았고 시간/서비스/레지스트리를 변경하지 않았다.
- V4.6의 Windows 루트 분산 미검사 결점을 운영 계층에 보강했다. 영문/한국어 필드·동기화 상대 나이≤3600초·루트 거리≤1초, 직접NTP표본 나이≤15초를 요구한다. 기존1초·spread0.5초·packet계산·단조 제한·점프/절전 guard는 그대로다. 탐지 전략·threshold·label·점수·collector·300초 가격 정책은 불변이다.
- 시계 gate실패로 **LIVE0회·실제resume0회·거래소API0회·신규LIVE신호0개**, 새 관측DB는 생성하지 않았다. 원천/가격 완성도·수집성공률·실제30/60분 예약/완료는N/A다. NO_TRADE 실시간/사후 증거 추가0, 근거 없는 구간은UNKNOWN 유지. 기존25%·사후98.75% 결과는 보존했다.
- **선별76개 테스트 통과**, 실제HTTP/UDP 금지·전체 회귀/백테스트 없음. 작은offset+큰Windows분산·표본신선도·시각역전·차단시worker미생성, 기존leakage/PENDING/재연결/자원guard를 검증했다. 실제60분·절전/24시간 안정성은 미검증이다.
- 기존163신호·86보호 입력·STALE_OPEN115·이전 증거103파일 hash 유지, 원본/이전 관측DB quick_check=ok. 주문·키·CHIO BOT통합·자동재시작·Windows종료 없음. [시계 증거](../reports/scanner_v47_20261025/clock_final.json), [LIVE차단 결정](../reports/scanner_v47_20261025/live_decision.json), [보존 검증](../reports/scanner_v47_20261025/completion_checks.json). 다음은 루트 분산 조건 충족 후 신규DB의 감독하 제한 관측이다.

## 2026-10-25 V4.6 시계 검증 원인 규명·LIVE 준비

- [V4.6 보고서](scanner_v46_clock_recovery_20261025.md), 인프라 **PARTIAL / 실제 LIVE admission BLOCKED**. W32Time STOPPED·Manual, 서비스 조회0x80070426, 비도메인 PC의 서비스 시작 트리거는DOMAIN JOINED다. 현재 부팅 이후 실행 이력 없음(exit1077), 마지막 확인 동기화 로그는10/24 00:07 KST다. 환경 설정·서비스·시각을 변경하지 않았다.
- 두 NTP 제공자에 실제 접근 성공. 최종 로컬 시각20:28:55 이후 Windows offset **+4.39309~+4.39440초**(표본 최대 불확실성0.012968초), Cloudflare **+4.39595~+4.39608초**(0.069907초). 로컬이 약4.39초 느려 기존1초 한도를 벗어난다. 이번 차단은 허용 가능한 시계의 오탐이 아니다.
- 서비스 실패로 외부 측정까지 생략하던 진단 결점, offset 불확실성 미기록, 절전 복귀 재검증 공백을 수정했다. 기존1초·spread0.5초를 유지하고 전체 오차 구간이1초 이내인 두 제공자의 일치를 요구한다. 외부 검사 child12초·서비스 조회3초, 최대6 NTP 패킷이다. awake 타이머/검사 공백에 따른 복귀 재검증·실패 차단을 추가했다.
- 거래소 진단은 BTC ticker 각1회, 총2회 모두200. HTTP Date는 독립 시계 대신 쓰지 않는다. 빗썸 ticker의 numeric trade timestamp가 명명된UTC 시각보다32400.613초 앞서는 응답을 보존했으며 자동 보정·탐지 입력 사용은 하지 않았다. 기존 원천 분봉 시각 경로는 변경하지 않았다.
- LIVE 조건이 충족되지 않아 **실제 scanner 시작0, 재시작0, 신규LIVE신호0**. 실제60분 후속·절전/복귀·24시간 운영은 미검증이다. NO_TRADE 자동 체결 증거 수집도SKIP이며 source absence는 UNKNOWN/평가 불가로 유지한다. 기존25%와 V4.5의 사후98.75% 지표는 불변이다.
- **선별65개 테스트 통과**(실제HTTP/UDP 금지), 전체 회귀·백테스트 없음. 실제 임시DB·WAL·OS lock 및 mock 시계/네트워크를 구분해 검증했다. 기록 스크립트UTF-8 읽기 오류 후 측정 즉시 저장으로 수정하고 별도 한도를 고정해 재측정했다. NTP 총상한19패킷, 거래소 진단2회다.
- 기존163신호·86보호 입력·STALE_OPEN115·이전 증거83파일 hash 보존. 탐지/label/threshold/점수·collector·300초 가격 정책·연구 원본 불변, 주문·키·CHIO BOT 통합·자동 재시작·Windows 종료 없음. [시계 증거](../reports/scanner_v46_20261025/clock_recheck.json), [보존 검증](../reports/scanner_v46_20261025/completion_checks.json). 다음은 사용자 시계 환경 복구 후 두 제공자 재검증 및 새 episode의 감독하 제한 관측이다.

## 2026-10-25 V4.5 NO_TRADE·장시간 운영 준비 검증

- [V4.5 보고서](scanner_v45_observation_readiness_20261025.md), 관측 인프라 **PARTIAL**, 현재 호스트의 LIVE 시작 **CLOCK_SYNC_UNVERIFIED로 BLOCKED**. W32Time 서비스 조회가0x80070426으로 실패해 독립 시계 정확도는 미검증이다. 시계/서비스를 변경하거나 장시간 LIVE를 시작하지 않았다.
- 기존 V4.4 **4/16=25% 원천30봉 완성도는 그대로**다. 독립 체결 근거를 재검증한 사후 가격 전용 평가는 **474/480slot=98.75%**(실제380+파생94), 고유276/280, 가격 격자13/16이다. 이 값은 원천 봉·range·탐지 완성도가 아니다. 가격 신선도 상한300초(원천 분봉 시작 기준)를 넘는6slot은 제외했다.
- 나중에 확보한 NO_TRADE 증거는 당시 feature로 쓸 수 없다. 당시 지식 기준 가격 평가380/480은 보존했다. 원천 candle·거래량·거래대금·threshold·label·5분 간격·cluster·점수 없음 정책은 불변이다. 기존 수집92/92 성공, NO_TRADE100/480slot·60/280고유분도 유지한다.
- 기존 V4.3 wrapper에 별도 가격 endpoint 테이블과 시계 admission/600초 재검증, 단조 실행 제한·벽시계 drift 차단·재시작 미래 시각 차단, 실패 HTTP 간격 및 큰 로그 행 제한을 보강했다. 기존 core/collector/V4.2/V15·동결 연구 정의는 변경하지 않았다. 실시간 NO_TRADE 증거 자동 수집은 SKIP이며 근거 없는 원천 부재는 계속 평가 불가다.
- 실제 새 신호0, 실제 후속 평가율 N/A. 동일16진단격자 후속30/60분은 전체 경로·부가 endpoint 모두0/16이다. 종료 이후 자료를 수집했다고 간주하지 않는다. 자연60분 완료·실제24시간 자원/장애·재부팅은 미검증이다.
- **영향 범위 선별70개 테스트 통과**. 실제 임시 DB close/reopen·별도 child 비정상 종료 WAL/PENDING 복구·OS lock, mock 네트워크/시계/자원 장애·watchdog를 구분해 기록했다. 전체 회귀·백테스트·거래소 API 추가 호출은0이다.
- 기존163신호·86보호 입력·STALE_OPEN115 장부·구형 DB 및 기존 V4.2/V4.3/V4.4 파일 hash 보존을 확인했다. 원본 DB는 immutable 읽기, 부가 증거는 메모리 복사/임시 DB에서만 적용했다. 주문·키·CHIO BOT 통합·자동 재시작·Windows 종료 없음. [비교 증거](../reports/scanner_v45_20261025/comparison.json), [보존 검증](../reports/scanner_v45_20261025/completion_checks.json).

## 2026-10-25 V4.4 분봉 결측 원인 검증

- [V4.4 보고서](scanner_v44_gap_validation_20261025.md), 최종 **PARTIAL**. V4.3의 LOOKBACK_30M 완전 격자는 저장값과 core로 재구성해 **4/16(25%) 그대로**다. 후속30분 성과의 완결률이 아니며, 기준·분모 완화나 가상 봉 생성은 없다.
- 고유 결측60분(중복 포함100slot/12격자)은 별도 체결 endpoint와 주변150개 분봉의 거래대금·고저가 대조로 **NO_TRADE** 근거를 확보했다. 업비트27분/44slot, 빗썸33분/56slot. API_MISSING·COLLECTION_FAILURE·LATE_CANDLE·ALIGNMENT_ERROR·UNKNOWN은 이 과거 범위에서0. 단순 candle API 부재만으로 무거래를 단정하지 않는다.
- 10/25 00:13:21~00:13:28 KST, 사전36회/120초/재시도0 한도에서 실제24회 모두200(분봉18·체결6). 원천47개5/15분봉이 실제1분 합계와 일치했고 업비트 FLOCK의5분1구간은 체결·캔들 모두 부재였다. 원시 응답 약1.84MiB는 Git 제외 보존.
- 실제 수집·평가 오류는 발견되지 않아 기존 V4.1 core/collector/V4.2/V4.3·V15를 수정하지 않았다. 별도 read-only `scanner_gap_audit_v44.py`를 추가했다. 빗썸 체결 ID 재사용은 행 중복도를 보존하고 합계로 검증하며, 충돌이 있는 다중 페이지는 부재 증거로 거부한다. 기존 분봉 수집은 체결 ID를 사용하지 않는다.
- 기존92/92 호출 성공률 유지. HTTP Date는 로컬 수신보다1.194~2.122초 앞섰으나 독립 시계 교정 증거는 아니므로 운영 시계 확인은 미검증으로 남겼다. 역사적 봉·체결 UTC/KST 정렬 오류는0이다.
- 실제 신호0, 후속30/60분 완료0. V4.3 종료 당시 진단16격자의 두 horizon 모두 EVALUATION_PENDING. 고정 검증 스냅샷10/25 00:21:35에는30분8개 미수집·8개 대기,60분16개 대기였다. 시간이 지났어도 종료 이후 가격을 수집했다고 간주하지 않는다.
- **선별29개 테스트 통과**, 전체 회귀·백테스트·LIVE scanner 실행 없음. 기존163신호·86보호 입력·STALE_OPEN115 장부·V4.2/V4.3 원시 파일 hash 유지. 원본/feature/label/가상거래 수정·주문·키·다른 작업 종료·Windows 종료 없음. [증거](../reports/scanner_v44_20261025/final_summary.json).
- 24시간 명령/STOP/resume 절차는 기존 안내에 준비돼 있으나 장기 장애·시계 기준·재부팅·실제 하루 자원 사용은 미검증이다. 이번 진단으로 무인24시간 운영이나 급등 예측 성능을 승인하지 않는다.

## 2026-10-24 V4.3 관측 이어받기·안정화 검증

- [V4.3 보고서](scanner_v43_stability_validation_20261024.md), 관측 인프라 **PARTIAL**, 탐지 성능 **INSUFFICIENT_DATA**. 24시간 명령은 [운영 안내](scanner_v43_operations.md)에 준비했으나 이번에는 실행하지 않았으며 무인24시간 안전성을 입증한 상태가 아니다. 현재 관측 프로세스는 종료됐다.
- V4.2 불완전15/24격자는 성공적으로 조회한 범위의 원천 분봉 부재였다. FLOCK·SAND 양 거래소 제한 재조회에서 기존 누락 봉 새 반환0. BTC 네이티브5/15분 거래대금과 기존 저장1분 합계12구간 모두 허용오차 내 일치. 진단8회, 오류0. 무체결/원천 부재를 보간하거나 NULL 정책을 바꾸지 않았다.
- 별도 V4.3 wrapper에 수동 새 run 예산·동일 dataset resume, durable HTTP 장부, 로그 순환, round 예약, transient next-poll recovery/circuit, CPU·메모리·디스크 guard, receipt 기반 가격 proxy·coverage를 추가했다. 원래 V4.1 core/collector/V4.2·V15 및 점수 없음·threshold·cluster·label·관측 주기·고정5종목 cohort는 불변이다.
- 실제 첫 실행 **23:49:30.183~23:50:34.200 KST**, STOP 종료. 같은 DB resume **23:50:58.124~23:56:07.854**, ROUND_TIME_RESERVE 종료. 합계373.748초, 재시작 공백23.924초 제외. 총9round·LIVE HTTP92회+진단8회=100회. 기존 append-only 모든 행·state 진도 보존, 실제 duplicate lock 거부 확인.
- 업비트/빗썸 각5시장, 새 신호0. 저장2,814봉 중warmup2,771·signal_start 이후43봉. 신규30분 완전4/16(25.0%), 나머지12개 SOURCE_ABSENT·NOT_COLLECTED0. 기존9/24(37.5%)와 시간·표본이 달라 개선 효과로 주장하지 않는다. 자연60분 사건/신호 성과는 미검증, synthetic PENDING→resume→COMPLETE만 확인했다.
- 양 DB/HTTP 장부 quick_check=ok, API 오류·미완료 job·시각 오류·중복 신호0. 두 worker 모두 정상 reap, forced kill0·close_errors={}. RSS max35.094MiB, CPU max8.428%/한 코어, episode 약0.846MiB. 실제 장기 장애·재부팅·24시간 자원 사용은 미검증이다.
- **선별61개 테스트 통과**, 전체 회귀·장기 백테스트·최적화 없음. 원본163신호·86보호 입력·V4.2 원시 파일 hash 유지. raw DB/로그/진단 응답/backup은 Git 제외, 작은 증거는 `reports/scanner_v43_20261024/`. 주문·키·가상체결·다른 작업 중단·Windows 종료 없음.

## 2026-10-24 V4.2 제한 LIVE 관측 완료

- [V4.2 실제 관측 보고서](scanner_v42_live_review_20261024.md), 판정 **INSUFFICIENT_DATA**. `4426c56`의 V4.1 탐지·점수 정책(점수 없음)·4% threshold·label은 변경하지 않았다. 새 공개 시세 wrapper에서 업비트·빗썸 별도 DB로 같은 V4 정책을 실행했다. 구형 V15 점수 전략 검증은 아니다.
- 최초 ICX 포함 scope는 업비트 지원 목록 누락으로1회 조회 후 BLOCKED, 캔들0. 원본 universe를 수정하지 않고 새 cohort를 BTC·ENA·ETH·FLOCK·SAND로 고정했다. 각5시장, BTC 제외 신호 대상 총8거래소-종목쌍이다.
- 실제 정상 지원 episode는 **2026-10-24 23:21:06~23:36:06 KST**, worker899.668초·완료15round·HTTP168회. 최초 지원 확인1회를 합친 task HTTP169회로220회 한도 안이다. 신규 신호 **0개**, 신규 signal_start는23:25이며 그 전 봉은 warmup으로 분리했다. 원본163개 신호와 성과를 혼합하지 않았다.
- 총 저장2,853봉 중 signal_start 이후98봉. 신규 range 관측24개 중 유효9개(37.5%), 유효 범위 max 업비트2.0161%/빗썸2.4194%. 양쪽 FLOCK·SAND는3개 격자 모두 최근30분 결측으로 NULL이다. 조기/추격/누락률 및5/15/30/60분 후속 성과는 N/A,60분 완전 사건 기준점0개다.
- 양 DB quick_check=ok, 중복·시각 정렬·미래 봉 오류0. 실제 disk close/reopen·bootstrap backup 일치, 실제 두 번째 supervisor lock 거부 확인. 시간 한도가 마지막 빗썸 round 도중 도달해 FLOCK TIME_LIMIT·미완료 job1개를 보존하고 종료했다. 최상위 오류 요약의 stale cache를 shutdown 재조회로 작은 수정, 원시 LIVE 로그/summary는 그대로 보존했다.
- 종료 후 worker와 supervisor 모두 종료·reap 확인. RSS max35.36MiB, runtime 약0.99MiB. 장기 무인 운영은 승인하지 않았다. [안전 종료/재시작 안내](scanner_v42_operations.md). raw DB·LIVE 로그는 `data/scanner_v42_live/`에 Git 제외 보존, 작은 증거는 `reports/scanner_v42_20261024/`.
- **선별58개 테스트 통과**, 전체 회귀·과거 재평가·최적화 없음. 원본 신호163개·보호 입력86개 hash 유지, 원본 V4/구형 DB 사전 일관 backup 확보. 주문·가상자금 체결·API 키·다른 작업 중단·Windows 종료 없음.

## 2026-10-24 V4.1 핵심 복구·재검증

- 구현4.1, frozen POLICY v4 유지. [V4.1 복구 보고서](scanner_v41_repair_validation_20261024.md). 운영 기반 판정 **PARTIAL**, 수익성·급등 조기 탐지 승인 아님. 장시간 LIVE 미실행, 현재 원본 세션 STOPPED 유지.
- V4에 입력 UTC/KST·1/5/15분 마감·원천 KRW 거래대금·오류본문 검증, malformed/봉 충돌의 fail-closed 중단, 신호별 실제 detected_at, read-only health·종료 사유 로그를 추가했다. 직전120초를 수집 재확인해 실제 늦은 봉을 기록하되 과거 신호/feature/state를 되감지 않는다.
- 보관 V15는 이전 가격으로 분 마감 후 새 가격 반영, 오래된 체결 제외, preload 확정 UTC 봉·원천 거래대금·최신 연속 구간 사용으로 작은 수정. 외부 `C:\dev\coin_API` 원본은 수정하지 않았으며 구형 전체 운영은 여전히 미검증이다.
- 별도 원본 보존 장부에서10/24 00:00 KST 기준 CLOSED190 / **STALE_OPEN115**. 종료 연속 관측 부족으로 검증 청산0, 신규 pnl0. 원본 OPEN·exit/pnl 보존. 기존 종료 DIP99 평균 **-0.423361%**, REBOUND66 **-0.340038%** 유지. 구형 수정 신호 자체의 성과는 NOT_REPRODUCIBLE.
- 371,708봉 검증·메모리 재생에서163신호의 ID/시각/cluster/feature(기존 수치 허용오차)/326outcome 및5/15/30/60분 경로 일치. 기존 LIVE L1 **0/24**, L2 **0/20**, 60분 평균 **-0.262473%** 유지. 독립 OOS 아님.
- BTC 제한 API는총9회(정상6, 최초 빗썸 요청 서식 오류3), 추가 재시도 없음. 수정된 KST 서식 후 양 거래소1/5/15분 검증 성공. 거래대금32개 교차 합산 모두 `max(1원, 원천×1e-8)` 이내 일치. 실제 WS/장기 장애 회복은 미검증.
- **선별41개 테스트 통과**, 전체 회귀 미실행. 격리 복사본에서 기존12테이블 모든 값 보존·새 운영2테이블 추가 확인. 보호 입력86개 hash 전후 동일. 증거는 `reports/scanner_v41_validation_20261024/`, 원본 DB에는 migration/수집/신호 재작성을 실행하지 않았다.

## 2026-10-24 급등 Scanner 종합 진단

- 최종 실전 활용 판정 **NOT_READY**, 기술 구성은 부분 작동. 별도 [종합 보고서](scanner_comprehensive_audit_20261024.md)에 버전·실행·가상거래·가격 경로·포착 평가·결점·개선 우선순위를 기록했다. production 코드, 연구 정의, 원본 DB·기존 결과는 변경하지 않았다.
- V4 마지막 정상 cycle은 **10/7 19:27:12 KST**, session 종료 19:27:59 STOPPED. 현재 급등 Scanner 프로세스 없음. 371,708봉 / LIVE32 / CATCHUP131. 재검산 feature·cluster·완료 outcome 불일치 0, quick_check=ok. LIVE L1 **0/24**, L2 **0/20**, UNKNOWN8/12. 60분 완전20건 평균 가격 변화 **-0.2625%**, 실제 detected_at 후 첫 분 종가 기준 proxy는 -0.6080%. 비용 미반영, 실현 수익 아님.
- `C:\dev\coin_API\crypto_scanner.db`에서 구형 원본 신호1,761 / 가상거래305건을 추가 발견했다. 종료 DIP99 평균 -0.4234%, REBOUND66 평균 -0.3400%. 점수60~64·TP3/SL1.5·신호 후45분 DIP 재계산은37건 평균 +0.3744%이나 최신12건 -0.0650%; V7의 사후 조건 선별 이력 때문에 독립 OOS 아님. OPEN115 중104개가 마지막 관측 시각 기준 기한 경과. 구형 분봉 마감 순서·preload 거래대금 결점과 가격 시각 증빙 한계가 있다.
- discovery522 / validation455 cluster와 label을 원본 봉으로 재구성해 기존 수치 일치. 연구용 V16 proxy929건도 기존 event/summary와 정확히 일치. 기존 validation PARTIAL 및 OOS 한계 유지. 원본76개 입력과 구형5개 파일 전후 hash 동일, 두 연구 DB·policy·manifest의 이전 custody hash도 일치.
- 별도 EXPLORATORY +5%/+10%/60분 사건은72/15개. 명목 정책 목표 전 포착41/72,11/15와 실제 LIVE 기록3/72,1/15를 구분했다. 전 시장 연속 관측이 아니며5분 기준점111,400개 중 평가가능15,427개(13.85%)뿐이라 전체 누락률·진짜 상승 onset 조기탐지율은 확정하지 않는다.
- BTC 한정 양 거래소 ticker·1/5/15분봉 **총8회** 제한 REST 확인은 모두200. 새 Scanner/장기 수집/WS/주문 미실행. CHIO BOT은 별도 빗썸 시세 UI 경로이며 구형/V4 급등 신호 조회 연결 없음. 다른 실행 중 연구 작업 보존.
- 관련 **선별34개 테스트 통과**, 전체 회귀 미실행. 진단 코드·JSON은 `reports/scanner_audit_20261024/`에 분리했다. 실시간 자연 신호·장기 안정성·구형 원시 체결·실제 포트폴리오 수익/MDD는 미검증이다.

## 2026-10-08 V4 WAL 정상화

- `data/forward_scanner_v4.db`의 메인 파일은 정상이었으나 이전 세대 WAL/SHM이 남아 정상 SQLite 연결이 실패했다. WAL 유효 prefix의 마지막 commit은 6,274 page, 현재 메인 DB는 8,622 page여서 sidecar와 메인 파일의 세대가 일치하지 않았다.
- 원본 세 파일을 먼저 백업한 뒤 sidecar를 격리했다. 복구 전후 전체 12개 테이블의 행 수와 모든 값 hash가 동일하다. candles 371,708, signals/features 163, outcomes 326이며 signal/source/feature/outcome 값 변경은 없다. 정상 read-only/writable 연결과 `quick_check=ok` 확인.
- 정상 종료 시 WAL TRUNCATE checkpoint, 강제 종료 후 commit WAL 복구, 시작 시 quick_check, stale sidecar 전용 오류와 백업 기반 `repair-wal` 명령을 추가했다. 전체 자동 테스트 **126개 통과**. API와 scanner cycle은 실행하지 않았다.
- 기존 재개 명령 유지: `python -m coin_analysis.forward_scanner_v4 --mode run --db data/forward_scanner_v4.db`.

최종 갱신: 2026-10-25. 현재 단계: **V4.7 외부 시각 정확도 복구PASS·Windows 루트 불확실성으로 LIVE BLOCKED, 인프라 PARTIAL /24시간 NOT_READY / 조기 탐지 실효성 INSUFFICIENT_DATA**. 무인24시간 운영·매매 전략으로 승인된 상태가 아니다. 신규 요청 없이 장기 실행·대량 수집하지 않는다. 아래 이전 smoke 기록은 해당 시점의 이력이다.

## 최신 LIVE 성과 점검 — 2026-10-05 22:43 KST

- ALL 103 / LIVE 12 / CATCHUP 91. LIVE만 L1 S/F/P/U=0/9/0/3, L2=0/7/0/5. valid 성공률 둘 다 0%이지만 표본 부족으로 실패 판정 불가. 성공 0이므로 세 관찰 후보 성공/실패 차이를 계산할 수 없다.
- LIVE 9시장, ENA/WLD/ICX 각2건. KST 00시1/22시5/23시6건. 마지막 LIVE는 10/2 23:35이며 정상 운영 노출 자체가 야간에 치우쳤다. 야간 시장 효과로 해석하지 않는다.
- 10/2 DNS 오류 cycle 약66분, 최신 공통 verified_until 10/3 23:08, 가장 앞선 시장 10/4 10:01. 마지막 cycle 종료 미기록. DB의 RUNNING만으로 현재 프로세스가 살아 있다고 판단하지 않는다. 며칠간 연속 live 관측이 충분히 누적된 상태가 아니다.
- UNKNOWN L1 25%, L2 41.67%. complete 표본 선택 편향 주의. 다음 중간 점검 valid100건/label 제안: 추가 valid L1 91/L2 93, 현재 완결률 유지 가정 추가 LIVE 약160건. 이는 정식 검정력/합격 기준이 아니며 성공20건과 시장 분산은 별도 필요.
- 상세 `reports/forward_scanner_v4_live_review_20261005.md/.json`. 코드/DB/frozen 정의 변경, API 호출, scanner 실행 없이 read-only memory snapshot 분석만 수행했다.

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
