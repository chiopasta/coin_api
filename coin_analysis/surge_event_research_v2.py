"""Offline, price-defined event research. No network or trading functionality."""

import argparse
from array import array
from bisect import bisect_left, bisect_right
from collections import deque
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics

from .paths import DATA_DIR, REPORTS_DIR

OFFSETS = (5, 15, 30, 60, 120)
DEFINITIONS = {'A': (60, 10.0), 'B': (360, 20.0)}
FLAGS = {
    'return_5m_positive': '5분 수익률 > 0',
    'return_15m_positive': '15분 수익률 > 0',
    'return_30m_positive': '30분 수익률 > 0',
    'return_60m_positive': '60분 수익률 > 0',
    'trade_value_double': '최근 5분 거래대금이 이전 평균의 2배 이상',
    'trade_value_increasing': '최근 5분 거래대금 증가율 > 0',
    'trade_value_accelerating': '거래대금 가속 > 1',
    'ma5_above_ma20': '1분봉 MA5 > MA20',
    'ma20_rising': 'MA20의 5분 변화율 > 0',
    'range_expanding': '30분 고저폭이 이전 30분보다 증가',
    'prior_high_breakout': '종가가 직전 60분 고점 돌파',
    'relative_strength_positive': '60분 수익률이 타 종목 중앙값 초과',
}


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def parse_time(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = int(dt.timestamp())
    if ts % 60:
        raise ValueError('Times must be aligned to whole minutes')
    return ts


def pct(new, old):
    return (new / old - 1) * 100 if new is not None and old is not None and old > 0 else None


def identity(*parts):
    return hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:20]


class Series:
    """Sparse candles keyed by their CLOSE time; never fill absent candles."""

    def __init__(self, rows):
        self.times = array('q')
        self.high = array('d')
        self.low = array('d')
        self.close = array('d')
        self.value_prefix = array('d', [0])
        for ts, op, hi, lo, cl, value in rows:
            if (ts % 60 or (self.times and ts + 60 <= self.times[-1])
                    or not all(math.isfinite(x) and x > 0 for x in (op, hi, lo, cl))
                    or not math.isfinite(value) or value < 0
                    or lo > min(op, cl) or hi < max(op, cl)):
                raise ValueError(f'Invalid candle at {ts}')
            self.times.append(ts + 60)
            self.high.append(hi)
            self.low.append(lo)
            self.close.append(cl)
            self.value_prefix.append(self.value_prefix[-1] + value)

    def bounds(self, start, end):
        # Complete candles with close times in (start, end].
        return bisect_right(self.times, start), bisect_right(self.times, end)

    def price(self, ts):
        i = bisect_left(self.times, ts)
        return self.close[i] if i < len(self.times) and self.times[i] == ts else None

    def coverage(self, start, end):
        a, b = self.bounds(start, end)
        expected = (end - start) // 60
        return dict(observed_minutes=b-a, expected_minutes=expected,
                    coverage=(b-a)/expected if expected else None)

    def full(self, start, end):
        q = self.coverage(start, end)
        return q['observed_minutes'] == q['expected_minutes']

    def values(self, start, end):
        if not self.full(start, end):
            return None
        a, b = self.bounds(start, end)
        return self.value_prefix[b] - self.value_prefix[a]

    def return_at(self, ts, minutes):
        return pct(self.price(ts), self.price(ts-minutes*60))

    def mean_close(self, start, end):
        if not self.full(start, end):
            return None
        a, b = self.bounds(start, end)
        return statistics.fmean(self.close[a:b]) if b > a else None

    def high_low(self, start, end):
        if not self.full(start, end):
            return None, None
        a, b = self.bounds(start, end)
        return (max(self.high[a:b]), min(self.low[a:b])) if b > a else (None, None)


