# CHIO COIN SCANNER V5.0 사용 안내

독립 관측 전용 웹 대시보드. Python 3.11 이상과 표준 라이브러리만 사용하며 CHIO BOT과 연결하지 않는다.

## 실행·상태·종료

프로젝트 루트 `C:\dev\coin_api-1`의 BAT를 더블클릭한다. CMD와 PowerShell에서도 동일하다.

```powershell
cd C:\dev\coin_api-1
.\start_coin_api.bat
.\status_coin_api.bat
.\stop_coin_api.bat
```

시작 BAT는 별도 관측 저장소와 기존 관측 엔진을 사용한다. 전체 Windows/NTP 검증을 통과해야 Scanner를 실행한다.
브라우저가 자동으로 열리지 않으면 **http://127.0.0.1:8765** 를 직접 연다.
시계 검증에 실패해도 웹은 열리며 Scanner **BLOCKED**와 원인을 표시한다. BAT 오류창은 입력을 기다린다.

**웹 RUNNING은 Scanner LIVE 실행을 뜻하지 않는다.** LIVE 카드의 OBSERVING·실제 수집 중을 확인한다.
PRECHECK/STARTING은 수집 준비 상태다. 신호 0건도 정상적인 관측 결과일 수 있다.
시작 후 BAT 창과 브라우저를 닫아도 백그라운드 관측은 계속된다. 반드시 종료 BAT로 끝낸다.
종료 BAT는 이 프로젝트에서 소유한 Scanner의 기존 STOP 이벤트와 웹의 별도 STOP 이벤트만 사용한다.
종료가 확인되지 않으면 BLOCKED를 출력하며 다른 Python/CHIO BOT을 종료하거나 강제 종료하지 않는다.

기본 관측은 수동 종료까지 계속하되 기존 **86400초 / 16000 HTTP** 상한과 모든 fail-safe를 유지한다.
상한·네트워크·시계·자원 조건으로 더 일찍 끝날 수 있다. 자동 재시작은 없다.
**감독하에 사용해야 하며 24시간 무인 운영은 NOT_READY다.**

저장 신호만 볼 때는 LIVE를 시작하지 않는 다음 명령을 사용한다.

```powershell
.\start_coin_api.bat --dashboard-only
# 제한된 감독 관측: 기존 전체 안전 검증을 통과할 때만 수집
.\start_coin_api.bat --seconds 120 --max-requests 80
```

`--dashboard-only`는 시계 검증을 통과한 것으로 처리하지 않는다. 기존 기록의 시계 상태를 그대로 표시한다.
`--check`는 오프라인 Python/import 확인만 수행하고 웹·NTP·LIVE를 시작하지 않는다.
자동 검증용 `--no-browser`는 브라우저 열기만 생략한다. `COIN_API_NO_PAUSE=1`은 BAT 표시 대기만 생략한다.
Python 탐색 순서와 `COIN_API_PYTHON` 지정 방법은 [V4.10 안내](scanner_v410_windows_launcher.md)를 따른다.
API 키나 `.env`, 추가 패키지는 이 관측 진입점에 필요하지 않다.

## 화면의 숫자와 결측

- 감시 종목: 현재 관리 중인 Scanner가 OBSERVING일 때 DB의 실제 범위를 표시한다. 비활성은 0, 근거를 읽지 못하면 UNKNOWN이다. BTC 기준 종목과 거래소·종목 쌍을 구별한다.
- 오늘 신호: KST 탐지일, `source=LIVE`, 별도 관측 DB 기준이다. 원본 연구 163개를 오늘의 신규 신호에 합산하지 않는다.
- 연결: 현재 관측의 마지막 HTTP 장부 결과와 신선도(150초)를 표시한다. 독립 접속 검사를 보내지 않는다. STOPPED/BLOCKED일 때 과거 HTTP 200을 CONNECTED로 표시하지 않는다.
- 시계: 기존 관리 preflight 및 worker CLOCK_CHECK의 상태·나이를 표시한다. 오래된 PASS는 UNKNOWN이다. 웹 조회가 NTP를 추가 호출하거나 차단을 해제하지 않는다.
- 목록: 원본 연구 보관 / 이번 관측 기록 / 이전 관측을 구별한다. 원천 LIVE/CATCHUP도 별도로 표시한다. 최신 200건을 구분별 조회하며 원본 163개는 연구 보관 필터로 조회할 수 있다. 관측 저장소는 최근 32개 범위다.
- 점수: 기존 V4 엔진은 점수를 정의하지 않아 UNKNOWN이 정상이다. 변동폭을 점수로 바꾸지 않는다.
- 후속 지표: 관측 DB에 저장된 `live_horizons`를 우선 사용하며 PENDING을 재계산해 완료로 바꾸지 않는다. 원본 연구 DB는 5/15/30/60분 지표 테이블이 없으므로 **연속된 실제 저장 분봉 전체가 있을 때만** 종가 변화·고가 MFE·저가 MAE를 화면에서 계산한다. 미래 마감 봉·부분 구간·보간·마지막 가격 채우기는 사용하지 않는다. 원래 L1/L2 연구 평가를 상세 하단에 별도로 유지한다.
- MFE/MAE: 완료된 가장 긴 후속 구간과 그 분 수를 함께 표시한다. 탐지 표시 가격의 근거와 후속 지표 기준 `signal_price`를 구별한다. 체결 수익률이 아니다.
- 차트: 실제 저장 1분봉 종가, 신호 −30분~+60분, 봉 마감 시각 기준이다. 결측 구간은 선을 끊는다. 자료 부족은 PENDING/NO_DATA/UNKNOWN이다.

화면은 5초마다 갱신하며 숨겨진 탭의 폴링은 멈춘다. 선택한 신호는 같은 탭의 새로고침 후 복구한다.
서버 연결이 끊어지면 상태 카드를 UNKNOWN으로 바꾸고 마지막 조회 목록임을 알린다.
브라우저에서 주문·시작/종료·설정 변경을 실행하는 API는 없다.

## 저장·접속 문제

원본 `data/forward_scanner_v4.db`는 immutable 읽기 전용이며 비어 있지 않은 WAL이 있으면 보관 조회를 차단한다.
새 관측 DB는 기존 `data/scanner_v43_live/console_<ID>/`를 사용하고 WAL을 포함한 짧은 읽기 전용 트랜잭션으로 조회한다.
웹 관리 상태와 최대 1MiB×2 로그는 `data/scanner_dashboard_v50/`에 분리한다. 관리 폴더 8MiB/여유 디스크 256MiB 시작 조건, HTTP 동시 처리 8개를 제한한다.
기존 Scanner의 DB 저장·HTTP·로그·자원·1초 시계 기준은 그대로다.

포트 8765가 다른 프로그램에 사용 중이면 `WEB_PORT_OR_START_FAILURE`를 출력하고 새 Scanner 시작도 하지 않는다.
다른 프로그램을 강제 종료하지 않는다. 기존 사용 프로그램을 확인한 후 사용자가 정리하거나 종료한다.
시계 실패는 `status_coin_api.bat`에서 상세 원인을 확인하고 Windows 동기화/NTP 환경을 복구한 후 다시 시작한다.
서비스·방화벽·레지스트리·시각 설정은 BAT가 변경하지 않는다.

서버는 `127.0.0.1`에만 바인딩하고 Host/Origin 검사, 외부 리소스 차단, 읽기 전용 GET API를 사용한다.
외부 네트워크 공개, Windows 자동 시작 등록, 주문 기능은 없다.

실제 검증 결과와 한계는 [V5.0 검증 보고서](scanner_v50_dashboard_validation_20261026.md)에 기록했다.
