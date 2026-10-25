# Coin Scanner V4.10 — Windows 실행·종료·상태

프로젝트: `C:\dev\coin_api-1`. 기존 관측 전용 V4.3 진입점과 V4.9 시계 검증을 사용한다.
새 탐지 엔진이나 주문 기능은 없다. **감독하 실행용이며24시간 무인 운영은 NOT_READY**다.

## 사용 방법

프로젝트 루트의 다음 파일을 더블클릭한다.

|파일|동작|
|---|---|
|`start_coin_api.bat`|새 관측 저장소로 시작하고 콘솔 상태를10초마다 표시|
|`stop_coin_api.bat`|이 BAT 관리 계층이 시작한 현재 관측에 STOP 요청 후 종료/저장 확인|
|`status_coin_api.bat`|현재 관리 대상의 실제 프로세스·DB·시계 기록 조회|

PowerShell에서는 다음과 같이 실행한다. CMD에서도 같은 파일 이름을 실행하면 된다.

```powershell
cd C:\dev\coin_api-1
.\start_coin_api.bat
# 다른 PowerShell/CMD 창에서
.\status_coin_api.bat
.\stop_coin_api.bat
```

BAT 자신의 위치가 프로젝트 기준이므로 다른 현재 디렉터리에서 절대 경로로 호출해도 된다.
공백·한글 경로를 지원한다. 시작 콘솔은 관측 중 열린 상태로 두고 **종료 BAT**를 사용한다.
Ctrl+C도 STOP 요청을 시도하지만 창의X/강제 닫기는 정상 저장을 보장하지 않는다.

기본은 사용자가 종료할 때까지 관측하되 기존 **최대86400초/16000HTTP**에서 끝나는 단일 실행이다.
API·시계·네트워크·CPU·메모리·디스크 guard나 round 여유 조건에 따라 더 일찍 멈출 수 있다.
한도를 늘려서 이어 달리거나 자동 재시작하지 않는다. 기본24시간 상한은 무인24시간 운영 승인이나
이번24시간 실행을 뜻하지 않는다. STOPPED/BLOCKED로 끝나면 원인을 확인한 뒤 사용자가 다시 시작한다.

짧은 감독 관측과 오프라인 환경 확인도 가능하다.

```powershell
.\start_coin_api.bat --check
.\start_coin_api.bat --seconds 120 --max-requests 80
```

`--check`는 Python/import/내장 구성 경로 확인만 한다. NTP·API·LIVE를 실행하지 않으며
시계가PASS라고 간주하지 않는다. 실제 시작은 별도의 전체 시계 검사를 요구한다.

## Python·설정

Python3.11 이상과 표준 라이브러리 `sqlite3`·`ssl`·`ctypes`를 확인한다. 이 관측 진입점에는
별도 패키지 설치·API 키·`.env`가 필요하지 않다. `requirements.txt`의선택WebSocket 패키지는
이 공개REST 관측 실행에 사용하지 않는다. 패키지/서비스를 자동 설치하거나 설정을 바꾸지 않는다.

선택 순서는 `COIN_API_PYTHON` 지정값, `.venv\Scripts\python.exe`, `venv\Scripts\python.exe`,
유효한 `py -3`, 유효한 `python`이다. 각 후보의 실제 버전을 검사한다. 명시적 지정이나
프로젝트venv가 잘못됐으면 조용히 다른 환경으로 바꾸지 않고 BLOCKED로 안내한다.

```powershell
# 자동 선택이 안 될 때만 실제 실행 파일을 지정한다.
$env:COIN_API_PYTHON = 'C:\경로에 공백\Python\python.exe'
.\start_coin_api.bat --check
```

BAT는 기본적으로 종료/오류 후 키 입력을 기다려 창이 즉시 사라지지 않게 한다.
자동화된 조회에서만 다음과 같이 대기를 끌 수 있다. LIVE 안전 검사에는 영향이 없다.

```powershell
$env:COIN_API_NO_PAUSE = '1'
.\status_coin_api.bat
```

## 화면 해석

- `Status`: RUNNING/STOPPED/BLOCKED. `Phase`의 PRECHECK·STARTING은 아직 실제 수집 전일 수 있다.
  OBSERVING은 기존 worker의 heartbeat가 확인된 상태다. 신호0은 정상일 수 있다.
