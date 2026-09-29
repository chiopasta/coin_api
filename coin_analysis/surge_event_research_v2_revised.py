"""V2 revised research policies. Local SQLite only; no API/download capability."""

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict, deque
from contextlib import closing
import json
import math
from pathlib import Path

from . import surge_event_research_v2 as old
from .surge_event_audit_v2 import digest, kst, table, null_reason
from .paths import DATA_DIR, REPORTS_DIR


def quality(s, start, end):
    """Expected close-time grid (start,end]; absent observations remain unknown."""
    a,b=s.bounds(start,end)
    previous=start
    gaps=[]
    for ts in s.times[a:b]:
        missing=(ts-previous)//60-1
        if missing>0:gaps.append(missing)
        previous=ts
    trailing=(end-previous)//60
    if trailing>0:gaps.append(trailing)
    expected=(end-start)//60
    return dict(expected_minutes=expected,observed_minutes=b-a,
                coverage_ratio=(b-a)/expected if expected>0 else None,
                longest_gap_minutes=max(gaps,default=0),gap_count=len(gaps),
                missing_cause='unknown: no-trade and collection gaps cannot be distinguished')


def baseline_at(s, target_time, minutes):
    """target_time is hit-candle CLOSE (known time). Exclude that entire candle.

    Search all observed closes in [target_time-H, target_time), latest tie wins.
    This function has no episode/reset state and never reads a future candle.
    """
    a=bisect_left(s.times,target_time-minutes*60)
    b=bisect_left(s.times,target_time)
    if a==b:return None
    return min(range(a,b),key=lambda i:(s.close[i],-s.times[i]))


def milestones(s,t0,base,end):
    a,b=s.bounds(t0,end)
    result={}
    for threshold in (2,5,10):
        hit=next((i for i in range(a,b) if old.pct(s.high[i],base)>=threshold),None)
        result[str(threshold)]=None if hit is None else dict(
            bar_start=s.times[hit]-60,known_time=s.times[hit],high=s.high[hit],
            minutes_lower=(s.times[hit]-60-t0)/60,minutes_upper=(s.times[hit]-t0)/60,
            prefix_quality=quality(s,t0,s.times[hit]))
    return result


def price_events(market,s,kind,start,end):
    """Every first observed target hit for the unrestricted trailing minimum.

    A later recross of the same target from the same base is not a first hit.
    Complete evaluation time is required; quality never erases raw records.
    """
    minutes,threshold=old.DEFINITIONS[kind]
    q=deque();events=[]
    for j,target in enumerate(s.times):
        if j:
            i=j-1
            while q and s.close[q[-1]]>=s.close[i]:q.pop()
            q.append(i)
        while q and s.times[q[0]]<target-minutes*60:q.popleft()
        above=bool(q) and old.pct(s.high[j],s.close[q[0]])>=threshold
        if not above:continue
        i=q[0];t0=s.times[i];finish=t0+minutes*60
        if t0<start or finish>end:continue
        a,b=s.bounds(t0,finish)
        first=next(k for k in range(a,j+1) if old.pct(s.high[k],s.close[i])>=threshold)
        if first!=j:continue
        peak=max(range(a,b),key=lambda k:s.high[k])
        event=dict(event_id=old.identity('v2r',market,kind,target),market=market,
            definition=kind,horizon_minutes=minutes,threshold_pct=threshold,
            t0=t0,t0_utc=old.iso(t0),base_price=s.close[i],
            target_time=target,target_utc=old.iso(target),target_bar_start=target-60,
            target_high=s.high[j],target_return_pct=old.pct(s.high[j],s.close[i]),
            t0_to_target_minutes=(target-t0)/60,
            search_start=target-minutes*60,t0_from_search_start_minutes=(t0-(target-minutes*60))/60,
            peak_time=s.times[peak],peak_high=s.high[peak],
            max_rise_pct=old.pct(s.high[peak],s.close[i]),end_ts=finish,
            milestones=milestones(s,t0,s.close[i],finish),
            target_semantics='observed hit candle close/confirmation time; actual hit lies in previous minute',
            anchor_semantics='retrospective observed minimum, not a live onset detector')
        events.append(event)
    return events


