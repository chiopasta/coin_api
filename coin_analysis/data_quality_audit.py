"""Small offline inventory of minute-candle availability; no event research/network."""

import csv
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from .paths import DATA_DIR, REPORTS_DIR

KST = timezone(timedelta(hours=9))
THRESHOLDS = (.8, .9, .95, 1.)


def day_of(ts):
    return (ts+32400)//86400


def day_start(day):
    return day*86400-32400


def label(day):
    return datetime.fromtimestamp(day_start(day),KST).strftime('%Y-%m-%d')


def stamp(ts):
    return datetime.fromtimestamp(ts,KST).isoformat()


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def inventory(db):
    result={}
    for market,ts in db.execute('SELECT market,ts FROM minute_candles ORDER BY market,ts'):
        if ts%60:raise ValueError(f'Unaligned timestamp: {market} {ts}')
        if market not in result:
            result[market]=dict(first_ts=ts,last_ts=ts,count=0,daily=Counter(),
                longest_run_minutes=0,longest_run_start=ts,longest_run_end=ts+60,
                longest_gap_minutes=0,gap_count=0,run_start=ts,run_length=0)
        r=result[market]
        if r['count'] and ts<=r['last_ts']:raise ValueError('Duplicate or unordered timestamp')
        if r['count'] and ts!=r['last_ts']+60:
            r['gap_count']+=1
            r['longest_gap_minutes']=max(r['longest_gap_minutes'],(ts-r['last_ts'])//60-1)
            r['run_start']=ts;r['run_length']=0
        r['run_length']+=1
        if r['run_length']>r['longest_run_minutes']:
            r['longest_run_minutes']=r['run_length'];r['longest_run_start']=r['run_start'];r['longest_run_end']=ts+60
        r['last_ts']=ts;r['count']+=1;r['daily'][day_of(ts)]+=1
    for r in result.values():
        r.pop('run_start');r.pop('run_length')
    return result


def windows(markets,full_days):
    rows=[]
    for length in (3,5,7):
        for start in full_days:
            days=list(range(start,start+length))
            if days[-1] not in full_days:continue
            for threshold in THRESHOLDS:
                eligible=[m for m,r in markets.items() if all(r['daily'].get(d,0)/1440>=threshold for d in days)]
                values=[markets[m]['daily'].get(d,0)/1440 for m in eligible for d in days]
                rows.append(dict(days=length,threshold=threshold,start_day=start,end_day=start+length,
                    start=label(start),end_exclusive=label(start+length),markets=eligible,
                    market_count=len(eligible),mean_coverage=sum(values)/len(values) if values else None,
                    minimum_daily_coverage=min(values) if values else None,
                    candle_count=sum(markets[m]['daily'].get(d,0) for m in eligible for d in days)))
    return rows


def best_window(rows,threshold,length):
    choices=[r for r in rows if r['threshold']==threshold and r['days']==length]
    return max(choices,key=lambda r:(r['market_count'],r['mean_coverage'] or 0,-r['start_day']))


def gap_lengths(timestamps,start,end):
    previous=start-60
    for ts in timestamps:
        n=(ts-previous)//60-1
        if n>0:yield n
        previous=ts
    n=(end-previous)//60-1
    if n>0:yield n


def supplementation(db,markets,full_days,length,target=100,threshold=.9):
    plans=[]
    required=math.ceil(1440*threshold)
    for start in full_days:
        days=list(range(start,start+length))
        if days[-1] not in full_days:continue
        ranked=sorted((sum(max(0,required-r['daily'].get(d,0)) for d in days),m) for m,r in markets.items())[:target]
        plans.append((sum(n for n,m in ranked),start,ranked))
    deficit,start,ranked=min(plans)
    details=[];calls=0;all_gaps=0
    for _,m in ranked:
        for d in range(start,start+length):
            n=markets[m]['daily'].get(d,0);needed=max(0,required-n)
            if not needed:continue
            ts=[r[0] for r in db.execute('SELECT ts FROM minute_candles WHERE market=? AND ts>=? AND ts<? ORDER BY ts',(m,day_start(d),day_start(d+1)))]
            gaps=list(gap_lengths(ts,day_start(d),day_start(d+1)))
            missing=sum(gaps)
            requests=sum(math.ceil(g/200) for g in gaps)
            calls+=requests;all_gaps+=missing
            details.append(dict(market=m,date=label(d),observed=n,coverage=n/1440,
                deficit_to_90pct=needed,unobserved_minutes=missing,gap_count=len(gaps),
                theoretical_gap_page_calls=requests))
    packed_calls=sum(math.ceil(r['deficit_to_90pct']/200) for r in details)
    return dict(target_markets=target,days=length,threshold=threshold,start=label(start),
        end_exclusive=label(start+length),markets=[m for _,m in ranked],minimum_additional_observations=deficit,
        affected_market_days=len(details),affected_markets=len({r['market'] for r in details}),
        affected_dates=sorted({r['date'] for r in details}),
        unobserved_minutes_in_deficient_days=all_gaps,
        ideal_packed_calls=packed_calls,theoretical_all_gap_page_calls=calls,
        ideal_packed_pacing_minutes=packed_calls*.13/60,
        all_gap_pacing_minutes=calls*.13/60,
        all_gap_seconds_05_latency_minutes=calls*(.13+.5)/60,
        assumptions='Hypothetical recoverable observations, 200 candles/call and existing downloader 0.13s pacing. Gap-page estimate inspects all gaps on deficient days, not just threshold deficit. Not a promise of recoverable candles or zero duplicate API responses.',
        details=details)


def csv_write(path,rows):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def mdtable(headers,rows):
    return ['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+[
        '| '+' | '.join('N/A' if v is None else f'{v:.4f}' if isinstance(v,float) else str(v) for v in row)+' |' for row in rows]


def main():
    path=DATA_DIR/'altcoin_market.db';before=sha(path)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        markets=inventory(db)
        first=min(r['first_ts'] for r in markets.values());last=max(r['last_ts'] for r in markets.values())
        days=list(range(day_of(first),day_of(last)+1))
        full_days=[d for d in days if day_start(d)>=first and day_start(d+1)<=last+60]
        daily=[];market_daily=[]
        for d in days:
            counts=[r['daily'].get(d,0) for r in markets.values()]
            daily.append(dict(date=label(d),full_calendar_day_in_global_span=d in full_days,
                markets_with_data=sum(n>0 for n in counts),candles=sum(counts),
                **{f'coverage_{int(t*100)}':sum(n/1440>=t for n in counts) for t in THRESHOLDS}))
            for m,r in markets.items():
                n=r['daily'].get(d,0)
                market_daily.append(dict(market=m,date=label(d),observed_minutes=n,expected_minutes=1440,coverage=n/1440))
        candidates=windows(markets,full_days)
        best=[best_window(candidates,t,n) for t in THRESHOLDS for n in (3,5,7)]
        # Prefer breadth at >=90% among requested 5/7-day datasets; then length.
        recommendation=max([r for r in best if r['threshold']==.9 and r['days'] in (5,7)],
                           key=lambda r:(r['market_count'],r['days'],r['mean_coverage'] or 0))
        if recommendation['market_count']==0:raise ValueError('No recommended cohort at 90%')
        grade_rows=[]
        for m,r in markets.items():
            n=sum(r['daily'].get(d,0) for d in range(recommendation['start_day'],recommendation['end_day']))
            coverage=n/(recommendation['days']*1440)
            grade='GOOD' if coverage>=.95 else 'USABLE' if coverage>=.8 else 'POOR'
            grade_rows.append(dict(market=m,first_timestamp=r['first_ts'],last_timestamp=r['last_ts'],
                first_kst=stamp(r['first_ts']),last_kst=stamp(r['last_ts']),observed_candles=r['count'],
                longest_contiguous_minutes=r['longest_run_minutes'],longest_contiguous_start_kst=stamp(r['longest_run_start']),
                longest_contiguous_end_exclusive_kst=stamp(r['longest_run_end']),
                longest_internal_gap_minutes=r['longest_gap_minutes'],internal_gap_count=r['gap_count'],
                research_period_coverage=coverage,grade=grade,recommended=m in recommendation['markets']))
        need_target=all(r['market_count']<100 for r in best if r['threshold']==.9 and r['days'] in (5,7))
        plans=[supplementation(db,markets,full_days,n) for n in (5,7)] if need_target else []
    after=sha(path);assert before==after
    result=dict(source=str(path),source_hash_before=before,source_hash_after=after,
        market_count=len(markets),candles=sum(r['count'] for r in markets.values()),first_kst=stamp(first),last_kst=stamp(last),
        coverage_definition='KST calendar day, denominator 1440; missing dates are zero observations, not zero-price candles. Consecutive cohort must meet threshold on EVERY day with the SAME markets. Exclude partial boundary days from window selection.',
        gap_definition='Market lifetime gaps between first/last observed candles; boundary time before listing/after last observation is not counted as an internal gap.',
        best_windows=best,recommendation=recommendation,daily=daily,grades=dict(Counter(r['grade'] for r in grade_rows)),
        grade_definition='Temporary data-quality grade on recommended full period average: GOOD>=95%, USABLE>=80%, POOR<80%; not a trading score and not the daily cohort rule.',
        target_100_at_90pct_feasible=not need_target,supplementation=plans)
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR/'data_quality_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    csv_write(REPORTS_DIR/'data_quality_markets.csv',grade_rows)
    csv_write(REPORTS_DIR/'data_quality_market_daily.csv',market_daily)
    csv_write(REPORTS_DIR/'data_quality_daily.csv',daily)
    for p in plans:csv_write(REPORTS_DIR/f'data_quality_deficits_{p["days"]}d.csv',p['details'])
    lines=['# 기존 DB 데이터 품질 진단','',f"{len(markets)}종목 / {result['candles']:,}봉 / KST {stamp(first)} ~ {stamp(last)}",'',
        'API 및 다운로드, 이벤트·feature 분석 없이 timestamp만 조회했습니다. 원본 DB 읽기 전용이며 실행 전후 SHA-256 동일.',
        '관측률은 KST 달력일 1,440분 대비 저장된 분봉 수입니다. 공백은 무체결과 수집 누락을 구분할 수 없습니다. 처음·마지막 불완전 날짜는 기간 추천에서 제외합니다.',
        '연속 기간은 같은 종목이 매일 기준을 충족해야 합니다. 평균만 높거나 날짜마다 구성 종목이 달라지는 경우는 제외합니다.', '', '## 기준별 최적 연속 기간','']
    lines+=mdtable(['기준','일수','시작 KST','종료 KST(미포함)','종목','평균 관측률','최저 일 관측률','총 봉'],[
        [f'{r["threshold"]:.0%}',r['days'],r['start'] if r['market_count'] else '해당 없음',r['end_exclusive'] if r['market_count'] else None,r['market_count'],r['mean_coverage'],r['minimum_daily_coverage'],r['candle_count']] for r in best])
    r=recommendation
    lines+=['','## 추천','',f"{r['start']} 00:00 ~ {r['end_exclusive']} 00:00 KST / {r['market_count']}종목 / 매일 90% 이상 / 평균 {r['mean_coverage']:.2%} / {r['candle_count']:,}봉.",
        '선정 기준: 90% 이상 5일/7일 후보 중 종목 수 우선, 동률이면 긴 기간. 가격 상승률은 사용하지 않았습니다.',
        '종목: '+', '.join(r['markets']),'', '추천 기간 전체 280종목의 임시 등급: '+json.dumps(result['grades']),
        '등급은 기간 평균이고, 추천 종목은 매일 기준이므로 등급 개수와 추천 종목 수는 다를 수 있습니다.', '', '## 날짜별 시장 관측 상태','']
    lines+=mdtable(['KST 날짜','존재 종목','80%','90%','95%','100%','총 봉'],[
        [r['date'],r['markets_with_data'],r['coverage_80'],r['coverage_90'],r['coverage_95'],r['coverage_100'],r['candles']] for r in daily])
    lines+=['','## 부족분 추정 (다운로드하지 않음)','',
        '100종목이 매일 90%를 충족하는 목표의 최소 부족분을 계산했습니다. 기간과 대상은 부족분이 가장 작은 조합이며 추천 소규모 연구 기간과 다를 수 있습니다.',
        '없는 분봉이 실제로 복구 가능한 수집 누락이라는 가정에서만 다음 수치가 성립합니다. 무체결 분봉은 재요청해도 생성되지 않습니다. 실제 추가 수집 필요성은 이 숫자만으로 확정할 수 없습니다.',
        '기존 수집기의 가정인 요청당 최대 200봉·0.13초 간격을 사용합니다. 패킹 최소치는 종목·날짜별 부족분을 200개씩 묶을 수 있다고 가정한 낙관적 참고치이며 실제 호출량이 아닙니다. 공백별 값은 부족한 종목·날짜의 모든 공백을 조회하는 가정이며 최적 호출량이나 상한을 뜻하지 않습니다.',
        'Upbit의 역방향 count/to 페이지는 공백이 무체결이면 기존 봉을 반환할 수 있습니다. 기존 봉을 다시 받지 않는다는 보장은 현재 DB만으로 할 수 없습니다. 이 추정은 기존 전체 기간 재다운로드 계획이 아닙니다.','']
    for p in plans:
        lines += [f"### 100종목 × {p['days']}일 / {p['start']} ~ {p['end_exclusive']}",'',
            f"최소 추가 관측 필요: {p['minimum_additional_observations']:,}분봉. 부족한 종목 {p['affected_markets']}개 / 종목×날짜 {p['affected_market_days']}개.",
            f"이상적 패킹 최소 {p['ideal_packed_calls']:,}회 / 간격만 {p['ideal_packed_pacing_minutes']:.1f}분. 부족한 날짜의 공백별 조회 가정 {p['theoretical_all_gap_page_calls']:,}회 / 간격만 {p['all_gap_pacing_minutes']:.1f}분 / 요청당 응답 0.5초 가정 포함 {p['all_gap_seconds_05_latency_minutes']:.1f}분.",
            f"부족 날짜: {', '.join(p['affected_dates'])}. 종목·날짜별 부족분은 data_quality_deficits_{p['days']}d.csv 참고.",'']
    lines+=['## 상세 파일','',
        '- [종목별 최초/마지막 시각·연속 구간·공백·등급](data_quality_markets.csv)',
        '- [280종목 × 날짜별 관측 수·coverage](data_quality_market_daily.csv)',
        '- [날짜별 시장 집계](data_quality_daily.csv)',
        '- [전체 결과 및 추천 종목 목록](data_quality_audit.json)','']
    (REPORTS_DIR/'data_quality_audit.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(markets=result['market_count'],candles=result['candles'],recommendation=recommendation,
        best=[{k:v for k,v in r.items() if k!='markets'} for r in best],grades=result['grades'],
        supplementation=[{k:v for k,v in p.items() if k not in ('markets','details')} for p in plans]),ensure_ascii=False))


if __name__=='__main__':main()
