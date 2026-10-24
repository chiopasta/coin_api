"""Bounded, read-only audit. Run from repo root; writes only beside this file.

No strategy tuning, scanner cycles, downloads, orders or source DB writes.
The optional public probe is exactly 8 single-attempt BTC requests, timeout 4s
each, total admission deadline 40s. It does not run either legacy scanner.
"""
import ast
from bisect import bisect_left
from collections import Counter, defaultdict, deque
from contextlib import closing, redirect_stdout
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import statistics as st
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from coin_analysis import forward_scanner_v4 as v4
from coin_analysis import forward_scanner_v4_operations as ops
from coin_analysis import forward_surge_research_v3 as v3
from coin_analysis import backtest_v16 as bt

OUT = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def stamp(t):
    return datetime.fromtimestamp(t, KST).isoformat() if t is not None else None


def readonly(path):
    db = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


def stats(values):
    x = [v for v in values if v is not None]
    return dict(n=len(x), mean=st.fmean(x) if x else None,
                median=st.median(x) if x else None,
                positive_pct=100*sum(v > 0 for v in x)/len(x) if x else None,
                min=min(x, default=None), max=max(x, default=None))


def corr(pairs):
    pairs = [(x,y) for x,y in pairs if x is not None and y is not None]
    def pearson(a,b):
        if len(a)<3 or len(set(a))<2 or len(set(b))<2:
            return None
        return st.correlation(a,b)
    def ranks(a):
        result = [0.]*len(a)
        order = sorted(range(len(a)), key=a.__getitem__)
        i = 0
        while i<len(order):
            j=i+1
            while j<len(order) and a[order[j]]==a[order[i]]:j+=1
            for k in order[i:j]:result[k]=(i+j-1)/2
            i=j
        return result
    a=[p[0] for p in pairs]; b=[p[1] for p in pairs]
    return dict(n=len(a), pearson=pearson(a,b), spearman=pearson(ranks(a),ranks(b)))


def near(a,b):
    if a is None or b is None:return a is b
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):
        return math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-7)
    return a==b


def path_metrics(s,t,price,h):
    a,b=s.bounds(t,t+h*60)
    if b-a!=h or s.price(t+h*60) is None:return None
    return dict(return_pct=v3.v2.old.pct(s.price(t+h*60),price),
                mfe_pct=v3.v2.old.pct(max(s.high[a:b]),price),
                mae_pct=v3.v2.old.pct(min(s.low[a:b]),price))


def legacy_reproduction():
    # Never import V15: module import creates a DB and starts network/threads.
    source=(ROOT/'archive/scanner_v15.py').read_text(encoding='utf8')
    tree=ast.parse(source)
    names={'finish_minute','upbit_message','calculate_score'}
    module=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    ns=dict(json=json, prices={'UPBIT':{'KRW-X':100.}},
            current_minute={'UPBIT':0},current_volume={'UPBIT':defaultdict(float,{'KRW-X':20.})},
            data={'UPBIT':defaultdict(lambda:deque(maxlen=120))},
            minute_prices={'UPBIT':defaultdict(lambda:deque(maxlen=120))})
    exec(compile(module,'V15_AST_SELECTED_ONLY','exec'),ns)
    ns['upbit_message'](None,json.dumps(dict(type='trade',code='KRW-X',trade_price=110.,trade_volume=1.,trade_timestamp=60000)))
    possible={ns['calculate_score'](a,b,c,d,e,f)
              for a in (0,3,5,10) for b in (0,3,5) for c in (0,2,3)
              for d in (0,.3,.7) for e in (-3,0,1,3) for f in (0,3,20,30)}
    return dict(boundary_previous_price=100.,actual_previous_close=ns['minute_prices']['UPBIT']['KRW-X'][-1],
                actual_current_minute_value=ns['current_volume']['UPBIT']['KRW-X'],
                possible_scores=sorted(possible),scores_60_64=sorted(possible & set(range(60,65))),
                preload_example=dict(trades=[[100,1],[200,1]],true_value=300,close_times_quantity=400))