def price_episodes(market,s,events,start,end):
    """Segment price path on close <= 95% of an EARLIER observed high.

    Hit-candle assignment, not overlapping evaluation windows, determines event
    membership. A boundary candle ends the old segment; the next candle starts
    the next one. Boundaries without any events do not become research episodes.
    """
    a,b=s.bounds(start,end)
    if a==b:return []
    prior=s.price(start)
    segment_start=start if prior is not None else s.times[a]
    start_price=prior if prior is not None else s.close[a]
    if prior is None:a+=1  # begin at the first observed close, never backfill it
    peak=start_price;low=start_price;segments=[];boundary_reason='analysis_start'
    def segment(finish,last_price,reason):
        return dict(start_time=segment_start,end_time=finish,start_price=start_price,
            end_price=last_price,episode_low=low,episode_high=peak,
            episode_return=old.pct(last_price,start_price),episode_range_pct=old.pct(peak,low),
            start_reason=boundary_reason,end_reason=reason,
            quality=quality(s,segment_start,finish))
    for i in range(a,b):
        previous_peak=peak
        peak=max(peak,s.high[i]);low=min(low,s.low[i])
        if s.close[i]<=previous_peak*.95:
            seg=segment(s.times[i],s.close[i],'close_drawdown_5pct_from_prior_high')
            seg['boundary_reference_high']=previous_peak
            seg['boundary_drawdown_pct']=old.pct(s.close[i],previous_peak)
            segments.append(seg)
            segment_start=s.times[i];start_price=s.close[i];peak=start_price;low=start_price
            boundary_reason='after_close_drawdown_5pct'
    if segment_start<s.times[b-1]:
        segments.append(segment(s.times[b-1],s.close[b-1],'analysis_end_right_censored'))
    finishes=[x['end_time'] for x in segments]
    grouped=defaultdict(list)
    for e in events:
        idx=bisect_left(finishes,e['target_time'])
        grouped[idx].append(e)
    result=[]
    for idx,es in grouped.items():
        seg=segments[idx]
        eid=old.identity('v2r_episode',market,seg['start_time'])
        reps={}
        for kind in old.DEFINITIONS:
            typed=[e for e in es if e['definition']==kind]
            if typed:reps[kind]=min(typed,key=lambda e:(e['target_time'],e['t0']))['event_id']
        for e in es:
            e['episode_id']=eid
            e['t0_precedes_episode']=e['t0']<seg['start_time']
            e['is_representative']=reps[e['definition']]==e['event_id']
        result.append(dict(**seg,episode_id=eid,market=market,
            A=sum(e['definition']=='A' for e in es),B=sum(e['definition']=='B' for e in es),
            representative_events=reps,event_ids=[e['event_id'] for e in es]))
    return result


WINDOWS={
    'trade_value_5m':[(5,0)],'prior_mean_trade_value_5m':[(65,5)],
    'trade_value_ratio':[(5,0),(65,5)],'trade_value_change_pct':[(5,0),(10,5)],
    'trade_value_acceleration':[(5,0),(10,5),(15,10)],
    'ma5':[(5,0)],'ma20':[(20,0)],'ma5_ma20_ratio':[(5,0),(20,0)],
    'ma20_slope_5m_pct':[(20,0),(25,5)],'range_30m_pct':[(30,0)],
    'range_change_pct':[(30,0),(60,30)],'distance_to_prior_high_pct':[(61,1)],
    'alt_relative_60m_pct':[(60,0)],'btc_relative_60m_pct':[(60,0)],
}


