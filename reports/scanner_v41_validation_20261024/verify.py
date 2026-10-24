"""Bounded V4.1 evidence, never changes inputs. Run from project root.

--execute-live: BTC only, 6 requests total, each timeout 4s, 40s admission
deadline, no retries, worker hard timeout 55s. Never runs a scanner cycle.
"""
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from coin_analysis import forward_scanner_v4 as s
from coin_analysis import forward_scanner_v4_operations as ops
from coin_analysis import scanner_candles as candles
from coin_analysis.legacy_open_reconciliation import digest
OUT=Path(__file__).resolve().parent


def save(name,data):
    with (OUT/name).open('x',encoding='utf8') as f:json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False)


def live_worker(bithumb_only=False):
    started=time.monotonic();cutoff=candles.closed_cutoff(time.time(),15)
    rows=[];cross=[]
    exchanges=[('BITHUMB','https://api.bithumb.com')] if bithumb_only else [('UPBIT','https://api.upbit.com'),('BITHUMB','https://api.bithumb.com')]
    for exchange,host in exchanges:
        intervals={}
        for minutes,count in [(1,60),(5,12),(15,4)]:
            record=dict(exchange=exchange,minutes=minutes,requested_count=count)
            if time.monotonic()-started>=40:
                record['status']='SKIP_DEADLINE';rows.append(record);continue
            params=dict(market='KRW-BTC',count=count,to=candles.api_to(exchange,cutoff))
            record['request_to']=params['to']
            url=host+f'/v1/candles/minutes/{minutes}?'+urllib.parse.urlencode(params)
            began=time.monotonic()
            try:
                request=urllib.request.Request(url,headers={'User-Agent':'CHIO-V4.1-bounded-validation/1.0'})
                with urllib.request.urlopen(request,timeout=4) as response:
                    raw=json.load(response);record.update(http_status=response.status,remaining_req=response.headers.get('Remaining-Req'))
                record['raw']=raw
                if not isinstance(raw,list):raise ValueError('API error payload instead of candle array')
                normalized=[candles.candle(r,'KRW-BTC',minutes,cutoff) for r in raw]
                stamps=[r[0] for r in normalized]
                if len(stamps)!=len(set(stamps)) or stamps!=sorted(stamps,reverse=True):raise ValueError('Duplicate or unordered live bars')
                intervals[minutes]={r[0]:r for r in normalized}
                record.update(status='PASS',normalized_count=len(normalized),normalized=normalized)
                # Exact source field preservation through an isolated SQLite round-trip.
                with closing(sqlite3.connect(':memory:')) as db:
                    db.execute('CREATE TABLE candles(ts PRIMARY KEY,o,h,l,c,value)')
                    db.executemany('INSERT INTO candles VALUES(?,?,?,?,?,?)',normalized)
                    read={r[0]:r[-1] for r in db.execute('SELECT * FROM candles')}
                    record['max_storage_value_difference_krw']=max((abs(read[r[0]]-float(src['candle_acc_trade_price'])) for r,src in zip(normalized,raw)),default=0)
            except Exception as exc:record.update(status='BLOCKED',error=repr(exc))
            record['seconds']=time.monotonic()-began;rows.append(record);time.sleep(.15)
        for minutes in (5,15):
            small=intervals.get(1,{});large=intervals.get(minutes,{})
            for ts,row in large.items():
                parts=[small.get(t) for t in range(ts,ts+minutes*60,60)]
                if any(p is None for p in parts):
                    cross.append(dict(exchange=exchange,minutes=minutes,ts=ts,status='NOT_REPRODUCIBLE_MISSING_COMPONENT'));continue
                summed=math.fsum(p[-1] for p in parts);native=row[-1]
                diff=abs(summed-native);tol=candles.value_tolerance(native)
                cross.append(dict(exchange=exchange,minutes=minutes,ts=ts,native_krw=native,minute_sum_krw=summed,
                                  absolute_difference_krw=diff,tolerance_krw=tol,status='PASS' if diff<=tol else 'MISMATCH'))
    save('live_bithumb_corrected.json' if bithumb_only else 'live_api.json',dict(market='KRW-BTC',max_requests=3 if bithumb_only else 6,timeout_per_request_seconds=4,
        admission_deadline_seconds=40,hard_worker_seconds=55,retries=0,cutoff_utc=s.collector.iso(cutoff),
        seconds=time.monotonic()-started,requests=rows,trade_value_cross_interval=cross,
        tolerance='max(1 KRW, native value * 1e-8); aggregate only complete aligned component bars',
        note='REST data admission and arithmetic only; not full-market, WebSocket or signal delivery validation'))


