# Scanner V4.9 — NTP timeout 분석과 제한 LIVE 검증

기준 커밋: `8a703fb5aa95bb64909da7f5798da2f7b8a0b00e`. 측정일: 2026-10-25 KST.
판정: 관측 인프라 **PARTIAL / 제한 LIVE admission PASS·관측 완료 /24시간 NOT_READY**.
실제 timeout2건을 제한 재시도로 복구하고 두 제공자 각각3개 표본을 확보한 뒤 관측했다.
READY는 관측 인프라만의 판정이며 탐지 정확도나 수익성을 뜻하지 않는다.

## 1. 확인된 원인과 미확정 원인

V4.8의 직접 차단 원인은 Windows NTP 수신 timeout으로 필수6표본 중1개가 누락된 것이다.
이번에도 기존 코드를 먼저2회 실행해 Windows **5/6 응답**, Cloudflare **6/6 응답**,
전체 시계 검사 **1/2 PASS**를 재현했다. 과거 V4.8의 수치는 별도 시점의 증거이며 이 분모에 합치지 않는다.

기존 구현은 직렬6요청 사이0.25초를 기다려 같은 제공자에는 정상 응답 시 약0.5초 간격으로
접근했다. 개별 socket timeout은1.2초이며 재시도가 없어 단1회 누락도 차단한다.
이는 간헐적 통신 실패를 복구하지 못하는 구현 특성이다. 기존 로그는 peer 연결 이후의
timeout만 저장해 send/receive 단계를 별도로 식별하지 못한다. 이번 새 로그의 두 실패는
RECEIVE 단계임을 확인했다. **그 누락이 실제 어디에서 발생했는지는 미확정**이다.

성공 응답의 네트워크 왕복 지연은 다음과 같다. timeout은 RTT 통계에 포함하지 않는다.
기존 코드는 실패 표본의 실제 대기 경과를 저장하지 않아1.2초를 실측 RTT라고 기록하지 않는다.

|방식·제공자|성공/전체 요청|실패율|성공 RTT 최소/중앙/최대(ms)|
|---|---:|---:|---|
|기존 Windows|5/6|16.67%|2.923 /4.951 /5.761|
|기존 Cloudflare|6/6|0%|2.393 /2.827 /4.723|
|개선 비교 Windows|6/6|0%|2.662 /4.092 /5.554|
|개선 비교 Cloudflare|6/6|0%|2.716 /4.273 /4.744|

빠른 연속 요청에 대한 서버/경로의 제한이나 순간 손실은 **추정**이다. RATE/KoD 응답을 받거나
패킷 캡처로 손실 지점을 확인한 것은 아니다. 작은 표본의 전후 비교이므로 인과관계·장기 실패율을 확정하지 않는다.
현재 근거로 socket timeout을 늘리거나 서버를 교체할 이유는 확인하지 못했다.
[기존 검사1](../reports/scanner_v49_20261025/baseline_1.json),
[기존 검사2](../reports/scanner_v49_20261025/baseline_2.json),
[개선 비교1](../reports/scanner_v49_20261025/clock_paced_1.json),
[개선 비교2](../reports/scanner_v49_20261025/clock_paced_2.json).

## 2. DNS·UDP·Windows·방화벽

개선 첫 검사에서 Windows는52.231.114.183, Cloudflare는162.159.200.1/162.159.200.123으로
IPv4 해석됐다. 최초 DNS 약11.41ms, 후속 표본 약0.52~0.59ms이며 실패가 없다.
원래 연결 방식과 동일한IPv4/UDP123·같은 두 제공자를 유지한다. hostname의 첫 IPv4를 사용하며
다른 서버를 성공할 때까지 탐색하는 정책은 도입하지 않았다.

실제 양쪽 UDP 응답이 있으므로 전면적인 UDP123 차단은 관측되지 않았다.
W32Time의 로컬123 포트 소유와 별개로 진단은 임시 source port를 사용해 포트 충돌을 피한다.
TCP123 연결 검사를 UDP 성공 증거로 쓰지 않았다. NIC 오류·폐기 카운터는 시작 시 모두0이었다.

