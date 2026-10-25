# Scanner V4.8 — Windows 시간 불확실성 분석 및 제한 관측

기준 커밋: `8cdc6e2ec38fc042e92a91a2e47be7796661ac64`. 측정일: 2026-10-25 KST.
판정: 관측 인프라 **PARTIAL / 전체 시계 검증 FAIL·LIVE BLOCKED / 24시간 NOT_READY**.
Windows 루트 조건은 설정 변경 없이 자연 수렴하여 통과했다. 이후 두 차례의 새 전체 검사에서
각각 Windows NTP 표본1개가 timeout되어 LIVE는 실행하지 않았다.
READY는 관측 인프라만의 판정이며 탐지 정확도·수익성 판정이 아니다.

## 원인과 시간 값의 의미

직접 차단 원인은 `CLOCK_WINDOWS_ROOT_UNCERTAINTY`다. V4.7의 Windows 루트 거리
7.78255935초는 외부에서 관측한 실제 offset이 아니라 Windows가 보고한 시간 품질의
불확실성이다. 이번 최초 전체 검사에서도 Windows 루트 분산3.8087560초,
루트 지연0.0394439초, 합성 루트 거리3.82847795초로 기존1초 조건을 초과했다.
외부 두 제공자의 작은 offset만으로 이 조건을 덮어쓰지 않았다.

동일 Google 원본에서 자연 동기화가 진행되며 분산이 감소했다.

|마지막 성공 동기화 KST|루트 분산(초)|루트 거리(초)|기존 Windows 판정|
|---|---:|---:|---|
|21:12:28, V4.7 보존 증거|7.7630189|7.78255935|BLOCKED|
|21:29:32|3.8087560|3.82847795|BLOCKED|
|21:46:36|1.8216905|1.84138495|BLOCKED|
|22:03:40|0.8362296|0.8558684|PASS|

자연 갱신 간격은1024초다. 같은 동기화 epoch를 여러 번 조회한 것은 새 NTP 표본으로
세지 않는다. 원본 직접 조회3표본의 광고 root dispersion은0.000091552734375초,
root delay는0으로, 당시 호스트가 보고한 수초 분산과 다르다.

