# V4 탐지 지연 원인 조사 — 원래 48건

코드/정책/feature/outcome/DB 수정, API 호출, scanner 실행·중단 없음. 현재 DB를 읽기 전용으로 조회했다. 원래 중간 점검의 마지막 signal_time(2026-10-01 22:20 KST)까지 48건을 고정 대상으로 삼았다.

## 결론

**지연 40건은 두 번의 catch-up 일괄 처리에서 생성됐다. 정상적인 REST 순차 수집 지연은 나머지 8건에서 12초였다.** catch-up이 발생한 직접적인 코드 경로는 확인되지만, 그 전에 왜 처리가 끊겼는지(종료/재시작/절전/장기 오류)는 로그 부재로 단정할 수 없다.

|분류|건수|signal_time 범위 KST|동일 detected_at KST|지연|
|---|---|---|---|---|
|catch-up 1|20|9/30 02:30 ~ 22:10|9/30 22:45:13|35분13초 ~ 20시간15분13초|
|catch-up 2|20|10/1 00:50 ~ 21:55|10/1 22:07:13|12분13초 ~ 21시간17분13초|
|live 시점과 일치|8|9/30 22:55 ~ 10/1 22:20 중 개별 시점|각 t+12초|모두 12초|

첫 두 행은 과거 observation을 처리한 사실이 명확하다. 이들을 각각 “최초 프로그램 실행”/“재시작 실행”으로 강제 분류하지 않는다. session/process 시작 이력이 없다. live-compatible 8건 역시 장기 무중단 운용 전체를 보증하는 표현은 아니다.

## 정확한 시간 정의와 코드 경로

- `minute_candles.ts`: UTC 1분봉 시작 초. V3 Series는 ts+60을 확정 시각으로 사용한다.
- `signal_time=t`: 5분 관측 격자의 과거/현재 평가 기준 시각. 그때 확정 종가를 signal_price로 저장한다. 실제 컴퓨터가 찾아낸 시각이 아니다.
- `detected_at`: cycle에서 전체 수집을 마친 직후 한 번 읽은 `now`. `process_observations` 안에서 생성하는 모든 신호에 동일하게 전달된다. 개별 INSERT 순간이나 알림 전송 완료 시각도 아니다.
- `delay_seconds=max(0, detected_at-signal_time)`. catch-up 한 cycle에서 서로 다른 과거 t가 동일 detected_at을 가진 이유다.
- `first=min(last_observation)+300`부터 `end=floor(min(verified_until, now)/300)*300`까지 누락된 모든 과거 t를 순회한다. t>=config.start이면 과거 t도 signal로 저장한다. 이 경로에는 “현재 cycle의 live 신호만”이라는 제한이 없다.

### 최초 run

`init` 시 forward 시작을 다음 5분 경계로 동결하고, 상태는 start-6시간부터 준비한다. run이 즉시 시작되면 start 이전 warmup에서는 신호를 저장하지 않는다. init 후 실제 run이 수시간 늦으면 **start 이후 과거 신호를 처음 run에서 생성할 수 있다**.

현재 DB의 start는 9/30 00:50 KST이며 page endpoint는 이미 00:47, 00:48 … 00:55 구간에 존재한다. 따라서 첫 20건을 단순히 “초기 6시간 warmup 신호”라고 설명할 근거는 없다. initial init과 첫 실행의 정확한 벽시계 시각도 별도 이력이 없어 확정 불가다.

### 재시작 또는 중단 후 재개

last_observation을 보존하여 과거 미처리 t부터 재개한다. collection_jobs가 남았으면 그 job의 과거 end까지 먼저 마치고 return하므로 최신 cutoff 추격이 다음 cycle까지 미뤄질 수도 있다. 이때 이전 신호 중복은 막지만 **과거 신규 cluster의 복구 생성은 의도된 현재 동작**이다.

전 시장의 최소 verified_until을 watermark로 사용하므로 한 시장의 오래된 job/오류가 전체 신호 계산을 붙잡을 수 있다. last_error는 성공 후 NULL로 지워져 과거 오류를 복원할 수 없다.

## 실제 페이지 기록 / loop 주기

모든 51시장에 공통으로 존재하는 page end를 정렬한 176개 cutoff 중 인접 간격 175개:

- **171개는 60초**, 1개는 120초.
- 9/30 00:55 → 22:45: **21시간50분**.
- 10/1 00:41 → 22:07: **21시간26분**.
- 10/1 22:48 → 23:32: **44분**(원래 48건에 추가 신호를 만들지는 않음).

page end는 요청 데이터 경계이며 응답 수신 시각이 아니다. 역순 backfill 페이지의 중간 end를 실제 그 시간에 polling했다고 오해하면 안 된다. 위 긴 공백은 정상적인 전 시장 매분 cutoff 진행이 보존되어 있지 않다는 증거이며 그 자체로 “프로세스가 정확히 이 시간 동안 종료됐다”는 증거는 아니다.

