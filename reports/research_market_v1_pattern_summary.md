# 53건의 급등 전에 무엇이 달랐나?

**요약: 급등군은 이미 가격 움직임이 컸고, 직전 고점보다 더 내려와 있었습니다. 거래대금 증가 → 모멘텀 강화 → 돌파라는 일정한 순서는 보이지 않았습니다.**

A 53건은 9개 시장에서 발생했습니다. FLOCK 25건(47.17%), 상위 3개 79.25%로 쏠려 있습니다.
아래는 결측이 양쪽 모두 없는 matched pair의 중앙값이며, 시점마다 유효 pair 집합이 다릅니다.

### 급등 120분 전

이미 고저폭이 더 컸습니다. 알트 대비 상대강도는 급등군 쪽이 높았지만 이후까지 같은 방향이 유지되지는 않았습니다.

| 특징 | 급등군 중앙값 | control 중앙값 | 차이 | 유효 pair |
|---|---|---|---|---|
| 최근 30분 고저폭(%) | 3.956 | 0.5679 | 3.388 | 28 |
| 직전 고점까지 거리(%) | 2.71 | 0.3669 | 2.343 | 25 |
| 알트 대비 60분 상대강도(%p) | 0.6536 | -0.0903 | 0.7439 | 45 |
| 거래대금 배율(배) | 0.779 | 0.9325 | -0.1534 | 25 |
### 급등 60분 전

높은 고저폭은 유지됐지만 상대강도와 MA 기울기는 오히려 약했습니다. 상승 준비 신호가 순서대로 강해졌다는 모습은 아닙니다.

| 특징 | 급등군 중앙값 | control 중앙값 | 차이 | 유효 pair |
|---|---|---|---|---|
| 최근 30분 고저폭(%) | 4.636 | 0.5054 | 4.131 | 28 |
| 직전 고점까지 거리(%) | 3.272 | 0.368 | 2.904 | 21 |
| 알트 대비 60분 상대강도(%p) | -0.5959 | 0.1208 | -0.7168 | 47 |
| 거래대금 배율(배) | 0.7678 | 0.8745 | -0.1067 | 21 |
### 급등 30분 전

MA5 > MA20 발생률은 일시적으로 높았지만, 60분 수익률은 control보다 낮았습니다. 거래대금 2배 조건도 우세하지 않았습니다.

| 특징 | 급등군 중앙값 | control 중앙값 | 차이 | 유효 pair |
|---|---|---|---|---|
| 최근 30분 고저폭(%) | 3.929 | 0.4724 | 3.456 | 31 |
| 직전 고점까지 거리(%) | 3.171 | 0.3521 | 2.818 | 24 |
| 알트 대비 60분 상대강도(%p) | -0.4226 | -0.07486 | -0.3477 | 49 |
| 거래대금 배율(배) | 0.9181 | 0.9963 | -0.07814 | 24 |
### 급등 15분 전

고저폭과 고점에서 떨어진 정도가 컸습니다. 거래대금 배율 중앙값은 비슷하며, 단기 MA 우위는 다시 약해졌습니다.

| 특징 | 급등군 중앙값 | control 중앙값 | 차이 | 유효 pair |
|---|---|---|---|---|
| 최근 30분 고저폭(%) | 4.881 | 0.6479 | 4.233 | 31 |
| 직전 고점까지 거리(%) | 3.81 | 0.3239 | 3.486 | 25 |
| 알트 대비 60분 상대강도(%p) | -0.3035 | -0.1475 | -0.1559 | 47 |
| 거래대금 배율(배) | 0.6501 | 0.6233 | 0.02685 | 25 |
### 급등 5분 전

기준 저점에 가까워지며 가격 수익률과 MA 기울기가 더 약했습니다. 고점 돌파는 양쪽 모두 관측되지 않았고 거래대금 배율 중앙값 차이도 작았습니다.

| 특징 | 급등군 중앙값 | control 중앙값 | 차이 | 유효 pair |
|---|---|---|---|---|
| 최근 30분 고저폭(%) | 4.263 | 0.6296 | 3.633 | 33 |
| 직전 고점까지 거리(%) | 3.909 | 0.3677 | 3.542 | 24 |
| 알트 대비 60분 상대강도(%p) | -0.596 | -0.03685 | -0.5592 | 47 |
| 거래대금 배율(배) | 0.5403 | 0.5012 | 0.03912 | 23 |

### 현재 가장 유망해 보이는 특징

이는 매수 신호가 아니라 추가 확인할 기술적 차이 후보입니다.

| 특징 | 시점 | event | control | 차이 | 유효 E/C | paired N | 방향 |
|---|---|---|---|---|---|---|---|
| 최근 30분 고저폭 | 15 | 4.881 | 0.6479 | 4.233 | 40/34 | 31 | 더 큼 |
| 직전 60분 고점까지 거리 | 5 | 3.909 | 0.3677 | 3.542 | 35/30 | 24 | 고점보다 더 아래 |
| MA20의 5분 기울기 | 5 | -0.3269 | 0.0009381 | -0.3278 | 46/35 | 34 | 더 하락 |

### 별 차이가 없었던 특징

- 거래대금 배율 중앙값: 일관된 증가 우위 없음
- 고점 돌파 발생률: 낮거나 동일
- 알트/BTC 상대강도: 120분 전 우위가 이후 지속되지 않음

### 아직 판단할 수 없는 특징

- 여러 시장으로 일반화 가능한가
- 시장당 첫 사건 9개로도 재현되는가
- B 15건에서 같은 패턴인가
- 실시간으로 관측 가능한 예측 신호인가

### 특정 사건·시장 의존성

시장당 최초 사건 1개만 남기면 A는 9쌍입니다. 고저폭 차이는 5개 시점 모두 같은 방향이지만 유효 pair가 5~7개라 INSUFFICIENT_SAMPLE입니다.
FLOCK을 전부 제외하면 28쌍입니다. 5분 전 고저폭 차이는 +4.14%p(유효 20쌍)로 남습니다. 한 시장만의 현상은 아니지만 시장 중립적 전조임을 입증하지는 않습니다.
5분 전 거래대금 배율은 평균 1.40배 vs 0.69배지만 중앙값은 0.54배 vs 0.50배입니다. 평균만 보고 전반적 거래대금 폭증이라고 해석하면 안 됩니다.
큰 고저폭이 이미 120분 전부터 관측된 점은 종목의 평소 변동성 차이일 수도 있습니다. t0는 사후 저점이므로 직전 하락 역시 기준점 선정의 영향을 받을 수 있습니다.

### B는 참고용

15쌍, 5개 시장뿐이며 모든 비교가 INSUFFICIENT_SAMPLE입니다. 아래 상세 표의 수치는 참고용이며 A와 같은 결론이라고 단정하지 않습니다.

### 최종 답변

WEAK — 더 큰 고저폭과 고점 대비 하락은 반복되지만, 시장 쏠림과 사후 저점 정의의 영향 때문에 일반적인 급등 전조로 확정하기 어렵습니다.

---

# 상세 수치: 기존 matched snapshots 비교

A 53쌍을 중심으로 기존 snapshot만 비교한다. B 15쌍은 INSUFFICIENT_SAMPLE 참고자료다.
차이는 모두 event-control. 수익률/고저폭/거리/기울기는 % 단위이므로 차이는 %p, 거래대금은 KRW, 배율은 배수다.
유효 event/control 수는 각 군별 결측 제외 수다. 해석은 양쪽 모두 유효한 matched pair의 중앙값을 우선한다.
두 군 중앙값의 차이와 쌍별 차이의 중앙값은 다르므로 둘 다 JSON에 저장했다. False/0은 유효값이다.
단위가 다른 연속형 값을 하나의 점수로 정렬하지 않는다. 기존 boolean 조건은 발생률 차이(%p)로만 정렬한다.
min-valid는 paired count까지 20 이상이어야 한다. 통계적 유의성 검정/예측성 검증을 뜻하지 않는다.

## A: 53쌍

발생 시장 9개. 최대 시장 비중 47.17%, 상위3개 79.25%.