def feature_snapshot(series, ts):
    """Every input candle must have closed no later than ts."""
    f = {f'return_{m}m_pct': series.return_at(ts, m) for m in (5, 15, 30, 60)}
    v0 = series.values(ts-300, ts)
    v1 = series.values(ts-600, ts-300)
    v2 = series.values(ts-900, ts-600)
    prior = series.values(ts-3900, ts-300)
    baseline = prior / 12 if prior is not None else None
    ratio = v0 / baseline if v0 is not None and baseline is not None and baseline > 0 else None
    accel = (v0 / v1) / (v1 / v2) if all(v is not None and v > 0 for v in (v0, v1, v2)) else None
    ma5 = series.mean_close(ts-300, ts)
    ma20 = series.mean_close(ts-1200, ts)
    old_ma20 = series.mean_close(ts-1500, ts-300)
    hi, lo = series.high_low(ts-1800, ts)
    old_hi, old_lo = series.high_low(ts-3600, ts-1800)
    width, old_width = pct(hi, lo), pct(old_hi, old_lo)
    prior_hi, _ = series.high_low(ts-3660, ts-60)
    price = series.price(ts)
    f.update(trade_value_5m=v0, prior_mean_trade_value_5m=baseline,
             trade_value_ratio=ratio, trade_value_change_pct=pct(v0, v1),
             trade_value_acceleration=accel, ma5=ma5, ma20=ma20,
             ma5_ma20_ratio=ma5/ma20 if ma5 is not None and ma20 else None,
             ma20_slope_5m_pct=pct(ma20, old_ma20), range_30m_pct=width,
             range_change_pct=pct(width, old_width),
             distance_to_prior_high_pct=pct(prior_hi, price),
             alt_relative_60m_pct=None, btc_relative_60m_pct=None)
    flags = {f'return_{m}m_positive': f[f'return_{m}m_pct'] > 0
             if f[f'return_{m}m_pct'] is not None else None for m in (5, 15, 30, 60)}
    for name, key, limit, inclusive in (
        ('trade_value_double', 'trade_value_ratio', 2, True),
        ('trade_value_increasing', 'trade_value_change_pct', 0, False),
        ('trade_value_accelerating', 'trade_value_acceleration', 1, False),
        ('ma5_above_ma20', 'ma5_ma20_ratio', 1, False),
        ('ma20_rising', 'ma20_slope_5m_pct', 0, False),
        ('range_expanding', 'range_change_pct', 0, False)):
        v = f[key]
        flags[name] = None if v is None else v >= limit if inclusive else v > limit
    flags['prior_high_breakout'] = price > prior_hi if price is not None and prior_hi is not None else None
    flags['relative_strength_positive'] = None
    return dict(asof_ts=ts, asof_utc=iso(ts), values=f, flags=flags,
                quality=series.coverage(ts-3900, ts))


