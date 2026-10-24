"""Read-only legacy DB audit, fixed requested experiment only; no grid search.

Separate from the current V4 evidence. Adjacent original project is never run.
Reuses its guarded read-only analyzer's decoders and fixed-path simulator.
"""
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

from audit import ROOT, OUT, digest, readonly, stats, corr, near

LEGACY = Path('C:/dev/coin_API')
spec = importlib.util.spec_from_file_location('legacy_analyzer', LEGACY/'db_analyzer_v7.py')
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)  # module is main-guarded; no DB or network side effects


def dt(s):
    return datetime.fromisoformat(s) if s else None


def equity(values):
    additive=peak=drawdown=0.; capital=high=1.;mdd=0.
    for x in values:
        additive+=x;peak=max(peak,additive);drawdown=max(drawdown,peak-additive)
        capital*=1+x/100;high=max(high,capital);mdd=max(mdd,100*(1-capital/high))
    return dict(sum_pct_points=sum(values),serial_compound_pct=100*(capital-1),
                serial_mdd_pct=mdd,additive_max_drawdown_pct_points=drawdown,
                caveat='Synthetic serial reinvestment; actual positions overlap. Not a portfolio or realized return.')


def summarize_trades(rows):
    closed=[r for r in rows if r['status']=='CLOSED' and r['pnl_pct'] is not None]
    closed.sort(key=lambda r:(r.get('exit_at') or r['entry_at'],r['id']))
    return dict(total=len(rows),closed=len(closed),open=sum(r['status']=='OPEN' for r in rows),
        returns=stats([r['pnl_pct'] for r in closed]),equity=equity([r['pnl_pct'] for r in closed]),
        exit_reasons=dict(Counter(r['exit_reason'] for r in closed)),
        markets=dict(Counter(r['market'] for r in rows)),
        start=min((r['entry_at'] for r in rows),default=None),end=max((r['entry_at'] for r in rows),default=None))


