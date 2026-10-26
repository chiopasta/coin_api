# CHIO COIN SCANNER V5.2 전체 KRW 수집·검증 — 2026-10-26

**전체 판정: PARTIAL.** 전체 적격 시장의 WebSocket 응답 범위를 실제 확인했다. 전체 시장의 초기화·유효 30분 자료·탐지 평가 완료까지 입증한 상태는 아니다. 자연 신규 LIVE 신호는 0개다. 24시간 실행·무인 운영은 수행하거나 승인하지 않았다.

## 프로젝트와 기존 자료

권위 있는 경로는 `C:\dev\coin_api-1`, Git origin은 `https://github.com/chiopasta/coin_api.git`, 작업 전 HEAD는 `a1616a964408f9af5d7cd52e969a9e1a36c42e78`이다. 작업 전 Git 변경은 없었다. `C:\dev\Coin_api`에는 구형 V15/V16 파일과 DB가 있지만 Git 저장소·현재 BAT·V5.1 보고서는 없었다. 이 폴더와 실행 중인 CHIO BOT Python 3개는 변경·종료하지 않았다.

이 체크아웃에서 **작업 전부터 원본 signals는 163개**다. 요청과 이전 V5.1 문서의 215개와 다르다. 원본 DB의 시작 해시와 종료 해시가 동일하고 실제 분석 API 전체 수도 163개다. 없는 52개를 복원했다고 주장하거나 임의 생성하지 않았다. 215개 원본 실물의 존재·보존은 이 환경에서 입증하지 못했다. [작업 전 파일 기준](../reports/scanner_v52_20261026/baseline.json).

## 실행 경로의 5종목 조사

| 경로 | 최종 동작과 남은 제한 |
|---|---|
| `start_coin_api.bat` → 웹 시작 버튼 | `scanner_desktop_v50 → scanner_control_v410 → forward_scanner_v52`, 전체 공개 KRW 동적 목록. 웹을 여는 것만으로 수집기를 시작하지 않음 |
| `start_scanner_only.bat` → `_scanner` | 같은 manager와 V5.2. 기본 600초/180 HTTP, 전체 목록. 웹 자동 실행 없음 |
| `scanner_control_v410 start` | 같은 V5.2 전체 목록. 기존 manager lock·PID 생성시각·시계 gate·scoped STOP 유지 |
| `python -m coin_analysis.forward_scanner_v52` | 기본 전체 목록. `--validation-markets KRW-BTC KRW-ETH`는 명시적인 소규모 검증 전용. 운영 기본값에는 5개 목록이 없음 |
| V4.2/V4.3 직접 CLI | 과거 고정 BTC/ENA/ETH/FLOCK/SAND, 각 5개·총 10쌍을 보존. 이전 dataset의 동결 범위·resume 재현용이며 새 manager가 실행하지 않음 |
| V4 원본 직접 CLI | 해당 DB의 동결 manifest 범위. 현재 연구 DB를 전체 시장으로 수정하지 않음 |
| `scanner_v16`, `archive/scanner_v15.py` | 기존 별도 연구/보관 경로 그대로. V15 전체 KRW WS와 preload50은 현재 V4 정책과 다름. 보관 프로그램을 수입·실행하지 않음 |

현재 운영 경로에서 `v42.MARKETS`는 구형 dataset의 설명·호환용으로만 남는다. V5.2의 요청 허용 범위는 실시간 목록으로 생성한 거래소별 `venue_markets`다. [이전 전수 조사](scanner_market_scope_20261026.md)의 fixture와 원래 코어는 보존했다.

## 수집과 탐지 구현

`forward_scanner_v52.py`를 추가했다. 공식 공개 REST 시장목록을 읽고 KRW 거래소·종목 쌍을 별도로 등록한다. 공식 `is_trading_suspended`, `market_state`, 종료일을 근거로 제외하며 CAUTION만으로 제외하지 않는다. 상태 필드가 없으면 `LIST_ONLY_STATUS_UNKNOWN`을 기록한다. 목록만으로 주문 가능 여부를 보장하지 않는다.

