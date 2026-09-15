# 코인 급등 분석 프로젝트

과거 데이터로 급등 사례의 특징을 찾고 백테스트로 검증합니다. 실시간 검사는 검증 이후로 보류 중입니다.

## 알트코인 급등 사전 신호 연구

최근 30일 원화 알트코인의 급등 사례를 찾고, 급등 전 특징을 비급등 대조군과 비교합니다. 별도 모듈 `altcoin_research`는 과거 봉만으로 생성한 초기 신호 가설의 적중률·오탐 수·급등 포착률도 평가합니다.

```powershell
# 현재 상장된 업비트 원화 종목 중 제외 목록을 뺀 종목 수집
# 종목 수에 따라 오래 걸립니다. 기존 BTC·ETH DB와 별도로 저장합니다.
python -m coin_analysis.altcoin_research download --days 30

# 1시간 내 +10% 급등 연구
python -m coin_analysis.altcoin_research analyze

# 6시간 내 +20% 급등을 별도 보고서로 비교
python -m coin_analysis.altcoin_research analyze --horizon 360 --threshold 20 --output reports/altcoin_6h
```

기본 제외 목록은 `BTC,ETH,XRP,SOL,DOGE,ADA,TRX,BNB,USDT,USDC`이며 `--exclude`로 교체할 수 있습니다. 이 목록은 시가총액 순위에 따른 소형주 분류가 아닙니다. `--markets SYMBOL1,SYMBOL2`로 수집·분석 종목을 직접 지정할 수도 있습니다. 다운로드 재개 시 같은 기간을 유지하려면 `--end 2026-09-15T00:00:00Z`처럼 종료 시각을 고정하세요.

입력 DB는 `data/altcoin_market.db`, 기본 결과는 `reports/altcoin_research.md`와 `.json`입니다. 분석 기간은 DB 내 대상 종목의 마지막 봉을 기준으로 합니다. 기존 보고서는 그대로 보존됩니다.

초기 신호 가설은 조용한 가격 움직임 속 거래대금 증가, 반복 거래대금 급증, 좁은 가격 범위와 거래대금 증가입니다. 아직 학습·검증된 매매 조건이 아닙니다. JSON에는 사건별 이전 특징, 전체 알림, 신호 뒤 최대 상승과 고가 봉 이후 하락을 기록합니다.

선행 시간은 **목표 상승률 도달 봉 시작까지의 시간**이며, 실제 상승 시작 전 예측 성공을 의미하지 않습니다. 신호는 완성된 과거 1분봉만 사용합니다. 현재 단계는 오프라인 연구이며 실시간 알림 연결은 포함하지 않습니다.

업비트는 체결이 없는 분의 캔들을 생성하지 않습니다([공식 문서](https://docs.upbit.com/kr/reference/list-candles-minutes)). 이 연구는 공백을 채우지 않으므로 거래가 드문 종목의 사건을 놓칠 수 있습니다. 보고서의 누락 분·평가 가능 기준점 수와 함께 결과를 읽어야 합니다. 현재 상장 목록만으로는 상장폐지 종목도 분석할 수 없습니다.

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

아래 명령은 현재 저장소의 프로젝트 루트에서 실행합니다. 오프라인 분석과 테스트에는 Python 표준 라이브러리만 필요합니다.

### 최초 실행: 과거 DB 준비

새로 복제한 저장소에는 DB가 포함되어 있지 않습니다. 기존 `historical_market.db`를 `data/`에 복사하거나, 아래 명령으로 최근 30일의 BTC·ETH 1분봉을 다운로드합니다. 다운로드에는 네트워크 연결이 필요하며 시간이 걸릴 수 있습니다. `data/` 폴더는 자동 생성됩니다.

```powershell
python -m coin_analysis.historical_breakout_lab_v1 download --markets BTC,ETH --days 30
```

BTC·ETH는 초기 실행 예시이며, 기존 보고서의 분석 종목·기간과 다릅니다.
다른 위치에 DB가 있다면 분석 명령에 `--db "C:\경로\historical_market.db"`를 지정합니다.
`unable to open database file` 오류가 나면 DB 파일의 존재 여부와 경로를 먼저 확인하세요.

### 분석 및 테스트

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
