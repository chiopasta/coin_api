"""Read-only diagnosis and bounded-episode review; never writes source DBs."""
from collections import Counter
import json
import math
from pathlib import Path
import sqlite3

from coin_analysis import forward_scanner_v43 as v
from coin_analysis import scanner_observation_v45 as prices


def root_trend(rows):
    """Describe observed epochs; never extrapolate a PASS or waive a gate."""
    epochs=[];seen=set()
    for row in rows:
        status=row.get('windows',{})
        key=(status.get('source'),status.get('last_sync_display'))
        if None in key or key in seen:continue
        seen.add(key)
        if not all(isinstance(status.get(k),(int,float)) and math.isfinite(status[k]) for k in ('root_dispersion_seconds','root_distance_seconds')):
            continue
        if status['root_dispersion_seconds']<0 or status['root_distance_seconds']<0:continue
        epochs.append(dict(source=key[0],last_sync=key[1],at=row['at'],
            root_dispersion_seconds=status['root_dispersion_seconds'],root_distance_seconds=status['root_distance_seconds'],
            leap=status.get('leap'),stratum=status.get('stratum'),last_sync_error=status.get('last_sync_error')))
    decreasing=len(epochs)>=2 and all(b['root_dispersion_seconds']<a['root_dispersion_seconds'] for a,b in zip(epochs,epochs[1:]))
    same_source=len({r['source'] for r in epochs})==1
    healthy=all(r['leap']==0 and r['last_sync_error']==0 and isinstance(r['stratum'],int) and 1<=r['stratum']<=15 for r in epochs)
    ratios=[b['root_dispersion_seconds']/a['root_dispersion_seconds'] for a,b in zip(epochs,epochs[1:]) if a['root_dispersion_seconds']>0]
    return dict(epochs=epochs,strictly_decreasing_across_syncs=decreasing,unchanged_selected_source=same_source,
        ratios=ratios,consistent_with_filter_warmup=len(epochs)>=3 and decreasing and same_source and healthy,
        qualification='Inference supported by observed convergence and RFC filter behavior; internal Windows filter memory not inspected',
        admits_live=False,policy_changed=False)