| market | events |
|---|---|
| KRW-FLOCK | 25 |
| KRW-SKR | 12 |
| KRW-ICX | 5 |
| KRW-CPOOL | 3 |
| KRW-0G | 2 |
| KRW-ONG | 2 |
| KRW-LA | 2 |
| KRW-CHIP | 1 |
| KRW-ZORA | 1 |

### t0 -120분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 50/51 | 48 | 0 | 0 | 0 | 0.3345 | 0.05201 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 49/50 | 46 | 0 | -0.02925 | 0.02925 | 0.5443 | -0.09049 | 0.06046 | -0.06569 | 0.1262 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 47/51 | 46 | -0.1815 | 0 | -0.1815 | 0.5475 | -0.01045 | 0.09376 | -0.02592 | 0.1197 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 47/51 | 45 | 0.2268 | -0.05855 | 0.2853 | 0.7633 | 0.006427 | 0.4695 | -0.1036 | 0.5731 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 46/46 | 42 | 9.111e+07 | 1.256e+08 | -3.452e+07 | 2.655e+08 | 2.591e+08 | 9.217e+07 | 1.411e+08 | -4.894e+07 | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 32/31 | 25 | 1.725e+08 | 1.861e+08 | -1.357e+07 | 2.992e+08 | 3.267e+08 | 1.906e+08 | 2.023e+08 | -1.171e+07 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 32/31 | 25 | 0.7673 | 0.9546 | -0.1873 | 1.05 | 1.109 | 0.779 | 0.9325 | -0.1534 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 42/42 | 38 | 5.653 | -10.19 | 15.84 | 59.64 | 61.26 | 5.653 | -10.19 | 15.84 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 39/38 | 32 | 1.438 | 0.9003 | 0.5376 | 2.952 | 6.476 | 1.294 | 0.8449 | 0.4489 | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 46/46 | 42 | 74.9 | 1906 | -1831 | 76.52 | 3.868e+05 | 73.32 | 1911 | -1837 | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 39/37 | 32 | 74.91 | 1915 | -1840 | 76.46 | 4.769e+05 | 73.54 | 1922 | -1848 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 39/37 | 32 | 0.9998 | 0.9995 | 0.0002607 | 1.002 | 0.9992 | 0.9994 | 0.9995 | -0.0001302 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 36/35 | 29 | 0.05735 | -0.01295 | 0.07031 | 0.08423 | -0.01332 | -0.02472 | -0.008108 | -0.01662 | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 34/35 | 28 | 3.956 | 0.4958 | 3.46 | 5.108 | 0.8043 | 3.956 | 0.5679 | 3.388 | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 32/31 | 25 | -0.5319 | -0.105 | -0.4269 | 17.07 | 16.82 | 1.423 | 0 | 1.423 | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 32/31 | 25 | 2.818 | 0.3669 | 2.452 | 3.164 | 0.6032 | 2.71 | 0.3669 | 2.343 | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 47/51 | 45 | 0.6203 | -0.07097 | 0.6913 | 0.8306 | 0.03232 | 0.6536 | -0.0903 | 0.7439 | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 47/51 | 45 | 0.5108 | -0.0349 | 0.5457 | 0.8479 | 0.02622 | 0.6027 | -0.04033 | 0.643 | SUFFICIENT_FOR_DESCRIPTION |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 50/51 | 48 | 47.92 | 43.75 | 4.167 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 49/50 | 46 | 50 | 45.65 | 4.348 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 47/51 | 46 | 50 | 39.13 | 10.87 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 47/51 | 45 | 55.56 | 40 | 15.56 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 32/31 | 25 | 12 | 8 | 4 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 42/42 | 38 | 50 | 39.47 | 10.53 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 39/38 | 32 | 59.38 | 43.75 | 15.62 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 39/37 | 32 | 40.62 | 40.62 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 36/35 | 29 | 44.83 | 44.83 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 32/31 | 25 | 52 | 48 | 4 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 32/31 | 25 | 0 | 4 | -4 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 47/51 | 45 | 57.78 | 40 | 17.78 | SUFFICIENT_FOR_DESCRIPTION |

### t0 -60분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 50/52 | 49 | 0 | 0 | 0 | 0.3077 | 0.1893 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 51/51 | 49 | -0.3077 | 0 | -0.3077 | 0.2258 | 0.1162 | -0.3077 | 0 | -0.3077 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 50/52 | 49 | -0.2021 | 0.01495 | -0.217 | 0.4666 | 0.1237 | -0.1855 | 0 | -0.1855 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 50/50 | 47 | -0.3396 | 0.149 | -0.4886 | 0.3087 | 0.2984 | -0.3436 | 0.1522 | -0.4958 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 51/47 | 45 | 7.201e+07 | 1.353e+08 | -6.325e+07 | 2.742e+08 | 2.479e+08 | 7.201e+07 | 1.353e+08 | -6.325e+07 | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 32/30 | 23 | 1.828e+08 | 2.245e+08 | -4.173e+07 | 3.372e+08 | 2.925e+08 | 2.003e+08 | 2.037e+08 | -3.478e+06 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 31/29 | 21 | 0.7855 | 0.8443 | -0.05874 | 1.178 | 1.175 | 0.7678 | 0.8745 | -0.1067 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 46/45 | 39 | -5.238 | -20.35 | 15.11 | 51.82 | 39.58 | -4.584 | -16.13 | 11.54 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 41/41 | 33 | 0.9639 | 0.6441 | 0.3198 | 2.02 | 2.261 | 0.9267 | 0.678 | 0.2487 | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 51/47 | 45 | 71.74 | 1883 | -1811 | 73.01 | 3.757e+05 | 54.62 | 1863 | -1808 | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 40/40 | 32 | 72.28 | 1902 | -1829 | 71.23 | 4.411e+05 | 72.28 | 1898 | -1826 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 40/40 | 32 | 0.997 | 1 | -0.003152 | 0.9996 | 1.001 | 0.997 | 0.9999 | -0.002889 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 34/39 | 29 | -0.2434 | 0.008052 | -0.2515 | -0.1285 | 0.007516 | -0.2654 | 0.008052 | -0.2734 | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 33/38 | 28 | 4.412 | 0.578 | 3.834 | 5.907 | 1.157 | 4.636 | 0.5054 | 4.131 | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 31/30 | 21 | 16.56 | -8.353 | 24.92 | 34.83 | 11.24 | 8.396 | -6.846 | 15.24 | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 31/30 | 21 | 3.272 | 0.4208 | 2.851 | 4.391 | 0.6033 | 3.272 | 0.368 | 2.904 | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 50/50 | 47 | -0.4357 | 0.1098 | -0.5455 | 0.321 | 0.3098 | -0.5959 | 0.1208 | -0.7168 | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 50/50 | 47 | -0.2789 | 0.04857 | -0.3275 | 0.3542 | 0.3425 | -0.3204 | 0.04809 | -0.3685 | SUFFICIENT_FOR_DESCRIPTION |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 50/52 | 49 | 48.98 | 46.94 | 2.041 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 51/51 | 49 | 38.78 | 48.98 | -10.2 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 50/52 | 49 | 44.9 | 46.94 | -2.041 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 50/50 | 47 | 44.68 | 61.7 | -17.02 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 31/29 | 21 | 19.05 | 9.524 | 9.524 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 46/45 | 39 | 46.15 | 43.59 | 2.564 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 41/41 | 33 | 42.42 | 27.27 | 15.15 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 40/40 | 32 | 40.62 | 46.88 | -6.25 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 34/39 | 29 | 27.59 | 51.72 | -24.14 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 31/30 | 21 | 61.9 | 47.62 | 14.29 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 31/30 | 21 | 4.762 | 4.762 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 50/50 | 47 | 40.43 | 57.45 | -17.02 | SUFFICIENT_FOR_DESCRIPTION |

