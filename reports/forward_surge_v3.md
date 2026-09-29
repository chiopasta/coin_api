# Forward surge V3: 고정 시점의 사전 특징 비교

판정: **PROMISING**

50알트 × 4032시점 = 201,600 observations. 정확한 t 종가 존재 128,512.
BTC는 동일 DB의 기준 데이터. API/보간/threshold 최적화 없음.
L1: t 종가 대비 30분 내 고가 +5%; L2: 60분 내 +10%; L3: 360분 내 +20%.

## 핵심 결과

|label|positive|cluster|발생 시장|matched|cluster 첫 시점 matched|
|---|---|---|---|---|---|
|L1|1150|235|32|661|109|
|L2|541|62|14|303|32|
|L3|944|23|11|102|2|

### 반복 후보: 최근 15분·30분 고저폭

양쪽 값이 있는 pair만 사용한다. 범위는 (high/low-1)*100, 차이는 %p다.
|label|feature|view|유효 pair|시장|positive 중앙값|control 중앙값|차이 %p|
|---|---|---|---|---|---|---|---|
|L1|range_30m_pct|all|504|14|5.000|0.701|+4.299|
|L1|range_15m_pct|all|572|15|3.396|0.486|+2.910|
|L1|range_30m_pct|cluster_representatives|76|10|4.010|0.635|+3.375|
|L1|range_15m_pct|cluster_representatives|88|13|2.794|0.507|+2.287|
|L1|range_30m_pct|market_balanced|504|14|3.364|1.080|+2.284|
|L1|range_15m_pct|market_balanced|572|15|2.174|0.647|+1.527|
|L1|range_30m_pct|without_top_market|304|13|5.442|0.722|+4.720|
|L1|range_15m_pct|without_top_market|340|14|3.630|0.530|+3.100|
|L2|range_30m_pct|all|226|7|5.185|0.585|+4.600|
|L2|range_15m_pct|all|262|8|3.532|0.433|+3.099|
|L2|range_30m_pct|cluster_representatives|24|7|4.961|0.668|+4.293|
|L2|range_15m_pct|cluster_representatives|27|7|3.908|0.434|+3.474|
|L2|range_30m_pct|market_balanced|226|7|5.085|0.931|+4.154|
|L2|range_15m_pct|market_balanced|262|8|4.167|0.748|+3.419|
|L2|range_30m_pct|without_top_market|122|6|6.319|0.806|+5.513|
|L2|range_15m_pct|without_top_market|134|7|3.910|0.527|+3.384|

### 사람이 읽는 해석

- 사후 저점을 쓰지 않아도 최근 고저폭이 큰 시점의 차이는 남는다. L1/L2에서 같은 방향이며 cluster 대표와 시장 균형, 최대 시장 제외 비교에서도 남는다.
- 60분 수익률은 전체 observation에서는 positive가 높지만 cluster 첫 시점만 남기면 반대로 낮아진다. 상승 모멘텀을 일관된 전조로 분류하지 않는다.
- L1 거래대금 배율 차이는 있으나 L2 cluster 대표 유효 pair는 20 미만이다. 거래대금 폭증이 두 label에 반복된다는 결론은 내리지 않는다.
- 고점 돌파 역시 cluster 대표에서 우위가 유지되지 않는다. L3는 cluster 첫 시점 매칭이 2쌍뿐이므로 INSUFFICIENT_SAMPLE 참고용이다.
- 고저폭은 상방뿐 아니라 하방 움직임도 커지는 변동성 상태일 수 있다. 지금 결과는 방향성 진입 시점이나 기대수익을 검증한 것이 아니다.
- 15분/30분 범위는 서로 중첩된 feature이고 L1/L2도 독립 표본이 아니다. 시간 분리 검증이 없으므로 PROMISING은 반복되는 기술적 차이라는 뜻이다.
- absolute MA5/MA20은 코인 단위 가격이 달라 시장 간 크기를 비교할 수 없어 후보 선정에서 제외했다. 원시 거래대금도 매칭 진단으로만 보존한다.
- 각 feature의 시장 균형은 그 feature가 양쪽 모두 유효한 positive 시장들에 동일 총 가중치를 준다. 제외 시장이 control 쪽에 있는 pair도 제거했다.

## 사전에 고정한 연구 규칙

- grid: 5 minute calendar timestamps, [research_start,research_end); all feature candles closed at/before t
- labels: Anchor exact close at t. Future highs in (t,t+H]. Missing non-hit => UNKNOWN, not negative. Hit with partial future => positive but excluded from matching.
- matching: Same timestamp, different market; past360 and baseline120 coverage>=80%, exact anchor, future coverage=100% symmetrically for both classes. Prior trade-value baseline [t-360m,t-240m], ratio 1/3..3. Greedy by closest log-liquidity, deterministic market ties.
- reuse: No duplicate negative at same timestamp and label; overlapping future intervals across different timestamps remain dependent.
- cluster: Connected overlapping positive [t,t+H] intervals per market/label; conservative clusters, not independently verified price episodes. First positive fixed BEFORE matching; never replace unmatched representative.
- balance: Equal total weight per positive market among feature-valid pairs. Original paired controls retain those weights.
- sensitivity: Remove highest positive-count market from BOTH positive and control sides; no rematching.
- candidates: All/cluster-representative/equal-market/exclude-top: >=20 valid pairs and >=3 positive markets; same nonzero direction. Existing boolean thresholds only. No new feature threshold search.
- limitations: Descriptive, no held-out validation; labels and adjacent observations correlated. Full-future requirement favors active periods; label rates are observed-grid rates, not trading probabilities. Cluster count is not independent market count.

## L1