def metrics(series,t,price,h):
    a,b=series.bounds(t,t+h*60)
    if b-a!=h or series.price(t+h*60) is None:return None
    return dict(return_pct=100*(series.price(t+h*60)/price-1),
                mfe_pct=100*(max(series.high[a:b])/price-1),mae_pct=100*(min(series.low[a:b])/price-1))


def offline(output_name='before_after_checked.json'):
    with ops.readonly(ROOT/'data/forward_scanner_v4.db') as original:
        snapshot=sqlite3.connect(':memory:');original.backup(snapshot)
    snapshot.row_factory=sqlite3.Row
    cfg=s.config(snapshot);original_signals={r['signal_id']:dict(r) for r in snapshot.execute('SELECT * FROM signals')}
    end=snapshot.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0]
    db=s.connect(':memory:');s.initialize(db,cfg['markets'],cfg['start'])
    invalid=[];count=0
    # Admit existing candles through the repaired timestamp/native-value gate.
    # Original DB has no quantity; volume/value envelope verification is N/A here.
    for m in cfg['markets']:
        admitted=[]
        for row in snapshot.execute('SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? ORDER BY ts',(m,)):
            ts,o,h,l,c,v=row
            raw=dict(market=m,unit=1,candle_date_time_utc=s.collector.iso(ts)[:19],
                candle_date_time_kst=s.collector.iso(ts,s.collector.KST)[:19],opening_price=o,high_price=h,
                low_price=l,trade_price=c,candle_acc_trade_price=v)
            try:admitted.append((m,)+candles.candle(raw,m,closed_until=end))
            except ValueError as exc:invalid.append(dict(market=m,ts=ts,error=str(exc)))
        count+=len(admitted)
        with db:db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',admitted)
    with db:
        for state in snapshot.execute('SELECT market,verified_until FROM scanner_state'):
            db.execute('UPDATE scanner_state SET verified_until=? WHERE market=?',(state['verified_until'],state['market']))
    began=time.monotonic()
    s.process_observations(db,end,lambda _:None)
    s.evaluate_outcomes(db,end+s.GRACE,lambda _:None)
    rebuilt={r['signal_id']:dict(r) for r in db.execute('SELECT * FROM signals')}
    mismatches=[];feature_text_differences=0;numeric_differences=[]
    def equivalent(a,b,key):
        if isinstance(a,dict) and isinstance(b,dict):
            return a.keys()==b.keys() and all(equivalent(a[k],b[k],key+'.'+k) for k in a)
        if isinstance(a,(float,int)) and isinstance(b,(float,int)):
            if a!=b:numeric_differences.append(dict(key=key,absolute=abs(a-b),relative=abs(a-b)/max(abs(a),abs(b),1)))
            return math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-7)
        return a==b
    for sid,old in original_signals.items():
        new=rebuilt.get(sid)
        if new is None:mismatches.append(dict(signal_id=sid,kind='missing_signal'));continue
        for key in ('market','signal_time','signal_price','range_30m','cluster_id'):
            if new[key]!=old[key]:mismatches.append(dict(signal_id=sid,kind=key))
        oldf=snapshot.execute('SELECT * FROM signal_features WHERE signal_id=?',(sid,)).fetchone()
        newf=db.execute('SELECT * FROM signal_features WHERE signal_id=?',(sid,)).fetchone()
        if tuple(oldf)!=tuple(newf):feature_text_differences+=1
        if oldf['asof_time']!=newf['asof_time'] or any(not equivalent(json.loads(oldf[key]),json.loads(newf[key]),key) for key in ('values_json','flags_json','observed_candidates_json')):
            mismatches.append(dict(signal_id=sid,kind='features'))
        for oldo in snapshot.execute('SELECT * FROM signal_outcomes WHERE signal_id=?',(sid,)):
            newo=db.execute('SELECT * FROM signal_outcomes WHERE signal_id=? AND label=?',(sid,oldo['label'])).fetchone()
            for key in ('status','max_return','first_target_time','observed_minutes','expected_minutes'):
                if oldo[key]!=newo[key]:mismatches.append(dict(signal_id=sid,kind='outcome_'+key,label=oldo['label']))
    for sid in set(rebuilt)-set(original_signals):mismatches.append(dict(signal_id=sid,kind='extra_signal'))
    # Repeated processing is idempotent after a simulated persisted-state restore.
    before=ops.full_fingerprints(db)
    restarted=sqlite3.connect(':memory:');db.backup(restarted);restarted.row_factory=sqlite3.Row
    s.process_observations(restarted,end,lambda _:None);s.evaluate_outcomes(restarted,end+s.GRACE,lambda _:None)
    restart_preserved=before==ops.full_fingerprints(restarted);restarted.close()
    research=s.load_research(db,cfg['collection_start'],end)
    baseline=json.loads((ROOT/'reports/scanner_audit_20261024/evidence.json').read_text(encoding='utf8'))
    oldpaths={r['signal_id']:r['paths'] for r in baseline['v4']['signals']}
    metric_records=[];path_mismatches=[]
    for sid,row in rebuilt.items():
        paths={str(h):metrics(research.panel[row['market']],row['signal_time'],row['signal_price'],h) for h in (5,15,30,60)}
        if any(paths[str(h)]!=oldpaths[sid][str(h)] for h in (5,15,30,60)):path_mismatches.append(sid)
        metric_records.append(dict(signal_id=sid,original_source=original_signals[sid]['source'],market=row['market'],signal_time=row['signal_time'],paths=paths))
    live_summary={}
    for label in s.LABELS:
        selected=[dict(o) for o in db.execute('SELECT * FROM signal_outcomes WHERE label=?',(label,)) if original_signals[o['signal_id']]['source']=='LIVE']
        counts=Counter(o['status'] for o in selected)
        live_summary[label]=dict(counts=dict(counts),valid=counts['SUCCESS']+counts['FAILURE'],success=counts['SUCCESS'])
    performance={}
    for h in ('5','15','30','60'):
        complete=[r['paths'][h] for r in metric_records if r['original_source']=='LIVE' and r['paths'][h] is not None]
        performance[h]=dict(n=len(complete),**{key:sum(p[key] for p in complete)/len(complete) if complete else None for key in ('return_pct','mfe_pct','mae_pct')})
    reconciliation=json.loads((OUT/'legacy_reconciliation.json').read_text(encoding='utf8'))
    legacy=json.loads((ROOT/'reports/scanner_audit_20261024/legacy_evidence.json').read_text(encoding='utf8'))
    legacy_comparison={}
    for strategy in ('DIP_MINUS_1','REBOUND_2_1'):
        closed=[r['original']['pnl_pct'] for r in reconciliation['records'] if r['included_in_original_closed_statistics'] and r['original']['strategy']==strategy]
        legacy_comparison[strategy]=dict(n=len(closed),before_mean_pct=legacy['recorded_trades'][strategy]['returns']['mean'],
            after_original_record_mean_pct=math.fsum(closed)/len(closed),corrected_signal_replay='NOT_REPRODUCIBLE',
            reason='No raw trade stream/version custody to regenerate corrected legacy features or signal timestamps')
    report=dict(implementation=s.IMPLEMENTATION_VERSION,research_policy_unchanged=s.POLICY==cfg['policy'],
        original_health=ops.health(snapshot),input_candles=count,invalid_candles=invalid,original_signals=len(original_signals),rebuilt_signals=len(rebuilt),
        policy_replay_mismatches=mismatches,path_metric_mismatches=path_mismatches,restart_idempotent=restart_preserved,
        replay_seconds=time.monotonic()-began,original_live_cohort=live_summary,live_paths=performance,
        feature_text_differences=feature_text_differences,feature_numeric_differences=numeric_differences,
        feature_comparison_tolerance=dict(relative=1e-8,absolute=1e-7,basis='Same tolerance as baseline audit near(); prefix-sum accumulation depends on load window'),
        legacy_comparison=legacy_comparison,signal_metrics=metric_records,
        note='Retrospective fixed-policy replay. Source membership is original cohort, not a new LIVE run. New replay detected_at/source cannot stand in for original delivery.')
    db.close();snapshot.close();save(output_name,report)
    print('OFFLINE',count,len(rebuilt),'signal mismatches',len(mismatches),'path mismatches',len(path_mismatches),flush=True)


def preserve(output_name='preservation_final.json'):
    manifest=json.loads((OUT/'input_manifest.json').read_text(encoding='utf8'))
    checks={path:digest(path)==meta['sha256'] for path,meta in manifest['inputs'].items()}
    save(output_name,dict(files=len(checks),all_preserved=all(checks.values()),checks=checks))
    if not all(checks.values()):raise AssertionError('Original input changed')


def main():
    if '--live-worker' in sys.argv:live_worker();return
    if '--bithumb-worker' in sys.argv:live_worker(True);return
    offline('before_after_final.json' if '--final' in sys.argv else 'before_after_checked.json')
    if '--execute-live' in sys.argv:
        try:subprocess.run([sys.executable,str(Path(__file__).resolve()),'--live-worker'],check=True,timeout=55)
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as exc:
            save('live_api_blocked.json',dict(status='BLOCKED',reason=repr(exc),max_requests=6))
    if '--bithumb-corrected' in sys.argv:
        subprocess.run([sys.executable,str(Path(__file__).resolve()),'--bithumb-worker'],check=True,timeout=55)
    preserve('preservation_completion.json' if '--final' in sys.argv else 'preservation_final.json')


if __name__=='__main__':main()
