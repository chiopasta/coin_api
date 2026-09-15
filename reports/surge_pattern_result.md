# Surge Pattern Discovery

Status: EXPLORATORY, NOT VALIDATED.

UTC: 2026-08-16T13:43:00+00:00 to 2026-09-15T13:43:00+00:00
70/30 split: 2026-09-06T13:43:00+00:00

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
| 360 | 20 | 72081 | 0 | 0 | 0 |
| 360 | 50 | 72081 | 0 | 0 | 0 |
| 360 | 100 | 72081 | 0 | 0 | 0 |
| 1440 | 20 | 49911 | 0 | 0 | 0 |
| 1440 | 50 | 49911 | 0 | 0 | 0 |
| 1440 | 100 | 49911 | 0 | 0 | 0 |
| 4320 | 20 | 27347 | 2 | 1 | 1 |
| 4320 | 50 | 27347 | 0 | 0 | 0 |
| 4320 | 100 | 27347 | 0 | 0 | 0 |

## 4320m_20pct

| Market | Anchor UTC | Phase | Max future rise % | First hit min |
|---|---|---|---|---|
| KRW-BTC | 2026-08-18T20:56:00+00:00 | discovery | 20.56 | 3603 |
| KRW-ETH | 2026-08-18T22:56:00+00:00 | discovery | 29.46 | 2507 |

### Discovery

| Minutes before anchor | Feature | Pairs | Surge % | Control % | Difference pp |
|---|---|---|---|---|---|
| 0 | ma_up | 1 | 0.0 | 0.0 | +0.0 |
| 0 | ma_flat | 1 | 100.0 | 100.0 | +0.0 |
| 0 | ma5_above_ma20 | 1 | 0.0 | 100.0 | -100.0 |
| 0 | tight_box | 1 | 100.0 | 100.0 | +0.0 |
| 0 | value_burst | 1 | 0.0 | 0.0 | +0.0 |
| 0 | quiet_price_value_rise | 1 | 100.0 | 0.0 | +100.0 |
| 0 | repeated_value_bursts | 1 | 100.0 | 0.0 | +100.0 |

### Validation

| Minutes before anchor | Feature | Pairs | Surge % | Control % | Difference pp |
|---|---|---|---|---|---|

No matched pairs: no common-pattern inference is possible.

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
| KRW-BTC | 43192 | 9 | 15804 |
| KRW-ETH | 43136 | 63 | 8500 |

Detailed past feature values, matched controls, and missing snapshots are in the JSON output.
Few or zero matches require better data; they do not establish the absence of useful patterns.