### t0 -30분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 51/48 | 47 | 0 | 0 | 0 | -0.03598 | -0.04145 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 52/50 | 50 | -0.2255 | -0.1024 | -0.1231 | 0.2 | -0.1698 | -0.2255 | -0.1024 | -0.1231 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 51/50 | 48 | -0.2384 | -0.09701 | -0.1414 | 0.4507 | -0.1268 | -0.179 | -0.09701 | -0.08199 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 50/51 | 49 | -0.7223 | -0.07077 | -0.6515 | 0.7558 | -0.0372 | -0.7056 | -0.1609 | -0.5448 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 46/48 | 44 | 1.153e+08 | 1.417e+08 | -2.649e+07 | 2.854e+08 | 2.575e+08 | 1.252e+08 | 1.624e+08 | -3.722e+07 | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 31/32 | 24 | 1.538e+08 | 2.466e+08 | -9.282e+07 | 3.579e+08 | 3.091e+08 | 2.607e+08 | 2.594e+08 | 1.26e+06 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 31/32 | 24 | 0.9307 | 0.9963 | -0.06552 | 1.24 | 1.164 | 0.9181 | 0.9963 | -0.07814 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 44/42 | 38 | 23.09 | 13.5 | 9.587 | 78.01 | 101.7 | 23.09 | 13.5 | 9.587 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 41/41 | 36 | 1.421 | 1.581 | -0.1595 | 3.079 | 18.49 | 1.408 | 1.491 | -0.08292 | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 46/48 | 44 | 71.13 | 1899 | -1828 | 76.85 | 3.713e+05 | 71.13 | 1904 | -1833 | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 40/40 | 34 | 71.23 | 1902 | -1831 | 77.02 | 4.451e+05 | 71.23 | 1902 | -1831 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 40/40 | 34 | 1 | 0.9996 | 0.0008371 | 1.001 | 0.9994 | 1 | 0.9996 | 0.0006937 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 38/38 | 31 | -0.1196 | -0.008634 | -0.111 | -0.04146 | -0.03195 | -0.06625 | -0.01454 | -0.05171 | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 37/38 | 31 | 3.929 | 0.5041 | 3.424 | 6.376 | 1.103 | 3.929 | 0.4724 | 3.456 | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 31/32 | 24 | -5.259 | 13.36 | -18.62 | 17.01 | 11.65 | -1.246 | 15.45 | -16.7 | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 31/32 | 24 | 3.175 | 0.3537 | 2.821 | 4.586 | 0.7711 | 3.171 | 0.3521 | 2.818 | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 50/51 | 49 | -0.5283 | -0.06791 | -0.4604 | 0.7433 | -0.02507 | -0.4226 | -0.07486 | -0.3477 | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 50/51 | 49 | -0.5552 | -0.0205 | -0.5347 | 0.7469 | -0.04588 | -0.5452 | -0.02793 | -0.5172 | SUFFICIENT_FOR_DESCRIPTION |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 51/48 | 47 | 40.43 | 31.91 | 8.511 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 52/50 | 50 | 34 | 30 | 4 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 51/50 | 48 | 41.67 | 33.33 | 8.333 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 50/51 | 49 | 36.73 | 38.78 | -2.041 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 31/32 | 24 | 8.333 | 12.5 | -4.167 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 44/42 | 38 | 63.16 | 57.89 | 5.263 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 41/41 | 36 | 58.33 | 61.11 | -2.778 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 40/40 | 34 | 52.94 | 32.35 | 20.59 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 38/38 | 31 | 38.71 | 35.48 | 3.226 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 31/32 | 24 | 50 | 58.33 | -8.333 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 31/32 | 24 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 50/51 | 49 | 38.78 | 40.82 | -2.041 | SUFFICIENT_FOR_DESCRIPTION |

### t0 -15분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 52/49 | 48 | 0.05593 | 0 | 0.05593 | 0.2085 | 0.03595 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 51/49 | 48 | 0 | 0 | 0 | -0.2961 | 0.07889 | -0.1188 | 0 | -0.1188 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 52/49 | 48 | -0.2178 | -0.1017 | -0.1161 | -0.09998 | -0.02862 | -0.2554 | -0.103 | -0.1524 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 51/49 | 47 | 0 | -0.07077 | 0.07077 | 0.301 | 0.04703 | -0.1199 | -0.1043 | -0.01557 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 49/42 | 41 | 1.243e+08 | 9.444e+07 | 2.989e+07 | 2.373e+08 | 2.249e+08 | 1.631e+08 | 1.031e+08 | 6.004e+07 | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 34/33 | 26 | 2.141e+08 | 2.203e+08 | -6.176e+06 | 3.616e+08 | 3.287e+08 | 2.874e+08 | 2.348e+08 | 5.256e+07 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 34/31 | 25 | 0.7001 | 0.6441 | 0.05603 | 1.376 | 0.901 | 0.6501 | 0.6233 | 0.02685 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 48/39 | 38 | 9.731 | 0.7809 | 8.95 | 29.21 | 98.35 | 15.78 | -5.031 | 20.81 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 47/38 | 37 | 1.23 | 1.562 | -0.3325 | 1.741 | 6.182 | 1.295 | 1.521 | -0.226 | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 49/42 | 41 | 68.84 | 1907 | -1838 | 72.87 | 4.239e+05 | 68.84 | 1912 | -1844 | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 43/38 | 36 | 69.11 | 1905 | -1836 | 75.27 | 4.611e+05 | 70.12 | 1910 | -1840 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 43/38 | 36 | 0.9983 | 1 | -0.001962 | 0.998 | 1 | 0.9974 | 1 | -0.00282 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 42/35 | 33 | -0.1141 | 0 | -0.1141 | -0.113 | 0.01954 | -0.1022 | 0 | -0.1022 | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 40/34 | 31 | 5.188 | 0.6878 | 4.5 | 5.849 | 0.9863 | 4.881 | 0.6479 | 4.233 | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 34/31 | 25 | -14.46 | -21.74 | 7.279 | 17.91 | 6.116 | -18.29 | -21.74 | 3.444 | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 34/31 | 25 | 3.853 | 0.3655 | 3.487 | 5.086 | 0.633 | 3.81 | 0.3239 | 3.486 | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 51/49 | 47 | -0.1739 | -0.1475 | -0.02638 | 0.3825 | 0.08442 | -0.3035 | -0.1475 | -0.1559 | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 51/49 | 47 | -0.1873 | -0.1751 | -0.01224 | 0.2702 | 0.009122 | -0.1873 | -0.1826 | -0.004715 | SUFFICIENT_FOR_DESCRIPTION |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 52/49 | 48 | 47.92 | 41.67 | 6.25 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 51/49 | 48 | 39.58 | 43.75 | -4.167 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 52/49 | 48 | 39.58 | 37.5 | 2.083 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 51/49 | 47 | 42.55 | 38.3 | 4.255 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 34/31 | 25 | 8 | 12 | -4 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 48/39 | 38 | 60.53 | 50 | 10.53 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 47/38 | 37 | 56.76 | 64.86 | -8.108 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 43/38 | 36 | 44.44 | 61.11 | -16.67 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 42/35 | 33 | 45.45 | 48.48 | -3.03 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 34/31 | 25 | 36 | 44 | -8 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 34/31 | 25 | 4 | 4 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 51/49 | 47 | 40.43 | 38.3 | 2.128 | SUFFICIENT_FOR_DESCRIPTION |

