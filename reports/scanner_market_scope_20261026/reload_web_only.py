"""Replace an idle dashboard only; protect the user's existing collector."""
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from coin_analysis import scanner_control_v410 as control,scanner_desktop_v50 as desktop
REPORT=Path(__file__).resolve().parent


def get(path):
    conn=http.client.HTTPConnection('127.0.0.1',8765,timeout=8)
    try:
        conn.request('GET',path);r=conn.getresponse();body=r.read();assert r.status==200
        return json.loads(body) if path.startswith('/api/') else body.decode('utf-8')
    finally:conn.close()


before=control.current();web=desktop.web_state();status=get('/api/control');status.pop('token',None)
assert before['status']=='RUNNING' and before['phase']=='OBSERVING'
assert web['status']=='RUNNING' and not status['busy']
root=control.owned_root(before)
worker=control.identity(control.read_json(root/'supervisor.json')['worker_pid'])
assert control.alive(before['manager']) and control.alive(before['child']) and control.alive(worker)
markers=dict(runtime_stop=(root/'STOP').exists(),control_stop=control.stop_marker(before).exists())
assert not markers['runtime_stop'] and not markers['control_stop']
result=dict(before_launch=before['launch_id'],manager=before['manager'],supervisor=before['child'],worker=worker,
            web_before=web['process'],limits=dict(seconds=status['seconds'],max_requests=status['max_requests']),
            before_at=time.time(),before_markers=markers,scanner_start_calls=0,scanner_stop_calls=0)
assert desktop.stop_web()==0
assert control.alive(before['manager']) and control.alive(before['child']) and control.alive(worker)
new=desktop.ensure_web(status['seconds'],status['max_requests'])
result['web_after']=new['process']
snapshot=get('/api/snapshot');current=control.current()
assert current['launch_id']==before['launch_id']
assert current['manager']==before['manager'] and current['child']==before['child']
assert control.alive(before['manager']) and control.alive(before['child']) and control.alive(worker)
assert not (root/'STOP').exists() and not control.stop_marker(before).exists()
assert snapshot['scanner']['live_collecting']
cli=control.snapshot()['market_scope'];shown=snapshot['scanner']['market_scope']
assert cli['scan']==shown['scan'] and cli['total']==shown['total']
result['scope']=shown;result['cli_scope']=cli
result['independent_db_counts']={}
for exchange in control.observer.v42.HOSTS:
    with sqlite3.connect((root/(exchange.lower()+'.db')).as_uri()+'?mode=ro',uri=True) as db:
        result['independent_db_counts'][exchange]=dict(markets=db.execute('select count(*) from scanner_state').fetchone()[0],
            followup=db.execute("select count(distinct s.market) from signals s join live_horizons h using(signal_id) where h.status='PENDING'").fetchone()[0])
html=get('/');assert 'id="nav-live"' in html
assert all('id="'+name+'"' in html for name in ('markets','total-markets','focus-markets'))
assert 'id="nav-analysis"' in get('/analysis')
result.update(after_at=time.time(),scanner_phase=current['phase'],all_three_collector_identities_preserved=True,
              scanner_stop_markers_created=False,web_kept_running=True,html_three_scope_fields=True,
              independent_venue_pairs=sum(v['markets'] for v in result['independent_db_counts'].values()))
(REPORT/'web_reload_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
(REPORT/'snapshot.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
print(json.dumps(dict(scope=shown,collector_preserved=True,web_running=True)))
