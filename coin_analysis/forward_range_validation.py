"""Fixed range-threshold validation using existing DB only; no threshold search."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics as st

from . import forward_surge_research_v3 as v3
from .paths import DATA_DIR, REPORTS_DIR

THRESHOLDS=(1,2,3,4,5,6,8,10)
LABELS={'L1':(30,5),'L2':(60,10)}


def cluster_starts(rows,threshold):
    active=False;starts=[]
    for r in rows:
        value=r['range']
        # Unknown range cannot prove a reset. Only observed below-threshold resets.
        if value is None:continue
        if value<threshold:active=False
        elif not active:
            starts.append(r);active=True
    return starts


def rates(rows,cutoff=None):
    result={}
    for kind,(minutes,_) in LABELS.items():
        eligible=[r for r in rows if r['labels'][kind]['complete'] and r['labels'][kind]['value'] is not None
                  and (cutoff is None or r['t']+minutes*60<=cutoff)]
        pos=sum(r['labels'][kind]['value'] for r in eligible)
        by=defaultdict(lambda:[0,0])
        for r in eligible:
            by[r['market']][0]+=1;by[r['market']][1]+=r['labels'][kind]['value']
        ex=[r for r in eligible if r['market']!='KRW-FLOCK']
        result[kind]=dict(valid=len(eligible),excluded=len(rows)-len(eligible),positive=pos,
            rate_pct=100*pos/len(eligible) if eligible else None,
            status='SUFFICIENT_FOR_DESCRIPTION' if len(eligible)>=20 else 'INSUFFICIENT_SAMPLE',
            signal_markets=len(by),success_markets=sum(p>0 for n,p in by.values()),
            market_median_rate_pct=st.median(100*p/n for n,p in by.values()) if by else None,
            by_market={m:dict(n=n,positive=p,rate_pct=100*p/n) for m,(n,p) in sorted(by.items())},
            without_flock=dict(n=len(ex),positive=sum(r['labels'][kind]['value'] for r in ex),rate_pct=100*sum(r['labels'][kind]['value'] for r in ex)/len(ex) if ex else None))
    return result


def describe(rows,baseline,cutoff=None):
    counts=Counter(r['market'] for r in rows);summary=rates(rows,cutoff)
    for kind,s in summary.items():
        b=baseline[kind]['rate_pct']
        s['lift']=s['rate_pct']/b if b and s['rate_pct'] is not None else None
        eb=baseline[kind]['without_flock']['rate_pct'];er=s['without_flock']['rate_pct']
        s['without_flock']['lift']=er/eb if eb and er is not None else None
    return dict(observations=len(rows),signal_markets=len(counts),largest_market=counts.most_common(1)[0][0] if counts else None,
                largest_market_share_pct=100*max(counts.values())/len(rows) if rows else None,labels=summary)


def direction_groups(rows):
    groups={}
    for minutes in (5,15):
        key=f'return_{minutes}m_pct'
        groups[key+'_positive']=[r for r in rows if r[key] is not None and r[key]>0]
        groups[key+'_nonpositive']=[r for r in rows if r[key] is not None and r[key]<=0]
        groups[key+'_missing']=[r for r in rows if r[key] is None]
    # Explicit descriptive bands; never used to select or optimize a trading rule.
    for name,lo,hi in [('0_to_1pct',-1,0),('1_to_3pct',-3,-1),('3_to_5pct',-5,-3),('more_than_5pct',-float('inf'),-5)]:
        groups['drawdown_'+name]=[r for r in rows if r['drawdown30'] is not None and lo<=r['drawdown30']<hi]
    groups['drawdown_at_high']=[r for r in rows if r['drawdown30']==0]
    groups['trade_value_ratio_observed']=[r for r in rows if r['trade_value_ratio'] is not None]
    for value in (1,2):groups[f'trade_value_ratio_ge{value}']=[r for r in rows if r['trade_value_ratio'] is not None and r['trade_value_ratio']>=value]
    return groups


def run(path,output):
    before=v3.v2.digest(path)
    manifest,panel,btc=v3.v2.load_manifest_dataset(path)
    start,end=manifest['research_start'],manifest['research_end'];mid=start+7*86400
    all_rows=[];starts={x:[] for x in THRESHOLDS}
    for market,s in panel.items():
        timeline=[]
        for t in range(manifest['collection_start'],end,300):
            high,low=s.high_low(t-1800,t);width=v3.v2.old.pct(high,low)
            row=dict(market=market,t=t,range=width)
            if start<=t:
                fs=v3.v2.old.feature_snapshot(s,t)['values']
                row.update(return_5m_pct=fs['return_5m_pct'],return_15m_pct=fs['return_15m_pct'],
                           trade_value_ratio=fs['trade_value_ratio'],drawdown30=v3.v2.old.pct(s.price(t),high),
                           labels={k:v3.label_at(s,t,h,p) for k,(h,p) in LABELS.items()})
                if width is not None:all_rows.append(row)
            timeline.append(row)
        for x in THRESHOLDS:starts[x].extend(r for r in cluster_starts(timeline,x) if start<=r['t']<end)
    result=dict(source=str(path),source_sha256=before,total_grid_observations=len(panel)*((end-start)//300),feature_valid_observations=len(all_rows),
                thresholds=list(THRESHOLDS),start_utc=v3.v2.old.iso(start),split_utc=v3.v2.old.iso(mid),end_utc=v3.v2.old.iso(end),periods={})
    for name,a,b in [('all',start,end),('discovery',start,mid),('validation',mid,end)]:
        cutoff=mid if name=='discovery' else None
        rows=[r for r in all_rows if a<=r['t']<b];baseline=rates(rows,cutoff)
        period=dict(feature_valid=len(rows),baseline=baseline,thresholds={})
        for x in THRESHOLDS:
            selected=[r for r in rows if r['range']>=x]
            cs=[r for r in starts[x] if a<=r['t']<b]
            period['thresholds'][str(x)]=dict(observation=describe(selected,baseline,cutoff),cluster=describe(cs,baseline,cutoff),
                feature_valid_share_pct=100*len(selected)/len(rows) if rows else None,
                all_grid_share_pct=100*len(selected)/(len(panel)*(b-a)//300),
                daily_clusters=len(cs)/((b-a)/86400),
                subgroups={k:describe(rs,baseline,cutoff) for k,rs in direction_groups(selected).items()})
        result['periods'][name]=period
    result['cluster_first_observations']={str(x):starts[x] for x in THRESHOLDS}
    result['policies']=dict(denominator='Range30 requires all 30 observed closed candles. Each label rate requires complete future H on BOTH hits and nonhits. Incomplete labels excluded separately, never counted as failure. L1/L2 denominators differ.',
        baseline='Same feature-valid population and future-completeness filter for each label and time period; no matched-control sampling or past360 matching filter.',
        clusters='Per market and fixed threshold: first observed >=threshold; reset ONLY after observed range<threshold. NULL does not reset. Warm up state on pre-buffer, no period-split reset. Assign cluster to first time, not retrospectively first valid outcome.',
        split='Discovery KST Sep1-8 (exclusive); validation Sep8-15 (exclusive). Discovery outcomes crossing split are purged. Validation outcomes may use existing post-buffer. Thresholds never chosen using discovery results.',
        drawdown='(current close / observed last30m high -1)*100, explicit requested price position using existing OHLC. Descriptive fixed bands 0,1,3,5%; no best band selected.',
        caveats='Complete-window population favors liquid periods. Unknown range may conservatively join separate bursts. Baseline observation lift is not a cluster-matched causal comparison. Overlapping outcome windows and market concentration remain. High-only targets do not establish trade profit or downside safety.')
    if v3.v2.digest(path)!=before:raise RuntimeError('Source changed')
    result['source_unchanged']=True
    result['assessment']=dict(verdict='PROMISING', reasons=[
        '고정 8개 기준의 observation lift는 앞/뒤 7일 모두 1보다 높다. 그러나 1% 기준은 cluster 최초 시점의 성공률이 baseline보다 낮아 반복 observation 효과가 크다.',
        '예시 4% 기준: L1/L2 observation 발생률 14.39%/7.20%, cluster 최초 시점 10.14%/7.56%. FLOCK 제외 cluster도 7.40%/5.93%로 차이가 남는다. 이 예시는 최적 threshold 추천이 아니다.',
        '4% 기준 신호는 44개 시장, 성공 cluster는 L1 11개/L2 8개 시장에서 발생한다. 시장별 cluster 성공률 중앙값은 둘 다 0%로 보편적인 패턴이라고 단정할 수 없다.',
        '높은 threshold에서 lift가 커지지만 발생 시장은 줄고 FLOCK 비중이 커진다. 10% 기준 cluster는 14개 시장에 분포하며 FLOCK 비중은 33.7%다.',
        '최근 5분 상승/비상승 구분은 뚜렷한 추가 차이가 없다. 15분 상승 구간의 L1 우위는 보이지만 L2에 일관되게 이어지지 않는다. 거래대금 결합과 drawdown 구간은 탐색적 비교만 유지한다.',
        'range 후보 자체가 전체 14일의 V3 결과에서 발견되었으므로 이번 시간 분리는 독립 holdout 검증이 아닌 사후 시간 안정성 검사다. 새로운 기간에서의 검증이 필요하다.',
        '완전 관측 구간만의 조건부 발생률이며 전체 저유동성 시점으로 일반화할 수 없다. 고가 목표 도달은 실제 체결 수익률이나 손실 위험을 뜻하지 않는다.'
    ])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    output.with_suffix('.md').write_text(render(result),encoding='utf-8')
    print('FEATURE VALID',len(all_rows))
    for name,p in result['periods'].items():
        print(name,'BASELINE',{k:(s['valid'],s['positive'],s['rate_pct']) for k,s in p['baseline'].items()})
        for x,row in p['thresholds'].items():
            print(x,'obs',row['observation']['observations'],'clusters',row['cluster']['observations'],
                  {k:(s['valid'],s['positive'],round(s['rate_pct'],2) if s['rate_pct'] is not None else None,round(s['lift'],2) if s['lift'] is not None else None) for k,s in row['observation']['labels'].items()},
                  'cluster rates',{k:(s['valid'],s['positive'],s['rate_pct']) for k,s in row['cluster']['labels'].items()})
    return result


def fmt(x):return 'NULL' if x is None else f'{x:.3f}' if isinstance(x,float) else str(x)


def render(r):
    lines=['# V3 최근 30분 고저폭: 고정 threshold 검증','',f"전체 grid {r['total_grid_observations']:,}, range 계산 가능 {r['feature_valid_observations']:,}.",'']
    lines+=['## 판정: '+r['assessment']['verdict'],'']
    lines.extend('- '+reason for reason in r['assessment']['reasons'])
    lines+=['','연구 기간: 2026-09-01 00:00 ~ 09-15 00:00 KST (종료 제외). 앞 7일과 뒤 7일을 구분한다.','',
            '관측 단위 baseline: L1 735/22,819 = 3.221%, L2 310/19,519 = 1.588%. range 계산 가능 30,305건 중 미래 완전 관측 여부에 따라 각 분모가 달라진다.',
            '각 cluster의 최초 시점이 미래 불완전이면 제외하며 이후 시점으로 대체하지 않는다. NULL range는 cluster를 종료하지 않는다.','']
    for k,v in r['policies'].items():lines.append(f'- {k}: {v}')
    lines+=['','## 전체 grid 대비 신호 비중 및 성공 시장 수','',
            '|range ≥ %|전체 grid 대비 %|observation 성공 시장 L1/L2|cluster 성공 시장 L1/L2|','|---|---|---|---|']
    for x,s in r['periods']['all']['thresholds'].items():
        o=s['observation']['labels'];c=s['cluster']['labels']
        lines.append(f"|{x}|{fmt(s['all_grid_share_pct'])}|{o['L1']['success_markets']}/{o['L2']['success_markets']}|{c['L1']['success_markets']}/{c['L2']['success_markets']}|")
    for name,p in r['periods'].items():
        lines+=['',f'## {name}','',f"Baseline: "+str({k:dict(valid=s['valid'],positive=s['positive'],rate_pct=s['rate_pct']) for k,s in p['baseline'].items()}),'',
            '|range≥%|신호 observation|valid feature 대비 %|L1 성공/유효|L1 %|lift|L2 성공/유효|L2 %|lift|cluster/일|',
            '|---|---|---|---|---|---|---|---|---|---|']
        for x,s in p['thresholds'].items():
            a=s['observation']['labels']['L1'];b=s['observation']['labels']['L2']
            lines.append('| '+' | '.join(map(fmt,[x,s['observation']['observations'],s['feature_valid_share_pct'],f"{a['positive']}/{a['valid']}",a['rate_pct'],a['lift'],f"{b['positive']}/{b['valid']}",b['rate_pct'],b['lift'],s['daily_clusters']]))+' |')
        lines+=['','### Cluster 첫 신호와 시장 분포','',
                '|threshold|cluster|발생 시장|최대 시장/비중%|L1 성공/유효 (%)|L2 성공/유효 (%)|L1 시장 중앙 성공률|L2 시장 중앙 성공률|FLOCK 제외 L1/L2 %|',
                '|---|---|---|---|---|---|---|---|---|']
        for x,s in p['thresholds'].items():
            c=s['cluster'];a=c['labels']['L1'];b=c['labels']['L2']
            lines.append('| '+' | '.join(map(fmt,[x,c['observations'],c['signal_markets'],f"{c['largest_market']} / {fmt(c['largest_market_share_pct'])}",f"{a['positive']}/{a['valid']} ({fmt(a['rate_pct'])})",f"{b['positive']}/{b['valid']} ({fmt(b['rate_pct'])})",a['market_median_rate_pct'],b['market_median_rate_pct'],f"{fmt(a['without_flock']['rate_pct'])}/{fmt(b['without_flock']['rate_pct'])}"]))+' |')
        lines+=['','### 방향 및 거래대금: 사전 고정 구간의 단순 비교','',
                '|range≥%|구분|관측 수|L1 유효/성공률%/상태|L2 유효/성공률%/상태|','|---|---|---|---|---|']
        for x,s in p['thresholds'].items():
            for group,g in s['subgroups'].items():
                a=g['labels']['L1'];b=g['labels']['L2']
                lines.append(f"|{x}|{group}|{g['observations']}|{a['valid']} / {fmt(a['rate_pct'])} / {a['status']}|{b['valid']} / {fmt(b['rate_pct'])} / {b['status']}|")
    lines+=['','시장별 분모·성공 수·중앙 성공률, observation/cluster별 FLOCK 제외 결과와 성공 시장 수는 동명 JSON에 모두 보존했다.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DATA_DIR/'research_market_v1.db')
    p.add_argument('--output',type=Path,default=REPORTS_DIR/'forward_surge_v3_range_validation')
    a=p.parse_args();run(a.db,a.output)


if __name__=='__main__':main()