labels {'negative': 28865, 'unknown': 171585, 'positive': 1150}; positive 시장 32, cluster 235, matched 661
matching eligible 695, 미매칭 {'no_same_time_liquidity_negative': 34, 'case_history_or_future_incomplete': 455}
positive 시장 분포 {'KRW-FLOCK': 335, 'KRW-SKR': 173, 'KRW-ICX': 83, 'KRW-CPOOL': 72, 'KRW-LA': 69, 'KRW-CHIP': 48, 'KRW-ZORA': 46, 'KRW-ONG': 46, 'KRW-MIRA': 39, 'KRW-ZKC': 37, 'KRW-0G': 33, 'KRW-MANTRA': 28, 'KRW-RVN': 20, 'KRW-PUMP': 14, 'KRW-SAND': 14, 'KRW-ENA': 11, 'KRW-UNI': 10, 'KRW-NEAR': 10, 'KRW-TREE': 9, 'KRW-PEPE': 7, 'KRW-PRL': 6, 'KRW-ZKP': 6, 'KRW-TRUMP': 5, 'KRW-DOGE': 5, 'KRW-LINK': 5, 'KRW-DATA': 4, 'KRW-O': 4, 'KRW-ETH': 4, 'KRW-ENS': 4, 'KRW-KAITO': 1, 'KRW-WLD': 1, 'KRW-ERA': 1}; 제외 시장 KRW-FLOCK

