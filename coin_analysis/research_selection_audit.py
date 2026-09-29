"""Selection-only survey. Never creates candles or starts the research downloader."""
import argparse
import csv
import json
from pathlib import Path
import time
import statistics

from . import research_dataset_collector_v1 as c
from .paths import REPORTS_DIR


def daily_evidence(raw, market, start):
    end = start//86400*86400
    if any(r.get('market') != market for r in raw):
        raise ValueError('Wrong market')
    rows = [c.candle(r) for r in raw]
    if len({r[0] for r in rows}) != len(rows) or any(r[0] % 86400 or r[0] >= end for r in rows):
        raise ValueError('Invalid or future daily candle')
    recent = {r[0]:r for r in rows if end-7*86400 <= r[0] < end}
    complete = set(recent) == set(range(end-7*86400,end,86400))
    return dict(market=market,mean_daily_trade_value=sum(r[5] for r in recent.values())/7 if complete else None,
                age_30d_pass=bool(rows and min(r[0] for r in rows)<=start-30*86400),
                full_prior_7days=complete,stable_excluded=market[4:] in c.STABLES)


def save(path, data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    temporary.replace(path)


def survey(start, path):
    client=c.Client(max_requests=3000)
    report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(start=start,rows={},requests=0)
    if report['start']!=start:
        raise ValueError('Use separate cache for a different T')
    try:
        if 'markets' not in report:
            report['markets']=[r['market'] for r in client.get('/v1/market/all',isDetails='true') if r['market'].startswith('KRW-') and r['market']!='KRW-BTC']
            report['retrieved_at']=c.iso(int(time.time()))
            report['limitation']='Current market list; historical survivor bias. All ranking/coverage observations strictly before T.'
            save(path,report)
        for i,m in enumerate(report['markets'],1):
            row=report['rows'].get(m)
            if row is None:
                raw=client.get('/v1/candles/days',market=m,to=c.iso(start//86400*86400),count=32)
                row=daily_evidence(raw,m,start)
                report['rows'][m]=row
                save(path,report)
            row['stable_excluded']=m[4:] in c.STABLES
            if row['full_prior_7days'] and 'diagnostic' not in row:
                row['diagnostic']=c.prior_day_coverage(client,m,start)
                row['prior_24h_coverage']=row['diagnostic']['coverage']
                save(path,report)
            print(f'AUDIT {i}/{len(report["markets"])} {m} coverage={row.get("prior_24h_coverage")}',flush=True)
    finally:
        report['requests']+=client.requests
        save(path,report)
    ranked=sorted((r for r in report['rows'].values() if r['mean_daily_trade_value'] is not None),key=lambda r:(-r['mean_daily_trade_value'],r['market']))
    for rank,row in enumerate(ranked,1):row['trade_value_rank']=rank
    eligible=[r for r in ranked if r['age_30d_pass'] and not r['stable_excluded']]
    report['distribution']={str(t):sum(r['prior_24h_coverage']>=t for r in eligible) for t in (.99,.95,.9,.8,.7,.6,.5,.4,.3,.2,.1)}
    report['eligible_candidates']=len(eligible)
    report['ranked_candidates']=len(ranked)
    report['top100']=[{k:v for k,v in r.items() if k!='diagnostic'} for r in ranked[:100]]
    top_values=[r['prior_24h_coverage'] for r in ranked[:100]]
    report['top100_summary']=dict(mean=statistics.mean(top_values),median=statistics.median(top_values),minimum=min(top_values),maximum=max(top_values),
        age_pass=sum(r['age_30d_pass'] for r in ranked[:100]),stable_excluded=sum(r['stable_excluded'] for r in ranked[:100]),
        above60=sum(r['prior_24h_coverage']>=.6 for r in ranked[:100]))
    report['proposals']={}
    for name,threshold,limit in [('A',.8,50),('B',.6,50),('C',.5,75)]:
        pool=[r for r in eligible if r['prior_24h_coverage']>=threshold]
        selected=pool[:limit]
        values=[r['prior_24h_coverage'] for r in selected]
        report['proposals'][name]=dict(threshold=threshold,available=len(pool),selected=len(selected),mean=statistics.mean(values),minimum=min(values),
            estimated_14d_alt_candles=round(sum(values)*20160),maximum_14d_alt_candles=len(values)*20160,markets=[r['market'] for r in selected])
    report['threshold_cohorts']={}
    for threshold in (.95,.9,.8,.7,.6,.5,.4,.3,.2,.1):
        available=[r for r in eligible if r['prior_24h_coverage']>=threshold]
        selected=available[:50]
        values=[r['prior_24h_coverage'] for r in selected]
        report['threshold_cohorts'][str(threshold)]=dict(available=len(available),selected=len(selected),mean=sum(values)/len(values) if values else None,minimum=min(values) if values else None,
            estimated_14d_alt_candles=sum(values)*20160,maximum_14d_alt_candles=len(values)*20160,markets=[r['market'] for r in selected])
    save(path,report)
    with path.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(report['top100'][0]))
        writer.writeheader();writer.writerows(report['top100'])
    print(json.dumps({k:report[k] for k in ('requests','distribution','eligible_candidates','ranked_candidates','top100_summary','proposals')},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',required=True)
    p.add_argument('--output',type=Path,default=REPORTS_DIR/'research_selection_distribution.json')
    a=p.parse_args()
    survey(c.parse(a.start),a.output)


if __name__=='__main__':main()
