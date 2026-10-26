"""Read-only hashes/counts and terminated-process checks after bounded runs."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_desktop_v50 as desktop

REPORT=Path(__file__).resolve().parent
baseline=json.loads((REPORT/'baseline.json').read_text(encoding='utf-8'))
changed=[];missing=[]
for name,digest in baseline['files'].items():
    path=ROOT/name
    if not path.exists():missing.append(name)
    elif hashlib.sha256(path.read_bytes()).hexdigest()!=digest:changed.append(name)
allowed={'docs/research_status.md','docs/scanner_v50_dashboard.md',
         'data/scanner_console_v410/current.json','data/scanner_dashboard_v50/scanner_pending.json'}
dbs={}
for name,before in baseline['dbs'].items():
    path=ROOT/name
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        counts={t:db.execute('select count(*) from "'+t+'"').fetchone()[0] for t in before['counts']}
        dbs[name]=dict(counts_before=before['counts'],counts_after=counts,counts_equal=counts==before['counts'],
                       quick_check=db.execute('pragma quick_check').fetchone()[0],
                       hash_equal=hashlib.sha256(path.read_bytes()).hexdigest()==baseline['files'][name])
runs=[];ntp_attempts=0;http_requests=0
standalone=json.loads((REPORT/'clock.json').read_text())
ntp_attempts+=len(standalone['measurement']['attempts'])
for name in ('start1','start2'):
    result=json.loads((REPORT/(name+'.json')).read_text())
    state=control.read_json(control.CONTROL/'launches'/result['launch_id']/'state.json')
    root=control.owned_root(state)
    counts={}
    for path in root.glob('*.db'):
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            counts[path.name]=dict(quick_check=db.execute('pragma quick_check').fetchone()[0])
            tables={r[0] for r in db.execute("select name from sqlite_master where type='table'")}
            for table in ('signals','minute_candles','http_calls'):
                if table in tables:counts[path.name][table]=db.execute('select count(*) from '+table).fetchone()[0]
            if 'http_attempts' in tables:
                counts[path.name]['request_statuses']=db.execute('select status,count(*) from http_attempts group by status').fetchall()
                counts[path.name]['endpoints']=db.execute('select endpoint,count(*) from http_attempts group by endpoint').fetchall()
                counts[path.name]['http_statuses']=db.execute("select json_extract(details_json,'$.http_status'),count(*) from http_attempts group by 1").fetchall()
    gates={}
    for stage in ('manager','worker'):
        evidence=json.loads((REPORT/(name+'_'+stage+'_clock.json')).read_text())
        gates[stage]=dict(status=evidence['status'],attempts=len(evidence['measurement']['attempts']),
                          providers=evidence['provider_summary'],execution=evidence['execution'])
        ntp_attempts+=gates[stage]['attempts']
    gates['supervisor']=result['supervisor_clock']
    ntp_attempts+=sum(p['attempts'] for e in result['supervisor_clock'] for p in e['provider_summary'])
    http_requests+=result['actual_http']
    runs.append(dict(name=name,validation=result['validation'],gates=gates,
        requests=result['actual_http'],worker_seconds=result['summary'][0]['elapsed_monotonic_seconds'],
        manager_alive=control.alive(state.get('manager')),supervisor_alive=control.alive(state.get('child')),
        listener_closed=result['listener_closed'],exit=result['exit'],dbs=counts))
sources=['coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_ntp_v49.py',
         'coin_analysis/scanner_desktop_v50.py','coin_analysis/forward_scanner_v43.py',
         'tests/test_scanner_clock_v46.py','tests/test_scanner_ntp_v49.py','tests/test_scanner_start_v53.py']
value=dict(baseline_files=len(baseline['files']),byte_identical=len(baseline['files'])-len(changed)-len(missing),
    changed=changed,missing=missing,unexpected_changes=sorted(set(changed)-allowed),original_dbs=dbs,runs=runs,
    actual_ntp_attempts=ntp_attempts,ntp_cap=baseline['bounds']['max_total_ntp_packets'],actual_http_requests=http_requests,
    http_cap=baseline['bounds']['max_exchange_requests_total'],web_status=desktop.web_state()['status'],
    source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources})
(REPORT/'completion_checks.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
assert not missing and not value['unexpected_changes']
assert all(v['hash_equal'] and v['counts_equal'] and v['quick_check']=='ok' for v in dbs.values())
assert all(not r['manager_alive'] and not r['supervisor_alive'] and r['listener_closed'] for r in runs)
assert ntp_attempts<=value['ntp_cap'] and http_requests<=value['http_cap']
assert value['web_status']!='RUNNING'
print(json.dumps(dict(preservation='PASS',baseline_files=value['baseline_files'],changed=changed,
    dbs=len(dbs),signals=dbs['data/forward_scanner_v4.db']['counts_after']['signals'],
    ntp_attempts=ntp_attempts,http_requests=http_requests,runs=[dict(name=r['name'],seconds=r['worker_seconds'],gates={k:v.get('attempts') if isinstance(v,dict) else sum(p['attempts'] for e in v for p in e['provider_summary']) for k,v in r['gates'].items()}) for r in runs])))
