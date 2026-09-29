"""Offline success/failure study of first range30 >=4% cluster observations."""
import argparse
from collections import Counter
import json
from pathlib import Path
import statistics as st
from . import forward_range_validation as rv

v3=rv.v3
KEYS=([f'return_{m}m_pct' for m in (5,15,30,60,120)]
      +[f'range_{m}m_pct' for m in (15,30,60)]
      +['drawdown_from_high_60m_pct','drawdown30_pct','position30',
         'trade_value_ratio','trade_value_acceleration','ma5_ma20_ratio',
         'ma20_slope_5m_pct','prior_high_breakout','alt_relative_60m_pct',
         'btc_relative_60m_pct','exploratory_value5_prior25_ratio','exploratory_value15_prior15_ratio'])

def features(research,market,t):
    base=v3.features(research,market,t)
    f={**base['values'],**base['flags']};s=research.panel[market]
    high,low=s.high_low(t-1800,t);price=s.price(t)
    f['drawdown30_pct']=v3.v2.old.pct(price,high)
    f['position30']=(price-low)/(high-low) if price is not None and high is not None and high>low else None
    a=s.values(t-300,t);b=s.values(t-1800,t-300)
    f['exploratory_value5_prior25_ratio']=a/(b/5) if a is not None and b is not None and b>0 else None
    a=s.values(t-900,t);b=s.values(t-1800,t-900)
    f['exploratory_value15_prior15_ratio']=a/b if a is not None and b is not None and b>0 else None
    return {k:f[k] for k in KEYS}

def starts(s,start,end):
    timeline=[]
    for t in range(start,end,300):
        hi,lo=s.high_low(t-1800,t)
        timeline.append(dict(t=t,range=v3.v2.old.pct(hi,lo)))
    return rv.cluster_starts(timeline,4)

def outcome(label):
    return label['value'] if label['complete'] else None

def counts(rows,kind,cutoff=None):
    values=[outcome(r['labels'][kind]) if cutoff is None or r['t']+rv.LABELS[kind][0]*60<=cutoff else None for r in rows]
    yes=sum(x is True for x in values);no=sum(x is False for x in values)
    return dict(signals=len(rows),success=yes,failure=no,unknown=len(rows)-yes-no,rate_pct=100*yes/(yes+no) if yes+no else None)

def compare(rows,kind,key,balanced=False,cutoff=None):
    groups={True:[],False:[]}
    for r in rows:
        y=outcome(r['labels'][kind]);x=r['features'][key]
        if cutoff is not None and r['t']+rv.LABELS[kind][0]*60>cutoff:continue
        if y is not None and x is not None:groups[y].append((r['market'],float(x)))
    result={};weighted={}
    for label,name in [(True,'success'),(False,'failure')]:
        data=groups[label];cs=Counter(m for m,x in data)
        xs=[(x,1/cs[m] if balanced else 1) for m,x in data];weighted[label]=xs
        result.update({name+'_valid_n':len(data),name+'_markets':len(cs),
                       name+'_median':v3.weighted_median(xs) if xs else None,
                       name+'_mean':sum(x*w for x,w in xs)/sum(w for x,w in xs) if xs else None})
    a,b=weighted[True],weighted[False]
    result['difference']=result['success_median']-result['failure_median'] if a and b else None
    # Rank effect, insensitive to units/outliers; not a trading score or cutoff search.
    result['cliffs_delta']=sum((int(x>y)-int(x<y))*wx*wy for x,wx in a for y,wy in b)/(sum(w for _,w in a)*sum(w for _,w in b)) if a and b else None
    result['status']='OK' if min(len(a),len(b))>=20 else 'INSUFFICIENT_SAMPLE'
    return result

