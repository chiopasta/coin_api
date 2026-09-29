"""Offline final preflight of a manifest dataset using unchanged revised V2 policies."""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import statistics

from . import surge_event_research_v2_revised as v
from .paths import DATA_DIR, REPORTS_DIR

KST=timezone(timedelta(hours=9))
FEATURES=['return_5m_pct','return_15m_pct','return_30m_pct','return_60m_pct',
          'return_120m_pct','trade_value_ratio','trade_value_acceleration','ma5','ma20',
          'ma5_ma20_ratio','ma20_slope_5m_pct','range_30m_pct','distance_to_prior_high_pct',
          'prior_high_breakout','alt_relative_60m_pct','btc_relative_60m_pct']


def period(a,b):
    return dict(start_utc=v.old.iso(a),end_exclusive_utc=v.old.iso(b),
                start_kst=datetime.fromtimestamp(a,KST).isoformat(),end_exclusive_kst=datetime.fromtimestamp(b,KST).isoformat())


def values(research,market,ts):
    f=research.snapshot(market,ts)
    result=dict(f['values'])
    result['prior_high_breakout']=f['flags']['prior_high_breakout']
    # V2 has no 120m return feature: endpoint-only diagnostic, NOT a new research feature.
    result['return_120m_pct']=research.panel[market].return_at(ts,120)
    return {k:result[k] for k in FEATURES}


def percentage(n,total):
    return 100*n/total if total else None