### t0 -5분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 51/48 | 47 | -0.4535 | 0 | -0.4535 | -0.6164 | -0.02031 | -0.369 | 0 | -0.369 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 52/50 | 49 | -0.4798 | -0.0406 | -0.4392 | -0.8507 | -0.1038 | -0.3632 | -0.02944 | -0.3338 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 51/48 | 47 | -1.17 | 0 | -1.17 | -1.429 | -0.0352 | -1.313 | 0 | -1.313 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 50/50 | 47 | -0.9271 | -0.1421 | -0.785 | -0.5621 | 0.05784 | -0.9019 | -0.1564 | -0.7455 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 50/47 | 46 | 1.211e+08 | 1.071e+08 | 1.401e+07 | 2.195e+08 | 1.7e+08 | 1.091e+08 | 1.047e+08 | 4.393e+06 | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 34/31 | 24 | 2.543e+08 | 2.493e+08 | 5.009e+06 | 3.548e+08 | 3.486e+08 | 2.688e+08 | 2.635e+08 | 5.313e+06 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 34/30 | 23 | 0.6704 | 0.5052 | 0.1652 | 1.292 | 0.7747 | 0.5403 | 0.5012 | 0.03912 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 50/44 | 43 | -14.81 | -31.02 | 16.22 | 20.83 | 4.293 | -17.35 | -32.96 | 15.61 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 48/38 | 36 | 0.9661 | 0.7532 | 0.213 | 1.596 | 1.551 | 0.9865 | 0.7532 | 0.2333 | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 50/47 | 46 | 69.31 | 1893 | -1824 | 72.37 | 3.759e+05 | 62.51 | 1893 | -1830 | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 47/36 | 35 | 69.22 | 1906 | -1836 | 74.05 | 4.866e+05 | 55.95 | 1912 | -1856 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 47/36 | 35 | 0.994 | 0.9999 | -0.005923 | 0.9935 | 0.9999 | 0.9957 | 0.9999 | -0.004187 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 46/35 | 34 | -0.3269 | -0.003512 | -0.3234 | -0.3525 | 0.004272 | -0.3269 | 0.0009381 | -0.3278 | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 43/35 | 33 | 4.244 | 0.7277 | 3.516 | 6.009 | 1.087 | 4.263 | 0.6296 | 3.633 | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 36/30 | 25 | -8.453 | 6.174 | -14.63 | 58.31 | 11.3 | -12.9 | 10.17 | -23.07 | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 35/30 | 24 | 4.598 | 0.3677 | 4.23 | 5.996 | 0.6179 | 3.909 | 0.3677 | 3.542 | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 50/50 | 47 | -0.5905 | -0.02538 | -0.5651 | -0.4597 | 0.0967 | -0.596 | -0.03685 | -0.5592 | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 50/50 | 47 | -0.7471 | -0.08394 | -0.6632 | -0.5583 | 0.01339 | -0.7098 | -0.1197 | -0.5902 | SUFFICIENT_FOR_DESCRIPTION |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 51/48 | 47 | 29.79 | 36.17 | -6.383 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 52/50 | 49 | 32.65 | 32.65 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 51/48 | 47 | 34.04 | 38.3 | -4.255 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 50/50 | 47 | 38.3 | 38.3 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 34/30 | 23 | 13.04 | 4.348 | 8.696 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 50/44 | 43 | 39.53 | 32.56 | 6.977 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 48/38 | 36 | 47.22 | 33.33 | 13.89 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 47/36 | 35 | 37.14 | 42.86 | -5.714 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 46/35 | 34 | 35.29 | 50 | -14.71 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 36/30 | 25 | 36 | 52 | -16 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 35/30 | 24 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 50/50 | 47 | 42.55 | 40.43 | 2.128 | SUFFICIENT_FOR_DESCRIPTION |

### 시장당 첫 사건 1개 sensitivity

Earliest target_time event per market, retaining original matched control; never choose by feature/result.
9쌍이므로 모두 표본 부족. 아래 수치는 방향 확인용이며 독립적인 확인 증거가 아니다.

| feature | 시점 | paired N | E 중앙값 | C 중앙값 | 차이 |
|---|---|---|---|---|---|
| return_60m_pct | 120 | 8 | -0.981 | -0.4208 | -0.5602 |
| trade_value_ratio | 120 | 6 | 0.5805 | 0.5753 | 0.005149 |
| trade_value_acceleration | 120 | 7 | 2.259 | 0.6665 | 1.593 |
| range_30m_pct | 120 | 6 | 3.7 | 0.7086 | 2.992 |
| alt_relative_60m_pct | 120 | 8 | 0.3247 | -0.2705 | 0.5952 |
| btc_relative_60m_pct | 120 | 8 | -0.09218 | -0.3005 | 0.2083 |
| return_60m_pct | 60 | 8 | -0.2649 | 0.1408 | -0.4058 |
| trade_value_ratio | 60 | 3 | 1.069 | 1.242 | -0.1731 |
| trade_value_acceleration | 60 | 4 | 0.894 | 0.4059 | 0.4881 |
| range_30m_pct | 60 | 3 | 3.774 | 0.3523 | 3.421 |
| alt_relative_60m_pct | 60 | 8 | -0.3359 | 0.3386 | -0.6745 |
| btc_relative_60m_pct | 60 | 8 | -0.1205 | 0.3158 | -0.4363 |
| return_60m_pct | 30 | 8 | 0.3509 | -0.05868 | 0.4096 |
| trade_value_ratio | 30 | 3 | 0.9055 | 1.372 | -0.4661 |
| trade_value_acceleration | 30 | 5 | 1.676 | 3.402 | -1.727 |
| range_30m_pct | 30 | 5 | 3.929 | 0.5291 | 3.399 |
| alt_relative_60m_pct | 30 | 8 | 0.6379 | -0.0284 | 0.6663 |
| btc_relative_60m_pct | 30 | 8 | 0.2683 | 0.01908 | 0.2492 |
| return_60m_pct | 15 | 9 | -1.408 | 0 | -1.408 |
| trade_value_ratio | 15 | 3 | 0.4565 | 1.308 | -0.8517 |
| trade_value_acceleration | 15 | 8 | 1.414 | 0.857 | 0.5566 |
| range_30m_pct | 15 | 5 | 2.827 | 0.5297 | 2.297 |
| alt_relative_60m_pct | 15 | 9 | -0.9566 | -0.04417 | -0.9124 |
| btc_relative_60m_pct | 15 | 9 | -1.012 | -0.1963 | -0.8155 |
| return_60m_pct | 5 | 9 | -0.2317 | -0.1582 | -0.07352 |
| trade_value_ratio | 5 | 3 | 0.5567 | 1.104 | -0.5475 |
| trade_value_acceleration | 5 | 8 | 2.315 | 0.7047 | 1.611 |
| range_30m_pct | 5 | 7 | 3.442 | 0.7848 | 2.657 |
| alt_relative_60m_pct | 5 | 9 | 0.571 | -0.1494 | 0.7205 |
| btc_relative_60m_pct | 5 | 9 | 0.4649 | -0.1896 | 0.6545 |
## B: 15쌍

발생 시장 5개. 최대 시장 비중 46.67%, 상위3개 86.67%.

| market | events |
|---|---|
| KRW-FLOCK | 7 |
| KRW-SKR | 4 |
| KRW-0G | 2 |
| KRW-ICX | 1 |
| KRW-CPOOL | 1 |

