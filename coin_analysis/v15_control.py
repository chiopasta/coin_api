"""Own only dashboard-launched V15 processes; never signal or kill a PID."""
from contextlib import closing
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

from . import scanner_control_v410 as utilities

ROOT=utilities.PROJECT_ROOT
SCRIPT=ROOT/'archive/scanner_v15.py'
DATABASE=SCRIPT.parent/'crypto_scanner.db'
FOLDER=utilities.DATA_DIR/'scanner_v15_web'
STOP_WAIT_SECONDS=45
alive=utilities.alive
_children={}
_inventory_lock=threading.Lock()
_inventory_cache=(0,[])


def state_root(token):
    if not re.fullmatch('[0-9a-f]{32}',token):raise ValueError('Invalid V15 launch')
    path=FOLDER/'launches'/token
    if path.is_symlink() or path.resolve().parent!=(FOLDER/'launches').resolve():raise ValueError('Invalid V15 path')
    return path


def inventory(fresh=False):
    global _inventory_cache
    with _inventory_lock:
        if not fresh and time.monotonic()-_inventory_cache[0]<2:return _inventory_cache[1]
        command="$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' } | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"
        result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',command],
                              capture_output=True,timeout=8,creationflags=0x08000000)
        if result.returncode:raise RuntimeError('PROCESS_INVENTORY_UNAVAILABLE')
        rows=json.loads(result.stdout.decode('utf-8-sig') or '[]');rows=rows if isinstance(rows,list) else [rows]
        found=[]
        for row in rows:
            line=row.get('CommandLine') or ''
            if re.search(r'(?i)(?:^|[\\/\s".])scanner_v15\.py(?:[\s"]|$)',line) or 'coin_analysis.v15_runtime' in line:
                found.append(utilities.identity(row['ProcessId']))
        _inventory_cache=(time.monotonic(),found)
        return found


def current():
    pointer=FOLDER/'current.json'
    if not pointer.exists():return None
    value=utilities.read_json(pointer);state_root(value['launch_id'])
    return value


def snapshot():
    state=current();owned=bool(state and alive(state.get('child')))
    external=[p for p in inventory() if not state or p!=state.get('child')]
    heartbeat={}
    if state:
        path=state_root(state['launch_id'])/'heartbeat.json'
        if path.exists():heartbeat=utilities.read_json(path)
    fresh=owned and 0<=time.time()-heartbeat.get('heartbeat',0)<=5
    status='EXTERNAL_RUNNING' if external else heartbeat.get('status','RUNNING') if owned else 'STOPPED'
    if owned and not fresh:status='BLOCKED'
    result=dict(heartbeat,engine='V15',status=status,
                phase=heartbeat.get('phase','STARTING') if owned else 'EXTERNAL' if external else 'TERMINAL',
                process_alive=owned or bool(external),owned=owned,external_count=len(external),
                heartbeat_fresh=fresh,live_collecting=fresh and heartbeat.get('phase')=='OBSERVING',
                stop_allowed=owned and not external,reason='EXTERNAL_V15_PROTECTED' if external else
                'HEARTBEAT_STALE' if owned and not fresh else heartbeat.get('reason'))
    if not owned:
        result['live_collecting']=False
        result['db_saved']=heartbeat.get('db_saved','UNKNOWN')
    return result


def preflight_database(path=DATABASE):
    import sqlite3
    if not Path(path).is_file():raise RuntimeError('V15_DB_MISSING_NO_AUTO_CREATE')
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=.1)) as db:
        db.execute('PRAGMA query_only=ON')
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'signals','signal_price_history','pullback_paper_trades','pullback_watch','prepump_events','prepump_tracking'}<=tables:
            raise RuntimeError('V15_SCHEMA_UNSUPPORTED_NO_AUTO_MIGRATION')
        cols={r[1] for r in db.execute('PRAGMA table_info(signals)')}
        if not {f'{prefix}_{m}m' for prefix in ('max_profit','max_drawdown','price_after','return') for m in (5,10,30,60)}<=cols:
            raise RuntimeError('V15_SCHEMA_UNSUPPORTED_NO_AUTO_MIGRATION')


def start(seconds,max_requests,cancellation_event=None):
    if not 30<=seconds<=86400 or not 26<=max_requests<=16000:raise ValueError('Invalid V15 safety budget')
    FOLDER.mkdir(parents=True,exist_ok=True)
    if FOLDER.is_symlink():raise RuntimeError('V15_RUNTIME_PATH_REJECTED')
    if sum(p.stat().st_size for p in FOLDER.rglob('*') if p.is_file())>32*1024*1024:
        raise RuntimeError('V15_RUNTIME_STORAGE_LIMIT_NO_AUTO_DELETE')
    with utilities.observer.scanner.exclusive(FOLDER/'launcher'):
        if cancellation_event and cancellation_event.is_set():return dict(status='STOPPED',phase='TERMINAL',reason='CANCELLED')
        if inventory(True) or (current() and alive(current().get('child'))):raise RuntimeError('DUPLICATE_V15_PROTECTED')
        old=utilities.current()
        if old and (alive(old.get('manager')) or alive(old.get('child'))):raise RuntimeError('EXISTING_V4_OBSERVER_PROTECTED')
        preflight_database()
        token=uuid.uuid4().hex;root=state_root(token);root.mkdir(parents=True)
        utilities.write_metadata(root/'authorized.json',dict(engine='V15',launch_id=token))
        env=dict(os.environ);env.pop('PYTHONHOME',None);env.pop('PYTHONPATH',None)
        env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1')
        with (root/'scanner.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,'-m','coin_analysis.v15_runtime','--launch',token,
                '--seconds',str(seconds),'--max-requests',str(max_requests)],cwd=ROOT,env=env,
                stdout=log,stderr=log,creationflags=0x08000000)
        state=dict(launch_id=token,child=utilities.identity(child.pid),engine='V15',seconds=seconds,max_requests=max_requests)
        utilities.write_metadata(FOLDER/'current.json',state);_children[token]=child
    until=time.monotonic()+75
    try:
        while time.monotonic()<until:
            if cancellation_event and cancellation_event.is_set():return stop()
            value=snapshot()
            if value['live_collecting']:return value
            if child.poll() is not None:
                child.wait();raise RuntimeError('V15_START_FAILED_OR_BUDGET_REACHED')
            time.sleep(.2)
        raise RuntimeError('V15_START_TIMEOUT')
    except BaseException:
        stop();raise


def stop():
    state=current()
    if not state or not alive(state.get('child')):
        child=_children.get(state['launch_id']) if state else None
        if child and child.poll() is not None:
            child.wait();_children.pop(state['launch_id'],None)
        return dict(snapshot(),reason='NO_RUNNING_SCANNER')
    # Ownership and creation time checked, then only a private launch file is touched.
    root=state_root(state['launch_id']);(root/'STOP_REQUESTED').touch(exist_ok=True)
    until=time.monotonic()+STOP_WAIT_SECONDS
    while alive(state['child']) and time.monotonic()<until:time.sleep(.1)
    if alive(state['child']):raise RuntimeError('V15_STOP_UNCONFIRMED_NO_FORCE_KILL')
    child=_children.pop(state['launch_id'],None)
    if child:child.wait(timeout=2)
    value=snapshot()
    if value.get('db_saved')!='CLOSED':raise RuntimeError('V15_DB_CLOSE_UNCONFIRMED')
    return value
