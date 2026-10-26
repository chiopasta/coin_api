# V5.2 시계 수정 후 실제 시작 경로 최종 검증 — 2026-10-26

**제한 LIVE 시작·상태·정상 종료 2회 PASS.** 원본 신호215개와 기존DB·연구 결과를 보존했다. 필수 NTP 응답 누락은 계속 차단되며, 24시간 무인 운영은 NOT_READY다.

## 경로·환경 조사

- 공통 admission은 `coin_analysis/scanner_clock_v45.py::verify_clock()`다. 단독 Python 검사는1회, 웹 `POST /api/control/start`는 `scanner_dashboard_v50.Operations → scanner_desktop_v50.start_scanner → scripts/coin_api_entry.py _scanner → scanner_control_v410.start` 관리 사전 검사, `forward_scanner_v43.run` 감독기 검사, `Budget.check` 수집기 검사로 **독립된 새 검사3회**를 수행한다. 이들은 같은 Windows 상태·두 제공자·표본·정확도·신선도 정책을 쓴다. 과거 PASS를 새 시작에 재사용하는 캐시는 없다. 상태 GET도 NTP를 호출하지 않는다.
- 실제 Python은 모두3.14.7이다. 단독은 isolation=False, 관리 진입은 `-I`로 True, 감독기/수집기는 False다. 관리자는 프로젝트 cwd와 PYTHONHOME/PYTHONPATH 제거 환경으로 실행하며, 서비스 계정으로 전환하지 않는다. 별도의 방화벽·프록시·네트워크 권한 설정은 없다. OS 내부 패킷 손실 원인까지 확인한 것은 아니다.
- NTP child도 프로젝트 cwd를 명시하고 `-E -s`로 Python 환경 변수·사용자 site 영향을 배제했다. 외부 cwd에서 단독 함수를 호출해도 같은 모듈을 실행하는 회귀 검사를 추가했다. 네트워크 설정·Windows 시각/서비스/레지스트리는 변경하지 않았다.
- 이전 기록은 단독6/7응답 PASS, 시작API5/7응답 BLOCKED였다. 실패한 논리 표본은 Windows NTP의 최초 요청·재시도 모두 **RECEIVE TimeoutError**였고 Cloudflare3/3은 정상이었다. 단위·캐시·API에만 존재하는 다른 정확도 기준 때문이 아니다. 어느 서버/방화벽/경로가 손실을 일으켰는지는 UNKNOWN이며 서버 제한으로 단정하지 않는다.

## 변경

| 파일 | 변경 역할 |
|---|---|
| `coin_analysis/scanner_ntp_v49.py` | 수신 대기1.2→1.5초, 논리 표본 재시도1→최대2회. 전체 재시도2회와8요청을 명시적으로 제한. 내부12.75초/child13.25초 이내. 제공자별 유효표본·성공/실패 시도·실패 단계/예외 종류 요약 추가 |
| `coin_analysis/scanner_clock_v45.py` | 공통 NTP 실행 cwd/환경 고정, Python 버전·isolation·cwd 일치 여부와 제공자 요약 기록. child 실패 시에도 필수 표본 부족으로 표시 |
| `coin_analysis/forward_scanner_v43.py` | 감독기 시계 검사 결과의 허용 필드만 launch.log에 출력. 수집·탐지·label 동작 변경 없음 |
| `coin_analysis/scanner_desktop_v50.py` | 독립 시계 gate3회×최대15초와 최초 수집 준비를 고려해 readiness 대기35→75초. 초과 시 기존 소유권 확인·취소/STOP 사용 |
| 테스트3개 | 전송 장애/전역 재시도 상한, 민감 문자열 제외, 외부 cwd, child timeout,35초 이후 실제 프로세스 readiness 경로 검사 |

동일 제공자 간격2초·전체 간격0.5초·backoff2초를 유지한다. **Windows 검사 포함 전체15초**, 두 제공자 각각3개 유효 표본, abs(offset)+uncertainty≤1초, spread≤0.5초, 오차 구간 중첩, 표본15초·Windows 동기화3600초 신선도와 V5.2 루트 교차 검증 조건은 그대로다. DNS/잘못된 패킷/정상 응답의 나쁜 정확도를 좋은 표본이 나올 때까지 재시도하지 않는다. 필수 표본 부족·시간 오차·동기화 실패는 차단한다. 새 진단 요약은 패킷·IP·로컬 포트·원시 오류 문자열·환경 변수 값·인증 토큰을 복사하지 않는다.