### t0 -120분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 14/13 | 12 | 0.2367 | -0.02934 | 0.266 | 0.3718 | -0.1917 | 0.2367 | -0.06926 | 0.3059 | INSUFFICIENT_SAMPLE |
| return_15m_pct | 13/14 | 13 | 0.1186 | -0.3102 | 0.4289 | 0.113 | -0.3969 | 0.1186 | -0.2937 | 0.4123 | INSUFFICIENT_SAMPLE |
| return_30m_pct | 13/14 | 12 | -0.1815 | -0.1322 | -0.04932 | -0.7417 | -0.1193 | -0.03143 | -0.1322 | 0.1007 | INSUFFICIENT_SAMPLE |
| return_60m_pct | 14/13 | 13 | -0.003451 | 0 | -0.003451 | 0.4397 | -0.0007282 | 0.4762 | 0 | 0.4762 | INSUFFICIENT_SAMPLE |
| trade_value_5m | 13/12 | 11 | 1.313e+08 | 6.724e+07 | 6.409e+07 | 1.89e+08 | 1.482e+08 | 1.365e+08 | 7.26e+07 | 6.388e+07 | INSUFFICIENT_SAMPLE |
| prior_mean_trade_value_5m | 8/7 | 5 | 1.813e+08 | 1.549e+08 | 2.636e+07 | 2.498e+08 | 3.274e+08 | 3.419e+08 | 1.549e+08 | 1.869e+08 | INSUFFICIENT_SAMPLE |
| trade_value_ratio | 8/7 | 5 | 0.8557 | 0.6661 | 0.1896 | 1.095 | 1.036 | 0.9394 | 0.6661 | 0.2732 | INSUFFICIENT_SAMPLE |
| trade_value_change_pct | 13/10 | 9 | 17.98 | -41.92 | 59.9 | 50.9 | 28.84 | 17.98 | -34.04 | 52.02 | INSUFFICIENT_SAMPLE |
| trade_value_acceleration | 12/10 | 8 | 1.081 | 0.3844 | 0.6966 | 1.425 | 2.371 | 0.8945 | 0.3844 | 0.5101 | INSUFFICIENT_SAMPLE |
| ma5 | 13/12 | 11 | 74.7 | 1860 | -1786 | 92.64 | 8.486e+05 | 39.68 | 1831 | -1791 | INSUFFICIENT_SAMPLE |
| ma20 | 11/10 | 8 | 38.84 | 1910 | -1871 | 93.89 | 1.019e+06 | 37.11 | 1910 | -1873 | INSUFFICIENT_SAMPLE |
| ma5_ma20_ratio | 11/10 | 8 | 1.002 | 0.9994 | 0.00215 | 1.003 | 0.999 | 1.002 | 0.9996 | 0.002296 | INSUFFICIENT_SAMPLE |
| ma20_slope_5m_pct | 10/10 | 7 | 0.03831 | -0.02514 | 0.06344 | 0.02469 | -0.02322 | 0.1547 | -0.02846 | 0.1832 | INSUFFICIENT_SAMPLE |
| range_30m_pct | 10/10 | 7 | 6.276 | 0.7281 | 5.548 | 6.341 | 1.348 | 6.725 | 0.5184 | 6.207 | INSUFFICIENT_SAMPLE |
| range_change_pct | 9/7 | 6 | 2.1 | 0.02936 | 2.071 | 9.032 | 33.08 | 1.294 | 16.68 | -15.39 | INSUFFICIENT_SAMPLE |
| distance_to_prior_high_pct | 9/7 | 6 | 3.767 | 0.3623 | 3.405 | 4.768 | 0.8063 | 5.172 | 0.3134 | 4.859 | INSUFFICIENT_SAMPLE |
| alt_relative_60m_pct | 14/13 | 13 | 0.7249 | 0.005165 | 0.7197 | 0.5255 | 0.1154 | 0.838 | 0.005165 | 0.8328 | INSUFFICIENT_SAMPLE |
| btc_relative_60m_pct | 14/13 | 13 | 0.09481 | -0.08752 | 0.1823 | 0.4436 | 0.02408 | 0.2702 | -0.08752 | 0.3577 | INSUFFICIENT_SAMPLE |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 14/13 | 12 | 50 | 25 | 25 | INSUFFICIENT_SAMPLE |
| return_15m_positive | 13/14 | 13 | 53.85 | 15.38 | 38.46 | INSUFFICIENT_SAMPLE |
| return_30m_positive | 13/14 | 12 | 50 | 33.33 | 16.67 | INSUFFICIENT_SAMPLE |
| return_60m_positive | 14/13 | 13 | 53.85 | 30.77 | 23.08 | INSUFFICIENT_SAMPLE |
| trade_value_double | 8/7 | 5 | 20 | 20 | 0 | INSUFFICIENT_SAMPLE |
| trade_value_increasing | 13/10 | 9 | 55.56 | 22.22 | 33.33 | INSUFFICIENT_SAMPLE |
| trade_value_accelerating | 12/10 | 8 | 50 | 25 | 25 | INSUFFICIENT_SAMPLE |
| ma5_above_ma20 | 11/10 | 8 | 50 | 25 | 25 | INSUFFICIENT_SAMPLE |
| ma20_rising | 10/10 | 7 | 57.14 | 42.86 | 14.29 | INSUFFICIENT_SAMPLE |
| range_expanding | 9/7 | 6 | 66.67 | 66.67 | 0 | INSUFFICIENT_SAMPLE |
| prior_high_breakout | 9/7 | 6 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| relative_strength_positive | 14/13 | 13 | 61.54 | 53.85 | 7.692 | INSUFFICIENT_SAMPLE |

### t0 -60분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 14/13 | 12 | -0.0625 | 0.1497 | -0.2122 | 0.1182 | 0.4927 | 0.1192 | 0.1676 | -0.04843 | INSUFFICIENT_SAMPLE |
| return_15m_pct | 15/12 | 12 | -0.7453 | 0.1873 | -0.9326 | -0.4937 | 0.6033 | -0.05938 | 0.1873 | -0.2467 | INSUFFICIENT_SAMPLE |
| return_30m_pct | 15/13 | 13 | -0.9836 | 0.1036 | -1.087 | -0.7464 | 0.5084 | -0.9836 | 0.1036 | -1.087 | INSUFFICIENT_SAMPLE |
| return_60m_pct | 15/13 | 13 | -1.942 | 0.3702 | -2.312 | -2.012 | 0.3147 | -2 | 0.3702 | -2.37 | INSUFFICIENT_SAMPLE |
| trade_value_5m | 15/12 | 12 | 9.275e+07 | 7.652e+07 | 1.622e+07 | 1.21e+08 | 2.967e+08 | 9.666e+07 | 7.652e+07 | 2.014e+07 | INSUFFICIENT_SAMPLE |
| prior_mean_trade_value_5m | 10/9 | 8 | 1.54e+08 | 1.346e+08 | 1.933e+07 | 1.992e+08 | 2.78e+08 | 1.826e+08 | 1.569e+08 | 2.568e+07 | INSUFFICIENT_SAMPLE |
| trade_value_ratio | 10/8 | 7 | 0.7152 | 1.151 | -0.4358 | 0.8103 | 1.689 | 0.7678 | 1.391 | -0.623 | INSUFFICIENT_SAMPLE |
| trade_value_change_pct | 13/11 | 9 | -3.64 | 11.49 | -15.13 | 37.12 | 17.87 | -13.23 | 11.49 | -24.72 | INSUFFICIENT_SAMPLE |
| trade_value_acceleration | 13/10 | 8 | 1.252 | 1.066 | 0.1867 | 2.02 | 1.297 | 1.307 | 1.014 | 0.2934 | INSUFFICIENT_SAMPLE |
| ma5 | 15/12 | 12 | 72.32 | 1853 | -1781 | 87.08 | 8.525e+05 | 61.88 | 1853 | -1791 | INSUFFICIENT_SAMPLE |
| ma20 | 12/10 | 8 | 80.12 | 1908 | -1828 | 99.04 | 1.022e+06 | 78.68 | 1851 | -1772 | INSUFFICIENT_SAMPLE |
| ma5_ma20_ratio | 12/10 | 8 | 0.9965 | 1.001 | -0.004274 | 0.9972 | 1.003 | 0.9977 | 1.001 | -0.003041 | INSUFFICIENT_SAMPLE |
| ma20_slope_5m_pct | 12/10 | 8 | -0.06756 | 0.03636 | -0.1039 | -0.1213 | 0.1027 | -0.0863 | 0.03912 | -0.1254 | INSUFFICIENT_SAMPLE |
| range_30m_pct | 12/10 | 8 | 3.644 | 0.9248 | 2.719 | 3.743 | 1.917 | 3.644 | 0.9444 | 2.699 | INSUFFICIENT_SAMPLE |
| range_change_pct | 10/8 | 7 | -38.41 | 12.49 | -50.9 | -9.62 | 51.25 | -32.64 | 18.64 | -51.28 | INSUFFICIENT_SAMPLE |
| distance_to_prior_high_pct | 10/8 | 7 | 4.534 | 0.1663 | 4.368 | 4.367 | 0.2006 | 4.637 | 0.1553 | 4.482 | INSUFFICIENT_SAMPLE |
| alt_relative_60m_pct | 15/13 | 13 | -1.779 | 0.343 | -2.122 | -1.776 | 0.57 | -1.873 | 0.343 | -2.216 | INSUFFICIENT_SAMPLE |
| btc_relative_60m_pct | 15/13 | 13 | -1.874 | 0.1194 | -1.994 | -1.873 | 0.453 | -1.914 | 0.1194 | -2.033 | INSUFFICIENT_SAMPLE |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 14/13 | 12 | 50 | 66.67 | -16.67 | INSUFFICIENT_SAMPLE |
| return_15m_positive | 15/12 | 12 | 41.67 | 58.33 | -16.67 | INSUFFICIENT_SAMPLE |
| return_30m_positive | 15/13 | 13 | 23.08 | 53.85 | -30.77 | INSUFFICIENT_SAMPLE |
| return_60m_positive | 15/13 | 13 | 15.38 | 61.54 | -46.15 | INSUFFICIENT_SAMPLE |
| trade_value_double | 10/8 | 7 | 0 | 14.29 | -14.29 | INSUFFICIENT_SAMPLE |
| trade_value_increasing | 13/11 | 9 | 44.44 | 55.56 | -11.11 | INSUFFICIENT_SAMPLE |
| trade_value_accelerating | 13/10 | 8 | 75 | 50 | 25 | INSUFFICIENT_SAMPLE |
| ma5_above_ma20 | 12/10 | 8 | 37.5 | 62.5 | -25 | INSUFFICIENT_SAMPLE |
| ma20_rising | 12/10 | 8 | 12.5 | 87.5 | -75 | INSUFFICIENT_SAMPLE |
| range_expanding | 10/8 | 7 | 42.86 | 71.43 | -28.57 | INSUFFICIENT_SAMPLE |
| prior_high_breakout | 10/8 | 7 | 0 | 28.57 | -28.57 | INSUFFICIENT_SAMPLE |
| relative_strength_positive | 15/13 | 13 | 15.38 | 53.85 | -38.46 | INSUFFICIENT_SAMPLE |