def analyze(path):
    before=v3.v2.digest(path);manifest,panel,btc=v3.v2.load_manifest_dataset(path)
    start,end=manifest['research_start'],manifest['research_end'];mid=start+7*86400
    research=v3.v2.old.Research(panel,[],start,end,btc);rows=[]
    for market,s in panel.items():
        for signal in starts(s,manifest['collection_start'],end):
            t=signal['t']
            if t<start:continue
            rows.append(dict(market=market,t=t,t_utc=v3.v2.old.iso(t),features=features(research,market,t),
                             labels={k:v3.label_at(s,t,h,p) for k,(h,p) in rv.LABELS.items()}))
    top=Counter(r['market'] for r in rows).most_common(1)[0][0]
    subsets={'all':rows,'market_balanced':rows,'without_flock':[r for r in rows if r['market']!='KRW-FLOCK'],
             'without_top_market':[r for r in rows if r['market']!=top],
             'first7d':[r for r in rows if r['t']<mid],'last7d':[r for r in rows if r['t']>=mid]}
    groups={}
    for kind in rv.LABELS:
        views={}
        for name,rs in subsets.items():
            cutoff=mid if name=='first7d' else None
            views[name]=dict(counts=counts(rs,kind,cutoff),features={k:compare(rs,kind,k,name=='market_balanced',cutoff) for k in KEYS})
        groups[kind]=views
    classification={};common=[]
    for k in KEYS:
        all_stats=[groups[y]['all']['features'][k] for y in rv.LABELS]
        checks=[groups[y][view]['features'][k] for y in rv.LABELS for view in subsets]
        ds=[x['cliffs_delta'] for x in checks]
        direction=all(d is not None and d>0 for d in ds) or all(d is not None and d<0 for d in ds)
        supported=direction and all(x['status']=='OK' and min(x['success_markets'],x['failure_markets'])>=3 for x in checks)
        meaningful=all(x['cliffs_delta'] is not None and abs(x['cliffs_delta'])>=.147 for x in all_stats)
        category='반복적으로 의미 있는 차이 후보' if supported and meaningful else '약한 차이' if any(x['cliffs_delta'] is not None and abs(x['cliffs_delta'])>=.147 for x in all_stats) else '차이가 거의 없음'
        classification[k]=dict(category=category,all_sensitivity_directions_agree=direction,all_views_sufficient=all(x['status']=='OK' and min(x['success_markets'],x['failure_markets'])>=3 for x in checks),
                               common_direction=all_stats[0]['cliffs_delta']*all_stats[1]['cliffs_delta']>0 if all(x['cliffs_delta'] is not None for x in all_stats) else False)
        if supported and meaningful:common.append(k)
    # No derived numeric thresholds: only pre-existing natural neutral points.
    neutral={**{f'return_{m}m_pct':0 for m in (5,15,30,60,120)},'ma5_ma20_ratio':1,'ma20_slope_5m_pct':0,
             'alt_relative_60m_pct':0,'btc_relative_60m_pct':0,'trade_value_ratio':1,'trade_value_acceleration':1,
             'exploratory_value5_prior25_ratio':1,'exploratory_value15_prior15_ratio':1,'position30':.5}
    combinations={}
    for k in common:
        if k not in neutral:continue
        up=groups['L1']['all']['features'][k]['cliffs_delta']>0;boundary=neutral[k]
        chosen=[r for r in rows if r['features'][k] is not None and (r['features'][k]>boundary if up else r['features'][k]<boundary)]
        combinations[k]=dict(boundary=boundary,direction='>' if up else '<',signals=len(chosen),removed=len(rows)-len(chosen),
                            labels={y:counts(chosen,y) for y in rv.LABELS})
    if before!=v3.v2.digest(path):raise RuntimeError('Source DB changed')
    return dict(source=str(path),source_sha256=before,source_unchanged=True,manifest=manifest,cluster_count=len(rows),top_signal_market=top,
                market_counts=dict(Counter(r['market'] for r in rows).most_common()),groups=groups,classification=classification,
                common_candidates=common,
                tentative_directional_candidates=[k for k in KEYS if classification[k]['all_sensitivity_directions_agree'] and
                    all(groups[y]['all']['features'][k]['cliffs_delta'] is not None and abs(groups[y]['all']['features'][k]['cliffs_delta'])>=.147 for y in rv.LABELS)],
                combinations=combinations,observations=rows,
                verdict='YES' if common else 'WEAK' if any(v['category']=='약한 차이' for v in classification.values()) else 'NO',
                policies=['4% fixed; 5-minute grid; first cluster observation only. Warm-up pre-buffer; NULL range does not reset, observed <4% resets.',
                          'All incomplete future windows are UNKNOWN, including observed partial hits. First signal is never replaced.',
                          'Features use candle close <=t, no fill. Range=(high/low-1)*100; position=(close-low)/(high-low).',
                          'New exploratory trade-value ratios: last5/(preceding25/5), last15/preceding15; complete respective windows, zero denominator => NULL.',
                          'Market-balanced: equal total weight per market separately within each feature-valid success/failure group. Different class market composition remains a confounder.',
                          'First7d outcomes crossing split excluded; trailing buffer allowed. Time split is retrospective, not independent holdout.',
                          'Descriptive Cliff delta measures rank separation; abs<0.147 is classified near-zero, not a significance test. No p-value or trading cutoff search.',
                          'Repeated candidate requires same rank-effect sign in both labels/all six views, >=20 valid in each class and >=3 markets/class in every view. Median ties are reported, not invented as directional differences.',
                          'Absolute MA prices excluded from cross-market comparison. Labels and features overlap; cluster observations can still be temporally dependent.'])

