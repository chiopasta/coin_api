# Surge Pattern Discovery

Status: EXPLORATORY, NOT VALIDATED.

UTC: 2026-08-12T06:30:00+00:00 to 2026-09-11T06:30:00+00:00
70/30 split: 2026-09-02T06:30:00+00:00

## Method and Limits

- Event: first eligible close whose future high reaches the threshold within the horizon.
- Anchors are retrospective labels, NOT detectable pump-start times or entry signals.
- Require 120 contiguous past minutes and a complete contiguous future horizon.
- Within each market/horizon/threshold, skip the full horizon after an event.
- Different horizons and thresholds may describe the same rally; do not sum them.
- Past snapshots: anchor and 5/15/60/360 minutes earlier; unavailable snapshots remain null.
- Controls: same market and split, within 7 days, preceding hourly value within 1/3 to 3x.
- Control future high must remain below half the event threshold; candidates sampled hourly.
- One control per case, without reuse or overlap with case/control future windows.
- Features use past candles only; event/control labels deliberately use future data.
- Missing candles are not filled. This favors liquid markets and can omit real surges.
- Matching is approximate liquidity/calendar matching, not market-regime adjustment.
- No causal claims, predictive accuracy, significance tests, or parameter optimization.
- Validation is descriptive on already observed data; a fresh period is still required.
- Trade quantity/count is absent; all volume-like features use KRW traded value.

## Event Counts

| Horizon min | Threshold % | Eligible anchors | Events | Matched | Unmatched |
|---|---|---|---|---|---|
| 360 | 20 | 27351 | 5 | 3 | 2 |
| 360 | 50 | 27351 | 1 | 1 | 0 |
| 360 | 100 | 27351 | 0 | 0 | 0 |
| 1440 | 20 | 14654 | 0 | 0 | 0 |
| 1440 | 50 | 14654 | 0 | 0 | 0 |
| 1440 | 100 | 14654 | 0 | 0 | 0 |
| 4320 | 20 | 6336 | 0 | 0 | 0 |
| 4320 | 50 | 6336 | 0 | 0 | 0 |
| 4320 | 100 | 6336 | 0 | 0 | 0 |

## 360m_20pct

| Market | Anchor UTC | Phase | Max future rise % | First hit min |
|---|---|---|---|---|
| KRW-0G | 2026-08-31T03:36:00+00:00 | discovery | 21.34 | 360 |
| KRW-0G | 2026-08-31T21:04:00+00:00 | discovery | 20.13 | 323 |
| KRW-SOPH | 2026-09-07T21:36:00+00:00 | validation | 41.37 | 174 |
| KRW-SOPH | 2026-09-08T03:37:00+00:00 | validation | 45.28 | 62 |
| KRW-SOPH | 2026-09-09T00:38:00+00:00 | validation | 20.73 | 59 |

### Discovery

| Minutes before anchor | Feature | Pairs | Surge % | Control % | Difference pp |
|---|---|---|---|---|---|
| 0 | ma_up | 1 | 100.0 | 0.0 | +100.0 |
| 0 | ma_flat | 1 | 0.0 | 100.0 | -100.0 |
| 0 | ma5_above_ma20 | 1 | 100.0 | 0.0 | +100.0 |
| 0 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 0 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 0 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 0 | repeated_value_bursts | 1 | 0.0 | 0.0 | +0.0 |
| 5 | ma_up | 1 | 100.0 | 0.0 | +100.0 |
| 5 | ma_flat | 1 | 0.0 | 100.0 | -100.0 |
| 5 | ma5_above_ma20 | 1 | 100.0 | 0.0 | +100.0 |
| 5 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 5 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 5 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 5 | repeated_value_bursts | 1 | 0.0 | 0.0 | +0.0 |

### Validation