def extract_events(market, series, kind, start, end, min_coverage=.8, reset_pct=5):
    """Price-only first hits against a trailing minimum CLOSE, not a signal filter.

    t0 is retrospective: the lowest completed close before the first target hit.
    Same-family episodes stay locked until horizon expiry and a later close
    retraces reset_pct from the observed running peak.
    """
    minutes, threshold = DEFINITIONS[kind]
    horizon = minutes * 60
    lows = deque()
    events = []
    blocked_until = -math.inf
    locked = False
    running_peak = 0
    reset_seen = False
    rejected = 0
    for j, close_ts in enumerate(series.times):
        hit_start = close_ts-60
        if j:
            i = j-1
            # Latest equal low avoids moving a flat-price onset arbitrarily far back.
            while lows and series.close[lows[-1]] >= series.close[i]:
                lows.pop()
            lows.append(i)
        while lows and series.times[lows[0]] < close_ts-horizon:
            lows.popleft()
        if locked:
            if close_ts > blocked_until:
                if reset_seen or (series.high[j] <= running_peak and series.close[j] <= running_peak*(1-reset_pct/100)):
                    locked = False
                    lows.clear()  # a new episode cannot reuse the old pre-rally low
                else:
                    running_peak = max(running_peak, series.high[j])
            continue
        if not lows:
            continue
        i = lows[0]
        t0 = series.times[i]
        if t0 < start or t0+horizon > end or pct(series.high[j], series.close[i]) < threshold:
            continue
        quality = series.coverage(t0, t0+horizon)
        if quality['coverage'] < min_coverage:
            rejected += 1
            continue
        a, b = series.bounds(t0, t0+horizon)
        peak = max(range(a, b), key=lambda k: series.high[k])
        running_peak = series.high[peak]
        reset_seen = any(series.close[k] <= running_peak*(1-reset_pct/100) for k in range(peak+1, b))
        event = dict(event_id=identity('v2', market, kind, t0), market=market,
            definition=kind, horizon_minutes=minutes, threshold_pct=threshold,
            t0=t0, t0_utc=iso(t0), base_price=series.close[i],
            first_hit_bar_ts=hit_start, first_hit_bar_utc=iso(hit_start),
            first_hit_known_ts=close_ts, peak_bar_ts=series.times[peak]-60,
            peak_bar_utc=iso(series.times[peak]-60), max_rise_pct=pct(series.high[peak], series.close[i]),
            minutes_to_target_lower=(hit_start-t0)/60, minutes_to_target_upper=(close_ts-t0)/60,
            end_ts=t0+horizon, future_label=True, sampling_design='price_event_case',
            quality=dict(**quality, past_360m=series.coverage(t0-360*60,t0),
                         first_hit_window_complete=series.full(t0,close_ts),
                         extrema_policy='observed candles only; absent candles are unknown'))
        events.append(event)
        locked = True
        blocked_until = t0+horizon
    return events, rejected


def assign_episodes(events):
    """Link overlapping A/B records; counts per definition must not be summed."""
    for market in sorted({e['market'] for e in events}):
        end, episode = -1, None
        for e in sorted((e for e in events if e['market'] == market), key=lambda e:e['t0']):
            if e['t0'] >= end:
                episode = identity('episode', market, e['t0'])
            e['episode_id'] = episode
            end = max(end, e['end_ts'])


