"""Bounded offline audit: select 40 markets by coverage, never by returns."""

from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone, timedelta
import hashlib
import html
import json
import math
from pathlib import Path
import statistics

from . import surge_event_research_v2 as v2
from .paths import DATA_DIR, REPORTS_DIR

STAGES = ('candidates', 'case_liquidity', 'not_reused', 'candidate_liquidity',
          'liquidity_ratio', 'time_bounds', 'price_at_t0', 'past_complete',
          'future_complete', 'no_event_overlap', 'no_future_surge',
          'no_control_overlap', 'selected')


class AuditedResearch(v2.Research):
    """Instrument every candidate; delegate the actual choice to unchanged V2."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.matching_diagnostics = {}

    def match(self, event, mode):
        market, ts, kind = event['market'], event['t0'], event['definition']
        h, threshold = v2.DEFINITIONS[kind]
        h *= 60
        if mode == 'primary':
            options = [(m,ts) for m in sorted(self.panel) if m != market]
        else:
            lo,hi = max(self.start,ts-7*86400),min(self.end,ts+7*86400)
            options = [(market,t) for t in range((lo+3599)//3600*3600,hi,3600)]
        counts = dict.fromkeys(STAGES,0)
        counts['candidates'] = len(options)
        failures = Counter()
        base = self.liquidity(market,ts)
        for m,t in options:
            s = self.panel[m]
            checks = (
                ('case_liquidity', lambda: base is not None and base > 0),
                ('not_reused', lambda: (mode,kind,m,t) not in self.used),
                ('candidate_liquidity', lambda: self.liquidity(m,t) is not None and self.liquidity(m,t)>0),
                ('liquidity_ratio', lambda: 1/3 <= self.liquidity(m,t)/base <= 3),
                ('time_bounds', lambda: t >= self.start and t+h <= self.end),
                ('price_at_t0', lambda: s.price(t) is not None),
                ('past_complete', lambda: s.full(t-360*60,t)),
                ('future_complete', lambda: s.full(t,t+h)),
                ('no_event_overlap', lambda: not any(t<b and a<t+h for a,b in self.intervals.get((m,kind),[]))),
                ('no_future_surge', lambda: self.control_eligible(m,t,kind)),
                ('no_control_overlap', lambda: not any(md==mode and kd==kind and mm==m and abs(tt-t)<h for md,kd,mm,tt in self.used)),
            )
            for stage,predicate in checks:
                if not predicate():
                    failures[stage] += 1
                    break
                counts[stage] += 1
        chosen,reason = super().match(event,mode)
        counts['selected'] = int(chosen is not None)
        assert counts['selected'] == int(counts['no_control_overlap'] > 0)
        self.matching_diagnostics.setdefault(event['event_id'],{})[mode] = dict(
            passed=counts, first_failure=dict(failures), unmatched_reason=reason,
            case_liquidity=base, case_liquidity_quality=self.panel[market].coverage(ts-360*60,ts-240*60),
            note='Exhaustive sequential first-failure audit in production filter order; candidate-event pairs, not unique coins')
        return chosen,reason


def select_sample(path):
    """Quality-only daily inventory across DB; event mining only on selected 40."""
    with closing(v2.open_readonly(path)) as db:
        rows = db.execute('SELECT market,(ts+32400)/86400 day,COUNT(*) FROM minute_candles GROUP BY market,day')
        daily = defaultdict(dict)
        for market,day,n in rows:
            daily[market][day] = n
    days = [d for counts in daily.values() for d in counts]
    choices = []
    for first in range(min(days),max(days)-4):
        eligible = []
        for m,counts in daily.items():
            values = [counts.get(d,0) for d in range(first,first+5)]
            average,minimum = sum(values)/7200,min(values)/1440
            if average >= .5 and minimum >= .3:
                eligible.append((average,m,minimum))
        eligible.sort(reverse=True)
        pool = eligible[:80]
        if len(pool)>=40:
            choices.append((statistics.fmean(x[0] for x in pool),first,pool))
    if not choices:
        raise ValueError('No 5-day window with 40 eligible markets; do not silently expand scope')
    score,day,pool = max(choices,key=lambda x:(x[0],-x[1]))
    # Systematic sampling across coverage ranks, not just the most liquid 40.
    selected = [pool[round(i*(len(pool)-1)/39)] for i in range(40)]
    start = day*86400-32400
    return dict(markets=sorted(x[1] for x in selected),start=start,end=start+5*86400,
        selection='5 KST days; average coverage>=50%, each day>=30%; best mean coverage among up to top80 eligible; 40 systematic coverage-rank samples; no return screening',
        bias='Quality-selected, favors active assets; not a random or historically complete market sample',
        pool_size=len(pool),pool_mean_coverage=score,
        market_quality=[dict(market=m,coverage=c,min_daily_coverage=d) for c,m,d in selected],
        windows_considered=[dict(start=v2.iso(d*86400-32400),pool_size=len(p),score=s) for s,d,p in choices])


def null_reason(s, ts, key, research, market):
    """Report actual missing inputs, without substituting zero or changing features."""
    if key.startswith('return_'):
        m=int(key.split('_')[1][:-1])
        return 'missing exact close: '+','.join(v2.iso(t) for t in (ts,ts-m*60) if s.price(t) is None)
    windows = {
        'trade_value_5m':[(5,0)], 'prior_mean_trade_value_5m':[(65,5)],
        'trade_value_ratio':[(5,0),(65,5)], 'trade_value_change_pct':[(5,0),(10,5)],
        'trade_value_acceleration':[(5,0),(10,5),(15,10)],
        'ma5':[(5,0)], 'ma20':[(20,0)], 'ma5_ma20_ratio':[(5,0),(20,0)],
        'ma20_slope_5m_pct':[(20,0),(25,5)], 'range_30m_pct':[(30,0)],
        'range_change_pct':[(30,0),(60,30)], 'distance_to_prior_high_pct':[(61,1)],
    }
    if key in windows:
        missing=[]
        for a,b in windows[key]:
            q=s.coverage(ts-a*60,ts-b*60)
            if q['observed_minutes']!=q['expected_minutes']:
                missing.append(f'{a}..{b}m: {q["observed_minutes"]}/{q["expected_minutes"]} candles')
        if key=='distance_to_prior_high_pct' and s.price(ts) is None:
            missing.append('missing current close')
        return '; '.join(missing) or 'zero denominator / zero trade-value input'
    if key=='alt_relative_60m_pct':
        f=research.snapshot(market,ts)
        return 'own 60m return missing' if s.return_at(ts,60) is None else f'only {f["quality"]["relative_peer_count"]} peers; need 3'
    if key=='btc_relative_60m_pct':
        return 'own 60m return missing' if s.return_at(ts,60) is None else 'BTC exact endpoint missing or no BTC DB'
    return 'missing prerequisite'


def audit_records(report,panel,btc,start,end):
    events=report['events']
    research=v2.Research(panel,events,start,end,btc)
    groups=defaultdict(list)
    for e in events:
        groups[e['episode_id']].append(e)
    episodes=[]
    invariant_failures=[]
    for eid,es in groups.items():
        first=min(es,key=lambda e:(e['t0'],e['definition']))
        finish=max(e['end_ts'] for e in es)
        s=panel[first['market']]
        a,b=s.bounds(first['t0'],finish)
        episodes.append(dict(episode_id=eid,market=first['market'],start=first['t0'],end=finish,
            A=sum(e['definition']=='A' for e in es),B=sum(e['definition']=='B' for e in es),
            rise_from_first_t0_pct=v2.pct(max(s.high[a:b]),first['base_price']),
            event_ids=[e['event_id'] for e in sorted(es,key=lambda e:(e['t0'],e['definition']))]))
    for e in events:
        s=panel[e['market']]
        lo=e['first_hit_known_ts']-e['horizon_minutes']*60
        # Inclusive left boundary, completed candles strictly before the hit candle.
        from bisect import bisect_left,bisect_right
        a=bisect_left(s.times,lo); b=bisect_right(s.times,e['first_hit_bar_ts'])
        i=min(range(a,b),key=lambda i:(s.close[i],-s.times[i]))
        if s.times[i]!=e['t0']:
            invariant_failures.append(dict(event_id=e['event_id'],market=e['market'],
                actual_t0=e['t0'],unrestricted_trailing_min_t0=s.times[i],
                actual_price=e['base_price'],unrestricted_price=s.close[i]))
    # Ten unique episodes: prioritize distinct markets, then multi-A and duration.
    ranked=sorted(episodes,key=lambda ep:(-int(ep['A']>1),-(ep['end']-ep['start']),ep['start'],ep['market']))
    chosen=[]; seen=set()
    for ep in ranked:
        if ep['market'] not in seen and len(chosen)<10:
            chosen.append(ep);seen.add(ep['market'])
    for ep in ranked:
        if len(chosen)>=10:break
        if ep not in chosen:chosen.append(ep)
    cases=[]; feature_missing=Counter(); feature_total=Counter(); leakage_checks=0
    for ep in chosen:
        es=sorted(groups[ep['episode_id']],key=lambda e:(e['t0'],e['definition']))
        e=es[0];s=panel[e['market']];ts=e['t0']
        a,b=s.bounds(ts-121*60,ts-60)
        points=[]
        for offset in (-120,-60,-30,-15,-5,0,5,15,30,60):
            price=s.price(ts+offset*60)
            points.append(dict(offset=offset,time=ts+offset*60,price=price,return_pct=v2.pct(price,e['base_price'])))
        j=bisect_left(s.times,e['first_hit_known_ts'])
        target_high=s.high[j]
        features=[]
        for offset in (120,60,30,15,5):
            t=ts-offset*60
            f=research.snapshot(e['market'],t)
            reasons={k:null_reason(s,t,k,research,e['market']) for k,v in f['values'].items() if v is None}
            for k,v in f['values'].items():
                feature_total[k]+=1
                if v is None:feature_missing[k]+=1
            features.append(dict(offset=offset,snapshot=f,null_reasons=reasons))
            # Real-data truncation: reconstruct just candles available at the cutoff.
            n=bisect_right(s.times,t)
            truncated=v2.Series((s.times[i]-60,s.close[i],s.high[i],s.low[i],s.close[i],
                                 s.value_prefix[i+1]-s.value_prefix[i]) for i in range(n))
            before=v2.feature_snapshot(s,t);after=v2.feature_snapshot(truncated,t)
            for k,v in before['values'].items():
                other=after['values'][k]
                assert (v is None and other is None) or (v is not None and other is not None and math.isclose(v,other,rel_tol=1e-9,abs_tol=1e-6)), (k,v,other)
            leakage_checks+=1
        pa,pb=s.bounds(ts,e['end_ts'])
        cases.append(dict(episode=ep,event=e,all_events=[{k:x[k] for k in ('event_id','definition','t0','end_ts','base_price','first_hit_bar_ts','max_rise_pct')} for x in es],
            prior120_low=min(s.low[a:b]) if b>a else None,prior120_min_close=min(s.close[a:b]) if b>a else None,
            prior120_last_close=s.price(ts-60),target_high=target_high,
            post_min_return_pct=v2.pct(min(s.low[pa:pb]),e['base_price']),
            end_close=s.price(e['end_ts']),end_return_pct=v2.pct(s.price(e['end_ts']),e['base_price']),
            target_return_pct=v2.pct(target_high,e['base_price']),points=points,features=features))
    totals={}
    for kind in ('A','B'):
        es=[e for e in events if e['definition']==kind]
        totals[kind]=dict(events=len(es))
        for mode in ('primary','auxiliary'):
            counts=Counter();failures=Counter();reasons=Counter()
            for e in es:
                d=e['matching_diagnostics'][mode]
                counts.update(d['passed']);failures.update(d['first_failure'])
                if e['unmatched_reasons'][mode]:reasons[e['unmatched_reasons'][mode]]+=1
            matched=sum(e['controls'][mode] is not None for e in es)
            totals[kind][mode]=dict(matched=matched,rate_pct=100*matched/len(es) if es else None,
                funnel=dict(counts),first_failures=dict(failures),unmatched_events=dict(reasons))
    # Explicit alternative sampling unit: first chronological event per episode/type.
    representatives=[]
    for es in groups.values():
        for kind in ('A','B'):
            subset=[e for e in es if e['definition']==kind]
            if subset:representatives.append(min(subset,key=lambda e:e['t0']))
    return dict(totals=totals,episodes=sorted(episodes,key=lambda e:(e['start'],e['market'])),
        partial_future_events=sum(e['quality']['coverage']<1 for e in events),
        incomplete_first_hit_windows=sum(not e['quality']['first_hit_window_complete'] for e in events),
        mixed_episodes=sum(ep['A']>0 and ep['B']>0 for ep in episodes),
        multi_A_episodes=sum(ep['A']>1 for ep in episodes),
        t0_invariant_failures=invariant_failures,cases=cases,real_truncation_checks=leakage_checks,
        feature_missing=dict(feature_missing),feature_total=dict(feature_total),
        episode_statistics=v2.summarize(representatives),
        episode_statistics_policy='First chronological event per episode and type, preserving its original controls; not rematched; A/B must not be summed')


def kst(ts):
    return datetime.fromtimestamp(ts,timezone(timedelta(hours=9))).strftime('%m-%d %H:%M')


def cell(x):
    return 'NULL' if x is None else f'{x:.3f}' if isinstance(x,float) else str(x)


def table(headers,rows):
    return ['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+[
        '| '+' | '.join(cell(x) for x in row)+' |' for row in rows]


def render_audit(audit):
    sample= audit['sample'];a=audit['audit']
    lines=['# V2 중간 규모 데이터 검증','',f"종목 {len(sample['markets'])}개 / KST {kst(sample['start'])} ~ {kst(sample['end'])}",'',
        '선정: 가격 상승률을 보지 않고 일별 분봉 관측률로 5일 구간과 40종목을 결정했습니다. 유동적인 종목에 치우친 품질 표본이며 시장 무작위 표본은 아닙니다.',
        '매칭 조건과 이벤트 알고리즘은 변경하지 않았습니다. 전체 DB 조회는 일별 개수 집계뿐이며 이벤트 분석은 선정된 40종목에만 수행했습니다.',
        '',', '.join(sample['markets']),'','## 요약','']
    lines+=table(['유형','사건','주 매칭','주 %','보조 매칭','보조 %'],[
        [k,t['events'],t['primary']['matched'],t['primary']['rate_pct'],t['auxiliary']['matched'],t['auxiliary']['rate_pct']] for k,t in a['totals'].items()])
    lines += ['',f"고유 episode {len(a['episodes'])} / A+B 혼합 {a['mixed_episodes']} / A 여러 개 {a['multi_A_episodes']}",
        f"제약 없는 과거 최저 종가 정의와 t0가 다른 사건: {len(a['t0_invariant_failures'])}",
        f"미래 창 일부 누락 사건 {a['partial_future_events']} / 최초 목표 도달 이전 일부 누락 {a['incomplete_first_hit_windows']}. 누락 구간의 더 이른 목표 도달이나 최고가는 배제할 수 없습니다.",
        f"실제 데이터 미래 제거 검증 {a['real_truncation_checks']}개 통과",'',
        '## 매칭 필터별 통과 수','',
        '후보 수는 사건×대조 후보 조합 수입니다. 순차 필터의 첫 탈락 원인으로 집계하므로 원인 비중은 필터 순서에 의존합니다. 모든 후보를 검사한 수이며, 실제 선택은 원본 V2의 순위와 재사용 규칙을 그대로 따릅니다. case_liquidity는 사건 자체의 과거 기준 거래대금입니다.','']
    for kind,t in a['totals'].items():
        for mode in ('primary','auxiliary'):
            d=t[mode]
            lines += [f'### {kind} / {mode}','']+table(['단계','통과 후보','해당 단계 탈락'],[[s,d['funnel'].get(s,0),d['first_failures'].get(s,0)] for s in STAGES])
            lines+=['', '미매칭 사건 사유: '+json.dumps(d['unmatched_events'],ensure_ascii=False),'']
    if (audit.get('previous_smoke') or {}).get('summary'):
        lines+=['## 기존 8종목 0건 원인 재검증','', '저장된 사건을 그대로 사용해 매칭 진단만 수행했습니다. 기존 주/보조 대조군 ID와 모두 일치했습니다.','']
        for kind,modes in audit['previous_smoke']['summary'].items():
            lines += [f'### 기존 {kind} 주 대조군','']+table(['단계','통과','탈락'],[[s,modes['primary']['passed'].get(s,0),modes['primary']['first_failures'].get(s,0)] for s in STAGES])
    lines+=['## 모든 episode','', '상승폭은 episode의 첫 t0 가격 대비 병합 구간의 관측 최고가입니다. 구간 중첩의 전이적 연결이므로 여러 번의 상승·하락을 한 episode로 합칠 수 있습니다.','']
    lines += ['A는 60분 평가 창 종료 후 5% 되돌림이 확인되면 다시 생성됩니다. B의 360분 창 안에 이 A 사건들이 여러 개 들어갈 수 있어 동일 episode에 A가 여러 건 포함됩니다. 연결된 평가 창은 실제 가격 흐름의 자연스러운 구분을 보장하지 않습니다.','']
    lines+=table(['episode_id','종목','A','B','시작 KST','종료 KST','상승폭 %'],[[e['episode_id'],e['market'],e['A'],e['B'],kst(e['start']),kst(e['end']),e['rise_from_first_t0_pct']] for e in a['episodes']])
    lines+=['','## 대표 사례 10개','', '종목 다양성을 우선하고 다중 A/긴 episode를 포함한 진단용 사례입니다. 각 episode의 첫 event를 대표로 사용합니다. 모든 시각은 KST, 목표 도달은 관측 분봉 고가 기준입니다.','']
    for n,c in enumerate(a['cases'],1):
        e=c['event']
        lines += [f"### {n}. {e['market']} / {e['definition']} / {e['episode_id']}",'',
            f"t0 {kst(e['t0'])}, 가격 {e['base_price']}; 목표 {kst(e['first_hit_bar_ts'])}, 고가 {c['target_high']}; 최대 상승 {e['max_rise_pct']:.3f}%; 도달 {e['minutes_to_target_lower']}~{e['minutes_to_target_upper']}분.",
            f"직전 120분 관측 최저가 {c['prior120_low']}, 최저 종가 {c['prior120_min_close']}, t0 1분 전 종가 {c['prior120_last_close']}.",'']
        lines += [f"t0 이후 평가 창 최저가 수익률 {c['post_min_return_pct']:.3f}%, 종료 종가 {cell(c['end_close'])}, 종료 수익률 {cell(c['end_return_pct'])}%. 구간 관측률 {e['quality']['coverage']:.3f}.",'']
        lines+=table(['t0 상대 분','KST','확정 종가','t0 대비 %'],[[p['offset'],kst(p['time']),p['price'],p['return_pct']] for p in c['points']]+[['목표 도달 봉 고가',kst(e['first_hit_bar_ts']),c['target_high'],c['target_return_pct']]])
        lines+=['','가격 흐름과 중복 event 목록:','']+table(['유형','t0','기준 가격','목표 도달','평가 종료','최대 상승 %'],[[x['definition'],kst(x['t0']),x['base_price'],kst(x['first_hit_bar_ts']),kst(x['end_ts']),x['max_rise_pct']] for x in c['all_events']])
        lines+=['','사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):','']
        keys=('return_5m_pct','return_15m_pct','return_30m_pct','return_60m_pct','trade_value_ratio','trade_value_acceleration','ma5','ma20','range_30m_pct','distance_to_prior_high_pct','alt_relative_60m_pct')
        lines+=table(['분 전']+list(keys)+['MA5>MA20','돌파'],[[f['offset']]+[f['snapshot']['values'][k] for k in keys]+[f['snapshot']['flags']['ma5_above_ma20'],f['snapshot']['flags']['prior_high_breakout']] for f in c['features']])
        for f in c['features']:
            if f['null_reasons']:
                lines+=['',f"- {f['offset']}분 전 NULL: "+'; '.join(k+': '+v for k,v in f['null_reasons'].items())]
        lines+=['']
    lines+=['## t0 정의 불일치 목록','', '새 episode를 시작할 때 과거 저점 큐를 비우는 동작은 이전 episode 저점을 재사용하지 않게 하지만, 전체 과거 H분의 최저 종가라는 설명과 달라질 수 있습니다. 아래는 조건을 바꾸지 않고 측정한 차이입니다.','']
    lines+=table(['종목','event_id','현재 t0','전체 창 최저 종가 시각','현재 가격','전체 창 최저 종가'],[[e['market'],e['event_id'],kst(e['actual_t0']),kst(e['unrestricted_trailing_min_t0']),e['actual_price'],e['unrestricted_price']] for e in a['t0_invariant_failures']])
    lines+=['','## 특징별 NULL 수 (대표 10개 × 5시점)','']+table(['특징','NULL','전체'],[[k,a['feature_missing'].get(k,0),n] for k,n in a['feature_total'].items()])
    lines+=['','## 통계 단위','',
        '원본 event 기준 단일 특징 통계는 같은 이름의 research JSON/Markdown에 있습니다. audit JSON의 episode_statistics는 episode·유형별 첫 event 하나만 남긴 별도 집계이며 원래 대조군을 유지합니다. 매칭 유무에 따라 대표를 바꾸지 않습니다. A/B 유형 합산 확률이나 독립 표본 추론은 하지 않습니다.',
        '## 판단','',
        '현재 전체 실행을 연구 결론 산출용으로 권하지 않습니다. 결측으로 인한 표본·대조군 선택 편향, t0의 episode 경계 예외, 전이적 episode 병합과 통계 단위를 먼저 확정해야 합니다. 매칭률을 올리려고 이번 작업에서 조건을 완화하지 않았습니다.', '']
    return '\n'.join(lines)


def digest(path):
    with open(path,'rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def audit_previous_smoke(path, btc_path):
    previous=REPORTS_DIR/'surge_event_research_v2_smoke.json'
    if not previous.exists():
        return None
    report=json.loads(previous.read_text(encoding='utf-8'))
    if len(report['markets'])!=8:
        return dict(skipped='Saved smoke report does not contain 8 markets')
    start,end=map(v2.parse_time,(report['start_utc'],report['end_utc']))
    with closing(v2.open_readonly(path)) as db:
        panel={m:v2.load_series(db,m,start-360*60,end) for m in report['markets']}
    research=AuditedResearch(panel,report['events'],start,end)
    summary={}
    for e in sorted(report['events'],key=lambda e:(e['t0'],e['market'],e['definition'])):
        for mode in ('primary','auxiliary'):
            chosen,reason=research.match(e,mode)
            old=e['controls'][mode]
            assert (chosen['control_id'] if chosen else None)==(old['control_id'] if old else None)
    for kind in ('A','B'):
        es=[e for e in report['events'] if e['definition']==kind]
        summary[kind]={}
        for mode in ('primary','auxiliary'):
            passed=Counter();failures=Counter()
            for e in es:
                d=research.matching_diagnostics[e['event_id']][mode]
                passed.update(d['passed']);failures.update(d['first_failure'])
            summary[kind][mode]=dict(passed=dict(passed),first_failures=dict(failures))
    return dict(events=len(report['events']),unchanged_control_ids=True,summary=summary)


def render_charts(audit,panel):
    parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><title>V2 t0 사례 검증</title>',
           '<style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:24px}svg{width:100%;border:1px solid #ccc}article{margin:32px 0}p{line-height:1.6}</style>',
           '<h1>대표 episode 10개: 관측 종가와 t0</h1><p>시각 KST. 파란 선은 완성 봉 종가이며 누락 분봉에서 끊습니다. 붉은 선은 t0, 녹색 선은 목표 도달 봉 시작, 원은 그 봉의 고가입니다. 음영은 t0 이전입니다. 차트는 상승 원인이나 실시간 탐지 성과를 뜻하지 않습니다.</p>']
    for i,c in enumerate(audit['cases'],1):
        e=c['event'];s=panel[e['market']]
        begin=e['t0']-120*60;end=c['episode']['end']
        a,b=s.bounds(begin-60,end)
        vals=list(s.close[a:b])+[c['target_high']]
        low,high=min(vals),max(vals)
        pad=max((high-low)*.1,high*.005);low-=pad;high+=pad
        x=lambda ts:65+(ts-begin)/(end-begin)*900
        y=lambda price:260-(price-low)/(high-low)*230
        parts += [f'<article><h2>{i}. {html.escape(e["market"])} / {e["definition"]} / {e["episode_id"]}</h2>',
            f'<p>t0 {kst(e["t0"])} · {e["base_price"]} / 목표 {kst(e["first_hit_bar_ts"])} · 고가 {c["target_high"]} / episode A {c["episode"]["A"]}, B {c["episode"]["B"]}</p>',
            '<svg viewBox="0 0 1020 310" role="img" aria-label="t0 전후 가격 차트">',
            f'<rect x="65" y="25" width="{x(e["t0"])-65:.2f}" height="235" fill="#f2f2f2"/>']
        for frac in (0,.25,.5,.75,1):
            price=low+(high-low)*frac;yy=y(price)
            parts += [f'<line x1="65" x2="965" y1="{yy}" y2="{yy}" stroke="#ddd"/><text x="3" y="{yy}" font-size="12">{price:.3g}</text>']
        chunks=[];chunk=[];last=None
        for j in range(a,b):
            if last is not None and s.times[j]-last>60:
                chunks.append(chunk);chunk=[]
            chunk.append(f'{x(s.times[j]):.2f},{y(s.close[j]):.2f}');last=s.times[j]
        chunks.append(chunk)
        for chunk in chunks:
            if chunk:parts.append(f'<polyline points="{" ".join(chunk)}" fill="none" stroke="#1765ad" stroke-width="1.4"/>')
        for ts,color,label in ((e['t0'],'#bd2525','t0'),(e['first_hit_bar_ts'],'#16804a','target')):
            xx=x(ts);parts.append(f'<line x1="{xx}" x2="{xx}" y1="25" y2="260" stroke="{color}"/><text x="{xx+4}" y="18" fill="{color}">{label}</text>')
        parts.append(f'<circle cx="{x(e["first_hit_bar_ts"])}" cy="{y(c["target_high"])}" r="4" fill="#16804a"/>')
        for t in (begin,e['t0'],end):
            parts.append(f'<text x="{x(t)}" y="290" text-anchor="middle" font-size="12">{kst(t)}</text>')
        parts.append('</svg></article>')
    return '\n'.join(parts)+ '</html>'


def main():
    path=DATA_DIR/'altcoin_market.db';btc_path=DATA_DIR/'historical_market.db'
    before={str(p):digest(p) for p in (path,btc_path)}
    sample=select_sample(path)
    print('SELECTED',sample['markets'],v2.iso(sample['start']),v2.iso(sample['end']),flush=True)
    report=v2.run_research(path,sample['markets'],sample['start'],sample['end'],btc_path=btc_path,research_class=AuditedResearch)
    with closing(v2.open_readonly(path)) as db:
        panel={m:v2.load_series(db,m,sample['start']-360*60,sample['end']) for m in sample['markets']}
    with closing(v2.open_readonly(btc_path)) as db:
        btc=v2.load_series(db,'KRW-BTC',sample['start']-360*60,sample['end'])
    audit=audit_records(report,panel,btc,sample['start'],sample['end'])
    previous=audit_previous_smoke(path,btc_path)
    after={str(p):digest(p) for p in (path,btc_path)}
    assert before==after,'Source DB hash changed'
    output=dict(sample=sample,audit=audit,previous_smoke=previous,source_hashes_before=before,source_hashes_after=after)
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR/'surge_event_v2_medium_audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (REPORTS_DIR/'surge_event_v2_medium_audit.md').write_text(render_audit(output),encoding='utf-8')
    (REPORTS_DIR/'surge_event_v2_medium_research.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (REPORTS_DIR/'surge_event_v2_medium_research.md').write_text(v2.render(report),encoding='utf-8')
    (REPORTS_DIR/'surge_event_v2_medium_charts.html').write_text(render_charts(audit,panel),encoding='utf-8')
    print('AUDIT',json.dumps(dict(totals=audit['totals'],episodes=len(audit['episodes']),mixed=audit['mixed_episodes'],multi_A=audit['multi_A_episodes'],t0_mismatches=len(audit['t0_invariant_failures'])),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