### all: 661 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 650 | 20 | 0 | 0 | 0 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 648 | 19 | 0.11855 | 0 | 0.11855 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 642 | 20 | 0.25387 | 0 | 0.25387 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 635 | 20 | 0.83037 | 0.029274 | 0.80109 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 630 | 18 | 1.8066e+08 | 1.2373e+08 | 5.6931e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 391 | 11 | 2.3603e+08 | 1.9086e+08 | 4.5174e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 384 | 11 | 0.85052 | 0.72333 | 0.12719 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 597 | 16 | 3.631 | -0.48538 | 4.1164 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 572 | 15 | 0.99117 | 1.0191 | -0.027957 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 630 | 18 | 75.12 | 1932 | -1856.9 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 549 | 15 | 75.04 | 1936 | -1861 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 549 | 15 | 1.0004 | 1 | 0.0003132 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 528 | 15 | 0.037827 | 0.00533 | 0.032497 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 504 | 14 | 5 | 0.70102 | 4.299 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 396 | 11 | -3.7875 | -8.9525 | 5.165 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 389 | 11 | 2.9197 | 0.37076 | 2.5489 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 635 | 20 | 0.83061 | 0 | 0.83061 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 635 | 20 | 0.76768 | 0.015738 | 0.75194 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 634 | 20 | 1.4426 | 0 | 1.4426 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 572 | 15 | 3.3959 | 0.48594 | 2.9099 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 396 | 11 | 7.362 | 0.83709 | 6.5249 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 396 | 11 | -2.7876 | -0.36515 | -2.4224 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 650 | 20 | 0 | 0 | 0 | 2.1538 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 648 | 19 | 1 | 0 | 1 | 6.4815 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 642 | 20 | 1 | 0 | 1 | 4.9844 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 635 | 20 | 1 | 1 | 0 | 8.3465 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 384 | 11 | 0 | 0 | 0 | 0.52083 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 597 | 16 | 1 | 0 | 1 | 1.005 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 572 | 15 | 0 | 1 | -1 | -0.87413 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 549 | 15 | 1 | 1 | 0 | -0.18215 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 528 | 15 | 1 | 1 | 0 | -0.56818 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 396 | 11 | 0 | 0 | 0 | 5.5556 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 389 | 11 | 0 | 0 | 0 | 1.5424 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 635 | 20 | 1 | 0 | 1 | 11.654 | SUFFICIENT_FOR_DESCRIPTION |
### cluster_representatives: 109 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 107 | 17 | -0.66667 | -0.029317 | -0.63735 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 108 | 18 | -0.92309 | 0 | -0.92309 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 106 | 18 | -0.74732 | 0 | -0.74732 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 107 | 17 | -0.46893 | 0 | -0.46893 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 101 | 17 | 1.0191e+08 | 1.3458e+08 | -3.2674e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 63 | 9 | 2.2043e+08 | 1.8181e+08 | 3.8614e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 62 | 9 | 0.78407 | 0.69182 | 0.092255 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 94 | 14 | 6.6956 | 8.6178 | -1.9223 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 88 | 13 | 0.91546 | 1.1747 | -0.25929 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 101 | 17 | 83.64 | 2652.4 | -2568.8 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 88 | 13 | 83.037 | 2737.2 | -2654.1 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 88 | 13 | 0.9957 | 0.99995 | -0.0042433 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 85 | 13 | -0.14615 | 0.0070198 | -0.15317 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 76 | 10 | 4.0098 | 0.63531 | 3.3745 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 64 | 9 | -13.476 | -12.231 | -1.2452 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 63 | 9 | 3.6217 | 0.38771 | 3.234 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 107 | 17 | -0.24631 | 0 | -0.24631 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 107 | 17 | -0.41561 | -0.010051 | -0.40556 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 107 | 17 | 0 | 0.072939 | -0.072939 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 88 | 13 | 2.7944 | 0.50695 | 2.2875 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 64 | 9 | 5.8871 | 0.84553 | 5.0416 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 64 | 9 | -3.6197 | -0.3683 | -3.2514 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 107 | 17 | 0 | 0 | 0 | -17.757 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 108 | 18 | 0 | 0 | 0 | -14.815 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 106 | 18 | 0 | 0 | 0 | -20.755 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 107 | 17 | 0 | 0 | 0 | -8.4112 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 62 | 9 | 0 | 0 | 0 | -12.903 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 94 | 14 | 1 | 1 | 0 | -1.0638 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 88 | 13 | 0 | 1 | -1 | -4.5455 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 88 | 13 | 0 | 0 | 0 | -23.864 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 85 | 13 | 0 | 1 | -1 | -22.353 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 64 | 9 | 0 | 0 | 0 | -3.125 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 63 | 9 | 0 | 0 | 0 | -3.1746 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 107 | 17 | 0 | 0 | 0 | -2.8037 | SUFFICIENT_FOR_DESCRIPTION |
### market_balanced: 661 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 650 | 20 | 0 | 0 | 0 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 648 | 19 | 0.32584 | 0 | 0.32584 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 642 | 20 | 0.34843 | -0.028986 | 0.37742 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 635 | 20 | 0.86957 | 0.14646 | 0.72311 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 630 | 18 | 8.319e+07 | 8.843e+07 | -5.2397e+06 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 391 | 11 | 2.1289e+08 | 1.9755e+08 | 1.5337e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 384 | 11 | 1.0042 | 0.63655 | 0.3676 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 597 | 16 | 9.7653 | 6.4462 | 3.3191 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 572 | 15 | 0.9022 | 1.0786 | -0.17639 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 630 | 18 | 116.6 | 247 | -130.4 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 549 | 15 | 91.515 | 1856.8 | -1765.3 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 549 | 15 | 1.0019 | 1.0001 | 0.0018155 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 528 | 15 | 0.071419 | 0.010935 | 0.060484 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 504 | 14 | 3.3643 | 1.0799 | 2.2844 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 396 | 11 | 4.5821 | -8.7459 | 13.328 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 389 | 11 | 2.5862 | 0.57845 | 2.0078 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 635 | 20 | 0.82816 | 0 | 0.82816 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 635 | 20 | 0.81686 | 0.057534 | 0.75932 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 634 | 20 | 1.6398 | 0.058703 | 1.5811 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 572 | 15 | 2.1739 | 0.64655 | 1.5274 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 396 | 11 | 6.7616 | 1.2411 | 5.5205 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 396 | 11 | -2.521 | -0.57513 | -1.9459 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 650 | 20 | 0 | 0 | 0 | 7.6428 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 648 | 19 | 1 | 0 | 1 | 17.757 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 642 | 20 | 1 | 0 | 1 | 16.579 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 635 | 20 | 1 | 1 | 0 | 14.452 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 384 | 11 | 0 | 0 | 0 | 16.423 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 597 | 16 | 1 | 1 | 0 | 0.28717 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 572 | 15 | 0 | 1 | -1 | -7.6463 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 549 | 15 | 1 | 1 | 0 | 8.0159 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 528 | 15 | 1 | 1 | 0 | 3.5604 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 396 | 11 | 1 | 0 | 1 | 7.2008 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 389 | 11 | 0 | 0 | 0 | 1.2016 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 635 | 20 | 1 | 0 | 1 | 23.521 | SUFFICIENT_FOR_DESCRIPTION |
### without_top_market: 391 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 384 | 19 | 0 | 0 | 0 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 385 | 18 | 0.34014 | 0 | 0.34014 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 384 | 19 | 0.31067 | 0.058574 | 0.25209 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 378 | 19 | 0.88121 | 0.093406 | 0.78781 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 372 | 17 | 1.7204e+08 | 1.1583e+08 | 5.6204e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 242 | 10 | 2.3505e+08 | 1.9639e+08 | 3.8656e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 239 | 10 | 0.8975 | 0.70864 | 0.18886 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 354 | 15 | 4.7282 | -0.87526 | 5.6034 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 340 | 14 | 0.98334 | 1.017 | -0.033668 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 372 | 17 | 40.61 | 3024.7 | -2984.1 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 331 | 14 | 40.715 | 3081.4 | -3040.7 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 331 | 14 | 1.0017 | 1.0001 | 0.0015451 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 320 | 14 | 0.085211 | 0.014088 | 0.071123 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 304 | 13 | 5.4422 | 0.72196 | 4.7202 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 244 | 10 | -3.9509 | -8.5334 | 4.5826 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 243 | 10 | 2.9412 | 0.4309 | 2.5103 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 378 | 19 | 0.94205 | 0.0038434 | 0.9382 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 378 | 19 | 0.86831 | 0.022821 | 0.84549 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 370 | 19 | 1.4986 | 0.02978 | 1.4688 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 340 | 14 | 3.6298 | 0.52978 | 3.1 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 244 | 10 | 8.1818 | 0.9539 | 7.2279 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 244 | 10 | -2.8571 | -0.42345 | -2.4337 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 384 | 19 | 0 | 0 | 0 | 2.8646 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 385 | 18 | 1 | 0 | 1 | 6.7532 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 384 | 19 | 1 | 1 | 0 | 1.8229 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 378 | 19 | 1 | 1 | 0 | 5.5556 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 239 | 10 | 0 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 354 | 15 | 1 | 0.5 | 0.5 | 1.4124 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 340 | 14 | 0 | 1 | -1 | -2.3529 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 331 | 14 | 1 | 1 | 0 | 0.60423 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 320 | 14 | 1 | 1 | 0 | -0.3125 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 244 | 10 | 0 | 0 | 0 | 3.2787 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 243 | 10 | 0 | 0 | 0 | 1.6461 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 378 | 19 | 1 | 1 | 0 | 11.64 | SUFFICIENT_FOR_DESCRIPTION |

