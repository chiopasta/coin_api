"""Supervised console management of the existing V4.3 observer; no engine.

STOP is a scoped file event, never a PID kill. Windows creation times prevent
recycled PIDs from being treated as owned processes. No automatic relaunch.
"""
import argparse
from contextlib import closing
import ctypes
import errno
from ctypes import wintypes
from datetime import datetime,timezone,timedelta
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

from . import forward_scanner_v43 as observer
from .paths import PROJECT_ROOT,DATA_DIR

CONTROL=DATA_DIR/'scanner_console_v410'
MAX_CONTROL_BYTES=32*1024*1024
STOP_WAIT_SECONDS=45
KST=timezone(timedelta(hours=9))


def read_json(path):
    """Read fresh metadata, tolerating a brief Windows replace/share collision.

    Never reuse an older state. Size/JSON errors and persistent access failures
    still raise; only Windows access/sharing failures retry for at most 0.5s.
    """
    path=Path(path)
    began=time.monotonic();until=began+.5;retries=0
    while True:
        try:
            if path.stat().st_size>128*1024:raise ValueError('Metadata size limit')
            with path.open('r',encoding='utf8') as stream:body=stream.read(128*1024+1)
            if len(body)>128*1024:raise ValueError('Metadata size limit')
            value=json.loads(body)
            if retries:
                logging.getLogger('scanner_dashboard').info(json.dumps(dict(at=time.time(),event='METADATA_READ_RECOVERED',
                    metadata_kind='STATE' if path.name=='state.json' else 'CURRENT' if path.name=='current.json' else 'OTHER',
                    retries=retries,elapsed_seconds=time.monotonic()-began)))
            return value
        except PermissionError as exc:
            winerror=getattr(exc,'winerror',None)
            transient=winerror in (5,32,33) or winerror is None and exc.errno==errno.EACCES
            if os.name!='nt' or not transient or time.monotonic()>=until:raise
            retries+=1;time.sleep(.01)


def write_metadata(path,value):
    """Bounded retry of Windows metadata replacement during a brief reader.

    Applies only to management JSON. No DB writes or clock admission changes.
    Persistent sharing/permission errors still fail closed within 0.5 seconds.
    """
    until=time.monotonic()+.5
    while True:
        try:
            observer.write_json(path,value);return
        except PermissionError as exc:
            if os.name!='nt' or getattr(exc,'winerror',None) not in (5,32,33) or time.monotonic()>=until:raise
            time.sleep(.01)


def process_birth(pid):
    """Return a live Windows process's creation FILETIME, or None if exited."""
    if not isinstance(pid,int) or pid<=0:return None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:return None
        raise OSError('Process inspection unavailable; no process action taken')
    try:
        code=wintypes.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise OSError('Cannot query process exit')
        if code.value!=259:return None
        stamps=[wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(s) for s in stamps]):raise OSError('Cannot query process creation')
        return (stamps[0].dwHighDateTime<<32)|stamps[0].dwLowDateTime
    finally:kernel.CloseHandle(handle)


def identity(pid):return dict(pid=pid,birth=process_birth(pid))


def alive(value):
    return bool(value and value.get('birth') is not None and process_birth(value.get('pid'))==value['birth'])


def owned_root(state):
    token=state['launch_id']
    if not re.fullmatch('[0-9a-f]{32}',token):raise ValueError('Invalid managed launch ID')
    root=Path(state['root'])
    expected=observer.RUNTIME_ROOT/('console_'+token)
    if root!=expected or root.resolve().parent!=observer.RUNTIME_ROOT.resolve() or root.is_symlink():
        raise ValueError('Managed runtime path rejected; no STOP written')
    return root


def current():
    pointer=CONTROL/'current.json'
    if not pointer.exists():return None
    token=read_json(pointer)['launch_id']
    if not re.fullmatch('[0-9a-f]{32}',token):raise ValueError('Invalid launch pointer')
    state=read_json(CONTROL/'launches'/token/'state.json')
    if state['launch_id']!=token:raise ValueError('Launch identity mismatch')
    owned_root(state)
    return state


def state_path(state):return CONTROL/'launches'/state['launch_id']/'state.json'


def stop_marker(state):return CONTROL/'launches'/state['launch_id']/'STOP_REQUESTED'


