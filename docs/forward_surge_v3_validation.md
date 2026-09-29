# V3 独立期間検証 / 독립 기간 검증 계획

주 검증은 A: discovery에서 고정한 동일 50알트 + BTC. 종목 구성 변화를 제거하여 4% 필터의 시간 재현성을 확인한다. 종목이 거래 중단되거나 데이터가 부족해도 대체하지 않고 품질/UNKNOWN으로 보고한다.

B는 별도 보조 검증이다. 2026-09-15 00:00 KST 이전의 완결 7개 UTC 일봉 평균 거래대금, 이전 24시간 coverage >=60%, 30일 이전 거래 증거, stable/pegged 제외 정책으로 재선정한다. 현재 시장 목록을 사용하므로 당시 상장/폐지 종목 전체를 정확히 복원하지 못하는 한계가 있다. B는 추가 선정 API 비용이 있으며 이번에는 실행하지 않는다.

## 기간

- 본 기간: 2026-09-15 00:00 ~ 09-29 00:00 KST, 종료 제외.
- UTC: 2026-09-14 15:00 ~ 09-28 15:00.
- 앞 buffer: 09-14 18:00 ~ 09-15 00:00 KST.
- 뒤 buffer: 09-29 00:00 ~ 06:00 KST.
- 전체 UTC: 09-14 09:00 ~ 09-28 21:00.
- 완결 분봉만 받으며 마지막 buffer까지 닫히기 전 실행은 거부한다. 부분 기간으로 자동 변경하지 않는다.

현재 시각별 수집 가능 끝은 dry-run의 `closed_through_kst`와 `latest_research_end_with_6h_buffer_kst`를 본다. 보존한 출력은 그 실행 시각의 스냅샷이다. dry-run은 API/DB 생성을 하지 않는다.

## 동결과 독립성

동결 정책은 `forward_surge_v3_validation_policy.json`, A 종목 50개와 기간/정책 사본은 `research_market_validation_v1_manifest.json`에 보존했다. 새 DB 생성 시 전체 사본이 dataset_manifest에 저장된다. 연구 결과에 따라 threshold나 종목을 바꾸지 않는다. 2차 feature는 관찰만 한다.

본 기간끼리는 겹치지 않는다. 단 discovery의 미래 buffer는 9월 15일 06:00까지 이미 관측된 자료다. 이 노출을 숨기지 않고 첫 6시간 제외 결과를 사전 지정 보조 분석으로 함께 보고한다. 또한 동결 시점이 9월 26일이므로 전체 validation 기간이 동결 이후의 미래였다고 주장하지 않는다. 진정한 전향 검증은 동결 이후 시작하는 별도 기간이 필요하나 이번 요청의 기간을 임의로 변경하지 않는다.

## 수집 재사용 및 비용

기존 수집기에 `--manifest-file`만 추가했다. A는 선정 API 없이 고정 목록을 사용한다. discovery DB는 계획 작성 시 manifest를 read-only로 읽었고 실제 A 수집은 JSON만 읽는다. source DB 경로를 목적지로 지정하면 거부한다. 같은 manifest로 재실행하면 기존 페이지 transaction/cursor와 COMPLETE skip을 사용한다. 다른 manifest로 덮어쓰기는 거부한다.

51시장 × 14.5일 × 1440분 = 최대 1,064,880봉. 200봉 batch 기준 5,355회, latency 포함 0.35~0.65초/요청 가정 31.2~58.0분. retry/빈 구간 검증/선택 일봉 crosscheck 비용은 별도다. 이는 확정 상한 호출량이나 속도 보장이 아니다. 분봉 누락은 무체결 가능성이 있으므로 보간하지 않는다.

DB 크기는 봉당 100~200 bytes 가정 약 106~213 MB(일시 journal/페이지 기록 등 별도). 기존 DB 실측 약 107 bytes/봉이므로 완전 관측 가정 약 114 MB지만 실제 거래 빈도에 따라 줄어든다.

## 실행 (아직 실행하지 않음)

```powershell
python -m coin_analysis.research_dataset_collector_v1 --db data/research_market_validation_v1.db --manifest-file docs/research_market_validation_v1_manifest.json --dry-run
```

2026-09-29 06:00 KST 이후:

```powershell
python -m coin_analysis.research_dataset_collector_v1 --db data/research_market_validation_v1.db --manifest-file docs/research_market_validation_v1_manifest.json
```

중단 후 위 명령을 그대로 재실행한다. 새 downloader를 만들지 않았으며 validation 분석은 실행하지 않았다.