def historical_verification():
    out={}
    for tag,db_name,report_name in [
        ('discovery','research_market_v1','forward_surge_v3_range_validation'),
        ('validation','research_market_validation_v1','forward_surge_v3_independent_validation')]:
        manifest,panel,btc=v3.v2.load_manifest_dataset(ROOT/'data'/f'{db_name}.db')
        report=json.loads((ROOT/'reports'/f'{report_name}.json').read_text(encoding='utf8'))
        saved=report['cluster_first_observations']['4'] if tag=='discovery' else report['analysis']['signal_first_observations']
        actual=[];valid_range=0
        for m,s in panel.items():
            active=False
            for t in range(manifest['collection_start'],manifest['research_end'],300):
                hi,lo=s.high_low(t-1800,t);width=v3.v2.old.pct(hi,lo)
                if width is None:continue
                if t>=manifest['research_start']:valid_range+=1
                if width<4:active=False
                elif not active:
                    active=True
                    if t>=manifest['research_start']:actual.append((m,t))
        expected={(r['market'],r['t']) for r in saved}
        mismatch=Counter();labels={}
        for label,(h,target) in v4.LABELS.items():
            valid=success=0
            for r in saved:
                s=panel[r['market']];t=r['t'];p=s.price(t)
                met=path_metrics(s,t,p,h)
                old=r['labels'][label]
                if (met is not None)!=old['complete']:mismatch['completeness']+=1
                if met:
                    valid+=1;hit=met['mfe_pct']>=target;success+=hit
                    if hit!=old['value'] or not near(met['mfe_pct'],old['max_rise_pct']):mismatch['outcome']+=1
            labels[label]=dict(valid=valid,success=success,rate_pct=100*success/valid)
        out[tag]=dict(signals=len(saved),valid_range_observations=valid_range,
                      cluster_symmetric_difference=sorted(set(actual)^expected),
                      outcome_mismatches=dict(mismatch),labels=labels)
        print('HISTORICAL',tag,len(saved),dict(mismatch),flush=True)
    stored=json.loads((ROOT/'reports/backtest_v16_result.json').read_text(encoding='utf8'))
    with redirect_stdout(io.StringIO()):
        actual=bt.run_backtest(ROOT/'data/historical_market.db',bt.ProxyConfig(**stored['config']),(30,60,360,1440,4320))
    out['v16_proxy']=dict(signals=len(actual['events']),events_exact_match=actual['events']==stored['events'],
                         summary_exact_match=actual['summary']==stored['summary'],summary=actual['summary'])
    return out


