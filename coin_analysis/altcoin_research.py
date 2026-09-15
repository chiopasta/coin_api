"""Altcoin event discovery and causal candidate-signal evaluation."""

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import sqlite3
import statistics

from .backtest_v16 import contiguous_runs, iso
from .historical_breakout_lab_v1 import (
    Candle, choose_markets, download_all, init_db, parse_utc,
)
from .paths import DATA_DIR, REPORTS_DIR
from .surge_pattern_lab import extract, features, match_controls, compare, phase
from .scanner_v16 import pct


# Editable research universe, not a historical market-cap classification.
DEFAULT_EXCLUDE = 'BTC,ETH,XRP,SOL,DOGE,ADA,TRX,BNB,USDT,USDC'
RULES = ('quiet_accumulation', 'repeated_bursts', 'compressed_breakout')


def symbols(value):
    return sorted({'KRW-' + s.strip().upper().removeprefix('KRW-')
                   for s in value.split(',') if s.strip()})


def candidates(f):
    """Only completed past candles enter these fixed hypotheses."""
    if f is None:
        return []
    result = []
    if f['quiet_price_value_rise'] and f['mean_value_60m'] >= 1_000_000:
        result.append('quiet_accumulation')
    if f['repeated_value_bursts'] and 0 <= f['price_15m_pct'] <= 3:
        result.append('repeated_bursts')
    if f['tight_box'] and f['value_burst'] and f['ma5_above_ma20']:
        result.append('compressed_breakout')
    return result


def evaluate_run(rows, horizon, threshold, split, cooldown=30, last=None):
    """Replay alerts before looking at outcomes; keep incomplete labels explicit."""
    alerts = []
    if last is None:
        last = {name: -math.inf for name in RULES}
    for i in range(119, len(rows)):
        f = features(rows, i)
        for rule in candidates(f):
            ts = rows[i].ts + 60
            if ts - last[rule] < cooldown * 60:
                continue
            last[rule] = ts
            future = rows[i + 1:i + 1 + horizon]
            complete = len(future) == horizon
            label = phase(rows[i].ts, horizon, split)
            hit = next((j for j, c in enumerate(future)
                        if pct(c.high, rows[i].close) >= threshold), None)
            peak = max(range(len(future)), key=lambda j: future[j].high) if future else None
            # Exclude the peak candle: intrabar high/low order is unknown.
            after_peak = future[peak + 1:] if peak is not None else []
            alerts.append(dict(rule=rule, signal_ts=ts, signal_utc=iso(ts),
                phase=label, features=f, complete=complete,
                success=(hit is not None) if complete else None,
                hit_bar_ts=future[hit].ts if hit is not None else None,
                lead_minutes_lower_bound=hit if hit is not None else None,
                max_up_pct=pct(future[peak].high, rows[i].close) if complete else None,
                peak_to_later_low_pct=pct(min(c.low for c in after_peak), future[peak].high)
                    if complete and after_peak else None))
    return alerts


def metrics(alerts, cases):
    result = {}
    for part in ('discovery', 'validation'):
        events = [c for c in cases if c['phase'] == part]
        result[part] = {}
        for rule in RULES:
            selected = [a for a in alerts if a['rule'] == rule and a['phase'] == part]
            valid = [a for a in selected if a['complete']]
            hits = [a for a in valid if a['success']]
            # Match the retrospective event's first threshold-hit bar, not its anchor.
            matched = []
            for event in events:
                hit_ts = event['anchor_ts'] + (event['first_hit_minutes'] - 1) * 60
                leads = [(hit_ts - a['signal_ts']) / 60 for a in valid
                         if a['market'] == event['market']
                         and event['anchor_ts'] <= a['signal_ts'] <= hit_ts - 5 * 60]
                if leads:
                    matched.append(max(leads))
            result[part][rule] = dict(alerts=len(selected), evaluated=len(valid),
                incomplete=len(selected) - len(valid), successes=len(hits),
                false_alerts=len(valid) - len(hits),
                precision_pct=100 * len(hits) / len(valid) if valid else None,
                events=len(events), events_warned_5m_early=len(matched),
                missed_events=len(events) - len(matched),
                recall_pct=100 * len(matched) / len(events) if events else None,
                median_event_lead_minutes=statistics.median(matched) if matched else None)
    return result


