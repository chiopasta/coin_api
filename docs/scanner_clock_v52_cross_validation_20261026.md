# V5.2 시계 교차 검증 수정 — 2026-10-26

## 결과

Windows 루트 분산 단독 차단에 대해 **새 직접 NTP 증거를 사용하는 조건부 교차 검증**을 추가했다. 루트 경고를 지우거나 1초 정확도 기준을 늘리지 않았다. 실제 현재 시계 검사 1회는 통과했고, 시작 API 검사에서는 Windows NTP 응답 누락으로 안전 차단됐다. 실제 수집 성공·장기 안정성은 미검증이며 거래소 HTTP는 0회다.

## 원인과 호출 경로

웹 시작 POST → `scanner_dashboard_v50.Operations` → `scanner_desktop_v50.start_scanner` → `_scanner` 자식 → `scanner_control_v410.start` → `scanner_clock_v45.verify_clock`이다. 이후 V4.3 supervisor와 worker도 같은 검증기를 호출한다. worker는 최초 요청 전, 600초마다, 긴 검사 공백·절전 복귀 때 재검증한다.

`verify_clock`은 `w32tm /query /status /verbose`와 별도 `scanner_ntp_v49` 프로세스를 실행한다. V4.7 파서는 Windows 상태를 해석하며, V4.9 전송은 V4.6의 NTP 패킷 계산·정확도 판정을 재사용한다.

보존된 실제 실패 기록은 동기화 오류0·윤초0·계층2·최근 Google 원본 동기화 상태였지만 다음 조건에서 차단됐다.

```
루트 분산 = 7.7619620초
루트 지연 = 0.0390476초
루트 거리 = 분산 + 지연/2 = 7.7814858초 > 1초
```

