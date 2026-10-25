# Scanner V4.10 — Windows 런처 검증

기준: `11404d3561a6de24f262a5f29d0a027fee6b6bd2`. 검증일: 2026-10-25 KST.
판정: **런처 기능 검증 PASS / 관측 인프라 PARTIAL /24시간 무인 NOT_READY**.
최종 Scanner 상태는 **STOPPED / DB SAVED**다. Windows 종료·재부팅은 수행하지 않았다.

## 구현 범위

프로젝트 루트에 `start_coin_api.bat`, `stop_coin_api.bat`, `status_coin_api.bat`를 추가했다.
공통 Python 선택 helper와 절대 경로 entry를 통해 `scanner_control_v410.py`를 호출한다.
관리 계층은 기존 `forward_scanner_v43`의 supervisor/worker·STOP 파일·잠금·DB/시계/자원 guard를 재사용한다.
기존 엔진·V4.9 NTP 전송/판정·탐지 threshold·label·점수 없음·5분 격자·결측 정책은 변경0이다.

기본은 사용자가 종료할 때까지의 단일 감독 실행이며 기존 최대86400초/16000요청에서 끝난다.
한도 도달 후 새 예산을 자동 지급하거나 재시작하지 않는다. 이 기본값은 이번24시간 실행이나 무인 승인과 다르다.
새 dataset만 사용하며 과거DB 자동resume/통합·원본 덮어쓰기·주문·키 로딩·Windows 자동 실행 등록은 없다.

관리 preflight와 기존 supervisor/worker의 전체 시계 검사를 각각 거친다.
Windows 루트 거리≤1초·나이≤3600초, 두 제공자3표본씩·offset+불확실성≤1초·spread0.5초·
구간 중첩·표본 신선도15초와 기존V4.9 제한 재시도를 그대로 유지한다.
시계 실패를 BAT가PASS로 바꾸거나 과거PASS를 다음 시작에 재사용할 수 없다.

종료는 고유ID와경로를 검증한 현재 관리 dataset에만STOP 이벤트를 보낸다.
프로세스 확인에는 PID와Windows 생성시각을 함께 사용한다. 새 관리 계층에는kill/terminate/taskkill이 없다.
기존 supervisor의 자기worker watchdog은 변경하지 않았다.45초 내 정상 종료/저장을 확인하지 못하면BLOCKED이며
다른Python·CHIO BOT·소유권 불명 실행을 강제 종료하지 않는다.

## Python·경로·사용성

호스트 `py -3`가Python3.4.4를 선택함을 확인했고 이를 거부한 후 실제Python3.14.7을 선택했다.
명시적Python/venv가 잘못됐으면 원인을 안내하고 차단한다. 필요한 추가패키지·API 키·`.env`는 없다.
오류 창은 기본pause를 유지하며 잘못된Python 환경에서 실제 CMD가 키 입력 전까지 종료되지 않음을 검증했다.

공백·한글·`&()`·`!`가 포함된 임시 복사 프로젝트에서 CMD와PowerShell의 오프라인BAT 호출이 통과했다.
BAT/공통CMD는ASCII/CRLF·인용된자기경로·delayed expansion 비활성으로 작성했다.
실제API 검증은 원래 프로젝트에서만 수행했다. 복사 경로의 실제LIVE는SKIP이다.

Windows Shell의BAT 연결 방식으로 실행해 entry/NTP 차단까지 도달한 것을 확인했다.
물리 마우스로Explorer를 더블클릭하고 화면을 시각 검사한 것은 **미검증**이다.
이는 Shell 연결 검증과 구분한다. 정상 기동·콘솔 상태·종료는 실제PowerShell/CMD BAT 호출로 확인했다.

## 선별 검증

최종 **81개 PASS**, 실패/오류/skip0,8.568초다. 전체 회귀·대규모 백테스트는 수행하지 않았다.
테스트 프로세스의 실제HTTP/UDP를 금지했다. 자식BAT는 `--check` 또는잘못된Python으로 실행해API를 호출하지 않았다.

|항목|결과·증거 유형|
|---|---|
|CMD/PowerShell·한글/공백 경로|실제 자식BAT 오프라인 호출PASS|
|잘못된Python·3.4 거부·오류 창pause|실제 프로세스PASS|
|관리/기존observer 중복 잠금|실제Windows 파일 lock PASS|
|시계 실패 시 worker/DB 미생성|mock 및 실제 실패 시도PASS|
|PID 재사용·경로 변조 거부|mock 생성시각/임시경로PASS|
|종료 이벤트·최종 저장 확인|실제 임시DB/STOP 및 실제LIVE PASS|
|상태 수치·신호0/1·최근수신·DB크기|실제 임시DB 조회PASS|
|종목 수|DB의 실제 state를 집계, fixture9쌍/7신호쌍도정확히표시|
|데이터 미존재·오래된시계|UNKNOWN 및stalePASS표시PASS|
|원래 시계/공개endpoint/누수/PENDING/WAL/자원guard|영향 범위 선별 재사용PASS|

