"""Explicit, bounded supervised validation. Never refresh analysis or source DBs.

Run `python -B reports/.../verify_live.py clock|start1|start2` from project root.
Limits are fixed in baseline.json before network access. No automatic retry.
"""
import http.client
import json
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from coin_analysis import scanner_clock_v45 as clock
from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_dashboard_v50 as dashboard

REPORT=Path(__file__).resolve().parent


def save(name,value):
    (REPORT/(name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=True),encoding='utf-8')


def evidence(value):
    result={k:value.get(k) for k in ('at','completed_at','status','reason','blockers','warnings',
        'clock_policy','elapsed_monotonic_seconds','wall_monotonic_difference_seconds','execution',
        'provider_summary','external_assessment','measurement_freshness','root_crosscheck')}
    result['windows_status']={k:v for k,v in value.get('windows_status',{}).items()
                              if k not in ('source','last_sync','last_sync_text')}
    measurement=value.get('measurement',{})
    result['measurement']={k:measurement.get(k) for k in ('probe_policy','max_packets','required_samples',
        'timeout_seconds','internal_seconds','elapsed_monotonic_seconds','abort_reason',
        'host_interval_seconds','global_interval_seconds','backoff_seconds')}
    keys=('host','slot_id','attempt_number','status','phase','error_type','retryable',
          'local_sent_at','local_received_at','offset_seconds','uncertainty_seconds',
          'attempt_elapsed_seconds','receive_elapsed_seconds','dns_seconds')
    result['measurement']['attempts']=[{k:r[k] for k in keys if k in r} for r in measurement.get('attempts',[])]
    return result


def inactive():
    state=control.current()
    assert not state or not(control.alive(state.get('manager')) or control.alive(state.get('child'))), 'Protect existing active scanner'


def run_start(name):
    inactive()
    result=dict(seconds_cap=120,http_cap=40,ntp_packet_cap=24,analysis_refresh=False,events=[])
    server=dashboard.Server(('127.0.0.1',0),seconds=120,max_requests=40)
    thread=threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.1),daemon=True)
    thread.start();old=control.current();token=old.get('launch_id') if old else None

    def request(method,path,origin=None):
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        try:
            headers={}
            if method=='POST':headers={'Origin':origin or f'http://127.0.0.1:{server.server_port}',
                'Content-Type':'application/json','X-CSRF-Token':server.csrf}
            conn.request(method,path,body='{}' if method=='POST' else None,headers=headers)
            response=conn.getresponse();body=response.read()
            value=json.loads(body) if path.startswith('/api/') else dict(bytes=len(body))
            value.pop('token',None)
            return response.status,value
        finally:conn.close()

    def wait_operation(limit):
        deadline=time.monotonic()+limit;last=None
        while time.monotonic()<deadline:
            status,value=request('GET','/api/control')
            phase=value.get('scanner',{}).get('phase')
            if phase!=last:
                result['events'].append(dict(at=time.time(),phase=phase));last=phase
                print(name,phase,flush=True)
            if not value.get('busy'):return value
            time.sleep(.4)
        raise TimeoutError('Bounded operation wait exhausted')

    try:
        result['foreign_origin_status']=request('POST','/api/control/start','https://example.invalid')[0]
        assert result['foreign_origin_status']==403
        result['start_http']=request('POST','/api/control/start')[0]
        assert result['start_http']==202
        started=wait_operation(90);result['started']=started
        state=control.current();assert state and state['launch_id']!=token
        token=state['launch_id'];result['launch_id']=token
        save(name+'_manager_clock',evidence(state.get('clock_evidence') or {}))
        if started['state']=='SUCCEEDED':
            assert started['process_alive'] and started['scanner']['phase']=='OBSERVING'
            result['manager_alive_at_readiness']=control.alive(state.get('manager'))
            result['supervisor_alive_at_readiness']=control.alive(state.get('child'))
            result['duplicate_status']=request('POST','/api/control/start')[0]
            assert result['duplicate_status']==409
        result['stop_http']=request('POST','/api/control/stop')[0]
        assert result['stop_http']==202
        result['stopped']=wait_operation(55)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and control.alive(control.current().get('manager')):time.sleep(.1)
        final=control.current();root=control.owned_root(final)
        result['final']={k:control.snapshot(final).get(k) for k in ('status','phase','reason','db_saved','clock','signals','markets','venue_pairs')}
        result['manager_alive_after_stop']=control.alive(final.get('manager'))
        result['supervisor_alive_after_stop']=control.alive(final.get('child'))
        result['dashboard_http_after_stop']=request('GET','/')[0]
        result['snapshot_after_stop']=request('GET','/api/snapshot')[1]
        result['summary']=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'runs').glob('*.summary.json')]
        result['exit']=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'runs').glob('*.exit.json')]
        for path in root.glob('events*.jsonl'):
            for line in path.read_text(encoding='utf-8').splitlines():
                row=json.loads(line)
                if row.get('kind')=='CLOCK_CHECK':save(name+'_worker_clock',evidence(row['evidence']))
        log=control.CONTROL/'launches'/token/'launch.log'
        result['supervisor_clock']=[]
        if log.exists():
            for line in log.read_text(encoding='utf-8').splitlines():
                pos=line.find('{"event": "CLOCK_CHECK"')
                if pos>=0:
                    try:result['supervisor_clock'].append(json.loads(line[pos:]))
                    except ValueError:pass
        result['actual_http']=sum(s['requests'] for s in result['summary'])
        assert result['actual_http']<=40
        assert not result['manager_alive_after_stop'] and not result['supervisor_alive_after_stop']
        assert result['dashboard_http_after_stop']==200
        if started['state']=='SUCCEEDED':
            assert result['stopped']['state']=='SUCCEEDED'
            assert result['final']['db_saved'].startswith('SAVED')
            assert result['actual_http']>0
            assert all(e['worker_reaped'] and not e['forced_kill'] and e['worker_returncode']==0 for e in result['exit'])
        result['validation']='PASS' if started['state']=='SUCCEEDED' else 'SAFETY_BLOCKED'
    except BaseException as exc:
        result['error_type']=type(exc).__name__;raise
    finally:
        state=control.current()
        if state and state.get('launch_id')!= (old or {}).get('launch_id') and (control.alive(state.get('manager')) or control.alive(state.get('child'))):
            request('POST','/api/control/stop');wait_operation(55)
        server.operations.close();server.analysis.close()
        server.shutdown();server.server_close();thread.join(3)
        result['listener_closed']=not thread.is_alive()
        save(name,result)
    print(json.dumps({k:result.get(k) for k in ('validation','actual_http','manager_alive_after_stop','supervisor_alive_after_stop','listener_closed','final')}),flush=True)


if __name__=='__main__':
    mode=sys.argv[1]
    assert mode in ('clock','start1','start2')
    assert not (REPORT/(mode+'.json')).exists(),'No repeated probes under same run name'
    if mode=='clock':
        inactive();value=evidence(clock.verify_clock());save('clock',value)
        print(json.dumps(dict(status=value['status'],reason=value['reason'],providers=value['provider_summary'])),flush=True)
    else:run_start(mode)