def review_episode(root):
    root=Path(root);cfg=json.loads((root/'config.json').read_text(encoding='utf8'))
    v.validate_config(cfg);result={};all_grid=[];all_points=[]
    initial=json.loads(Path('reports/scanner_v48_20261025/before_resume.json').read_text(encoding='utf8'))
    for exchange in v.v42.HOSTS:
        with v.ops.readonly(root/(exchange.lower()+'.db')) as db, v.ops.readonly(root/'before_resume'/(exchange.lower()+'.db')) as old:
            append_tables=('minute_candles','signals','signal_features','collection_pages','candle_receipts','coverage_windows',
                'signal_context','live_signal_details','scanner_sessions','scanner_cycles','no_trade_evidence_v45')
            preserved={}
            for table in append_tables:
                current={tuple(r) for r in db.execute('SELECT * FROM '+table)}
                preserved[table]=all(tuple(r) in current for r in old.execute('SELECT * FROM '+table))
            terminal_preserved={}
            for table in ('live_horizons','price_horizons_v45'):
                current={tuple(r) for r in db.execute('SELECT * FROM '+table)}
                terminal_preserved[table]=all(tuple(r) in current for r in old.execute("SELECT * FROM "+table+" WHERE status='COMPLETE'"))
            current_outcomes={tuple(r) for r in db.execute('SELECT * FROM signal_outcomes')}
            terminal_preserved['signal_outcomes']=all(tuple(r) in current_outcomes for r in old.execute("SELECT * FROM signal_outcomes WHERE status IN ('SUCCESS','FAILURE')"))
            states=[dict(r) for r in db.execute('SELECT * FROM scanner_state')]
            prior={r['market']:r for r in initial['databases'][exchange]['state']}
            progress={r['market']:all(r[k]>=prior[r['market']][k] for k in ('verified_until','last_observation')) for r in states}
            if not all(preserved.values()) or not all(terminal_preserved.values()) or not all(progress.values()):
                raise RuntimeError('Resume preservation mismatch')
            grids=[];points=[]
            for win in db.execute('SELECT * FROM coverage_windows WHERE minutes=30 ORDER BY t,market'):
                wanted=set(range(win['t']-1800,win['t'],60))
                present={r[0] for r in db.execute('''SELECT c.ts FROM minute_candles c JOIN candle_receipts r USING(market,ts)
                    WHERE c.market=? AND c.ts>=? AND c.ts<? AND r.first_received_at<=?''',
                    (win['market'],win['t']-1800,win['t'],win['recorded_at']))}
                if win['observed']!=len(present) or json.loads(win['missing_json'])!=sorted(wanted-present):
                    raise RuntimeError('Stored coverage differs from actual snapshot; preserve and diagnose late data')
                samples=[dict(ts=t,**prices.price_point(db,win['market'],t+60,win['recorded_at'])) for t in sorted(wanted)]
                entry=dict(exchange=exchange,market=win['market'],t=win['t'],recorded_at=win['recorded_at'],
                    source_status=win['status'],observed=win['observed'],expected=30,source_complete=win['observed']==30,
                    price_available=sum(p['status']=='AVAILABLE' for p in samples),
                    price_complete=all(p['status']=='AVAILABLE' for p in samples),
                    price_unavailable_reasons=Counter(p['reason'] for p in samples if p['status']!='AVAILABLE'),
                    missing=json.loads(win['missing_json']),points=samples)
                grids.append(entry);all_grid.append(entry);points.extend(samples);all_points.extend(samples)
            signals=[dict(r) for r in db.execute('SELECT * FROM signals ORDER BY signal_time')]
            times=[dict(signal_id=r['signal_id'],signal_time=r['signal_time'],detected_at=r['detected_at'],delay_seconds=r['delay_seconds'],
                source=r['source'],grid_aligned=r['signal_time']%300==0,delay_matches=r['delay_seconds']==r['detected_at']-r['signal_time']) for r in signals]
            result[exchange]=dict(quick_check=db.execute('PRAGMA quick_check').fetchone()[0],states=states,signals=signals,signal_times=times,
                candles=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],
                warmup_candles=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts<?',(cfg['signal_start'],)).fetchone()[0],
                after_start_candles=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts>=?',(cfg['signal_start'],)).fetchone()[0],
                duplicated_signals=db.execute('SELECT COUNT(*) FROM (SELECT market,signal_time,COUNT(*) n FROM signals GROUP BY market,signal_time HAVING n>1)').fetchone()[0],
                candle_alignment_errors=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts%60!=0').fetchone()[0],
                pending_jobs=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0],
                collection_errors=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')],
                no_trade_evidence=db.execute('SELECT COUNT(*) FROM no_trade_evidence_v45').fetchone()[0],
                score_nonnull=db.execute('SELECT COUNT(*) FROM live_signal_details WHERE score IS NOT NULL').fetchone()[0],
                horizons=[dict(r) for r in db.execute('SELECT * FROM live_horizons')],
                price_horizons=[dict(r) for r in db.execute('SELECT * FROM price_horizons_v45')],
                outcomes=[dict(r) for r in db.execute('SELECT * FROM signal_outcomes')],
                sessions=[dict(r) for r in db.execute('SELECT * FROM scanner_sessions')],grids=grids,
                prior_append_rows_preserved=preserved,prior_complete_results_preserved=terminal_preserved,state_progress_preserved=progress)
    with v.ops.readonly(root/'control.db') as db:
        requests=[dict(r) for r in db.execute('SELECT * FROM http_attempts ORDER BY seq')]
    return dict(config=cfg,per_exchange=result,signals=sum(len(r['signals']) for r in result.values()),
        actual_source_grids=dict(complete=sum(g['source_complete'] for g in all_grid),denominator=len(all_grid)),
        actual_source_slots=dict(observed=sum(g['observed'] for g in all_grid),expected=30*len(all_grid)),
        price_grids=dict(complete=sum(g['price_complete'] for g in all_grid),denominator=len(all_grid)),
        price_slots=dict(available=sum(p['status']=='AVAILABLE' for p in all_points),expected=len(all_points)),
        no_trade_live_proofs=sum(r['no_trade_evidence'] for r in result.values()),
        unknown_source_absent_slots=sum(30-g['observed'] for g in all_grid if g['source_status']=='SOURCE_ABSENT'),
        live_http_attempts=len(requests),live_http_statuses=Counter(r['status'] for r in requests),
        live_http_by_run=Counter(r['run_id'] for r in requests),
        success_http_codes=Counter(json.loads(r['details_json']).get('http_status') for r in requests if r['status']=='HTTP_END'),
        # Future data is NEVER generated just because nominal time passed.
        natural_60m_completion_verified=False,all_requests_public=all(r['endpoint'] in ('/v1/market/all','/v1/candles/minutes/1') for r in requests))
