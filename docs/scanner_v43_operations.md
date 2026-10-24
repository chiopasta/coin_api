# Scanner V4.3 관측 전용 운영

V4.1 core와 V4.2 공개 전송 계층을 재사용한다. 4% range, 5분 격자, cluster,
NULL 결측 정책, feature, L1/L2 label과 LIVE/CATCHUP 경계는 불변이다.
점수는 원래 없으므로 NULL이며 주문·계정 endpoint·API 키 로딩 경로는 없다.
각 거래소 BTC·ENA·ETH·FLOCK·SAND의 고정 cohort로 전체 시장 포착률을 주장하지 않는다.

## 실행 제한과 보존

- 각 명시적 실행은 30~86,400초, HTTP 26~16,000회. 기본은 600초/180회다.
  재실행은 새 run ID/예산을 만들지만 기존 데이터·고정 signal_start·누적 HTTP 장부를 유지한다.
  자동 재시작이나 Windows 자동 실행 등록은 없다. 24시간은 사용자 별도 실행용이다.
- 전체 직렬 최소 간격 0.25초, 거래소 Remaining-Req와 기존 retry/backoff 적용.
  한 요청 timeout 최대5초. 418은 중단, 429/5xx/timeout은 최대5시도 후 다음 분
  같은 durable job에서 재개한다. 연속 오류 round5회면 circuit stop한다.
- 정상 round 시작 전에 최소15초/12회(최초30초/24회)를 남긴다. 장애·많은 backlog의
  최악 시간을 보장하는 예약은 아니므로 그 경우 부분 job도 보존한다.
- RSS256MiB, CPU 한 코어 기준10초 이상 표본60% 초과 시 중단,
  episode 폴더256MiB 또는 가용 디스크256MiB 미만 시 중단.
  heartbeat에 자원·오류를 기록한다. CPU 감시는 차단형 quota가 아니다.
- telemetry는 1MiB×4파일 순환. 새 observer 로그만 가장 오래된 것부터 교체한다.
  HTTP 시도는 별도 SQLite 장부에 호출 전에 FULL sync로 예약한다. 로그 순환·crash로
  호출 카운터를 초기화하지 않는다. DB/신호/가격 기록은 용량 한도 도달 시 삭제 없이 중단한다.
- DB는 commit된 WAL을 복구하고 quick_check를 통과해야 연다. STOP/정상 종료 시
  session 종료·PENDING 보존·WAL checkpoint. Windows 재부팅 후 디스크 기록은 유지되며,
  운영자가 같은 경로에서 `--resume`한다. OS 재부팅 자체는 이번 테스트 범위가 아니다.
- 중단 공백이6시간 초과이면 대량 catchup 대신 BLOCKED한다. 새 관측은 별도 폴더를
  사용하고, 이전 미완료 표본을 삭제하거나 새 cohort와 합치지 않는다.
- V4.2와 공통 supervisor/observer OS lock, 거래소별 DB lock을 사용한다.
  다른 서비스와 같은 IP의 API 사용량은 통제하지 못하므로 운영 전 확인한다.

## 짧은 실행과 이어받기

프로젝트 디렉터리에서 foreground로 시작한다. 원본 DB나 V4.2 episode 경로는 허용하지 않는다.

```powershell
python -m coin_analysis.forward_scanner_v43 --execute-live --runtime-dir data/scanner_v43_live/my_observation --seconds 600 --max-requests 180
```

해당 episode에 STOP 파일을 만들거나 foreground Ctrl+C로 종료 요청한다.

```powershell
New-Item -ItemType File -Path data/scanner_v43_live/my_observation/STOP
```

종료 후 `runs/*.summary.json`의 close_errors가 비어 있고 해당 `*.exit.json`의
worker_reaped=true/forced_kill=false인지 확인한다. supervisor가 자신의 child만 기한+30초에
종료 요청하고 추가5초 안에 끝나지 않으면 kill/reap한다. 강제 종료는 정상 종료로 보고하지 않는다.
DB health 확인 없이 다른 프로세스나 sidecar를 삭제하지 않는다.