네 비교에서 같은 방향을 유지한 후보: [{'section': 'values', 'feature': 'trade_value_ratio', 'direction': 'higher', 'differences': {'all': 0.12718857240032078, 'cluster_representatives': 0.09225467637158014, 'market_balanced': 0.36760131920610173, 'without_top_market': 0.1888615306171979}}, {'section': 'values', 'feature': 'trade_value_acceleration', 'direction': 'lower', 'differences': {'all': -0.027957025791209844, 'cluster_representatives': -0.2592886571682391, 'market_balanced': -0.1763899408424855, 'without_top_market': -0.03366837021583857}}, {'section': 'values', 'feature': 'range_30m_pct', 'direction': 'higher', 'differences': {'all': 4.298979306006712, 'cluster_representatives': 3.37451300578272, 'market_balanced': 2.284355534619875, 'without_top_market': 4.7202163615772115}}, {'section': 'values', 'feature': 'distance_to_prior_high_pct', 'direction': 'higher', 'differences': {'all': 2.5489453173326737, 'cluster_representatives': 3.2340178860217783, 'market_balanced': 2.0077542573615714, 'without_top_market': 2.5102746546448618}}, {'section': 'values', 'feature': 'range_15m_pct', 'direction': 'higher', 'differences': {'all': 2.9099246698690795, 'cluster_representatives': 2.2874575152062593, 'market_balanced': 1.527361319340348, 'without_top_market': 3.099993349360386}}, {'section': 'values', 'feature': 'range_60m_pct', 'direction': 'higher', 'differences': {'all': 6.5248720817857375, 'cluster_representatives': 5.041599139083319, 'market_balanced': 5.520486096925659, 'without_top_market': 7.2279231102760475}}, {'section': 'values', 'feature': 'drawdown_from_high_60m_pct', 'direction': 'lower', 'differences': {'all': -2.4223965659003976, 'cluster_representatives': -3.251372496914823, 'market_balanced': -1.9458825945906755, 'without_top_market': -2.4336919865583506}}, {'section': 'flags', 'feature': 'trade_value_accelerating', 'direction': 'lower', 'differences': {'all': -0.8741258741258806, 'cluster_representatives': -4.545454545454541, 'market_balanced': -7.6463229290419825, 'without_top_market': -2.352941176470585}}]

## L2

labels {'negative': 22225, 'unknown': 178834, 'positive': 541}; positive 시장 14, cluster 62, matched 303
matching eligible 320, 미매칭 {'case_history_or_future_incomplete': 221, 'no_same_time_liquidity_negative': 17}
positive 시장 분포 {'KRW-FLOCK': 214, 'KRW-SKR': 68, 'KRW-ICX': 68, 'KRW-CPOOL': 48, 'KRW-ONG': 33, 'KRW-0G': 20, 'KRW-LA': 20, 'KRW-MIRA': 18, 'KRW-ZORA': 18, 'KRW-MANTRA': 15, 'KRW-ZKC': 11, 'KRW-TREE': 4, 'KRW-CHIP': 3, 'KRW-PUMP': 1}; 제외 시장 KRW-FLOCK