두 거래소의 공식 Public v1을 사용한다. 100개씩 나누는 것은 보수적인 로컬 batch이며 공식 코드 수 상한으로 주장하지 않는다. trade/ticker를 한 요청으로 전송하고, 전역 연결 간격 ≥0.3초, shard당 최대 3회 시도, 재연결 1/2/4초 대기와 구독 복원을 적용한다. HTTP 418 또는 WS handshake 418/429는 중단한다. 해당 문서에 별도 종목 수 상한은 확인하지 못했고, 실제 3+5개 연결로 범위를 검증했다. [업비트 규격](https://docs.upbit.com/kr/reference/websocket-trade), [업비트 요청 제한](https://docs.upbit.com/kr/reference/rate-limits), [빗썸 Public v1·연결 제한](https://apidocs.bithumb.com/reference/기본-정보), [빗썸 체결](https://apidocs.bithumb.com/reference/체결-trade), [빗썸 연결 관리](https://apidocs.bithumb.com/reference/연결-관리).

수신 thread는 DB를 쓰지 않는다. 8,192개 bounded queue와 단일 SQLite writer를 사용하며 overflow는 조용한 drop 대신 중단한다. message 수·byte·중복·역순·지연·오류·연결 시도를 집계한다. PING과 제한된 연결 timeout을 사용한다.

UTC millisecond 체결 시각과 로컬 수신 시각을 따로 처리한다. `sequential_id`는 유일성 근거로만 쓰고 연속 번호·순서를 가정하지 않는다. 같은 ID의 다른 내용은 차단한다. 역순 체결은 아직 확정되지 않은 분 안에서 event time으로 시가/종가를 정한다. 거래량은 coin 수량, 거래대금은 각 체결의 `price × volume` 합(KRW)이며 종가×총거래량으로 대체하지 않는다.

연결 첫 부분 분봉·단절 분봉은 폐기하고 원래 5초 settle 이후에만 온전한 연결 분의 봉을 저장한다. queue가 남아 있으면 확정을 보류한다. 무체결·누락 분을 가격/거래량 0으로 채우지 않는다. settle 후 늦은 체결은 해당 시장을 BLOCKED로 두고 복구 대상으로 기록한다. 원천 봉 충돌은 덮어쓰지 않고 중단한다. REST 초기화·단절/부분 분 복구는 기존 durable pagination·요청 장부·rate/retry·예산을 재사용하며 한 번의 작업은 1 page로 양보한다. HTTP 예산이 부족하면 WS를 유지하되 미초기화/결측은 그대로 남는다.

공식 정지/종료 항목은 탐지를 건너뛰고 cluster 상태를 보존한다. 비적격 항목이 전체 watermark를 영원히 막지 않도록 운영 상태 진도만 전진시킨다. 봉·feature·label·signal을 생성하는 처리는 아니다. 공식 ACTIVE/정지 해제 정보를 얻으면 부분 분 복구 대상으로 되돌린다. 원래 4%·5분 격자·6시간 warmup·NULL cluster·L1/L2·LIVE/CATCHUP 기준과 원본 연구 코어 파일은 변경하지 않았다.

새 DB는 거래소별 기존 V4 schema와 부가 `ws_candles`, `ws_signal_provenance`를 사용한다. 신호 ID·기준 시각/가격·실제 탐지·평가 지연은 원래 값을 보존한다. WS 기준 마지막 분의 exchange/receipt 시각과 수신 지연을 추가한다. REST만 있는 신호의 확인 불가능한 exchange 지연은 NULL이다. 기존 `record_metrics`와 분석의 5/15/30/60분·MFE/MAE·표본 분모를 재사용한다.

## 카탈로그 변경과 미완료 사항

목록은 매 실행 시 새로 가져오고 600초 및 단절 뒤 제한적으로 재조회한다. membership 변경은 `CATALOG_CHANGED_NEW_FROZEN_DATASET_REQUIRED`로 중단하고 새 목록 증거를 남긴다. 새 명시적 실행은 새 전체 목록을 등록한다. **동일 dataset 안에서 신규 상장을 자동 추가하고 중단 없이 계속 운영하는 기능은 구현하지 않았다.** 기존 고정 universe의 feature/peer 의미와 이전 신호를 바꾸지 않기 위한 제한이며 이 요구는 PARTIAL이다. V5.2 자동 resume/새 세대 dataset 전환도 미구현이다. 과거 V4.3 resume 경로는 그대로다.

WS의 TCP 연결과 수신 분봉은 거래소 내부의 무통보 누락까지 증명하지 않는다. 이를 `NO_EXCHANGE_SEQUENCE_CONTINUITY_PROOF`로 저장한다. 전 시장의 native REST 봉과 지속 대조하는 실증도 없으므로 전체 시장 확정 봉 품질을 완전히 입증했다고 보고하지 않는다.

## 실제 시험 — 시각은 KST

[사전 한도](../reports/scanner_v52_20261026/live_plan.json): 소규모 90초/30 HTTP, 전체 목록 150초/50 HTTP, 시작 최대 2회, 합계 80 HTTP·48 NTP 시도. 실제 **55 HTTP·30 NTP 시도**, 추가 재시도 실행 없음. 시스템 시간·서비스·NTP 원본·방화벽·관리자 설정 변경 0이다. W32Time은 시작 시 Running/Automatic, 원본은 Google이었다. Windows 정상 상태와 두 제공자 각 3개 필수 표본을 그대로 검증했다. 과거 실패 이력은 보존했다.

소규모 시험은 UPBIT/BITHUMB BTC·ETH 4쌍, **21:24:47.444~21:26:17.127**, worker 89.683초다. HTTP 10회, NTP 12시도, 양쪽 2/2쌍 실수신, 실제 WS 봉 각 2개 저장, 총 원천 봉 720/715개다. 각 거래소 알트 1쌍씩 평가 시도했지만 30분 완전 자료는 0이다. 첫 부분 분의 공백이 있었으며 추가 부분 분 복구를 최종 소스에 보강했다. 종료 TIME_LIMIT·정상 reap·forced kill 0·close_errors={}·무결성 ok다.

전체 시험은 실제 인증된 웹 POST 시작 202 → 중복 시작 409·외부 Origin 403 → OBSERVING → 웹 STOP 202 → STOPPED/SAVED다. worker **21:27:53.683~21:29:41.615**, 107.932초. HTTP 45회, NTP 18시도다. 정상 종료 후 웹/분석 HTTP 200을 확인하고 BAT로 웹도 종료했다.

| 완료 조건 | 실제 전체 시장 시험 결과 |
|---|---|
| 1. 업비트 적격 | 목록 298, 공식 상태 제외 2, **296쌍** |
| 2. 빗썸 적격 | 목록 489, 공식 상태 제외 12, **477쌍** |
| 3. WS 구독 | 8연결에 **787쌍 요청 전송**. 개별 ACK는 없음. payload가 확인된 적격 **773쌍**(296+477). 제외 항목 포함 schema 응답 확인은 782쌍 |
| 4. 실제 유효 수신 | 적격 773쌍의 응답을 확인. 60초 이내 신선한 event의 **동시 최대 363쌍**(UPBIT 192·BITHUMB 171). 목록/스냅샷 등록 전체를 ACTIVE로 세지 않음 |
| 5. 탐지 평가 완료 | **0쌍**, 30분 완전 자료 0. 최초 signal_start **21:30:00** 이전에 종료했고 전체 warmup·공통 watermark도 미완료 |
| 6. 마지막 정상 수신 | UPBIT **21:29:41.439**, BITHUMB **21:29:41.352** |
| 7. 호출·오류 | 전체 시험 45 HTTP 모두 200, WS schema 오류/재연결 오류 0. 9,041/4,752 messages, 7,070,463/2,762,584 bytes |
| 8. 시계 | 두 시험 모든 5개 gate PASS. 최대 abs(offset)+불확실성 **0.124531초**, 기존 1초 이내 |
| 9. 자연 LIVE 신호 | **0개**, 자연 신호 저장·실제 30/60분 후속 완료는 미검증 |
| 10. 기존 자료 | 기존 DB **35개 바이트 동일**, 원본 163신호·기존 분석/연구 자료 보존. 요청의 215개 실물은 확인 불가 |
| 11. 테스트/HTTP/브라우저 | 관련 자동 테스트 통과, 실제 두 페이지·API 200, 웹 STOP·BAT 웹 종료 통과. 브라우저 없음으로 클릭·시각 QA BLOCKED |
| 12. 남은 5종목 | 구형 V4.2/V4.3 CLI·그 dataset과 명시적 검증 fixture에만 남음. 현재 BAT/웹 manager는 V5.2 전체 목록 |

전체 시험의 WS 원천 봉은 **0개**다. 마지막 부분 분 뒤 첫 완전 분이 닫히기 전에 요청한 STOP이 처리됐다. 전체 DB의 1,651/947봉은 제한 REST 초기화 자료다. 작은 시험의 실제 WS 4봉과 혼동하지 않는다. 전체 시험은 최초 신호 격자 21:30:00보다 18.385초 먼저 끝났고, 초기 수집 job도 남았다. 전 시장 REST 초기화·기존 탐지 적용 완료를 성공으로 표시하지 않는다.

[호출·수신·종료 집계](../reports/scanner_v52_20261026/live_results.json), [웹 제어·시계·scope 시계열](../reports/scanner_v52_20261026/full_live_control.json), [거래쌍별 수신·제외 근거](../reports/scanner_v52_20261026/full_market_states.json), [소규모 시계](../reports/scanner_v52_20261026/small_clock_checks.json), [전체 시계](../reports/scanner_v52_20261026/full_clock_checks.json). 원시 전체 snapshot 19.66MB와 DB는 Git 제외 runtime에 보존하고 보고서에는 해시와 작은 집계만 둔다.

실제 두 번의 실행 뒤에 제외 시장 watermark·현재 적격 응답 집계·부분 분 복구 예약·418/429 중단·정지 상태 표시를 추가 검증/보강했다. **이 최종 보강 소스의 추가 LIVE 재실행은 하지 않았다.** 앞의 실제 결과는 당시 실행된 revision의 결과이며 최종 소스 전체의 실증과 같다고 주장하지 않는다.

## 자동 검증과 보존

오프라인 시험은 전체 목록 분할, 두 거래소 별도 상태, dedup·conflicting ID·역순, coin/KRW 단위, 첫 부분 분·snapshot 배제, settle·미래/비정상 timestamp, 단절·구독 복원·재시도 한도, 큐 overflow, 공식 정지/재개 경계, 원래 코어 신호/feature/LIVE·PENDING 및 분석 연결·미래 데이터 leakage를 검증한다. 실제 신호를 흉내 낸 자료는 임시 DB에만 기록했다. 원본 DB에 테스트 신호를 삽입하지 않았다.

자동 테스트 **165개 모두 통과**, 실패/오류/skip 0이다. 자동 테스트의 실제 거래소 HTTP/UDP 호출은 없다. 실제 HTTP 제어 테스트와 합성 탐지 테스트를 구분한다. 최종 결과와 파일 보존 대조는 [검증 결과](../reports/scanner_v52_20261026/test_result.json), [보존·프로세스 검사](../reports/scanner_v52_20261026/completion_checks.json)에 기록한다. node 구문 검사와 두 메뉴/71개 고유 DOM ID·363 ACTIVE/중지0 표시 renderer 검사도 통과했다.

브라우저 inventory가 apps=[], browsers=[]이고 `createBrowserTab('iab',...)`가 `Browser is not available: iab`를 반환했다. [브라우저 차단 기록](../reports/scanner_v52_20261026/browser_validation.json). 접근 제한을 우회하지 않았다. renderer 검사는 브라우저 시각 QA를 대체하지 않는다.

종료 후 소유 manager/supervisor/worker/웹 listener가 없고 다른 Python 3개는 계속 존재한다. 정상 close와 checkpoint·SQLite 무결성을 확인했다. 기존 580개 파일 기준 중 관리 pointer/로그 4개와 의도한 연구 상태 문서 1개가 변경됐다. 원본 DB의 비어 있던 WAL(초기 SHA256은 빈 파일 해시)과 SHM 2개는 SQLite 읽기 연결 종료 중 자동 정리됐으며 수동 삭제·가상 복원은 하지 않았다. DB 35개 본체·기존 보고서·연구 정의는 동일하다. 주문·계정 API·키·자동매매·Windows 자동 시작·24시간 관측은 추가하지 않았다.

## 사용

현재 BAT/웹은 V5.2를 실행한다. 짧은 새 관측의 직접 CLI 예:

```powershell
python -m coin_analysis.forward_scanner_v52 --execute-live --runtime-dir data/scanner_v43_live/v52_new_observation --seconds 600 --max-requests 180
```

새 direct-child 경로만 허용한다. 기존 runtime·연구 DB를 지정하지 않는다. 직접 CLI는 해당 runtime의 STOP 파일 또는 Ctrl+C로 종료한다. BAT/웹은 기존 scoped STOP을 사용한다. 전체 초기화가 요청 상한 안에 끝나지 않으면 평가가 0일 수 있으므로 등록 수를 탐지 완료로 해석하지 않는다.