| Minutes before anchor | Feature | Pairs | Surge % | Control % | Difference pp |
|---|---|---|---|---|---|
| 0 | ma_up | 2 | 100.0 | 0.0 | +100.0 |
| 0 | ma_flat | 2 | 0.0 | 0.0 | +0.0 |
| 0 | ma5_above_ma20 | 2 | 100.0 | 0.0 | +100.0 |
| 0 | tight_box | 2 | 0.0 | 0.0 | +0.0 |
| 0 | value_burst | 2 | 0.0 | 0.0 | +0.0 |
| 0 | quiet_price_value_rise | 2 | 50.0 | 0.0 | +50.0 |
| 0 | repeated_value_bursts | 2 | 50.0 | 0.0 | +50.0 |
| 5 | ma_up | 1 | 100.0 | 0.0 | +100.0 |
| 5 | ma_flat | 1 | 0.0 | 0.0 | +0.0 |
| 5 | ma5_above_ma20 | 1 | 100.0 | 0.0 | +100.0 |
| 5 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 5 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 5 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 5 | repeated_value_bursts | 1 | 100.0 | 100.0 | +0.0 |
| 15 | ma_up | 1 | 100.0 | 0.0 | +100.0 |
| 15 | ma_flat | 1 | 0.0 | 0.0 | +0.0 |
| 15 | ma5_above_ma20 | 1 | 100.0 | 0.0 | +100.0 |
| 15 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 15 | value_burst | 1 | 0.0 | 100.0 | -100.0 |
| 15 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 15 | repeated_value_bursts | 1 | 100.0 | 100.0 | +0.0 |
| 60 | ma_up | 1 | 100.0 | 0.0 | +100.0 |
| 60 | ma_flat | 1 | 0.0 | 0.0 | +0.0 |
| 60 | ma5_above_ma20 | 1 | 100.0 | 0.0 | +100.0 |
| 60 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 60 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 60 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 60 | repeated_value_bursts | 1 | 0.0 | 100.0 | -100.0 |
| 360 | ma_up | 1 | 100.0 | 100.0 | +0.0 |
| 360 | ma_flat | 1 | 0.0 | 0.0 | +0.0 |
| 360 | ma5_above_ma20 | 1 | 100.0 | 100.0 | +0.0 |
| 360 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 360 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 360 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 360 | repeated_value_bursts | 1 | 100.0 | 0.0 | +100.0 |

## 360m_50pct

| Market | Anchor UTC | Phase | Max future rise % | First hit min |
|---|---|---|---|---|
| KRW-SOPH | 2026-09-07T21:51:00+00:00 | validation | 55.91 | 360 |

### Discovery

| Minutes before anchor | Feature | Pairs | Surge % | Control % | Difference pp |
|---|---|---|---|---|---|

No matched pairs: no common-pattern inference is possible.

### Validation

| Minutes before anchor | Feature | Pairs | Surge % | Control % | Difference pp |
|---|---|---|---|---|---|
| 0 | ma_up | 1 | 100.0 | 0.0 | +100.0 |
| 0 | ma_flat | 1 | 0.0 | 0.0 | +0.0 |
| 0 | ma5_above_ma20 | 1 | 100.0 | 0.0 | +100.0 |
| 0 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 0 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 0 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 0 | repeated_value_bursts | 1 | 100.0 | 100.0 | +0.0 |
| 5 | ma_up | 1 | 100.0 | 0.0 | +100.0 |
| 5 | ma_flat | 1 | 0.0 | 0.0 | +0.0 |
| 5 | ma5_above_ma20 | 1 | 100.0 | 0.0 | +100.0 |
| 5 | tight_box | 1 | 0.0 | 0.0 | +0.0 |
| 5 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 5 | quiet_price_value_rise | 1 | 0.0 | 0.0 | +0.0 |
| 5 | repeated_value_bursts | 1 | 100.0 | 100.0 | +0.0 |

## Feature Definitions

- ma_up/ma_flat: completed 5m SMA20 change over three bars >0.10% / within +/-0.10%.
- ma5_above_ma20: five-minute SMA5 above SMA20.
- tight_box: last 60-minute high/low range <=3%.
- value_burst: mean last 5-minute value >=3x preceding 20-minute mean.
- quiet_price_value_rise: absolute 5-minute return <=1% with value ratio >=2x.
- repeated_value_bursts: at least two of last 15 minutes >=3x their preceding 20-minute mean.

## Coverage

| Market | Candles | Runs | Longest continuous minutes |
|---|---|---|---|
| KRW-0G | 21029 | 7630 | 1367 |
| KRW-1INCH | 4660 | 3198 | 19 |
| KRW-2Z | 13277 | 6105 | 660 |
| KRW-A | 8681 | 5374 | 26 |
| KRW-AAVE | 20641 | 7617 | 199 |
| KRW-ADA | 14000 | 2081 | 180 |
| KRW-BTC | 10078 | 3 | 5134 |
| KRW-DOGE | 8887 | 884 | 246 |
| KRW-ETH | 10063 | 17 | 1386 |
| KRW-SOL | 9908 | 157 | 953 |
| KRW-SOPH | 8482 | 709 | 1370 |
| KRW-XRP | 10080 | 1 | 10080 |

Detailed past feature values, matched controls, and missing snapshots are in the JSON output.
Few or zero matches require better data; they do not establish the absence of useful patterns.