기존 코드는 직접 NTP가 정상이어도 이 Windows 루트 조건을 별도 필수 조건으로 적용했다. 이는 계산 버그보다 **품질 추정치와 직접 측정 증거를 함께 해석하는 정책의 문제**다. 루트 거리는 실제 로컬 위상 오차와 같은 값이 아니다. 정의와 처리 단위는 [RFC5905](https://www.rfc-editor.org/rfc/rfc5905.html), Windows의 시간 선택·보정 동작은 [Microsoft 설명](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/how-the-windows-time-service-works)을 확인했다.

같은 기록을 당시 검사 시각으로 재현하면 Windows 루트 조건은 계속 실패하지만, 당시 직접 두 제공자의 최대 `abs(offset)+uncertainty`는 **0.087094534초**이며 신선도·일치 조건을 만족한다. 이것은 역사적 재현이고 과거 표본을 현재 시작 승인에 사용하지 않는다. [재현 결과](../reports/scanner_clock_v52_20261026/recorded_failure_replay.json).

Windows 초기 필터의 품질 추정치가 수렴 중이라는 해석은 이전 관측과 일치하지만, Windows 내부 상태를 조사한 것은 아니므로 확정 원인으로 단정하지 않는다. 현재 실측에서는 루트 거리가 **0.34033845초**로 내려갔고 원본은 `time.google.com,0x8`이었다. 사용자 제공 시각·원본과 조회 시점이 다르며 이 작업은 Windows 원본·서비스·시각을 변경하지 않았다.

## 단위·불확실성·캐시 점검

- Windows 출력은 명시적 `s` 단위만 초로 읽는다. 초/밀리초 혼동이나 UTC/KST 변환 오류는 확인되지 않았다. `7.767s`를 `7.767ms`로 바꾸지 않는다.
- NTP 루트 지연은 signed 16.16, 루트 분산은 unsigned 16.16을 `/65536`으로 초로 변환한다. 타임스탬프 소수부는 `/2**32`다. '분산'은 이 계산에서 통계적 분산의 제곱근을 취할 값이 아니라 시간 오차 항이다.
- 직접 측정의 불확실성은 네트워크 지연/2 + 서버 루트 지연/2 + 서버 광고 분산 + 정밀도 + 로컬 wall/monotonic 차이 + 기존 반올림 여유다. 서버 광고 분산과 정밀도를 제거하지 않았다.
- 실제 검증 함수는 호출마다 Windows와 NTP를 새로 조회한다. 이전 PASS나 실패 기록은 admission 캐시로 사용하지 않는다. 대시보드는 최근 관리 기록을 표시하므로, Windows를 동기화해도 과거 실패 문구가 남을 수 있었다. 화면 문구를 '마지막 검사/최근 결과'로 명확히 하고 다음 시작에서 새로 검증한다. GET 조회가 NTP를 보내거나 차단을 자동 해제하지 않는다.

## 개선한 안전 조건

Windows 파서는 높은 루트 거리를 계속 `CLOCK_WINDOWS_ROOT_UNCERTAINTY`로 기록한다. 이 경고만 있는 경우 다음을 **모두** 만족해야 별도 측정 근거로 전체 검증을 통과한다.

1. Windows 서비스 조회 성공, 윤초0·계층1~15·마지막 동기화 오류0·네트워크 시간 원본·동기화 나이3600초 이내. 오래된 동기화 검사를 루트 경고보다 먼저 수행해 가려지지 않게 했다. Local CMOS·로컬 원본은 허용하지 않는다.
2. Windows 지연 자체가 한도를 넘는 경우는 제외한다. 높은 분산만 직접 교차 검증 대상으로 삼는다.
3. 기존 Windows·Cloudflare 두 제공자 각각3개, 총6개 새 유효 NTP 표본. 두 제공자의 실제 응답 IP 집합도 서로 겹치지 않아야 한다.
4. **각 표본**의 `abs(offset)+uncertainty <= 1초`, 전체 offset spread<=0.5초, 모든 오차 구간의 중첩, 15초 이내 신선도. 평균이나 일부 좋은 표본으로 대체하지 않는다.
5. 전체 검사15초, Windows 동기화 나이, wall/monotonic 점프 검사를 유지한다. 초기·주기·복귀 재검증과 기존 STOP·자원 한도도 유지한다.

통과해도 원래 Windows 수치와 루트 경고를 남기고 '직접 NTP 교차 검증 통과·Windows 루트 품질 경고 유지'를 표시한다. 필수 응답 누락·실제 오차·과도한 불확실성·불일치·통신 장애·동기화 실패는 계속 차단한다. 이 방식은 기존 비인증 NTP의 공학적 검사이며 암호학적 시간 인증을 추가한 것은 아니다.

## 테스트와 실제 검사

- [회귀 결과](../reports/scanner_clock_v52_20261026/test_result.json): **151개 중150통과·1skip**, 실패/오류0. skip은 구형 Python 미설치다. 정상/높은 루트·동기화 실패·오래된 Windows/NTP·오차 및 불확실성 경계·제공자 불일치·동일 IP·패킷 단위·재시작 캐시·기존 STOP/DB/시작 API 테스트를 포함한다.
- 실제 읽기 전용 시계 검사: **VERIFIED**, NTP7시도·6유효·1timeout. 오차 약21~31ms, 최대 오차+불확실성 약0.105초. [원문](../reports/scanner_clock_v52_20261026/actual_clock_check.json).
- 실제 시작 API는 격리된 loopback 포트에서202를 받았고 PRECHECK 중 STOP을202로 요청했다. Windows NTP의 한 필수 표본이 재시도 후에도 없어서 `CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE`로 차단됐다. NTP7시도·5유효·2timeout. worker·관측DB·거래소HTTP는0이고 manager 종료를 확인했다. 이 경우 제어 결과의 FAILED는 시계 검증 실패를 뜻하며 프로세스 잔존을 뜻하지 않는다. 실패를 PASS로 바꾸지 않았고 실제 정상 수집 시작은 미검증이다. [실제 API 결과](../reports/scanner_clock_v52_20261026/api_validation_result.json).
- 실제 NTP 총14시도로 사전 상한24 이내다. 정상값이 나올 때까지 반복하지 않았다. 새 장시간 수집·주문은 실행하지 않았다.
- 대시보드 API의 실제 차단 코드·구체 원인 메시지를 확인했고 JS 렌더 함수로 과거 실패 문구·교차 검증 PASS 경고·오류 해제를 검사했다. JS 구문 정상. [렌더 검사](../reports/scanner_clock_v52_20261026/ui_renderer_check.json). 실제 브라우저 시각 QA는 이번 검사에 포함하지 않았다.

## 변경 파일과 보존

|파일|변경|
|---|---|
|`coin_analysis/scanner_clock_v47.py`|Windows 건강 상태 분리, 오래된 동기화 우선 차단, 직접 측정 교차 검증|
|`coin_analysis/scanner_clock_v45.py`|새 검사 정책 연결·근거와 경고 보존|
|`coin_analysis/scanner_control_v410.py`|PASS의 교차 검증 근거·경고 표시|
|`coin_analysis/scanner_dashboard_v50.py`|안전하게 제한한 실제 오류 코드와 원인별 안내|
|`coin_analysis/dashboard_assets/app.js`|마지막 검사 문구, 교차 검증 경고 표시·실패 해제|
|`tests/test_scanner_clock_v52.py`|새 안전 조건·오류 API 회귀|
|`tests/test_scanner_clock_v47.py`, `tests/test_scanner_dashboard_v50.py`|바뀐 교차 검증·오류 계약 검증|
|`docs/research_status.md`, `docs/scanner_v50_dashboard.md`|현재 정책·실제 결과·한계|

작업 전에 실행 중인 Scanner는 없었다. 원본 SQLite·신호·연구 결과의 기준 해시를 기록하고 마지막에 대조했다. 기준313파일 중309개가 바이트 동일하며, 차이는 의도한 문서2개와 테스트용 관리 pointer2개뿐이다. 기존 DB·연구 결과는 모두 보존했고 원본 신호215개·DB6개 quick_check=ok를 확인했다. manager/worker는 없고8765 listener도0이다. 테스트가 만든 관리 pointer와 신규 검사 기록은 원본 관측 DB와 구분한다. 기존 탐지 threshold·label·관측 간격·결측 정책·NTP 전송 예산은 변경하지 않았다. 작업 전부터 있던 README·콘솔 BAT·잠금 파일 변경도 보존했다. [보존 검사](../reports/scanner_clock_v52_20261026/completion_checks.json).
