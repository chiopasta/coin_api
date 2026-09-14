"""Retrospective surge-event discovery and matched-control comparison, offline."""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import statistics

from .backtest_v16 import Candle, contiguous_runs, iso
from .scanner_v16 import pct
from .paths import DATA_DIR, REPORTS_DIR


LOOKBACK = 120
OFFSETS = (0, 5, 15, 60, 360)
FLAGS = ('ma_up', 'ma_flat', 'ma5_above_ma20', 'tight_box',
         'value_burst', 'quiet_price_value_rise', 'repeated_value_bursts')


def future_highs(rows, horizon):
    """Maximum over i+1..i+horizon, excluding the anchor candle."""
    queue = deque()
    result = [None] * len(rows)
    for j, candle in enumerate(rows):
        while queue and rows[queue[-1]].high <= candle.high:
            queue.pop()
        queue.append(j)
        while queue and queue[0] <= j - horizon:
            queue.popleft()
        if j >= horizon:
            result[j - horizon] = rows[queue[0]].high
    return result


def features(rows, index):
    if index < LOOKBACK - 1:
        return None
    past = rows[index - LOOKBACK + 1:index + 1]
    aligned = [c.close for c in past if c.ts % 300 == 240]
    if len(aligned) < 23:
        return None
    ma20 = statistics.fmean(aligned[-20:])
    old = statistics.fmean(aligned[-23:-3])
    slope = pct(ma20, old)
    ma5 = statistics.fmean(aligned[-5:])
    values = [c.value for c in past]
    base = statistics.fmean(values[-25:-5])
    ratio = statistics.fmean(values[-5:]) / base if base > 0 else None
    p5 = pct(past[-1].close, past[-6].close)
    box = pct(max(c.high for c in past[-60:]), min(c.low for c in past[-60:]))
    bursts = 0
    for j in range(len(past) - 15, len(past)):
        prior = statistics.fmean(values[j - 20:j])
        if prior > 0 and values[j] >= 3 * prior:
            bursts += 1
    result = dict(ma20_slope_pct=slope, ma_gap_pct=pct(ma5, ma20),
                  extension_pct=pct(past[-1].close, ma20), box_60m_pct=box,
                  price_5m_pct=p5, price_15m_pct=pct(past[-1].close, past[-16].close),
                  price_60m_pct=pct(past[-1].close, past[-61].close),
                  mean_value_60m=statistics.fmean(values[-60:]),
                  value_ratio_5m=ratio, burst_minutes_15m=bursts,
                  ma_up=slope > 0.10, ma_flat=abs(slope) <= 0.10,
                  ma5_above_ma20=ma5 > ma20, tight_box=box <= 3,
                  value_burst=ratio >= 3 if ratio is not None else None,
                  quiet_price_value_rise=(abs(p5) <= 1 and ratio >= 2) if ratio is not None else None,
                  repeated_value_bursts=bursts >= 2)
    return result


def phase(ts, horizon, split):
    end = ts + 60 + horizon * 60
    if end <= split:
        return 'discovery'
    if ts + 60 >= split:
        return 'validation'
    return None


def sample(rows, index, horizon, high, split):
    return dict(anchor_ts=rows[index].ts + 60, anchor_utc=iso(rows[index].ts + 60),
                horizon_end_ts=rows[index].ts + 60 + horizon * 60,
                anchor_price=rows[index].close,
                future_max_up_pct=pct(high, rows[index].close),
                phase=phase(rows[index].ts, horizon, split),
                snapshots={str(offset): features(rows, index - offset) for offset in OFFSETS})


def extract(rows, horizon, threshold, split):
    highs = future_highs(rows, horizon)
    cases, controls = [], []
    next_anchor = -1
    eligible = 0
    for i in range(LOOKBACK - 1, len(rows) - horizon):
        if phase(rows[i].ts, horizon, split) is None:
            continue
        eligible += 1
        gain = pct(highs[i], rows[i].close)
        if gain >= threshold and i >= next_anchor:
            event = sample(rows, i, horizon, highs[i], split)
            future = rows[i + 1:i + 1 + horizon]
            hit = next(j for j, c in enumerate(future) if pct(c.high, rows[i].close) >= threshold)
            event['first_hit_minutes'] = hit + 1
            event['first_hit_bar_utc'] = iso(future[hit].ts)
            event['low_before_hit_bar_pct'] = pct(
                min((c.low for c in future[:hit]), default=rows[i].close), rows[i].close)
            cases.append(event)
            next_anchor = i + horizon + 1
        elif gain < threshold / 2 and rows[i].ts % 3600 == 0:
            controls.append(sample(rows, i, horizon, highs[i], split))
    return cases, controls, eligible


