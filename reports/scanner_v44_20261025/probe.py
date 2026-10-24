"""Bounded retrospective public source probe; never modifies observed DBs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from coin_analysis import forward_scanner_v43 as v

OUT=Path('reports/scanner_v44_20261025')
RAW=Path('data/scanner_v44_audit/20261025')
MARKETS=['KRW-ENA','KRW-FLOCK','KRW-SAND']
END=v.scanner.collector.parse('2026-10-24T23:55:00+09:00')
START=END-35*60


def sha(path):
    with open(path,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    if RAW.exists() or (OUT/'probe.json').exists():raise RuntimeError('Evidence already exists; no repeat collection')
    RAW.mkdir(parents=True)
    protected=json.loads(Path('reports/scanner_v41_validation_20261024/input_manifest.json').read_text())['inputs']
    checks={p:sha(p)==r['sha256'] for p,r in protected.items()}
    assert len(checks)==86 and all(checks.values())
    prior={str(p):sha(p) for base in ['data/scanner_v42_live/episode_20261024_supported','data/scanner_v43_live/episode_20261024']
           for p in Path(base).rglob('*') if p.is_file()}
    v.write_json(OUT/'preflight.json',dict(at=time.time(),protected_inputs=checks,prior_runtime_hashes=prior))
    began=time.time();deadline=began+120;records=[];blocked=False;next_request=0
    limits=dict(frozen_at=began,max_requests=36,max_seconds=120,retries=0,min_spacing_seconds=.3,
        markets=MARKETS,exchanges=list(v.v42.HOSTS),candle_units=[1,5,15],tick_pages_max_per_market=3,
        tick_count=500,candle_count=200,window_start=START,window_end=END,raw_max_bytes=20*1024*1024,
        no_live_scanner=True,no_orders=True,no_keys=True)
    v.write_json(OUT/'bounds.json',limits)

    def request(exchange,endpoint,params):
        nonlocal blocked,next_request
        if blocked or time.time()>=deadline or len(records)>=limits['max_requests']:return None
        if endpoint not in ['/v1/trades/ticks',*[f'/v1/candles/minutes/{n}' for n in (1,5,15)]]:raise ValueError('Non-public audit scope')
        assert params['market'] in MARKETS
        time.sleep(max(0,next_request-time.monotonic()));next_request=time.monotonic()+.3
        index=len(records);r=dict(exchange=exchange,endpoint=endpoint,params=params,started_at=time.time(),file=str(RAW/f'{index:02}.json'))
        records.append(r)
        # Request evidence is durable even if interpreter/network is interrupted.
        v.write_json(OUT/'probe_progress.json',dict(at=time.time(),records=records))
        try:
            req=urllib.request.Request(v.v42.HOSTS[exchange]+endpoint+'?'+urllib.parse.urlencode(params),
                headers={'Accept':'application/json','User-Agent':'CHIO-v4.4-bounded-source-audit/1'})
            with urllib.request.urlopen(req,timeout=max(.1,min(5,deadline-time.time()))) as response:
                data=response.read(2*1024*1024+1)
                if len(data)>2*1024*1024:raise ValueError('Oversize response')
                body=json.loads(data)
                if not isinstance(body,list):raise ValueError('Expected public array')
                Path(r['file']).write_bytes(data)
                r.update(status=response.status,received_at=time.time(),server_date=response.headers.get('Date'),
                    remaining_req=response.headers.get('Remaining-Req'),rows=len(body),sha256=sha(r['file']))
                if sum(p.stat().st_size for p in RAW.iterdir())>limits['raw_max_bytes']:blocked=True
                return body
        except Exception as exc:
            r.update(error=repr(exc),received_at=time.time())
            if getattr(exc,'code',None) in (418,429):blocked=True
            return None
        finally:v.write_json(OUT/'probe_progress.json',dict(at=time.time(),records=records))

    for exchange in v.v42.HOSTS:
        for market in MARKETS:
            for unit in (1,5,15):
                cutoff=END//(unit*60)*(unit*60)
                request(exchange,f'/v1/candles/minutes/{unit}',dict(market=market,count=200,to=v.candles.api_to(exchange,cutoff)))
            # Trade endpoint clocks are NOT the candle endpoint serialization.
            # Upbit uses UTC/day offset; Bithumb uses KST and camelCase daysAgo.
            zone=v.scanner.collector.UTC if exchange=='UPBIT' else v.scanner.collector.KST
            day_offset=(datetime.now(zone).date()-datetime.fromtimestamp(END,zone).date()).days
            params=dict(market=market,count=500,to=datetime.fromtimestamp(END,zone).strftime('%H:%M:%S'))
            if day_offset:
                if not 1<=day_offset<=7:continue
                params['days_ago' if exchange=='UPBIT' else 'daysAgo']=day_offset
            seen=set()
            for _ in range(3):
                body=request(exchange,'/v1/trades/ticks',dict(params))
                if not body:break
                try:
                    stamps=[int(r['timestamp'])/1000 for r in body]
                    cursor=str(body[-1]['sequential_id'])
                    if min(stamps)<=START or cursor in seen:break
                    seen.add(cursor);params['cursor']=cursor
                except (KeyError,ValueError,TypeError):break
    result=dict(started_at=began,ended_at=time.time(),limits=limits,http_attempts=len(records),
        successes=sum('status' in r for r in records),errors=sum('error' in r for r in records),blocked=blocked,records=records,
        protected_inputs_preserved=all(sha(p)==r['sha256'] for p,r in protected.items()),
        prior_runtimes_preserved=all(sha(p)==h for p,h in prior.items()))
    v.write_json(OUT/'probe.json',result)
    print(json.dumps(dict(attempts=len(records),successes=result['successes'],errors=[r for r in records if 'error' in r],
        trade_pages=[dict(exchange=r['exchange'],market=r['params']['market'],rows=r.get('rows')) for r in records if r['endpoint'].endswith('ticks')])))


if __name__=='__main__':main()