def main():
    sources=[LEGACY/n for n in ('crypto_scanner.db','scanner_v15.py','scanner_v16.py','db_analyzer_v7.py','db_checker_v1.py')]
    before={p.as_posix():digest(p) for p in sources}
    with closing(readonly(LEGACY/'crypto_scanner.db')) as db:
        integrity=db.execute('PRAGMA quick_check').fetchone()[0]
        raw_signals=[dict(r) for r in db.execute('SELECT * FROM signals')]
        signals=[]
        for r in raw_signals:
            r['id']=analyzer.as_int(r['id']);r['score']=analyzer.as_int(r['score'])
            for k in ('price','price_1m','price_5m','price_15m','volume_5m','volume_15m','volume_60m',
                      'return_5m','return_10m','return_30m','return_60m'):
                r[k]=analyzer.as_float(r[k])
            signals.append(r)
        smap={r['id']:r for r in signals}
        histories=analyzer.load_histories(db)
        hrows=[dict(r) for r in db.execute('SELECT * FROM signal_price_history')]
        hquality=Counter();by_observation=defaultdict(list);deltas=[]
        for r in hrows:
            sid=analyzer.as_int(r['signal_id']);minute=analyzer.as_int(r['minute'])
            delta=(dt(r['observed_at'])-dt(smap[sid]['created_at'])).total_seconds()-minute*60
            deltas.append(delta)
            if not 0<=delta<60:hquality['timestamp_outside_labeled_minute']+=1
            by_observation[(sid,r['observed_at'])].append(minute)
        hquality['multi_minute_same_observed_at_groups']=sum(len(set(ms))>1 for ms in by_observation.values())
        hquality['multi_minute_same_observed_at_rows']=sum(len(ms) for ms in by_observation.values() if len(set(ms))>1)
        hquality['decoded_duplicate_keys']=len(hrows)-sum(len(v) for v in histories.values())
        rows=analyzer.load_trades(db)
        extras={analyzer.as_int(r['id']):dict(r) for r in db.execute('SELECT * FROM pullback_paper_trades')}
        for r in rows:
            raw=extras[r['id']]
            for k in ('exit_at','tp_pct','sl_pct','exit_minute','exit_price','exit_deadline_minute'):
                r[k]=raw[k] if k=='exit_at' else analyzer.as_int(raw[k]) if k in ('exit_minute','exit_deadline_minute') else analyzer.as_float(raw[k])
        verification=Counter();mismatches=[]
        for r in rows:
            if r['status']!='CLOSED':continue
            history=histories.get(r['signal_id'],{})
            start=r['entry_minute'];end=r['exit_minute']
            if start in history and not near(history[start],r['entry_price']):verification['entry_price_mismatch']+=1
            if end in history and not near(history[end],r['exit_price']):verification['exit_price_mismatch']+=1
            if end is None or any(m not in history for m in range(start+1,end+1)):
                verification['closed_path_incomplete']+=1;continue
            first=None
            for minute in range(start+1,end+1):
                raw=100*(history[minute]/r['entry_price']-1)
                if raw>=r['tp_pct']:first=(minute,'TP',r['tp_pct']-.1);break
                if raw<=-r['sl_pct']:first=(minute,'SL',-r['sl_pct']-.1);break
                if minute>=r['exit_deadline_minute']:first=(minute,'TIME',raw-.1);break
            if first and first[0]==end and first[1]==r['exit_reason'] and near(first[2],r['pnl_pct']):
                verification['closed_path_match']+=1
            else:
                verification['closed_path_mismatch']+=1;mismatches.append(dict(id=r['id'],stored=[end,r['exit_reason'],r['pnl_pct']],replayed=first))
        fixed=[]
        for strategy in ('DIP_MINUS_1','REBOUND_2_1'):
            for low in (False,True):
                selected=[r for r in rows if r['strategy']==strategy and (not low or analyzer.score_low(r))]
                simulated=[]
                for r in selected:
                    res=analyzer.simulate(r,histories.get(r['signal_id'],{}),3.,1.5,45)
                    if res:simulated.append(dict(id=r['id'],signal_id=r['signal_id'],entry_at=r['entry_at'],pnl=res[0],reason=res[1],exchange=r['exchange'],market=r['market']))
                train,test=analyzer.chronological_split(simulated) if len(simulated)>1 else (simulated,[])
                fixed.append(dict(strategy=strategy,score_filter='60_64' if low else 'ALL',selected=len(selected),eligible=len(simulated),missing=len(selected)-len(simulated),
                    tp_pct=3.,sl_pct=1.5,deadline_from_signal_minutes=45,fee_pct=.1,slippage_pct=0,
                    all=analyzer.simulated_stats(simulated),train=analyzer.simulated_stats(train),test=analyzer.simulated_stats(test),
                    equity=equity([r['pnl'] for r in simulated]),records=simulated))
        signal_paths=[]
        for r in signals:
            h=histories.get(r['id'],{});paths={}
            for horizon in (1,5,15,30,60):
                if any(m not in h for m in range(1,horizon+1)) or r['price'] is None:paths[str(horizon)]=None;continue
                p=r['price'];values=[h[m] for m in range(1,horizon+1)]
                paths[str(horizon)]=dict(return_pct=100*(h[horizon]/p-1),mfe_pct=100*(max(values)/p-1),mae_pct=100*(min(values)/p-1))
            signal_paths.append(dict(id=r['id'],exchange=r['exchange'],market=r['market'],created_at=r['created_at'],score=r['score'],
                price=r['price'],past15_pct=r['price_15m'],trade_value_ratio=r['volume_5m'],paths=paths))
        perf={}
        for exchange in ('ALL','UPBIT','BITHUMB'):
            subset=[r for r in signal_paths if exchange=='ALL' or r['exchange']==exchange]
            perf[exchange]=dict(n=len(subset),paths={str(h):{k:stats([r['paths'][str(h)][k] if r['paths'][str(h)] else None for r in subset]) for k in ('return_pct','mfe_pct','mae_pct')} for h in (1,5,15,30,60)},
                score_30m_correlation=corr([(r['score'],r['paths']['30']['return_pct'] if r['paths']['30'] else None) for r in subset]),
                value_30m_correlation=corr([(r['trade_value_ratio'],r['paths']['30']['return_pct'] if r['paths']['30'] else None) for r in subset]),
                score_groups={str(score):stats([r['paths']['30']['return_pct'] if r['paths']['30'] else None for r in subset if r['score']==score]) for score in sorted({r['score'] for r in subset if r['score'] is not None})})
        sigtime=defaultdict(list)
        for r in signals:sigtime[(r['exchange'],r['market'])].append(dt(r['created_at']))
        cooldown_violations=[]
        for key,times in sigtime.items():
            times.sort()
            for a,b in zip(times,times[1:]):
                if (b-a).total_seconds()<1800:cooldown_violations.append(dict(exchange=key[0],market=key[1],first=a.isoformat(),second=b.isoformat(),seconds=(b-a).total_seconds()))
        # Cross-check available UPBIT paths with independent minute OHLC envelopes.
        # Legacy history is a once-per-minute sampled trade, not a minute close.
        # Use observed_at's UTC minute, never label minute, and do not pretend exact equality.
        cross=Counter();outside=[]
        with closing(readonly(ROOT/'data/altcoin_market.db')) as marketdb:
            for r in hrows:
                sid=analyzer.as_int(r['signal_id']);sig=smap[sid]
                if sig['exchange']!='UPBIT':continue
                # Legacy naive clock was local; KST is an assumption, checked explicitly.
                epoch=int((dt(r['observed_at'])-datetime(1970,1,1)).total_seconds())-9*3600
                ts=epoch//60*60
                c=marketdb.execute('SELECT low,high FROM minute_candles WHERE market=? AND ts=?',(sig['market'],ts)).fetchone()
                if c is None:cross['no_independent_candle']+=1;continue
                cross['matched_candle']+=1;p=analyzer.as_float(r['price'])
                if c['low']-1e-8<=p<=c['high']+1e-8:cross['inside_envelope']+=1
                else:
                    cross['outside_envelope']+=1
                    if len(outside)<10:outside.append(dict(signal_id=sid,observed_at=r['observed_at'],price=p,low=c['low'],high=c['high']))
        result=dict(at_kst=datetime.now().isoformat(),classification='IN_SAMPLE_EXPLORATORY',legacy_path=LEGACY.as_posix(),quick_check=integrity,
            counts={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('signals','signal_price_history','pullback_paper_trades','prepump_events','low_heat_watch')},
            signal_start=min(r['created_at'] for r in signals),signal_end=max(r['created_at'] for r in signals),
            history_end=max(r['observed_at'] for r in hrows),exchange_counts=dict(Counter(r['exchange'] for r in signals)),
            score_counts=dict(Counter(r['score'] for r in signals)),market_counts={e:dict(Counter(r['market'] for r in signals if r['exchange']==e)) for e in ('UPBIT','BITHUMB')},
            recorded_trades={s:summarize_trades([r for r in rows if r['strategy']==s]) for s in sorted({r['strategy'] for r in rows})},
            score60_64_recorded={s:summarize_trades([r for r in rows if r['strategy']==s and analyzer.score_low(r)]) for s in sorted({r['strategy'] for r in rows})},
            trade_verification=dict(verification),trade_mismatch_examples=mismatches[:10],
            history_quality=dict(hquality),history_label_time_delta_seconds=stats(deltas),
            fixed_requested_experiment=fixed,signal_performance=perf,
            cooldown_violations=cooldown_violations,independent_upbit_ohlc_check=dict(counts=dict(cross),examples=outside,timezone_assumption='legacy naive datetime assumed KST; observed_at used'),
            signal_paths=signal_paths,decoded_trades=rows)
    after={p.as_posix():digest(p) for p in sources}
    result['custody']=dict(before=before,after=after,unchanged=before==after)
    assert before==after
    with (OUT/'legacy_evidence.json').open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print('SAVED LEGACY',result['counts'],result['trade_verification'],result['history_quality'])


if __name__=='__main__':main()
