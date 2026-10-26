"""Bounded production dashboard API, with browser-like snapshot polling.

No analysis refresh, operating DB writes, clock mock, trading or process kill.
One invocation per fixed name; at most two starts under baseline.json bounds.
"""
import http.client
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from coin_analysis import scanner_control_v410 as control,scanner_dashboard_v50 as dashboard
from reports.scanner_start_v53_20261026.verify_live import evidence

REPORT=Path(__file__).resolve().parent


def run(name):
    assert name in ('start1','start2') and not (REPORT/(name+'.json')).exists()
    old=control.current()
    assert not old or not(control.alive(old.get('manager')) or control.alive(old.get('child')))
    result=dict(bounds=dict(seconds=120,http=40,ntp=24),events=[],snapshots=[],poll_errors=[])
    logger=dashboard.rotating_logger(REPORT)
    server=dashboard.Server(('127.0.0.1',8765),logger=logger,seconds=120,max_requests=40)
    thread=threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.1),daemon=True);thread.start()
    token=None;poll_stop=threading.Event()

    def request(method,path):
        nonlocal token
        conn=http.client.HTTPConnection('127.0.0.1',8765,timeout=5)
        try:
            headers={'Origin':'http://127.0.0.1:8765','Content-Type':'application/json','X-CSRF-Token':token or ''} if method=='POST' else {}
            conn.request(method,path,body='{}' if method=='POST' else None,headers=headers)
            response=conn.getresponse();body=response.read()
            value=json.loads(body) if path.startswith('/api/') else dict(bytes=len(body))
            if value.get('token'):token=value.pop('token')
            return response.status,value
        finally:conn.close()

    def poll():
        while not poll_stop.is_set():
            try:
                code,value=request('GET','/api/snapshot')
                result['snapshots'].append(dict(at=time.time(),http=code,scanner=value.get('scanner'),errors=value.get('errors')))
            except Exception as exc:result['poll_errors'].append(dict(at=time.time(),error_type=type(exc).__name__))
            poll_stop.wait(5)

    poller=None
    def wait_operation(seconds):
        until=time.monotonic()+seconds;last=None
        while time.monotonic()<until:
            code,value=request('GET','/api/control');assert code==200
            phase=value.get('scanner',{}).get('phase')
            if phase!=last:
                result['events'].append(dict(at=time.time(),phase=phase,state=value.get('state')))
                print(name,phase,value.get('state'),flush=True);last=phase
            if not value.get('busy'):return value
            time.sleep(.5)
        raise TimeoutError('Bounded control confirmation wait')

    try:
        assert request('GET','/')[0]==200
        assert request('GET','/api/control')[0]==200 and token
        poller=threading.Thread(target=poll,daemon=True);poller.start()
        result['start_http'],_=request('POST','/api/control/start');assert result['start_http']==202
        result['started']=wait_operation(90)
        state=control.current();assert state and state['launch_id']!=(old or {}).get('launch_id')
        result['launch_id']=state['launch_id'];root=control.owned_root(state)
        (REPORT/(name+'_manager_clock.json')).write_text(json.dumps(evidence(state.get('clock_evidence') or {}),indent=2),encoding='utf-8')
        if result['started']['state']=='SUCCEEDED':
            assert result['started']['process_alive'] and result['started']['scanner']['phase']=='OBSERVING'
            result['duplicate_http']=request('POST','/api/control/start')[0];assert result['duplicate_http']==409
            # The display cache may precede readiness by at most four seconds.
            until=time.monotonic()+9
            while time.monotonic()<until:
                _,snapshot=request('GET','/api/snapshot')
                if snapshot['scanner'].get('live_collecting'):break
                time.sleep(.5)
            result['observing_snapshot']=snapshot
            assert snapshot['scanner']['live_collecting']
            assert all(row['status']=='CONNECTED' for row in snapshot['scanner']['connections'].values())
            result['committed_candles_before_stop']={}
            for exchange in control.observer.v42.HOSTS:
                with sqlite3.connect((root/(exchange.lower()+'.db')).as_uri()+'?mode=ro',uri=True) as db:
                    result['committed_candles_before_stop'][exchange]=db.execute('select count(*) from minute_candles').fetchone()[0]
            assert all(v>0 for v in result['committed_candles_before_stop'].values())
        result['stop_requested_at']=time.time()
        result['stop_http'],_=request('POST','/api/control/stop');assert result['stop_http']==202
        result['stopped']=wait_operation(55)
        until=time.monotonic()+5
        while control.alive(control.current().get('manager')) and time.monotonic()<until:time.sleep(.1)
        final=control.current()
        result['manager_alive']=control.alive(final.get('manager'));result['supervisor_alive']=control.alive(final.get('child'))
        result['final']={k:control.snapshot(final).get(k) for k in ('status','phase','reason','db_saved','signals','clock')}
        result['summary']=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'runs').glob('*.summary.json')]
        result['exit']=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'runs').glob('*.exit.json')]
        result['actual_http']=sum(v['requests'] for v in result['summary'])
        result['web_after_stop']=request('GET','/')[0]
        assert result['actual_http']<=40 and result['web_after_stop']==200
        assert not result['manager_alive'] and not result['supervisor_alive']
        if result['started']['state']=='SUCCEEDED':
            assert result['stopped']['state']=='SUCCEEDED' and result['final']['db_saved'].startswith('SAVED')
            assert result['actual_http']>0
            assert all(e['worker_reaped'] and not e['forced_kill'] and e['worker_returncode']==0 for e in result['exit'])
        result['validation']='PASS' if result['started']['state']=='SUCCEEDED' else 'START_FAILED'
    except BaseException as exc:
        result['error']=dashboard.exception_details(exc);raise
    finally:
        state=control.current()
        if state and state.get('launch_id')!=(old or {}).get('launch_id') and (control.alive(state.get('manager')) or control.alive(state.get('child'))):
            request('POST','/api/control/stop');wait_operation(55)
        poll_stop.set()
        if poller:poller.join(7)
        server.operations.close();server.analysis.close();server.shutdown();server.server_close();thread.join(3)
        result['listener_closed']=not thread.is_alive()
        for handler in logger.handlers[:]:handler.flush();handler.close();logger.removeHandler(handler)
        (REPORT/(name+'.json')).write_text(json.dumps(result,indent=2,ensure_ascii=True),encoding='utf-8')
    print(json.dumps({k:result.get(k) for k in ('validation','actual_http','committed_candles_before_stop','manager_alive','supervisor_alive','listener_closed','final','poll_errors')}),flush=True)


if __name__=='__main__':run(sys.argv[1])