def recall(panel,signals,start,end):
    """EXPLORATORY: first full-future qualifying 5m anchor, 60m non-overlap.

    It is a retrospective reference, not a claim about the true rally onset.
    Policy-time replay and actually emitted LIVE alarms are separate views.
    """
    result={}
    for target in (5,10):
        events=[];eligible=0;grid=0
        for m,s in panel.items():
            blocked=-1;ms=[r for r in signals if r['market']==m]
            for t in range(start,end-3600+1,300):
                grid+=1;p=s.price(t);a,b=s.bounds(t,t+3600)
                if p is None or b-a!=60:continue
                eligible+=1
                if t<=blocked:continue
                hit=next((s.times[i] for i in range(a,b) if v3.v2.old.pct(s.high[i],p)>=target),None)
                if hit is None:continue
                blocked=t+3600
                e=dict(market=m,t=t,target_pct=target,hit_time=hit,anchor_price=p,
                       future_60m_value=s.values(t,t+3600),past_30m_complete=s.full(t-1800,t),views={})
                for view in ('policy_replay','emitted_live'):
                    times=[r['signal_time'] if view=='policy_replay' else r['detected_at']
                           for r in ms if view=='policy_replay' or r['source']=='LIVE']
                    early=[x for x in times if t-1800<=x<=t]
                    chase=[x for x in times if t<x<hit]
                    late=[x for x in times if hit<=x<=t+3600]
                    category='early_reference' if early else 'before_target_chase' if chase else 'after_target' if late else 'miss'
                    e['views'][view]=dict(category=category,early=len(early),chase=len(chase),late=len(late))
                events.append(e)
        summaries={}
        for view in ('policy_replay','emitted_live'):
            counts=Counter(e['views'][view]['category'] for e in events)
            n=len(events)
            summaries[view]=dict(counts=dict(counts),events=n,
                capture_before_target_pct=100*(counts['early_reference']+counts['before_target_chase'])/n if n else None,
                early_reference_pct=100*counts['early_reference']/n if n else None,
                chase_pct=100*counts['before_target_chase']/n if n else None,
                repeated_notifications_events=sum(sum(e['views'][view][k] for k in ('early','chase','late'))>1 for e in events))
        result[str(target)]=dict(grid_anchors=grid,eligible_full_future_anchors=eligible,
            eligible_share_pct=100*eligible/grid if grid else None,summaries=summaries,
            by_market=dict(Counter(e['market'] for e in events)),events=events)
    return result


