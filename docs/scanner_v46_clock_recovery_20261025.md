# Scanner V4.6 — 시계 검증 원인 규명 및 LIVE 준비

**최종 운영 판정: PARTIAL. LIVE admission은 BLOCKED이며 차단 해제 불가다.**
시계 검증 코드는 보강했지만 호스트의 실제 오차가 기존1초 한도를 넘는다.
Windows 설정·시각·서비스를 강제 변경하지 않았고 LIVE 및24시간 관측은 시작하지 않았다.
READY는 관측 인프라의 준비만 뜻한다. 탐지 정확도·수익성은 기존 INSUFFICIENT_DATA다.

기준 `a61d0f6`, [V4.5 보고서](scanner_v45_observation_readiness_20261025.md).
[환경](../reports/scanner_v46_20261025/environment.json),
[초기 시계 측정](../reports/scanner_v46_20261025/clock_probe.json),
[최종 재측정·오차 검증](../reports/scanner_v46_20261025/clock_recheck.json),
[거래소 비교](../reports/scanner_v46_20261025/exchange_clock.json),
[보존·완료 검증](../reports/scanner_v46_20261025/completion_checks.json).
모든 사람이 읽는 시각은 별도 표시가 없으면2026-10-25 KST다. epoch 계산은UTC다.
호스트가 기록한 시각은 측정된 지연을 포함하며 임의 보정하지 않았다. 과거 로그의 당시 오차는 확정할 수 없다.

## 1. 정확한 실패 원인: 환경·측정·코드의 분리

|분류|확인한 사실|해석|
|---|---|---|
|환경: 서비스|W32Time STOPPED, DEMAND_START/Manual, Win32 exit1077. `w32tm /query /status /verbose`는0x80070426|현재 부팅 이후 서비스가 실행되지 않은 상태. V4.5의 직접 실패 원인|
|환경: 설정|Type=NTP, NtpServer=`time.windows.com,0x9`, NtpClient Enabled=1, SpecialPollInterval=604800초|NTP 사용 설정은 있으나 실행·현재 동기화를 증명하지 않음|
|환경: 시작 경로|서비스 자체의 시작 트리거는 DOMAIN JOINED, 실제 PartOfDomain=false|현재 PC에서 해당 서비스 트리거가 성립하지 않음. 시작 모드를 임의 변경하지 않음|
|환경: 작업 스케줄러|SynchronizeTime Ready, 마지막 실행10/25 01:34:34, LastTaskResult=0, NextRunTime=null|작업 성공 코드가 최근 실제 시계 동기화 성공을 뜻하지 않음. 스케줄을 수정하지 않음|
|환경: 최근 동기화|조회한7일 System 로그에서 마지막 동기화 Event35는10/24 00:07:04.914, 유효 시간 수신 Event37은00:07:25.619|현재 정확도의 인증값이 아닌 과거 로그 시각. 현재 API 상태는 서비스 중지로 조회 불가|
|측정: NTP 통신|Windows·Cloudflare 두 제공자에서 각3표본 응답. Windows stripchart1표본도 성공|이번 경로에서 UDP123 접속 차단이 원인이 아님|
|측정: 실제 오차|로컬이 기준보다 약4.39초 느림. 두 제공자 및 HTTP Date 방향이 일치|이번 LIVE 차단은 허용 가능한 시계를 잘못 거부한 오탐이 아님|
|코드: V4.5 조기 반환|서비스 조회 실패 시 독립 표본 수집도 생략|서비스 실패와 실제 오차를 구분할 수 없었던 진단 결점. 분리해 수정|
|코드: 불확실성|stripchart offset만 판단하고 RTT·서버 root error를 기록하지 않음|숫자만1초 안에 있어도 오차 범위가 한도 밖일 수 있었음. 더 엄격한 판정으로 수정|
|코드: 복귀|벽시계와 monotonic이 함께 절전 시간을 포함하면 기존 drift 검사만으로 복귀를 놓칠 수 있음|Windows awake 시간과 비교해 재검증 경로 추가|