class Research:
    def __init__(self, panel, events, start, end, btc=None):
        self.panel, self.events = panel, events
        self.start, self.end, self.btc = start, end, btc
        self.used = set()
        self.market_returns = {}
        self.feature_cache = {}
        self.intervals = {}
        for e in events:
            self.intervals.setdefault((e['market'], e['definition']), []).append((e['t0'], e['end_ts']))

    def snapshot(self, market, ts):
        key = market, ts
        if key not in self.feature_cache:
            f = feature_snapshot(self.panel[market], ts)
            if ts not in self.market_returns:
                self.market_returns[ts] = {m:s.return_at(ts, 60) for m,s in self.panel.items()}
            peers = [v for m,v in self.market_returns[ts].items() if m != market and v is not None]
            own = f['values']['return_60m_pct']
            # At least three other observed assets; no missing return is replaced by zero.
            relative = own-statistics.median(peers) if own is not None and len(peers) >= 3 else None
            btc_ret = self.btc.return_at(ts, 60) if self.btc else None
            f['values']['alt_relative_60m_pct'] = relative
            f['values']['btc_relative_60m_pct'] = own-btc_ret if own is not None and btc_ret is not None else None
            f['flags']['relative_strength_positive'] = relative > 0 if relative is not None else None
            f['quality']['relative_peer_count'] = len(peers)
            self.feature_cache[key] = f
        return self.feature_cache[key]

    def snapshots(self, market, t0):
        return {str(m):self.snapshot(market, t0-m*60) for m in OFFSETS}

    def liquidity(self, market, ts):
        # Before all studied snapshots, to avoid matching away trade-value increases.
        value = self.panel[market].values(ts-360*60, ts-240*60)
        return value/120 if value is not None else None

    def control_eligible(self, market, ts, kind):
        s = self.panel[market]
        horizon, target = DEFINITIONS[kind]
        finish = ts+horizon*60
        if ts < self.start or finish > self.end or s.price(ts) is None:
            return False
        if not s.full(ts-360*60, ts) or not s.full(ts, finish):
            return False
        if any(ts < b and a < finish for a,b in self.intervals.get((market,kind), [])):
            return False
        # Reject both an anchor-relative rise and a dip-then-rally inside the window.
        a,b = s.bounds(ts, finish)
        low = s.price(ts)
        for i in range(a,b):
            if pct(s.high[i], low) >= target:
                return False
            low = min(low, s.close[i])
        return True

    def match(self, event, mode):
        market, ts, kind = event['market'], event['t0'], event['definition']
        base = self.liquidity(market, ts)
        if base is None or base <= 0:
            return None, 'case_preperiod_liquidity_unavailable'
        if mode == 'primary':
            options = [(m,ts) for m in sorted(self.panel) if m != market]
        else:
            lo, hi = max(self.start,ts-7*86400), min(self.end,ts+7*86400)
            options = [(market,t) for t in range((lo+3599)//3600*3600, hi, 3600)]
        ranked = []
        for m,t in options:
            if (mode,kind,m,t) in self.used:
                continue
            value = self.liquidity(m,t)
            if value is None or value <= 0 or not 1/3 <= value/base <= 3:
                continue
            ranked.append((abs(math.log(value/base))+abs(t-ts)/(7*86400),m,t,value))
        for score,m,t,value in sorted(ranked):
            if not self.control_eligible(m,t,kind):
                continue
            # Avoid reusing overlapping control outcomes within each control analysis.
            h = DEFINITIONS[kind][0]*60
            if any(md == mode and kd == kind and mm == m and abs(tt-t) < h
                   for md,kd,mm,tt in self.used):
                continue
            self.used.add((mode,kind,m,t))
            return dict(control_id=identity(mode,kind,m,t), market=m, t0=t, t0_utc=iso(t),
                        liquidity_ratio=value/base, match_score=score,
                        snapshots=self.snapshots(m,t),
                        future_label=False, sampling_design='matched_case_control'), None
        return None, 'no_eligible_liquidity_matched_control'


def summarize(events):
    result = []
    for kind in DEFINITIONS:
        cases = [e for e in events if e['definition'] == kind]
        for mode in ('primary', 'auxiliary'):
            matched = [e for e in cases if e['controls'][mode] is not None]
            for offset in OFFSETS:
                for flag,title in FLAGS.items():
                    pairs = [(e['snapshots'][str(offset)]['flags'][flag],
                              e['controls'][mode]['snapshots'][str(offset)]['flags'][flag]) for e in matched]
                    pairs = [(a,b) for a,b in pairs if a is not None and b is not None]
                    n = len(pairs)
                    ca = sum(a for a,b in pairs)
                    cb = sum(b for a,b in pairs)
                    result.append(dict(definition=kind, control_type=mode, feature=flag, title=title,
                        offset_minutes=offset, total_events=len(cases), matched_events=len(matched),
                        event_n=n, control_n=n, event_positive=ca, control_positive=cb,
                        missing_pairs=len(matched)-n,
                        event_rate_pct=100*ca/n if n else None,
                        control_rate_pct=100*cb/n if n else None,
                        difference_pp=100*(ca-cb)/n if n else None))
    return result


def open_readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True)
    db.execute('PRAGMA query_only=ON')
    return db


def load_series(db, market, start, end):
    return Series(db.execute('SELECT ts,open,high,low,close,trade_value FROM minute_candles '
                            'WHERE market=? AND ts>=? AND ts<? ORDER BY ts', (market,start,end)))


def run_research(path, markets=None, start=None, end=None, min_coverage=.8, btc_path=None,
                 research_class=None):
    with closing(open_readonly(path)) as db:
        available = [r[0] for r in db.execute('SELECT DISTINCT market FROM minute_candles ORDER BY market')]
        selected = sorted(set(markets or available))
        if not selected or set(selected)-set(available):
            raise ValueError('Requested markets missing from DB')
        placeholders = ','.join('?' for _ in selected)
        first,last = db.execute(f'SELECT MIN(ts),MAX(ts) FROM minute_candles WHERE market IN ({placeholders})', selected).fetchone()
        start = first+60 if start is None else start
        end = last+60 if end is None else end
        if start >= end:
            raise ValueError('Start must precede end')
        panel = {m:load_series(db,m,start-360*60,end) for m in selected}
    btc = None
    if btc_path:
        with closing(open_readonly(btc_path)) as db:
            btc = load_series(db,'KRW-BTC',start-360*60,end)
    events, coverage = [], []
    for market,s in panel.items():
        row = dict(market=market, loaded_candles=len(s.times), **s.coverage(start,end))
        row['events'] = {}
        for kind in DEFINITIONS:
            found,rejected = extract_events(market,s,kind,start,end,min_coverage)
            events.extend(found)
            row['events'][kind] = dict(events=len(found), low_coverage_candidate_hits=rejected)
        coverage.append(row)
        print('MINED',market,row['events'],flush=True)
    assign_episodes(events)
    research = (research_class or Research)(panel,events,start,end,btc)
    for e in sorted(events,key=lambda e:(e['t0'],e['market'],e['definition'])):
        e['snapshots'] = research.snapshots(e['market'],e['t0'])
        e['controls'],e['unmatched_reasons'] = {},{}
        for mode in ('primary','auxiliary'):
            c,reason = research.match(e,mode)
            e['controls'][mode] = c
            e['unmatched_reasons'][mode] = reason
        if hasattr(research, 'matching_diagnostics'):
            e['matching_diagnostics'] = research.matching_diagnostics[e['event_id']]
    return dict(version=2, status='DESCRIPTIVE_EVENT_RESEARCH_NOT_A_SIGNAL',
        source_db=str(Path(path).resolve()), start_utc=iso(start), end_utc=iso(end),
        markets=selected, definitions=DEFINITIONS, offsets_minutes=OFFSETS,
        min_event_future_coverage=min_coverage, reset_drawdown_pct=5,
        feature_policy='Exact timestamps; full windows for aggregates; exact endpoints for returns; missing=null',
        control_policy='One each; liquidity 1/3..3x at t0-360..-240m; complete past360m and future; no overlapping known event',
        probability_policy='Case-control rates are P(feature|group), never P(surge|feature). A future full risk-set table is required.',
        market_benchmark='Median of observed 60m returns of other selected DB markets; >=3 peers; membership is not historical listing reconstruction',
        btc_db=str(btc_path) if btc_path else None,
        coverage=coverage, events=events, statistics=summarize(events))


def render(report):
    lines = ['# 급등 이벤트 연구 V2', '', f"기간 UTC: {report['start_utc']} ~ {report['end_utc']}",
        f"분석 종목: {len(report['markets'])}개", '',
        '가격만으로 사건을 추출합니다. t0는 최초 목표 도달 직전 과거 구간의 최저 종가 확정 시각으로, 사후 기준점입니다. 실제 상승 시작을 실시간으로 식별했다는 뜻이 아닙니다.',
        '사전 특징에는 각 스냅샷 시각까지 완성된 봉만 사용합니다. MA5/20은 1분봉 5개/20개의 평균입니다.',
        '집계 특징은 창 전체 데이터가 있어야 계산하며, 수익률은 정확한 양 끝 종가를 요구합니다. 결측은 NULL입니다.',
        '이벤트 미래 창의 기본 관측 비율은 최소 80%입니다. 공백이 있으면 최초 도달과 최고가는 관측된 봉 기준이며 실제 최초 도달/최고가를 보장하지 않습니다. 완전한 창만 보려면 --min-event-coverage 1을 사용하세요.',
        '같은 유형은 미래 창 종료와 고점 대비 5% 되돌림을 거쳐야 다음 사건을 허용합니다. A/B 중첩은 episode_id로 연결되므로 사건 수를 합산하지 마세요.',
        '주 대조군은 같은 시점 타 종목, 보조 대조군은 같은 종목의 다른 시점입니다. 데이터 부족으로 매칭되지 않은 사건도 원본에 남깁니다.',
        '표는 유효한 매칭 쌍만 비교합니다. 조건부 상승 확률·매수 신호가 아니며 독립 검증이나 통계적 유의성을 주장하지 않습니다.',
        '시장 상대강도는 선택한 DB 종목 중 타 종목의 중앙 수익률 기준입니다. 소수 종목 실행에서는 전체 시장 지표가 아닙니다.', '',
        '## 사건 수', '', '| 유형 | 사건 | 주 대조 매칭 | 보조 대조 매칭 |', '|---|---:|---:|---:|']
    for kind in DEFINITIONS:
        es = [e for e in report['events'] if e['definition']==kind]
        lines.append(f"| {kind} | {len(es)} | {sum(e['controls']['primary'] is not None for e in es)} | {sum(e['controls']['auxiliary'] is not None for e in es)} |")
    for kind in DEFINITIONS:
        for mode in ('primary','auxiliary'):
            lines += ['',f'## {kind} / {mode}', '', '| 특징 | 이전 시점(분) | 급등군 표본수 | 대조군 표본수 | 급등군 발생률 % | 대조군 발생률 % | 차이 %p | 결측 쌍 |',
                      '|---|---:|---:|---:|---:|---:|---:|---:|']
            for r in report['statistics']:
                if r['definition']!=kind or r['control_type']!=mode:
                    continue
                cells=[r[k] for k in ('title','offset_minutes','event_n','control_n','event_rate_pct','control_rate_pct','difference_pp','missing_pairs')]
                lines.append('| '+' | '.join('N/A' if x is None else f'{x:.2f}' if isinstance(x,float) else str(x) for x in cells)+' |')
    lines += ['', '## 데이터 품질', '', '| 종목 | 기간 내 봉 수 | 예상 분 | 관측 비율 |', '|---|---:|---:|---:|']
    for r in report['coverage']:
        lines.append(f"| {r['market']} | {r['observed_minutes']} | {r['expected_minutes']} | {r['coverage']:.3f} |")
    return '\n'.join(lines)+'\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DATA_DIR/'altcoin_market.db')
    p.add_argument('--btc-db',type=Path,help='Optional existing DB; never downloaded')
    p.add_argument('--markets',nargs='+',help='Default: every market stored in DB')
    p.add_argument('--start',help='Inclusive t0 bound, ISO timestamp; naive times are UTC')
    p.add_argument('--end',help='Exclusive candle-open bound; all event horizons must finish by this time')
    p.add_argument('--min-event-coverage',type=float,default=.8)
    p.add_argument('--output',type=Path,default=REPORTS_DIR/'surge_event_research_v2')
    args=p.parse_args()
    if not 0 < args.min_event_coverage <= 1:
        p.error('Event coverage must be in (0,1]')
    if not args.db.is_file() or (args.btc_db and not args.btc_db.is_file()):
        p.error('Existing local database required; no download is performed')
    # Do not allow report destinations to replace source databases.
    sources={args.db.resolve()}
    if args.btc_db:
        sources.add(args.btc_db.resolve())
    outputs=[args.output.with_suffix(s).resolve() for s in ('.json','.md')]
    if any(o in sources for o in outputs):
        p.error('Output must not overwrite source database')
    try:
        markets=[m.upper() if m.upper().startswith('KRW-') else 'KRW-'+m.upper() for m in args.markets] if args.markets else None
        report=run_research(args.db,markets,parse_time(args.start) if args.start else None,
                            parse_time(args.end) if args.end else None,args.min_event_coverage,args.btc_db)
    except (ValueError,sqlite3.Error) as exc:
        p.error(str(exc))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    args.output.with_suffix('.md').write_text(render(report),encoding='utf-8')
    print('REPORT',args.output.with_suffix('.md'), 'EVENTS',len(report['events']))


if __name__ == '__main__':
    main()
