"""Offline 1-minute proxy of V16; not a replay of its 30-second trade signals."""

import argparse
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import statistics

from .historical_breakout_lab_v1 import Candle
from .scanner_v16 import pct
from .paths import DATA_DIR, REPORTS_DIR


@dataclass(frozen=True)
class ProxyConfig:
    value_ratio: float = 3.0
    min_value: float = 60_000_000
    slope_floor_pct: float = -0.10
    max_extension_pct: float = 3.0
    max_price_5m_pct: float = 3.0
    cooldown_minutes: int = 30
    round_trip_cost_pct: float = 0.20


def contiguous_runs(candles):
    run = []
    for candle in candles:
        if run and candle.ts != run[-1].ts + 60:
            yield run
            run = []
        run.append(candle)
    if run:
        yield run


def detect(run, config, last_signal=-math.inf):
    closes5 = deque(maxlen=23)
    first = run[0].ts
    for i, candle in enumerate(run):
        # Only completed, aligned five-minute bars with all five minutes present.
        if candle.ts % 300 == 240 and candle.ts - 240 >= first:
            closes5.append(candle.close)
        if len(closes5) < 23 or i < 10:
            continue
        if candle.ts - last_signal < config.cooldown_minutes * 60:
            continue
        closes = list(closes5)
        ma20 = statistics.fmean(closes[-20:])
        slope = pct(ma20, statistics.fmean(closes[:20]))
        extension = pct(candle.close, ma20)
        p5 = pct(candle.close, run[i - 5].close)
        baseline = [c.value for c in run[i - 10:i]]
        base = max(statistics.fmean(baseline), statistics.median(baseline))
        if base <= 0:
            continue
        ratio = candle.value / base
        if (slope >= config.slope_floor_pct
                and 0 <= extension <= config.max_extension_pct
                and 0 <= p5 <= config.max_price_5m_pct
                and candle.value >= config.min_value and ratio >= config.value_ratio):
            last_signal = candle.ts
            yield i, dict(signal_ts=candle.ts + 60, price=candle.close,
                          ma20=ma20, slope_pct=slope, extension_pct=extension,
                          price_5m_pct=p5, value=candle.value, value_ratio=ratio)


def outcome(run, index, minutes, cost):
    # Signal exists only at close. Entry assumption is the next minute's open.
    future = run[index + 1:index + 1 + minutes]
    if len(future) != minutes:
        return None
    entry = future[0].open
    return dict(entry_ts=future[0].ts, end_ts=future[-1].ts + 60,
                entry_price=entry, net_return_pct=pct(future[-1].close, entry) - cost,
                max_up_pct=pct(max(c.high for c in future), entry),
                max_down_pct=pct(min(c.low for c in future), entry))


def summarize(events, horizons, split_ts):
    result = {}
    for label in ('all', 'discovery', 'validation'):
        subset = [e for e in events if label == 'all' or
                  (e['signal_ts'] < split_ts if label == 'discovery' else e['signal_ts'] >= split_ts)]
        table = {}
        for horizon in horizons:
            rows = [e['outcomes'][str(horizon)] for e in subset
                    if e['outcomes'][str(horizon)] is not None]
            if label == 'discovery':
                rows = [r for r in rows if r['end_ts'] <= split_ts]
            returns = [r['net_return_pct'] for r in rows]
            table[str(horizon)] = dict(
                eligible=len(rows), unavailable_or_cross_split=len(subset) - len(rows),
                mean_net_pct=statistics.fmean(returns) if returns else None,
                median_net_pct=statistics.median(returns) if returns else None,
                positive_pct=100 * sum(r > 0 for r in returns) / len(rows) if rows else None,
                hit_3_pct=sum(r['max_up_pct'] >= 3 for r in rows),
                hit_10_pct=sum(r['max_up_pct'] >= 10 for r in rows),
                hit_100_pct=sum(r['max_up_pct'] >= 100 for r in rows),
                hit_200_pct=sum(r['max_up_pct'] >= 200 for r in rows),
                worst_excursion_pct=min((r['max_down_pct'] for r in rows), default=None))
        result[label] = dict(signals=len(subset), horizons=table)
    return result


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def run_backtest(db_path, config, horizons):
    with sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True) as conn:
        bounds = conn.execute('SELECT MIN(ts),MAX(ts),COUNT(*) FROM minute_candles').fetchone()
        if not bounds[2]:
            raise ValueError('No candles in database')
        start, end = bounds[0], bounds[1] + 60
        split_ts = start + int((end - start) * 0.70 / 60) * 60
        markets = [r[0] for r in conn.execute('SELECT DISTINCT market FROM minute_candles ORDER BY market')]
        events, coverage = [], []
        for market in markets:
            candles = [Candle(*r) for r in conn.execute(
                'SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? ORDER BY ts',
                (market,))]
            if any(not all(math.isfinite(v) and v > 0 for v in (c.open, c.high, c.low, c.close))
                   or not math.isfinite(c.value) or c.value < 0
                   or c.low > min(c.open, c.close) or c.high < max(c.open, c.close)
                   or c.ts % 60 for c in candles):
                raise ValueError('Invalid candle in ' + market)
            runs = list(contiguous_runs(candles))
            coverage.append(dict(market=market, candles=len(candles), runs=len(runs),
                                 max_contiguous_minutes=max(map(len, runs)),
                                 start=iso(candles[0].ts), end=iso(candles[-1].ts + 60)))
            last_signal = -math.inf
            for segment in runs:
                for index, event in detect(segment, config, last_signal):
                    last_signal = event['signal_ts'] - 60
                    event['market'] = market
                    event['outcomes'] = {str(h): outcome(segment, index, h, config.round_trip_cost_pct)
                                         for h in horizons}
                    events.append(event)
            print('PROCESSED', market, len(candles), 'candles', flush=True)
    events.sort(key=lambda e: (e['signal_ts'], e['market']))
    return dict(mode='V16_ONE_MINUTE_VALUE_ONLY_PROXY', verdict='NOT_VALIDATED',
                config=asdict(config), start_utc=iso(start), end_utc=iso(end),
                validation_start_utc=iso(split_ts), candles=bounds[2], coverage=coverage,
                summary=summarize(events, horizons, split_ts), events=events)