### all: 303 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 298 | 8 | 0 | 0 | 0 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 296 | 8 | 0 | 0 | 0 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 294 | 8 | 0.32734 | 0 | 0.32734 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 293 | 8 | 1.0135 | 0.0293 | 0.98421 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 290 | 8 | 1.7585e+08 | 1.1698e+08 | 5.887e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 181 | 7 | 2.2813e+08 | 1.8159e+08 | 4.6547e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 177 | 7 | 0.81799 | 0.71782 | 0.10017 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 276 | 8 | -6.7903 | -3.3798 | -3.4106 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 262 | 8 | 1.0564 | 0.94384 | 0.11252 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 290 | 8 | 82.75 | 1938.3 | -1855.5 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 248 | 7 | 85.575 | 3045.4 | -2959.8 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 248 | 7 | 0.99958 | 0.99999 | -0.0004035 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 237 | 7 | 0.03651 | 0.0029332 | 0.033576 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 226 | 7 | 5.1852 | 0.58535 | 4.5998 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 184 | 7 | 2.0547 | -8.5334 | 10.588 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 180 | 7 | 2.8536 | 0.38196 | 2.4716 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 293 | 8 | 0.93199 | 0.0023491 | 0.92965 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 293 | 8 | 0.82463 | 0.012823 | 0.81181 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 293 | 8 | 1.049 | 0 | 1.049 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 262 | 8 | 3.5318 | 0.43253 | 3.0993 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 184 | 7 | 7.2258 | 0.8228 | 6.403 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 184 | 7 | -2.8155 | -0.37714 | -2.4384 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 298 | 8 | 0 | 0 | 0 | 5.0336 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 296 | 8 | 0 | 0 | 0 | 4.7297 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 294 | 8 | 1 | 0 | 1 | 9.1837 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 293 | 8 | 1 | 1 | 0 | 8.5324 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 177 | 7 | 0 | 0 | 0 | 6.2147 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 276 | 8 | 0 | 0 | 0 | -3.9855 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 262 | 8 | 1 | 0 | 1 | 2.2901 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 248 | 7 | 0 | 0 | 0 | 0.80645 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 237 | 7 | 1 | 1 | 0 | 1.6878 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 184 | 7 | 1 | 0 | 1 | 9.7826 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 180 | 7 | 0 | 0 | 0 | 3.3333 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 293 | 8 | 1 | 1 | 0 | 9.8976 | SUFFICIENT_FOR_DESCRIPTION |
### cluster_representatives: 32 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 31 | 7 | -0.95847 | 0 | -0.95847 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 32 | 7 | -0.72866 | -0.10428 | -0.62438 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 32 | 7 | -1.8845 | -0.089565 | -1.7949 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 32 | 7 | -1.5346 | 0 | -1.5346 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 30 | 7 | 2.177e+08 | 1.6933e+08 | 4.8365e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 20 | 6 | 2.3779e+08 | 2.5829e+08 | -2.0499e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 19 | 6 | 1.1586 | 0.82595 | 0.33265 | NULL | INSUFFICIENT_SAMPLE |
| trade_value_change_pct | 29 | 7 | -10.565 | 10.711 | -21.276 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 27 | 7 | 1.2299 | 0.81242 | 0.41745 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 30 | 7 | 81.41 | 1899.2 | -1817.8 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 26 | 7 | 84.92 | 1904.8 | -1819.9 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 26 | 7 | 0.9933 | 0.99968 | -0.0063771 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 25 | 7 | -0.34414 | -0.015789 | -0.32835 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 24 | 7 | 4.9609 | 0.66798 | 4.2929 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 19 | 6 | 1.6181 | -8.9543 | 10.572 | NULL | INSUFFICIENT_SAMPLE |
| distance_to_prior_high_pct | 19 | 6 | 4.811 | 0.32544 | 4.4856 | NULL | INSUFFICIENT_SAMPLE |
| alt_relative_60m_pct | 32 | 7 | -1.4693 | -0.1029 | -1.3664 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 32 | 7 | -1.5727 | -0.10573 | -1.467 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 30 | 7 | -0.50858 | -0.13408 | -0.3745 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 27 | 7 | 3.908 | 0.43415 | 3.4739 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 19 | 6 | 5.7572 | 0.92593 | 4.8313 | NULL | INSUFFICIENT_SAMPLE |
| drawdown_from_high_60m_pct | 19 | 6 | -4.5902 | -0.32439 | -4.2658 | NULL | INSUFFICIENT_SAMPLE |
| return_5m_positive | 31 | 7 | 0 | 0 | 0 | -22.581 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 32 | 7 | 0 | 0 | 0 | -9.375 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 32 | 7 | 0 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 32 | 7 | 0 | 0 | 0 | -9.375 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 19 | 6 | 0 | 0 | 0 | 15.789 | INSUFFICIENT_SAMPLE |
| trade_value_increasing | 29 | 7 | 0 | 1 | -1 | -17.241 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 27 | 7 | 1 | 0 | 1 | 3.7037 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 26 | 7 | 0 | 0 | 0 | -23.077 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 25 | 7 | 0 | 0 | 0 | -8 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 19 | 6 | 1 | 0 | 1 | 5.2632 | INSUFFICIENT_SAMPLE |
| prior_high_breakout | 19 | 6 | 0 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| relative_strength_positive | 32 | 7 | 0 | 0 | 0 | 3.125 | SUFFICIENT_FOR_DESCRIPTION |
### market_balanced: 303 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 298 | 8 | 0.11455 | 0 | 0.11455 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 296 | 8 | 0.29499 | 0 | 0.29499 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 294 | 8 | 0.69849 | 0 | 0.69849 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 293 | 8 | 1.4235 | 0.069686 | 1.3538 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 290 | 8 | 1.5608e+08 | 1.1901e+08 | 3.7069e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 181 | 7 | 1.7898e+08 | 1.6731e+08 | 1.1668e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 177 | 7 | 0.90984 | 0.73851 | 0.17133 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 276 | 8 | 1.5031 | 5.2253 | -3.7222 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 262 | 8 | 0.85937 | 1.0758 | -0.2164 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 290 | 8 | 45.58 | 3039.2 | -2993.6 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 248 | 7 | 87.09 | 3065.2 | -2978.1 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 248 | 7 | 1.0017 | 0.99995 | 0.0017747 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 237 | 7 | 0.10183 | 0 | 0.10183 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 226 | 7 | 5.0847 | 0.93081 | 4.1539 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 184 | 7 | 11.801 | 10.995 | 0.80666 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 180 | 7 | 2.5723 | 0.58634 | 1.986 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 293 | 8 | 1.5606 | 0.0038415 | 1.5568 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 293 | 8 | 1.463 | -0.00035787 | 1.4633 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 293 | 8 | 2.0339 | -0.052994 | 2.0869 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 262 | 8 | 4.1667 | 0.74797 | 3.4187 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 184 | 7 | 7.6923 | 1.6097 | 6.0826 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 184 | 7 | -2.5814 | -0.58292 | -1.9984 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 298 | 8 | 1 | 0 | 1 | 9.0082 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 296 | 8 | 1 | 0 | 1 | 7.3004 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 294 | 8 | 1 | 0 | 1 | 10.77 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 293 | 8 | 1 | 1 | 0 | 14.103 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 177 | 7 | 0 | 0 | 0 | 4.3633 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 276 | 8 | 1 | 1 | 0 | -2.5205 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 262 | 8 | 0 | 1 | -1 | -7.6847 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 248 | 7 | 1 | 0 | 1 | 8.1057 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 237 | 7 | 1 | 0 | 1 | 5.0608 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 184 | 7 | 1 | 1 | 0 | 3.9691 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 180 | 7 | 0 | 0 | 0 | 3.5026 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 293 | 8 | 1 | 1 | 0 | 21.316 | SUFFICIENT_FOR_DESCRIPTION |
### without_top_market: 147 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 146 | 7 | 0 | 0 | 0 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 145 | 7 | 0.34722 | 0.052219 | 0.295 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 144 | 7 | 0.77221 | 0.055418 | 0.71679 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 142 | 7 | 1.5625 | 0.11833 | 1.4442 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 143 | 7 | 1.8423e+08 | 1.4457e+08 | 3.9659e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 101 | 6 | 2.2345e+08 | 2.0087e+08 | 2.2577e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 100 | 6 | 0.91473 | 0.73673 | 0.178 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 139 | 7 | -6.0477 | -2.3596 | -3.6882 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 134 | 7 | 1.0408 | 0.98015 | 0.060609 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 143 | 7 | 38.46 | 3090.2 | -3051.7 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 129 | 6 | 40.305 | 3091.8 | -3051.5 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 129 | 6 | 1.0022 | 1 | 0.0021689 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 126 | 6 | 0.078177 | 0.015891 | 0.062286 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 122 | 6 | 6.3186 | 0.80591 | 5.5127 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 104 | 6 | 11.346 | 3.134 | 8.2123 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 102 | 6 | 2.9412 | 0.58634 | 2.3548 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 142 | 7 | 1.6094 | 0.017438 | 1.5919 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 142 | 7 | 1.566 | -0.021487 | 1.5875 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 142 | 7 | 1.6969 | 0 | 1.6969 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 134 | 7 | 3.9104 | 0.52666 | 3.3838 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 104 | 6 | 8.1818 | 1.2671 | 6.9147 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 104 | 6 | -2.8876 | -0.58292 | -2.3047 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 146 | 7 | 0 | 0 | 0 | 4.7945 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 145 | 7 | 1 | 1 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 144 | 7 | 1 | 1 | 0 | 7.6389 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 142 | 7 | 1 | 1 | 0 | 14.085 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 100 | 6 | 0 | 0 | 0 | 6 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 139 | 7 | 0 | 0 | 0 | -2.8777 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 134 | 7 | 1 | 0 | 1 | 1.4925 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 129 | 6 | 1 | 1 | 0 | 3.876 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 126 | 6 | 1 | 1 | 0 | -2.381 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 104 | 6 | 1 | 1 | 0 | 7.6923 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 102 | 6 | 0 | 0 | 0 | 3.9216 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 142 | 7 | 1 | 1 | 0 | 19.014 | SUFFICIENT_FOR_DESCRIPTION |