초기 시계 검사 중 경과시간0 고정과 종목 수의 상수 표시를 발견해 단조 시간 및 실제DB 집계로 보강했다.
이 표시 수정 후81개를 다시 통과했다. 실제관측 후 수행한 마지막 수정은 종목 수표시/fixture이며 기동·시계·종료 경로는 동일하다.
[테스트 코드 hash·목록](../reports/scanner_v410_20261025/test_result.json),
[최종 로그](../reports/scanner_v410_20261025/selective_tests.log).

## 실제 제한 검증

사전 한도는 최대2기동시도·실제LIVE합계240초/160요청·NTP72패킷, 각 실행120초/80요청이다.
실제 두 번의 기동 시도 중 첫 번째는 차단, 두 번째만 관측했다. 중복 기동 요청은 잠금에서 차단돼 새 실행/NTP를 만들지 않았다.

|시도|결과|
|---|---|
|23:30:36 KST경 Windows Shell BAT 기동|Windows 루트 거리0.1352706초PASS, NTP 논리 표본1개의 최초/재수신 모두timeout.8.720초 뒤BLOCKED|
|23:33:26.860~23:34:13.399 관리 실행|PowerShell BAT, 전체 시계PASS·공개API 정상·관측 후종료BAT 정상 반환0|
|실제worker|23:33:39.879~23:34:12.976 KST,33.096초·2round·29HTTP모두200·신호0|

첫 시도는 관측DB/supervisor/worker/API 생성0이다. 두 번째는 관리 preflight7시도·7.452초,
supervisor6시도·4.738초, worker7시도·7.416초로 모두 필수6개 유효 표본을 확보한 뒤 진행했다.
직접NTP총27패킷이며 한도 안이다. Windows의 간헐적timeout 자체를 해결한 것은 아니다.
V4.9 정책을 우회하지 않고 통과/차단 결과를 그대로 사용했다.
[차단 증거](../reports/scanner_v410_20261025/first_blocked_attempt.json),
[시계 전체](../reports/scanner_v410_20261025/clock_review.json).

실행 중 실제상태는 RUNNING/OBSERVING·양거래소·5종목/10쌍·신호0·최근수신시각·DB/WAL크기·
ClockPASS로 표시됐다. 중복start는 반환2이며 기존launch ID를 유지했다.
종료BAT는 STOP_REQUESTED로 worker/supervisor를 정상reap하고 close_errors={}·forced_kill=false를 확인했다.
두 DB quick_check=ok·빈WAL, 최종STOPPED/SAVED다. 종료된 상태에서PowerShell status/stop 재호출도 반환0이며 추가 신호/kill은 없다.
[실행 중 출력](../reports/scanner_v410_20261025/running_status_bat.json),
[중복 차단](../reports/scanner_v410_20261025/duplicate_start.json),
[종료 출력](../reports/scanner_v410_20261025/stop_bat.json),
[worker 결과](../reports/scanner_v410_20261025/worker_summary.json).

원천2608봉은 첫signal_start23:35 이전 warmup 범위다. 실제eligible5분 격자·자연 신호·30/60분 평가 표본은 없다.
이 짧은검증은 실행/저장 UI 검증이며 탐지 성능이나 데이터 완성도 개선으로 해석하지 않는다.
원천 부재의NO_TRADE 확정·가격300초 정책·기존25%/사후98.75% 결과는 그대로다.

## 보존·남은 범위

원본163신호·보호입력86개·STALE_OPEN115·이전증거169파일·이전V4.9 LIVE 원시26파일의 hash가 유지됐다.
원본DB immutable quick_check=ok, 새두DB ok, 미완료수집job/중복/시각정렬 오류0이다.
최종활성 Scanner0이며 새DB/로그는Git제외경로에 보존한다. Windows설정·서비스·시각·전원 변경0이다.
[최종 보존·상태](../reports/scanner_v410_20261025/completion_checks.json).

미검증: 물리마우스/화면배치, 한글복사경로LIVE, 기본상한24시간 실행, 실제창X강제닫기,
장기NTP/네트워크/디스크 장애·절전/재부팅·자연30/60분 평가다. 기본장기profile은 이번에 실행하지 않았다.
상태/종료는이런처의현재관리대상만 다룬다. 미래에 다른수동기동을 자동 채택하거나강제종료하지 않는다.
감독하런처 사용은 가능하지만 이 검증으로24시간 무인운영을 승인하지 않는다.

사용 명령과경로는 [간단 사용 안내](scanner_v410_windows_launcher.md)에 정리했다.
