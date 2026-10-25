# Reuses the V4.8 bounded controller; separate paths and a seven-check STOP reserve.
"""One explicit, bounded V4.9 episode with a single manual-style resume.

Uses the existing public-only scanner CLI and all unchanged admission gates.
Never starts on a failed clock, never relaunches after an error, no scheduler.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from coin_analysis import forward_scanner_v43 as v

OUT=Path('reports/scanner_v49_20261025')
ROOT=Path('data/scanner_v43_live/episode_20261025_v49').resolve()


def write(name,value):
    target=OUT/name;tmp=target.with_suffix(target.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');tmp.replace(target)


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def preflight_api():
    clock=json.loads((OUT/'clock_admission.json').read_text(encoding='utf8'))
    if clock['status']!='VERIFIED':raise RuntimeError('Clock failed; API/LIVE forbidden')
    if time.time()-clock['completed_at']>15:raise RuntimeError('Clock evidence expired; do not reuse')
    processes=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"],capture_output=True,timeout=5)
    if processes.returncode or json.loads(processes.stdout.strip() or b'[]'):raise RuntimeError('Duplicate scanner or process inspection unavailable')
    records=[];start=time.monotonic()
    for exchange,host in v.v42.HOSTS.items():
        for endpoint in ('/v1/market/all','/v1/candles/minutes/1'):
            if time.monotonic()-start>=20:raise RuntimeError('API preflight time exhausted')
            cutoff=v.candles.closed_cutoff(time.time())
            params={} if endpoint.endswith('/all') else dict(market='KRW-BTC',count=200,to=v.candles.api_to(exchange,cutoff))
            record=dict(exchange=exchange,endpoint=endpoint,params=params,started_at=time.time());records.append(record)
            write('api_preflight.json',dict(records=records,finished=False,max_requests=4))
            request=urllib.request.Request(host+endpoint+'?'+urllib.parse.urlencode(params),headers={'User-Agent':'ScannerV48-bounded-preflight/1'})
            with urllib.request.urlopen(request,timeout=min(5,20-(time.monotonic()-start))) as response:
                raw=response.read(262145)
                if len(raw)>262144:raise RuntimeError('Oversize public response')
                body=json.loads(raw)
                if endpoint.endswith('/all'):
                    if set(v.MARKETS)-{r['market'] for r in body}:raise RuntimeError('Fixed cohort unsupported')
                else:v.candles.validate_page(body,cutoff,'KRW-BTC')
                record.update(status=response.status,rows=len(body),received_at=time.time(),remaining_req=response.headers.get('Remaining-Req'))
            time.sleep(.25)
    write('api_preflight.json',dict(records=records,finished=True,max_requests=4,elapsed=time.monotonic()-start))


def clock_checks():
    total=0
    for path in ROOT.glob('events*.jsonl'):
        for line in path.read_text(encoding='utf8').splitlines():
            try:total+=json.loads(line).get('kind')=='CLOCK_CHECK'
            except ValueError:continue
    return total


def cleanup_owned(process):
    """Only this Popen's still-live supervisor and descendants, after STOP."""
    if process.poll() is not None:return False
    if ROOT.exists():(ROOT/'STOP').touch(exist_ok=True)
    try:
        process.wait(timeout=40)
        return False
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            # Popen retains the original process handle: this live PID cannot
            # have been recycled. /T is restricted to our owned child tree.
            if os.name=='nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=5,creationflags=0x08000000)
            else:process.kill()
        process.wait(timeout=5)
        return True


