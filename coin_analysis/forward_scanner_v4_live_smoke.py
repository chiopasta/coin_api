"""Explicit opt-in real Upbit smoke: BTC/ETH/XRP, <=20 HTTP attempts, <=180s."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.parse

from . import forward_scanner_v4 as s
from .paths import DATA_DIR,REPORTS_DIR

MAX_REQUESTS=20
MAX_SECONDS=180
MARKETS=['KRW-BTC','KRW-ETH','KRW-XRP']
REPORT=REPORTS_DIR/'forward_scanner_v4_live_smoke.json'

def worker():
    began=time.monotonic();deadline=began+150;attempts=[];messages=[]
    now=int(time.time());path=DATA_DIR/f'forward_scanner_v4_smoke_{now}.db'
    sources={str(p):s.v3.v2.digest(p) for p in (DATA_DIR/'research_market_v1.db',DATA_DIR/'research_market_validation_v1.db')}
    def emit(msg):messages.append(msg);print(msg,flush=True)
    def transport(endpoint,params):
        if endpoint!='/v1/candles/minutes/1' or params['market'] not in MARKETS:raise ValueError('Out of smoke scope')
        if len(attempts)>=MAX_REQUESTS or time.monotonic()>=deadline:raise s.collector.CollectionBlocked('Global smoke bound')
        entry=dict(market=params['market'],to=params['to'],count=params['count'],started_monotonic=time.monotonic());attempts.append(entry)
        url='https://api.upbit.com'+endpoint+'?'+urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'v4-bounded-smoke/1'}),timeout=max(.1,min(20,deadline-time.monotonic()))) as response:
                entry['status']=response.status;entry['remaining_req']=response.headers.get('Remaining-Req')
                body=json.loads(response.read());entry['candles']=len(body)
                return body,dict(response.headers)
        except Exception as exc:
            entry['error']=str(exc);entry['status']=getattr(exc,'code',None);raise
        finally:entry['elapsed_seconds']=time.monotonic()-entry['started_monotonic']
    def bounded_sleep(seconds):
        if time.monotonic()+seconds>=deadline:raise s.collector.CollectionBlocked('Smoke deadline')
        time.sleep(seconds)
    result=dict(markets=MARKETS,db=str(path),max_requests=MAX_REQUESTS,hard_wall_limit_seconds=MAX_SECONDS,
                started_utc=s.collector.iso(now),api_attempts=attempts,passed=False)
    try:
        with s.exclusive(path):
            with closing(s.connect(path)) as db:
                s.initialize(db,MARKETS,(now//300+1)*300)
                first=s.collector.Client(transport=transport,sleep=bounded_sleep,max_requests=1)
                cutoff=(now-5)//60*60
                try:s.fetch_market(db,first,'KRW-BTC',cutoff)
                except s.collector.CollectionBlocked:pass
                job=db.execute('SELECT * FROM collection_jobs WHERE market=?',('KRW-BTC',)).fetchone()
                if job is None:raise AssertionError('Expected interrupted warmup page')
                resume_cursor=job['cursor'];result['restart_cursor']=resume_cursor
            # Reopen disk DB, resume the real partially committed reverse page job.
            client=s.collector.Client(transport=transport,sleep=bounded_sleep,max_requests=MAX_REQUESTS-1)
            with closing(s.connect(path)) as db:
                s.fetch_market(db,client,'KRW-BTC',cutoff)
                result['resume_from_saved_cursor']=s.collector.parse(attempts[1]['to'])==resume_cursor
                s.cycle(db,client,now,emit)
                count=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0]
                requests=len(attempts)
                s.cycle(db,client,now,emit)
                result['same_cutoff_idempotent']=count==db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0] and len(attempts)==requests
            # Wait only until next closed minute is available; no long scanner loop.
            bounded_sleep(max(0,cutoff+66-time.time()))
            with closing(s.connect(path)) as db:
                s.cycle(db,client,None,emit)
                result['stats']=s.statistics(db)
                result['rows']=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0]
                result['new_rows_after_next_minute']=result['rows']-count
                result['duplicates']=db.execute('SELECT COUNT(*) FROM (SELECT market,ts FROM minute_candles GROUP BY market,ts HAVING COUNT(*)>1)').fetchone()[0]
                result['timestamp_errors']=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts%60<>0 OR ts>=?',((int(time.time())-5)//60*60,)).fetchone()[0]
                result['per_market']=[dict(r) for r in db.execute('SELECT market,COUNT(*) AS candles,MIN(ts) AS first_ts,MAX(ts) AS last_ts FROM minute_candles GROUP BY market')]
                result['states']=[dict(r) for r in db.execute('SELECT * FROM scanner_state')]
                result['integrity']=db.execute('PRAGMA integrity_check').fetchone()[0]
                result['unfinished_collection_jobs']=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0]
                result['pending_note']='Natural live signals only; if none, PENDING path covered by synthetic restart tests, not claimed live-tested. Less than 10m cannot complete L1/L2.'
                result['retries']=client.retries+first.retries
                result['passed']=all([result['resume_from_saved_cursor'],result['same_cutoff_idempotent'],result['rows']>0,
                    not result['duplicates'],not result['timestamp_errors'],result['integrity']=='ok',not result['stats']['collection_errors'],not result['unfinished_collection_jobs']])
    except Exception as exc:result['error']=repr(exc)
    finally:
        result['elapsed_seconds']=time.monotonic()-began;result['actual_api_requests']=len(attempts)
        result['finished_utc']=s.collector.iso(int(time.time()));result['scanner_closed']=True
        result['research_db_hashes_unchanged']=all(s.v3.v2.digest(Path(p))==digest for p,digest in sources.items())
        result['messages']=messages
        REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:result.get(k) for k in ('passed','actual_api_requests','elapsed_seconds','rows','error','scanner_closed')},ensure_ascii=False),flush=True)
    return 0 if result['passed'] else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute-live',action='store_true');p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    if not a.execute_live:p.error('Explicit --execute-live required; at most 20 actual requests')
    if a.worker:raise SystemExit(worker())
    try:
        finished=subprocess.run([sys.executable,'-m',__spec__.name,'--execute-live','--worker'],timeout=MAX_SECONDS)
        raise SystemExit(finished.returncode)
    except subprocess.TimeoutExpired:
        # subprocess.run kills and waits for its sole worker, which has no children.
        REPORT.write_text(json.dumps(dict(passed=False,error='Hard 180s timeout; worker killed and reaped',actual_api_requests='unknown, hard bounded <=20',scanner_closed=True),indent=2),encoding='utf-8')
        raise SystemExit(1)

if __name__=='__main__':main()