## 검증 결과

실행 전에 [한도와 원본 기준](../reports/scanner_start_v53_20261026/baseline.json)을 고정했다. 단독1회·시작최대2회·NTP최대56요청, 시작당120초/40 HTTP, 기존5종목×2거래소 범위다. 웹은 임의 loopback 포트에서 같은 실제 제어 API를 사용했다. 분석 캐시는 시작/갱신하지 않았다.

| 실제 검사 | Windows NTP | Cloudflare NTP | 결과 |
|---|---|---|---|
| 단독 | 4시도/1유효/3수신timeout | 3시도/3유효 | 필수표본 부족 BLOCKED |
| 시작1 관리 gate | 4시도/3유효/1수신timeout | 3시도/3유효 | VERIFIED |
| 시작1 감독기/수집기 각 gate | 각각3/3 | 각각3/3 | 모두 VERIFIED |
| 시작2 관리/감독기 각 gate | 각각3/3 | 각각3/3 | 모두 VERIFIED |
| 시작2 수집기 gate | 4시도/3유효/1수신timeout | 3시도/3유효 | VERIFIED |

- [시작1](../reports/scanner_start_v53_20261026/start1.json): POST202 → OBSERVING → 중복409 → 종료202 → STOPPED/SAVED. worker13.48초,19 HTTP,2752봉,신호0. 관리 시작부터 종료까지약28.98초.
- [시작2·최종 코드](../reports/scanner_start_v53_20261026/start2.json): 같은 경로 PASS. worker15.86초,19 HTTP,2732봉,신호0. 관리 시작부터 종료까지약27.32초. 두 실행은 각각 새 격리 관측DB이며 기존 운영DB를 테스트 입력으로 수정하지 않았다.
- 실제 NTP45/56요청 중40응답·5수신timeout. HTTP총38/80은 모두 공개 시장목록·분봉 GET이며 대량 다운로드/주문 없음. 두 worker 정상 reap·returncode0·forced_kill=False·close_errors={}·WAL 정상 마감. 종료 후 웹 HTTP200, 관리/감독 프로세스0, 작업 listener 종료. 외부 Origin403과 중복 시작409도 실제 확인했다. 최종 snapshot의 시계PASS/오류없음/STOPPED/SAVED를 확인했다.
- [선별 회귀](../reports/scanner_start_v53_20261026/test_result.json): **157개 중156통과·구형Python 미설치1 skip·실패/오류0**. 정상·한 번/같은 표본 두 번 일시 손실 복구·일부/전체 장애·실제 offset 초과·동기화 실패·오래된 PASS 비재사용을 오프라인으로 확인했다. 실제 PC 시간을 틀리게 하거나 네트워크를 차단하지 않았다.
- [보존·종료 대조](../reports/scanner_start_v53_20261026/completion_checks.json): 기존DB6개 전체 SHA256/전체 테이블 건수 동일, quick_check=ok. 원본 signals215·minute_candles460997·scanner_state51·signal_outcomes430 그대로다. 기존 연구 결과·이전 보고서도 기준 해시와 같다. 의도한 문서2개와 관리 pointer2개 외 기존 data/docs/reports 변경·삭제 없음. 새 보고서/문서/격리 관측 자료는 추가 보존한다. 기존 dirty 작업은 덮어쓰거나 커밋하지 않았다.

## 남은 한계

Windows NTP 수신 누락은 이번 단독 검사에서도 발생했다. 정상 Windows 시계라도 필수 제공자 응답이 없으면 다음 시작이 안전 차단될 수 있다. 재시도 보완은 상시 성공 보장이 아니다. 외부 NTP는 비인증 UDP이며 이번 작업은 기존 신뢰 모델을 확장하지 않았다. 실제 브라우저 외관/클릭, 자연 신규 신호 후30/60분 평가, 장시간·절전·재부팅·24시간 무인 안정성은 이번 검증 범위가 아니다. Windows 종료·자동 재시작·자동매매 기능은 실행/추가하지 않았다.