def overlaps(a, b):
    return (a['anchor_ts'] < b['horizon_end_ts'] and b['anchor_ts'] < a['horizon_end_ts'])


def match_controls(cases, controls):
    matches, used = [], []
    for case in cases:
        base = case['snapshots']['0']['mean_value_60m']
        candidates = []
        for control in controls:
            if control['phase'] != case['phase'] or abs(control['anchor_ts'] - case['anchor_ts']) > 7 * 86400:
                continue
            if any(overlaps(control, other) for other in cases + used):
                continue
            value = control['snapshots']['0']['mean_value_60m']
            if base <= 0 or value <= 0 or not 1 / 3 <= value / base <= 3:
                continue
            score = abs(math.log(value / base)) + abs(control['anchor_ts'] - case['anchor_ts']) / (7 * 86400)
            candidates.append((score, control['anchor_ts'], control))
        if candidates:
            control = min(candidates, key=lambda item: item[:2])[2]
            used.append(control)
            matches.append(dict(case=case, control=control))
    return matches


def compare(pairs, phase_name):
    subset = [p for p in pairs if p['case']['phase'] == phase_name]
    result = {}
    for offset in OFFSETS:
        paired = [(p['case']['snapshots'][str(offset)], p['control']['snapshots'][str(offset)]) for p in subset]
        paired = [(a, b) for a, b in paired if a is not None and b is not None]
        flags, numeric = {}, {}
        for name in FLAGS:
            valid = [(a[name], b[name]) for a, b in paired if a[name] is not None and b[name] is not None]
            n = len(valid)
            a = 100 * sum(x for x, _ in valid) / n if n else None
            b = 100 * sum(y for _, y in valid) / n if n else None
            flags[name] = dict(pairs=n, surge_pct=a, control_pct=b,
                               difference_pp=a - b if n else None)
        if paired:
            for name in paired[0][0]:
                if name in FLAGS:
                    continue
                valid = [(a[name], b[name]) for a, b in paired if a[name] is not None and b[name] is not None]
                numeric[name] = dict(pairs=len(valid),
                    surge_median=statistics.median(a for a, _ in valid) if valid else None,
                    control_median=statistics.median(b for _, b in valid) if valid else None)
        result[str(offset)] = dict(pairs=len(paired), flags=flags, numeric=numeric)
    return result


def analyze(path, horizons, thresholds):
    groups = {f'{h}m_{t:g}pct': dict(horizon_minutes=h, threshold_pct=t, eligible_anchors=0,
                                   cases=[], pairs=[]) for h in horizons for t in thresholds}
    coverage = []
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        start, last = db.execute('SELECT MIN(ts),MAX(ts) FROM minute_candles').fetchone()
        if start is None:
            raise ValueError('Database has no candles')
        split = start + int((last + 60 - start) * 0.7 / 60) * 60
        markets = [r[0] for r in db.execute('SELECT DISTINCT market FROM minute_candles ORDER BY market')]
        for market in markets:
            rows = [Candle(*r) for r in db.execute(
                'SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? ORDER BY ts', (market,))]
            if any(c.ts % 60 or not all(math.isfinite(v) and v > 0 for v in (c.open, c.high, c.low, c.close))
                   or not math.isfinite(c.value) or c.value < 0 or c.high < max(c.open, c.close)
                   or c.low > min(c.open, c.close) for c in rows):
                raise ValueError('Invalid OHLCV data: ' + market)
            runs = list(contiguous_runs(rows))
            coverage.append(dict(market=market, candles=len(rows), runs=len(runs),
                                 longest_run_minutes=max(map(len, runs))))
            for group in groups.values():
                cases, controls = [], []
                for run in runs:
                    a, b, count = extract(run, group['horizon_minutes'], group['threshold_pct'], split)
                    cases.extend(a)
                    controls.extend(b)
                    group['eligible_anchors'] += count
                for item in cases + controls:
                    item['market'] = market
                group['cases'].extend(cases)
                group['pairs'].extend(match_controls(cases, controls))
            print('ANALYZED', market, flush=True)
    for group in groups.values():
        group['unmatched_cases'] = len(group['cases']) - len(group['pairs'])
        group['comparisons'] = {p: compare(group['pairs'], p) for p in ('discovery', 'validation')}
    return dict(status='EXPLORATORY_NOT_VALIDATED', start_utc=iso(start), end_utc=iso(last + 60),
                split_utc=iso(split), coverage=coverage, groups=groups)


