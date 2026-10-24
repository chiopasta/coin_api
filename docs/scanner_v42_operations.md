# V4.2 제한 관측 운영 안내

V4.1 엔진의 조건·feature·label을 바꾸지 않는 관측 wrapper다. 점수·주문·가상자금 체결은 없다. 업비트와 빗썸은 공개1분봉 전송 계층만 다르며 별도 DB에서 같은 V4 정책을 실행한다. 빗썸 결과를 구형 V15 점수 전략의 검증으로 간주하지 않는다.

## 범위와 제한

- 사전 고정 시장: 각 거래소 `KRW-BTC, KRW-ENA, KRW-ETH, KRW-FLOCK, KRW-SAND`. BTC는 benchmark이며 신호 대상은 나머지4개다. 시작 전 두 거래소 시장 목록에 모두 있는지 확인한다. 없으면 중단하며 실행 중 교체하지 않는다.
- 최대900초, episode당 HTTP 최대220회(시장 확인·warmup·retry 포함), 전체 직렬 요청 간격0.2초 이상 및 기존 Remaining-Req/backoff 적용. 매분 polling, 신호는 기존 UTC5분 격자다.
- 실행 파일 합계64MiB, worker RSS256MiB, JSONL 로그1MiB, 가용 디스크256MiB 이상. 한 요청 timeout은 최대5초, 부모 watchdog은 고정 deadline+30초다.
- 원본 DB를 입력·출력으로 열지 않는다. 새 API warmup을 별도로 수집하며, signal_start 이전 약6시간은 사전 자료다. warmup 구간을 실행 중 LIVE 노출 시간으로 집계하지 않는다.
- 실행 상태·request·오류는 `events.jsonl`, 고정 범위는 `config.json`, 실제 종료는 `worker_summary.json`과 `supervisor_exit.json`에 기록한다. raw DB·로그·bootstrap backup은 Git 제외 경로에 보존한다.

## 실행과 안전 종료

새 관측은 명시적인 LIVE 실행 요청이 있을 때만 다음처럼 새 디렉터리에서 시작한다. 아래 명령을 문서 작성이나 분석 과정에서 자동으로 실행하지 않는다.

```powershell
python -m coin_analysis.forward_scanner_v42 --execute-live --runtime-dir data/scanner_v42_live/새_episode --seconds 900 --max-requests 220
```

하나의 supervisor와 worker가 동작한다. Windows Python alias launcher가 별도로 보일 수 있다. 모든 episode에 공통인 supervisor/observer OS lock과 각 DB writer lock을 사용한다. 두 번째 실행은 기존 프로세스를 종료하지 않고 거부한다. 다른 프로그램의 API 사용이나 동일 NAT의 외부 요청까지 제어하는 기능은 아니다.

worker가 있는 해당 episode에 **STOP 파일만 생성**하면 다음 안전 지점에서 수집을 멈추고 session 종료·미완성 결과 보존·WAL checkpoint 후 닫는다. 기존 DB나 다른 프로세스를 삭제하거나 강제 종료하지 않는다.

```powershell
New-Item -ItemType File -Path data/scanner_v42_live/해당_episode/STOP
```

foreground supervisor의 Ctrl+C도 같은 STOP 요청을 시도한다. 정해진 시간 안에 worker가 끝나지 않으면 supervisor가 자신이 만든 worker만 kill/reap하고 `watchdog.json`에 BLOCKED를 남긴다. 그 경우 graceful shutdown으로 보고하지 않으며 재사용 전 SQLite/WAL 검사가 필요하다. 정상 종료 여부는 `supervisor_exit.worker_reaped`, `worker_summary.close_errors`, DB quick_check로 확인한다.

## 재시작 정책

- 자동 재시작은 없다. API418·budget·데이터 충돌·지원 시장 누락·리소스 초과를 숨기고 계속하지 않는다.
- 최초 수집 round 후 실제 disk DB close/reopen과 bootstrap backup을 수행한다. 재연결 전후 모든 저장 논리 값 hash가 같아야 계속한다.
- 같은 episode의 수동 `--resume`은 원래 deadline 이내, STOP 파일 없음, 동일 시장·연구 정책일 때만 가능하다. 요청 수는 append-only HTTP_START 이력에서 이어 계산하며 시간·호출 한도를 초기화하지 않는다.
- deadline이 지났거나 STOP이 설정된 episode는 resume하지 않는다. 새 실행은 새 디렉터리·새 범위이며 별도 관측으로 기록해야 한다. 다른 episode와 성능을 무심코 합산하지 않는다.

## 기록·평가의 의미

- canonical signal_time/price, 실제 detected_at, 확정봉 asof, 직전 가격·거래대금 특징은 기존 signals와 signal_features에 보존한다. score는 **NULL / NOT_DEFINED_BY_V4**, pattern은 기존 `RANGE_30M_GE4_FIRST_CLUSTER`다.
- `live_signal_details.detection_price`는 detected_at 이전 마지막 저장 확정 종가의 proxy다. 정확한 해당 순간 체결가나 주문 가격이 아니다. 재시작/늦은 데이터에서는 도착 시각 custody 한계도 고려한다.
- `live_horizons`는5/15/30/60분 전체 미래 봉·verified 범위가 완전할 때만 COMPLETE다. 부족하면 PENDING으로 남기며 0수익·실패로 바꾸지 않는다. V4 기존 L1/L2의 PENDING/UNKNOWN 규칙을 변경한 것이 아닌 별도 가격 경로 표다.
- 수익률·MFE·MAE는 canonical 신호 확정 종가 기준의 가격 변화이며 수수료·슬리피지·호가·주문 체결이 없다. 완료 결과만 통계에 넣고 LIVE와 CATCHUP을 구분한다.
- 가격 사건 역추적은 신규 episode 내 +5%/+10%/60분의 완전 관측 기준점만 평가한다. anchor 이전 신호도 진짜 급등 onset 예측이라고 단정하지 않는다. 15분 실행에서는60분 사건 분모 자체가 부족할 수 있다.
- 과거163개 신호·원본 DB·기존 연구 결과를 읽어 신규 성과에 보태지 않는다. 종료된 episode의 최종 요약은 `forward_scanner_v42_review.review_episode()`로 read-only 작성한다.

장기 무인 운용을 입증한 문서가 아니다. 현재 단계에서는 제한된 실행을 종료하고 원본을 보존한 채 결과를 검토한다.
