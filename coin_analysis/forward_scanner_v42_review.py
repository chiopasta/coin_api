"""Read-only review of separate V4.2 observation episodes; no network."""
from collections import Counter
import json
from pathlib import Path
import sqlite3
import statistics
import time

from . import forward_scanner_v42 as observer
from . import forward_scanner_v4 as scanner


EVENT_POLICY=dict(horizon_minutes=60,thresholds_pct=[5,10],grid_seconds=300,
    reference='First fully observed 5-minute anchor whose future high hits target; suppress new same-threshold anchor through t+60m',
    early_reference='Actual LIVE detected_at in [anchor-30m,anchor]; NOT certified onset prediction',
    chase='Actual LIVE detected_at in (anchor,first_target_close)',
    late='Actual LIVE detected_at in [first_target_close,anchor+60m]',
    population='Only new episode, fixed four alts per venue, exact anchor and full future 60m; exclude bootstrap')


def describe(values):
    x=[v for v in values if v is not None]
    return dict(n=len(x),mean=statistics.fmean(x) if x else None,median=statistics.median(x) if x else None,
                positive_pct=100*sum(v>0 for v in x)/len(x) if x else None)


def events_at(series,signals,start,end,target):
    grid=eligible=0;events=[];blocked_until=-1
    for t in range(start,end-3600+1,300):
        grid+=1;price=series.price(t);a,b=series.bounds(t,t+3600)
        if price is None or b-a!=60:continue
        eligible+=1
        if t<=blocked_until:continue
        hit=next((series.times[i] for i in range(a,b) if 100*(series.high[i]/price-1)>=target),None)
        if hit is None:continue
        blocked_until=t+3600
        detections=[r['detected_at'] for r in signals if r['source']=='LIVE']
        early=[x for x in detections if t-1800<=x<=t]
        chase=[x for x in detections if t<x<hit]
        late=[x for x in detections if hit<=x<=t+3600]
        kind='early_reference' if early else 'chase' if chase else 'after_target' if late else 'miss'
        events.append(dict(anchor=t,first_target_close=hit,threshold_pct=target,kind=kind,
                           early_detections=early,chase_detections=chase,late_detections=late))
    return dict(grid_anchors=grid,eligible_full_future_anchors=eligible,events=events)


def snapshot(path):
    source=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        target=sqlite3.connect(':memory:');source.backup(target);target.row_factory=sqlite3.Row
        return target
    finally:source.close()


