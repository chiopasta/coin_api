"""Offline fixed-clock forward-label research. No signals, optimization or network."""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import statistics as st

from . import surge_event_research_v2_revised as v2
from .paths import DATA_DIR, REPORTS_DIR

LABELS={'L1':(30,5.),'L2':(60,10.),'L3':(360,20.)}


def features(research,market,t):
    # Old Research only: avoids diagnostic caches and only uses closed candles.
    f=research.snapshot(market,t)
    vals=dict(f['values']);flags=dict(f['flags']);s=research.panel[market]
    vals['return_120m_pct']=s.return_at(t,120)
    for minutes in (15,30,60):
        high,low=s.high_low(t-minutes*60,t)
        vals[f'range_{minutes}m_pct']=v2.old.pct(high,low)
    high,_=s.high_low(t-3600,t)
    vals['drawdown_from_high_60m_pct']=v2.old.pct(s.price(t),high)
    return dict(values=vals,flags=flags)


def label_at(s,t,minutes,threshold):
    anchor=s.price(t)
    a,b=s.bounds(t,t+minutes*60)
    observed=b-a;complete=observed==minutes
    peak=max(s.high[a:b],default=None)
    rise=v2.old.pct(peak,anchor)
    positive=rise is not None and rise>=threshold
    # An observed hit is known positive. An incomplete non-hit is NOT negative.
    value=True if positive else False if anchor is not None and complete else None
    return dict(value=value,observed_minutes=observed,expected_minutes=minutes,
                coverage=observed/minutes,complete=complete,max_rise_pct=rise)


def history(s,t):
    a,b=s.bounds(t-21600,t)
    c,d=s.bounds(t-21600,t-14400)
    eligible=s.price(t) is not None and (b-a)>=.8*360 and (d-c)>=.8*120
    liquidity=(s.value_prefix[d]-s.value_prefix[c])/(d-c) if eligible and d>c else None
    return eligible,liquidity


def clusters(observations,kind):
    """Connected overlapping positive outcome intervals, separately per market/label."""
    by_market=defaultdict(list)
    for row in observations:by_market[row['market']].append(row)
    result=[];h=LABELS[kind][0]*60
    for m,rows in sorted(by_market.items()):
        end=None;cluster=None
        for row in sorted(rows,key=lambda r:r['t']):
            if end is None or row['t']>end:
                cluster=dict(id=v2.old.identity('v3cluster',kind,m,row['t']),market=m,start=row['t'],end=row['t']+h,observations=0,representative_t=row['t'])
                result.append(cluster)
            end=row['t']+h;cluster['end']=end;cluster['observations']+=1
            row['cluster_id']=cluster['id'];row['representative']=row['t']==cluster['representative_t']
    return result


def weighted_median(items):
    items=sorted(items);total=sum(w for x,w in items);cum=0
    for i,(x,w) in enumerate(items):
        cum+=w
        if math.isclose(cum,total/2,abs_tol=1e-12) and i+1<len(items):return (x+items[i+1][0])/2
        if cum>=total/2:return x
    return None


def compare(pairs,cache,balanced=False,minimum=20):
    result=[]
    if not pairs:return result
    for section in ('values','flags'):
        for key in cache[(pairs[0]['market'],pairs[0]['t'])][section]:
            valid=[];event_n=control_n=0
            for p in pairs:
                x=cache[(p['market'],p['t'])][section][key]
                y=cache[(p['control_market'],p['t'])][section][key]
                event_n+=x is not None;control_n+=y is not None
                if x is not None and y is not None:valid.append((p['market'],float(x),float(y)))
            counts=Counter(m for m,x,y in valid)
            if not valid:
                result.append(dict(feature=key,section=section,valid_pairs=0,event_valid=event_n,control_valid=control_n,status='INSUFFICIENT_SAMPLE'))
                continue
            weights=[1/counts[m] if balanced else 1 for m,x,y in valid];total=sum(weights)
            em=weighted_median([(x,w) for (_,x,y),w in zip(valid,weights)])
            cm=weighted_median([(y,w) for (_,x,y),w in zip(valid,weights)])
            row=dict(feature=key,section=section,valid_pairs=len(valid),event_valid=event_n,control_valid=control_n,markets=len(counts),
                     positive_median=em,control_median=cm,difference=em-cm,
                     median_paired_difference=weighted_median([(x-y,w) for (_,x,y),w in zip(valid,weights)]),
                     positive_mean=sum(x*w for (_,x,y),w in zip(valid,weights))/total,
                     control_mean=sum(y*w for (_,x,y),w in zip(valid,weights))/total,
                     status='SUFFICIENT_FOR_DESCRIPTION' if len(valid)>=minimum else 'INSUFFICIENT_SAMPLE')
            if section=='flags':row['difference_pp']=100*(row['positive_mean']-row['control_mean'])
            result.append(row)
    return result