class RevisedResearch(old.Research):
    def __init__(self,panel,events,start,end,btc=None,min_coverage=.8,research_end=None):
        super().__init__(panel,events,start,end,btc)
        self.min_coverage=min_coverage
        self.research_end=end if research_end is None else research_end

    def snapshot(self,market,ts):
        result=super().snapshot(market,ts)
        if 'feature_quality' in result:return result
        s=self.panel[market]
        result['feature_quality']={}
        # Install maps before calling null_reason, which can query this snapshot.
        result['null_reasons']={}
        for key,value in result['values'].items():
            windows=WINDOWS.get(key)
            if windows is None and key.startswith('return_'):
                windows=[(int(key.split('_')[1][:-1]),0)]
            result['feature_quality'][key]=[
                dict(start=ts-a*60,end=ts-b*60,**quality(s,ts-a*60,ts-b*60)) for a,b in windows or []]
            if value is None:result['null_reasons'][key]=null_reason(s,ts,key,self,market)
        result['snapshot_context_quality']=quality(s,ts-120*60,ts)
        result['btc_window_quality']=quality(self.btc,ts-3600,ts) if self.btc else None
        return result

    def policy_quality(self,market,ts,kind):
        s=self.panel[market];h=old.DEFINITIONS[kind][0]*60
        windows={'past_360m':(ts-360*60,ts),'liquidity_baseline':(ts-360*60,ts-240*60),
                 'future':(ts,ts+h)}
        qs={k:quality(s,*span) for k,span in windows.items()}
        reasons=[]
        if ts<self.start or ts>=self.research_end or ts+h>self.end:reasons.append('outside_evaluation_period')
        if s.price(ts) is None:reasons.append('missing_anchor_close')
        reasons += ['low_coverage_'+k for k,q in qs.items() if q['coverage_ratio']<self.min_coverage]
        return dict(eligible=not reasons,reasons=reasons,windows=qs)

    def liquidity(self,market,ts):
        s=self.panel[market];start,end=ts-360*60,ts-240*60
        q=quality(s,start,end)
        if q['coverage_ratio']<self.min_coverage or q['observed_minutes']==0:return None
        a,b=s.bounds(start,end)
        # Mean per observed minute, NOT a sum treating absent minutes as zero.
        return (s.value_prefix[b]-s.value_prefix[a])/(b-a)

    def control_eligible(self,market,ts,kind):
        if not self.policy_quality(market,ts,kind)['eligible']:return False
        s=self.panel[market];h,target=old.DEFINITIONS[kind]
        if any(ts<b and a<ts+h*60 for a,b in self.intervals.get((market,kind),[])):
            return False
        a,b=s.bounds(ts,ts+h*60);low=s.price(ts)
        for i in range(a,b):
            if old.pct(s.high[i],low)>=target:return False
            low=min(low,s.close[i])
        return True

    def match(self,event,mode):
        if not event['observation_policy']['eligible']:
            return None,'case_observation_policy_failed'
        c,reason=super().match(event,mode)
        if c:
            c['observation_policy']=self.policy_quality(c['market'],c['t0'],event['definition'])
            q=c['observation_policy']['windows']['future']
            c['future_label_status']='NO_OBSERVED_SURGE_COMPLETE' if q['coverage_ratio']==1 else 'NO_OBSERVED_SURGE_PARTIAL_UNKNOWN_GAPS'
            c['liquidity_estimator']='mean trade value per observed minute; no imputation'
        return c,reason


def statistics_table(events,min_valid=20):
    """One representative per episode/type; report independent validity + pairs."""
    result=[]
    for kind in old.DEFINITIONS:
        cases=[e for e in events if e['definition']==kind and e['is_representative'] and e['observation_policy']['eligible']]
        for mode in ('primary','auxiliary'):
            controls=[e['controls'][mode] for e in cases if e['controls'][mode]]
            for offset in old.OFFSETS:
                for flag,title in old.FLAGS.items():
                    ev=[e['snapshots'][str(offset)]['flags'][flag] for e in cases]
                    cv=[c['snapshots'][str(offset)]['flags'][flag] for c in controls]
                    valid_e=[v for v in ev if v is not None];valid_c=[v for v in cv if v is not None]
                    pairs=[(e['snapshots'][str(offset)]['flags'][flag],e['controls'][mode]['snapshots'][str(offset)]['flags'][flag]) for e in cases if e['controls'][mode]]
                    pairs=[(x,y) for x,y in pairs if x is not None and y is not None]
                    # Keep the contrast matched, while exposing all group denominators.
                    er=100*sum(x for x,y in pairs)/len(pairs) if pairs else None
                    cr=100*sum(y for x,y in pairs)/len(pairs) if pairs else None
                    status='SUFFICIENT_FOR_DESCRIPTION' if min(len(valid_e),len(valid_c),len(pairs))>=min_valid else 'INSUFFICIENT_SAMPLE'
                    result.append(dict(definition=kind,control_type=mode,feature=flag,title=title,offset_minutes=offset,
                        total_events=len(ev),valid_event_count=len(valid_e),event_valid_rate=len(valid_e)/len(ev) if ev else None,
                        total_controls=len(cv),valid_control_count=len(valid_c),control_valid_rate=len(valid_c)/len(cv) if cv else None,
                        paired_valid_count=len(pairs),event_rate_pct=er,control_rate_pct=cr,
                        difference_pp_reference=er-cr if pairs else None,
                        difference_pp=er-cr if status=='SUFFICIENT_FOR_DESCRIPTION' else None,status=status,
                        minimum_valid_required=min_valid))
    return result


def dataset_events(panel,start,end,research_end=None):
    """Separate t0 eligibility from availability of outcome-buffer candles."""
    research_end=end if research_end is None else research_end
    if not start<research_end<=end:raise ValueError('Invalid research/outcome bounds')
    events=[];episodes=[]
    for market,s in panel.items():
        es=[]
        for kind in old.DEFINITIONS:
            es.extend(e for e in price_events(market,s,kind,start,end) if e['t0']<research_end)
        episodes.extend(price_episodes(market,s,es,start,end));events.extend(es)
    return events,episodes


