# Research dataset collector V1

별도 DB에 KRW 알트 50개 + BTC의 연구 14일 및 앞뒤 6시간을 수집합니다.
기존 DB/연구 알고리즘은 수정하지 않습니다. 실제 전체 수집은 사용자가 실행합니다.

## 명령

먼저 오프라인 계획 확인 (네트워크와 DB 생성 없음):

```powershell
python -m coin_analysis.research_dataset_collector_v1 --dry-run --start 2026-09-01T00:00:00+09:00
```

연구 기간은 9/1 00:00~9/15 00:00 KST, 수집 기간은 8/31 18:00~9/15 06:00입니다.
종료 buffer까지 완결된 기간만 수집할 수 있습니다. 내부 저장 시각은 UTC epoch 초입니다.
새 DB의 dry-run은 종목을 조회하지 않으므로 `UNSELECTED`를 표시합니다.
이미 manifest가 있으면 확정된 목록을 출력합니다. 알 수 없는 종목명을 추정하지 않습니다.

전체 수집 명령 (이번 구현 검증에서는 실행하지 않음):

```powershell
python -m coin_analysis.research_dataset_collector_v1 --db data/research_market_v1.db --start 2026-09-01T00:00:00+09:00 --days 14 --alt-count 50 --min-prior-coverage 0.60
```

중단 후 동일 명령 또는 `--db data/research_market_v1.db`만 지정해 재시작합니다.
명시한 기간/종목 수/제외 목록이 고정 manifest와 다르면 오류를 냅니다.
새로운 연구는 다른 DB 이름을 사용합니다. `--exclude TICKER1,TICKER2`로 스테이블 목록을 보완할 수 있습니다.

제한된 실제 테스트:

```powershell
python -m coin_analysis.research_dataset_collector_v1 --smoke --max-pages 1
python -m coin_analysis.research_dataset_collector_v1 --smoke
```

smoke는 별도 `research_market_v1_smoke.db`, BTC/ETH/XRP, 2시간, buffer 없음,
프로세스당 최대 12 HTTP 시도로 제한합니다. 각 요청은 200봉이므로 시작 전 봉도 응답에
포함될 수 있지만 2시간 범위만 저장합니다. 선택 API 및 일봉 검증은 실행하지 않습니다.
`--max-pages`는 commit한 페이지 수에 도달하면 정상 종료하며 다음 실행에서 이어집니다.

## 선정과 한계

- 연구 시작 T 이전 완결 UTC 일봉 7일 평균 거래대금 순위.
- T보다 30일 이상 오래된 실제 봉으로 상장 기간을 보수적으로 확인.
- T 이전 24시간 실제 분봉 관측률 60% 이상인 후보 중 거래대금 상위 50개.
- 과거 정책은 95%였으나 T=2026-09-01 조사에서 7개만 확보했다. 70%는 37개,
  60%는 52개여서 고정 60%를 채택했다. 수집 중 자동 완화하지 않는다.
- `--min-prior-coverage`는 명시적으로 지정 가능하며 manifest에 고정한다.
  기존 manifest는 재선정하거나 새 기준으로 덮어쓰지 않는다.
- manifest에 T, 적격 후보 내 거래대금 순위, prior coverage, 적용 최소값, 선정 이유를 저장한다.
- 후보 분포와 거래대금 상위 100개는 `reports/research_selection_distribution.json/.csv`에 보존했다.
- BTC는 별도 기준 데이터로 추가. 고정 스테이블 목록 및 사용자 제외 목록 적용.
- 미래 상승률/연구 기간 내 품질은 선정에 사용하지 않음. 통과 종목 부족 시 오류; 기준 자동 완화 없음.
- 과거 T의 전체 시장 목록을 복원하지 못하므로 현재 시장 목록에 의한 생존 편향이 있음.
- 스테이블 목록은 명시적이며 완전성을 보장하지 않음. 과거 관측률은 미래 연속성을 보장하지 않음.
- manifest 생성 이후 재선정하지 않음. 선정 완료 전 중단되면 다음 실행은 선정을 다시 수행함.

## 저장 및 오류 처리

`minute_candles(market,ts,open,high,low,close,trade_value)`의 `(market,ts)` 기본키와 ts 인덱스를 유지합니다.
`dataset_manifest`, `collection_state`, `collection_pages`, `quality_daily`, `daily_crosscheck`를 추가합니다.
페이지별 캔들 INSERT, 확인 구간 기록, 커서 이동은 동일 트랜잭션입니다.
잘못된 OHLC, 다른 종목 응답, 중복/역전 timestamp, 정체된 커서, 빈 응답은 ERROR입니다.
시작점 이하까지 실제 정상 응답으로 확인한 경우에만 COMPLETE입니다.
ERROR는 다음 실행에 마지막 commit 커서부터 재시도하며 COMPLETE는 API 요청 없이 건너뜁니다.

공용 직렬 요청 제한(시작 간격 0.15초), Remaining-Req 잔여량, 429/5xx/timeout 최대 5시도,
지수 backoff+jitter를 적용합니다. 418은 즉시 중단 상태로 처리하고 운영자가 차단 시간을 확인해야 합니다.
418 또는 smoke 호출 예산 소진은 전체 종목 처리를 즉시 중단합니다.
진행률은 종목·페이지·행·HTTP 시도·retry·성공/실패·속도·남은 페이지 기반 ETA를 출력합니다.
ETA는 해당 실행 속도 추정이며 초기값은 부정확할 수 있습니다.

## 품질과 연구기 연결

KST 날짜별 기대 분수(양끝 부분일은 수집 범위만), 관측 수, coverage, 최장 공백/개수를 저장합니다.
`verified_minutes`는 정상 API 페이지로 확인한 분수, `api_absent_minutes`는 그 중 캔들이 없는 분수,
`unverified_minutes`는 아직 요청 범위를 확인하지 못한 분수입니다.
공백을 다운로드 실패나 확정 무체결로 단정하지 않고 보간하지 않습니다.

`--crosscheck`는 COMPLETE 종목의 완결 UTC 날짜에 한해 일봉 거래대금과 분봉 합계를 비교합니다.
상대 오차 1e-6 이하는 MATCH이며, 나머지는 MISMATCH/UNVERIFIED입니다. 데이터 수정 없음.
일봉 검증은 날짜당 1회 추가 API 호출이며 smoke에서는 비활성입니다.

수정판 V2가 사용하는 `old.load_series`로 실제 smoke DB를 읽는 것을 검증합니다.
수정판의 기존 고정 표본 실행부는 그대로 두었으며 일반 데이터셋의 이벤트 분석은 실행하지 않습니다.
원본 V2 CLI 사용 시 `--markets`에 알트 목록만 지정하고 `--btc-db`에는 같은 DB를 지정합니다.
수정판 V2 전체 실행용 일반 CLI 연결은 별도 작업입니다.

## 비용

51종목 × (14일 + 12시간) = 최대 1,064,880봉, 200봉 batch 기준 5,355회.
선정은 후보 C개/연속성 검사 K개 기준 약 `1+C+8*K`회 추가(재시도 제외).
C=280, K=50이면 총 약 6,036회; K=280이면 약 7,876회.
응답 0.2~0.5초 및 요청 간격을 보수적으로 합산하면 본 수집 31~58분,
선정 포함 위 두 시나리오의 범위는 약 35~85분. 실제 응답속도/희소성/재시도에 따라 달라집니다.
사전 연속성 통과 종목이 50개 미만이면 수집을 시작하지 않고 종료합니다.