### t0 -30분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 14/13 | 12 | -0.06234 | 0 | -0.06234 | -0.1565 | 0.03564 | -0.2089 | -0.07325 | -0.1357 | INSUFFICIENT_SAMPLE |
| return_15m_pct | 15/13 | 13 | -0.365 | -0.1862 | -0.1787 | -0.461 | -0.03606 | -0.6329 | -0.1862 | -0.4467 | INSUFFICIENT_SAMPLE |
| return_30m_pct | 15/12 | 12 | -0.6944 | -0.3312 | -0.3632 | -0.9364 | -0.1886 | -0.7356 | -0.3312 | -0.4043 | INSUFFICIENT_SAMPLE |
| return_60m_pct | 15/13 | 13 | -1.087 | 0.3185 | -1.405 | -1.698 | 0.2953 | -1.134 | 0.3185 | -1.452 | INSUFFICIENT_SAMPLE |
| trade_value_5m | 12/13 | 11 | 8.877e+07 | 7.735e+07 | 1.141e+07 | 1.054e+08 | 4.087e+08 | 9.093e+07 | 7.735e+07 | 1.357e+07 | INSUFFICIENT_SAMPLE |
| prior_mean_trade_value_5m | 9/9 | 7 | 1.112e+08 | 2.14e+08 | -1.029e+08 | 1.998e+08 | 2.945e+08 | 1.857e+08 | 2.272e+08 | -4.154e+07 | INSUFFICIENT_SAMPLE |
| trade_value_ratio | 9/9 | 7 | 0.6047 | 1.105 | -0.5001 | 0.8587 | 2.106 | 0.6047 | 0.8312 | -0.2265 | INSUFFICIENT_SAMPLE |
| trade_value_change_pct | 10/12 | 10 | 42.01 | 55.16 | -13.15 | 52.09 | 187.6 | 42.01 | 25.35 | 16.66 | INSUFFICIENT_SAMPLE |
| trade_value_acceleration | 10/10 | 9 | 1.054 | 1.79 | -0.7365 | 1.558 | 1.935 | 0.9534 | 1.65 | -0.6962 | INSUFFICIENT_SAMPLE |
| ma5 | 12/13 | 11 | 75.27 | 1893 | -1818 | 95.69 | 7.859e+05 | 71.74 | 1893 | -1821 | INSUFFICIENT_SAMPLE |
| ma20 | 10/10 | 9 | 75.56 | 2313 | -2238 | 104.6 | 1.022e+06 | 71.98 | 1934 | -1862 | INSUFFICIENT_SAMPLE |
| ma5_ma20_ratio | 10/10 | 9 | 0.9962 | 0.9995 | -0.003301 | 0.996 | 1.001 | 0.9966 | 0.9992 | -0.002626 | INSUFFICIENT_SAMPLE |
| ma20_slope_5m_pct | 10/9 | 8 | -0.1967 | 0 | -0.1967 | -0.3269 | -0.006918 | -0.1965 | -0.01451 | -0.182 | INSUFFICIENT_SAMPLE |
| range_30m_pct | 10/9 | 8 | 3.24 | 0.6878 | 2.553 | 4.278 | 1.375 | 3.631 | 0.6551 | 2.976 | INSUFFICIENT_SAMPLE |
| range_change_pct | 9/9 | 7 | -11.58 | 8.29 | -19.87 | 6.263 | 16.51 | -6.846 | 8.29 | -15.14 | INSUFFICIENT_SAMPLE |
| distance_to_prior_high_pct | 9/9 | 7 | 3.521 | 0.4401 | 3.081 | 4.968 | 0.7705 | 3.521 | 0.6878 | 2.833 | INSUFFICIENT_SAMPLE |
| alt_relative_60m_pct | 15/13 | 13 | -0.7621 | -0.08778 | -0.6743 | -1.752 | 0.2501 | -1.094 | -0.08778 | -1.007 | INSUFFICIENT_SAMPLE |
| btc_relative_60m_pct | 15/13 | 13 | -0.9523 | 0.1114 | -1.064 | -1.637 | 0.3728 | -1.388 | 0.1114 | -1.5 | INSUFFICIENT_SAMPLE |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 14/13 | 12 | 33.33 | 41.67 | -8.333 | INSUFFICIENT_SAMPLE |
| return_15m_positive | 15/13 | 13 | 23.08 | 30.77 | -7.692 | INSUFFICIENT_SAMPLE |
| return_30m_positive | 15/12 | 12 | 33.33 | 33.33 | 0 | INSUFFICIENT_SAMPLE |
| return_60m_positive | 15/13 | 13 | 23.08 | 53.85 | -30.77 | INSUFFICIENT_SAMPLE |
| trade_value_double | 9/9 | 7 | 0 | 28.57 | -28.57 | INSUFFICIENT_SAMPLE |
| trade_value_increasing | 10/12 | 10 | 60 | 60 | 0 | INSUFFICIENT_SAMPLE |
| trade_value_accelerating | 10/10 | 9 | 44.44 | 66.67 | -22.22 | INSUFFICIENT_SAMPLE |
| ma5_above_ma20 | 10/10 | 9 | 33.33 | 33.33 | 0 | INSUFFICIENT_SAMPLE |
| ma20_rising | 10/9 | 8 | 12.5 | 37.5 | -25 | INSUFFICIENT_SAMPLE |
| range_expanding | 9/9 | 7 | 42.86 | 57.14 | -14.29 | INSUFFICIENT_SAMPLE |
| prior_high_breakout | 9/9 | 7 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| relative_strength_positive | 15/13 | 13 | 15.38 | 38.46 | -23.08 | INSUFFICIENT_SAMPLE |