def review_episode(root):
    root=Path(root).resolve()
    if root.parent!=observer.RUNTIME_ROOT.resolve():raise ValueError('Only isolated V4.2 runtime may be reviewed')
    config=json.loads((root/'config.json').read_text(encoding='utf8'))
    summary=json.loads((root/'worker_summary.json').read_text(encoding='utf8'))
    supervisor=json.loads((root/'supervisor_exit.json').read_text(encoding='utf8'))
    if not supervisor['worker_reaped']:raise ValueError('Cannot claim a finalized run while worker not reaped')
    log=[];incomplete_log=False
    for line in (root/'events.jsonl').read_text(encoding='utf8').splitlines():
        try:log.append(json.loads(line))
        except ValueError:incomplete_log=True
    starts=[r for r in log if r['kind']=='HTTP_START']
    ends=[r for r in log if r['kind']=='HTTP_END'];errors=[r for r in log if r['kind']=='HTTP_ERROR']
    rounds=[r for r in log if r['kind']=='ROUND_COMPLETE']
    per_exchange={}
    for exchange in observer.HOSTS:
        path=root/(exchange.lower()+'.db')
        if not path.exists():continue
        db=snapshot(path)
        try:
            cfg=scanner.config(db);states=[dict(r) for r in db.execute('SELECT * FROM scanner_state ORDER BY market')]
            end=min(r['verified_until'] for r in states)
            signals=[dict(r) for r in db.execute('SELECT * FROM signals ORDER BY signal_time')]
            details={r['signal_id']:dict(r) for r in db.execute('SELECT * FROM live_signal_details')}
            metric_rows=[dict(r) for r in db.execute('SELECT * FROM live_horizons ORDER BY signal_id,minutes')]
            for row in signals:
                row['details']=details.get(row['signal_id'])
                feature=db.execute('SELECT * FROM signal_features WHERE signal_id=?',(row['signal_id'],)).fetchone()
                row['features']=json.loads(feature['values_json'])
                row['horizons']=[r for r in metric_rows if r['signal_id']==row['signal_id']]
            horizon_summary={}
            live_ids={r['signal_id'] for r in signals if r['source']=='LIVE'}
            for h in (5,15,30,60):
                rows=[r for r in metric_rows if r['minutes']==h and r['signal_id'] in live_ids]
                complete=[r for r in rows if r['status']=='COMPLETE']
                horizon_summary[str(h)]=dict(complete=len(complete),pending=len(rows)-len(complete),
                    return_pct=describe([r['return_pct'] for r in complete]),
                    mfe_pct=describe([r['mfe_pct'] for r in complete]),mae_pct=describe([r['mae_pct'] for r in complete]))
            recall={}
            research=scanner.load_research(db,cfg['collection_start'],end)
            range_panel={}
            for market,series in research.panel.items():
                widths=[];missing=0;grid=0
                processed=next(state['last_observation'] for state in states if state['market']==market)
                for t in range(cfg['start'],min(end//300*300,processed)+1,300):
                    grid+=1;high,low=series.high_low(t-1800,t)
                    if high is None or low is None:missing+=1
                    else:widths.append(100*(high/low-1))
                range_panel[market]=dict(grid=grid,valid=len(widths),missing=missing,
                    range30_max_pct=max(widths,default=None),at_or_above4=sum(x>=4 for x in widths))
            for target in EVENT_POLICY['thresholds_pct']:
                all_events=[];grid=eligible=0
                for market,series in research.panel.items():
                    info=events_at(series,[r for r in signals if r['market']==market],cfg['start'],end,target)
                    grid+=info['grid_anchors'];eligible+=info['eligible_full_future_anchors']
                    all_events.extend(dict(market=market,**r) for r in info['events'])
                counts=Counter(r['kind'] for r in all_events);n=len(all_events)
                recall[str(target)]=dict(grid_anchors=grid,eligible_full_future_anchors=eligible,events=n,
                    counts=dict(counts),capture_before_target_pct=100*(counts['early_reference']+counts['chase'])/n if n else None,
                    early_reference_pct=100*counts['early_reference']/n if n else None,cases=all_events,
                    verdict='INSUFFICIENT_DATA' if not eligible or not n else 'EXPLORATORY_ONLY')
            episodes=[dict(r) for r in db.execute('SELECT * FROM scanner_cycles ORDER BY cycle_id')]
            counts=[dict(r) for r in db.execute('SELECT market,COUNT(*) AS total,SUM(ts>=?) AS new_candles,MIN(ts) AS first_ts,MAX(ts) AS last_ts FROM minute_candles GROUP BY market',(cfg['start'],))]
            duplicates=db.execute('SELECT COUNT(*) FROM (SELECT market,signal_time,COUNT(*) AS n FROM signals GROUP BY market,signal_time HAVING n>1)').fetchone()[0]
            quality=dict(quick_check=db.execute('PRAGMA quick_check').fetchone()[0],duplicate_signals=duplicates,
                duplicate_candles=db.execute('SELECT COUNT(*) FROM (SELECT market,ts,COUNT(*) AS n FROM minute_candles GROUP BY market,ts HAVING n>1)').fetchone()[0],
                future_candles_at_stop=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts+60>?',(int(summary['worker_ended_at']),)).fetchone()[0],
                timestamp_misalignment=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts%60<>0').fetchone()[0],
                orphan_features=db.execute('SELECT COUNT(*) FROM signal_features f LEFT JOIN signals s USING(signal_id) WHERE s.signal_id IS NULL').fetchone()[0],
                unfinished_collection_jobs=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0],
                collection_errors=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')],
                late_candles=db.execute('SELECT COUNT(*) FROM scanner_late_candles').fetchone()[0])
            repeated={m:n for m,n in Counter(r['market'] for r in signals).items() if n>1}
            per_exchange[exchange]=dict(config=cfg,states=states,signal_count=len(signals),source_counts=dict(Counter(r['source'] for r in signals)),
                signals=signals,horizon_summary=horizon_summary,recall=recall,quality=quality,candle_counts=counts,
                range_observation_panel=range_panel,
                common_verified_until=end,last_observation=min(r['last_observation'] for r in states if r['market']!='KRW-BTC'),
                cycles=len(episodes),cycle_statuses=dict(Counter(r['status'] for r in episodes)),
                new_label_statistics=scanner.grouped_statistics(db),repeated_market_signals=repeated,
                immediate_declines=[r for r in signals if any(h['minutes']==5 and h['status']=='COMPLETE' and h['return_pct']<0 for h in r['horizons'])],
                additional_surge_cases=[dict(r) for r in db.execute("SELECT s.market,s.signal_time,s.detected_at,o.* FROM signal_outcomes o JOIN signals s USING(signal_id) WHERE s.source='LIVE' AND o.status='SUCCESS'")])
        finally:db.close()
    return dict(runtime=str(root),config=config,worker=summary,supervisor=supervisor,
        process_interval=dict(start=summary['worker_started_at'],end=summary['worker_ended_at']),
        http=dict(attempts=len(starts),successes=len(ends),errors=len(errors),error_details=errors,
                  count_matches_worker=len(starts)==summary['requests'],incomplete_log=incomplete_log,
                  first_attempt=starts[0]['at'] if starts else None,last_response=ends[-1]['at'] if ends else None),
        round_completion_gaps_seconds=describe([b['at']-a['at'] for a,b in zip(rounds,rounds[1:])]),
        event_policy=EVENT_POLICY,per_exchange=per_exchange,
        historical_cohort_merged=False,score_policy='NULL; V4 never defined a score',
        price_metrics='Unlevered price changes versus signal confirmed close; no fees/slippage, no actual fills',
        performance_verdict='INSUFFICIENT_DATA')