def report_text(report):
    lines = ['# V16 Offline Proxy Report', '',
             'Verdict: NOT VALIDATED. Descriptive results only.', '',
             f"UTC range: {report['start_utc']} to {report['end_utc']}",
             f"Validation begins: {report['validation_start_utc']}", '',
             '## Assumptions', '',
             '- One-minute value-only proxy; no 30-second volume or trade-count test.',
             '- Missing minutes split the data; no invented candles or returns across gaps.',
             '- Signal at close; hypothetical entry at next open with fixed round-trip cost.',
             '- Common chronological 70/30 split; discovery outcomes crossing the split excluded.',
             '- No parameter search. The validation period is now observed, not a fresh holdout.',
             '- Signals can overlap; means are event statistics, not portfolio returns.',
             '- High/low excursions are not realizable profits or stop-loss simulations.',
             '- Limited market selection; no missed-surge recall or unbiased control baseline.', '',
             '- Continuous-data selection favors liquid markets; horizons use different subsets.',
             '- Zero +100% hits does not establish that the dataset contained no such surges.', '',
             'Config: `' + json.dumps(report['config'], sort_keys=True) + '`', '']
    for label, group in report['summary'].items():
        lines += [f'## {label.title()}', '', f"Signals: {group['signals']}", '',
                  '| Minutes | Eligible | Missing/purged | Mean net % | Median net % | Positive % | +3% hits | +10% hits | +100% hits | +200% hits | Worst low % |',
                  '|---|---|---|---|---|---|---|---|---|---|---|']
        for horizon, row in group['horizons'].items():
            cells = [horizon] + [f'{v:.3f}' if isinstance(v, float) else str(v) if v is not None else 'N/A'
                                  for v in row.values()]
            lines.append('| ' + ' | '.join(cells) + ' |')
        lines.append('')
    lines += ['## Coverage', '', '| Market | Candles | Continuous runs | Longest run (minutes) |',
              '|---|---|---|---|']
    for row in report['coverage']:
        lines.append(f"| {row['market']} | {row['candles']} | {row['runs']} | {row['max_contiguous_minutes']} |")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DATA_DIR / 'historical_market.db')
    parser.add_argument('--output', type=Path, default=REPORTS_DIR / 'backtest_v16_result')
    parser.add_argument('--cost-pct', type=float, default=0.20, help='Assumed round-trip fee plus slippage, percentage points')
    args = parser.parse_args()
    if not math.isfinite(args.cost_pct) or args.cost_pct < 0:
        parser.error('Cost must be nonnegative and finite')
    report = run_backtest(args.db, ProxyConfig(round_trip_cost_pct=args.cost_pct), (30, 60, 360, 1440, 4320))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    args.output.with_suffix('.md').write_text(report_text(report), encoding='utf-8')
    print(report_text(report))


if __name__ == '__main__':
    main()