STOP으로 끝냈다면 이전 요청 파일을 보존 이름으로 바꾼 뒤 명시적으로 이어받는다.
이 명령은 해당 STOP 파일만 대상으로 한다. 새 episode를 init하거나 원본을 복사하지 않는다.

```powershell
Move-Item -LiteralPath data/scanner_v43_live/my_observation/STOP -Destination data/scanner_v43_live/my_observation/STOP.previous
python -m coin_analysis.forward_scanner_v43 --execute-live --resume --runtime-dir data/scanner_v43_live/my_observation --seconds 600 --max-requests 180
```

같은 `STOP.previous`가 이미 있다면 다른 보존 이름을 정한다. 기한 종료는 STOP을 만들지 않는다.
신호·feature·cluster·collection cursor·미완성 horizon은 동일 DB에서 이어진다. 중단 중 복구한
신호는 실제 detected_at 지연에 따라 CATCHUP이며 당시 LIVE 성공으로 간주하지 않는다.

## 24시간 명령 준비 — 이번 작업에서는 실행하지 않음

```powershell
python -m coin_analysis.forward_scanner_v43 --execute-live --runtime-dir data/scanner_v43_live/day_YYYYMMDD --seconds 86400 --max-requests 16000
```

정상10시장 요청은 분당10회, 하루약14,400회+warmup/시장확인/retry다.
16,000회 hard cap, 기존 cohort와 자원 제한을 유지한다. 분당102회가 필요한
원래51시장×2거래소 확장은 요청·처리 지연 및 미지원 종목 검증이 없어 이번 운영 대상이 아니다.
장기 장애/디스크/CPU 한도에 도달하면24시간 전에도 중단하므로 실제 로그 시간만 관측으로 센다.
짧은 정상 수집·재시작 시험만으로24시간 무인 안전성을 입증했다고 간주하지 않는다.

## 데이터 해석

coverage_windows는 해당 격자 처리 당시1/5/15/30분의 실제 분봉 수를 동결한다.
COMPLETE, 성공적으로 조회한 범위의 SOURCE_ABSENT, NOT_COLLECTED를 구분한다.
SOURCE_ABSENT는 거래소 API에 없는 봉이며 거래정지/무체결의 원인을 단정하지 않는다.
없는 봉은 보간하지 않고 기존 range/feature는 NULL이다. 미래 horizon은 시간이 안 지났으면
HORIZON_NOT_REACHED, 지났지만 실제 봉이 부족하면 INCOMPLETE_FUTURE로 PENDING이다.
이는 오래 기다리면 반드시 COMPLETE가 된다는 의미가 아니다.

신호 context는 기존 feature의 직전5분 가격 변화와 거래대금 배율을 보존한다.
탐지 가격은 response receipt 시각이 detected_at 이하인 확정 종가 proxy다.
초 단위 provenance 한계가 있고 틱 가격·체결가가 아니다. 5/15/30/60분 가격 변화와 MFE/MAE는
기존 nominal signal_time 기준이며 실제 탐지 지연·가격 proxy와 구분한다. 전 구간 실제 봉과
verified 범위가 있어야 완료하며, 완료 값은 immutable이다. 비용·슬리피지·매매 수익률은 없다.

raw DB/로그는 `data/scanner_v43_live/`에 Git 제외 보존한다. 각24시간 실행 종료 후
디스크/무결성을 확인하고 필요하면 종료된 episode 전체를 별도 저장소에 백업한다.

API 근거(2026-10-24 확인): [업비트 분봉·무체결 봉·캔들 그룹 초당10회](https://docs.upbit.com/kr/reference/list-candles-minutes),
[빗썸 분봉 KST 요청 시각](https://apidocs.bithumb.com/reference/분minute-캔들-조회),
[빗썸 Public API 초당150회와 임시 하향 가능성](https://apidocs.bithumb.com/v2.1.0/docs/api-요청-수-제한-안내).
이 관측기의 전체 직렬 상한은 초당4회 이하이며 동일 IP의 다른 작업은 별도 확인 대상이다.