def run_one(seconds,requests,resume,stop_after=None,deadline=None):
    before=set((ROOT/'runs').glob('*.json')) if ROOT.exists() else set()
    log=OUT/('resume_stdout.log' if resume else 'first_stdout.log')
    began=time.monotonic();stopped=False
    with log.open('x',encoding='utf8') as stream:
        process=subprocess.Popen([sys.executable,'-X','utf8','-m','coin_analysis.forward_scanner_v43',
            '--execute-live','--runtime-dir',str(ROOT),'--seconds',str(seconds),'--max-requests',str(requests),
            *(['--resume'] if resume else [])],stdout=stream,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
        forced=False
        try:
            while process.poll() is None:
                elapsed=time.monotonic()-began
                request_stop=(stop_after is not None and elapsed>=stop_after) or (OUT/'STOP_MANAGER').exists() or clock_checks()>=7 or time.monotonic()>=deadline
                if request_stop and ROOT.exists() and not stopped:
                    (ROOT/'STOP').touch(exist_ok=True);stopped=True
                write('live_progress.json',dict(at=time.time(),supervisor_pid=process.pid,resume=resume,elapsed=elapsed,
                    stop_requested=stopped,clock_checks=clock_checks(),absolute_seconds_left=deadline-time.monotonic()))
                if elapsed>seconds+40:raise RuntimeError('Owned supervisor exceeded cleanup allowance')
                time.sleep(2)
            code=process.wait(timeout=2)
        finally:
            forced=cleanup_owned(process)
            if forced:write('forced_owned_cleanup.json',dict(at=time.time(),supervisor_pid=process.pid,forced=True,no_unrelated_process_target=True))
    summaries=set((ROOT/'runs').glob('*.summary.json'))-before
    if len(summaries)!=1:raise RuntimeError('Missing unique worker summary; no resume')
    summary=json.loads(summaries.pop().read_text(encoding='utf8'));run_id=summary['run_id']
    if not re.fullmatch('[0-9a-f]{32}',run_id):raise RuntimeError('Invalid owned run ID')
    exit_info=json.loads((ROOT/'runs'/f'{run_id}.exit.json').read_text(encoding='utf8'))
    result=dict(summary=summary,exit=exit_info,supervisor_returncode=code,supervisor_reaped=True)
    if code or summary['close_errors'] or exit_info['forced_kill'] or summary['status'] not in ('STOPPED','BOUNDED_STOP'):
        write('live_failed.json',result);raise RuntimeError('Unsafe/incomplete run; no resume')
    return result


def snapshot():
    result=dict(config_sha256=sha(ROOT/'config.json'),databases={})
    destination=ROOT/'before_resume';destination.mkdir(exist_ok=False)
    for exchange in v.v42.HOSTS:
        with v.ops.readonly(ROOT/(exchange.lower()+'.db')) as db:
            backup=sqlite3.connect(destination/(exchange.lower()+'.db'))
            try:db.backup(backup)
            finally:backup.close()
            result['databases'][exchange]=dict(fingerprints=v.ops.full_fingerprints(db),
                state=[dict(r) for r in db.execute('SELECT * FROM scanner_state')],
                pending=[dict(r) for r in db.execute("SELECT * FROM live_horizons WHERE status='PENDING'")])
    write('before_resume.json',result)


def main():
    if ROOT.parent!=v.RUNTIME_ROOT.resolve() or ROOT.exists():raise RuntimeError('New isolated episode required')
    if (OUT/'live_result.json').exists():raise RuntimeError('Never repeat this explicit observation')
    before=json.loads((OUT/'preflight.json').read_text(encoding='utf8'))
    if not all(sha(p)==h for p,h in before['protected_hashes'].items()):raise RuntimeError('Protected input changed')
    preflight_api()
    started=time.time();deadline=time.monotonic()+1200
    write('live_started.json',dict(at=started,root=str(ROOT),max_seconds=1200,
        runs=[dict(seconds=180,max_requests=80,stop_after_seconds=90),dict(seconds=780,max_requests=180,resume=True)],
        no_orders=True,no_auto_restart=True))
    first=run_one(180,80,False,stop_after=90,deadline=deadline)
    snapshot()
    if (OUT/'STOP_MANAGER').exists() or clock_checks()>=7:
        write('live_aborted.json',dict(at=time.time(),reason='EXPLICIT_STOP_OR_CLOCK_TASK_BUDGET',first=first,no_resume=True))
        return
    if time.monotonic()+780+40>deadline:raise RuntimeError('Insufficient task time for bounded resume')
    if not (ROOT/'STOP').exists():raise RuntimeError('Expected explicit STOP before resume')
    (ROOT/'STOP').rename(ROOT/f"STOP.first_{first['summary']['run_id']}")
    second=run_one(780,180,True,deadline=deadline)
    result=dict(started_at=started,ended_at=time.time(),root=str(ROOT),runs=[first,second],
        clock_checks=clock_checks(),requests=sum(r['summary']['requests'] for r in (first,second)),
        no_orders=True,no_24h_run=True,only_explicit_single_resume=True)
    assert result['requests']<=260
    write('live_result.json',result)
    print(json.dumps(dict(status='COMPLETE_BOUNDED_OBSERVATION',requests=result['requests'],runs=2)),flush=True)


if __name__=='__main__':main()
