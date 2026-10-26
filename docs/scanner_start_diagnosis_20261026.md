# SCANNER_CONTROL_FAILED 집중 조사·수정 — 2026-10-26

**실제 대시보드 API에서 동일 증상을 재현하고, 관리 상태 JSON의 일시적 읽기 실패를 수정했다. 수정 후 OBSERVING·저장·정상 종료 PASS.** NTP나 탐지 정책은 변경하지 않았다.

## 사용자의 직전 실행과 수동 Stop

대상 launch는 `640341845e17424f802aa924de48a22a`다. 원본 로그·상태·관측 자료는 수정하지 않았다. [시간순 조사 기록](../reports/scanner_start_diagnosis_20261026/prior_timeline.json).

| KST | 확인된 기록 |
|---|---|
| 13:41:15.001 | 관리 프로세스 시작·PRECHECK |
| 13:41:23.391 | 관리 NTP VERIFIED, 이어 감독 프로세스 생성 |
| 13:41:24.173~32.134 | 감독기 NTP VERIFIED, config/control DB 및 worker 생성 |
| 13:41:33.133 | worker 시작 |
| 13:41:33.142~40.996 | worker의 새 NTP 검사, 결과 VERIFIED |
| 13:41:37.621 /37.656 | CANCEL / STOP_REQUESTED 표식. 시작 후22.65초이며 worker NTP 검사 도중 |
| 13:41:41.004~41.076 | STOP_REQUESTED 정상 종료·worker returncode0·정상 reap·강제 종료 없음 |

사용자의 설명에 따라 이 Stop은 **수동 종료 사건으로 구분**한다. STOPPED/CANCELLED_BEFORE_COLLECTION만 보고 자동 종료 버그로 판정하지 않는다. HTTP0·거래소별 관측DB 미생성은 Stop이 최초 수집 전에 처리된 결과다. 75초 readiness timeout에 도달하지 않았고 worker 비정상 종료도 없다.

당시 웹은 시작 HTTP 응답 코드·제어 예외를 기록하지 않고, 예외를 메모리의 공통 문구로만 바꿨다. 따라서 **그 실행의 SCANNER_CONTROL_FAILED 내부 예외는 원본 기록만으로 확정할 수 없다.** 웹 로그의 오래된 ConnectionAbortedError도 시각/요청 연결 정보가 없어 이번 실패 원인으로 지정하지 않는다.

## 실제 API에서 확인한 실패 원인

새 진단을 추가한 뒤 `http://127.0.0.1:8765`의 실제 시작 API와 실시간 화면과 같은 snapshot 폴링을 실행했다. 시계·수집기·API를 mock하지 않았다. 분석 캐시 갱신은 실행하지 않았다.

1. **13:52:22.899 시작 응답202**, 관리 프로세스 생성, PRECHECK→STARTING. 세 단계 NTP 모두 VERIFIED.
2. **13:52:50.183**, 시작 확인기 `scanner_desktop_v50.start_scanner → scanner_control_v410.current → read_json → Path.open`에서 **PermissionError, errno13, winerror=None**. 시작 확인 경과27.23초로75초 timeout이 아니다.
3. 이 예외가 시작 확인 전체를 중단하고 기존 fail-safe 취소/STOP을 실행했다. 공통 예외 표시 때문에 대시보드에는 **SCANNER_CONTROL_FAILED**가 나타났다. 거래소 HTTP0·관측DB 미생성·worker 정상 종료였다.
4. 검증 도구의 명시적 Stop API는 **13:52:53.780**에 별도로 요청됐다. 앞선 시작 확인 예외·취소와 구별된다.

즉, **재현된 실패는 HTTP 시작 요청 거부나 거래소 오류, NTP 실패, worker crash가 아니라 관리 상태 파일을 읽는 시작 확인기의 오류**다. 갱신 중인 Windows 파일의 공유/교체 경합과 일치하는 일시적 접근 거부이며, OS·보안 프로그램 내부의 구체적인 공유 주체까지 식별한 것은 아니다. 이 재현 결과를 사용자의 과거 수동 Stop과 혼동하지 않는다. [실제 예외·회복 기록](../reports/scanner_start_diagnosis_20261026/root_cause_and_recovery.json), [구조화 로그](../reports/scanner_start_diagnosis_20261026/web.log).

## 최소 수정