def analyze(db_path, excluded, included, days, horizon, threshold):
    with closing(sqlite3.connect(Path(db_path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        available = [r[0] for r in db.execute('SELECT DISTINCT market FROM minute_candles')]
        markets = sorted(m for m in available if m.startswith('KRW-') and m not in excluded
                         and (not included or m in included))
        if not markets:
            raise ValueError('No eligible altcoin data. Run the download command first.')
        placeholders = ','.join('?' for _ in markets)
        end = db.execute(f'SELECT MAX(ts) FROM minute_candles WHERE market IN ({placeholders})', markets).fetchone()[0] + 60
        start = end - days * 86400
        split = start + int(days * 86400 * .7 / 60) * 60
        cases, pairs, alerts, coverage = [], [], [], []
        for market in markets:
            rows = [Candle(*r) for r in db.execute(
                'SELECT ts,open,high,low,close,trade_value FROM minute_candles '
                'WHERE market=? AND ts>=? AND ts<? ORDER BY ts', (market, start, end))]
            if not rows:
                continue
            for c in rows:
                if (c.ts % 60 or not all(math.isfinite(v) and v > 0 for v in (c.open, c.high, c.low, c.close))
                        or not math.isfinite(c.value) or c.value < 0
                        or c.low > min(c.open, c.close) or c.high < max(c.open, c.close)):
                    raise ValueError('Invalid candle: ' + market)
            runs = list(contiguous_runs(rows))
            market_cases, controls = [], []
            eligible = 0
            last_alert = {name: -math.inf for name in RULES}
            for run in runs:
                a, b, count = extract(run, horizon, threshold, split)
                market_cases.extend(a)
                controls.extend(b)
                eligible += count
                for alert in evaluate_run(run, horizon, threshold, split, last=last_alert):
                    alert['market'] = market
                    alerts.append(alert)
            for item in market_cases + controls:
                item['market'] = market
            cases.extend(market_cases)
            pairs.extend(match_controls(market_cases, controls))
            coverage.append(dict(market=market, candles=len(rows), runs=len(runs),
                missing_minutes=days * 1440 - len(rows), eligible_anchors=eligible,
                longest_run_minutes=max(map(len, runs))))
            print('ANALYZED', market, 'events', len(market_cases), flush=True)
    return dict(status='EXPLORATORY_NOT_VALIDATED', start_utc=iso(start), end_utc=iso(end),
        split_utc=iso(split), horizon_minutes=horizon, threshold_pct=threshold,
        excluded=sorted(excluded), markets=markets, coverage=coverage, cases=cases,
        pairs=pairs, comparisons={p: compare(pairs, p) for p in ('discovery', 'validation')},
        alerts=alerts, metrics=metrics(alerts, cases),
        cross_split_alerts=sum(a['phase'] is None for a in alerts))


def render(report):
    lines = ['# 알트코인 급등 사전 신호 연구', '', '**상태: 탐색 중 · 예측력 검증 미완료**', '',
        f"기간(UTC): {report['start_utc']} ~ {report['end_utc']}",
        f"급등 기준: {report['horizon_minutes']}분 이내 고가 +{report['threshold_pct']:g}%", '',
        '## 해석', '',
        '- 제외 목록을 적용한 원화 알트코인 연구이며 시가총액 소형주 분류가 아닙니다.',
        '- 신호 조건은 과거 완성 봉만 사용합니다. 공통점 비교의 사건 라벨은 미래를 사용합니다.',
        '- 선행 시간은 목표 상승률 최초 도달 봉 시작까지의 시간입니다. 급등 시작 전 예측을 뜻하지 않습니다.',
        '- 적중률: 완전한 미래 구간을 가진 알림 중 신호 가격 대비 목표 고가에 도달한 비율.',
        '- 포착률: 사후 사건 기준점 이후, 목표 도달 최소 5분 전에 알림이 있었던 사건 비율.',
        '- 고가 도달은 체결 가능 수익이 아닙니다. 급락은 고가 봉 다음부터 평가하여 봉 내부 순서를 가정하지 않습니다.',
        '- 데이터 공백을 채우지 않습니다. 거래가 드문 종목의 급등은 분석에서 빠질 수 있습니다.',
        '- 전반 70% / 후반 30% 시간 분할. 경계를 넘는 결과는 제외하며 후반을 본 뒤 새 기간 검증이 필요합니다.',
        '- 현재 상장 종목 수집은 상장폐지 종목을 놓칩니다. 규칙은 초기 가설이며 최적화하지 않았습니다.', '',
        f"사건 {len(report['cases'])}건 / 대조군 매칭 {len(report['pairs'])}건 / 경계 제외 알림 {report['cross_split_alerts']}건", '']
    for part, rules in report['metrics'].items():
        lines += [f'## {part}', '', '| 규칙 | 평가 알림 | 오탐 | 적중률 % | 사건 | 포착률 % | 선행 중앙값(분) |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for rule, m in rules.items():
            values = [rule, m['evaluated'], m['false_alerts'], m['precision_pct'], m['events'],
                      m['recall_pct'], m['median_event_lead_minutes']]
            lines.append('| ' + ' | '.join('N/A' if v is None else f'{v:.2f}' if isinstance(v, float) else str(v) for v in values) + ' |')
        lines += ['', '### 급등 전 공통점 (대조군과 비율 차이)', '']
        for offset, comparison in report['comparisons'][part].items():
            flags = [(name, data) for name, data in comparison['flags'].items() if data['pairs']]
            flags.sort(key=lambda item: item[1]['difference_pp'], reverse=True)
            for name, data in flags[:3]:
                lines.append(f"- 기준점 {offset}분 전 · {name}: {data['pairs']}쌍, 차이 {data['difference_pp']:+.1f}%p")
    lines += ['', '## 데이터 범위', '', '| 종목 | 봉 수 | 누락 분 | 연속 구간 수 | 평가 가능 기준점 |', '|---|---:|---:|---:|---:|']
    for c in report['coverage']:
        lines.append(f"| {c['market']} | {c['candles']} | {c['missing_minutes']} | {c['runs']} | {c['eligible_anchors']} |")
    lines += ['', '사건별 종목·시간·이전 특징, 모든 알림과 급락 지표는 같은 이름의 JSON에서 확인합니다.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['download', 'analyze'])
    parser.add_argument('--db', type=Path, default=DATA_DIR / 'altcoin_market.db')
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--end', help='Download end in UTC; fix this to resume the same period')
    parser.add_argument('--markets', default='', help='Comma-separated symbols; default all KRW alts')
    parser.add_argument('--exclude', default=DEFAULT_EXCLUDE)
    parser.add_argument('--horizon', type=int, default=60)
    parser.add_argument('--threshold', type=float, default=10)
    parser.add_argument('--output', type=Path, default=REPORTS_DIR / 'altcoin_research')
    args = parser.parse_args()
    if args.days <= 0 or args.horizon <= 0 or not math.isfinite(args.threshold) or args.threshold <= 0:
        parser.error('Days, horizon and threshold must be positive finite values')
    excluded, included = symbols(args.exclude), symbols(args.markets)
    if args.command == 'download':
        markets = [m for m in choose_markets(args.markets, None) if m not in excluded]
        if not markets:
            parser.error('No eligible markets after exclusions')
        end = parse_utc(args.end) or datetime.now(timezone.utc).replace(second=0, microsecond=0)
        args.db.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(args.db)) as db:
            init_db(db)
            download_all(db, markets, end - timedelta(days=args.days), end)
        return
    if not args.db.is_file():
        parser.error('Database missing. First run: python -m coin_analysis.altcoin_research download')
    try:
        report = analyze(args.db, excluded, included, args.days, args.horizon, args.threshold)
    except (ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    args.output.with_suffix('.md').write_text(render(report), encoding='utf-8')
    print('REPORT', args.output.with_suffix('.md'))


if __name__ == '__main__':
    main()