네 비교에서 같은 방향을 유지한 후보: [{'section': 'values', 'feature': 'trade_value_change_pct', 'direction': 'lower', 'differences': {'all': -3.410594012935436, 'cluster_representatives': -21.275666898766055, 'market_balanced': -3.7221792640248053, 'without_top_market': -3.6881702789256288}}, {'section': 'values', 'feature': 'range_30m_pct', 'direction': 'higher', 'differences': {'all': 4.59983195061281, 'cluster_representatives': 4.292921643667913, 'market_balanced': 4.15393595818192, 'without_top_market': 5.512711758570832}}, {'section': 'values', 'feature': 'range_15m_pct', 'direction': 'higher', 'differences': {'all': 3.0993160068334857, 'cluster_representatives': 3.4738925761432116, 'market_balanced': 3.4186991869918693, 'without_top_market': 3.38375885847797}}, {'section': 'flags', 'feature': 'trade_value_increasing', 'direction': 'lower', 'differences': {'all': -3.9855072463768124, 'cluster_representatives': -17.24137931034483, 'market_balanced': -2.5204888524753, 'without_top_market': -2.877697841726623}}, {'section': 'flags', 'feature': 'relative_strength_positive', 'direction': 'higher', 'differences': {'all': 9.897610921501709, 'cluster_representatives': 3.125, 'market_balanced': 21.315975001819364, 'without_top_market': 19.01408450704225}}]

## L3

labels {'negative': 10497, 'unknown': 190159, 'positive': 944}; positive 시장 11, cluster 23, matched 102
matching eligible 171, 미매칭 {'case_history_or_future_incomplete': 773, 'no_same_time_liquidity_negative': 69}
positive 시장 분포 {'KRW-FLOCK': 343, 'KRW-ICX': 182, 'KRW-SKR': 103, 'KRW-CPOOL': 97, 'KRW-ONG': 71, 'KRW-ZORA': 46, 'KRW-CHIP': 41, 'KRW-LA': 27, 'KRW-MANTRA': 18, 'KRW-TREE': 13, 'KRW-0G': 3}; 제외 시장 KRW-FLOCK

