"""One authorized bounded local-control trial; never retries a failed start.

Requires the dashboard already running with 150s/50 HTTP server-side bounds.
No clock mocking, direct worker launch, or bypass path is provided.
"""
import http.client
import json
from pathlib import Path
import time

OUT=Path(__file__).parent


def request(path,token=None,origin='http://127.0.0.1:8765'):
    conn=http.client.HTTPConnection('127.0.0.1',8765,timeout=8)
    try:
        headers={'Origin':origin}
        if token is not None:
            headers.update({'X-CSRF-Token':token,'Content-Type':'application/json'})
        conn.request('GET' if token is None else 'POST',path,None if token is None else '{}',headers)
        response=conn.getresponse();raw=response.read()
        return response.status,json.loads(raw) if response.getheader('Content-Type','').startswith('application/json') else len(raw)
    finally:conn.close()


def main():
    result=dict(at=time.time(),snapshots=[],http_checks={})
    code,c=request('/api/control');token=c.pop('token')
    assert code==200 and c['seconds']==150 and c['max_requests']==50
    result['bounds']=dict(seconds=c['seconds'],max_requests=c['max_requests'])
    for path in ('/','/analysis','/app.js','/style.css','/api/analysis?group=ALL'):
        code,body=request(path);result['http_checks'][path]=dict(status=code,
            total=body.get('summary',{}).get('total') if isinstance(body,dict) else None)
    result['start_http'],_=request('/api/control/start',token)
    assert result['start_http']==202
    result['duplicate_start_http'],_=request('/api/control/start',token)
    result['external_origin_http'],_=request('/api/control/start',token,'https://example.invalid')
    began=time.monotonic();observing=None
    try:
        while time.monotonic()-began<175:
            code,snapshot=request('/api/snapshot')
            _,op=request('/api/control');op.pop('token',None)
            result['snapshots'].append(dict(at=time.time(),http=code,snapshot=snapshot,operation=op))
            state=snapshot.get('scanner',{})
            if state.get('phase')=='OBSERVING' and observing is None:observing=time.monotonic()
            if state.get('status')=='BLOCKED' and not op.get('busy'):break
            if observing is not None and time.monotonic()-observing>=100:break
            time.sleep(2)
    finally:
        result['stop_http'],_=request('/api/control/stop',token)
        until=time.monotonic()+45
        while time.monotonic()<until:
            _,op=request('/api/control');op.pop('token',None)
            if not op.get('busy'):break
            time.sleep(.5)
        result['final_operation']=op
        _,result['final_snapshot']=request('/api/snapshot')
        result['web_after_stop']=request('/analysis')[0]
        result['ended_at']=time.time()
        (OUT/'full_live_control.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(start=result['start_http'],stop=result['stop_http'],final=op,
                          snapshots=len(result['snapshots'])),ensure_ascii=False))


if __name__=='__main__':main()