관찰 결과는 **서비스 복구 후 초기 필터가 충분한 유효 표본을 확보하며 수렴하는 현상**과
일치한다. RFC5905의 필터는 초기 큰 분산의 dummy 표본을 유효 표본으로 교체하면서
가중 분산이 감소한다. 다만 W32Time은 RFC의 정확한 구현이 아니며 Windows 내부 필터
메모리를 조사하지 않았다. 따라서 내부 원인까지 단정하지 않고 관측에 근거한 추론으로 기록한다.
근거: [RFC5905 §10](https://www.rfc-editor.org/rfc/rfc5905.html#section-10),
[Microsoft W32Time 알고리즘](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/how-the-windows-time-service-works).

`LocalClockDispersion=10`은 원본을 얻지 못할 때 내부 시계의 정확도를 나타내는 설정이며,
현재 offset10초나 이 분산의 직접 원인으로 해석하지 않는다.
[Microsoft 설정 설명](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings).
레지스트리·시각·서비스·폴링·NTP 서버 변경이나 강제 resync는 수행하지 않았다.

분류상 직접 차단은 환경이 보고한 큰 불확실성이고, 이를 실제 시각 오차로 읽는 것은
측정 의미의 혼동이다. 새 production 코드 결점은 확인하지 못했다.
복구 후 초기 필터 수렴이라는 내부 원인 설명은 **추론**이며, 비공개 내부 상태까지 입증한
정확한 근본 원인으로 과장하지 않는다. 마지막까지 분산이 큰 고장 상태가 지속된 것은 아니다.
[추세 원문31회](../reports/scanner_v48_20261025/trend.json),
[분석·독립 측정 원문](../reports/scanner_v48_20261025/root_diagnosis.json).

## Windows 환경과 변경하지 않은 정책

W32Time은 Running/Automatic, 윤초0·계층2·마지막 동기화 오류0,
선택 원본은 `time.google.com,0x8`이다. 구성 peer는 Windows와 Google이며
현재 poll exponent10=1024초, MinPoll10·MaxPoll15다. SpecialPollInterval32768이라는
설정값을 현재 실제 폴링 주기로 사용하지 않는다.

시스템 이벤트에는 복구 당시21:12의 약4.4454초 시계 조정과 정상 NTP 수신/원본 선택이 있다.
VMIC158 정보 이벤트는 비Hyper-V 환경에서의 공급자 안내이며 NTP 동기화 오류로
분류하지 않는다.21:35:41과22:05:44의 서비스 조회 모두 Running/Automatic이다.
최근6시간 조회 범위에는 새 NTP 오류나21:12 이후 Kernel-General 시계 step 이벤트가 없다.
이벤트 부재로 모든 작은 slew/drift가 없었다고 주장하지 않는다.
재부팅 후 자동 시작 가능성은 설정에서 확인하지만 실제 재부팅은 수행하지 않았다.
[시작 환경](../reports/scanner_v48_20261025/environment_initial.json),
[종료 환경](../reports/scanner_v48_20261025/environment_final.json),
[읽기 전용 구성](../reports/scanner_v48_20261025/configuration.json).

시계 검증 정책과 production 코드는 변경하지 않는다.

- Windows 루트 거리 `분산+지연/2≤1초`, 동기화 상대 나이≤3600초,
  윤초·계층·오류 및 필드 파싱 정상 조건을 모두 유지한다.
- Windows·Cloudflare 각각3표본의 `abs(offset)+uncertainty≤1초`,
  offset spread≤0.5초, 오차 구간 공통 중첩, 가장 오래된 표본≤15초를 유지한다.
- 불확실성에는 왕복 지연/2, 원본 root delay/2·dispersion, precision 및
  로컬 wall/monotonic 표본 차이를 포함한다. 서버 광고값과 비인증 UDP 경로에 의존하므로
  보안 인증이나 하루 전체의 절대 정확도를 증명하는 것은 아니다.
- 내부UTC·KST표시 분리, 확정봉 마감+5초,1/5/15분 정렬은 그대로다.
  단조 시간 실행 한도, wall/monotonic 누적 차이1초 차단,600초 재검증,
  재시작·절전 복귀/검사 공백 재검증도 유지한다.

Windows 루트 분산을 무시하는 독립 측정 대체 정책은 도입하지 않았다.
자연 수렴의 추세 분석은 진단일 뿐 LIVE admission을 만들지 않는다.
전체 기존 검사를 새로 통과한 뒤에만 시장/API·프로세스·DB·자원 조건을 검사한다.

## 측정 한도와 보존

사전 고정 한도는 read-only Windows 조회40분/최대42회/60초 간격,
전체 시계 진단최대4회(각6패킷/15초), 선택 원본 진단2회(각3패킷/6초),
거래소 사전 조회4회/20초다. 조건부LIVE는 별도 새 episode에서
두 거래소·기존BTC/ENA/ETH/FLOCK/SAND cohort, 합계최대1200초·2run·260요청이다.
작업 전체 직접NTP 상한96패킷을 별도로 두었다.

원본 DB와 이전V4.3 DB3개는 immutable 읽기에서 quick_check=ok다.
조건부 신규 경로는 `data/scanner_v43_live/episode_20261025_v48/`이며 실제 생성하지 않았다.
추세 조회는21:34:09~22:04:10 KST, 단조 시간1801.286초·31회로 종료했다.
전체 시계 진단3회×6패킷과 Google 원본 진단2회×3패킷, **직접NTP 총24패킷**이다.
OS 자체의 정상 폴링은 이 진단 트래픽과 별개다. 거래소 요청은0회다.

## 외부 시각 오차와 측정 신뢰성

각 셀은 측정 성공 표본의 offset 범위와 표본 최대 불확실성이다. 양수는 참조가 로컬보다
앞선다는 뜻이다. 실패 표본은 평균·범위에서 제외하되 표본 성공 수와 전체 실패 판정을 보존한다.

|검사 시작 KST|Windows 성공/3·offset(ms)·최대불확실성(ms)|Cloudflare 성공/3·offset(ms)·최대불확실성(ms)|전체 판정|
|---|---|---|---|
|21:35:38|3/3, +26.863~+28.356, 13.619|3/3, +28.759~+28.833, 71.025|Windows 루트 조건 FAIL|
|22:04:24|2/3, +47.179~+47.299, 11.975|3/3, +49.745~+51.092, 70.490|NTP 표본 누락 FAIL|
|22:05:04|2/3, +47.334~+48.517, 12.845|3/3, +50.841~+52.435, 71.952|NTP 표본 누락 FAIL|

최초6표본은 두 제공자의 오차 구간 중첩·1초 조건·0.5초 spread·신선도를 통과했고
가장 오래된 표본도1.294초 전이었다. 이후 **측정된** 표본 역시 모두1초 안이며
최종 최대 `abs(offset)+uncertainty`는124.387ms다. 이는 관측된 현재 skew가 수초라는
설명을 지지하지 않지만,5개 성공 표본으로 필수6개를 대체할 수는 없다.

22:04:24와22:05:04 검사에서는 각각 Windows UDP 응답1개가 timeout되었다.
기록된 reason은 `CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE`이며 누락 표본의
송수신 시각도 없어 `CLOCK_REFERENCE_FRESHNESS_UNVERIFIED`가 함께 저장됐다.
오래된 캐시를 사용했다는 뜻이 아니라 **전체 표본의 신선도를 입증할 수 없다는 뜻**이다.
실패 증거를 덮어쓰지 않고 한 번만 새 전체 검사를 시행했으며 재차 실패한 뒤 추가 admission 재시도를 중단했다.
[최초](../reports/scanner_v48_20261025/clock_initial.json),
[루트 통과 후 검사](../reports/scanner_v48_20261025/clock_ready.json),
[재검사](../reports/scanner_v48_20261025/clock_recheck.json).

Windows 성공7/9, Cloudflare9/9, 추가 Google6/6으로 총22/24 응답이 확보됐다.
이 작은 표본의 비율은 장기 서비스 가용성이 아니다. timeout 원인이 경로 손실·방화벽·서버 부하·
응답 제한 중 무엇인지는 **UNKNOWN/BLOCKED**다. 패킷 캡처·방화벽 변경·서버 교체를 강제하지 않았다.
Google의22:04 직접 응답 root dispersion도0.000106812~0.000122070초여서
호스트의 초기 수초 분산이 현재 upstream 광고값 그 자체였다는 설명과는 다르다.
[Google 최초/후속](../reports/scanner_v48_20261025/upstream_ready.json).

시간 기준의 성공 표본들은 서로 일치하지만 비인증NTP와 짧은 표본의 한계가 있다.
따라서 **Windows 루트 조건 PASS, 측정된 오차 범위 양호, 전체 시계 검증 FAIL**을 분리한다.
저장된 성공·실패 검사는 이후 LIVE를 위한 유효 기간이 연장되지 않으며 다음 실행에서도 새 검증이 필요하다.

## 최종 시계 검사·LIVE·품질·종료 결과

|안전 조건/실행 항목|실제 결과|
|---|---|
|Windows 루트 조건|PASS, 루트 거리0.8558684초·동기화 나이83.706초, 최종 시계 검사 시점|
|전체 외부6표본·신선도|FAIL/UNVERIFIED, Windows 표본1개 timeout|
|LIVE 차단|유지, `CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE`|
|기존 DB 무결성·보존|PASS, 원본 및 이전V4.3 DB3개 quick_check=ok|
|중복 Scanner 프로세스|시작/종료 환경 조회 모두0|
|거래소 API preflight|SKIP_CLOCK_BLOCKED,0요청|
|주문 차단·자원·로그 guard|기존 공개 endpoint allowlist/guard 선별 테스트 PASS, 실제 새 LIVE 자원 사용은N/A|
|실제 worker 시작/동일DB resume|0회/0회|
|실제 관측 시작·종료 시각|N/A, 로컬 시계 진단 시간을 LIVE로 세지 않음|
|신규 신호·원천 봉·가격 평가|0개·0개·0개|
|원천/가격 완성도·수집 성공률|N/A, 관측 시도와 분모가 없음|
|신규 결측·실시간/사후 NO_TRADE 증거|N/A·0/0건|
|실제30/60분 예약·완료·PENDING 이어받기|N/A/미검증, 실제 새 신호나 관측DB 없음|

준비한 제한 실행 보조를 두 번 호출했지만 각 호출은 실패한 시계 JSON을 읽고 **API·DB·
supervisor·worker 생성 전에 차단**됐다. 이를 LIVE2회나 실제 재시작 검증으로 세지 않는다.
[최종 결정](../reports/scanner_v48_20261025/live_decision.json).

기존 V4.4 원천30봉 격자 **4/16=25%**, 당시 지식의 가격380/480,
V4.5 사후 증거 가격474/480=98.75%는 보존했다. 이번 신규 완성도나 개선 효과로 재사용하지 않는다.
실시간 체결 증거 수집을 새로 구현하지 않았고 근거 없는 source absence는 UNKNOWN/평가 불가다.
원천 봉·거래량·거래대금·feature·label을 생성/보간하거나 과거 신호를 수정하지 않았다.

## 구현 범위·선별 검증·보존 확인

production 코드 변경0이다. `reports/scanner_v48_20261025/`의 read-only 추세·진단·
보존 검토와 이번 작업 전용 제한 실행 보조, 진단/자식 종료 보호 테스트 및 문서만 추가했다.
관측 보조의 재검사 파일 선택을 명시적으로 변경한 뒤 관련 선별 검증을 다시 실행했다.
기존1초 안전 한도·확정봉·전략·threshold·label·점수 없음·관측 간격·가격300초 기준은 모두 불변이다.

최종 **선별64개 통과**, 실패/오류/skip0,2.952초다.
전체 회귀·discovery·대규모 백테스트는 실행하지 않았다.
테스트 프로세스의 실제HTTP/UDP를 금지했고 시계/root/신선도·점프/복귀·공개 API 범위·
자원/로그 guard·미래 데이터 leakage·PENDING 및 확정 결과 보존을 선별 재사용했다.
실제 임시SQLite close/reopen·자식WAL 복구·OS lock과 mock 네트워크/시계/강제 종료 시험을 구분한다.
강제 정리는 mock에서 자신의 살아 있는 자식 PID 트리만 대상으로 확인했고 실제 강제 종료는0회다.
[선별 로그](../reports/scanner_v48_20261025/selective_tests.log),
[테스트 대상·코드 hash](../reports/scanner_v48_20261025/test_result.json).

원본163신호·보호 입력86개 SHA-256·STALE_OPEN115 및 이전 증거113개 파일의 hash가 유지됐다.
원본 Scanner DB quick_check=ok이며 원본은 비어 있는WAL 확인 후 immutable 읽기만 했다.
탐지 core·collector·V4.2/V4.3·V15·NTP 계산·가격 overlay·동결 policy/manifest에 기준 커밋 대비 변경0을 확인했다.
종료 환경과 프로세스 재조회 모두 활성 Scanner0, 새 관측 경로 없음이다.
[무결성 사전 검사](../reports/scanner_v48_20261025/db_integrity_preflight.json),
[완료·보존 검증](../reports/scanner_v48_20261025/completion_checks.json).

주문·API 키 로딩·CHIO BOT 통합·원본 DB 덮어쓰기·자동 재시작 등록·Windows 설정/시각 변경·
Windows 종료는0이다. Git에는 작은 진단 증거와 코드/문서만 포함한다.

## 남은 위험·24시간 가능 여부·다음 권장 작업

현재 **24시간 운영은 NOT_READY**다. Windows 루트 불확실성 조건이 자연 해소됐다는
성과와 별개로 전체 시계 admission이 실패했으며 실제 제한 관측·정상 종료/resume도 실증하지 못했다.
실제 재부팅·절전 복귀·장기NTP 단절·자연30/60분 후속·24시간 자원/장애 안정성은 미검증이다.
진단 종료 후 장시간 LIVE를 시작하지 않았다.

다음 단계는 Windows NTP 응답 누락의 반복성부터 제한된 패킷·시간 예산으로 조사하는 것이다.
서버/경로/로컬 방화벽 원인이 불명확하므로 timeout 확대·표본 축소·한 제공자로 대체하는
우회는 권장하지 않는다. 관리자 권한이나 네트워크 설정 변경이 필요한 조사는 별도 운영자 작업으로 남긴다.
그 후 기존 전체 검사를 다시 통과할 때만 새 episode의15~20분 감독 관측·STOP/수동resume을 수행한다.
자연30/60분 후속과 재부팅/절전·장기 자원 검증은 별도 승인된 범위에서 순차 진행한다.