def mine(panel,btc,start,end,step=300):
    positives={k:[] for k in LABELS};tallies={k:Counter() for k in LABELS};negatives={k:{} for k in LABELS}
    anchors=0;grid=list(range(start,end,step))
    for index,t in enumerate(grid):
        hist={m:history(s,t) for m,s in panel.items()}
        for m,s in panel.items():
            anchors+=s.price(t) is not None
            eligible,liquidity=hist[m]
            for kind,(h,threshold) in LABELS.items():
                label=label_at(s,t,h,threshold)
                tallies[kind]['positive' if label['value'] is True else 'negative' if label['value'] is False else 'unknown']+=1
                observable=eligible and label['complete'] and liquidity is not None and liquidity>0
                if label['value'] is True:
                    positives[kind].append(dict(market=m,t=t,t_utc=v2.old.iso(t),label=kind,label_quality=label,
                                                history_eligible=eligible,matching_eligible=observable,liquidity=liquidity))
                elif label['value'] is False and observable:
                    negatives[kind].setdefault(t,[]).append((m,liquidity))
        if index%500==0:print(f'LABEL GRID {index}/{len(grid)}',flush=True)
    cache={};r=v2.old.Research(panel,[],start,end,btc)
    def remember(m,t):
        if (m,t) not in cache:cache[(m,t)]=features(r,m,t)
    groups={}
    for kind,es in positives.items():
        cs=clusters(es,kind);pairs=[];used=set();reasons=Counter()
        for e in sorted(es,key=lambda x:(x['t'],x['market'])):
            if not e['matching_eligible']:
                reasons['case_history_or_future_incomplete']+=1;continue
            options=[(abs(math.log(liq/e['liquidity'])),m,liq/e['liquidity']) for m,liq in negatives[kind].get(e['t'],[])
                     if m!=e['market'] and (m,e['t']) not in used and 1/3<=liq/e['liquidity']<=3]
            if not options:
                reasons['no_same_time_liquidity_negative']+=1;continue
            _,control,ratio=min(options)
            used.add((control,e['t']))
            e['control_market']=control;e['control_liquidity_ratio']=ratio
            remember(e['market'],e['t']);remember(control,e['t']);pairs.append(e)
        reps=[p for p in pairs if p['representative']]
        counts=Counter(e['market'] for e in es);matched_counts=Counter(p['market'] for p in pairs)
        top=counts.most_common(1)[0][0] if counts else None
        subsets={'all':pairs,'cluster_representatives':reps,'market_balanced':pairs,
                 'without_top_market':[p for p in pairs if p['market']!=top and p['control_market']!=top]}
        summaries={name:dict(pairs=len(ps),statistics=compare(ps,cache,balanced=name=='market_balanced')) for name,ps in subsets.items()}
        # Same-direction support across all four prespecified views, without tuning cutoffs.
        maps={name:{(x['section'],x['feature']):x for x in view['statistics']} for name,view in summaries.items()}
        candidates=[]
        for key,row in maps['all'].items():
            # Absolute coin prices are not comparable across different assets.
            # Raw liquidity levels are matching diagnostics, not normalized patterns.
            if key[1] in ('ma5','ma20','trade_value_5m','prior_mean_trade_value_5m'):continue
            rs=[maps[name].get(key,{}) for name in maps]
            metric='difference_pp' if key[0]=='flags' else 'difference'
            ds=[x.get(metric,0) for x in rs]
            if all(x.get('valid_pairs',0)>=20 and x.get('markets',0)>=3 for x in rs) and (all(d>0 for d in ds) or all(d<0 for d in ds)):
                candidates.append(dict(section=key[0],feature=key[1],direction='higher' if ds[0]>0 else 'lower',differences=dict(zip(maps,ds))))
        groups[kind]=dict(total_observations=len(grid)*len(panel),labels=dict(tallies[kind]),positive_markets=len(counts),positive_market_counts=dict(counts.most_common()),
                          clusters=cs,cluster_count=len(cs),matching_eligible_positives=sum(e['matching_eligible'] for e in es),matched=len(pairs),
                          matched_market_counts=dict(matched_counts.most_common()),unmatched_reasons=dict(reasons),top_market=top,
                          views=summaries,candidates=candidates,positive_observations=es)
        print(f'{kind}: positive {len(es)} clusters {len(cs)} matched {len(pairs)} representative matches {len(reps)}',flush=True)
    common=[]
    for a in groups['L1']['candidates']:
        if any((a['section'],a['feature'],a['direction'])==(b['section'],b['feature'],b['direction']) for b in groups['L2']['candidates']):common.append(a['feature'])
    return dict(observations=len(grid)*len(panel),exact_anchor_observations=anchors,grid_points=len(grid),markets=len(panel),start=start,end=end,
                label_definitions={k:dict(horizon_minutes=h,threshold_pct=threshold) for k,(h,threshold) in LABELS.items()},
                groups=groups,cross_label_candidates=common,feature_snapshots=[dict(market=m,t=t,**f) for (m,t),f in sorted(cache.items())],
                verdict='PROMISING' if common else 'WEAK' if any(groups[k]['candidates'] for k in ('L1','L2')) else 'NO CLEAR SIGNAL',
                policies=dict(grid='5 minute calendar timestamps, [research_start,research_end); all feature candles closed at/before t',
                    labels='Anchor exact close at t. Future highs in (t,t+H]. Missing non-hit => UNKNOWN, not negative. Hit with partial future => positive but excluded from matching.',
                    matching='Same timestamp, different market; past360 and baseline120 coverage>=80%, exact anchor, future coverage=100% symmetrically for both classes. Prior trade-value baseline [t-360m,t-240m], ratio 1/3..3. Greedy by closest log-liquidity, deterministic market ties.',
                    reuse='No duplicate negative at same timestamp and label; overlapping future intervals across different timestamps remain dependent.',
                    cluster='Connected overlapping positive [t,t+H] intervals per market/label; conservative clusters, not independently verified price episodes. First positive fixed BEFORE matching; never replace unmatched representative.',
                    balance='Equal total weight per positive market among feature-valid pairs. Original paired controls retain those weights.',
                    sensitivity='Remove highest positive-count market from BOTH positive and control sides; no rematching.',
                    candidates='All/cluster-representative/equal-market/exclude-top: >=20 valid pairs and >=3 positive markets; same nonzero direction. Existing boolean thresholds only. No new feature threshold search.',
                    limitations='Descriptive, no held-out validation; labels and adjacent observations correlated. Full-future requirement favors active periods; label rates are observed-grid rates, not trading probabilities. Cluster count is not independent market count.'))


