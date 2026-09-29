"""Read-only validation of the previously frozen 4% V3 policy; no network."""
import argparse
from collections import Counter
from contextlib import closing
import json
import math
from pathlib import Path
import statistics as st

from . import forward_range_validation as rv
from . import forward_surge_success_failure as sf
from .research_market_quality import period

v=rv.v3.v2
SECONDARY=('range_15m_pct','range_30m_pct','alt_relative_60m_pct')

def audit(path,expected,policy):
    errors=Counter();markets=[]
    with closing(v.old.open_readonly(path)) as db:
        manifest=json.loads(db.execute('SELECT payload FROM dataset_manifest WHERE id=1').fetchone()[0])
        if manifest!=expected:errors['frozen_manifest_mismatch']+=1
        if manifest.get('validation_policy')!=policy:errors['frozen_policy_mismatch']+=1
        integrity=[r[0] for r in db.execute('PRAGMA integrity_check')]
        if integrity!=['ok']:errors['sqlite_integrity']+=1
        lo,hi=manifest['collection_start'],manifest['collection_end']
        start,end=manifest['research_start'],manifest['research_end']
        columns=[r[1] for r in db.execute('PRAGMA table_info(collection_state)')]
        states=[dict(zip(columns,r)) for r in db.execute('SELECT * FROM collection_state ORDER BY market')]
        status=Counter(s['status'] for s in states)
        actual=[r[0] for r in db.execute('SELECT DISTINCT market FROM minute_candles ORDER BY market')]
        if len(manifest['markets'])!=51 or len(manifest['alts'])!=50 or 'KRW-BTC' not in actual:errors['expected_51_markets_btc']+=1
        if set(actual)!=set(manifest['markets']) or set(actual)!={s['market'] for s in states}:errors['market_mismatch']+=1
        duplicate=db.execute('SELECT COUNT(*) FROM (SELECT market,ts FROM minute_candles GROUP BY market,ts HAVING COUNT(*)>1)').fetchone()[0]
        if duplicate:errors['duplicate_market_timestamp']+=duplicate
        counts=Counter();times={m:[] for m in actual}
        for m,t,o,h,l,c,tv in db.execute('SELECT market,ts,open,high,low,close,trade_value FROM minute_candles ORDER BY market,ts'):
            counts[m]+=1
            if not isinstance(t,int) or t%60 or not lo<=t<hi:errors['timestamp_invalid']+=1
            if times[m] and t<=times[m][-1]:errors['nonincreasing_timestamp']+=1
            times[m].append(t)
            if not all(isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in (o,h,l,c)) or not l<=min(o,c)<=max(o,c)<=h:errors['ohlc_invalid']+=1
            if not isinstance(tv,(int,float)) or not math.isfinite(tv) or tv<0:errors['trade_value_invalid']+=1
        def q(ts,a,b):
            inside=[t for t in ts if a<=t<b];expected_n=(b-a)//60
            gaps=[(y-x)//60-1 for x,y in zip([a-60]+inside,inside+[b])]
            return dict(expected_minutes=expected_n,observed_minutes=len(inside),coverage_pct=100*len(inside)/expected_n,
                        longest_gap_minutes=max(gaps,default=expected_n),gap_count=sum(g>0 for g in gaps))
        for s in states:
            m=s['market']
            if s['status']!='COMPLETE' or s['last_error']:errors['collection_not_complete_or_error']+=1
            if s['requested_start']!=lo or s['requested_end']!=hi or s['next_cursor']>lo:errors['requested_range_or_cursor']+=1
            if s['rows_saved']!=counts[m]:errors['state_row_count']+=1
            pages=list(db.execute('SELECT request_cursor,verified_start,verified_end,response_count,rows_inserted FROM collection_pages WHERE market=? ORDER BY request_cursor DESC',(m,)))
            cursor=hi
            for req,a,b,n,inserted in pages:
                if req!=cursor or b!=cursor or not lo<=a<b or not 1<=n<=200:errors['page_chain_invalid']+=1
                cursor=a
            if cursor!=lo or len(pages)!=s['pages_completed'] or sum(p[4] for p in pages)!=counts[m]:errors['page_range_unverified']+=1
            ts=times[m];before=q(ts,lo,start);after=q(ts,end,hi)
            if not before['observed_minutes'] or not after['observed_minutes']:errors['missing_buffer_market']+=1
            markets.append(dict(market=m,research=q(ts,start,end),before_buffer=before,after_buffer=after,
                                first_open_ts=min(ts) if ts else None,last_open_ts=max(ts) if ts else None))
    return dict(passed=not errors,errors=dict(errors),integrity=integrity,manifest_market_count=len(manifest['markets']),
                states_count=dict(status),total_candles=sum(counts.values()),duplicates=duplicate,states=states,markets=markets,
                research_mean_coverage_pct=st.mean(m['research']['coverage_pct'] for m in markets),
                periods=dict(research=period(start,end),before_buffer=period(lo,start),after_buffer=period(end,hi)),
                coverage_basis='Candle OPEN timestamps in [start,end); feature engine uses confirmed CLOSE timestamps (open+60). Missing minutes are not filled or presumed failed downloads.')

def decide(summary):
    labels=summary['cluster']['labels'];rep=[];supported=[]
    for kind in rv.LABELS:
        s=labels[kind];ex=s['without_flock'];ex_markets=sum(m!='KRW-FLOCK' and x['positive']>0 for m,x in s['by_market'].items())
        if not s['valid'] or s['lift'] is None or ex['lift'] is None:return 'DATA_INSUFFICIENT'
        supported.append(s['lift']>1 and s['success_markets']>=3 and ex['lift']>1)
        rep.append(s['positive']>=20 and s['valid']-s['positive']>=20 and s['success_markets']>=3 and s['lift']>=1.5 and ex['lift']>1 and ex_markets>=3)
    return 'REPLICATED' if all(rep) else 'PARTIAL' if any(supported) else 'FAILED'

def summarize(observations,signals,start,end):
    obs=[r for r in observations if start<=r['t']<end];cs=[r for r in signals if start<=r['t']<end]
    baseline=rv.rates(obs);cluster=rv.describe(cs,baseline)
    result=dict(valid_range_observations=len(obs),grid_observations=50*((end-start)//300),
                signal_observations=sum(r['range']>=4 for r in obs),baseline=baseline,cluster=cluster,
                market_signal_counts=dict(Counter(r['market'] for r in cs).most_common()),
                secondary={y:{k:sf.compare(cs,y,k) for k in SECONDARY} for y in rv.LABELS},
                equal_market={})
    for y in rv.LABELS:
        # Mean of within-market rates: each market with a known outcome has weight 1.
        cr=cluster['labels'][y]['by_market'];br=baseline[y]['by_market']
        common=sorted(set(cr)&set(br));c=st.mean(cr[m]['rate_pct'] for m in common) if common else None
        b=st.mean(br[m]['rate_pct'] for m in common) if common else None
        result['equal_market'][y]=dict(markets=len(common),cluster_rate_pct=c,baseline_rate_pct=b,lift=c/b if b else None,
                                      basis='Same signal-outcome-valid markets for both equal-weight rates')
        successes=sorted(((m,x['positive']) for m,x in cr.items() if x['positive']),key=lambda x:(-x[1],x[0]))
        total=cluster['labels'][y]['positive']
        cluster['labels'][y]['success_concentration']=dict(by_market=successes,top_two_share_pct=100*sum(n for _,n in successes[:2])/total if total else None)
    result['verdict']=decide(result)
    return result

def analyze(path,policy,manifest):
    m,panel,btc=v.load_manifest_dataset(path);start,end=m['research_start'],m['research_end']
    research=v.old.Research(panel,[],start,end,btc);obs=[];signals=[]
    for market,s in panel.items():
        timeline=[]
        for t in range(m['collection_start'],end,300):
            hi,lo=s.high_low(t-1800,t);width=v.old.pct(hi,lo)
            row=dict(market=market,t=t,range=width)
            if t>=start and width is not None:
                row['labels']={y:rv.v3.label_at(s,t,h,p) for y,(h,p) in rv.LABELS.items()};obs.append(row)
            timeline.append(row)
        for r in rv.cluster_starts(timeline,4):
            if r['t']<start:continue
            t=r['t'];hi,lo=s.high_low(t-900,t)
            # Only the three frozen secondary features, not any other candidate.
            r['features']=dict(range_15m_pct=v.old.pct(hi,lo),range_30m_pct=r['range'],
                              alt_relative_60m_pct=research.snapshot(market,t)['values']['alt_relative_60m_pct'])
            signals.append(r)
    return dict(full=summarize(obs,signals,start,end),exclude_first6h=summarize(obs,signals,start+21600,end),
                signal_first_observations=signals,
                sensitivity_policy='Filter original cluster first timestamps >=Sep15 06:00. Never restart a cluster or promote a later observation at cutoff.')

def render(r):
    def f(x):return 'NULL' if x is None else f'{x:.3f}' if isinstance(x,float) else str(x)
    q=r['quality'];lines=['# V3 고정 4% 정책: 독립 기간 validation','',
        f"무결성: {q['passed']}; 상태 {q['states_count']}; 분봉 {q['total_candles']:,}; 중복 {q['duplicates']}; 오류 {q['errors']}",
        f"51시장 평균 본 기간 coverage: {q['research_mean_coverage_pct']:.3f}%",'',str(q['periods']),'']
    if 'analysis' not in r:return '\n'.join(lines+['수집/무결성 문제로 분석하지 않음.'])
    a=r['analysis'];d=r['discovery_reference'];dr=r['discovery_report_4pct']
    lines+=['## 결론: '+a['full']['verdict'],'',
            '첫 6시간 제외 판정: '+a['exclude_first6h']['verdict']+'. 판정은 사전에 동결한 수치 기준을 그대로 사용한다.',
            'REPLICATED에는 L1/L2 각각 성공 20건 이상이 필요하다. lift가 높아도 표본 기준에 못 미치면 완전 재현으로 판정하지 않는다.',
            '절대 성공률과 lift는 별개다. validation baseline이 낮아져 lift가 커져도 절대 성공률이 discovery보다 높아졌다는 뜻은 아니다.','']
    lines+=['## Discovery와 validation 비교','',
            '|지표|Discovery|Validation 전체|첫 6시간 제외|','|---|---|---|---|']
    rows=[('range 유효 observation',dr['feature_valid'],a['full']['valid_range_observations'],a['exclude_first6h']['valid_range_observations']),
          ('4% signal observation',dr['threshold']['observation']['observations'],a['full']['signal_observations'],a['exclude_first6h']['signal_observations']),
          ('signal cluster',d['clusters'],a['full']['cluster']['observations'],a['exclude_first6h']['cluster']['observations'])]
    for y in rv.LABELS:
        s=a['full']['cluster']['labels'][y];e=a['exclude_first6h']['cluster']['labels'][y]
        rows.extend([(y+' baseline %',dr['baseline'][y]['rate_pct'],a['full']['baseline'][y]['rate_pct'],a['exclude_first6h']['baseline'][y]['rate_pct']),
                     (y+' valid cluster',d[y]['valid'],s['valid'],e['valid']),(y+' success',d[y]['success'],s['positive'],e['positive']),
                     (y+' success %',d[y]['rate_pct'],s['rate_pct'],e['rate_pct']),
                     (y+' baseline lift',dr['threshold']['cluster']['labels'][y]['lift'],s['lift'],e['lift'])])
    for row in rows:lines.append('| '+' | '.join(f(x) for x in row)+' |')
    for name in ('full','exclude_first6h'):
        s=a[name];c=s['cluster']
        lines+=['',f"## {name}: {s['verdict']}",'',
                f"Signal 시장 {c['signal_markets']}; 최대 시장 {c['largest_market']} ({f(c['largest_market_share_pct'])}%); 시장별 신호 {s['market_signal_counts']}",'',
                '|label|baseline 성공/유효|cluster 성공/실패/UNKNOWN|성공 시장|FLOCK 제외 성공/유효|FLOCK 제외 % / lift|시장 동일가중 % / baseline % / lift|',
                '|---|---|---|---|---|---|---|']
        for y in rv.LABELS:
            b=s['baseline'][y];x=c['labels'][y];ex=x['without_flock'];eq=s['equal_market'][y]
            lines.append(f"|{y}|{b['positive']}/{b['valid']}|{x['positive']}/{x['valid']-x['positive']}/{x['excluded']}|{x['success_markets']}|{ex['positive']}/{ex['n']}|{f(ex['rate_pct'])} / {f(ex['lift'])}|{f(eq['cluster_rate_pct'])} / {f(eq['baseline_rate_pct'])} / {f(eq['lift'])}|")
        lines+=['','성공의 시장 집중도 (신호 발생 비중과 구분):','']
        for y in rv.LABELS:
            concentration=c['labels'][y]['success_concentration']
            lines.append(f"- {y}: 시장별 성공 {concentration['by_market']}; 상위 2시장 성공 비중 {f(concentration['top_two_share_pct'])}%. 시장 동일가중도 소수 관측 시장의 불안정한 성공률 영향을 받을 수 있다.")
        lines+=['','### 동결된 2차 후보 (조건 아님)','',
                '|label|feature|success N|failure N|success 중앙값|failure 중앙값|차이|rank effect|상태|','|---|---|---|---|---|---|---|---|---|']
        for y in rv.LABELS:
            for k,x in s['secondary'][y].items():
                lines.append('| '+' | '.join([y,k]+[f(x[z]) for z in ('success_valid_n','failure_valid_n','success_median','failure_median','difference','cliffs_delta','status')])+' |')
    lines+=['','## 동결 판정 기준','']+['- '+k+': '+val for k,val in r['policy']['verdict_rules'].items()]
    lines+=['','## 한계와 보존','',
            '- 본 기간은 discovery와 분리됐지만 discovery buffer 첫 6시간 노출이 있다. 제외 sensitivity에서도 기존 cluster를 재시작하지 않았다.',
            '- 동결일이 validation 시작일 이후이므로 완전한 전향 검증은 아니다. 이 기간에 대한 사후 threshold 탐색은 수행하지 않았다.',
            '- baseline은 전체 range-valid observation, signal은 cluster 최초 시점이다. 두 분모는 다르며 lift는 기술적 비교다. 완전 관측 필터는 활발한 거래 구간에 치우친다.',
            '- 시장 동일가중은 유효 cluster가 있는 동일 시장 집합에서 시장별 성공률과 baseline을 각각 평균한다. FLOCK 제외 baseline도 FLOCK을 제외하여 계산한다.',
            '- 각 시장의 state/requested 범위와 buffer 품질 및 label별 시장 성공 수는 JSON에 보존했다.',
            '- 두 DB 및 동결 정책/manifest 파일 해시: '+str(r['hashes'])]
    lines+=['','## 시장별 본 기간과 buffer 품질','',
            '|market|본 기간 candles|coverage %|최대 gap 분|앞 buffer candles|뒤 buffer candles|','|---|---|---|---|---|---|']
    for x in q['markets']:
        z=x['research'];lines.append(f"|{x['market']}|{z['observed_minutes']}|{f(z['coverage_pct'])}|{z['longest_gap_minutes']}|{x['before_buffer']['observed_minutes']}|{x['after_buffer']['observed_minutes']}|")
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',type=Path,default=rv.DATA_DIR/'research_market_validation_v1.db')
    p.add_argument('--output',type=Path,default=rv.REPORTS_DIR/'forward_surge_v3_independent_validation');args=p.parse_args()
    paths=dict(validation=args.db,discovery=rv.DATA_DIR/'research_market_v1.db',policy=Path('docs/forward_surge_v3_validation_policy.json'),manifest=Path('docs/research_market_validation_v1_manifest.json'))
    hashes={k:dict(before=v.digest(path)) for k,path in paths.items()}
    policy=json.loads(paths['policy'].read_text(encoding='utf-8'));expected=json.loads(paths['manifest'].read_text(encoding='utf-8'))
    result=dict(policy=policy,hashes=hashes,quality=audit(args.db,expected,policy))
    print('AUDIT',result['quality']['passed'],result['quality']['states_count'],result['quality']['total_candles'],result['quality']['errors'],flush=True)
    if result['quality']['passed']:
        result['analysis']=analyze(args.db,policy,expected);result['discovery_reference']=policy['discovery_reference']
        d=json.loads((rv.REPORTS_DIR/'forward_surge_v3_range_validation.json').read_text(encoding='utf-8'))['periods']['all']
        result['discovery_report_4pct']=dict(feature_valid=d['feature_valid'],baseline=d['baseline'],threshold=d['thresholds']['4'])
    for k,path in paths.items():
        hashes[k]['after']=v.digest(path);hashes[k]['unchanged']=hashes[k]['before']==hashes[k]['after']
        if not hashes[k]['unchanged']:raise RuntimeError(k+' changed')
    args.output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    args.output.with_suffix('.md').write_text(render(result),encoding='utf-8')
    if 'analysis' in result:print({k:result['analysis'][k]['verdict'] for k in ('full','exclude_first6h')})

if __name__=='__main__':main()