서비스 중지는 그 자체로 시계가 틀렸다는 증거가 아니다. 서비스 중지 상태에서도 정확한 PC라면
기존 서비스 필수 정책이 보수적으로 차단할 수 있다. 이번 호스트는 독립 측정에서도4초 이상 벗어나므로
그 경우에 해당하지 않는다. 서비스 필수 조건을 우회하거나 offset을 가상 보정하지 않았다.
오차 누적의 하드웨어/펌웨어 수준 원인과 서비스가 실행되지 않은 모든 과거 원인은 **미확정**이다.
현재 상태·설정·로그만으로 사용자의 의도나 특정 OS 결함을 단정하지 않는다.

## 2. 실제 오차·불확실성·시간 기준

NTP를 읽기 전용으로 조회했다. `scanner_ntp_v46.py`는 고정 두 제공자×3표본, 재시도0,
UDP 요청별1.2초이며, 별도 child의12초 timeout으로DNS까지 제한한다.
Windows 상태 조회3초를 합친 검증 상한은15초다. 시간 설정·보정·서비스 시작은 하지 않는다.

[RFC5905](https://datatracker.ietf.org/doc/html/rfc5905)의 네 시각 계산으로 offset과 delay를 구한다.
응답의 mode/version/leap/stratum, request origin 일치, peer, reference age, 수신·송신 시각 순서,
표본 중 wall/monotonic 차이를 검사한다. 불확실성에는 RTT/2, 양의 root delay/2,
root dispersion, server precision, 로컬 표본 차이 및 양자화 여유를 더했다.
이는 서버가 광고한 값과 경로 비대칭 상한을 이용한 공학적 범위이며 비인증 NTP에 대한 보안 증명은 아니다.
[Cloudflare 공식 시간 서비스](https://developers.cloudflare.com/time-services/ntp/usage/)와
[Windows 공식 시간 진단 설명](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)을 기준으로 참조를 고정했다.

|측정|time.windows.com|time.cloudflare.com|
|---|---:|---:|
|초기 로컬 시각20:22:38~39의 offset|+4.3849996~+4.3865174초|+4.3874269~+4.3878219초|
|초기 표본별 최대 불확실성|약0.0134초|약0.0704초|
|최종 로컬 시각20:28:55 이후 offset|+4.3930945~+4.3943977초|+4.3959451~+4.3960730초|
|최종 표본별 최대 불확실성|0.012968초|0.069907초|
|최종 표본 구간 합집합|[+4.381372,+4.407366]초|[+4.326106,+4.465918]초|

양수는 **참조 시계가 로컬보다 앞선다**는 뜻이다. 불확실성을 고려해도±1초 범위 밖이다.
기존 `MAX_OFFSET_SECONDS=1.0`, `MAX_SPREAD_SECONDS=0.5`, wall/monotonic1초 한도는 유지했다.
새 판정은 모든 표본의 **abs(offset)+uncertainty≤1초**, 전체 spread≤0.5초,
두 제공자의 오차 구간 중첩을 요구한다. 0.99±0.02초도 차단하는 테스트를 포함한다.

두 측정의 간격은 약377.24초다. 각 제공자 offset 중앙값이 약0.0081~0.0083초 증가했지만
개별 오차 구간이 겹치므로 이를 확정적인 장기 drift rate로 계산하지 않는다.
별도 약0.4초 로컬 표본에서 wall 경과와 monotonic 경과 차이는 약-0.81μs였다.
이는 그 짧은 표본에서 큰 점프가 없었다는 뜻이며 장기 drift나 절전 후 정확성을 증명하지 않는다.

UTC/KST는 현재 Korea Standard Time(+09:00)이며 OS의UTC 표시와 로컬 표시가9시간 차이다.
Scanner의 내부 epoch·NTP 계산은UTC, KST는 표시 및 기존 빗썸 요청 직렬화 계층에만 적용한다.
시스템 시각에4.39초를 더하는 임시 offset 보정은 하지 않았다.

## 3. 거래소 시간 비교와 timestamp 한계

사전 고정한 공개 `/v1/ticker?markets=KRW-BTC`를 거래소당1회, 총2회/재시도0으로 조회했다.
모두200이며 RTT는 업비트0.07370초·빗썸0.02305초다. scanner의 수집/신호 요청이 아닌 진단이다.

- 두 HTTP Date는UTC11:22:43이었다. 로컬 수신보다 각각3.53119초·3.49784초 앞섰다.
  초 단위 양자화와 요청/응답 경계를 고려한 참고 범위는 업비트[3.53119,4.60489]초,
  빗썸[3.49784,4.52090]초다. 서버의 생성·캐시 지점은 확정할 수 없어 admission에는 사용하지 않는다.
- ticker의 `timestamp`·`trade_timestamp`는 서버 NOW와 동일하다고 가정할 수 없다.
  특히 이번 빗썸 응답의 numeric trade timestamp는 `trade_date`/`trade_time`의UTC 해석보다
  **32400.613초** 앞섰다. KST 문자열과UTC 문자열은 서로9시간 차이로 정렬됐다.
  이는 이번 ticker 응답에서 관찰한 일관성 문제이며 모든 빗썸 endpoint에 일반화하지 않는다.
- 원시 응답은 hash와 함께 Git 제외 보존했다. numeric 값을9시간 이동시켜 원천을 고치지 않았다.
  기존 scanner는 ticker를 수집하지 않고 별도 분봉의 명명된UTC/KST 시각을 검증하므로 탐지 입력에 영향이 없다.

따라서 거래소 ticker timestamp를 NTP 대체 기준으로 채택하지 않는다.

## 4. 수정 내용·재시작·절전 안전성

`scanner_clock_v45.py` 진입점을 유지하고 V4.3 wrapper의 운영 revision만4.6으로 표시한다.
기존 dataset config와 연구 정의는 유지한다.

- 서비스 조회와 NTP 측정을 모두 기록한다. 최종 blockers는
  `CLOCK_WINDOWS_TIME_SERVICE_UNVERIFIED`와 `CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY`다.
- 언어 의존적인 stripchart 문자열 파싱을 admission에서 제거했다. UTF-8/CP949 진단 출력 구분을 보강했다.
- 최초 시작·worker 재시작·기존600초 재검증을 유지한다. reference 실패·부정확·측정 불가·DNS timeout은 LIVE 차단이다.
- [QueryUnbiasedInterruptTime](https://learn.microsoft.com/en-us/windows/win32/api/realtimeapiset/nf-realtimeapiset-queryunbiasedinterrupttime)으로
  절전/최대절전을 제외하는 Windows awake 시간을 읽는다. monotonic과의 경과 차이가0.5초를 넘으면
  다음 요청 전에 외부 시계를 다시 검증한다. 검사 공백10초 초과도 재검증한다.
- awake 타이머를 읽을 수 없으면 차단한다. 검증 도중 절전이 확인되면 CLOCK_SUSPEND_DURING_VERIFICATION으로 중단한다.
  느리지만 정상인 reference 검사가 검사 공백 때문에 재귀적으로 반복되지 않도록 갱신 시점을 정리했다.
- 기존1초 wall 점프 감지·단조 실행 한도·재시작 저장 시각 연속성·시계 오류 종료 시PENDING 보존을 유지했다.

실제 강제 절전/복귀 시험은 **SKIP**이다. PC의 다른 작업에 영향을 줄 수 있어 수행하지 않았다.
7일 로그에는10/18 22:50:33 KST의 복귀 이벤트가 있지만 그 직후 외부 오차 자료는 없다.
현재 awake 타이머의 사용 가능·비감소와 복귀 상황의 격리 주입 테스트만 확인했다.
0.5초 이하 복귀 차이·검사 사이의 모든 시계 변화·실제 OS 재부팅은 미검증이다.

## 5. NO_TRADE 실시간 증거 처리

**자동 수집 구현은 SKIP, 실시간 체결 조회0회.** 호스트 시계가 차단 상태이고
기존16,000회/일 예산에서 최악 호출량을 보장할 수 없어 자동 경로를 추가하지 않았다.

|항목|검토 결과|
|---|---|
|교차 검증|기존 V4.4 검증기 재사용 가능. 원천 부재만으로는 증거가 아니며 범위가 충분한 별도 ticks·주변 양성 합계가 필요|
|API 호출량|기존10시장 분당1회는 약14,400회/일+warmup/retry.8알트에 매분1 ticks 페이지를 더하면 최대25,920회/일로 cap 초과|
|최소 후보|예를 들어 고정1거래소-종목쌍을5분마다1페이지면 추가288회/일. 하지만 필요한 구간이500체결 안에 들지 않으면 UNKNOWN이어야 하며 실제 안전성은 미검증|
|증거 지연|새로 얻은 증거의 known_at을 기록하고 이후 가격 부가 평가에만 사용. 당시 signal/feature에 소급 반영 금지|
|보존·재시작|V4.5 원시 hash·증거 테이블·PENDING 복원 방식 유지. 자동 체결 cursor/예산/재시작 파이프라인은 미구현|
|빗썸 ID|기존 ID 재사용·충돌 때문에 다중 페이지 부재 증명을 그대로 확장할 수 없음|
|근거 부족|UNKNOWN/평가 불가 유지. 가상 캔들·거래량·거래대금 생성0, 기존 탐지 결과 수정0|

V4.5 사후 가격474/480=98.75%는 역사적 증거를 사용한 별도 지표로 보존한다.
원천 완성도4/16=25% 및 실시간 당시380/480을 덮어쓰지 않는다.

## 6. 제한 LIVE·시간·후속 평가 결과

시계 gate가 실패했으므로 **실제 LIVE 시작0회, 재시작0회, 신규 LIVE 신호0개**다.
시작·종료 시각, LIVE 분봉 완성도와 새 후속 성과는 **N/A**다.
2회 ticker 진단을 LIVE 관측 성과로 세지 않는다. 기존 관측 DB에 이어받기를 실행하지 않았다.

다른 준비 항목은 원본/신규 임시 DB quick_check=ok, 중복 scanner 프로세스0,
공개 endpoint allowlist·주문 차단·자원 guard를 선별 테스트로 확인했다.
진단 프로세스 RSS 약27.8MiB·가용 디스크 약15.8GiB였다.
실제 모든 고정 시장 지원·분봉 API·장시간 자원 사용은 이번에 재확인하지 않았다.
이 항목들이 준비됐더라도 시계 실패를 상쇄하지 않는다.

**선별65개 테스트 통과**(약4초), 실제 HTTP/UDP를 금지한 테스트 프로세스에서 실행했다.
[선별 목록·로그](../reports/scanner_v46_20261025/selective_tests.log),
[테스트 결과·실행 코드 hash](../reports/scanner_v46_20261025/test_result.json).
전체 회귀·대규모 백테스트는 수행하지 않았다.

검증 항목은 NTP 네 시각/오차 구간·불량 packet/origin·leap·stratum·stale reference·표본 중 점프,
측정 실패·불일치·불확실성 초과 차단, 재시작·복귀·검사 공백 후 재검증,
1/5/15분 정렬·마감+5초 settle, 실제 detected_at 지연, 미래 변경 시feature/cluster 불변,
30분 완료/60분 PENDING 분리, disk 재연결 후PENDING 복원 및 완료 불변이다.
실제 임시 SQLite·별도 child WAL 복구·OS lock과 mock 네트워크/시계 주입을 구분했다.
실제60분 후속 관측과 자연 신호의 복귀 후 평가 완료는 **미검증**이다.

초기 최종 재측정의 진단 파일 처리에서 UTF-8 JSON을 Windows cp949 기본값으로 읽는 오류가 발생했다.
그 측정 결과는 내구 기록되지 않아 원시 결과를 UNKNOWN으로 남겼다.
명시적UTF-8과 측정 즉시 저장으로 고친 뒤 추가6표본 상한을 먼저 기록하고 재측정했다.
전체 작업의 NTP 요청 상한은 초기6+stripchart1+기록 실패분최대6+최종6=**최대19개**다.
이 실패를 성공 표본에 합치지 않았다. 거래소 진단은2회/2성공으로 유지했다.

## 7. 사용자가 수행할 환경 복구 절차

다음은 **실행하지 않은 사용자 절차**다. 관리자 권한·다른 실행 작업에 대한 영향 확인이 필요하다.

1. scanner가 종료된 상태에서 Windows **설정 → 시간 및 언어 → 날짜 및 시간**의 자동 시간 설정과 동기화 상태를 점검한다.
   타임존은 현재처럼 Korea Standard Time을 유지한다. 로컬 시각을 수동으로4.39초 이동하는 방식을 사용하지 않는다.
2. 권한 있는 운영자가 W32Time 시작 경로와 Time Synchronization 작업 트리거를 점검한다.
   필요할 때 관리자 PowerShell에서 `Start-Service W32Time`, `w32tm /resync /rediscover`를 수행할 수 있다.
   이 명령은 시스템 시각을 바꿀 수 있으므로 다른 연구 작업 영향을 먼저 확인한다.
   지금 접속 가능한 NTP 서버를 바꾸거나 레지스트리/폴링 간격을 임의 변경할 근거는 없다.
3. `w32tm /query /status /verbose`와 `Get-Service W32Time`으로 상태를 확인하고,
   아래 읽기 전용 검증을 실행한다. 매 실행은 최대6 NTP 패킷/15초다.

```powershell
python -c "import json; from coin_analysis.scanner_clock_v45 import verify_clock; print(json.dumps(verify_clock(), indent=2))"
```

4. 결과가 VERIFIED이고 모든 offset+불확실성이1초 이내이며 두 제공자가 일치해야 한다.
   서비스가 다시 중지되거나 시간이 벗어나면 차단이 유지된다. 코드 상수를 늘리거나 예외 처리로 건너뛰지 않는다.
5. 그 뒤에만 새 episode의 시장 지원·API·DB·lock·보호 입력·주문 차단·자원 조건을 재확인한다.
   감독하 짧은 관측과 명시적 수동 재시작을 별도 고정 한도로 실행한다. 기존 증거 DB를 재사용하지 않는다.

## 8. 보존·운영 판정·V4.7 권장 작업

- 기존 신호 **163개**, 보호 입력 **86개**, **STALE_OPEN115** 장부·구형 원본 DB hash 불변.
- 기존 V4.2/V4.3 episode·V4.4/V4.5 원시 자료/보고서 등83개 이전 증거 파일 hash 불변.
  원본 DB는 비어 있는 WAL 확인 후 immutable 읽기만 했고 새 schema/lifecycle은 임시 DB에서 시험했다.
- 탐지 core·collector·V4.2·V15·price overlay 정책·동결 validation policy/manifest 변경0.
  4%·5분 격자·label·cluster·점수 없음·300초 가격 신선도는 유지했다.
- 주문·API 키 로딩·CHIO BOT 통합·서비스 시작/시각 보정·자동 재시작 등록·24시간 실행·Windows 종료0.
  진단 raw 응답은Git 제외, 코드·문서·작은 검증 증거만 커밋한다.
- 커밋·origin/main 푸시 후 로컬/원격HEAD와 보호 입력을 다시 확인한다. 정확한 커밋은 최종 응답에 남긴다.

운영 인프라는 **PARTIAL**, 실제 LIVE는 **BLOCKED**, **24시간 무인 운영 승인은 불가**다.
시계 원인과 실제 오차는 확인했고 측정·복귀 guard는 보강했지만 관리자 환경 조치가 남았다.
장기 drift·실제 절전/재부팅·자연60분 평가·하루 API/자원/오류 회복은 아직 검증되지 않았다.

V4.7은 사용자 환경 동기화 후 두 제공자 재검증을 먼저 통과시키는 것이 우선이다.
이후 짧은 새 episode에서 STOP/수동 resume·UTC 진행·수신 지연·원천/가격별 완성도·자원을 확인한다.
빗썸 ticker timestamp와 체결 endpoint의 의미는 별도 제한 자료로 검증하고 NO_TRADE 자동 수집 예산을 설계한다.
증거 없는 구간은 UNKNOWN으로 유지하며 실제30/60분 자료를 확보하기 전 성과 완료를 주장하지 않는다.