### t0 -15분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 15/12 | 12 | -0.369 | 0 | -0.369 | -0.4903 | -0.05085 | -0.4623 | 0 | -0.4623 | INSUFFICIENT_SAMPLE |
| return_15m_pct | 15/12 | 12 | -0.6579 | 0.02579 | -0.6837 | -1.019 | 0.1412 | -0.8784 | 0.02579 | -0.9042 | INSUFFICIENT_SAMPLE |
| return_30m_pct | 15/13 | 13 | -1.46 | -0.08785 | -1.372 | -1.474 | 0.04797 | -1.629 | -0.08785 | -1.541 | INSUFFICIENT_SAMPLE |
| return_60m_pct | 15/12 | 12 | -0.4545 | 0.04405 | -0.4986 | -2.423 | 0.4205 | -1.563 | 0.04405 | -1.607 | INSUFFICIENT_SAMPLE |
| trade_value_5m | 13/10 | 10 | 1.035e+08 | 9.173e+07 | 1.179e+07 | 1.454e+08 | 1.944e+08 | 1.082e+08 | 9.173e+07 | 1.643e+07 | INSUFFICIENT_SAMPLE |
| prior_mean_trade_value_5m | 9/8 | 7 | 1.375e+08 | 2.039e+08 | -6.643e+07 | 1.684e+08 | 3.753e+08 | 1.813e+08 | 2.134e+08 | -3.207e+07 | INSUFFICIENT_SAMPLE |
| trade_value_ratio | 9/7 | 7 | 0.6071 | 0.4577 | 0.1493 | 1.081 | 0.765 | 0.6071 | 0.4577 | 0.1493 | INSUFFICIENT_SAMPLE |
| trade_value_change_pct | 13/9 | 9 | 17.37 | 13.95 | 3.427 | 42.37 | 150 | 14.24 | 13.95 | 0.2911 | INSUFFICIENT_SAMPLE |
| trade_value_acceleration | 12/8 | 8 | 1.263 | 2.855 | -1.592 | 2.237 | 13.28 | 1.342 | 2.855 | -1.513 | INSUFFICIENT_SAMPLE |
| ma5 | 13/10 | 10 | 70.46 | 1913 | -1843 | 89.52 | 1.022e+06 | 73.46 | 1913 | -1840 | INSUFFICIENT_SAMPLE |
| ma20 | 11/8 | 8 | 71.13 | 1913 | -1842 | 96.72 | 8.507e+05 | 74.49 | 1913 | -1839 | INSUFFICIENT_SAMPLE |
| ma5_ma20_ratio | 11/8 | 8 | 0.996 | 0.9999 | -0.003982 | 0.9936 | 1 | 0.9957 | 0.9999 | -0.004231 | INSUFFICIENT_SAMPLE |
| ma20_slope_5m_pct | 10/8 | 8 | -0.2879 | -0.004038 | -0.2839 | -0.3902 | 0.06576 | -0.2879 | -0.004038 | -0.2839 | INSUFFICIENT_SAMPLE |
| range_30m_pct | 10/8 | 8 | 3.447 | 0.6846 | 2.763 | 3.896 | 1.154 | 3.447 | 0.6846 | 2.763 | INSUFFICIENT_SAMPLE |
| range_change_pct | 9/7 | 7 | -36.8 | -26.2 | -10.6 | -22.16 | -11.58 | -36.8 | -26.2 | -10.6 | INSUFFICIENT_SAMPLE |
| distance_to_prior_high_pct | 9/7 | 7 | 3.521 | 0.6637 | 2.857 | 5.347 | 0.7018 | 3.521 | 0.6637 | 2.857 | INSUFFICIENT_SAMPLE |
| alt_relative_60m_pct | 15/12 | 12 | -0.7813 | -0.1242 | -0.657 | -2.485 | 0.389 | -1.918 | -0.1242 | -1.794 | INSUFFICIENT_SAMPLE |
| btc_relative_60m_pct | 15/12 | 12 | -0.4829 | 0.05129 | -0.5342 | -2.41 | 0.4714 | -1.602 | 0.05129 | -1.654 | INSUFFICIENT_SAMPLE |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 15/12 | 12 | 25 | 25 | 0 | INSUFFICIENT_SAMPLE |
| return_15m_positive | 15/12 | 12 | 0 | 50 | -50 | INSUFFICIENT_SAMPLE |
| return_30m_positive | 15/13 | 13 | 7.692 | 46.15 | -38.46 | INSUFFICIENT_SAMPLE |
| return_60m_positive | 15/12 | 12 | 16.67 | 50 | -33.33 | INSUFFICIENT_SAMPLE |
| trade_value_double | 9/7 | 7 | 0 | 14.29 | -14.29 | INSUFFICIENT_SAMPLE |
| trade_value_increasing | 13/9 | 9 | 55.56 | 66.67 | -11.11 | INSUFFICIENT_SAMPLE |
| trade_value_accelerating | 12/8 | 8 | 62.5 | 100 | -37.5 | INSUFFICIENT_SAMPLE |
| ma5_above_ma20 | 11/8 | 8 | 25 | 37.5 | -12.5 | INSUFFICIENT_SAMPLE |
| ma20_rising | 10/8 | 8 | 12.5 | 37.5 | -25 | INSUFFICIENT_SAMPLE |
| range_expanding | 9/7 | 7 | 0 | 42.86 | -42.86 | INSUFFICIENT_SAMPLE |
| prior_high_breakout | 9/7 | 7 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| relative_strength_positive | 15/12 | 12 | 16.67 | 25 | -8.333 | INSUFFICIENT_SAMPLE |

### t0 -5분: 연속형

| feature | 유효 E/C | paired N | E 중앙값 | C 중앙값 | 차이 | E 평균 | C 평균 | paired E 중앙값 | paired C 중앙값 | paired 차이 | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| return_5m_pct | 12/12 | 10 | -0.3593 | 0.09721 | -0.4565 | -0.2658 | 0.06784 | -0.1786 | 0.07195 | -0.2505 | INSUFFICIENT_SAMPLE |
| return_15m_pct | 14/13 | 12 | -0.4155 | 0 | -0.4155 | -1.144 | -0.2224 | -0.343 | 0 | -0.343 | INSUFFICIENT_SAMPLE |
| return_30m_pct | 13/13 | 12 | -1.216 | 0.05283 | -1.269 | -1.887 | -0.0589 | -1.127 | 0.07809 | -1.205 | INSUFFICIENT_SAMPLE |
| return_60m_pct | 13/13 | 11 | -0.9019 | 0.2116 | -1.114 | -2.288 | 0.347 | -0.9019 | 0.2116 | -1.114 | INSUFFICIENT_SAMPLE |
| trade_value_5m | 13/11 | 10 | 9.001e+07 | 4.187e+07 | 4.814e+07 | 1.049e+08 | 1.323e+08 | 8.548e+07 | 5.788e+07 | 2.76e+07 | INSUFFICIENT_SAMPLE |
| prior_mean_trade_value_5m | 8/7 | 6 | 1.302e+08 | 2.441e+08 | -1.139e+08 | 1.572e+08 | 3.998e+08 | 1.302e+08 | 2.335e+08 | -1.033e+08 | INSUFFICIENT_SAMPLE |
| trade_value_ratio | 8/6 | 5 | 0.8465 | 0.3265 | 0.52 | 0.9732 | 0.5994 | 0.7458 | 0.3547 | 0.3911 | INSUFFICIENT_SAMPLE |
| trade_value_change_pct | 11/10 | 8 | 10.72 | -30.67 | 41.4 | 25.45 | 50.34 | 9.219 | -24.62 | 33.84 | INSUFFICIENT_SAMPLE |
| trade_value_acceleration | 11/8 | 7 | 1.198 | 0.5483 | 0.6495 | 1.425 | 1.316 | 1.198 | 0.3954 | 0.8024 | INSUFFICIENT_SAMPLE |
| ma5 | 13/11 | 10 | 70.74 | 1895 | -1824 | 89.04 | 9.286e+05 | 53.9 | 1854 | -1800 | INSUFFICIENT_SAMPLE |
| ma20 | 11/7 | 6 | 70.63 | 1890 | -1820 | 77.4 | 9.715e+05 | 51.65 | 1875 | -1824 | INSUFFICIENT_SAMPLE |
| ma5_ma20_ratio | 11/7 | 6 | 0.9965 | 0.9998 | -0.003293 | 0.9941 | 0.9992 | 0.9976 | 0.9998 | -0.002184 | INSUFFICIENT_SAMPLE |
| ma20_slope_5m_pct | 10/6 | 5 | -0.2803 | -0.01772 | -0.2626 | -0.3977 | -0.06412 | -0.2707 | -0.02512 | -0.2456 | INSUFFICIENT_SAMPLE |
| range_30m_pct | 9/6 | 5 | 3.448 | 0.5516 | 2.897 | 4.076 | 1.158 | 2.857 | 0.3818 | 2.475 | INSUFFICIENT_SAMPLE |
| range_change_pct | 9/6 | 5 | -10.85 | -28.3 | 17.45 | 66.98 | -19.53 | -16.72 | -33.35 | 16.64 | INSUFFICIENT_SAMPLE |
| distance_to_prior_high_pct | 8/6 | 5 | 3.399 | 0.2697 | 3.129 | 5.274 | 0.6546 | 3.107 | 0.2636 | 2.844 | INSUFFICIENT_SAMPLE |
| alt_relative_60m_pct | 13/13 | 11 | -1.01 | 0.0324 | -1.043 | -2.3 | 0.2232 | -1.01 | 0.0324 | -1.043 | INSUFFICIENT_SAMPLE |
| btc_relative_60m_pct | 13/13 | 11 | -0.9067 | 0.1867 | -1.093 | -2.281 | 0.3171 | -0.9067 | 0.1867 | -1.093 | INSUFFICIENT_SAMPLE |

