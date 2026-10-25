# Scanner V4.5 — NO_TRADE 처리 및 장시간 관측 준비 검증

**운영 인프라 판정: PARTIAL. 현재 호스트의 LIVE 시작은 CLOCK_SYNC_UNVERIFIED로 BLOCKED.**
가격 평가의 유효 범위는 늘었지만 실제 24시간 무인 관측을 승인할 상태는 아니다.
READY는 관측 인프라에만 적용하는 판정이며, 탐지 정확도·조기 포착률·수익성을 뜻하지 않는다.
탐지 성능 판정은 기존처럼 INSUFFICIENT_DATA다.

기준 커밋 `44eb07d`, [V4.4 보고서](scanner_v44_gap_validation_20261025.md),
[비교 증거](../reports/scanner_v45_20261025/comparison.json),
[시계·입력 보존 사전 확인](../reports/scanner_v45_20261025/preflight.json),
[완료 검증](../reports/scanner_v45_20261025/completion_checks.json).
검증일은 2026-10-25 KST다. 추가 거래소 API 호출·LIVE scanner·대규모 백테스트는 **0**이다.

## 1. NO_TRADE 정책과 구현 범위

[업비트 공식 분봉 문서](https://docs.upbit.com/kr/reference/list-candles-minutes)는
거래가 발생한 시간대에만 봉을 생성한다고 설명한다.
[빗썸 공식 분봉 문서](https://apidocs.bithumb.com/reference/분minute-캔들-조회)는
KST 기준의 배타적 `to`, 최대200개 및 역순 반환을 명시한다.
확인한 빗썸 문서에는 무거래 시 봉 생략에 대한 명시적 보장이 없으므로 이를 전체 시장의 영구 규칙으로 단정하지 않는다.
빗썸의 이번 대상 구간에서 무거래 분에 봉이 없었던 사실은 V4.4의 별도 체결 조회와 주변 양성 분봉 대조로 확인한다.
업비트도 개별 분의 NO_TRADE 판정에는 같은 증거를 요구한다.

`scanner_observation_v45.py`는 **가격 전용 부가 평가**다. 다음 원칙을 적용한다.

- 원천 `minute_candles`를 수정·추가하지 않는다. 가상 OHLC·체결·거래량·거래대금0을 만들지 않는다.
- 실제 원천 봉의 종가와 `candle_receipts`를 사용한다. 미래 봉과 평가 시각 이후 수신한 봉은 사용할 수 없다.
- 최근 실제 봉 이후의 모든 빈 분에 독립적으로 검증된 NO_TRADE 증거가 있어야 마지막 종가를 유지한다.
  candle API의 부재·수집 watermark만으로 NO_TRADE를 생성하지 않는다.
- 가격 신선도는 **목표 분 마감 시각 − 원천 봉 시작 시각 ≤300초**다.
  분봉 안의 마지막 체결 시각을 모르므로 실제 가격 나이의 보수적 상한을 사용한다.
  300초는 관측용 공학 한도이며 백테스트나 성과 최적화로 고른 값이 아니다.
- 300초 초과, 유효 가격 부재, 증거 부족, 늦게 수신한 실제 봉과의 모순은 평가 불가다.
  목표 분 마감+기존5초 settle 전에는 PENDING이다.
- `ACTUAL_CANDLE_CLOSE`와 `DERIVED_NO_TRADE_LAST_CLOSE`를 구분한다.
  파생 가격은 candle 테이블에 저장하지 않으며 가격 평가 결과에만 원천 시각·가격 나이·정책을 남긴다.
- NO_TRADE 증거의 `known_at`도 평가 지식 시각 이하여야 한다. 나중에 확인한 증거를 당시 feature로 사용하지 않는다.

기존 V4.3 wrapper를 재사용해 새 `no_trade_evidence_v45`·`price_horizons_v45` 테이블을 추가했다.
후자는 명목 신호 시각 기준 **30/60분 endpoint 종가 변화율**이며,
연속 전체 경로·MFE/MAE·L1/L2의 목표 고가 도달·체결 수익률을 뜻하지 않는다.
기존 `live_horizons`와 `signal_outcomes`를 대체하지 않는다.

**검증된 과거 증거의 적용은 원본의 메모리 복사본에만 수행했다.**
원시 응답 SHA-256, 체결 범위·시각·주변 거래대금 합계를 V4.4 검증기로 다시 확인한 뒤 증거를 넣었다.
실시간 체결 증거의 자동 수집·검증·주입은 **SKIP**이다. 그 호출 비용과 페이지 경계를 검증하지 않았기 때문이다.
실제 LIVE에서 증거가 없는 빈 분은 계속 UNKNOWN/평가 불가로 남는다.
다만 정상 원천 부재는 기존처럼 수집 오류나 전체 프로세스 실패로 계산하지 않는다.

**동결한 탐지 조건은 불변**이다. 기존 확정봉·품질 조건, 30분 range≥4%, 5분 observation,
cluster/reset/NULL 정책, feature, L1/L2, LIVE/CATCHUP 구분, 고정 cohort 및 점수 없음 정책을 유지했다.
CHIO BOT·구형 V15·연구 collector·discovery/validation과 통합하지 않았다.

## 2. 기존 25%와 새 평가 가능 범위

동일한 두 거래소 ENA·ETH·FLOCK·SAND, 23:50·23:55 KST 진단16격자를 사용한다.
이는 신호가 아닌 **LOOKBACK_30M**이다. BTC는 원래처럼 분모에서 제외한다.
480slot은16격자×30분으로 겹친 분을 중복 계산하며, 고유 분은8거래소-종목쌍×35분=280이다.

|지표|기존 결과|V4.5 검증 후|분모·해석|
|---|---:|---:|---|
|원천30봉 완전 격자|4/16=25.00%|**4/16=25.00%**|동일 기준·동일 분모, 탐지 가능 조건 유지|
|원천 분봉 보유 slot|380/480=79.17%|380/480=79.17%|원천 봉 수 불변|
|원천 분봉 보유 고유 분|220/280=78.57%|220/280=78.57%|중복 제외|
|기존 HTTP 수집 성공률|92/92=100%|92/92=100%|분봉88회+지원목록4회, 이번 추가 호출0|
|NO_TRADE slot|100/480=20.83%|100/480=20.83%|개별 부재를 독립 체결 증거로 확인|
|NO_TRADE 고유 분|60/280=21.43%|60/280=21.43%|업비트27·빗썸33분|
|당시 지식으로 가격 평가 가능한 slot|380/480=79.17%|380/480=79.17%|나중에 얻은 무거래 증거는 당시 사용 불가|
|사후 증거 적용 가격 평가 slot|기존 미정의|**474/480=98.75%**|실제 종가380+가격 유지94, 신선도 초과6 제외|
|사후 증거 적용 가격 평가 고유 분|기존 미정의|276/280=98.57%|가격 신선도 초과4개 고유 분|
|30개 가격 endpoint를 모두 평가 가능한 격자|기존 미정의|13/16=81.25%|**가격 proxy 기준**, 실제30봉·range 완전 격자가 아님|

원천 수집·저장 실패는 이번 범위에서 발견되지 않았고 V4.4의 수신/저장 불일치0 결과를 유지한다.
HTTP 성공률은 필요한 모든 달력 분에 거래가 있었다는 뜻이 아니다.
설명된 NO_TRADE로 인한 원천 부재12격자를 수집 실패12건으로 보고하지 않는다.

거래소별 가격 평가 가능 slot은 업비트235/240(파생39), 빗썸239/240(파생55)이다.
가격 평가가 모두 가능한 격자는 각각6/8·7/8이다.
제외6slot은 업비트 FLOCK5slot·빗썸 SAND1slot이며 가격 나이 상한은360~420초였다.
결측을 분모에서 삭제하지 않았고, 98.75%를 탐지 완성도 또는 탐지 성능 개선으로 표현하지 않는다.

## 3. 30분·60분 후속 평가

|평가|30분|60분|해석|
|---|---:|---:|---|
|원천 전체 경로 완료, 기존16진단격자|0/16=0%|0/16=0%|원천 verified_until 이후 자료 미수집|
|V4.5 가격 endpoint 평가 가능, 동일16격자|0/16=0%|0/16=0%|최대300초 가격으로 수십 분 공백을 채우지 않음|
|실제 신규 신호 후속 평가 완료율|N/A(신호0)|N/A(신호0)|0/0을0% 성공률로 보고하지 않음|

종료 뒤 시간이 경과한 것과 관측이 계속된 것은 다르다.
기존 V4.4 당시 PENDING/미수집 이력도 수정하지 않았다.
합성 fixture에서는30분 endpoint만 완료·60분 PENDING, 실제 disk close/reopen 뒤60분 COMPLETE,
완료 행 불변 및 기존 전체 경로 PENDING과의 분리를 확인했다. 자연 신호의60분 완료 실증은 **미검증**이다.

## 4. 시계 정합성

|항목|결과|
|---|---|
|UTC/KST 변환|기존 guard 및 원시 증거 재검증 PASS. 업비트 UTC·빗썸 KST `to` 구분 유지|
|거래소 timestamp|V4.4 원시 체결 epoch/UTC 문자열 및 캔들 UTC/KST 대조를 재사용·재검증. 신규 LIVE 응답 검증은 SKIP|
|봉 마감 경계|1/5/15분 경계 및 기존5초 settle 테스트 PASS. 새 가격 endpoint도 마감+5초 이전 PENDING|
|실제 시스템 시계 정확도|**BLOCKED**. 20:06 KST 사전 조회에서 `w32tm /query /status /verbose`가0x80070426 반환, W32Time 서비스 미실행|
|독립 offset 측정|서비스 조회 실패로 외부 NTP 표본0. 정확/부정확 어느 쪽으로도 단정하지 않음|
|벽시계 이상 차단|단조 시간 대비 누적 차이 절댓값>1초이면 CLOCK_WALL_MONOTONIC_DIVERGENCE. 전진·후진·누적 drift 주입 PASS|
|실행 한도|worker 예산·round 예약·대기 잔여량 및 supervisor timeout을 단조 시간으로 제한. 테스트 PASS|
|재시작 연속성|저장된 watermark/observation/receipt/session 종료/봉 마감/job 종료/부가 평가 시각이 현재보다1초 넘게 미래이면 차단|
|종료 시각|wall `ended_at`과 monotonic elapsed를 함께 저장, clock_fault 별도 표시. 시계 오류 종료에서는 마지막 평가 갱신을 생략|

시작 전과 worker 첫 요청 전, 이후600초마다 Windows 시계 검증을 요구한다.
서비스 조회3초와 `time.windows.com` stripchart3표본/12초를 상한으로 한다.
offset 절댓값≤1초·표본 spread≤0.5초·3표본 모두 확보가 필요하며 불명확한 출력/timeout도 차단한다.
[Microsoft 공식 w32tm 설명](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2012-r2-and-2012/ff799054%28v%3Dws.11%29)에 따라
조회·표본 측정만 하며 서비스 시작·재동기화·Windows 시각 변경을 수행하지 않는다.
단일 비인증 NTP 참조이므로 보안상 시계 증명이나 정밀 교정으로 주장하지 않는다.

기존 HTTP Date의1.194~2.122초 차이는 초 단위 서버 헤더와 로컬 수신 시각의 비교다.
독립 시계 검증을 대신하거나 candle 시각을 보정하는 데 쓰지 않았다.
실제 시계가 정상이라는 증거가 없으므로 **현재 호스트에서는 신규 LIVE 시작 전 차단이 정상 동작**이다.
검사 사이의 작은 시계 변화·OS suspend/reboot 및 장시간 drift의 실제 거동은 미검증이다.

## 5. 운영 안정성·장애 주입

[선별70개 테스트](../reports/scanner_v45_20261025/selective_tests.log)가 모두 통과했다(약4.06초).
전체 회귀·전체 unittest discovery·장기 백테스트는 수행하지 않았다.

|항목|짧은 검증 결과|실제 운영에서 남은 범위|
|---|---|---|
|API 제한|durable 호출 선예약·재구성 한도 차단 PASS. 실패 응답에도 최소0.25초 간격 적용하도록 수정|실제24시간 누적 호출 미검증|
|거래소 제한|업비트 공식 캔들10회/초, 빗썸 공식 캔들 분류150회/초보다 보수적인 전체 직렬4회/초 이하. Remaining-Req/retry/backoff 기존 구현 재사용|동일 IP 다른 프로그램의 합산 부하는 미검증|
|네트워크 재연결|mock URLError→재시도 회복, retry 소진 후 다음 round 회복,5round 연속 오류 circuit stop PASS|실제 장기 단절·DNS/라우터 복구 미검증|
|429/418|기존 Retry-After·Remaining-Req·418 차단 선별 테스트 PASS|거래소 실제 차단을 유발하지 않음|
|DB 이어받기|실제 임시 SQLite close/reopen·pending60분 복원·완료 행 불변 PASS|장기 DB 성장·큰 backlog 미검증|
|중복 프로세스|격리된 실제 OS lock 및 별도 프로세스 거부 테스트 PASS|Windows 재부팅 경로 미검증|
|로그 회전|1MiB×4개 유지, 큰 단일 행은 쓰기 전 LOG_RECORD_LIMIT. 축소 한도 반복 회전 주입 PASS|장시간 실제 로그 패턴 미검증|
|저장 용량|episode256MiB·가용256MiB guard, 용량 도달/가용량 부족 주입 PASS. 원천 삭제 없음|하드 실시간 quota가 아닌 검사 시점 제한이며 한 작업분 초과 가능|
|CPU·메모리|RSS256MiB·10초 표본 한 코어60% guard 주입 PASS|OS 자원 quota 아님. 응답 파싱/계산 도중 순간 peak 및24시간 사용량 미검증|
|비정상 종료|실제 별도 Python의 `os._exit(19)` 후 commit된 WAL·NO_TRADE 증거·PENDING 복구 PASS|전원 장애·디스크 손상·OS 강제 재부팅 미검증|
|정상 종료|mock 수집을 사용한 실제 worker 함수 STOP→세션 STOPPED·summary·DB checkpoint PASS|실제 장시간 LIVE 종료 미검증|
|시계 오류 종료|주입 CLOCK 오류→세션 ERROR·clock_fault·close_errors={}·pending 평가 시각 보존 PASS|검사 사이의 모든 시계 변화를 원자적으로 차단하는 보장은 아님|
|watchdog|timeout 시 자신의 child만 kill/reap하고 forced_kill 기록하는 mock 테스트 PASS|실제 멈춘 scanner child 강제 종료는 이번 작업에서 미실행|
|미완성 관측|collection job·원천 horizon·부가 endpoint는 삭제하지 않고 보존. no-signal은 완료 표본으로 만들지 않음|자연 신호의 중단/재시작 후60분 완료 미검증|

요청 제한 근거: [업비트](https://docs.upbit.com/kr/reference/list-candles-minutes),
[빗썸](https://apidocs.bithumb.com/docs/api-요청-수-제한-안내).
실제24시간 예산은 기존16,000회/86,400초 이내이며 이 작업에서 시작하지 않았다.
시간 한도에 도달하면 신규 평가/요청을 중단하며 종료 정리시간은 별도다.
supervisor는 단조 한도+30초 후 STOP, 추가5초 후 자기 child만 강제 종료한다.

## 6. 보존·완료 확인

- 기존 신호 **163개**, 보호 입력 **86개 SHA-256 불변**, 원본 DB `quick_check=ok`.
- **STALE_OPEN115** 장부와 구형 원본 DB SHA-256 불변. exit/pnl·연구 결과 재작성0.
- 기존 V4.2/V4.3 episode, V4.4 보고·원시 응답 파일을 사전 hash와 사후 대조했다.
  원본은 비어 있는 WAL을 확인한 뒤 immutable 읽기만 했고 추가 schema는 메모리/임시 DB에만 만들었다.
- V4 core·collector·V4.2·V15·동결 validation policy/manifest 변경0.
  V4.3 운영 wrapper와 선별 테스트, 독립 시계/가격 계층 및 문서만 변경했다.
- 거래소 API 추가 호출0, 실제 scanner 시작0, API 키 로딩0, 주문0, 자동 재시작 등록0,
  다른 작업/프로세스 종료0, Windows 종료0. 장애 시험 child는 본 테스트가 생성한 프로세스뿐이다.
- 코드·작은 검증 JSON·테스트 로그·문서를 Git에 포함하고 원본 DB·원시 응답을 추가하지 않는다.
  커밋·푸시 후 로컬 HEAD와 원격 브랜치 HEAD를 확인하며 정확한 커밋은 최종 응답에 남긴다.

## 7. 24시간 준비 판정과 V4.6 권장 작업

**PARTIAL**: 검증된 무거래와 수집 실패의 구분, 보수적인 별도 가격 평가,
재시작·종료·자원 guard는 짧은 격리 검증을 통과했다.
**현재 실제 실행의 admission은 BLOCKED**이며 READY 판정을 하지 않는다.
핵심 잔여 위험은 독립 시계 확인 실패, 실시간 NO_TRADE 증거 파이프라인 미구현,
자연 후속60분 자료 부재 및 하루 누적 운영 미검증이다.

V4.6에서는 운영자가 Windows 시계 동기화 경로를 먼저 점검하고 제한된 offset 검증을 통과시킨다.
이후 별도 새 episode에서 감독하 짧은 관측·수동 재시작으로 실제 자원 추이와 pending 복원을 확인하는 것이 우선이다.
NO_TRADE 자동 증거 수집은 거래소별 timestamp·체결 ID 충돌·pagination·호출 예산을 별도 고정해 검증한 뒤 검토한다.
실제30/60분 자료를 확보하고 원천 경로 완료와 가격 endpoint 완료를 계속 나눠 보고한다.
24시간 운영은 그 증거를 검토한 뒤 명시적 실행으로 진행한다. 전략 최적화·주문·탐지 threshold 변경은 포함하지 않는다.
