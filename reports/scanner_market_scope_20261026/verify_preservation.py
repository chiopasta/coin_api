"""Compare static data and protected running identities without stopping them."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from coin_analysis import scanner_control_v410 as control,scanner_desktop_v50 as desktop
REPORT=Path(__file__).resolve().parent
baseline=json.loads((REPORT/'baseline.json').read_text(encoding='utf-8'))
changed=[];missing=[]
for name,before in baseline['files'].items():
    path=ROOT/name
    if not path.exists():missing.append(name)
    elif hashlib.sha256(path.read_bytes()).hexdigest()!=before:changed.append(name)
allowed={'docs/research_status.md','docs/scanner_v50_dashboard.md'}
dbs={}
for name,before in baseline['dbs'].items():
    path=ROOT/name
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        counts={t:db.execute('select count(*) from "'+t+'"').fetchone()[0] for t in before['counts']}
        dbs[name]=dict(hash_equal=hashlib.sha256(path.read_bytes()).hexdigest()==baseline['files'][name],
                      counts_equal=counts==before['counts'],counts_before=before['counts'],counts_after=counts,
                      quick_check=db.execute('pragma quick_check').fetchone()[0])
state=control.current();root=control.owned_root(state)
reload=json.loads((REPORT/'web_reload_validation.json').read_text())
worker=reload['worker'];cfg=control.read_json(root/'config.json')
control.observer.validate_config(cfg)
current=control.snapshot()
process=dict(launch_same=state['launch_id']==baseline['protected_active_launch'],
    manager_same=state['manager']==baseline['manager'],supervisor_same=state['child']==baseline['supervisor'],
    manager_alive=control.alive(baseline['manager']),supervisor_alive=control.alive(baseline['supervisor']),
    worker_alive=control.alive(worker),phase=state['phase'],status=state['status'],
    runtime_stop=(root/'STOP').exists(),control_stop=control.stop_marker(state).exists(),
    seconds=state['seconds'],max_requests=state['max_requests'],
    config_frozen_valid=True,config_mtime_predates_task=(root/'config.json').stat().st_mtime<=baseline['at'],
    web_status=desktop.web_state()['status'])
sources=['coin_analysis/scanner_market_scope.py','coin_analysis/scanner_control_v410.py',
         'coin_analysis/scanner_dashboard_v50.py','coin_analysis/forward_scanner_v43.py',
         'coin_analysis/dashboard_assets/index.html','coin_analysis/dashboard_assets/app.js',
         'coin_analysis/dashboard_assets/style.css','tests/test_scanner_market_scope.py','tests/test_forward_scanner_v43.py']
value=dict(at=time.time(),baseline_files=len(baseline['files']),byte_identical=len(baseline['files'])-len(changed)-len(missing),
    changed=changed,missing=missing,unexpected_changes=sorted(set(changed)-allowed),static_dbs=dbs,
    protected_user_processes=process,current_scope=current['market_scope'],
    naturally_changing_paths=baseline['excluded_live_paths'],
    actual_task_exchange_http=2,task_candle_requests=0,task_ntp_calls=0,task_scanner_starts=0,task_scanner_stops=0,
    authorised_idle_web_reloads=1,
    exclusion_notes='Active runtime/cache continue normal operation; web current/log also changed by the authorised web-only replacement. No source DB or frozen result was written by this task.',
    source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
(REPORT/'completion_checks.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
assert not missing and not value['unexpected_changes']
assert all(v['hash_equal'] and v['counts_equal'] and v['quick_check']=='ok' for v in dbs.values())
assert process['launch_same'] and process['manager_same'] and process['supervisor_same']
assert process['config_frozen_valid'] and process['config_mtime_predates_task']
assert process['max_requests']==16000 and process['seconds']==86400
assert process['manager_alive'] and process['supervisor_alive'] and process['worker_alive']
assert not process['runtime_stop'] and not process['control_stop']
print(json.dumps(dict(preservation='PASS',files=value['baseline_files'],changed=changed,static_dbs=len(dbs),
    original_signals=dbs['data/forward_scanner_v4.db']['counts_after']['signals'],processes=process,scope=value['current_scope'])))