9/30 22:43 cutoff는 50시장만 존재하고 DATA가 빠져 있다. 10/1 22:06 역시 50시장만 존재하고 CPOOL이 빠져 있다. 다음 공통 cutoff에서 각 20건이 한꺼번에 계산된다. 최소 watermark 구조와 부합하지만, 해당 시장의 당시 미완료 job/HTTP 오류를 입증하는 수신 시간 로그는 없다.

## 51시장 순차 REST 자체의 지연

- 정상 8개 signal은 모두 **t+12초**. 그 값은 5초 settle/주기 대기와 전체 시장 fetch 종료까지 시간을 포함한다.
- Client는 요청 시작 간격을 최소 0.15초로 제어한다. 51회 시작 간격만 최소 약 7.5초이며 HTTP/DB 처리가 더해진다. 정상 12초 중 수집 부분은 대략 7~8초로 설명 가능하지만 **시장별 실측 응답시간으로 분해할 로그는 없다**.
- loop는 cycle 종료 후 `65-time.time()%60`초를 기다려 다음 분 :05 근처에서 시작한다. 오래 걸린 cycle은 wall clock 분을 건너뛰며, 항상 정확히 60초의 실행 간격을 보장하지 않는다.
- 이 초 단위 정상 지연이 20~21시간 backlog를 직접 설명하지는 못한다. 장기 오류/backoff와 중단 여부는 별도 운영 기록이 필요하다.

## 최신 state snapshot: 10/1 23:41:22 KST

- 51시장 verified_until 모두 **23:40:00**, 현재 시각 대비 **82초**.
- 50알트 last_observation 모두 **23:40:00**. BTC의 오래된 last_observation은 signal 계산 대상에서 제외되므로 정상이다.
- 실제 최신 candle close 지연: 최소/중앙 **82초**, 최대 **442초**.
- AUCTION 최신 close 23:34:00(442초), FLOCK 23:36:00(322초), ENS/MIRA/ONG 23:37:00(262초).
- 같은 시장의 verified_until은 23:40까지이므로 오래된 마지막 candle이 반드시 수집 지연을 뜻하지 않는다. 정상 API 검증 구간 내 무체결일 수 있다. last_error는 현재 NULL.
- 이 시점 조회만으로 프로세스 생존/과거 uptime은 보장할 수 없다. 시장별 전체 수치는 `forward_scanner_v4_delay_state_20261001.json`에 보존했다.

## 실제 사례

|market|signal_time KST|detected_at KST|해석|
|---|---|---|---|
|0G|9/30 02:30|9/30 22:45:13|20시간15분13초 뒤 batch 1에서 복구|
|NEAR|9/30 03:25|9/30 22:45:13|19시간20분13초 뒤 batch 1에서 복구|
|ENA|10/1 00:50|10/1 22:07:13|최대 21시간17분13초 뒤 batch 2에서 복구|
|STX|10/1 02:35|10/1 22:07:13|19시간32분13초 뒤 batch 2에서 복구|

48건 각각의 ID/종목/시각/분류는 `forward_scanner_v4_delay_causes_20261001.json`을 참조한다. 이 분류는 새로운 거래 조건이 아니라 기록의 처리 시점에 대한 진단이다.

## 최소 수정안 — 제안만, 미구현

1. **기존 신호/label을 보존한 채 출처 분리:** 세션 시작 시 복구 경계와 세션 ID를 저장하고 warmup/catch-up/live 처리 구분을 명시한다. 당시 실시간 처리와 사후 복구 결과를 별도 통계로 보여준다. 임의의 지연 cutoff로 과거 성공률을 유리하게 만들지 않는다.
2. **운영 감사 로그 추가:** process start/stop, cycle start/end, request/response 시각, market·cursor·retry/error, 공통 watermark를 기록한다. 개별 signal 실제 저장 시각도 현재 batch detected_at과 별도 보존한다.
3. **초기화-실행 간 공백 가시화:** 고정된 start를 조용히 바꾸지 말고 실행 시 backlog 길이를 출력한다. forward 누적 시작 여부와 catch-up 상태를 명확히 표시한다.
4. **지속 운영 확인:** PC 절전/종료, 실제 프로세스 실행 여부, 오류와 watermark 지연을 감시한다. 운영이 확인되기 전에는 누적 48건을 순수 live 성과로 사용하지 않는다.

WebSocket이나 연구 threshold 수정은 이번 원인에 대한 선행 해결책이 아니다. 우선 사후 복구와 live를 구별하고 실제 중단 원인을 남기는 최소 관측 장치가 필요하다.