- `Exchanges`, `Markets`: 실제 열린 새DB에서 확인한다. 현재고정대상은 두 거래소 각각
  BTC/ENA/ETH/FLOCK/SAND,5개 고유 종목/10거래소-종목쌍이며 신호 대상은BTC 제외8쌍이다.
- `Signals`, `Last signal`: 이번 관리 대상 DB의 신호 수와 실제 detected_at이다.
  원본163개나 이전 실행을 합산하지 않는다. 실제 신호가 없으면 최근 시각은UNKNOWN이다.
- `Collected`: 원천 확정봉과 연결된 receipt의 최신 저장 시각이다. 원천 부재를 가상 거래로 세지 않는다.
- `Clock`: 최근 전체 검증 결과와 경과 시간이다. 시작 시에는 관리 preflight, 이후에는worker 기록을 사용한다.
  과거PASS가 오래되면UNKNOWN으로 표시하며 status 명령 자체는NTP/API를 호출하지 않는다.
- `Started`·`Duration`: 이번 관리 실행 시작 시각(KST)과 단조 시간 경과다. 시계 검사/대기도 포함한다.
- `DB save`: 실행 중에는최종저장UNKNOWN이다. 종료 후 정상 summary·worker reap·강제 종료 없음·
  DB quick_check·빈WAL을 확인한 경우에만SAVED다. 예기치 않은 종료는 확인 전UNKNOWN/BLOCKED다.
- `DB bytes`: 이번 두 DB와WAL/SHM 크기 합계다. 데이터가 준비되지 않은 항목은UNKNOWN이다.
  `Recent error`는 수집/읽기/차단 오류, `Last result`는 정상STOP을 포함한 종료 사유다.

## 저장·종료 안전성

매번 `data/scanner_v43_live/console_<고유ID>/`의 새 DB를 사용한다. 기존 원본/연구/이전episode를
덮어쓰거나 자동으로 이어받지 않는다. 이전PENDING과 기록은 그대로 보존된다. 명시적동일DB resume은
기존 [V4.3 운영 절차](scanner_v43_operations.md)를 따르는 별도 작업이다.

관리 기록은 `data/scanner_console_v410/launches/<ID>/`에 저장한다. 시작 시계 증거·상태·launch.log를
남기고 새 로그는1MiB×2, 관리 폴더는32MiB에서 추가 실행/관측을 차단한다. 자동 삭제는 없다.
기존 worker의1MiB×4 로그·256MiB RSS/episode·CPU 표본 guard·가용 디스크256MiB 조건은 유지한다.
관리 폴더 한도에 도달하면 종료된 기록을 확인/백업한 뒤 사용자가 보관 위치를 정리한다.

중복은 관리 잠금과 기존 supervisor/observer 잠금으로 차단한다. PID와Windows 생성 시각을 함께
확인하며 PID만 보고 다른 프로세스를 조작하지 않는다. 종료는 소유한 새 runtime의STOP 이벤트뿐이다.
다른Python·CHIO BOT·수동으로 시작한 알 수 없는 실행을 검색해서 죽이지 않는다.
수동 Scanner가 기존 잠금을 보유하면 새 시작은BLOCKED이며 그 실행의 기존 종료 절차를 사용한다.

종료 BAT는최대45초 동안 정상 결과/DB 저장을 기다린다. 확인되지 않으면BLOCKED로 표시하고
강제 종료하지 않는다. 잠금·DB sidecar·프로세스를 임의로 삭제하지 말고 상태/로그를 확인한다.
기존 supervisor의 자기worker에 대한 시간 초과 watchdog은 그대로이며 새 BAT가 우회하지 않는다.

## 차단 시 조치

|표시|조치|
|---|---|
|잘못된Python|실행 파일/venv를 확인하고 `--check` 재실행|
|CLOCK 계열|W32Time·Windows 동기화·DNS/UDP123을 확인.1초 기준을 늘리지 말고 복구 후 새 시작|
|중복/Another scanner|현재 관리 상태 확인. 소유한 실행은종료BAT, 알 수 없는 실행은그 실행의 기존 절차 사용|
|저장/DB 오류|상태·summary·launch.log 보존. 원본/sidecar 삭제나강제복구를 자동 실행하지 않음|
|STOP 확인시간초과|다시status 조회. 강제 종료는제공하지 않음|

Windows 자동 시작 등록·시스템 시간 변경·종료·재부팅·실거래 주문은 수행하지 않는다.
실제 검증 범위와 미검증 항목은 [V4.10 검증 보고서](scanner_v410_launcher_validation_20261025.md)에 기록한다.
