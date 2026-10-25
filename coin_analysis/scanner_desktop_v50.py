"""BAT orchestration, reusing V4.10 admission/STOP and a separately owned web.

Only an explicit start action launches LIVE. Viewing/status never probes time or
exchanges. No automatic relaunch, process kill, system setting, or engine change.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
import webbrowser

from . import scanner_control_v410 as control
from . import scanner_dashboard_v50 as dashboard

WEB = control.DATA_DIR/'scanner_dashboard_v50'
ENTRY = control.PROJECT_ROOT/'scripts'/'coin_api_entry.py'


def web_state():
    path=WEB/'current.json'
    if not path.exists(): return dict(status='STOPPED')
    state=control.read_json(path)
    if not re.fullmatch('[0-9a-f]{32}',state.get('token','')): raise ValueError('Invalid web identity')
    running=control.alive(state.get('process'))
    return dict(state,status='RUNNING' if running and state['status']=='RUNNING' else
                'BLOCKED' if running or state['status']!='STOPPED' else 'STOPPED')


def stop_path(token):
    if not re.fullmatch('[0-9a-f]{32}',token): raise ValueError('Invalid web identity')
    return WEB/('STOP_'+token)


def serve(token):
    stop_path(token)  # Validate before any write.
    with control.observer.scanner.exclusive(WEB/'listener'):
        logger=dashboard.rotating_logger(WEB)
        state=dict(token=token,process=control.identity(os.getpid()),status='BLOCKED',started_at=time.time())
        server=None; previous={}; stopped=threading.Event()
        try:
            server=dashboard.Server((dashboard.HOST,dashboard.PORT),logger=logger)
            server.timeout=.5
            state['status']='RUNNING'
            control.write_metadata(WEB/'current.json',state)
            for sig in (signal.SIGINT,signal.SIGTERM):
                previous[sig]=signal.signal(sig,lambda *_:stopped.set())
            logger.info('Loopback dashboard started')
            while not stopped.is_set() and not stop_path(token).exists():
                server.handle_request()
            state['status']='STOPPED';return 0
        except Exception as exc:
            state.update(status='BLOCKED',reason=type(exc).__name__)
            logger.warning('Dashboard blocked (%s)',type(exc).__name__);return 2
        finally:
            if server: server.server_close()
            state['ended_at']=time.time()
            control.write_metadata(WEB/'current.json',state)
            for sig,handler in previous.items(): signal.signal(sig,handler)
            for handler in logger.handlers[:]:
                handler.flush();handler.close();logger.removeHandler(handler)


def spawn(arguments):
    env=dict(os.environ)
    env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1')
    return subprocess.Popen([sys.executable,'-I',str(ENTRY),*arguments],cwd=control.PROJECT_ROOT,env=env,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)


def ensure_web():
    existing=web_state()
    if existing['status']=='RUNNING': return existing
    if control.alive(existing.get('process')): raise RuntimeError('WEB_STOP_UNCONFIRMED; no relaunch')
    # No port probing/kill: child atomically binds with SO_EXCLUSIVEADDRUSE.
    if sum(p.stat().st_size for p in WEB.rglob('*') if p.is_file())>=8*1024*1024:
        raise RuntimeError('WEB_STORAGE_LIMIT')
    if control.observer.shutil.disk_usage(WEB).free<256*1024*1024:
        raise RuntimeError('FREE_DISK_LIMIT')
    token=uuid.uuid4().hex
    child=spawn(['_serve','--token',token])
    until=time.monotonic()+8
    while time.monotonic()<until:
        state=web_state()
        if state.get('token')==token and state['status']=='RUNNING': return state
        if child.poll() is not None:
            child.wait();raise RuntimeError('WEB_PORT_OR_START_FAILURE; port 8765 may belong to another program; nothing was killed')
        time.sleep(.1)
    # Persist ownership even if a delayed child has not published readiness.
    control.write_metadata(WEB/'pending.json',dict(token=token,process=control.identity(child.pid)))
    stop_path(token).touch(exist_ok=True)
    raise RuntimeError('WEB_START_TIMEOUT; safe STOP requested; no LIVE started')


def stop_web(wait=10):
    states=[web_state()]
    pending=WEB/'pending.json'
    if pending.exists(): states.append(control.read_json(pending))
    for state in states:
        if not control.alive(state.get('process')): continue
        stop_path(state['token']).touch(exist_ok=True)
        until=time.monotonic()+wait
        while control.alive(state.get('process')) and time.monotonic()<until: time.sleep(.1)
        if control.alive(state.get('process')):
            print('Web : BLOCKED / STOP not confirmed; no force kill');return 2
    latest=web_state()
    if latest.get('token') and not control.alive(latest.get('process')):
        latest.update(status='STOPPED',stop_confirmed_at=time.time())
        control.write_metadata(WEB/'current.json',latest)
    print('Web          : STOPPED / listener closed and log flushed');return 0


def start(seconds,max_requests,dashboard_only=False,no_browser=False):
    if not 30<=seconds<=control.observer.MAX_SECONDS or not 26<=max_requests<=control.observer.MAX_REQUESTS:
        raise ValueError('Outside existing Scanner safety limits')
    WEB.mkdir(parents=True,exist_ok=True)
    with control.observer.scanner.exclusive(WEB/'launcher'):
        pending=WEB/'pending.json'
        if pending.exists() and control.alive(control.read_json(pending).get('process')):
            raise RuntimeError('WEB_START_PENDING; use stop_coin_api.bat')
        ensure_web()
        if not dashboard_only:
            old=control.current()
            if old and (control.alive(old.get('manager')) or control.alive(old.get('child'))):
                print('Scanner      : already managed; no duplicate start')
            else:
                # Existing V4.10 start owns its lock, full clock gates and scoped
                # observation child. Backgrounding changes no admission policy.
                manager=spawn(['_scanner','--seconds',str(seconds),'--max-requests',str(max_requests)])
                until=time.monotonic()+35
                while time.monotonic()<until:
                    state=control.current()
                    if state and (not old or state['launch_id']!=old['launch_id']) and state['phase']!='PRECHECK': break
                    if manager.poll() is not None: manager.wait();break
                    time.sleep(.2)
                if manager.poll() is not None and control.current()==old:
                    print('Scanner      : BLOCKED / admission or duplicate lock; see status/logs')
        value=control.snapshot();control.render(value)
        print(f'Web          : RUNNING\nDashboard    : {dashboard.URL}\nSafety       : SUPERVISED ONLY; 24h unattended NOT_READY',flush=True)
        if not no_browser:
            try:
                if not webbrowser.open(dashboard.URL,new=2): print('Browser      : open the Dashboard URL manually')
            except Exception: print('Browser      : open the Dashboard URL manually')
        return 2 if not dashboard_only and value['status']=='BLOCKED' else 0


def main(argv=None):
    parser=argparse.ArgumentParser(description='CHIO COIN SCANNER: loopback dashboard; observation only.')
    parser.add_argument('action',choices=['start','stop','status','_serve','_scanner'])
    parser.add_argument('--seconds',type=int,default=control.observer.MAX_SECONDS)
    parser.add_argument('--max-requests',type=int,default=control.observer.MAX_REQUESTS)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--dashboard-only',action='store_true',help='Stored-data view only; never starts Scanner')
    parser.add_argument('--no-browser',action='store_true',help='Print localhost URL without opening browser')
    parser.add_argument('--token')
    args=parser.parse_args(argv)
    try:
        if args.check: return control.main(['status','--check'])
        if args.action=='_serve': return serve(args.token or '')
        if args.action=='_scanner': return control.start(args.seconds,args.max_requests)
        if args.action=='start': return start(args.seconds,args.max_requests,args.dashboard_only,args.no_browser)
        if args.action=='stop':
            try: scanner_code=control.stop()
            finally: web_code=stop_web()
            return max(scanner_code,web_code)
        value=control.snapshot();web=web_state()
        if args.json: print(json.dumps(dict(scanner=value,web=web),ensure_ascii=False,allow_nan=False))
        else:
            control.render(value);print(f"Web          : {web['status']}\nDashboard    : {dashboard.URL}")
        return 0
    except Exception as exc:
        print('Status : BLOCKED\nReason : '+str(exc)+'\nAction : '+control.guidance(str(exc)),flush=True)
        return 2


if __name__=='__main__': raise SystemExit(main())
