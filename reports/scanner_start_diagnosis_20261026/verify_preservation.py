"""Read-only comparison of all existing DB tables, hashes and owned lifecycles."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from coin_analysis import scanner_control_v410 as control,scanner_desktop_v50 as desktop
REPORT=Path(__file__).resolve().parent
baseline=json.loads((REPORT/'baseline.json').read_text(encoding='utf-8'))
changed=[];missing=[]
for name,before in baseline['files'].items():
    path=ROOT/name
    if not path.exists():missing.append(name)
    elif hashlib.sha256(path.read_bytes()).hexdigest()!=before:changed.append(name)
allowed={'docs/research_status.md','docs/scanner_v50_dashboard.md',
         'data/scanner_console_v410/current.json','data/scanner_dashboard_v50/scanner_pending.json'}
dbs={}
for name,before in baseline['dbs'].items():
    path=ROOT/name
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        counts={t:db.execute('select count(*) from "'+t+'"').fetchone()[0] for t in before['counts']}
        dbs[name]=dict(hash_equal=hashlib.sha256(path.read_bytes()).hexdigest()==baseline['files'][name],
                      counts_equal=counts==before['counts'],counts_before=before['counts'],counts_after=counts,
                      quick_check=db.execute('pragma quick_check').fetchone()[0])
runs=[];ntp=0;http=0
for name in ('start1','start2'):
    result=json.loads((REPORT/(name+'.json')).read_text(encoding='utf-8'))
    state=control.read_json(control.CONTROL/'launches'/result['launch_id']/'state.json');root=control.owned_root(state)
    gates=[state['clock_evidence']]
    for path in (root/'runs').glob('*.json'):
        value=json.loads(path.read_text(encoding='utf-8'))
        if 'clock_admission' in value:gates.append(value['clock_admission'])
    for path in root.glob('events*.jsonl'):
        for line in path.read_text(encoding='utf-8').splitlines():
            value=json.loads(line)
            if value.get('kind')=='CLOCK_CHECK':gates.append(value['evidence'])
    summaries=[dict(status=e['status'],reason=e['reason'],providers=e['provider_summary'],
                    ntp_attempts=len(e.get('measurement',{}).get('attempts',[]))) for e in gates]
    ntp+=sum(e['ntp_attempts'] for e in summaries);http+=result['actual_http']
    new_dbs={}
    for path in root.glob('*.db'):
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            tables={r[0] for r in db.execute("select name from sqlite_master where type='table'")}
            v=dict(quick_check=db.execute('pragma quick_check').fetchone()[0])
            for table in ('signals','minute_candles','http_attempts'):
                if table in tables:v[table]=db.execute('select count(*) from '+table).fetchone()[0]
            if 'http_attempts' in tables:
                v['http_statuses']=db.execute("select json_extract(details_json,'$.http_status'),count(*) from http_attempts group by 1").fetchall()
                v['endpoints']=db.execute('select endpoint,count(*) from http_attempts group by endpoint').fetchall()
            new_dbs[path.name]=v
    runs.append(dict(name=name,validation=result['validation'],clock_gates=summaries,actual_http=result['actual_http'],
                     manager_alive=control.alive(state.get('manager')),supervisor_alive=control.alive(state.get('child')),
                     listener_closed=result['listener_closed'],dbs=new_dbs,exit=result['exit']))
previous=json.loads((ROOT/'reports/scanner_start_v53_20261026/completion_checks.json').read_text())
policies=['coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_ntp_v49.py','coin_analysis/forward_scanner_v43.py']
unchanged={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==previous['source_sha256'][p] for p in policies}
sources=['coin_analysis/scanner_control_v410.py','coin_analysis/scanner_desktop_v50.py','coin_analysis/scanner_dashboard_v50.py',
         'tests/test_scanner_dashboard_v50.py','tests/test_scanner_start_diagnosis.py']
value=dict(baseline_files=len(baseline['files']),byte_identical=len(baseline['files'])-len(changed)-len(missing),
    changed=changed,missing=missing,unexpected_changes=sorted(set(changed)-allowed),original_dbs=dbs,runs=runs,
    actual_ntp_attempts=ntp,ntp_cap=baseline['bounds']['total_ntp'],actual_http=http,http_cap=baseline['bounds']['total_http'],
    unchanged_clock_transport_and_engine=unchanged,web_status=desktop.web_state()['status'],
    source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
(REPORT/'completion_checks.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
assert not missing and not value['unexpected_changes']
assert all(d['hash_equal'] and d['counts_equal'] and d['quick_check']=='ok' for d in dbs.values())
assert all(unchanged.values())
assert all(not r['manager_alive'] and not r['supervisor_alive'] and r['listener_closed'] for r in runs)
assert all(d['quick_check']=='ok' for r in runs for d in r['dbs'].values())
assert value['web_status']!='RUNNING' and ntp<=value['ntp_cap'] and http<=value['http_cap']
print(json.dumps(dict(preservation='PASS',baseline_files=value['baseline_files'],changed=changed,original_dbs=len(dbs),
    signals=dbs['data/forward_scanner_v4.db']['counts_after']['signals'],ntp_attempts=ntp,http=http,runs=runs)))