def live_audit():
    with closing(readonly(ROOT/'data/forward_scanner_v4.db')) as source:
        db=sqlite3.connect(':memory:');source.backup(db)
    db.row_factory=sqlite3.Row
    cfg=v4.config(db);start=cfg['start']
    states=[dict(r) for r in db.execute('SELECT * FROM scanner_state ORDER BY market')]
    end=min(r['verified_until'] for r in states)
    research=v4.load_research(db,cfg['collection_start'],max(r['verified_until'] for r in states))
    signals=[dict(r) for r in db.execute('SELECT * FROM signals ORDER BY signal_time,market')]
    checks=Counter();rows=[]
    for r in signals:
        t=r['signal_time'];m=r['market'];s=research.panel[m];p=r['signal_price']
        fs=dict(db.execute('SELECT * FROM signal_features WHERE signal_id=?',(r['signal_id'],)).fetchone())
        computed=v3.features(research,m,t)
        for k,x in json.loads(fs['values_json']).items():
            if not near(x,computed['values'][k]):checks['feature_'+k]+=1
        if json.loads(fs['flags_json'])!=computed['flags']:checks['flags']+=1
        if fs['asof_time']!=t or not near(s.price(t),p) or t%300:checks['time_or_price']+=1
        if ops.source_for(t,r['detected_at'])!=r['source']:checks['source']+=1
        if r['delay_seconds']!=max(0,r['detected_at']-t):checks['delay']+=1
        candidates=json.loads(fs['observed_candidates_json'])
        if any(not near(x,computed['values'][k]) for k,x in candidates.items()):checks['candidates']+=1
        for o in db.execute('SELECT * FROM signal_outcomes WHERE signal_id=?',(r['signal_id'],)):
            h,target=v4.LABELS[o['label']];met=path_metrics(s,t,p,h)
            a,b=s.bounds(t,t+h*60)
            if b-a!=o['observed_minutes']:checks['observed_minutes']+=1
            if o['status'] in ('SUCCESS','FAILURE'):
                hit=next((s.times[i] for i in range(a,b) if v3.v2.old.pct(s.high[i],p)>=target),None)
                if not met or not near(met['mfe_pct'],o['max_return']) or hit!=o['first_target_time'] or (hit is not None)!=(o['status']=='SUCCESS'):
                    checks['terminal_outcome']+=1
            elif o['status']=='UNKNOWN' and met is not None:checks['unknown_now_complete']+=1
        r['features']=computed['values']
        r['paths']={str(h):path_metrics(s,t,p,h) for h in (1,5,15,30,60)}
        # Operational view starts at the first minute close AFTER actual emission.
        # It is still an observed-close proxy, not an executable entry price.
        operational_t=math.ceil(r['detected_at']/60)*60
        op_price=s.price(operational_t)
        r['emitted_paths']={str(h):path_metrics(s,operational_t,op_price,h) if op_price else None for h in (1,5,15,30,60)}
        rows.append(r)
    actual=set()
    for m,s in research.panel.items():
        active=None
        state=next(x for x in states if x['market']==m)
        for t in range(cfg['collection_start'],state['last_observation']+1,300):
            hi,lo=s.high_low(t-1800,t);width=v3.v2.old.pct(hi,lo)
            if width is not None and width<4:active=False
            elif width is not None and width>=4 and active is False:
                active=True
                if t>=start:actual.add((m,t))
    expected={(r['market'],r['signal_time']) for r in rows}
    summary={}
    for source in ('LIVE','CATCHUP','ALL'):
        subset=[r for r in rows if source=='ALL' or r['source']==source]
        summary[source]=dict(count=len(subset),market_counts=dict(Counter(r['market'] for r in subset)),
            delays_seconds=stats([r['delay_seconds'] for r in subset]),
            past30_nonpositive=sum(r['features']['return_30m_pct'] is not None and r['features']['return_30m_pct']<=0 for r in subset),
            past30_missing=sum(r['features']['return_30m_pct'] is None for r in subset),
            last_signal=stamp(max((r['signal_time'] for r in subset),default=None)),
            paths={h:{metric:stats([r['paths'][h][metric] if r['paths'][h] else None for r in subset]) for metric in ('return_pct','mfe_pct','mae_pct')} for h in ('1','5','15','30','60')},
            emitted_paths={h:stats([r['emitted_paths'][h]['return_pct'] if r['emitted_paths'][h] else None for r in subset]) for h in ('1','5','15','30','60')},
            immediate_drop_5m=sum(r['paths']['5'] is not None and r['paths']['5']['return_pct']<0 for r in subset),
            value_return_correlation={h:corr([(r['features']['trade_value_ratio'],r['paths'][h]['return_pct'] if r['paths'][h] else None) for r in subset]) for h in ('30','60')},
            existing_value_double_groups={str(flag):stats([r['paths']['60']['return_pct'] if r['paths']['60'] else None for r in subset if (r['features']['trade_value_ratio']>=2 if r['features']['trade_value_ratio'] is not None else None)==flag]) for flag in (True,False)},
            market_60m_returns={m:stats([r['paths']['60']['return_pct'] if r['paths']['60'] else None for r in subset if r['market']==m]) for m in sorted({r['market'] for r in subset})})
    cycles=[dict(r) for r in db.execute('SELECT * FROM scanner_cycles ORDER BY cycle_id')]
    sessions=[dict(r) for r in db.execute('SELECT * FROM scanner_sessions ORDER BY started_at')]
    errors=[r for r in cycles if r['status']=='ERROR' or r['error'] or r['api_errors_json'] not in (None,'[]')]
    counts=dict(db.execute('SELECT market,COUNT(*) FROM minute_candles WHERE ts>=? AND ts<? GROUP BY market',(start,end)))
    expected_candles=len(cfg['markets'])*(end-start)//60
    result=dict(config=cfg,quick_check=db.execute('PRAGMA quick_check').fetchone()[0],
        counts={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('minute_candles','signals','signal_features','signal_outcomes','collection_jobs')},
        stats=v4.grouped_statistics(db),integrity_mismatches=dict(checks),cluster_symmetric_difference=sorted(actual^expected),
        coverage=dict(start=stamp(start),common_verified_until=stamp(end),observed_candles=sum(counts.values()),expected_candles=expected_candles,
                      candle_coverage_pct=100*sum(counts.values())/expected_candles,by_market=counts),
        states=states,sessions=sessions,cycles=dict(count=len(cycles),status_counts=dict(Counter(r['status'] for r in cycles)),
        last_complete=next((r for r in reversed(cycles) if r['status']=='COMPLETE'),None),errors=errors),
        summaries=summary,signals=rows,recall=recall(research.panel,rows,start,end))
    db.close()
    return result