def run(path,output):
    before=v.digest(path)
    with closing(v.old.open_readonly(path)) as db:
        manifest=json.loads(db.execute('SELECT payload FROM dataset_manifest WHERE id=1').fetchone()[0])
        start,end=manifest['research_start'],manifest['research_end']
        lo,hi=manifest['collection_start'],manifest['collection_end']
        actual=[r[0] for r in db.execute('SELECT DISTINCT market FROM minute_candles ORDER BY market')]
        schema=[list(r) for r in db.execute('PRAGMA table_info(minute_candles)')]
        errors=Counter();total=0;previous={};counts=Counter()
        for m,t,o,h,l,c,tv in db.execute('SELECT market,ts,open,high,low,close,trade_value FROM minute_candles ORDER BY market,ts'):
            total+=1;counts[m]+=1
            if not isinstance(t,int) or t%60 or not lo<=t<hi:errors['invalid_timestamp']+=1
            if m in previous and t<=previous[m]:errors['duplicate_or_nonincreasing_timestamp']+=1
            previous[m]=t
            if not all(x is not None and math.isfinite(x) and x>0 for x in (o,h,l,c)) or not l<=min(o,c)<=max(o,c)<=h:errors['invalid_ohlc']+=1
            if tv is None or not math.isfinite(tv) or tv<0:errors['invalid_trade_value']+=1
        duplicates=db.execute('SELECT COUNT(*) FROM (SELECT market,ts FROM minute_candles GROUP BY market,ts HAVING COUNT(*)>1)').fetchone()[0]
        integrity=db.execute('PRAGMA quick_check').fetchone()[0]
        state_columns=[r[1] for r in db.execute('PRAGMA table_info(collection_state)')]
        states=[dict(zip(state_columns,r)) for r in db.execute('SELECT * FROM collection_state')]
        if set(actual)!=set(manifest['markets']):errors['manifest_market_mismatch']+=1
        if set(actual)!=set(s['market'] for s in states):errors['state_market_mismatch']+=1
        if 'KRW-BTC' not in actual:errors['missing_btc']+=1
        if integrity!='ok':errors['sqlite_integrity']+=1
        for s in states:
            if s['status']!='COMPLETE':errors['state_not_complete']+=1
            if s['requested_start']!=lo or s['requested_end']!=hi or s['next_cursor']>lo:errors['state_range_unverified']+=1
            if s['rows_saved']!=counts[s['market']]:errors['state_row_mismatch']+=1
        series={m:v.old.load_series(db,m,lo,hi) for m in actual}
    btc=series['KRW-BTC'];panel={m:s for m,s in series.items() if m!='KRW-BTC'}
    prior={e['market']:e['prior_24h_coverage'] for e in manifest['selection_evidence']}
    markets=[]
    for m,s in series.items():
        q=v.quality(s,start,end)
        daily=[dict(date=datetime.fromtimestamp(t,KST).date().isoformat(),**v.quality(s,t,min(end,t+86400))) for t in range(start,end,86400)]
        p=prior.get(m)
        markets.append(dict(market=m,**q,daily=daily,daily_min_coverage=min(d['coverage_ratio'] for d in daily),
                            daily_mean_coverage=statistics.mean(d['coverage_ratio'] for d in daily),prior_coverage=p,
                            change_pp=100*(q['coverage_ratio']-p) if p is not None else None,
                            before_buffer=v.quality(s,lo,start),after_buffer=v.quality(s,end,hi)))
    print('Validated DB and coverage',flush=True)
    events,episodes=v.dataset_events(panel,start,hi,research_end=end)
    r=v.RevisedResearch(panel,events,start,hi,btc,min_coverage=.8,research_end=end)
    sampling=defaultdict(Counter);null_reasons=defaultdict(Counter)
    grid=list(range(start,end,3600))
    for ts in grid:
        for m in panel:
            fs=values(r,m,ts)
            for key,value in fs.items():
                sampling[(m,key)]['valid' if value is not None else 'null']+=1
            for key,reason in r.snapshot(m,ts)['null_reasons'].items():
                null_reasons[key][str(reason)]+=1
        # Deterministic grid does not need to remain in memory for event matching.
        r.feature_cache.clear()
    features={}
    for key in FEATURES:
        by_market=[dict(market=m,valid=sampling[(m,key)]['valid'],null=sampling[(m,key)]['null'],valid_pct=percentage(sampling[(m,key)]['valid'],len(grid))) for m in panel]
        n=sum(x['valid'] for x in by_market);n_total=len(grid)*len(panel)
        features[key]=dict(valid=n,null=n_total-n,total=n_total,valid_pct=percentage(n,n_total),
                           market_min_pct=min(x['valid_pct'] for x in by_market),market_max_pct=max(x['valid_pct'] for x in by_market),
                           by_market=by_market,null_reasons=dict(null_reasons[key]))
    print(f'Features checked: {len(grid)*len(panel)} fixed hourly samples; events={len(events)}',flush=True)
    per_event=[]
    for e in sorted(events,key=lambda e:(e['target_time'],e['market'],e['definition'])):
        m,ts,kind=e['market'],e['t0'],e['definition'];s=panel[m]
        e['observation_policy']=r.policy_quality(m,ts,kind)
        offsets={}
        for offset in (120,60,30,15,5):
            t=ts-offset*60;f=values(r,m,t);q=v.quality(s,t-7200,t)
            offsets[str(offset)]=dict(exact_close=s.price(t) is not None,coverage_120m=q['coverage_ratio'],
                                     observable=s.price(t) is not None and q['coverage_ratio']>=.8,
                                     valid_features=[k for k,val in f.items() if val is not None])
        future=v.quality(s,ts,ts+21600)
        future_ok=future['coverage_ratio']>=.8 and s.price(ts+21600) is not None
        usable=sum(x['observable'] for x in offsets.values())+future_ok
        category='all' if usable==6 else 'partial' if usable else 'insufficient'
        candidates=[];base=r.liquidity(m,ts)
        same_time=sum(other!=m and ss.price(ts) is not None for other,ss in panel.items())
        if e['observation_policy']['eligible'] and base is not None and base>0:
            for other in sorted(panel):
                if other==m:continue
                liq=r.liquidity(other,ts)
                if liq is not None and liq>0 and 1/3<=liq/base<=3 and r.control_eligible(other,ts,kind):candidates.append(other)
        match,reason=r.match(e,'primary') if e['is_representative'] else (None,'not_statistical_representative')
        paired={str(o):[k for k,value in values(r,m,ts-o*60).items() if value is not None and values(r,match['market'],ts-o*60)[k] is not None] for o in v.old.OFFSETS} if match else {}
        per_event.append(dict(**e,observations=offsets,future_6h=future,future_6h_observable=future_ok,
                             observation_category=category,all_features_all_offsets=all(len(o['valid_features'])==len(FEATURES) for o in offsets.values()),
                             same_time_other_markets=same_time,independent_control_candidates=candidates,
                             matched_control=({k:val for k,val in match.items() if k!='snapshots'} if match else None),
                             match_reason=reason,paired_valid_features=paired))
    summary={}
    for kind in v.old.DEFINITIONS:
        es=[e for e in per_event if e['definition']==kind];reps=[e for e in es if e['is_representative']]
        eligible=[e for e in reps if e['observation_policy']['eligible']];matched=[e for e in reps if e['matched_control']]
        summary[kind]=dict(raw=len(es),representatives=len(reps),policy_eligible_raw=sum(e['observation_policy']['eligible'] for e in es),
                           policy_eligible_representatives=len(eligible),observations=dict(Counter(e['observation_category'] for e in es)),
                           all_features_all_offsets=sum(e['all_features_all_offsets'] for e in es),
                           same_time_candidate_events=sum(e['same_time_other_markets']>0 for e in es),
                           independently_matchable_raw=sum(bool(e['independent_control_candidates']) for e in es),
                           matched_representatives=len(matched),unmatched_representatives=len(reps)-len(matched),
                           unmatched_eligible_representatives=len(eligible)-len(matched),
                           match_pct_of_eligible=percentage(len(matched),len(eligible)),match_pct_of_representatives=percentage(len(matched),len(reps)),
                           reasons=dict(Counter(e['match_reason'] for e in reps if not e['matched_control'])),
                           paired_feature_counts={str(o):{k:sum(k in e['paired_valid_features'][str(o)] for e in matched) for k in FEATURES} for o in v.old.OFFSETS})
    coverage_bins={label:sum(row['coverage_ratio']>=t for row in markets) for label,t in [('95',.95),('90',.9),('80',.8),('70',.7),('60',.6)]}
    coverage_bins['below60']=sum(row['coverage_ratio']<.6 for row in markets)
    after=v.digest(path)
    if before!=after:raise RuntimeError('Source DB changed during audit')
    result=dict(source=str(path),hash_before=before,hash_after=after,basic=dict(rows=total,markets=len(actual),btc_included='KRW-BTC' in actual,
                duplicates=duplicates,errors=dict(errors),integrity=integrity,schema=schema,states=states),
                periods=dict(research=period(start,end),before_buffer=period(lo,start),after_buffer=period(end,hi)),
                compatibility=dict(utc_epoch_seconds=True,candle_timestamp='open time; V2 Series adds 60 seconds to confirmed close time',
                                   trade_value='candle_acc_trade_price (KRW), not volume',btc_source=str(path),
                                   missing_policy='No imputation; return_120m_pct is endpoint diagnostic only (not an existing V2 feature)'),
                coverage=dict(mean=statistics.mean(x['coverage_ratio'] for x in markets),alt_mean=statistics.mean(x['coverage_ratio'] for x in markets if x['market']!='KRW-BTC'),
                              distribution=coverage_bins,markets=markets),
                features=features,deterministic_grid=dict(interval_minutes=60,times_per_market=len(grid),markets=len(panel),total=len(grid)*len(panel),range='start inclusive, end exclusive'),
                events=per_event,episodes=episodes,event_summary=summary,unique_episodes=len(episodes),
                overlap_episodes=sum(ep['A']>0 and ep['B']>0 for ep in episodes),event_markets=len({e['market'] for e in events}),
                top_event_markets=Counter(e['market'] for e in events).most_common(),
                observation_definition='all: all 5 exact pre-event closes with previous120m coverage>=80%, plus t0+6h exact close and future360m coverage>=80%; partial: 1..5 of these 6; insufficient: none. Separate from unchanged V2 policy and feature completeness.',
                control_definition='Raw candidate existence ignores reuse; actual allocation only first episode/type representatives, original chronological order, 80% symmetric policy and liquidity 1/3..3, original non-reuse.',
                boundary_policy='Mine unchanged V2 with collection_end as outcome limit; filter t0 to [research_start,research_end) BEFORE episode/statistics. No buffer t0 events. Episodes may end in outcome buffer.')
    result['readiness']='NOT READY' if errors or not any(s['matched_representatives'] for s in summary.values()) else 'READY'
    result['readiness_evidence']={kind:dict(matched=s['matched_representatives'],
        paired_feature_offset_cells_at_least20=sum(n>=20 for fs in s['paired_feature_counts'].values() for n in fs.values()),
        paired_feature_offset_cells_below20=sum(n<20 for fs in s['paired_feature_counts'].values() for n in fs.values())) for kind,s in summary.items()}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    output.with_suffix('.md').write_text(render(result),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('event_summary','unique_episodes','overlap_episodes','event_markets','readiness')},indent=2))
    return result


