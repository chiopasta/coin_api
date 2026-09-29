"""Describe stored matched snapshots only. No DB, API, new features or thresholds."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics as st

from .paths import REPORTS_DIR

OFFSETS=(120,60,30,15,5)


def med(xs):return st.median(xs) if xs else None
def mean(xs):return st.fmean(xs) if xs else None
def diff(a,b):return a-b if a is not None and b is not None else None


def summarize(events,minimum):
    continuous=[];flags=[]
    for offset in OFFSETS:
        for section,destination in [('values',continuous),('flags',flags)]:
            keys=list(events[0]['snapshots'][str(offset)][section]) if events else []
            for key in keys:
                pairs=[(e['snapshots'][str(offset)][section][key],e['controls']['primary']['snapshots'][str(offset)][section][key]) for e in events]
                ev=[a for a,b in pairs if a is not None];cv=[b for a,b in pairs if b is not None]
                paired=[(a,b) for a,b in pairs if a is not None and b is not None]
                x=[a for a,b in paired];y=[b for a,b in paired]
                row=dict(feature=key,offset=offset,total_pairs=len(events),valid_event_count=len(ev),valid_control_count=len(cv),paired_valid_count=len(paired),
                         event_median=med(ev),control_median=med(cv),median_difference=diff(med(ev),med(cv)),event_mean=mean(ev),control_mean=mean(cv),
                         paired_event_median=med(x),paired_control_median=med(y),paired_median_difference=diff(med(x),med(y)),
                         median_of_pair_differences=med([a-b for a,b in paired]),paired_event_mean=mean(x),paired_control_mean=mean(y),
                         status='SUFFICIENT_FOR_DESCRIPTION' if min(len(ev),len(cv),len(paired))>=minimum else 'INSUFFICIENT_SAMPLE')
                if section=='flags':
                    row.update(event_rate_pct=100*mean(x) if x else None,control_rate_pct=100*mean(y) if y else None,
                               difference_pp=100*(mean(x)-mean(y)) if x else None,
                               event_true_count=sum(x),control_true_count=sum(y))
                destination.append(row)
    return dict(events=len(events),continuous=continuous,flags=flags)


def build(source):
    minimum=max(20,source.get('min_valid',20))
    output=dict(min_valid=minimum,offsets=list(OFFSETS),method='Only representative, observation-eligible events with primary controls; stored snapshots unchanged. Main comparisons use pairwise complete observations. Separate marginal counts/means also retained. No imputation.',groups={})
    for kind in ('A','B'):
        es=sorted((e for e in source['events'] if e['definition']==kind and e['is_representative'] and e['observation_policy']['eligible'] and e['controls']['primary']),key=lambda e:(e['target_time'],e['t0'],e['event_id']))
        group=summarize(es,minimum)
        counts=Counter(e['market'] for e in es)
        first={}
        for e in es:first.setdefault(e['market'],e)
        group['market_counts']=dict(counts.most_common())
        group['market_count']=len(counts)
        group['largest_market_share_pct']=100*max(counts.values())/len(es) if es else None
        group['top3_share_pct']=100*sum(n for m,n in counts.most_common(3))/len(es) if es else None
        group['event_ids']=[e['event_id'] for e in es]
        group['one_per_market']=summarize(list(first.values()),minimum)
        group['one_per_market']['selection']='Earliest target_time event per market, retaining original matched control; never choose by feature/result.'
        group['one_per_market']['event_ids']=[e['event_id'] for e in first.values()]
        group['without_largest_market']=summarize([e for e in es if e['market']!=counts.most_common(1)[0][0]],minimum) if es else None
        group['largest_existing_flag_differences']=sorted((r for r in group['flags'] if r['status']=='SUFFICIENT_FOR_DESCRIPTION'),key=lambda r:-abs(r['difference_pp']))
        group['continuous_candidates_by_feature']={key:max((r for r in group['continuous'] if r['feature']==key and r['status']=='SUFFICIENT_FOR_DESCRIPTION'),key=lambda r:abs(r['paired_median_difference']),default=None) for key in {r['feature'] for r in group['continuous']}}
        output['groups'][kind]=group
    # Cross-check rates against the already produced research table.
    for kind,g in output['groups'].items():
        for row in g['flags']:
            previous=next(x for x in source['statistics'] if x['definition']==kind and x['control_type']=='primary' and x['feature']==row['feature'] and x['offset_minutes']==row['offset'])
            assert previous['paired_valid_count']==row['paired_valid_count']
            if row['difference_pp'] is not None:assert abs(previous['difference_pp_reference']-row['difference_pp'])<1e-8
    return output


def interpretation(result):
    a=result['groups']['A']
    rows={(r['feature'],r['offset']):r for r in a['continuous']}
    selected=[('range_30m_pct',15,'최근 30분 고저폭','더 큼'),
              ('distance_to_prior_high_pct',5,'직전 60분 고점까지 거리','고점보다 더 아래'),
              ('ma20_slope_5m_pct',5,'MA20의 5분 기울기','더 하락')]
    candidates=[dict(rows[(key,offset)],label=label,direction=direction) for key,offset,label,direction in selected
                if rows[(key,offset)]['status']=='SUFFICIENT_FOR_DESCRIPTION']
    texts={
        120:'이미 고저폭이 더 컸습니다. 알트 대비 상대강도는 급등군 쪽이 높았지만 이후까지 같은 방향이 유지되지는 않았습니다.',
        60:'높은 고저폭은 유지됐지만 상대강도와 MA 기울기는 오히려 약했습니다. 상승 준비 신호가 순서대로 강해졌다는 모습은 아닙니다.',
        30:'MA5 > MA20 발생률은 일시적으로 높았지만, 60분 수익률은 control보다 낮았습니다. 거래대금 2배 조건도 우세하지 않았습니다.',
        15:'고저폭과 고점에서 떨어진 정도가 컸습니다. 거래대금 배율 중앙값은 비슷하며, 단기 MA 우위는 다시 약해졌습니다.',
        5:'기준 저점에 가까워지며 가격 수익률과 MA 기울기가 더 약했습니다. 고점 돌파는 양쪽 모두 관측되지 않았고 거래대금 배율 중앙값 차이도 작았습니다.'}
    return dict(verdict='WEAK',timeline=texts,candidates=candidates,
                promising=['모든 시점에서 큰 최근 30분 고저폭','직전 고점보다 아래에 위치하는 큰 가격 이격','t0 직전의 약한 수익률·MA 기울기(사후 저점 정의 영향 주의)'],
                little_difference=['거래대금 배율 중앙값: 일관된 증가 우위 없음','고점 돌파 발생률: 낮거나 동일','알트/BTC 상대강도: 120분 전 우위가 이후 지속되지 않음'],
                undetermined=['여러 시장으로 일반화 가능한가','시장당 첫 사건 9개로도 재현되는가','B 15건에서 같은 패턴인가','실시간으로 관측 가능한 예측 신호인가'],
                conclusion='WEAK — 더 큰 고저폭과 고점 대비 하락은 반복되지만, 시장 쏠림과 사후 저점 정의의 영향 때문에 일반적인 급등 전조로 확정하기 어렵습니다.')


def reader_summary(result):
    a=result['groups']['A'];interp=result['interpretation']
    by={(r['feature'],r['offset']):r for r in a['continuous']}
    lines=['# 53건의 급등 전에 무엇이 달랐나?','',
           '**요약: 급등군은 이미 가격 움직임이 컸고, 직전 고점보다 더 내려와 있었습니다. 거래대금 증가 → 모멘텀 강화 → 돌파라는 일정한 순서는 보이지 않았습니다.**','',
           f"A {a['events']}건은 {a['market_count']}개 시장에서 발생했습니다. FLOCK {a['market_counts'].get('KRW-FLOCK',0)}건({a['largest_market_share_pct']:.2f}%), 상위 3개 {a['top3_share_pct']:.2f}%로 쏠려 있습니다.",
           '아래는 결측이 양쪽 모두 없는 matched pair의 중앙값이며, 시점마다 유효 pair 집합이 다릅니다.','']
    for offset in OFFSETS:
        lines += [f'### 급등 {offset}분 전','',interp['timeline'][offset],'']
        keys=['range_30m_pct','distance_to_prior_high_pct','alt_relative_60m_pct','trade_value_ratio']
        labels=['최근 30분 고저폭(%)','직전 고점까지 거리(%)','알트 대비 60분 상대강도(%p)','거래대금 배율(배)']
        lines+=table(['특징','급등군 중앙값','control 중앙값','차이','유효 pair'],[
            [label,by[(k,offset)]['paired_event_median'],by[(k,offset)]['paired_control_median'],by[(k,offset)]['paired_median_difference'],by[(k,offset)]['paired_valid_count']] for k,label in zip(keys,labels)])
    lines+=['','### 현재 가장 유망해 보이는 특징','',
            '이는 매수 신호가 아니라 추가 확인할 기술적 차이 후보입니다.','']
    lines+=table(['특징','시점','event','control','차이','유효 E/C','paired N','방향'],[
        [r['label'],r['offset'],r['paired_event_median'],r['paired_control_median'],r['paired_median_difference'],f"{r['valid_event_count']}/{r['valid_control_count']}",r['paired_valid_count'],r['direction']] for r in interp['candidates']])
    lines+=['','### 별 차이가 없었던 특징','']+['- '+s for s in interp['little_difference']]
    lines+=['','### 아직 판단할 수 없는 특징','']+['- '+s for s in interp['undetermined']]
    lines+=['','### 특정 사건·시장 의존성','',
            '시장당 최초 사건 1개만 남기면 A는 9쌍입니다. 고저폭 차이는 5개 시점 모두 같은 방향이지만 유효 pair가 5~7개라 INSUFFICIENT_SAMPLE입니다.',
            'FLOCK을 전부 제외하면 28쌍입니다. 5분 전 고저폭 차이는 +4.14%p(유효 20쌍)로 남습니다. 한 시장만의 현상은 아니지만 시장 중립적 전조임을 입증하지는 않습니다.',
            '5분 전 거래대금 배율은 평균 1.40배 vs 0.69배지만 중앙값은 0.54배 vs 0.50배입니다. 평균만 보고 전반적 거래대금 폭증이라고 해석하면 안 됩니다.',
            '큰 고저폭이 이미 120분 전부터 관측된 점은 종목의 평소 변동성 차이일 수도 있습니다. t0는 사후 저점이므로 직전 하락 역시 기준점 선정의 영향을 받을 수 있습니다.','',
            '### B는 참고용','',
            '15쌍, 5개 시장뿐이며 모든 비교가 INSUFFICIENT_SAMPLE입니다. 아래 상세 표의 수치는 참고용이며 A와 같은 결론이라고 단정하지 않습니다.','',
            '### 최종 답변','',interp['conclusion'],'','---','']
    return lines


def fmt(x):return 'NULL' if x is None else f'{x:.4g}' if isinstance(x,float) else str(x)


def table(headers,rows):
    return ['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(fmt(x) for x in row)+' |' for row in rows]


def render(result):
    lines=reader_summary(result)+['# 상세 수치: 기존 matched snapshots 비교','',
           'A 53쌍을 중심으로 기존 snapshot만 비교한다. B 15쌍은 INSUFFICIENT_SAMPLE 참고자료다.',
           '차이는 모두 event-control. 수익률/고저폭/거리/기울기는 % 단위이므로 차이는 %p, 거래대금은 KRW, 배율은 배수다.',
           '유효 event/control 수는 각 군별 결측 제외 수다. 해석은 양쪽 모두 유효한 matched pair의 중앙값을 우선한다.',
           '두 군 중앙값의 차이와 쌍별 차이의 중앙값은 다르므로 둘 다 JSON에 저장했다. False/0은 유효값이다.',
           '단위가 다른 연속형 값을 하나의 점수로 정렬하지 않는다. 기존 boolean 조건은 발생률 차이(%p)로만 정렬한다.',
           'min-valid는 paired count까지 20 이상이어야 한다. 통계적 유의성 검정/예측성 검증을 뜻하지 않는다.','']
    for kind,g in result['groups'].items():
        lines += [f'## {kind}: {g["events"]}쌍','',f"발생 시장 {g['market_count']}개. 최대 시장 비중 {g['largest_market_share_pct']:.2f}%, 상위3개 {g['top3_share_pct']:.2f}%.",'']
        lines+=table(['market','events'],g['market_counts'].items())
        for offset in OFFSETS:
            rows=[r for r in g['continuous'] if r['offset']==offset]
            lines += ['',f'### t0 -{offset}분: 연속형','']
            lines+=table(['feature','유효 E/C','paired N','E 중앙값','C 중앙값','차이','E 평균','C 평균','paired E 중앙값','paired C 중앙값','paired 차이','상태'],[
                [r['feature'],f"{r['valid_event_count']}/{r['valid_control_count']}",r['paired_valid_count'],r['event_median'],r['control_median'],r['median_difference'],r['event_mean'],r['control_mean'],r['paired_event_median'],r['paired_control_median'],r['paired_median_difference'],r['status']] for r in rows])
            lines+=['','기존 threshold 발생률(양쪽 유효한 pair만):','']
            lines+=table(['기존 flag','유효 E/C','paired N','E %','C %','차이 %p','상태'],[
                [r['feature'],f"{r['valid_event_count']}/{r['valid_control_count']}",r['paired_valid_count'],r['event_rate_pct'],r['control_rate_pct'],r['difference_pp'],r['status']] for r in g['flags'] if r['offset']==offset])
        lines += ['','### 시장당 첫 사건 1개 sensitivity','',g['one_per_market']['selection'],
                  f"{g['one_per_market']['events']}쌍이므로 모두 표본 부족. 아래 수치는 방향 확인용이며 독립적인 확인 증거가 아니다.",'']
        keys=('return_60m_pct','trade_value_ratio','trade_value_acceleration','range_30m_pct','alt_relative_60m_pct','btc_relative_60m_pct')
        lines+=table(['feature','시점','paired N','E 중앙값','C 중앙값','차이'],[
            [r['feature'],r['offset'],r['paired_valid_count'],r['paired_event_median'],r['paired_control_median'],r['paired_median_difference']] for r in g['one_per_market']['continuous'] if r['feature'] in keys])
    lines += ['','## A: 차이가 큰 기존 조건 (표본 20 이상)','']
    lines+=table(['flag','시점','paired N','event %','control %','차이 %p'],[
        [r['feature'],r['offset'],r['paired_valid_count'],r['event_rate_pct'],r['control_rate_pct'],r['difference_pp']] for r in result['groups']['A']['largest_existing_flag_differences'][:15]])
    lines+=['','## 해석의 한계','',
            '- t0는 미래 목표 도달을 보고 정한 사후 저점이다. t0에 가까운 하락/고점 이격은 이 정의의 영향을 받을 수 있다.',
            '- 같은 시각 control과 비교했으나 시장별 기질·유동성·변동성 차이와 특정 시장 쏠림이 남는다.',
            '- offset별 유효 pair 집합이 다르므로 시점별 숫자 변화가 동일 사건의 일관된 경로임을 뜻하지 않는다.',
            '- 결측이 무작위라는 보장이 없다. 적은 paired N의 비교는 전체 53건으로 일반화하지 않는다.',
            '- 여러 feature·시점을 기술적으로 비교했으며 p-value나 유의성, 미래 매수 성과를 주장하지 않는다.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=REPORTS_DIR/'research_market_v1_analysis.json')
    p.add_argument('--output',type=Path,default=REPORTS_DIR/'research_market_v1_pattern_summary')
    a=p.parse_args();raw=a.input.read_bytes();result=build(json.loads(raw))
    result['interpretation']=interpretation(result)
    result['source']=str(a.input);result['source_sha256']=hashlib.sha256(raw).hexdigest()
    a.output.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    a.output.with_suffix('.md').write_text(render(result),encoding='utf-8')
    print(json.dumps({k:dict(events=g['events'],market_counts=g['market_counts'],top=g['largest_existing_flag_differences'][:6]) for k,g in result['groups'].items()},indent=2))


if __name__=='__main__':main()
