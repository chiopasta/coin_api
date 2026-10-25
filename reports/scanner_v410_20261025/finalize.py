"""Read-only final preservation, process, status and bounded-run checks."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

from coin_analysis import scanner_control_v410 as c

OUT=Path('reports/scanner_v410_20261025')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(name,value):
    if (OUT/name).exists():
        assert read(OUT/name)==value,'Existing factual evidence differs: '+name
        return
    with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)


if __name__=='__main__':
    pre=read(OUT/'preflight.json')
    for group in ('protected_hashes','prior_evidence_hashes','previous_live_raw_hashes'):
        assert all(sha(p)==h for p,h in pre[group].items()),group
    original=Path('data/forward_scanner_v4.db');wal=Path(str(original)+'-wal')
    assert not wal.exists() or not wal.stat().st_size
    db=sqlite3.connect(original.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        assert db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]==163
    finally:db.close()
    legacy=read('reports/scanner_v41_validation_20261024/legacy_reconciliation.json')
    assert legacy['counts']['STALE_OPEN']==115 and sha(legacy['source'])==legacy['source_sha256']
    tests=read(OUT/'test_result.json');assert tests['successful']
    assert all(sha(p)==h for p,h in tests['source_sha256'].items())
    frozen=['forward_scanner_v4.py','forward_scanner_v4_operations.py','forward_scanner_v42.py',
        'forward_scanner_v43.py','scanner_candles.py','scanner_clock_v45.py','scanner_clock_v47.py',
        'scanner_ntp_v46.py','scanner_ntp_v49.py','scanner_observation_v45.py','research_dataset_collector_v1.py']
    assert not subprocess.check_output(['git','diff','11404d3','--',*[str(Path('coin_analysis')/p) for p in frozen],
        'archive/scanner_v15.py','docs/forward_surge_v3_validation_policy.json','docs/research_market_validation_v1_manifest.json'],text=True).strip()
    state=c.current();view=c.snapshot()
    assert state['status']=='STOPPED' and state['phase']=='TERMINAL' and view['db_saved'].startswith('SAVED')
    assert not c.alive(state['manager']) and not c.alive(state['child'])
    scan=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"],capture_output=True,timeout=5)
    assert scan.returncode==0 and not json.loads(scan.stdout.strip() or b'[]')
    first=read(OUT/'first_blocked_attempt.json');assert first['state']['status']=='BLOCKED' and not first['runtime_created']
    assert not Path(first['state']['root']).exists()
    root=c.owned_root(state)
    summary=read(root/'runs'/(state['run_id']+'.summary.json'));exit_info=read(root/'runs'/(state['run_id']+'.exit.json'))
    assert summary['status']=='STOPPED' and summary['reason']=='STOP_REQUESTED' and not summary['close_errors']
    assert summary['elapsed_monotonic_seconds']<=120 and summary['requests']<=80
    assert exit_info['worker_reaped'] and not exit_info['forced_kill'] and exit_info['worker_returncode']==0
    write('worker_summary.json',summary);write('worker_exit.json',exit_info)
    data={}
    for exchange in c.observer.v42.HOSTS:
        p=root/(exchange.lower()+'.db')
        with c.observer.ops.readonly(p) as db:
            data[exchange]=dict(health=db.execute('PRAGMA quick_check').fetchone()[0],
                signals=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0],
                candles=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],
                pending_jobs=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0],
                candle_alignment_errors=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts%60!=0').fetchone()[0],
                duplicates=db.execute('SELECT COUNT(*) FROM (SELECT market,signal_time,COUNT(*) n FROM signals GROUP BY market,signal_time HAVING n>1)').fetchone()[0])
        assert data[exchange]['health']=='ok' and data[exchange]['signals']==0 and data[exchange]['pending_jobs']==0 and data[exchange]['duplicates']==0
        wal=Path(str(p)+'-wal');assert not wal.exists() or not wal.stat().st_size
    with c.observer.ops.readonly(root/'control.db') as db:
        attempts=[dict(r) for r in db.execute('SELECT * FROM http_attempts')]
    assert len(attempts)==summary['requests'] and all(a['status']=='HTTP_END' and a['endpoint'] in ('/v1/market/all','/v1/candles/minutes/1') for a in attempts)
    checks=[first['state']['clock_evidence'],state['clock_evidence']]
    run=read(root/'runs'/(state['run_id']+'.json'));checks.append(run['clock_admission'])
    for path in root.glob('events*.jsonl'):
        for line in path.read_text(encoding='utf8').splitlines():
            row=json.loads(line)
            if row.get('kind')=='CLOCK_CHECK':checks.append(row['evidence'])
    packets=sum(len(q.get('measurement',{}).get('attempts',[])) for q in checks)
    assert packets<=72 and all(q['status']=='VERIFIED' for q in checks[1:])
    write('clock_review.json',dict(checks=checks,ntp_packets=packets))
    env=dict(os.environ,COIN_API_NO_PAUSE='1')
    commands={}
    for action in ('status','stop'):
        result=subprocess.run(['powershell','-NoProfile','-Command',"& '"+str(c.PROJECT_ROOT/(action+'_coin_api.bat'))+"'"],env=env,capture_output=True,timeout=15)
        assert result.returncode==0
        commands[action]=dict(returncode=0,stdout=result.stdout.decode('utf8',errors='replace'))
    write('stopped_powershell_commands.json',commands)
    write('completion_checks.json',dict(at=time.time(),status='PARTIAL',launcher_verified=True,unattended_24h='NOT_READY',
        original_signals=163,protected_count=86,prior_evidence_count=169,previous_live_raw_files=26,stale_open=115,
        all_protected_hashes_unchanged=True,all_prior_hashes_unchanged=True,previous_live_raw_unchanged=True,
        engine_clock_policy_and_research_unchanged=True,tests=tests,active_scanners=0,final_state=state,final_view=c.snapshot(),
        first_attempt='BLOCKED_CLOCK; no dataset/worker/API',actual_live_runs=1,worker_seconds=summary['elapsed_monotonic_seconds'],
        http_attempts=len(attempts),ntp_packets=packets,new_signals=0,db=data,exit=exit_info,
        new_runtime_hashes={str(p):sha(p) for p in root.rglob('*') if p.is_file()},
        management_hashes={str(p):sha(p) for p in c.CONTROL.rglob('*') if p.is_file()},
        shell_association_dispatch='VERIFIED',physical_mouse_doubleclick='UNVERIFIED',
        default_24h_execution='NOT_RUN',unicode_live='NOT_RUN; offline CMD and PowerShell verified',
        natural_30_60m='UNVERIFIED',no_orders=True,no_force_kill=True,no_autostart=True,no_windows_shutdown=True))
    print(json.dumps(dict(status='PARTIAL',final='STOPPED',saved=True,http=len(attempts),ntp=packets,tests=tests['tests_run'],preserved=86,prior=169)))