def load_manifest_dataset(path):
    """One read-only DB for all alts AND BTC; no fallback to historical DBs."""
    with closing(old.open_readonly(path)) as db:
        manifest=json.loads(db.execute('SELECT payload FROM dataset_manifest WHERE id=1').fetchone()[0])
        lo,hi=manifest['collection_start'],manifest['collection_end']
        alts=manifest['alts']
        if 'KRW-BTC' in alts:raise ValueError('BTC must not be in the alt population')
        panel={m:old.load_series(db,m,lo,hi) for m in alts}
        btc=old.load_series(db,'KRW-BTC',lo,hi)
    if not btc.times or any(not s.times for s in panel.values()):raise ValueError('Manifest market data missing')
    return manifest,panel,btc


def analyze(panel,start,end,btc,min_coverage=.8,min_valid=20,research_end=None):
    events,episodes=dataset_events(panel,start,end,research_end)
    r=RevisedResearch(panel,events,start,end,btc,min_coverage,research_end)
    for e in sorted(events,key=lambda e:(e['target_time'],e['market'],e['definition'])):
        e['observation_policy']=r.policy_quality(e['market'],e['t0'],e['definition'])
        e['snapshots']=r.snapshots(e['market'],e['t0'])
        e['controls']={};e['unmatched_reasons']={}
        for mode in ('primary','auxiliary'):
            c,reason=r.match(e,mode) if e['is_representative'] else (None,'not_statistical_representative')
            e['controls'][mode]=c;e['unmatched_reasons'][mode]=reason
    stats=statistics_table(events,min_valid)
    summary={}
    for kind in old.DEFINITIONS:
        raw=[e for e in events if e['definition']==kind]
        reps=[e for e in raw if e['is_representative']]
        eligible=[e for e in reps if e['observation_policy']['eligible']]
        summary[kind]=dict(raw_events=len(raw),quality_eligible_raw_events=sum(e['observation_policy']['eligible'] for e in raw),
            representative_events=len(reps),eligible_representative_events=len(eligible),
            quality_exclusions=dict(Counter(reason for e in reps for reason in e['observation_policy']['reasons'])))
        for mode in ('primary','auxiliary'):
            n=sum(e['controls'][mode] is not None for e in eligible)
            summary[kind][mode]=dict(matched=n,rate_pct=100*n/len(eligible) if eligible else None,
                denominator='quality-eligible representatives',
                unmatched_reasons=dict(Counter(e['unmatched_reasons'][mode] for e in eligible if not e['controls'][mode])))
    valid=Counter();missing=Counter()
    for e in events:
        if e['is_representative'] and e['observation_policy']['eligible']:
            for f in e['snapshots'].values():
                for k,v in f['values'].items():
                    valid[k]+=v is not None;missing[k]+=v is None
    return dict(version='V2_REVISED',min_coverage=min_coverage,min_valid=min_valid,start= start,end=end,
        research_end=end if research_end is None else research_end,
        markets=sorted(panel),events=events,episodes=episodes,summary=summary,statistics=stats,
        statistical_dataset=[e['event_id'] for e in events if e['is_representative'] and e['observation_policy']['eligible']],
        feature_valid=dict(valid),feature_null=dict(missing),
        insufficient_rows=sum(s['status']=='INSUFFICIENT_SAMPLE' for s in stats),
        policies=dict(target_time='hit candle close (confirmation time), bar itself excluded from t0 search',
            raw_event='first observed target hit from global trailing minimum; same-base recrosses excluded; episode-independent',
            representative='first target_time per episode and type, chosen BEFORE quality or matching',
            episode='target candle belongs to price segment ending at >=5% close drawdown from previously observed high',
            episode_return='end close / segment start price - 1, percent; episode_range_pct is high/low range',
            quality='same past360, baseline120 and futureH coverage thresholds for cases/controls; no longest-gap cutoff',
            features='unchanged exact quantities: complete aggregation windows; exact endpoint returns; missing=NULL',
            liquidity='matching-only observed-minute mean, coverage-gated; missing minutes not zero',
            caution='partial controls are no OBSERVED surge, not proven absence; no inference or probability claims'))