def render(r):
    def f(x):return 'NULL' if x is None else f'{x:.4f}' if isinstance(x,float) else str(x)
    lines=['# 30분 range ≥4%: cluster 최초 시점의 성공·실패 비교','',f"판정: **{r['verdict']}**",'',
           f"총 cluster {r['cluster_count']}; 최대 signal 시장 {r['top_signal_market']}; 시장 분포 {r['market_counts']}",'',
           '|label|signal|success|failure|unknown|성공률 %|','|---|---|---|---|---|---|']
    for y in rv.LABELS:
        c=r['groups'][y]['all']['counts'];lines.append('|'+y+'|'+'|'.join(f(c[k]) for k in ('signals','success','failure','unknown','rate_pct'))+'|')
    lines+=['','## 해석 및 분류','',
            '성공률 분모는 success+failure이며 UNKNOWN은 제외한다. 1차 필터 이후의 추가 분리력을 조사한다.',
            '방향만 반복된 잠정 후보: '+str(r['tentative_directional_candidates']),
            '각 민감도 분석에서 성공·실패 각각 20건 이상을 요구했다. 방향이 유지돼도 이 표본 조건을 충족하지 못하면 약한 후보로 남긴다.',
            '기준을 모두 통과한 공통 후보: '+str(r['common_candidates']),
            '보조 조건 비교: '+(str(r['combinations']) if r['combinations'] else '엄격한 공통 후보가 없어 2단계 조건을 만들지 않았다.'),'',
            '|feature|분류|L1/L2 방향 일치|모든 sensitivity 방향 일치|','|---|---|---|---|']
    for k,c in r['classification'].items():lines.append(f"|{k}|{c['category']}|{c['common_direction']}|{c['all_sensitivity_directions_agree']}|")
    lines+=['','## 사람이 읽는 주요 비교','',
            '최근 15/30분 고저폭과 60분 상대강도는 서로 독립적인 후보가 아니다. 고저폭은 동일한 변동성 상태를, 상대강도는 60분 수익률을 일부 공유한다.',
            '5/15/30분 수익률, MA 관계, 거래대금 배율·가속의 분리력은 전반적으로 작거나 sensitivity에서 방향이 바뀐다. 거래대금 탐색 feature는 원래 feature와 구분하여 표에 표시했다.',
            'drawdown30은 음수 값이 더 작을수록 고점에서 더 많이 내려온 상태다. 성공군이 고점에 더 가까웠다는 해석은 하지 않는다. position30 자체의 차이는 작다.',
            '최대 signal 시장이 FLOCK이므로 FLOCK 제외와 최대 시장 제외는 동일한 분석이며 두 독립 검증으로 세지 않는다.','',
            '|feature|label|success 중앙값|failure 중앙값|success/failure N|','|---|---|---|---|---|']
    for k in ('range_15m_pct','range_30m_pct','alt_relative_60m_pct','drawdown30_pct','position30'):
        for y in rv.LABELS:
            s=r['groups'][y]['all']['features'][k]
            lines.append(f"|{k}|{y}|{f(s['success_median'])}|{f(s['failure_median'])}|{s['success_valid_n']}/{s['failure_valid_n']}|")
    lines+=['','### 시간 분리의 유효 표본','']
    for y in rv.LABELS:
        for view in ('first7d','last7d'):
            lines.append(f"- {y} {view}: {r['groups'][y][view]['counts']}")
    lines+=['','## 계산·해석 정책','']+['- '+p for p in r['policies']]
    for y,views in r['groups'].items():
        for name,view in views.items():
            lines+=['',f'## {y} / {name}','',str(view['counts']),'',
                    '|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|',
                    '|---|---|---|---|---|---|---|---|---|---|']
            for k,s in view['features'].items():
                fields=('success_valid_n','failure_valid_n','success_median','failure_median','difference','success_mean','failure_mean','cliffs_delta','status')
                lines.append('|'+k+'|'+'|'.join(f(s[key]) for key in fields)+'|')
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',type=Path,default=rv.DATA_DIR/'research_market_v1.db')
    p.add_argument('--output',type=Path,default=rv.REPORTS_DIR/'forward_surge_v3_success_failure');a=p.parse_args()
    r=analyze(a.db);a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.with_suffix('.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    a.output.with_suffix('.md').write_text(render(r),encoding='utf-8')
    print(r['verdict'],r['common_candidates']);print({k:r['groups'][k]['all']['counts'] for k in rv.LABELS})

if __name__=='__main__':main()