기존 threshold 발생률(양쪽 유효한 pair만):

| 기존 flag | 유효 E/C | paired N | E % | C % | 차이 %p | 상태 |
|---|---|---|---|---|---|---|
| return_5m_positive | 12/12 | 10 | 40 | 60 | -20 | INSUFFICIENT_SAMPLE |
| return_15m_positive | 14/13 | 12 | 0 | 41.67 | -41.67 | INSUFFICIENT_SAMPLE |
| return_30m_positive | 13/13 | 12 | 0 | 58.33 | -58.33 | INSUFFICIENT_SAMPLE |
| return_60m_positive | 13/13 | 11 | 36.36 | 63.64 | -27.27 | INSUFFICIENT_SAMPLE |
| trade_value_double | 8/6 | 5 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| trade_value_increasing | 11/10 | 8 | 62.5 | 37.5 | 25 | INSUFFICIENT_SAMPLE |
| trade_value_accelerating | 11/8 | 7 | 71.43 | 28.57 | 42.86 | INSUFFICIENT_SAMPLE |
| ma5_above_ma20 | 11/7 | 6 | 16.67 | 16.67 | 0 | INSUFFICIENT_SAMPLE |
| ma20_rising | 10/6 | 5 | 20 | 20 | 0 | INSUFFICIENT_SAMPLE |
| range_expanding | 9/6 | 5 | 20 | 20 | 0 | INSUFFICIENT_SAMPLE |
| prior_high_breakout | 8/6 | 5 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| relative_strength_positive | 13/13 | 11 | 27.27 | 54.55 | -27.27 | INSUFFICIENT_SAMPLE |

### 시장당 첫 사건 1개 sensitivity

Earliest target_time event per market, retaining original matched control; never choose by feature/result.
5쌍이므로 모두 표본 부족. 아래 수치는 방향 확인용이며 독립적인 확인 증거가 아니다.

| feature | 시점 | paired N | E 중앙값 | C 중앙값 | 차이 |
|---|---|---|---|---|---|
| return_60m_pct | 120 | 5 | -0.4831 | -0.1758 | -0.3073 |
| trade_value_ratio | 120 | 2 | 1.712 | 0.6577 | 1.055 |
| trade_value_acceleration | 120 | 4 | 1.701 | 0.3397 | 1.361 |
| range_30m_pct | 120 | 4 | 7.32 | 0.5632 | 6.757 |
| alt_relative_60m_pct | 120 | 5 | 0.6118 | -0.2164 | 0.8282 |
| btc_relative_60m_pct | 120 | 5 | -0.08054 | -0.1064 | 0.02584 |
| return_60m_pct | 60 | 5 | -2 | 0.3702 | -2.37 |
| trade_value_ratio | 60 | 2 | 0.5592 | 1.695 | -1.136 |
| trade_value_acceleration | 60 | 2 | 1.307 | 1.758 | -0.4504 |
| range_30m_pct | 60 | 2 | 3.436 | 0.8648 | 2.571 |
| alt_relative_60m_pct | 60 | 5 | -2.124 | -0.04135 | -2.082 |
| btc_relative_60m_pct | 60 | 5 | -2.066 | 0.1194 | -2.186 |
| return_60m_pct | 30 | 5 | -1.73 | 0.3185 | -2.049 |
| trade_value_ratio | 30 | 2 | 1.118 | 0.968 | 0.1503 |
| trade_value_acceleration | 30 | 3 | 0.5244 | 1.931 | -1.406 |
| range_30m_pct | 30 | 3 | 3.394 | 0.6175 | 2.777 |
| alt_relative_60m_pct | 30 | 5 | -2.295 | -0.09422 | -2.201 |
| btc_relative_60m_pct | 30 | 5 | -2.111 | 0.1114 | -2.222 |
| return_60m_pct | 15 | 4 | -1.53 | 0.2182 | -1.748 |
| trade_value_ratio | 15 | 2 | 0.4671 | 0.4141 | 0.05299 |
| trade_value_acceleration | 15 | 2 | 0.9604 | 2.502 | -1.541 |
| range_30m_pct | 15 | 2 | 3.059 | 0.7013 | 2.357 |
| alt_relative_60m_pct | 15 | 4 | -1.918 | -0.1555 | -1.763 |
| btc_relative_60m_pct | 15 | 4 | -1.602 | 0.01562 | -1.618 |
| return_60m_pct | 5 | 3 | -2.108 | 0.2116 | -2.32 |
| trade_value_ratio | 5 | 1 | 0.9472 | 1.13 | -0.1825 |
| trade_value_acceleration | 5 | 2 | 1.341 | 0.3039 | 1.037 |
| range_30m_pct | 5 | 1 | 2.795 | 0.3818 | 2.413 |
| alt_relative_60m_pct | 5 | 3 | -2.108 | 0.2116 | -2.32 |
| btc_relative_60m_pct | 5 | 3 | -2.02 | -0.058 | -1.962 |

## A: 차이가 큰 기존 조건 (표본 20 이상)

| flag | 시점 | paired N | event % | control % | 차이 %p |
|---|---|---|---|---|---|
| ma20_rising | 60 | 29 | 27.59 | 51.72 | -24.14 |
| ma5_above_ma20 | 30 | 34 | 52.94 | 32.35 | 20.59 |
| relative_strength_positive | 120 | 45 | 57.78 | 40 | 17.78 |
| relative_strength_positive | 60 | 47 | 40.43 | 57.45 | -17.02 |
| return_60m_positive | 60 | 47 | 44.68 | 61.7 | -17.02 |
| ma5_above_ma20 | 15 | 36 | 44.44 | 61.11 | -16.67 |
| range_expanding | 5 | 25 | 36 | 52 | -16 |
| trade_value_accelerating | 120 | 32 | 59.38 | 43.75 | 15.62 |
| return_60m_positive | 120 | 45 | 55.56 | 40 | 15.56 |
| trade_value_accelerating | 60 | 33 | 42.42 | 27.27 | 15.15 |
| ma20_rising | 5 | 34 | 35.29 | 50 | -14.71 |
| range_expanding | 60 | 21 | 61.9 | 47.62 | 14.29 |
| trade_value_accelerating | 5 | 36 | 47.22 | 33.33 | 13.89 |
| return_30m_positive | 120 | 46 | 50 | 39.13 | 10.87 |
| trade_value_increasing | 120 | 38 | 50 | 39.47 | 10.53 |

## 해석의 한계

- t0는 미래 목표 도달을 보고 정한 사후 저점이다. t0에 가까운 하락/고점 이격은 이 정의의 영향을 받을 수 있다.
- 같은 시각 control과 비교했으나 시장별 기질·유동성·변동성 차이와 특정 시장 쏠림이 남는다.
- offset별 유효 pair 집합이 다르므로 시점별 숫자 변화가 동일 사건의 일관된 경로임을 뜻하지 않는다.
- 결측이 무작위라는 보장이 없다. 적은 paired N의 비교는 전체 53건으로 일반화하지 않는다.
- 여러 feature·시점을 기술적으로 비교했으며 p-value나 유의성, 미래 매수 성과를 주장하지 않는다.