def compare_t0(old_events,panel):
    result=[]
    for e in old_events:
        s=panel[e['market']];target=e['first_hit_known_ts']
        i=baseline_at(s,target,e['horizon_minutes'])
        j=bisect_left(s.times,target)
        result.append(dict(old_event_id=e['event_id'],market=e['market'],definition=e['definition'],
            old_t0=e['t0'],new_t0=s.times[i],delta_minutes=(s.times[i]-e['t0'])/60,
            old_price=e['base_price'],new_price=s.close[i],target_time=target,target_high=s.high[j],
            new_target_return_pct=old.pct(s.high[j],s.close[i]),new_elapsed_minutes=(target-s.times[i])/60,
            changed=e['t0']!=s.times[i],comparison='same frozen old target candle, independent of new event enumeration'))
    return result


def render(result):
    lines=['# V2 수정 정책 검증', '',f"coverage {result['min_coverage']:.0%}, 최소 유효 표본 {result['min_valid']}",'',
        't0는 사후 관측 저점입니다. target_time은 목표 고가를 확인한 봉의 마감 시각이며 t0 후보에서 그 봉을 제외합니다.',
        '원본 event는 보존하고, 가격 흐름 episode·유형별 최초 목표 도달 event를 먼저 대표로 고른 뒤 동일 품질 정책을 적용합니다.',
        '일부 누락이 허용된 대조군은 관측된 급등이 없다는 뜻이며, 누락 중 급등하지 않았음을 보장하지 않습니다.', '',
        f"고유 episode {len(result['episodes'])}; 유효 표본 부족 통계행 {result['insufficient_rows']}/{len(result['statistics'])}",'']
    lines+=table(['유형','raw','품질 적격 raw','대표','품질 적격 대표','주 매칭','주 %','보조 매칭','보조 %'],[
        [k,s['raw_events'],s['quality_eligible_raw_events'],s['representative_events'],s['eligible_representative_events'],s['primary']['matched'],s['primary']['rate_pct'],s['auxiliary']['matched'],s['auxiliary']['rate_pct']] for k,s in result['summary'].items()])
    lines+=['','## Episode','', '수익률은 시작 가격 대비 종료 종가입니다. low/high 범위 상승률과 구분합니다. t0는 episode 시작 이전일 수도 있으며 원본에 표시합니다.','']
    lines+=table(['ID','종목','시작 KST','종료 KST','low','high','종료 수익률 %','A','B','대표'],[
        [e['episode_id'],e['market'],kst(e['start_time']),kst(e['end_time']),e['episode_low'],e['episode_high'],e['episode_return'],e['A'],e['B'],json.dumps(e['representative_events'])] for e in result['episodes']])
    lines+=['','## 단일 특징 통계','', '발생률은 양쪽 값이 있는 매칭 쌍 기준입니다. 그룹별 유효 수·비율도 별도 표시하며 최소 유효 쌍 수에도 동일 기준을 적용합니다. 부족한 차이는 JSON에 참고 수치만 남깁니다.','']
    for kind in old.DEFINITIONS:
        for mode in ('primary','auxiliary'):
            lines += [f'### {kind} / {mode}','']+table(
                ['특징','분 전','전체 사건','유효 사건','유효율','전체 대조','유효 대조','유효율','유효 쌍','사건 %','대조 %','차이 %p / 상태'],[
                [s['title'],s['offset_minutes'],s['total_events'],s['valid_event_count'],s['event_valid_rate'],s['total_controls'],s['valid_control_count'],s['control_valid_rate'],s['paired_valid_count'],s['event_rate_pct'],s['control_rate_pct'],s['status'] if s['difference_pp'] is None else s['difference_pp']]
                for s in result['statistics'] if s['definition']==kind and s['control_type']==mode])+['']
    return '\n'.join(lines)


