"""Verify preservation and gracefully stop owned processes; no LIVE/API start."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import os
import time

from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_dashboard_v50 as dashboard
from coin_analysis import scanner_desktop_v50 as desktop

OUT=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')


if __name__=='__main__':
    web=desktop.web_state()
    if web['status']=='RUNNING':
        pid=web['process']['pid']
        command=['powershell','-NoProfile','-NonInteractive','-Command',
                 f'$p=Get-Process -Id {pid}; [pscustomobject]@{{working_set_bytes=$p.WorkingSet64;peak_working_set_bytes=$p.PeakWorkingSet64;cpu_seconds=$p.CPU;threads=$p.Threads.Count}} | ConvertTo-Json -Compress']
        resources=subprocess.run(command,capture_output=True,timeout=5)
        assert resources.returncode==0
        write('web_resources.json',dict(at=time.time(),process=web['process'],**json.loads(resources.stdout)))
    stopped=subprocess.run(['cmd','/d','/c','call',str(control.PROJECT_ROOT/'stop_coin_api.bat')],
                           cwd=control.PROJECT_ROOT,env=dict(os.environ,COIN_API_NO_PAUSE='1'),capture_output=True,timeout=55)
    write('final_stop.json',dict(at=time.time(),exit_code=stopped.returncode,stdout=stopped.stdout.decode('utf8',errors='replace')))
    assert stopped.returncode==0
    state=control.current();web=desktop.web_state()
    assert not control.alive(state.get('manager')) and not control.alive(state.get('child'))
    assert web['status']=='STOPPED' and not control.alive(web.get('process'))
    with closing(socket.socket()) as probe:
        probe.settimeout(.5);port_closed=probe.connect_ex(('127.0.0.1',8765))!=0
    assert port_closed
    command=['powershell','-NoProfile','-NonInteractive','-Command',
             "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*coin_api-1*' -and $_.CommandLine -match 'coin_api_entry[.]py.*(_serve|_scanner)|coin_analysis[.](forward_scanner_v4|scanner_control_v410)' } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"]
    processes=subprocess.run(command,capture_output=True,timeout=8)
    assert processes.returncode==0
    active=json.loads(processes.stdout.strip() or b'[]');assert not active
    before=read(OUT/'preflight.json');preserved={}
    for key,values in before.items():
        if key.endswith('_hashes'):
            changed=[p for p,h in values.items() if not Path(p).exists() or sha(p)!=h]
            assert not changed,(key,changed)
            preserved[key]=dict(count=len(values),unchanged=True)
    with dashboard.readonly(dashboard.ARCHIVE,True) as db:
        original_signals=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        assert original_signals==163
        assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    health={}
    for path in sorted(control.observer.RUNTIME_ROOT.glob('*/*.db')):
        with dashboard.readonly(path) as db:health[str(path)]=db.execute('PRAGMA quick_check').fetchone()[0]
    assert all(v=='ok' for v in health.values())
    legacy=read('reports/scanner_v41_validation_20261024/legacy_reconciliation.json')
    assert legacy['counts']['STALE_OPEN']==115 and sha(legacy['source'])==legacy['source_sha256']
    frozen=['coin_analysis/forward_scanner_v4.py','coin_analysis/forward_scanner_v4_operations.py',
            'coin_analysis/scanner_candles.py','coin_analysis/forward_scanner_v42.py','coin_analysis/forward_scanner_v43.py',
            'coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_clock_v47.py','coin_analysis/scanner_ntp_v49.py',
            'coin_analysis/scanner_observation_v45.py','archive/scanner_v15.py',
            'docs/forward_surge_v3_validation_policy.json','docs/research_market_validation_v1_manifest.json']
    assert not subprocess.check_output(['git','diff',before['baseline'],'--',*frozen]).strip()
    tests=read(OUT/'test_result.json');assert tests['successful']
    assert all(sha(p)==h for p,h in tests['source_sha256'].items())
    first=read(OUT/'first_start_state.json');second=read(OUT/'second_start_state.json')
    first_root=Path(first['root']);run=read(OUT/'first_2f514026f8bf4a08bed6a5986b981bdc.json')
    clocks=[first['clock_evidence'],run['clock_admission']]
    for path in first_root.glob('events*.jsonl'):
        for line in path.read_text(encoding='utf8').splitlines():
            row=json.loads(line)
            if row['kind']=='CLOCK_CHECK':
                clocks.append(row['evidence']);write('first_worker_clock.json',row['evidence'])
    clocks.append(second['clock_evidence'])
    attempts=[a for c in clocks for a in c.get('measurement',{}).get('attempts',c.get('measurement',{}).get('rows',[]))]
    measured=[a for a in attempts if a['status']=='MEASURED']
    assert len(attempts)<=before['bounds']['ntp_packets_max']
    summary=read(OUT/'first_2f514026f8bf4a08bed6a5986b981bdc.summary.json')
    exit_info=read(OUT/'first_2f514026f8bf4a08bed6a5986b981bdc.exit.json')
    assert summary['requests']==0 and not summary['close_errors']
    assert exit_info['worker_reaped'] and not exit_info['forced_kill'] and exit_info['worker_returncode']==0
    assert not control.owned_root(second).exists()
    value=dict(at=time.time(),dashboard='PASS',infrastructure='PARTIAL',unattended_24h='NOT_READY',
               original_signals=original_signals,stale_open=115,preservation=preserved,db_quick_check=health,
               engine_and_clock_policy_unchanged=True,tests_run=tests['tests_run'],tested_sources_match=True,
               actual_start_attempts=2,actual_exchange_http=0,new_signals=0,new_data_completeness='NO_DATA / no collection denominator',
               actual_ntp_attempts=len(attempts),actual_ntp_measured=len(measured),actual_ntp_failures=len(attempts)-len(measured),
               max_measured_abs_offset_plus_uncertainty_seconds=max(abs(a['offset_seconds'])+a['uncertainty_seconds'] for a in measured),
               latest_live_admission='BLOCKED / CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE',
               manager_alive=False,worker_alive=False,web_alive=False,port_8765_closed=port_closed,active_owned_processes=active,
               actual_natural_30_60m='UNVERIFIED',post_fix_clock_pass_live_collection='UNVERIFIED; second clock gate failed',
               no_orders=True,no_new_force_kill=True,no_autostart=True,no_windows_shutdown=True,
               new_runtime_hashes={p.as_posix():sha(p) for p in first_root.rglob('*') if p.is_file()})
    write('completion_checks.json',value)
    print(json.dumps({k:v for k,v in value.items() if k not in ('new_runtime_hashes','db_quick_check')},ensure_ascii=True))