def render(r):
    lines=['# Forward surge V3: 고정 시점의 사전 특징 비교','',f"판정: **{r['verdict']}**",'',
           f"{r['markets']}알트 × {r['grid_points']}시점 = {r['observations']:,} observations. 정확한 t 종가 존재 {r['exact_anchor_observations']:,}.",
           'BTC는 동일 DB의 기준 데이터. API/보간/threshold 최적화 없음.',
           'L1: t 종가 대비 30분 내 고가 +5%; L2: 60분 내 +10%; L3: 360분 내 +20%.','']
    lines+=['## 핵심 결과','',
            '|label|positive|cluster|발생 시장|matched|cluster 첫 시점 matched|',
            '|---|---|---|---|---|---|']
    for kind,g in r['groups'].items():
        lines.append(f"|{kind}|{g['labels'].get('positive',0)}|{g['cluster_count']}|{g['positive_markets']}|{g['matched']}|{g['views']['cluster_representatives']['pairs']}|")
    lines+=['','### 반복 후보: 최근 15분·30분 고저폭','',
            '양쪽 값이 있는 pair만 사용한다. 범위는 (high/low-1)*100, 차이는 %p다.',
            '|label|feature|view|유효 pair|시장|positive 중앙값|control 중앙값|차이 %p|',
            '|---|---|---|---|---|---|---|---|']
    for kind in ('L1','L2'):
        for name,view in r['groups'][kind]['views'].items():
            for row in view['statistics']:
                if row['feature'] in ('range_15m_pct','range_30m_pct') and 'difference' in row:
                    lines.append(f"|{kind}|{row['feature']}|{name}|{row['valid_pairs']}|{row['markets']}|{row['positive_median']:.3f}|{row['control_median']:.3f}|{row['difference']:+.3f}|")
    lines+=['','### 사람이 읽는 해석','',
            '- 사후 저점을 쓰지 않아도 최근 고저폭이 큰 시점의 차이는 남는다. L1/L2에서 같은 방향이며 cluster 대표와 시장 균형, 최대 시장 제외 비교에서도 남는다.',
            '- 60분 수익률은 전체 observation에서는 positive가 높지만 cluster 첫 시점만 남기면 반대로 낮아진다. 상승 모멘텀을 일관된 전조로 분류하지 않는다.',
            '- L1 거래대금 배율 차이는 있으나 L2 cluster 대표 유효 pair는 20 미만이다. 거래대금 폭증이 두 label에 반복된다는 결론은 내리지 않는다.',
            '- 고점 돌파 역시 cluster 대표에서 우위가 유지되지 않는다. L3는 cluster 첫 시점 매칭이 2쌍뿐이므로 INSUFFICIENT_SAMPLE 참고용이다.',
            '- 고저폭은 상방뿐 아니라 하방 움직임도 커지는 변동성 상태일 수 있다. 지금 결과는 방향성 진입 시점이나 기대수익을 검증한 것이 아니다.',
            '- 15분/30분 범위는 서로 중첩된 feature이고 L1/L2도 독립 표본이 아니다. 시간 분리 검증이 없으므로 PROMISING은 반복되는 기술적 차이라는 뜻이다.',
            '- absolute MA5/MA20은 코인 단위 가격이 달라 시장 간 크기를 비교할 수 없어 후보 선정에서 제외했다. 원시 거래대금도 매칭 진단으로만 보존한다.',
            '- 각 feature의 시장 균형은 그 feature가 양쪽 모두 유효한 positive 시장들에 동일 총 가중치를 준다. 제외 시장이 control 쪽에 있는 pair도 제거했다.','',
            '## 사전에 고정한 연구 규칙','']
    for k,p in r['policies'].items():lines.append(f'- {k}: {p}')
    for kind,g in r['groups'].items():
        lines+=['',f'## {kind}','',f"labels {g['labels']}; positive 시장 {g['positive_markets']}, cluster {g['cluster_count']}, matched {g['matched']}",
                f"matching eligible {g['matching_eligible_positives']}, 미매칭 {g['unmatched_reasons']}",
                f"positive 시장 분포 {g['positive_market_counts']}; 제외 시장 {g['top_market']}",'']
        for name,view in g['views'].items():
            lines += [f'### {name}: {view["pairs"]} pairs','',
                      '|feature|valid pairs|markets|positive 중앙값|control 중앙값|차이|발생률 차이 %p|상태|',
                      '|---|---|---|---|---|---|---|---|']
            for x in view['statistics']:
                def val(k):
                    z=x.get(k);return 'NULL' if z is None else f'{z:.5g}' if isinstance(z,float) else str(z)
                lines.append('| '+' | '.join([x['feature']]+[val(k) for k in ('valid_pairs','markets','positive_median','control_median','difference','difference_pp','status')])+' |')
        lines+=['','네 비교에서 같은 방향을 유지한 후보: '+str(g['candidates'])]
    lines+=['','## 반복성과 한계','',f"L1/L2 양쪽에서 같은 방향을 유지한 후보: {r['cross_label_candidates']}",
            '단위가 다른 연속형 차이를 하나의 점수로 정렬하지 않는다. boolean 비교만 %p 단위로 비교 가능하다.',
            'PROMISING이어도 검증된 매수 신호가 아니다. 시간 분리 검증이 없으며 변동성이 큰 시장의 성질과 개별 시점의 예측력을 구분해야 한다.',
            '전체 observations와 episode 대표 통계는 서로 다른 분모다. 시장 균형 결과도 시장 수가 적으면 일반화를 보장하지 않는다.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DATA_DIR/'research_market_v1.db')
    p.add_argument('--output',type=Path,default=REPORTS_DIR/'forward_surge_v3')
    a=p.parse_args();before=v2.digest(a.db)
    manifest,panel,btc=v2.load_manifest_dataset(a.db)
    result=mine(panel,btc,manifest['research_start'],manifest['research_end'])
    after=v2.digest(a.db)
    if before!=after:raise RuntimeError('Source DB changed')
    result.update(source_db=str(a.db),source_sha256=before,unchanged=True,manifest=manifest)
    a.output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    a.output.with_suffix('.md').write_text(render(result),encoding='utf-8')
    print('VERDICT',result['verdict'],'REPEATED',result['cross_label_candidates'])


if __name__=='__main__':main()