def render_comparison(c):
    lines=['# V2 연구 정책 수정: 동일 40종목 비교','',
        '표본을 다시 선정하지 않았습니다. 이전 보고서의 40종목과 KST 2026-08-19 00:00~08-24 00:00을 고정했습니다. API 및 다운로드 없음. 원본 DB 해시 동일.','',
        'target_time은 목표 고가를 확인한 분봉의 마감 시각입니다. 실제 도달은 그 직전 1분 안에 있습니다. t0는 [target_time-H,target_time)에서 관측된 종가 최솟값의 가장 최근 시각입니다. 목표 봉과 이후 봉은 제외합니다. 이 시각은 사후 연구 기준점입니다.','',
        '## 사건·대표·매칭 비교','',
        '과거 매칭률은 raw event를 분모로 사용했습니다. 수정 후 분모는 품질 적격 대표 event입니다. 비율 상승을 예측력 개선으로 해석하지 마세요. 대표는 품질 필터 전에 선택하므로 불완전한 첫 대표를 더 좋은 후속 사건으로 교체하지 않습니다.','']
    rows=[]
    for kind,s in c['previous'].items():
        rows.append(['이전',kind,s['events'],c['previous_representatives'][kind],s['events'],s['primary']['matched'],s['primary']['rate_pct'],s['auxiliary']['matched'],s['auxiliary']['rate_pct']])
    for cov,r in c['thresholds'].items():
        for kind,s in r['summary'].items():
            rows.append([cov,kind,s['raw_events'],s['representative_events'],s['eligible_representative_events'],s['primary']['matched'],s['primary']['rate_pct'],s['auxiliary']['matched'],s['auxiliary']['rate_pct']])
    lines+=table(['정책','유형','raw','대표','매칭 분모','주 매칭','주 %','보조 매칭','보조 %'],rows)
    lines+=['',f"이전 episode {c['previous_episode_count']} → 수정 episode {c['thresholds']['0.8']['episodes']}. 원본 사건과 episode는 관측률 정책에 따라 지우지 않고 적격 여부를 별도로 표시합니다.",'',
        '## t0 비교','',
        f"기존 목표 확인 시각을 고정한 {len(c['t0_comparisons'])}건 중 t0 변경 {c['changed_t0_count']}건. 대표 10개는 같은 ID를 유지해 별도 재계산했습니다.",
        f"새 사건 추출과 기존 추출의 공통 목표 봉 {c['target_identity']['common']}건, 기존에만 {c['target_identity']['old_only']}건, 새 결과에만 {c['target_identity']['new_only']}건. t0 변경과 사건 재선정은 다른 집계입니다.",'']
    lines+=table(['종목','유형','old t0 KST','new t0 KST','차이 분','old 가격','new 가격','목표 확인 KST','new 수익 %','소요 분'],[
        [e['market'],e['definition'],kst(e['old_t0']),kst(e['new_t0']),e['delta_minutes'],e['old_price'],e['new_price'],kst(e['target_time']),e['new_target_return_pct'],e['new_elapsed_minutes']] for e in c['representative_10']])
    e=c['ong_regression']
    lines+=['','### ONG regression','',
        f"고정 목표 {kst(e['target_time'])}: {kst(e['old_t0'])} / {e['old_price']} → {kst(e['new_t0'])} / {e['new_price']}. 시간 차이 {e['delta_minutes']}분, 새 기준 목표 고가 수익률 {e['new_target_return_pct']:.3f}%.",
        '이 고정 목표 봉 자체를 새 사건으로 강제로 남기지는 않습니다. 새 기준 가격에서 이미 목표를 먼저 달성했다면 나중 재돌파는 최초 사건이 아닙니다. 새 추출에서는 08-20 22:26 확인 봉의 A 사건 기준점이 21:30 / 82.3입니다. 목표 시각이 바뀌면 최저가 검색 창도 바뀝니다.','',
        '## ONG 이전 다중 사건 episode의 새 가격 경계','']
    lines+=table(['이전 episode','이전 유형','이전 목표 KST','새 price episode','새 시작','새 끝','끝 사유','기준 고점','종가 되돌림 %'],[
        [x['old_episode_id'],x['definition'],kst(x['target_time']),x.get('new_episode_id'),kst(x['new_start']) if x.get('new_start') is not None else None,kst(x['new_end']) if x.get('new_end') is not None else None,x.get('reason'),x.get('reference_high'),x.get('drawdown_pct')] for x in c['ong_episode_mapping']])
    lines+=['','평가 구간이 겹치는지는 병합에 사용하지 않습니다. 기존 ONG A4+B1은 고점 대비 종가 5% 되돌림을 사이에 둔 여러 가격 구간으로 분리됩니다. 목표 봉이 어느 가격 구간에 속하는지로 연결하므로 전역 저점 t0가 그 episode 시작보다 앞설 수 있습니다.','',
        '## 특징별 유효 표본·NULL','',
        '다음은 품질 적격 대표의 5개 시점을 합친 데이터 가용성입니다. 최소 표본 판단은 이 합계가 아니라 유형·대조군·시점별로 수행합니다.','']
    keys=c['thresholds']['0.8']['feature_valid']
    lines+=table(['특징','80% 유효','80% NULL','100% 유효','100% NULL'],[
        [k,c['thresholds']['0.8']['feature_valid'][k],c['thresholds']['0.8']['feature_null'][k],c['thresholds']['1.0']['feature_valid'][k],c['thresholds']['1.0']['feature_null'][k]] for k in keys])
    lines+=['',f"INSUFFICIENT_SAMPLE: 80% {c['thresholds']['0.8']['insufficient_rows']}/240행, 100% {c['thresholds']['1.0']['insufficient_rows']}/240행. 최소 유효 표본 {c['min_valid']}개. 사건과 대조군 각각 및 유효 매칭 쌍이 기준 이상이어야 차이를 기본 표에 표시합니다.",
        '같은 예전 대표 10개 × 5시점의 NULL 수 비교는 JSON의 fixed_case_feature_null_comparison에 저장했습니다. 이 10개는 t0가 그대로여서 기존 특징 값도 그대로입니다.','',
        '## 검증·남은 한계','',
        f"새 raw event 전부의 전역 최저 종가 및 최초 도달 조건 검증: {c['verified_raw_events']}건. 기존 10개 사례의 미래 제거 불변성: {c['real_feature_truncation_checks']}회.",
        'coverage 정책은 사건/대조군의 과거360분·기준 유동성120분·미래H분에 동일하게 적용합니다. 최장 공백은 기록만 하고 아직 상한을 정하지 않았습니다.',
        '80% 대조군은 관측된 급등이 없다는 뜻입니다. 누락 중 급등을 배제하지 못합니다. 100% 정책은 표본 손실이 크며 B 통계 표본이 없습니다.',
        '매칭용 유동성은 관측 분당 평균으로 계산합니다. 없는 분을 0으로 더하거나 가격을 보간하지 않습니다. 집계 특징의 정의는 바꾸지 않아 불완전 창은 NULL입니다.',
        f"t0가 가격 episode 시작 이전인 raw event: {c['thresholds']['0.8']['t0_before_episode']}건. 전역 사후 저점과 이후 가격 흐름의 경계는 서로 다른 기준입니다.",
        '**연구 설계 상태: NOT READY.** 구현 검증은 통과했지만 기본 coverage 정책 미확정, 최장 공백 허용 기준 미확정, 부분 관측 대조군의 음성 라벨 불확실성, B 유효 표본 부족 때문에 전체 종목 결과를 공통점의 증거로 해석하기에는 이릅니다. 전체 분석은 실행하지 않았습니다.','']
    return '\n'.join(lines)