def persist(state):
    state['updated_at']=time.time()
    write_metadata(state_path(state),state)


def clock_view(evidence,now):
    if not evidence:return 'UNKNOWN'
    age=now-evidence.get('completed_at',now+1)
    if evidence.get('status')!='VERIFIED':return 'FAIL: '+evidence.get('reason','UNKNOWN')
    if not 0<=age<=observer.clock_guard.RECHECK_SECONDS+15:return 'UNKNOWN (last PASS is stale)'
    basis='; fresh direct NTP cross-check; Windows root quality warning' if evidence.get('root_crosscheck',{}).get('status')=='VERIFIED' else ''
    return f'PASS (check age {age:.1f}s; periodic recheck 600s{basis})'


def recent_clock(root,fallback):
    latest=fallback
    for path in root.glob('events*.jsonl'):
        if path.stat().st_size>observer.LOG_BYTES:continue
        for line in path.read_text(encoding='utf8').splitlines():
            try:
                row=json.loads(line)
                if row.get('kind')=='CLOCK_CHECK' and (not latest or row['evidence']['at']>latest['at']):latest=row['evidence']
            except (ValueError,KeyError):continue
    return latest


def db_snapshot(root):
    totals=[];latest=[];collected=[];errors=[];exchanges=[];scopes=[];size=0
    for exchange in observer.v42.HOSTS:
        path=root/(exchange.lower()+'.db')
        size+=sum(p.stat().st_size for p in (path,Path(str(path)+'-wal'),Path(str(path)+'-shm')) if p.exists())
        if not path.exists():continue
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
            db.execute('PRAGMA query_only=ON')
            totals.append(db.execute('SELECT COUNT(*) FROM signals').fetchone()[0])
            latest.append(db.execute('SELECT MAX(detected_at) FROM signals').fetchone()[0])
            # Receipt joined to a committed source candle, not a synthetic tick.
            collected.append(db.execute('SELECT MAX(r.first_received_at) FROM candle_receipts r JOIN minute_candles c USING(market,ts)').fetchone()[0])
            errors.extend(f'{exchange} {m}: {e}' for m,e in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL'))
            scopes.append({r[0] for r in db.execute('SELECT market FROM scanner_state')})
            exchanges.append(exchange)
    return dict(signals=sum(totals) if len(totals)==2 else None,last_signal=max((t for t in latest if t is not None),default=None),
        collected=max((t for t in collected if t is not None),default=None),exchanges=exchanges,size=size if exchanges else None,
        errors=errors,markets=len(set().union(*scopes)) if len(scopes)==2 else None,
        venue_pairs=sum(len(s) for s in scopes) if len(scopes)==2 else None,
        signal_pairs=sum(len(s-{'KRW-BTC'}) for s in scopes) if len(scopes)==2 else None)


def snapshot(state=None):
    state=current() if state is None else state
    if state is None:return dict(status='STOPPED',phase='NO_MANAGED_RUN',clock='UNKNOWN',db_saved='UNKNOWN',signals=None)
    root=owned_root(state);result=dict(state)
    active=alive(state.get('manager')) or alive(state.get('child'))
    if active and state['phase']!='TERMINAL':result['status']='BLOCKED' if state['status']=='BLOCKED' else 'RUNNING'
    elif state['phase']!='TERMINAL':
        result.update(status='BLOCKED',reason='PROCESS_EXITED_WITHOUT_FINAL_STATE; save UNKNOWN')
        if root.exists():
            try:
                final=saved_result(root)
                if final['ok']:result.update(status='STOPPED',phase='TERMINAL',**{k:v for k,v in final.items() if k!='ok'})
            except (OSError,ValueError,sqlite3.DatabaseError):pass
    result['clock']=clock_view(recent_clock(root,state.get('clock_evidence')),time.time())
    result['warnings']=['SUPERVISED ONLY; 24-hour unattended operation NOT_READY']
    if active and not alive(state.get('manager')):result['warnings'].append('Control console lost; use stop_coin_api.bat')
    if active and state['phase']!='TERMINAL' and 'started_monotonic' in state:
        result['elapsed_monotonic_seconds']=max(0,time.monotonic()-state['started_monotonic'])
    try:result.update(db_snapshot(root))
    except (OSError,sqlite3.DatabaseError) as exc:result.update(signals=None,db_read_error=str(exc))
    if result.get('signals')==0:result['warnings'].append('No signals yet; zero is a normal observation result')
    return result


def stamp(value):
    return datetime.fromtimestamp(value,KST).strftime('%Y-%m-%d %H:%M:%S KST') if value is not None else 'UNKNOWN'


def render(value):
    unknown=lambda key:'UNKNOWN' if value.get(key) is None else value[key]
    rows=[('Status',value['status']),('Phase',value.get('phase','UNKNOWN')),('Mode','OBSERVATION ONLY'),
        ('Exchanges',' / '.join(value.get('exchanges',[])) or 'UNKNOWN'),
        ('Markets',f"{value['markets']} unique / {value['venue_pairs']} venue pairs ({value['signal_pairs']} signal pairs)" if value.get('markets') is not None else 'UNKNOWN'),
        ('Clock',value.get('clock','UNKNOWN')),('Signals',unknown('signals')),
        ('Started',stamp(value.get('started_at'))),('Duration',f"{value['elapsed_monotonic_seconds']:.1f}s" if value.get('elapsed_monotonic_seconds') is not None else 'UNKNOWN'),
        ('Last signal',stamp(value.get('last_signal'))),('Collected',stamp(value.get('collected'))),
        ('DB save',value.get('db_saved','UNKNOWN')),('DB bytes',unknown('size')),
        ('Recent error','; '.join(value.get('errors',[])) or value.get('db_read_error') or (value.get('reason') if value['status']=='BLOCKED' else None) or ('NONE' if value.get('markets') else 'UNKNOWN')),
        ('Last result',value.get('reason') or 'UNKNOWN'),
        ('Warning','; '.join(value.get('warnings',[])) or 'SUPERVISED ONLY; 24h NOT_READY'),
        ('Safety cap',f"{value['seconds']}s / {value['max_requests']} HTTP" if 'seconds' in value else 'UNKNOWN'),
        ('Stop','stop_coin_api.bat')]
    print('\n'+'='*60)
    for key,text in rows:print(f'{key:<13}: {text}')
    print('='*60,flush=True)


def guidance(reason):
    if 'CLOCK' in reason:
        return 'Check Windows time sync / W32Time and UDP123/DNS access; retry only after recovery. Do not widen the 1s limit.'
    if 'Another scanner' in reason or 'DUPLICATE' in reason:
        return 'Use status_coin_api.bat and stop_coin_api.bat for the owned run. Do not kill other Python processes.'
    return 'Inspect status and the managed launch log; fix the reported environment/storage problem before starting again.'


def saved_result(root):
    summaries=list((root/'runs').glob('*.summary.json'))
    if len(summaries)!=1:return dict(ok=False,reason='RUNNER_EXIT_BEFORE_FINAL_SUMMARY; inspect launch.log',db_saved='UNKNOWN')
    summary=read_json(summaries[0]);exit_info=read_json(root/'runs'/(summary['run_id']+'.exit.json'))
    ok=not summary['close_errors'] and exit_info['worker_reaped'] and not exit_info['forced_kill'] and exit_info['worker_returncode']==0
    if not any((root/(e.lower()+'.db')).exists() for e in observer.v42.HOSTS) and summary['requests']==0 and summary['reason']=='STOP_REQUESTED':
        return dict(ok=ok,reason='CANCELLED_BEFORE_COLLECTION',db_saved='UNKNOWN / no observation DB was created')
    for exchange in observer.v42.HOSTS:
        path=root/(exchange.lower()+'.db')
        if not path.exists():ok=False;continue
        with observer.ops.readonly(path) as db:
            ok=ok and db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        wal=Path(str(path)+'-wal')
        if wal.exists() and wal.stat().st_size:ok=False
    return dict(ok=ok,reason=summary['reason'],db_saved='SAVED / WAL checkpoint and normal close confirmed' if ok else 'UNKNOWN / inspect final summary',
        run_id=summary['run_id'],summary_status=summary['status'])


def stop(wait=STOP_WAIT_SECONDS):
    state=current()
    if state is None:render(snapshot());print('No managed Scanner process.');return 0
    if (state['phase']=='TERMINAL' and not alive(state.get('child'))) or not (alive(state.get('manager')) or alive(state.get('child'))):
        render(snapshot(state));print('No owned live process; no signal or kill sent.');return 0
    stop_marker(state).touch(exist_ok=True)
    root=owned_root(state);until=time.monotonic()+wait
    while time.monotonic()<until:
        if root.exists():(root/'STOP').touch(exist_ok=True)
        latest=read_json(state_path(state))
        if latest['phase']=='TERMINAL' and not alive(latest.get('child')):
            render(snapshot(latest));return 0 if latest['status']=='STOPPED' else 2
        if not alive(latest.get('manager')) and not alive(latest.get('child')):
            final=saved_result(root) if root.exists() else dict(ok=True,reason='Stopped before dataset creation',db_saved='UNKNOWN')
            latest.update(status='STOPPED' if final['ok'] else 'BLOCKED',phase='TERMINAL',**{k:v for k,v in final.items() if k!='ok'})
            persist(latest);render(snapshot(latest));return 0 if final['ok'] else 2
        time.sleep(.5)
    print('Status : BLOCKED\nSTOP requested; exit/flush not confirmed within 45s. No force kill was sent.\nRun status_coin_api.bat again.');return 2


def start(seconds,max_requests,request_id=None):
    if not 30<=seconds<=observer.MAX_SECONDS or not 26<=max_requests<=observer.MAX_REQUESTS:raise ValueError('Outside existing Scanner safety limits')
    if request_id is not None and not re.fullmatch('[0-9a-f]{32}',request_id):raise ValueError('Invalid start request')
    cancellation=CONTROL/('CANCEL_'+request_id) if request_id else None
    with observer.scanner.exclusive(CONTROL/'manager'):
        if cancellation and cancellation.exists():raise RuntimeError('SCANNER_START_CANCELLED')
        old=current()
        if old and (alive(old.get('manager')) or alive(old.get('child'))):raise RuntimeError('DUPLICATE_MANAGED_SCANNER')
        token=uuid.uuid4().hex;root=observer.RUNTIME_ROOT/('console_'+token)
        if root.exists():raise RuntimeError('A new isolated dataset is required')
        folder=CONTROL/'launches'/token;folder.mkdir(parents=True,exist_ok=False)
        began=time.monotonic()
        state=dict(launch_id=token,root=str(root),status='RUNNING',phase='PRECHECK',started_at=time.time(),
            manager=identity(os.getpid()),child=None,seconds=seconds,max_requests=max_requests,started_monotonic=began,
            elapsed_monotonic_seconds=0.,db_saved='UNKNOWN',clock_evidence=None,reason=None)
        persist(state);write_metadata(CONTROL/'current.json',dict(launch_id=token))
        requested=threading.Event()
        previous={}
        for sig in (signal.SIGINT,signal.SIGTERM):
            previous[sig]=signal.signal(sig,lambda *_:requested.set())
        child=None;thread=None;logger=None
        try:
            print(f'Python       : {sys.executable}\nProject      : {PROJECT_ROOT}\nConfig       : built-in frozen policy; no .env or API keys required\nSafety       : SUPERVISED ONLY; 24h unattended NOT_READY\nStop         : stop_coin_api.bat',flush=True)
            for lock in ('supervisor','observer'):
                with observer.scanner.exclusive(observer.v42.RUNTIME_ROOT/lock):pass
            if sum(p.stat().st_size for p in CONTROL.rglob('*') if p.is_file())>=MAX_CONTROL_BYTES:raise RuntimeError('MANAGEMENT_STORAGE_LIMIT')
            if observer.shutil.disk_usage(CONTROL).free<256*1024*1024:raise RuntimeError('FREE_DISK_LIMIT')
            print('Clock        : CHECKING (existing Windows + two-provider NTP gates)',flush=True)
            evidence=observer.clock_guard.verify_clock();state['clock_evidence']=evidence
            observer.write_json(folder/'preflight.json',evidence);persist(state)
            if evidence['status']!='VERIFIED':raise RuntimeError(evidence['reason'])
            if requested.is_set() or stop_marker(state).exists() or (cancellation and cancellation.exists()):
                state.update(status='STOPPED',phase='TERMINAL',reason='CANCELLED_BEFORE_LIVE');return 0
            env=dict(os.environ);env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
            env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1')
            child=subprocess.Popen([sys.executable,'-m','coin_analysis.forward_scanner_v43','--execute-live',
                '--runtime-dir',str(root),'--seconds',str(seconds),'--max-requests',str(max_requests)],
                cwd=PROJECT_ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=0x08000000)
            state.update(child=identity(child.pid),phase='STARTING',db_saved='UNKNOWN / final close not yet confirmed');persist(state)
            logger=logging.getLogger('scanner_console_'+token);logger.setLevel(logging.INFO);logger.propagate=False
            handler=RotatingFileHandler(folder/'launch.log',maxBytes=1024*1024,backupCount=1,encoding='utf8');logger.addHandler(handler)
            def drain():
                try:
                    while data:=child.stdout.read(4096):logger.info(data.decode('utf8',errors='replace'))
                finally:child.stdout.close()
            thread=threading.Thread(target=drain,daemon=True);thread.start()
            next_display=0.
            while child.poll() is None:
                if requested.is_set() or stop_marker(state).exists():
                    if root.exists():(root/'STOP').touch(exist_ok=True)
                    state['phase']='STOPPING'
                elif (root/'heartbeat.json').exists():state['phase']='OBSERVING'
                if sum(p.stat().st_size for p in CONTROL.rglob('*') if p.is_file())>=MAX_CONTROL_BYTES:
                    requested.set();state['reason']='MANAGEMENT_STORAGE_LIMIT'
                state['elapsed_monotonic_seconds']=time.monotonic()-began;persist(state)
                if time.monotonic()>=next_display:
                    render(snapshot(state));next_display=time.monotonic()+10
                time.sleep(.5)
            code=child.wait();thread.join(timeout=3)
            final=saved_result(root) if root.exists() else dict(ok=False,reason='RUNNER_PRECHECK_FAILED; inspect launch.log',db_saved='UNKNOWN')
            if code or thread.is_alive():final['ok']=False
            state.update(status='STOPPED' if final['ok'] else 'BLOCKED',phase='TERMINAL',**{k:v for k,v in final.items() if k!='ok'})
            return 0 if final['ok'] else 2
        except Exception as exc:
            state.update(status='BLOCKED',reason=str(exc))
            print('Blocked      : '+str(exc)+'\nAction       : '+guidance(str(exc)),flush=True)
            return 2
        finally:
            if child is not None and child.poll() is None:
                # Only the owned runtime STOP event; no taskkill/terminate/kill.
                stop_marker(state).touch(exist_ok=True)
                until=time.monotonic()+STOP_WAIT_SECONDS
                while child.poll() is None and time.monotonic()<until:
                    if root.exists():(root/'STOP').touch(exist_ok=True)
                    time.sleep(.5)
                if child.poll() is None:state.update(status='BLOCKED',reason='STOP_UNCONFIRMED; no force kill sent')
            if thread is not None:thread.join(timeout=3)
            if logger is not None:
                for handler in logger.handlers[:]:handler.flush();handler.close();logger.removeHandler(handler)
            if child is None or child.poll() is not None:state['phase']='TERMINAL'
            state['elapsed_monotonic_seconds']=time.monotonic()-began;persist(state)
            for sig,handler in previous.items():signal.signal(sig,handler)
            render(snapshot(state))


def main(argv=None):
    parser=argparse.ArgumentParser(description='Supervised observation only; no orders or automatic restart.')
    parser.add_argument('action',choices=['start','stop','status'])
    parser.add_argument('--seconds',type=int,default=observer.MAX_SECONDS)
    parser.add_argument('--max-requests',type=int,default=observer.MAX_REQUESTS)
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--check',action='store_true',help='Offline Python/import/config check only; no clock probe or LIVE')
    args=parser.parse_args(argv)
    try:
        if args.check:
            print('Environment : OK\nMode : OBSERVATION ONLY\nConfig : frozen built-in cohort/policy\nClock : UNKNOWN (offline check only)\nLIVE : NOT STARTED')
            return 0
        if args.action=='start':return start(args.seconds,args.max_requests)
        if args.action=='stop':return stop()
        value=snapshot()
        if args.json:print(json.dumps(value,ensure_ascii=False,allow_nan=False))
        else:render(value)
        return 0
    except Exception as exc:
        print('Status : BLOCKED\nReason : '+str(exc)+'\nAction : '+guidance(str(exc)),flush=True);return 2


if __name__=='__main__':raise SystemExit(main())
