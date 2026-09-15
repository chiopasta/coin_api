# V16 Offline Proxy Report

Verdict: NOT VALIDATED. Descriptive results only.

UTC range: 2026-08-16T13:43:00+00:00 to 2026-09-15T13:43:00+00:00
Validation begins: 2026-09-06T13:43:00+00:00

## Assumptions

- One-minute value-only proxy; no 30-second volume or trade-count test.
- Missing minutes split the data; no invented candles or returns across gaps.
- Signal at close; hypothetical entry at next open with fixed round-trip cost.
- Common chronological 70/30 split; discovery outcomes crossing the split excluded.
- No parameter search. The validation period is now observed, not a fresh holdout.
- Signals can overlap; means are event statistics, not portfolio returns.
- High/low excursions are not realizable profits or stop-loss simulations.
- Limited market selection; no missed-surge recall or unbiased control baseline.

- Continuous-data selection favors liquid markets; horizons use different subsets.
- Zero +100% hits does not establish that the dataset contained no such surges.

Config: `{"cooldown_minutes": 30, "max_extension_pct": 3.0, "max_price_5m_pct": 3.0, "min_value": 60000000, "round_trip_cost_pct": 0.2, "slope_floor_pct": -0.1, "value_ratio": 3.0}`

## All

Signals: 929

| Minutes | Eligible | Missing/purged | Mean net % | Median net % | Positive % | +3% hits | +10% hits | +100% hits | +200% hits | Worst low % |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 916 | 13 | -0.178 | -0.200 | 20.742 | 3 | 0 | 0 | 0 | -2.680 |
| 60 | 907 | 22 | -0.154 | -0.220 | 25.138 | 6 | 0 | 0 | 0 | -5.416 |
| 360 | 820 | 109 | 0.017 | -0.232 | 39.024 | 63 | 3 | 0 | 0 | -6.367 |
| 1440 | 600 | 329 | 1.061 | 0.152 | 53.000 | 194 | 27 | 0 | 0 | -4.117 |
| 4320 | 315 | 614 | 1.007 | -0.928 | 31.429 | 97 | 26 | 0 | 0 | -5.331 |

## Discovery

Signals: 664

| Minutes | Eligible | Missing/purged | Mean net % | Median net % | Positive % | +3% hits | +10% hits | +100% hits | +200% hits | Worst low % |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 656 | 8 | -0.163 | -0.200 | 23.171 | 2 | 0 | 0 | 0 | -1.346 |
| 60 | 648 | 16 | -0.126 | -0.200 | 29.012 | 5 | 0 | 0 | 0 | -5.416 |
| 360 | 589 | 75 | 0.149 | -0.146 | 43.803 | 54 | 3 | 0 | 0 | -6.367 |
| 1440 | 428 | 236 | 1.638 | 0.559 | 62.383 | 164 | 27 | 0 | 0 | -4.117 |
| 4320 | 209 | 455 | 2.003 | -0.831 | 34.928 | 76 | 26 | 0 | 0 | -4.917 |

## Validation

Signals: 265

| Minutes | Eligible | Missing/purged | Mean net % | Median net % | Positive % | +3% hits | +10% hits | +100% hits | +200% hits | Worst low % |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 260 | 5 | -0.218 | -0.224 | 14.615 | 1 | 0 | 0 | 0 | -2.680 |
| 60 | 258 | 7 | -0.223 | -0.257 | 15.504 | 1 | 0 | 0 | 0 | -2.680 |
| 360 | 227 | 38 | -0.314 | -0.429 | 27.313 | 9 | 0 | 0 | 0 | -3.188 |
| 1440 | 160 | 105 | -0.349 | -0.428 | 31.250 | 30 | 0 | 0 | 0 | -3.780 |
| 4320 | 106 | 159 | -0.955 | -1.104 | 24.528 | 21 | 0 | 0 | 0 | -5.331 |

## Coverage

| Market | Candles | Continuous runs | Longest run (minutes) |
|---|---|---|---|
| KRW-BTC | 43192 | 9 | 15804 |
| KRW-ETH | 43136 | 63 | 8500 |
