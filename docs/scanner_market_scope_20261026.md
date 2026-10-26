# 감시 종목 수·전체 시장 범위 점검 — 2026-10-26

**화면의5개는 실제 고정 수집 범위다. 전체 시장의 일부를 순위로 골라 집중 추적한 숫자가 아니다.** 현재 BAT CLI와 웹은 같은 범위지만, 과거 V15 전체 KRW WebSocket 스캐너와는 다르다. 전체 REST 감시는16,000 HTTP 상한과 기존 주기를 충족하지 못하므로 확장 실행하지 않았다.

## 실행 경로 비교

| 경로 | 시장 선택·수집 방식 |
|---|---|
| `archive/scanner_v15.py` | 업비트·빗썸 `get_markets`에서 KRW 전체 목록, 각 `upbit_open/bithumb_open`에서 전체 목록으로 trade WebSocket 구독. `PRELOAD_COUNT=50`은 초기 과거 봉 preload만 제한하며 전체 구독 목록을 자르지 않는다. 보관 프로그램은 paper tracking·top-level 실행이 있어 직접 실행/수입하지 않았다 |
| `coin_analysis/scanner_v16.py` | 명시적 `--markets`가 없으면 업비트 KRW 전체. 업비트 전용 별도 연구 엔진이며 위 V15와 다르다 |
| `coin_analysis/forward_scanner_v4.py` | `--market-manifest`로 초기화한 동결 DB 범위. 현재 원본DB는51종목(BTC포함). 전체 거래소 목록을 자동 재선택하지 않는다 |
| 현재 BAT CLI·웹 | `start_scanner_only.bat → _scanner → scanner_control_v410.start`와 웹 `Operations → start_scanner → _scanner` 모두 `forward_scanner_v43 → v42.MARKETS` 사용. BTC·ENA·ETH·FLOCK·SAND, 거래소별5개·합계10쌍. BTC는 기준 자료로 신호 대상은4개·8쌍 |

`docs/scanner_v42_operations.md` 및 `scanner_v43_operations.md`에서 이5개 cohort를 사전에 고정한 제한 관측으로 명시하고, config 검증도 같은 범위를 요구한다. **잊고 남은 max_markets=5가 아니라 실제 wrapper의 의도된 제한**이다. 코어에는 임의5개를 자르는 기능이 없다. 대시보드 최신200개 신호와 최근32개 관측 저장소 제한은 표시/조회 범위이며 시장 선택 제한이 아니다. 연구 수집기의50개 등도 현재 관측과 별개다.

## 실제 거래소 목록

시장목록만 **각1회·총2 HTTP**, timeout각5초·재시도0으로 조회했다. 캔들·NTP·추가 scanner 시작은0회다. [원시 응답·시각](../reports/scanner_market_scope_20261026/exchange_responses.json), [범위 대조](../reports/scanner_market_scope_20261026/legacy_actual_scope_comparison.json).

| 응답 기준 | KRW 수 |
|---|---:|
| UPBIT `/v1/market/all?is_details=true` | 298 |
| BITHUMB `/v1/market/all?isDetails=true` | 489 |
| 거래소·종목 쌍 합계 | 787 |
| KRW 코드 중복 제거 | 493 |

양쪽 HTTP200. 실제 응답에 거래 정지/주문 가능 상태 필드는 없다. 시장경보는 거래 정지와 같지 않으므로 유의종목을 임의 제외하지 않았다. 이 수치는 **공개 지원 KRW 목록**으로, 계정별 주문 가능 여부나 일시 정지까지 보장하지 않는다. 주문/계정 API로 검증하지 않았다. 과거 V15의 선택 함수만 AST로 분리해 같은 실제 응답을 입력한 결과, 업비트298/빗썸489 모두 동일 집합이었다. V15 전체 프로그램은 실행하지 않았다.

## 대시보드·CLI 수정

- **현재 스캔 대상:** OBSERVING 중 실제 `scanner_state`의 고유 종목과 거래소·종목 쌍. 현재5/10, 신호 대상8쌍. 중지는0, 읽기 실패는UNKNOWN이다. 고정 설정5/10도 함께 보여준다.
- **전체 KRW 시장·최근 조회:** 두 거래소의 실제 목록을 근거로493개/787쌍, 거래소별298/489와 조회 시각을 표시한다. 웹 GET/폴링은 거래소를 호출하지 않는다. 근거가 없으면UNKNOWN,1시간이 지나면 오래된 조회값으로 표시한다.
- **집중 추적·후속 평가 대기:** 기존 `signals JOIN live_horizons`에서 PENDING 평가를 가진 고유 종목 수. 같은 종목의 여러 지평을 중복 집계하지 않으며 거래소 쌍도 구별한다. 현재0개/0쌍. 순위 선정/자동 전략이 아니며 전체 스캔 대상 수와 다르다.

`scanner_market_scope.py`에 읽기 전용 설명·집계·예산 계산을 분리했다. 현재 응답은 새 `data/scanner_dashboard_v50/market_scope.json`에 저장했다. 앞으로 신규 worker는 **이미 보내던2개 시장목록 요청의 응답**을 자신의 새 runtime에 기록한다. 추가 HTTP나 cohort 변경이 없다. `scanner_control_v410.snapshot`을 CLI와 웹이 함께 사용한다. 웹은 공개 요약만 보내며 원시 목록·JSON·경로를 UI에 노출하지 않는다. 메뉴2개·시작/종료 버튼·관측 정책은 유지한다.

## 요청 예산·처리량

