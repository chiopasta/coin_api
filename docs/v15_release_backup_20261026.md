# V15 DB 비공개 Release 백업·PC 이전 검증

## 결과

2026-10-26 23:43:30 KST에 기존 V15를 종료하지 않고 SQLite Online Backup API로 두 DB의 스냅샷을 만들었다. 무결성 검사와 압축 후, 사용자가 생성에 동의한 **비공개** `chiopasta/coin-api-v15-backups`에 새 Release를 게시했다. 업로드한 파일을 다시 내려받아 ZIP CRC·SHA-256·DB 무결성·스키마·건수를 확인했다. 게시 후 다운로드 경로도 별도로 검증했다.

- [비공개 백업 Release](https://github.com/chiopasta/coin-api-v15-backups/releases/tag/v15-backup-20261026T144330Z-a5bdb121)
- 태그: `v15-backup-20261026T144330Z-a5bdb121` — UTC 시각과 무작위 접미사.
- ZIP: `v15-backup.zip`, 1,301,537 bytes.
- ZIP SHA-256: `bff4e5d37f94561cf249487a0906ea16cb29c2a6b636c9cf5e910ac4a2d14da3`.
- 원격 assets는 ZIP과 `v15-backup.zip.sha256` 두 개다. Manifest는 ZIP 내부에 있다.
- 현재 코드 원격 `chiopasta/coin_api`는 **공개**다. DB를 그 저장소나 그 Release에 올리지 않았다. 비공개 여부를 API로 확인하지 못하면 업로드를 차단한다.

스캐너·분석 엔진·탐지 점수·규칙·UI·기존 DB·연구 자료는 변경하지 않았다. 자동 업로드·스케줄·삭제·자동 병합 기능은 없다. 사용자 V15에 종료/재시작/시그널을 보내지 않았다. 백업 이후 생기는 자료는 이번 스냅샷에 포함되지 않으며 새 수동 백업이 필요하다.

## 1. 실제 파일과 데이터 범위

| 대상 | 실제 원본 | 백업 이름 | 스냅샷 내용 |
|---|---|---|---|
| 현재 수집 증가 DB | `C:\dev\coin_api-1\archive\crypto_scanner.db` | `live_archive.db` | signals23, 가격이력740, paper8, PRE-PUMP0 |
| 과거 분석 DB | `C:\dev\Coin_api\crypto_scanner.db` | `legacy_standalone.db` | signals1761, 가격이력43950, paper305, PRE-PUMP76 |

`archive/scanner_v15.py:58`의 DB_FILE은 CWD 상대 `crypto_scanner.db`다. `C:\dev\Coin_api\db_checker_v1.py:11`도 같은 상대 이름을 사용한다. `db_analyzer_v7.py:22`는 명시 인자가 있으면 그 DB, 없으면 CWD의 crypto DB를 선택한다. 따라서 실행 파일명만으로 실제 DB 위치를 결정하지 않고 절대 경로 두 개를 명시했다. 실행 중 프로세스의 상대 command line만으로 CWD나 시작 당시 소스 바이트까지 입증할 수 없다는 기존 한계는 유지한다. archive DB는 실제 기록 증가가 확인된 현재 수집 후보다.

가격 이력·후속 결과·PRE-PUMP 추적·기존 paper 기록은 위 DB 내부 테이블에 있다. 이 세 V15 계열 프로그램에서 별도 CSV/JSON 가격 파일을 필수 입력으로 참조하는 경로는 발견하지 못했다. Python 원본은 실행하지 않고 조사했다. 인증 설정, `.env`, Git credential, 실행 로그, 사용자 홈, 소스 디렉터리 전체는 ZIP에 넣지 않았다.

V4/V5.2 DB, discovery/validation, 시장 연구 분봉 DB는 이 백업 범위 밖이며 원래 위치에 보존했다. 기존 `data/backups/.../legacy.db`는 이전 조사에서 standalone DB와 논리적으로 같았던 보존본으로 이번 ZIP에 중복 수록하지 않았다. 이번 작업은 기존 모든 연구 DB를 백업했다는 의미가 아니다.

현재/과거 DB에 low_heat_watch 유무 등 스키마 차이가 있어 실제 교차 비교는 **QUARANTINE_SCHEMA_MISMATCH**였다. 과거 1,761개 모두를 현재 V15 파일이 생성했다고 소급 귀속하지 않는다.

## 2. 스냅샷·Manifest·보호 방식

도구는 [v15_transfer.py](../coin_analysis/v15_transfer.py), GitHub 전송은 [v15_release.py](../coin_analysis/v15_release.py)다. 기존 scanner/analyzer를 import하지 않는다.

원본은 `mode=ro`, `query_only=ON`, busy timeout 0.05초로 연다. `Connection.backup`을 64페이지 단위로 호출하고, 잠금/진행 재시도 시 0.01초 대기, 전체 진행 예산 20초를 둔다. 초과하면 실패하며 불완전 목적지는 남기되 ZIP으로 만들지 않는다. 원본에 journal_mode 변경·checkpoint·schema 변경·전체 integrity scan·장기 BEGIN을 수행하지 않는다. Online Backup은 페이지 단계마다 짧은 읽기 잠금을 사용할 수 있으므로 I/O 영향이 수학적으로 0이라고 주장하지 않는다. 실제 백업 API 소요는 live 약0.086초, standalone 약0.034초였고 두 프로세스 생존과 이후 수집 증가를 확인했다.

무결성·테이블 건수·foreign_key_check는 **복사된 DB에서만** 검사했다. 두 DB 모두 integrity_check=ok, FK 위반0이다. DB별 스냅샷은 각각 일관적이지만 서로 다른 두 DB 사이의 같은 시점 transaction을 보장하지 않는다. 원본을 잠그고 동시 스냅샷을 강제하지 않는다.

Manifest 항목:

- 포맷 버전, 무작위 backup_id, UTC 생성 시각 및 DB별 시작/완료 시각.
- 원천 PC 식별자: 무작위 UUID. hostname·계정명·MAC·MachineGuid 대신 로컬 identity registry에 보관하며 재사용한다.
- 원천 DB 식별자: 로컬 등록 UUID. 기존 기록에 없던 전역 신호 ID를 소급 생성했다는 뜻이 아니다.
- 파일명/원래 파일명, 크기, 파일 SHA-256, SQLite user_version/application_id, 스키마 SHA-256·정의, 테이블별 건수, 무결성/FK 검사 결과.
- 기존 V15는 명시적인 application migration 버전을 기록하지 않아 user_version=0이다. 이를 ‘V15 스키마 버전15’로 꾸미지 않고 스키마 지문으로 구분한다.

ZIP 허용 항목은 `manifest.json`과 명시한 DB 파일뿐이다. 이름·항목 수·비압축 크기를 제한하고 경로 이탈·중복 이름·symlink·암호화 ZIP을 거부한다. DB는 알려진 V15 계열 테이블만 허용하고 trigger/view/virtual table 등 지원하지 않는 구조는 차단한다. 대표 GitHub token/개인키 패턴도 패키징 전에 차단한다. 패턴 검사만으로 임의 데이터에 숨겨진 모든 종류의 비밀정보 부재를 증명할 수는 없다. 인증 자체는 OS/Git credential helper 또는 환경에서 메모리로만 읽으며 DB·ZIP·Manifest·로그에 기록하지 않는다.

`data/v15_transfer/source_identity.json`은 로컬 전용이다. 처음 등록한 전체 원본 집합으로 반복 백업하면 같은 PC/DB ID를 유지한다. 등록하지 않은 새 DB를 추가할 경우 도구가 기존 registry 변경을 거부한다. 임의 새 registry로 기존 출처가 이어진다고 가정하지 말고 별도 출처 등록 검토가 필요하다. 이 registry는 경로의 해시를 쓰며 원본 절대 경로를 ZIP Manifest에 수록하지 않는다.

## 3. Release 업로드 검증

GitHub API에서 코드 저장소가 public임을 확인한 뒤 기존 비공개 저장소 후보를 조사했다. 사용자가 새 비공개 백업 저장소 생성에 동의하여 해당 저장소를 생성하고 `private=true`, `visibility=private`, push 권한을 확인했다. 기존 저장소의 공개 범위는 변경하지 않았다.

업로드는 새 태그/Release가 모두 없을 때만 수행한다. 새 draft를 만들고 두 asset 업로드 → GitHub asset digest/크기 대조 → 실제 다운로드 → CRC/ZIP SHA/DB SHA/integrity/schema/count 검증을 통과한 뒤 해당 새 Release를 게시한다. 실패 시 draft/부분 파일을 그대로 남기며 기존 태그·asset 대체, 삭제·자동 재시도를 하지 않는다. 기존 Release 태그에 대한 차단을 실제 읽기 요청으로 확인했다. 태그 목록을 정리하거나 과거 Release를 변경하지 않았다.

다운로드는 인증된 asset API를 쓰고 GitHub의 HTTPS asset redirect를 처리한다. 다른 호스트로 redirect될 때 Authorization을 제거하며 허용되지 않은 호스트는 차단한다. 실패 로그에는 토큰·헤더·응답 본문·서명된 다운로드 URL을 출력하지 않는다. API 사용 근거: [GitHub Releases](https://docs.github.com/en/rest/releases/releases), [Release assets 다운로드/업로드](https://docs.github.com/en/rest/releases/assets).

이 도구의 덮어쓰기 금지는 GitHub 관리자까지 수정할 수 없게 하는 서버 측 immutable 보증과는 다르다. 원격 checksum도 변경될 수 있으므로 다른 PC에서는 아래처럼 독립적으로 보관한 이번 ZIP SHA를 고정하는 방법을 권장한다. SHA/CRC는 무결성 검증이며 별도의 전자서명은 구현하지 않았다. 비공개 저장소 접근 권한은 각 PC에서 별도로 필요하다.

## 4. 다른 PC에서 다운로드·검증

현재 Git 저장소의 이번 commit을 내려받은 뒤 Python 표준 라이브러리와 Git credential manager 인증을 사용한다. `gh` 설치는 필요 없다. 토큰을 명령행 인자로 전달하거나 문서/로그에 붙이지 않는다.

```powershell
python -m coin_analysis.v15_release --repo chiopasta/coin-api-v15-backups download --tag v15-backup-20261026T144330Z-a5bdb121 --sha256 bff4e5d37f94561cf249487a0906ea16cb29c2a6b636c9cf5e910ac4a2d14da3 --output data/v15_transfer/pc2-first-download
```

출력 폴더는 **존재하지 않아야 한다**. 성공 시 ZIP·checksum과 `restored/manifest.json`, `restored/live_archive.db`, `restored/legacy_standalone.db`, `restored/verification.json`이 생성된다. 성공 상태는 `VERIFIED_QUARANTINE`이며 운영 전환/병합 완료가 아니다. 검사 실패 시 해당 폴더는 격리된 채 남고 verification 성공 파일은 만들지 않는다. 같은 폴더를 재사용하거나 기존 crypto DB로 추출하지 않는다.

이미 ZIP을 별도 전달받았다면:

```powershell
python -m coin_analysis.v15_transfer restore --zip D:/transfer/v15-backup.zip --sha256 bff4e5d37f94561cf249487a0906ea16cb29c2a6b636c9cf5e910ac4a2d14da3 --output data/v15_transfer/pc2-offline-restore
```

실제 다른 물리 PC는 이번에 이용하지 못했다. 동일 PC의 완전히 새 폴더에 **원격에서 다시 다운로드하는 동일 명령 경로**를 실제 실행해 검증했다. 다른 PC의 인증·파일시스템·스캐너 실행은 미검증이다. 도구는 내려받은 DB를 scanner의 CWD나 기본 DB로 자동 연결하지 않는다. V15는 CWD에 따라 DB를 선택하고 시작 시 schema 업그레이드도 할 수 있으므로 검증 DB를 바로 운영 경로에 복사하지 않는다.

## 5. 원본을 보존하는 수동 백업

이번 로컬 원본 스냅샷은 `data/v15_transfer/20261026T144330Z-a5bdb121/`에 있다. 추가 수동 백업 예:

```powershell
python -m coin_analysis.v15_transfer backup --source live_archive=C:/dev/coin_api-1/archive/crypto_scanner.db --source legacy_standalone=C:/dev/Coin_api/crypto_scanner.db --registry data/v15_transfer/source_identity.json --output data/v15_transfer/NEW-UNIQUE-BACKUP
```

이번과 같은 두 원본을 명시하고 매번 새 output을 선택한다. 스냅샷 후 새 비공개 Release를 원할 때만 명시적으로 실행한다:

```powershell
python -m coin_analysis.v15_release --repo chiopasta/coin-api-v15-backups preflight
python -m coin_analysis.v15_release --repo chiopasta/coin-api-v15-backups upload --zip data/v15_transfer/NEW-UNIQUE-BACKUP/v15-backup.zip --tag v15-backup-NEW-UNIQUE-TAG --verification-output data/v15_transfer/NEW-UNIQUE-REMOTE-CHECK
```

기존 태그·Release·asset 덮어쓰기는 지원하지 않는다. 네트워크가 중단돼 draft가 남으면 자동 제거/재사용하지 않고 사용자가 상태를 검토한다. 저장 공간 정리·자동 주기 실행·데이터 삭제 명령도 없다.

## 6. 비교·중복·충돌 처리 설계

실제 복원본 두 개와 스냅샷의 테이블별 키/행을 비교해 전부 동일함을 확인했다. 서로 다른 원본 두 개의 비교는 스키마 차이로 격리되었다. 비교 명령은 **이미 만들어 둔 정적 스냅샷**에만 사용한다. active DB에 immutable 조회/전체 비교를 하지 않는다.

```powershell
python -m coin_analysis.v15_transfer compare --local-snapshot data/v15_transfer/LOCAL-SNAPSHOT/live_archive.db --incoming-snapshot data/v15_transfer/pc2-first-download/restored/live_archive.db
```

비교 출력은 동일 키·상이 값·한쪽에만 있는 키 수이며 자동 병합을 승인하지 않는다. 특히 `signals.id`, `prepump_events.id`, `pullback_paper_trades.id`는 DB-local 정수다. 서로 다른 PC가 id=1을 생성해도 같은 신호가 아니다. 시각/거래소/종목/점수가 같다는 자연 키만으로 동일성도 보장되지 않는다. `signal_price_history`의 signal_id/minute는 부모 DB 출처까지 포함해야 유일하다.

후속 병합이 명시적으로 필요해질 경우의 설계는 다음과 같다. 이번에는 병합 코드를 만들거나 원본에 적용하지 않았다.

1. 두 원본을 각각 Online Backup으로 보존하고, 검증한 복사본·Manifest만 비교한다. PC/DB lineage가 불명하거나 스키마 지문이 다르면 전체 격리한다.
2. 동일 출처로 확인된 기록은 `(source_database_id, table, local primary key)`를 가져오기 식별자로 별도 보존한다. 같은 키·같은 typed 값은 중복 후보이나 시간·버전·부모 연결까지 확인한다. 같은 키의 다른 값은 추적 갱신일 수도 ID 충돌일 수도 있어 자동 last-write-wins/IGNORE/REPLACE를 금지한다.
3. 서로 다른 출처는 원래 정수 ID를 공유하지 않는다. 별도 목적 DB와 provenance/import ledger를 설계하고 signals/prepump/paper의 부모 ID 매핑 및 history/watch/tracking/previous_event_id의 참조를 함께 검토해야 한다. 기존 `sqlite_sequence` 숫자를 복사해 합치지 않는다.
4. 명확한 출처·참조 관계·허용할 추적 갱신 정책을 먼저 확정한 경우에만 승인된 새 목적 DB에서 transaction으로 수행하고 integrity/FK/건수/중복 재입력 무변화 검증을 해야 한다. 성공해도 두 원본과 Release는 그대로 유지한다.

따라서 현재 안전한 이전 방법은 **출처별 DB 분리 보관·읽기 전용 분석**이다. 스키마 차이·충돌·출처 불명의 자동 병합은 전부 보류한다. `compare` 결과가 동일해도 운영 DB 덮어쓰기 허가를 뜻하지 않는다.

## 7. 검증 증거와 한계

- [백업 건수·스키마 지문·시간](../reports/v15_release_backup_20261026/backup_summary.json)
- [원격 업로드·다운로드 영수증](../reports/v15_release_backup_20261026/release_verification.json)
- [복원 행 대조·교차 원본 격리·게시 후 다운로드](../reports/v15_release_backup_20261026/comparison_and_download.json)
- [테스트 로그](../reports/v15_release_backup_20261026/tests.log): 신규12 + 기존 관련59 = **71개 PASS**. 동시 WAL 쓰기 중 transaction 일관성, busy 예산, 잘못된 hash/CRC/manifest, 경로 이탈·중복 ZIP·원본 덮어쓰기 차단, 스키마/키 충돌, public 업로드 차단, 기존 Release 거부, 인증 redirect 보호를 포함한다. 초기 신규 테스트의 예외 기대값/압축 오류 처리 두 건을 보완한 뒤 통과했다. 실제 exchange API/스캐너 시작은 없다.
- [보존·프로세스·수집 지속 확인](../reports/v15_release_backup_20261026/preservation_after.json): 기존 정적 DB/엔진/UI/연구 결과 지문, PID+생성 시각, 백업 이후 가격 이력 증가를 확인한다. active DB는 정상 수집으로 계속 바뀌므로 작업 전후 파일 hash 동일을 주장하지 않는다.

Git에는 백업 도구·테스트·문서와 토큰/원시 신호 행/PC UUID를 제외한 검증 메타데이터만 포함한다. `archive/*.db*`, `data/v15_transfer/`는 ignore 처리했으며 Release ZIP·스냅샷·identity registry를 커밋하지 않는다. 기존 미커밋 진단/설계 자료는 이번 commit과 분리해 그대로 남긴다. 실제 다른 PC·장기 네트워크 단절·대용량 GB급 DB는 미검증이며 이번 약1.3MB ZIP과 두 원본에 대한 검증 결과를 일반화하지 않는다.
