# 코인 급등 분석 프로젝트

과거 데이터로 급등 사례의 특징을 찾고 백테스트로 검증합니다. 실시간 검사는 검증 이후로 보류 중입니다.

## 폴더 구조

```text
Coin_api/
  coin_analysis/  분석 코드와 데이터 다운로드 도구
  tests/          자동 테스트
  data/           과거 시세와 실시간 관측 DB
  reports/        분석 결과 보고서와 상세 JSON
  docs/           상세 사용 설명서
  archive/        사용을 중단한 V15 원본
  README.md
  requirements.txt
```

`coin_analysis/historical_breakout_lab_v1.py`는 기존 다운로드 도구와 봉 자료형을 제공하므로 분석 코드에 함께 보관합니다. 기존 V1 전략도 파일 안에 유지되어 있습니다.

## 실행

아래 명령은 프로젝트 루트인 `C:\dev\Coin_api`에서 실행합니다. 오프라인 분석과 테스트에는 Python 표준 라이브러리만 필요합니다.

```powershell
# 실제 급등 사건의 특징 비교
python -m coin_analysis.surge_pattern_lab

# V16의 1분봉 근사 백테스트
python -m coin_analysis.backtest_v16

# 전체 테스트
python -m unittest discover -s tests -v
```

기본 입력은 `data/historical_market.db`, 결과 저장 위치는 `reports/`입니다. 과거 DB를 읽기 전용으로 분석하며, 분석을 다시 실행하면 같은 이름의 결과 보고서를 갱신합니다. `--db`와 `--output`으로 별도 경로를 지정할 수 있습니다.

코드는 파일을 직접 실행하는 대신 `python -m coin_analysis.모듈명` 형태로 실행합니다. 기존 루트의 `.py` 실행 명령은 위 명령으로 변경되었습니다.

## 문서와 결과

- [상세 사용 설명서](docs/README_v16.md)
- [급등 패턴 분석 보고서](reports/surge_pattern_result.md)
- [백테스트 결과 보고서](reports/backtest_v16_result.md)

DB 파일은 용량과 실행 중 변경을 고려해 Git 추적에서 제외했습니다. 기존 데이터는 `data/`에 그대로 보관하며, 저장소를 새로 복제한 경우 별도로 준비해야 합니다. `data/scanner_v16_smoke.db`는 연결 확인용 DB입니다.

실시간 검사를 재개할 때만 `python -m pip install -r requirements.txt`로 추가 의존성을 설치합니다. 실행 명령과 한계는 상세 사용 설명서를 참고하세요.