def public_probe():
    started=time.monotonic();result=[]
    for exchange,host in [('UPBIT','https://api.upbit.com'),('BITHUMB','https://api.bithumb.com')]:
        for path in ['/v1/ticker?markets=KRW-BTC']+[f'/v1/candles/minutes/{m}?market=KRW-BTC&count=21' for m in (1,5,15)]:
            if time.monotonic()-started>=40:
                result.append(dict(exchange=exchange,path=path,status='SKIP_DEADLINE'));continue
            began=time.monotonic()
            try:
                req=urllib.request.Request(host+path,headers={'User-Agent':'CHIO-readonly-audit/1.0'})
                with urllib.request.urlopen(req,timeout=4) as response:
                    data=json.load(response); row=dict(exchange=exchange,path=path,status=response.status,
                        count=len(data),remaining_req=response.headers.get('Remaining-Req'))
                row['sample']=data[0] if data else None
                if 'candles' in path:
                    now=int(time.time());closed=[]
                    minutes=int(path.split('/minutes/')[1].split('?')[0])
                    for candle in data:
                        t=int(datetime.fromisoformat(candle['candle_date_time_utc']).replace(tzinfo=timezone.utc).timestamp())
                        if t+minutes*60<=now:closed.append(candle)
                    row['closed_count']=len(closed)
                    row['closed_ma5']=st.fmean(c['trade_price'] for c in closed[:5]) if len(closed)>=5 else None
                    row['closed_ma20']=st.fmean(c['trade_price'] for c in closed[:20]) if len(closed)>=20 else None
                    row['latest_value_field']=data[0].get('candle_acc_trade_price') if data else None
            except Exception as exc:row=dict(exchange=exchange,path=path,status='ERROR',error=repr(exc))
            row['elapsed_seconds']=time.monotonic()-began;result.append(row)
    return dict(market='KRW-BTC',request_budget=8,timeout_seconds=4,admission_deadline_seconds=40,
                total_seconds=time.monotonic()-started,at_kst=datetime.now(KST).isoformat(),requests=result,
                limitations='REST endpoint probe only; no WebSocket, universe, live signals or trade execution validation')


def main():
    paths=sorted(set(list((ROOT/'data').glob('*.db'))+list((ROOT/'reports').glob('*.*'))+
        [ROOT/'docs/forward_surge_v3_validation_policy.json',ROOT/'docs/research_market_validation_v1_manifest.json']))
    before={p.relative_to(ROOT).as_posix():digest(p) for p in paths if p.is_file()}
    result=dict(at_kst=datetime.now(KST).isoformat(),classification='EXPLORATORY',legacy=legacy_reproduction())
    result['v4']=live_audit();print('V4 COMPLETE',flush=True)
    result['historical']=historical_verification()
    prior=json.loads((ROOT/'reports/forward_surge_v3_independent_validation.json').read_text(encoding='utf8'))['hashes']
    mapping=dict(discovery='data/research_market_v1.db',validation='data/research_market_validation_v1.db',
                 policy='docs/forward_surge_v3_validation_policy.json',manifest='docs/research_market_validation_v1_manifest.json')
    result['historical_custody_matches']={k:before[path]==prior[k]['after'] for k,path in mapping.items()}
    after={p.relative_to(ROOT).as_posix():digest(p) for p in paths if p.is_file()}
    result['custody']=dict(before=before,after=after,unchanged=before==after)
    assert before==after,'Original input changed during audit'
    if '--probe' in sys.argv:result['public_probe']=public_probe()
    # Refuse accidental replacement even within this diagnostic directory.
    with (OUT/'evidence.json').open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print('SAVED',OUT/'evidence.json',flush=True)


if __name__=='__main__':main()
