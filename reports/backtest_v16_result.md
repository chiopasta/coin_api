# V16 Offline Proxy Report

Verdict: NOT VALIDATED. Descriptive results only.

UTC range: 2026-08-12T06:30:00+00:00 to 2026-09-11T06:30:00+00:00
Validation begins: 2026-09-02T06:30:00+00:00

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

Signals: 361

| Minutes | Eligible | Missing/purged | Mean net % | Median net % | Positive % | +3% hits | +10% hits | +100% hits | +200% hits | Worst low % |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 348 | 13 | -0.228 | -0.252 | 12.356 | 4 | 1 | 0 | 0 | -5.882 |
| 60 | 338 | 23 | -0.320 | -0.289 | 16.568 | 5 | 1 | 0 | 0 | -11.569 |
| 360 | 275 | 86 | -0.467 | -0.543 | 18.545 | 10 | 6 | 0 | 0 | -20.438 |
| 1440 | 158 | 203 | -0.873 | -0.972 | 25.316 | 11 | 0 | 0 | 0 | -4.835 |
| 4320 | 66 | 295 | -1.917 | -1.844 | 0.000 | 4 | 0 | 0 | 0 | -4.819 |

## Discovery

Signals: 5

| Minutes | Eligible | Missing/purged | Mean net % | Median net % | Positive % | +3% hits | +10% hits | +100% hits | +200% hits | Worst low % |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 5 | 0 | -0.353 | -0.200 | 20.000 | 2 | 0 | 0 | 0 | -2.636 |
| 60 | 5 | 0 | 0.515 | 0.578 | 60.000 | 3 | 0 | 0 | 0 | -3.509 |
| 360 | 4 | 1 | 0.541 | 2.283 | 50.000 | 3 | 2 | 0 | 0 | -16.814 |
| 1440 | 0 | 5 | N/A | N/A | N/A | 0 | 0 | 0 | 0 | N/A |
| 4320 | 0 | 5 | N/A | N/A | N/A | 0 | 0 | 0 | 0 | N/A |

## Validation

Signals: 356

| Minutes | Eligible | Missing/purged | Mean net % | Median net % | Positive % | +3% hits | +10% hits | +100% hits | +200% hits | Worst low % |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 343 | 13 | -0.226 | -0.252 | 12.245 | 2 | 1 | 0 | 0 | -5.882 |
| 60 | 333 | 23 | -0.332 | -0.289 | 15.916 | 2 | 1 | 0 | 0 | -11.569 |
| 360 | 271 | 85 | -0.482 | -0.543 | 18.081 | 7 | 4 | 0 | 0 | -20.438 |
| 1440 | 158 | 198 | -0.873 | -0.972 | 25.316 | 11 | 0 | 0 | 0 | -4.835 |
| 4320 | 66 | 290 | -1.917 | -1.844 | 0.000 | 4 | 0 | 0 | 0 | -4.819 |

## Coverage

| Market | Candles | Continuous runs | Longest run (minutes) |
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
