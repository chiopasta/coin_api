# V4 실제 Upbit REST bounded smoke — PASS

- 실행: 2026-09-30 00:37:32 KST 시작, 33.37초.
- 한도: BTC/ETH/XRP만, retry 포함 최대 20 HTTP, hard timeout 180초. 장기 scanner run 미사용.
- 실제: **9 HTTP 요청, retry 0, 전부 200 응답**.
- 저장: **1,074봉**, 시장당 358봉. 마지막 분 polling에서 3봉 추가.
- DB: `data/forward_scanner_v4_smoke_1790696252.db`, 기존 연구/장기 DB와 분리.

## 검증

|항목|결과|
|---|---|
|실제 확정 1분봉|통과|
|역방향 API timestamp 정렬 / DB timestamp|통과 / 이상 0|
|동일 cutoff 재처리|행수 동일, 추가 API 0|
|중복 market/ts|0|
|실제 첫 페이지 저장 후 재연결|저장 cursor 다음부터 재개|
|다음 분 수집|3시장 각 1봉 추가|
|DB integrity|ok|
|수집 오류 / 미완료 job|0 / 0|
|Remaining-Req|sec 4~9, header 정상 수신|
|연속 요청 시작 최소 간격|약 0.150초|
|signal|0, 정상|
|PENDING|live 생성 없음. 합성 재시작 테스트로 확인; live 검증으로 주장하지 않음|
|30/60분 outcome|실행시간이 짧아 live 완결 미검증|
|종료|worker exit 0; V4 Python 잔여 프로세스 없음 확인|
|원본 연구 DB|discovery/validation 전후 해시 동일|

429/418을 유발하지 않았다. 실제 차단 회복은 검증하지 않았으며 기존 mock tests에서 확인한다. 4% 정의와 V3 계산은 변경하지 않았다. 모든 요청별 응답 헤더와 시각은 동명 JSON에 보존했다.

## 운영 판단

실제 REST 통신·저장·재개 경로가 확인되어 감독하 제한 운영은 가능하다. 장기 무인 운영의 안정성은 아직 보장할 수 없다. 51시장 기준 하루 약 73,440요청, 중복 payload, 단일 시장 오류에 의한 전체 watermark 정지, 누적 DB/UNKNOWN 검사 비용, 지연 signal의 구분, 모니터링 부재가 남아 있다. WebSocket/최적화/자동매매는 구현하지 않았다.