방화벽은 활성 상태이고 허용/차단 로깅은 비활성이었다. 조회된 앱별 inbound 차단 규칙 및
로컬 사용자/주소 범위 제한이 있는 outbound 규칙만으로 이 진단의 timeout 원인을 특정할 수 없다.
OS 전체나 중간 장비의 drop 로그·패킷 캡처는 확보하지 않았다. 방화벽 규칙·레지스트리·
서비스·시각·서버 설정 변경과 관리자 권한 강제 작업은 수행하지 않았다.
[환경](../reports/scanner_v49_20261025/environment_initial.json),
[규칙 조회](../reports/scanner_v49_20261025/firewall_rules.json),
[적용 범위 조회](../reports/scanner_v49_20261025/firewall_scope.json).

W32Time은 Running/Automatic·Google 원본·윤초0·계층2·동기화 오류0이다.
비교 시점 마지막 성공 동기화는22:20:45 KST, 루트 분산0.3335888초·지연0.0375974초·
루트 거리0.3523875초로 기존1초 조건을 통과했다. 당시 조회에 표시된 poll은2048초였다.
종료 후 마지막 동기화는22:37:48로 갱신됐으므로 그 표시값을 향후 모든 동기화 간격으로 고정하지 않는다.
스캐너의 직접 측정은 직렬이며 동시 UDP 요청을 만들지 않는다. OS 자체 동기화와 같은 NAT의
다른 장비까지 통제하거나 그 트래픽이 전혀 없었음을 입증한 것은 아니다.
방화벽 진단의 일반 근거: [Microsoft NTP/DNS/UDP 문제 분리](https://learn.microsoft.com/en-us/troubleshoot/windows-server/active-directory/error-message-run-w32tm-resync-no-time-data-available).

## 3. 최소 수정과 유지한 안전 기준

`scanner_ntp_v49.py`에서 전송 스케줄·실패 증거·재시도만 추가하고 V4.6의 패킷 파서·
offset/불확실성 계산·정확도 판정 함수를 재사용했다. `scanner_clock_v45.py`가 새 probe를 사용한다.
observer revision만4.9이며 dataset4.3 config와 탐지 구현은 불변이다.

- **동일 probe 안에서** 같은 제공자 요청은 이전 시도 종료 후 최소2초, 전체 직렬 시도는0.5초 간격이다.
  RFC5905의 burst2초를 보수적인 간격의 참고로 삼았으며 Windows 서버의 실제 제한값을 확인한 것은 아니다.
  [RFC5905 §13.2](https://www.rfc-editor.org/rfc/rfc5905.html#section-13.2).
- 수신 단계의 `TimeoutError`만 같은 논리 표본에서 한 번 재시도한다.2초 backoff,
  전체 최대8시도로 재시도는 합계최대2회다. DNS/연결 오류·형식/원본/시간 검증 실패·KoD는 재시도하지 않는다.
  유효하지만 나쁜 offset/불확실성 표본은 버리거나 더 좋은 표본으로 바꾸지 않는다.
- 필수 유효 표본은 여전히 **Windows3+Cloudflare3**이다. 실패한 모든 시도는 별도 `attempts`에 보존한다.
  성공 표본이 새로 확보돼야만 누락 슬롯을 충족할 수 있다. 실패를 PASS로 바꾸지 않는다.
- 개별 timeout1.2초, 내부 단조 예산10.5초, DNS를 포함한 child 상한12초,
  W32Time을 합친 전체 검사15초와 표본 나이15초를 유지한다. 남은 예산이 부족하면 요청하지 않고 차단한다.
- Windows 루트 거리≤1초·동기화 나이≤3600초, 표본별 `abs(offset)+uncertainty≤1초`,
  spread≤0.5초·두 제공자의 오차 구간 공통 중첩을 그대로 요구한다.
- 검사 전체의 wall/monotonic 차이1초 초과도 추가 차단한다. 기존 worker 점프·절전 복귀/긴 검사 공백·
  600초 재검증·재시작 미래 시각 방지 및 확정봉 마감 규칙을 유지한다.

프로세스 경계를 넘어선 NTP 요청 공유/전역 rate ledger를 새로 구현한 것은 아니다.
supervisor와 worker는 순서대로 재검증하며 이번 작업은 동시 진단을 실행하지 않았다.
OS/다른 도구까지 포함하는 전역 요청 간격과 장기 NAT별 응답 제한은 남은 검증이다.

## 4. 재시도 전후 검증 결과

기존 전체 검사1/2=50%, 개선 비교 전체 검사2/2=100%다.
원천 응답은11/12→12/12이며 비교2회에는 실제 재시도가 발생하지 않았다.
이 개선은 pacing과 제한 재시도를 함께 적용한 작은 비교이며 재시도만의 효과나 장기100%를 뜻하지 않는다.
합성 timeout 주입에서도 실패 기록을 남기고 새 유효 표본으로6개를 완성할 때만 PASS함을 검증했다.
영구 실패·잘못된 응답·큰 오차·DNS 실패·전체 시간 초과는 계속 차단한다.

실제 resume worker의22:35 검사에서는 Windows 두 번째 논리 표본이 수신 단계에서
1.207초 후 timeout됐다. 실패 시도 종료 뒤2.000초 backoff를 지킨 새 요청이 성공했다.
이 검사는 **7시도 중6유효 표본·Windows3/Cloudflare3**을 확보하여7.410초 만에 PASS했고,
가장 오래된 유효 표본도7.236초로15초 이내였다. 최초 실패는 `attempts`에 그대로 남는다.
따라서 실제 통신 실패의 제한 복구가 확인됐으며, pacing만으로 손실이 사라졌다고 주장하지 않는다.
해당 timeout은2초 간격을 지킨 probe 안에서도 발생해 빠른 간격만을 유일 원인으로 확정할 수 없다.

최초 supervisor 검사에서도 Windows 첫 표본 timeout이 발생했으나 새 표본을 받아
7시도·7.440초로 통과했다. 실패 표본을 버려서6개 중5개로 통과한 것이 아니다.
개선 방식 전체 **9/9 검사 PASS**, 유효54/전체56시도다(Windows27/29·Cloudflare27/27).
기존 방식2회와 합친 이번 직접NTP는68시도·65응답이며128패킷 사전 상한 안이다.
진단 비교2회·추가 admission1회·supervisor2회·worker3회·종료 후1회를 합친 분모임을 명시한다.
[모든 검사·실패 시도](../reports/scanner_v49_20261025/ntp_review.json).

개선 비교 성공 표본의 offset은 Windows +59.263~+60.605ms(최대 불확실성12.926ms),
Cloudflare +60.798~+63.600ms(71.206ms)였다. 양수는 참조가 로컬보다 앞선다는 뜻이다.
UTC epoch를 내부에 쓰고 KST는 표시/거래소 요청 형식 계층에서만 변환한다.
비인증NTP·서버 광고 불확실성에 기반한 공학적 검증이며 보안 인증/절대 오차 증명은 아니다.

종료 후 전체 검사도PASS다. Windows offset **+67.631~+70.436ms**(최대 불확실성14.443ms),
Cloudflare **+69.438~+70.848ms**(70.335ms), 최종 최대 `abs(offset)+uncertainty`140.552ms다.
유효 표본의 최대 나이는4.531초, Windows 루트 거리는0.12161355초·동기화 나이636.911초였다.
새 방식 모든 검사에서 최대 표본 나이는7.236초·최대 전체 검사시간7.440초이며 기준 이내다.
전체 검사·worker guard에서 시간 점프 차단은 발생하지 않았고 종료 후 wall/monotonic 차이는약0.071ms였다.
이는 실제 절전/복귀나 재부팅을 수행했다는 뜻은 아니다.
[종료 후 시계](../reports/scanner_v49_20261025/clock_post.json).

## 5. 실제 제한 관측·품질·후속 평가

새 관측 경로는 `data/scanner_v43_live/episode_20261025_v49/`이며 기존 원본/이전 episode와 분리했다.
API 사전 조회4회/20초·조건부LIVE 합계1200초/2run/260요청을 먼저 고정했다.
업비트·빗썸 각BTC/ENA/ETH/FLOCK/SAND, BTC 제외8거래소-종목쌍의 기존 정책을 사용했다.
시계 전체PASS·원본 DB 무결성/보호·중복 없음·시장/분봉API4회200·공개 endpoint만 허용·
기존 자원/로그 guard 및 선별 테스트 통과 후에만 시작했다.

|실행|worker 시작~종료 KST|단조 경과|종료 상태|LIVE HTTP|
|---|---|---:|---|---:|
|최초|22:34:03.761~22:35:26.120|82.358초|STOPPED / STOP_REQUESTED|29|
|동일DB resume|22:35:33.421~22:48:07.919|754.486초|BOUNDED_STOP / ROUND_TIME_RESERVE|132|

합계 **836.844초(13분56.844초)**이며 재시작 공백7.301초는 제외했다. API 사전 조회4회를
포함하면 HTTP총165회, LIVE만161/161=100%200 응답이다. 첫 실행은 명시적STOP,
두 번째는 다음 round의 시간 여유를 남겨 정상 종료했다. 두 worker/supervisor 모두 reap,
forced kill0·close_errors={}·최종 collection error0·미완료 collection job0이다.
600초 주기 시계 재검증도 실측PASS이며 시작/재시작/운영 중 총worker3회와supervisor2회를 확인했다.
[실행·종료](../reports/scanner_v49_20261025/live_result.json),
[API 사전 조회](../reports/scanner_v49_20261025/api_preflight.json).

최종 두 DB quick_check=ok, 동일 config·기존 append-only 행·완료 결과·state의 비후퇴를 확인했다.
신규 신호 **0개**, 중복 신호0·정렬 오류0이다. 신호/실제 탐지 시각 대조와 자연 신호PENDING
복원은 실제 표본이 없어N/A이며, 미래 데이터 불사용·PENDING30/60분·완료 결과 불변은 선별 fixture로 검증했다.
실제 신호가 없으므로 horizon 예약/완료율의 분모도0이다. 자연30/60분 후속 완료는 미검증이다.

저장 원천2713봉 중warmup2623봉, signal_start22:35 이후90봉이다. 실제 거래소 분봉만 저장했다.
가격 전용 평가는 각격자의 기록 당시 receipt/evidence 지식으로 재구성했으며 사후 자료를 섞지 않았다.

|품질 지표|이번 실제 결과·분모|
|---|---|
|원천 최근30분 완전 격자|4/24=16.67%,8종목쌍×22:35/40/45의3격자|
|원천 minute slot|483/720=67.08%,24격자×30분, 중첩 구간 포함|
|가격 평가 완전 격자/slot|4/24 및483/720, 원천과 구분한 부가 평가|
|원천 부재|237/720slot,20격자SOURCE_ABSENT·NOT_COLLECTED0|
|실시간 NO_TRADE 확정 증거|0건, 원천 부재의 실제 원인은 UNKNOWN 유지|
|가격 평가 불가 이유|미입증NO_TRADE151slot·300초 초과STALE_LAST_PRICE86slot|

API 성공은 모든 달력 분에 거래가 있었다는 뜻이 아니다. 원천 부재를 가상 봉·거래량0·이전 가격으로
채우지 않았고 range/feature/label을 임의로 복구하지 않았다. NO_TRADE 비율은 근거가 없어N/A다.
원천 부재 중 어떤 것이 실제 무거래인지는 이번에 체결API를 추가 조회하지 않아 미확정이다.
기존 **4/16=25%** 원천 결과와 V4.5의 당시380/480·사후474/480=98.75% 가격 결과는
보존했다. 새16.67%는 시점/분모가 달라 탐지 성능 저하나 이번 변경의 효과로 비교하지 않는다.
[품질·이어받기 보존](../reports/scanner_v49_20261025/live_review.json).

RSS peak36.219MiB·한 코어 CPU 표본 peak9.043%·새 episode 약1.862MiB(backup 포함)로
기존256MiB RSS/episode·CPU60% 표본 guard·1MiB×4 로그·가용 디스크256MiB 기준 안이었다.
CPU guard는 OS의 강제 사용량 quota가 아니며 하루 누적 안정성은 미검증이다.

## 6. 선별 테스트·보존·운영 판정

최종 선별69개가 통과했다(실패/오류/skip0,3.169초). 실제HTTP/UDP를 금지했고 전체 회귀나
대규모 백테스트를 실행하지 않았다. 새 테스트는 간격·timeout 복구/시도 보존·8패킷/시간 예산·
무효 응답과 나쁜 정확도 불변·DNS/수신 구분·전체 검사 시계 점프를 다룬다.
기존 root/신선도·leakage·PENDING·WAL·OS lock·자원/로그·공개 endpoint와 자신의 자식만 종료하는
검사를 선별 재사용했다. 실제 임시DB/child와 mock 네트워크 시험을 LIVE 결과와 구분한다.
[목록·코드 hash](../reports/scanner_v49_20261025/test_result.json),
[선별 로그](../reports/scanner_v49_20261025/selective_tests.log).

원본163신호·보호 입력86개 SHA-256·STALE_OPEN115 및 이전 증거138파일 hash가 유지됐다.
원본 및 이전V4.3 DB3개 quick_check=ok이며 원본은 비어 있는WAL을 확인한 immutable 읽기만 했다.
탐지 core·collector·V4.2/V15·V4.7 Windows/신선도 검사·V4.6 NTP 계산·가격 overlay·
동결 policy/manifest 변경0, V4.3은 revision 한 줄 외 변경0을 확인했다.
두DB 세션STOPPED·활성 Scanner0, 원시 신규 DB/로그/backup은 Git 제외 경로에 보존했다.
주문·API 키·CHIO BOT 통합·원본 덮어쓰기·자동 재시작 등록·Windows 시간/서비스/레지스트리 변경·Windows 종료0이다.
[완료·보존 검사](../reports/scanner_v49_20261025/completion_checks.json),
[종료 환경](../reports/scanner_v49_20261025/environment_final.json).

최종 **PARTIAL**, 제한 LIVE는 재개·종료 검증에 성공했지만 **24시간 무인 운영은 NOT_READY**다.
자연 신호30/60분·실제 재부팅/절전 복귀·장기NTP/네트워크 장애·하루 자원/로그 안정성은 미검증이다.
24시간 관측이나 추가 LIVE를 자동 시작하지 않았다.

개선 우선순위는 다음과 같다.

1. 승인된 제한 범위의 패킷/OS drop 증거로 Windows NTP 손실 지점을 조사한다. 지금의 재시도는
   통신을 복구할 뿐 서버/경로의 근본 손실을 제거했다는 증거가 아니다. 방화벽을 무조건 해제하지 않는다.
2. supervisor/worker/다른 진단 사이의 제공자별 전역 요청 간격과 NTP 장부 보존을 검토한다.
   새 검사의 필수6표본·15초 신선도를 유지하고 과거PASS를 무기한 공유하지 않는다.
3. 별도 승인된 감독 관측에서 자연 신호의30/60분PENDING 복원/완료와 실제 절전·재부팅 재검증을 확인한다.
   합성 fixture와 LIVE 완료를 구분한다.
4. 실시간 NO_TRADE 증거의 호출량/수집 지연을 별도 제한 검증하고 그 전에는UNKNOWN을 유지한다.
   장기 자원·장애 검증을 마치기 전에는24시간 무인 준비 완료로 승격하지 않는다.