| 파일 | 수정 |
|---|---|
| `coin_analysis/scanner_control_v410.py` | `read_json`에서 Windows 접근/공유 PermissionError만10ms 간격·재시도 예산0.5초로 다시 읽는다. errno13이고 winerror가 없는 실제 재현도 포함한다. 과거 상태 캐시를 돌려주지 않으며 지속 접근 오류·잘못된 JSON·128KiB 초과·다른 오류는 계속 차단한다. 회복 횟수/경과만 기록한다 |
| `coin_analysis/scanner_desktop_v50.py` | manager 생성·실제 phase 변화·시작 예외 위치·취소 출처·경과를 기록한다. 기존75초·프로세스 소유권·STOP 동작은 유지한다 |
| `coin_analysis/scanner_dashboard_v50.py` | 제어 요청/HTTP 수락·거부/시작 결과/Stop/예외를 시각·operation ID로 연결한다. 예외 종류·errno/winerror·프로젝트 코드 위치만 남기며 원시 예외 문자열·토큰·환경 값은 기록하지 않는다 |
| 같은 dashboard 모듈 | 연결 표시도 실제 DB로 재현해 수정했다. `http_attempts.status`는 `HTTP_END/HTTP_ERROR`이며 응답200은 `details_json.http_status`에 있다. 기존 문자열`200` 직접 비교는 정상 수집도 ERROR로 표시했다. 실제 장부 기준 CONNECTED/STALE/ERROR/UNKNOWN으로 표시한다 |
| 테스트 | 실제 Budget.event 장부 계약, 일시/영구 파일 접근 거부, 실제 Windows 공유 잠금, JSON/크기 제한, HTTP202와 백그라운드 실패 구분, 민감 문자열 제외, timeout와 Stop 사건 구분을 검증한다 |

이미지·메뉴·전략·임계값·주문 기능을 추가하지 않았다. NTP/전송/수집 엔진은 이전 검증의 SHA256과 동일하다. 재시도 예산은 사용자 공간에서 제한하며 OS 파일 I/O·스케줄링을 포함한 실제 완료 시간을 강제로 보장하는 것은 아니다. 실제 회복 경과는0.041/0.578/0.247초였다.

## 수정 후 검증

실행 전에 [한도와 보존 기준](../reports/scanner_start_diagnosis_20261026/baseline.json)을 고정했다. 실제 시작은 총2회(원인 재현1·수정 후1), 각120초/40 HTTP·기존5시장×2거래소, NTP총48요청 상한이다.

- [수정 후 실제 실행](../reports/scanner_start_diagnosis_20261026/start2.json): 시작202 → **OBSERVING** → 양쪽 **CONNECTED** → 두 거래소의 실제 committed candle 조회 → Stop202 → **STOPPED/SAVED**. 중복 시작409, 종료 후 웹200, snapshot 폴링8회·오류0. 준비에약37초가 걸렸고 수집 worker는21.02초만 실행했다.
- 같은 실행에서 metadata 읽기 충돌이 **3회 회복**됐다. 회복 후 새 상태를 읽어 정상 관측에 도달했으며 SCANNER_CONTROL_FAILED는 재발하지 않았다.
- 공개 HTTP **19회 모두200**(시장목록2·분봉17), UPBIT1485봉·BITHUMB1261봉·합계2746봉, 신규 신호0. 별도의 새 격리 관측 DB이며 기존 운영/연구DB를 변경하지 않았다. collection_errors/close_errors 없음, worker returncode0·정상 reap·forced_kill=False, WAL 정상 마감.
- 두 실행의 새 시계 gate6회 모두VERIFIED, NTP40/48요청. 시계 검증·정확도·표본·신선도·요청·시간·소유권 제한은 우회하거나 완화하지 않았다.
- [선별 테스트](../reports/scanner_start_diagnosis_20261026/test_result.json): **164개 중163통과·구형Python 미설치1skip·실패/오류0**. 실제 Windows 공유 거부·해제 후 read 회복도 통과했다. 전체 회귀·장기 부하 시험은 아니다.
- [보존·종료 검사](../reports/scanner_start_diagnosis_20261026/completion_checks.json): 기존DB **13개**의 SHA256·전 테이블 건수 동일, quick_check=ok. 원본 신호 **215→215**, 기존 분봉460997·상태51·후속 결과430 유지. 사용자의 실패 실행 원본과 기존 연구 결과·이전 보고서도 보존했다. 새 관측DB4개도 quick_check=ok. 기존 파일389개 중 문서2개·관리 pointer2개 외 변경/삭제 없음. 작업 소유 manager/감독기/worker/웹 listener 모두 종료했으며 다른 작업은 종료하지 않았다.

장기 반복 실행·절전/재부팅·외부 NTP 지속 장애·자연 신규 신호 후속 평가·브라우저 외관은 이번 범위가 아니다. 지속 파일 권한 장애는 계속 시작 실패로 남으며, OS/보안 프로그램의 공유 주체까지 추적하려면 추가 증거가 필요하다. 24시간 무인 운영은 NOT_READY다. 기존 dirty 변경과 과거 보고서를 덮어쓰거나 Git 작업으로 정리하지 않았다.
