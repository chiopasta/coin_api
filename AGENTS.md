# 프로젝트 작업 규칙

- 먼저 `docs/research_status.md`를 읽고, 작업 대상 모듈의 문서를 확인한다.
- 연구 threshold·label·관측 간격·결측 정책을 임의로 변경하지 않는다.
- Feature와 signal에는 해당 시각까지 확정된 데이터만 사용한다. 미래 데이터는 label에만 사용하며 leakage 테스트를 유지한다.
- 기존 구현을 우선 재사용한다. discovery/validation DB와 동결 정책은 보존한다.
- 명시적 요청 없이 대량 API 호출·다운로드·장기 scanner를 실행하지 않는다. 실제 API 테스트는 시장·호출·시간 한도를 먼저 고정한다.
- 명시적 요청 없이 자동매매·주문 기능을 구현하지 않는다.
- 변경 후 관련 테스트를 실행한다. 상태가 바뀌면 `docs/research_status.md`에 실제 결과와 미검증 한계를 갱신한다.