### all: 102 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 102 | 5 | 0 | -0.029248 | 0.029248 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 102 | 5 | 0 | 0.029386 | -0.029386 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 101 | 5 | 0 | 0.058531 | -0.058531 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 100 | 5 | -0.50806 | 0.11375 | -0.62181 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 100 | 5 | 8.071e+07 | 2.0895e+08 | -1.2824e+08 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 83 | 4 | 9.8532e+07 | 2.2239e+08 | -1.2386e+08 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 83 | 4 | 0.82493 | 0.75007 | 0.074868 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 98 | 5 | 2.5578 | -13.255 | 15.813 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 97 | 5 | 0.89515 | 1.1841 | -0.28891 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 100 | 5 | 33.94 | 3.4058e+06 | -3.4058e+06 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 96 | 5 | 33.668 | 3.403e+06 | -3.4029e+06 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 96 | 5 | 0.99918 | 1 | -0.00085895 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 95 | 5 | -0.030497 | 0.0029332 | -0.03343 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 94 | 5 | 3.4591 | 0.48578 | 2.9733 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 85 | 4 | 2.1053 | 8.694 | -6.5888 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 84 | 4 | 3.173 | 0.258 | 2.915 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 100 | 5 | -0.64061 | -0.036404 | -0.60421 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 100 | 5 | -0.6263 | 0.016829 | -0.64312 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 101 | 5 | -2.3729 | 0.1173 | -2.4902 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 97 | 5 | 2.454 | 0.30976 | 2.1442 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 85 | 4 | 4.6296 | 0.62167 | 4.008 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 85 | 4 | -3.0999 | -0.25733 | -2.8426 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 102 | 5 | 0 | 0 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 102 | 5 | 0 | 1 | -1 | -13.725 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 101 | 5 | 0 | 1 | -1 | -12.871 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 100 | 5 | 0 | 1 | -1 | -23 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 83 | 4 | 0 | 0 | 0 | -3.6145 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 98 | 5 | 1 | 0 | 1 | 8.1633 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 97 | 5 | 0 | 1 | -1 | -11.34 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 96 | 5 | 0 | 1 | -1 | -6.25 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 95 | 5 | 0 | 1 | -1 | -8.4211 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 85 | 4 | 1 | 1 | 0 | -7.0588 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 84 | 4 | 0 | 0 | 0 | 3.5714 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 100 | 5 | 0 | 0 | 0 | -4 | SUFFICIENT_FOR_DESCRIPTION |
### cluster_representatives: 2 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 2 | 2 | -0.7145 | -0.079327 | -0.63517 | NULL | INSUFFICIENT_SAMPLE |
| return_15m_pct | 2 | 2 | -1.2178 | -0.16661 | -1.0511 | NULL | INSUFFICIENT_SAMPLE |
| return_30m_pct | 2 | 2 | -1.5018 | -0.32913 | -1.1727 | NULL | INSUFFICIENT_SAMPLE |
| return_60m_pct | 2 | 2 | -2.9173 | -0.49322 | -2.4241 | NULL | INSUFFICIENT_SAMPLE |
| trade_value_5m | 2 | 2 | 1.5709e+08 | 6.4818e+08 | -4.9109e+08 | NULL | INSUFFICIENT_SAMPLE |
| prior_mean_trade_value_5m | 2 | 2 | 2.1456e+08 | 6.1878e+08 | -4.0422e+08 | NULL | INSUFFICIENT_SAMPLE |
| trade_value_ratio | 2 | 2 | 1.3626 | 1.0812 | 0.28137 | NULL | INSUFFICIENT_SAMPLE |
| trade_value_change_pct | 2 | 2 | 52.197 | -6.831 | 59.028 | NULL | INSUFFICIENT_SAMPLE |
| trade_value_acceleration | 2 | 2 | 2.3796 | 0.95146 | 1.4282 | NULL | INSUFFICIENT_SAMPLE |
| ma5 | 2 | 2 | 51.57 | 1872.4 | -1820.8 | NULL | INSUFFICIENT_SAMPLE |
| ma20 | 2 | 2 | 51.965 | 1873.2 | -1821.2 | NULL | INSUFFICIENT_SAMPLE |
| ma5_ma20_ratio | 2 | 2 | 0.99074 | 0.99957 | -0.0088314 | NULL | INSUFFICIENT_SAMPLE |
| ma20_slope_5m_pct | 2 | 2 | -0.51799 | -0.018306 | -0.49968 | NULL | INSUFFICIENT_SAMPLE |
| range_30m_pct | 2 | 2 | 3.7891 | 0.51452 | 3.2745 | NULL | INSUFFICIENT_SAMPLE |
| range_change_pct | 2 | 2 | -20.124 | 34.352 | -54.476 | NULL | INSUFFICIENT_SAMPLE |
| distance_to_prior_high_pct | 2 | 2 | 5.7824 | 0.60225 | 5.1801 | NULL | INSUFFICIENT_SAMPLE |
| alt_relative_60m_pct | 2 | 2 | -2.5495 | -0.05772 | -2.4918 | NULL | INSUFFICIENT_SAMPLE |
| btc_relative_60m_pct | 2 | 2 | -2.8649 | -0.44078 | -2.4241 | NULL | INSUFFICIENT_SAMPLE |
| return_120m_pct | 2 | 2 | -3.4704 | -1.102 | -2.3683 | NULL | INSUFFICIENT_SAMPLE |
| range_15m_pct | 2 | 2 | 2.7979 | 0.35211 | 2.4458 | NULL | INSUFFICIENT_SAMPLE |
| range_60m_pct | 2 | 2 | 6.9856 | 0.68017 | 6.3055 | NULL | INSUFFICIENT_SAMPLE |
| drawdown_from_high_60m_pct | 2 | 2 | -5.4588 | -0.59669 | -4.8622 | NULL | INSUFFICIENT_SAMPLE |
| return_5m_positive | 2 | 2 | 0 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| return_15m_positive | 2 | 2 | 0 | 0.5 | -0.5 | -50 | INSUFFICIENT_SAMPLE |
| return_30m_positive | 2 | 2 | 0 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| return_60m_positive | 2 | 2 | 0 | 0.5 | -0.5 | -50 | INSUFFICIENT_SAMPLE |
| trade_value_double | 2 | 2 | 0.5 | 0 | 0.5 | 50 | INSUFFICIENT_SAMPLE |
| trade_value_increasing | 2 | 2 | 1 | 0.5 | 0.5 | 50 | INSUFFICIENT_SAMPLE |
| trade_value_accelerating | 2 | 2 | 0.5 | 0.5 | 0 | 0 | INSUFFICIENT_SAMPLE |
| ma5_above_ma20 | 2 | 2 | 0 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| ma20_rising | 2 | 2 | 0 | 0.5 | -0.5 | -50 | INSUFFICIENT_SAMPLE |
| range_expanding | 2 | 2 | 0 | 1 | -1 | -100 | INSUFFICIENT_SAMPLE |
| prior_high_breakout | 2 | 2 | 0 | 0 | 0 | 0 | INSUFFICIENT_SAMPLE |
| relative_strength_positive | 2 | 2 | 0 | 0.5 | -0.5 | -50 | INSUFFICIENT_SAMPLE |
### market_balanced: 102 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 102 | 5 | -0.2994 | -0.052356 | -0.24705 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 102 | 5 | -0.58893 | 0.051573 | -0.6405 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 101 | 5 | 0 | 0.10466 | -0.10466 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 100 | 5 | -0.6689 | 0.23467 | -0.90357 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 100 | 5 | 1.1071e+08 | 1.694e+08 | -5.869e+07 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 83 | 4 | 1.0654e+08 | 2.7783e+08 | -1.7129e+08 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 83 | 4 | 1.0405 | 0.5535 | 0.48697 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 98 | 5 | -15.656 | 20.662 | -36.318 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 97 | 5 | 0.69743 | 1.5121 | -0.81466 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 100 | 5 | 83.74 | 3.2938e+06 | -3.2937e+06 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 96 | 5 | 83.92 | 3.3018e+06 | -3.3018e+06 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 96 | 5 | 0.99768 | 0.99988 | -0.0022007 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 95 | 5 | -0.082604 | -0.0058521 | -0.076752 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 94 | 5 | 3.7288 | 0.516 | 3.2128 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 85 | 4 | 23.76 | -7.2313 | 30.991 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 84 | 4 | 2.7778 | 0.26339 | 2.5144 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 100 | 5 | -0.61651 | 0.0035974 | -0.62011 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 100 | 5 | -0.6735 | 0.002315 | -0.67582 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 101 | 5 | -3.0303 | 0.23454 | -3.2648 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 97 | 5 | 3.003 | 0.33186 | 2.6711 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 85 | 4 | 5.5215 | 0.58703 | 4.9344 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 85 | 4 | -2.7027 | -0.2627 | -2.44 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 102 | 5 | 0 | 0 | 0 | 0.42857 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 102 | 5 | 0 | 1 | -1 | -20.257 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 101 | 5 | 0 | 1 | -1 | -22.062 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 100 | 5 | 0 | 1 | -1 | -38.384 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 83 | 4 | 0 | 0 | 0 | 19.375 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 98 | 5 | 0 | 1 | -1 | -11.561 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 97 | 5 | 0 | 1 | -1 | -30.763 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 96 | 5 | 0 | 0 | 0 | -6.6006 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 95 | 5 | 0 | 0 | 0 | -10.459 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 85 | 4 | 1 | 0 | 1 | 15.973 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 84 | 4 | 0 | 0 | 0 | 2.6014 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 100 | 5 | 0 | 1 | -1 | -15.271 | SUFFICIENT_FOR_DESCRIPTION |
### without_top_market: 82 pairs