def render(report):
    lines = ['# Surge Pattern Discovery', '', 'Status: EXPLORATORY, NOT VALIDATED.', '',
             f"UTC: {report['start_utc']} to {report['end_utc']}", f"70/30 split: {report['split_utc']}", '',
             '## Method and Limits', '',
             '- Event: first eligible close whose future high reaches the threshold within the horizon.',
             '- Anchors are retrospective labels, NOT detectable pump-start times or entry signals.',
             '- Require 120 contiguous past minutes and a complete contiguous future horizon.',
             '- Within each market/horizon/threshold, skip the full horizon after an event.',
             '- Different horizons and thresholds may describe the same rally; do not sum them.',
             '- Past snapshots: anchor and 5/15/60/360 minutes earlier; unavailable snapshots remain null.',
             '- Controls: same market and split, within 7 days, preceding hourly value within 1/3 to 3x.',
             '- Control future high must remain below half the event threshold; candidates sampled hourly.',
             '- One control per case, without reuse or overlap with case/control future windows.',
             '- Features use past candles only; event/control labels deliberately use future data.',
             '- Missing candles are not filled. This favors liquid markets and can omit real surges.',
             '- Matching is approximate liquidity/calendar matching, not market-regime adjustment.',
             '- No causal claims, predictive accuracy, significance tests, or parameter optimization.',
             '- Validation is descriptive on already observed data; a fresh period is still required.',
             '- Trade quantity/count is absent; all volume-like features use KRW traded value.', '',
             '## Event Counts', '', '| Horizon min | Threshold % | Eligible anchors | Events | Matched | Unmatched |',
             '|---|---|---|---|---|---|']
    for group in report['groups'].values():
        lines.append(f"| {group['horizon_minutes']} | {group['threshold_pct']} | {group['eligible_anchors']} | {len(group['cases'])} | {len(group['pairs'])} | {group['unmatched_cases']} |")
    for key, group in report['groups'].items():
        if not group['cases']:
            continue
        lines += ['', '## ' + key, '', '| Market | Anchor UTC | Phase | Max future rise % | First hit min |', '|---|---|---|---|---|']
        for case in group['cases']:
            lines.append(f"| {case['market']} | {case['anchor_utc']} | {case['phase']} | {case['future_max_up_pct']:.2f} | {case['first_hit_minutes']} |")
        for phase_name, offsets in group['comparisons'].items():
            lines += ['', '### ' + phase_name.title(), '',
                      '| Minutes before anchor | Feature | Pairs | Surge % | Control % | Difference pp |', '|---|---|---|---|---|---|']
            available = False
            for offset, summary in offsets.items():
                for name, row in summary['flags'].items():
                    if not row['pairs']:
                        continue
                    available = True
                    lines.append(f"| {offset} | {name} | {row['pairs']} | {row['surge_pct']:.1f} | {row['control_pct']:.1f} | {row['difference_pp']:+.1f} |")
            if not available:
                lines += ['', 'No matched pairs: no common-pattern inference is possible.']
    lines += ['', '## Feature Definitions', '',
              '- ma_up/ma_flat: completed 5m SMA20 change over three bars >0.10% / within +/-0.10%.',
              '- ma5_above_ma20: five-minute SMA5 above SMA20.',
              '- tight_box: last 60-minute high/low range <=3%.',
              '- value_burst: mean last 5-minute value >=3x preceding 20-minute mean.',
              '- quiet_price_value_rise: absolute 5-minute return <=1% with value ratio >=2x.',
              '- repeated_value_bursts: at least two of last 15 minutes >=3x their preceding 20-minute mean.', '',
              '## Coverage', '', '| Market | Candles | Runs | Longest continuous minutes |', '|---|---|---|---|']
    for row in report['coverage']:
        lines.append(f"| {row['market']} | {row['candles']} | {row['runs']} | {row['longest_run_minutes']} |")
    lines += ['', 'Detailed past feature values, matched controls, and missing snapshots are in the JSON output.',
              'Few or zero matches require better data; they do not establish the absence of useful patterns.']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=DATA_DIR / 'historical_market.db')
    parser.add_argument('--output', type=Path, default=REPORTS_DIR / 'surge_pattern_result')
    parser.add_argument('--horizons', nargs='+', type=int, default=[360, 1440, 4320])
    parser.add_argument('--thresholds', nargs='+', type=float, default=[20, 50, 100])
    args = parser.parse_args()
    if any(h <= 0 for h in args.horizons) or any(not math.isfinite(t) or t <= 0 for t in args.thresholds):
        parser.error('Horizons and thresholds must be positive finite numbers')
    report = analyze(args.db, sorted(set(args.horizons)), sorted(set(args.thresholds)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    args.output.with_suffix('.md').write_text(render(report), encoding='utf-8')
    for key, group in report['groups'].items():
        print(key, 'events=', len(group['cases']), 'matched=', len(group['pairs']), 'eligible=', group['eligible_anchors'])
    print('REPORT', args.output.with_suffix('.md'))


if __name__ == '__main__':
    main()