def render(r):
    lines=['# Research market V1 최종 품질검사','',f"판정: **{r['readiness']}**",'',
           f"{r['basic']['rows']:,}봉 / {r['basic']['markets']}시장. 오류: {r['basic']['errors']}. 중복: {r['basic']['duplicates']}. SHA256 동일.",
           'API 호출/보간/원본 DB 수정 없음. BTC는 동일 DB에서 읽으며 알트 모집단에서 제외.','', '## 기간','']
    for name,p in r['periods'].items():lines.append(f"- {name}: {p['start_kst']} ~ {p['end_exclusive_kst']} / UTC {p['start_utc']} ~ {p['end_exclusive_utc']}")
    lines+=['',r['boundary_policy'],'','## 시장별 coverage','',f"전체 평균 {r['coverage']['mean']:.2%}, 알트 평균 {r['coverage']['alt_mean']:.2%}. 누적 분포: {r['coverage']['distribution']}",'',
            '|market|관측/기대 분|coverage|최장 gap|일 최저|일 평균|prior 대비 %p|','|---|---|---|---|---|---|---|']
    for x in r['coverage']['markets']:
        lines.append(f"|{x['market']}|{x['observed_minutes']}/{x['expected_minutes']}|{x['coverage_ratio']:.2%}|{x['longest_gap_minutes']}|{x['daily_min_coverage']:.2%}|{x['daily_mean_coverage']:.2%}|{x['change_pp']}|")
    lines+=['','## Deterministic feature 검사','',str(r['deterministic_grid']),
            '120분 수익률은 현재 V2에 없는 endpoint 진단 항목이다. 나머지는 기존 revised snapshot 값과 flag를 사용한다.',
            '상대강도는 당시 계산 가능한 다른 알트 수익률의 중앙값 대비다. 결측을 0으로 채우지 않는다.','',
            '|feature|valid|NULL|valid %|시장별 최저~최고 %|','|---|---|---|---|---|']
    for k,f in r['features'].items():lines.append(f"|{k}|{f['valid']}|{f['null']}|{f['valid_pct']:.2f}|{f['market_min_pct']:.2f} ~ {f['market_max_pct']:.2f}|")
    lines+=['','## Event / control','',f"episode {r['unique_episodes']}, A/B 공통 episode {r['overlap_episodes']}, 발생 시장 {r['event_markets']}",
            'raw와 episode/type 대표 사건을 구분한다. 대조군 재사용 금지 정책으로 실제 매칭은 대표 사건에만 적용한다.','']
    for kind,s in r['event_summary'].items():
        lines += [f'### {kind}','',f"raw {s['raw']}, 대표 {s['representatives']}, 정책 적격 대표 {s['policy_eligible_representatives']}, 매칭 {s['matched_representatives']}",
                  f"관측 분류: {s['observations']}. raw 독립 매칭 가능 {s['independently_matchable_raw']}. 매칭률(적격 대표 분모) {s['match_pct_of_eligible']}%.",
                  f"미매칭 사유: {s['reasons']}",'']
    lines += [r['observation_definition'],'','시장별 event 순위: '+str(r['top_event_markets']),
              '', '## 해석','',
              'READY는 기술적·탐색적 본 분석 진행 가능을 뜻한다. 통계적 충분성은 대표 사건/매칭쌍과 feature별 유효 수를 함께 판단해야 한다.',
              '최소 유효 20개 정책을 유지하며 20 미만 feature는 INSUFFICIENT_SAMPLE로 처리해야 한다. NULL 자체는 DB 오류가 아니다.',
              '판정 근거(보조 진단 120분 수익률 포함): '+str(r['readiness_evidence']),
              '전체 시장별 feature 편차, 일별 coverage, event별 관측 여부와 매칭쌍 feature 수는 동명 JSON에 보존했다.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DATA_DIR/'research_market_v1.db')
    p.add_argument('--output',type=Path,default=REPORTS_DIR/'research_market_v1_quality')
    a=p.parse_args();run(a.db,a.output)


if __name__=='__main__':main()