|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|
|---|---|---|---|---|---|---|---|
| return_5m_pct | 82 | 4 | 0 | -0.029253 | 0.029253 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_pct | 82 | 4 | 0 | 0.029265 | -0.029265 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_pct | 81 | 4 | 0.26385 | 0.052383 | 0.21147 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_pct | 80 | 4 | -0.15198 | 0.043967 | -0.19594 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_5m | 80 | 4 | 7.423e+07 | 2.2263e+08 | -1.4841e+08 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| prior_mean_trade_value_5m | 63 | 3 | 9.1324e+07 | 2.7184e+08 | -1.8052e+08 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_ratio | 63 | 3 | 0.86761 | 0.73837 | 0.12924 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_change_pct | 78 | 4 | 4.3429 | -1.9592 | 6.3021 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_acceleration | 77 | 4 | 0.96135 | 1.1605 | -0.19912 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5 | 80 | 4 | 32.93 | 3.4122e+06 | -3.4122e+06 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20 | 76 | 4 | 32.84 | 3.4119e+06 | -3.4118e+06 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma5_ma20_ratio | 76 | 4 | 1.0005 | 1.0001 | 0.00040183 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| ma20_slope_5m_pct | 75 | 4 | 0.03474 | 0.0029276 | 0.031813 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_30m_pct | 74 | 4 | 3.4591 | 0.49949 | 2.9596 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_change_pct | 65 | 3 | 4.7737 | 8.2899 | -3.5163 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| distance_to_prior_high_pct | 64 | 3 | 2.7923 | 0.32676 | 2.4656 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| alt_relative_60m_pct | 80 | 4 | -0.29161 | -0.054677 | -0.23694 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| btc_relative_60m_pct | 80 | 4 | -0.33518 | -0.010419 | -0.32476 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_120m_pct | 81 | 4 | -3.01 | 0.058582 | -3.0686 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_15m_pct | 77 | 4 | 2.4922 | 0.32211 | 2.1701 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| range_60m_pct | 65 | 3 | 5.0314 | 0.61747 | 4.414 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| drawdown_from_high_60m_pct | 65 | 3 | -2.7211 | -0.32136 | -2.3997 | NULL | SUFFICIENT_FOR_DESCRIPTION |
| return_5m_positive | 82 | 4 | 0 | 0 | 0 | 6.0976 | SUFFICIENT_FOR_DESCRIPTION |
| return_15m_positive | 82 | 4 | 0 | 1 | -1 | -7.3171 | SUFFICIENT_FOR_DESCRIPTION |
| return_30m_positive | 81 | 4 | 1 | 1 | 0 | -2.4691 | SUFFICIENT_FOR_DESCRIPTION |
| return_60m_positive | 80 | 4 | 0 | 1 | -1 | -11.25 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_double | 63 | 3 | 0 | 0 | 0 | -1.5873 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_increasing | 78 | 4 | 1 | 0 | 1 | 6.4103 | SUFFICIENT_FOR_DESCRIPTION |
| trade_value_accelerating | 77 | 4 | 0 | 1 | -1 | -10.39 | SUFFICIENT_FOR_DESCRIPTION |
| ma5_above_ma20 | 76 | 4 | 1 | 1 | 0 | 0 | SUFFICIENT_FOR_DESCRIPTION |
| ma20_rising | 75 | 4 | 1 | 1 | 0 | -1.3333 | SUFFICIENT_FOR_DESCRIPTION |
| range_expanding | 65 | 3 | 1 | 1 | 0 | -3.0769 | SUFFICIENT_FOR_DESCRIPTION |
| prior_high_breakout | 64 | 3 | 0 | 0 | 0 | 3.125 | SUFFICIENT_FOR_DESCRIPTION |
| relative_strength_positive | 80 | 4 | 0 | 0 | 0 | 2.5 | SUFFICIENT_FOR_DESCRIPTION |

네 비교에서 같은 방향을 유지한 후보: []

## 반복성과 한계

L1/L2 양쪽에서 같은 방향을 유지한 후보: ['range_30m_pct', 'range_15m_pct']
단위가 다른 연속형 차이를 하나의 점수로 정렬하지 않는다. boolean 비교만 %p 단위로 비교 가능하다.
PROMISING이어도 검증된 매수 신호가 아니다. 시간 분리 검증이 없으며 변동성이 큰 시장의 성질과 개별 시점의 예측력을 구분해야 한다.
전체 observations와 episode 대표 통계는 서로 다른 분모다. 시장 균형 결과도 시장 수가 적으면 일반화를 보장하지 않는다.