def fixed_sample_run(min_valid=20):
    baseline_path=REPORTS_DIR/'surge_event_v2_medium_audit.json'
    baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
    previous=json.loads((REPORTS_DIR/'surge_event_v2_medium_research.json').read_text(encoding='utf-8'))
    sample=baseline['sample'];start,end=sample['start'],sample['end']
    if len(sample['markets'])!=40 or start!=old.parse_time('2026-08-19T00:00:00+09:00') or end!=old.parse_time('2026-08-24T00:00:00+09:00'):
        raise ValueError('Frozen 40-market/5-day baseline does not match requested scope')
    paths=[DATA_DIR/'altcoin_market.db',DATA_DIR/'historical_market.db']
    before={str(p):digest(p) for p in paths}
    with closing(old.open_readonly(paths[0])) as db:
        panel={m:old.load_series(db,m,start-360*60,end) for m in sample['markets']}
    with closing(old.open_readonly(paths[1])) as db:btc=old.load_series(db,'KRW-BTC',start-360*60,end)
    results={}
    for coverage in (.8,1.):
        print('REVALIDATE',len(panel),'markets coverage',coverage,flush=True)
        r=analyze(panel,start,end,btc,coverage,min_valid);results[str(coverage)]=r
        prefix=REPORTS_DIR/f'surge_event_v2_revised_{int(coverage*100)}'
        prefix.with_suffix('.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        prefix.with_suffix('.md').write_text(render(r),encoding='utf-8')
    comparisons=compare_t0(previous['events'],panel)
    by_id={c['old_event_id']:c for c in comparisons}
    cases=[by_id[c['event']['event_id']] for c in baseline['audit']['cases']]
    regression=next(c for c in comparisons if c['old_event_id']=='cc5e67ecc357ab6997ed')
    assert regression['new_t0']==old.parse_time('2026-08-20T22:06:00+09:00') and regression['new_price']==82.7
    r80=results['0.8']
    for e in r80['events']:
        s=panel[e['market']];i=baseline_at(s,e['target_time'],e['horizon_minutes'])
        assert (s.times[i],s.close[i])==(e['t0'],e['base_price'])
        a,b=s.bounds(e['t0'],e['target_time'])
        first=next(j for j in range(a,b) if old.pct(s.high[j],e['base_price'])>=e['threshold_pct'])
        assert s.times[first]==e['target_time']
    real_checks=0;old_null=Counter();new_null=Counter()
    researcher=RevisedResearch(panel,r80['events'],start,end,btc)
    for before_case,new_case in zip(baseline['audit']['cases'],cases):
        for offset in old.OFFSETS:
            ts=new_case['new_t0']-offset*60;m=new_case['market'];s=panel[m]
            f=researcher.snapshot(m,ts)
            old_f=next(f for f in before_case['features'] if f['offset']==offset)['snapshot']
            for k,v in f['values'].items():
                old_null[k]+=old_f['values'][k] is None;new_null[k]+=v is None
            n=bisect_right(s.times,ts)
            shortened=old.Series((s.times[i]-60,s.close[i],s.high[i],s.low[i],s.close[i],s.value_prefix[i+1]-s.value_prefix[i]) for i in range(n))
            short_panel=dict(panel);short_panel[m]=shortened
            truncated=RevisedResearch(short_panel,[],start,end,btc).snapshot(m,ts)
            for k,v in f['values'].items():
                w=truncated['values'][k]
                assert (v is None and w is None) or (v is not None and w is not None and math.isclose(v,w,rel_tol=1e-9,abs_tol=1e-6))
            assert f['feature_quality']==truncated['feature_quality']
            real_checks+=1
    old_keys={(e['market'],e['definition'],e['first_hit_known_ts']) for e in previous['events']}
    new_keys={(e['market'],e['definition'],e['target_time']) for e in r80['events']}
    ong_mapping=[]
    for e in previous['events']:
        if e['market']!='KRW-ONG':continue
        eps=next((ep for ep in r80['episodes'] if ep['market']=='KRW-ONG' and ep['start_time']<e['first_hit_known_ts']<=ep['end_time']),None)
        ong_mapping.append(dict(old_episode_id=e['episode_id'],definition=e['definition'],target_time=e['first_hit_known_ts'],
            new_episode_id=eps['episode_id'] if eps else None,new_start=eps['start_time'] if eps else None,
            new_end=eps['end_time'] if eps else None,reason=eps['end_reason'] if eps else 'no surviving first-hit event in this segment',
            reference_high=eps.get('boundary_reference_high') if eps else None,drawdown_pct=eps.get('boundary_drawdown_pct') if eps else None))
    after={str(p):digest(p) for p in paths};assert before==after
    comparison=dict(sample=sample,source_hashes_before=before,source_hashes_after=after,
        min_valid=min_valid,verified_raw_events=len(r80['events']),real_feature_truncation_checks=real_checks,
        previous_episode_count=len(baseline['audit']['episodes']),
        previous_representatives={k:sum(ep[k]>0 for ep in baseline['audit']['episodes']) for k in old.DEFINITIONS},
        target_identity=dict(common=len(old_keys&new_keys),old_only=len(old_keys-new_keys),new_only=len(new_keys-old_keys)),
        ong_episode_mapping=ong_mapping,
        fixed_case_feature_null_comparison=dict(before=dict(old_null),after=dict(new_null)),
        previous=baseline['audit']['totals'],t0_comparisons=comparisons,representative_10=cases,ong_regression=regression,
        changed_t0_count=sum(c['changed'] for c in comparisons),
        thresholds={k:dict(summary=r['summary'],episodes=len(r['episodes']),insufficient_rows=r['insufficient_rows'],
                          feature_valid=r['feature_valid'],feature_null=r['feature_null'],
                          t0_before_episode=sum(e['t0_precedes_episode'] for e in r['events'])) for k,r in results.items()})
    (REPORTS_DIR/'surge_event_v2_policy_comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (REPORTS_DIR/'surge_event_v2_policy_comparison.md').write_text(render_comparison(comparison),encoding='utf-8')
    print(json.dumps(comparison['thresholds'],ensure_ascii=False),flush=True)
    return comparison,results,panel,btc


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--min-valid',type=int,default=20)
    p.add_argument('--db',type=Path,help='Read-only manifest dataset, including its own BTC')
    p.add_argument('--output',type=Path,default=REPORTS_DIR/'research_market_v1_analysis')
    args=p.parse_args()
    if args.min_valid<1:p.error('--min-valid must be positive')
    if args.db:
        manifest,panel,btc=load_manifest_dataset(args.db)
        result=analyze(panel,manifest['research_start'],manifest['collection_end'],btc,
                       min_valid=args.min_valid,research_end=manifest['research_end'])
        result['source_db']=str(args.db)
        result['manifest']=manifest
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        args.output.with_suffix('.md').write_text(render(result),encoding='utf-8')
        print(json.dumps(result['summary'],ensure_ascii=False,indent=2))
    else:
        fixed_sample_run(args.min_valid)


if __name__=='__main__':main()