기존 방식은 매분 공개1분봉을 시장별로 조회한다. 연구 신호는UTC5분 격자이며, 조회 주기와 다르다. dense 시장의6시간 warmup은200봉/page로2요청/쌍이다. 다음은 retry·I/O·CPU·보호 여유를 제외한 계획값이며 성능 보장이 아니다. warmup을 정상24시간 polling에 추가해 보수적으로 계산했다. [계산 결과](../reports/scanner_market_scope_20261026/capacity.json).

| 항목 | 현재10쌍 | 전체787쌍 |
|---|---:|---:|
| 시장목록+warmup | 22회 | 1,576회 |
| 매분24시간+위 준비 | 14,422회 | **1,134,856회** |
| 직렬0.25초 간격만의 round 하한 | 2.25초 | **196.5초** |
| 16,000회 내 준비 후 완전 round | 1,597회 | **18회** |

전체 범위는 요청 상한의약70.93배이며 지연 없는 단순 간격만으로도 매분 한 바퀴를 돌 수 없다. 현재 round 예약12/24회도10쌍용이어서 범위만 늘리면 전체 round를 예약하지 못한다. 24시간을16,000회에 억지로 맞춘 이론적 평균 주기는약78.57분, 정수18회/일로는80분이다. 이는 기존 매분 수집·5분 관측·LIVE/CATCHUP 정책의 동등한 대안이 아니다. **수집 주기를 임의 변경하거나5개를 전체로 바꾸지 않았다.** 같은 가정에서 매분24시간 가능한 상한은11쌍이며, 실제로는 retry·자원 여유 때문에 더 적다. 현재10쌍도 장기 완료/무인 운영 보장은 아니다.

공식 제한은 [업비트 market/candle 각 그룹 초당10회](https://docs.upbit.com/kr/reference/rate-limits), [빗썸 Public 초당150회·상황에 따라 하향](https://apidocs.bithumb.com/v2.1.0/docs/api-%EC%9A%94%EC%B2%AD-%EC%88%98-%EC%A0%9C%ED%95%9C-%EC%95%88%EB%82%B4)다. 현재 코드의 전체 직렬 상한은약4회/초이며 응답의 Remaining-Req/backoff·418/429 처리를 그대로 따른다. 다른 프로그램의 같은 IP 사용은 별도 경쟁 요인이다. [업비트 캔들 문서](https://docs.upbit.com/kr/reference/list-candles-minutes)에 따라 최대200봉/page 및 무체결 시 봉 부재도 유지한다. 거래소 초당 한도가 충분해도16,000회 일일 실행 상한 문제는 해결되지 않는다.

현실적인 후속 최적화는 **두 거래소 전체 trade WebSocket 수신 + 확정 분봉 저장 + 제한 REST 대조/복구**다. 기존 V4의 확정 봉·trade value·receipt·결측·재연결·중복·시계/STOP 검증을 통과한 뒤 동일 엔진에 공급해야 한다. V15의 다른 신호/분봉 구현을 바로 이식하지 않는다. 전체 dense warmup1,574회를 지불한 뒤 REST1분 후속추적10쌍은14,400회를 더 써서 잔여24회뿐이다.8쌍이면 합계13,096회로2,904회 여유가 있으나 실제 WS 처리량·메모리·CPU·복구 비용은 미측정이다. 먼저 제한된 replay/격리 검증으로 처리량을 측정해야 하며, 이번에 새 WS/전략/장기 실행을 만들지 않았다.

## 검증·보존

- **170개 중169통과·구형Python 미설치1skip·실패/오류0.** 실제 장부의 후속종목 중복 제거, 현재 CLI/웹 동등 scope, legacy 전체 selector, 미조회/오래된 목록, 더 큰 목록 응답을 기록해도 cohort는5개인 점, idle 웹 종료가 scanner를 종료하지 않는 점을 검증했다. [테스트](../reports/scanner_market_scope_20261026/test_result.json).
- 사용자의 기존 Scanner가 RUNNING/OBSERVING이어서 **수집기는 중지·재시작하지 않았다.** idle 웹만 교체했고 manager·supervisor·worker의PID+생성시각과 launch/config·예산을 전후 대조했다. 종료 표식 생성0·새 scanner0. 기존 웹은 새 버전으로 유지한다. 실제 `/api/snapshot`과 현재 CLI scope가5/10·493/787·후속0으로 일치하며 독립 SQL도 일치한다. [웹 교체 검증](../reports/scanner_market_scope_20261026/web_reload_validation.json).
- 실제 snapshot으로 JS renderer를 실행해5/493/0·298/489/787, UNKNOWN·오래된 값·메뉴2개를 확인했다. [렌더 검사](../reports/scanner_market_scope_20261026/renderer_check.json). Computer Use의 Windows URL 확인 안전 검사가 브라우저 관찰을 차단해 실제 외관/모바일 검증은 미완료다. 우회하지 않았다.
- 원본 신호215개·기존 정적DB16개·연구 결과·이전 보고서의 해시/테이블 건수를 보존했다. 실행 중인 사용자 runtime·분석 캐시·관리 상태는 자연스럽게 갱신되므로 정적 해시 대조에서 분리하고, 원래 프로세스와 config가 유지됨을 확인한다. 작업은 이 DB에 테스트 신호/봉을 삽입하지 않았다. [보존 검사](../reports/scanner_market_scope_20261026/completion_checks.json).

현재 BAT CLI와 웹의 감지 범위 일치는 검증했지만 **구형 전체 KRW CLI와 현재 관측기의 범위/탐지 정책은 동일하지 않다.** 전체 시장 감시는 아직 적용하지 않았고, 기존1초 시계·OBSERVATION ONLY·16,000HTTP·86,400초·원본/연구 동결·결측 정책은 유지했다. 사용자의 실행을 작업 종료 시 임의 중단하거나24시간을 새로 시작하지 않았다.
