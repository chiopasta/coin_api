"""Operational provenance and SQLite lifecycle; no research-policy changes."""
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

SOURCE_POLICY={'version':1,'live_delay_seconds_exclusive':300,
               'rule':'LIVE iff 0 <= detected_at - signal_time < 300; otherwise CATCHUP. Fixed observation interval, not outcome optimized.'}

class DatabaseSidecarError(RuntimeError):
    """The main DB is readable but its WAL sidecar cannot be safely applied."""

def _file_sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def _readonly_uri(path,immutable=False):
    uri=Path(path).resolve().as_uri()+'?mode=ro'
    return uri+('&immutable=1' if immutable else '')

def main_db_health(path):
    """Inspect the main file without trusting or mutating WAL/SHM sidecars."""
    db=sqlite3.connect(_readonly_uri(path,True),uri=True)
    try:return db.execute('PRAGMA quick_check').fetchone()[0]
    finally:db.close()

def explain_open_error(path,exc):
    """Distinguish an unhealthy main file from an obsolete/corrupt sidecar."""
    try:health=main_db_health(path)
    except sqlite3.DatabaseError:return RuntimeError(f'V4 database main file is unreadable: {exc}')
    if health=='ok':
        return DatabaseSidecarError(
            'V4 main database quick_check is ok, but normal SQLite recovery failed; '
            'a stale or corrupt WAL/SHM sidecar is present. Preserve all files and run '
            '`python -m coin_analysis.forward_scanner_v4 --mode repair-wal --db <path>`.'
        )
    return RuntimeError(f'V4 database quick_check failed: {health}; original error: {exc}')

@contextmanager
def readonly(path):
    """Normal read-only access that never silently ignores a WAL."""
    db=None
    try:
        db=sqlite3.connect(_readonly_uri(path),uri=True)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        health=db.execute('PRAGMA quick_check').fetchone()[0]
        if health!='ok':raise sqlite3.DatabaseError('quick_check: '+health)
        yield db
    except sqlite3.DatabaseError as exc:
        raise explain_open_error(path,exc) from exc
    finally:
        if db is not None:db.close()

def full_fingerprints(db):
    """Hash every logical value, including signal source and operational tables."""
    result={}
    tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in tables:
        info=list(db.execute(f'PRAGMA table_info({table})'))
        cols=[r[1] for r in info]
        primary=[r[1] for r in sorted(info,key=lambda r:r[5]) if r[5]]
        order=primary or cols
        h=hashlib.sha256();count=0
        for row in db.execute(f'SELECT {",".join(cols)} FROM {table} ORDER BY {",".join(order)}'):
            h.update(json.dumps(tuple(row),ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8'))
            h.update(b'\n');count+=1
        result[table]={'rows':count,'sha256':h.hexdigest()}
    return result

def checkpoint(db,mode='PASSIVE'):
    if mode not in ('PASSIVE','FULL','RESTART','TRUNCATE'):raise ValueError('Invalid WAL checkpoint mode')
    row=tuple(db.execute(f'PRAGMA wal_checkpoint({mode})').fetchone())
    if row[0]:raise RuntimeError(f'WAL checkpoint {mode} remained busy: {row}')
    return row

def close_cleanly(db):
    """Roll back unfinished work, checkpoint committed WAL frames, then close."""
    try:
        if db.in_transaction:db.rollback()
        checkpoint(db,'TRUNCATE')
    finally:db.close()

def repair_stale_sidecars(path,backup_root=None):
    """Back up all files, quarantine WAL/SHM, and prove logical values unchanged."""
    path=Path(path)
    if not path.exists():raise ValueError('Existing scanner DB required')
    stamp=time.strftime('%Y%m%d_%H%M%S')
    root=Path(backup_root) if backup_root else path.parent/'backups'
    backup=root/f'{path.stem}_wal_repair_{stamp}_{time.time_ns()}'
    backup.mkdir(parents=True)
    files=[p for p in (path,Path(str(path)+'-wal'),Path(str(path)+'-shm')) if p.exists()]
    file_evidence={}
    for source in files:
        target=backup/source.name;shutil.copy2(source,target)
        file_evidence[source.name]={'bytes':source.stat().st_size,'sha256':_file_sha256(source)}
        if target.stat().st_size!=source.stat().st_size or _file_sha256(target)!=file_evidence[source.name]['sha256']:
            raise RuntimeError('Backup verification failed: '+source.name)
    try:
        with readonly(path):
            return {'repaired':False,'reason':'normal read-only open already succeeds','backup':str(backup),'files':file_evidence}
    except DatabaseSidecarError as diagnosed:
        diagnosis_text=str(diagnosed)
    if main_db_health(path)!='ok':raise RuntimeError('Immutable main database is not healthy')
    immutable=sqlite3.connect(_readonly_uri(path,True),uri=True);immutable.row_factory=sqlite3.Row
    try:before=full_fingerprints(immutable)
    finally:immutable.close()
    quarantined=[]
    try:
        for suffix in ('-wal','-shm'):
            sidecar=Path(str(path)+suffix)
            if sidecar.exists():
                target=backup/(sidecar.name+'.quarantined')
                os.replace(sidecar,target);quarantined.append(str(target))
        db=sqlite3.connect(path);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('PRAGMA journal_mode=WAL')
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Normalized DB quick_check failed')
            after=full_fingerprints(db)
            if before!=after:raise RuntimeError('Logical database values changed during WAL normalization')
            checkpoint(db,'TRUNCATE')
        finally:db.close()
        with readonly(path) as check:
            final_health=check.execute('PRAGMA quick_check').fetchone()[0]
            final=full_fingerprints(check)
        if final!=before:raise RuntimeError('Post-close logical database values changed')
    except BaseException:
        # Restore the exact verified input files; keep the backup for investigation.
        for suffix in ('-wal','-shm'):
            current=Path(str(path)+suffix)
            if current.exists():current.unlink()
        for source in files:
            shutil.copy2(backup/source.name,source)
        raise
    return {'repaired':True,'diagnosis':diagnosis_text,'backup':str(backup),'files':file_evidence,
            'quarantined':quarantined,'quick_check':final_health,'before':before,'after':final,
            'preserved':before==final}

def source_for(t,detected):
    return 'LIVE' if 0<=detected-t<300 else 'CATCHUP'

def schema(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS source_policy(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS scanner_sessions(session_id TEXT PRIMARY KEY,started_at INTEGER,ended_at INTEGER,status TEXT,restart INTEGER,previous_session_id TEXT);
      CREATE TABLE IF NOT EXISTS scanner_cycles(cycle_id INTEGER PRIMARY KEY,session_id TEXT,started_at INTEGER,ended_at INTEGER,watermark_before INTEGER,watermark_after INTEGER,backlog_before_seconds INTEGER,backlog_after_seconds INTEGER,status TEXT,api_errors_json TEXT,error TEXT);
      CREATE TABLE IF NOT EXISTS source_migrations(id INTEGER PRIMARY KEY,completed_at INTEGER,backup_path TEXT,report_json TEXT);
      CREATE TABLE IF NOT EXISTS scanner_runtime_events(event_id INTEGER PRIMARY KEY,session_id TEXT,at INTEGER,kind TEXT,details_json TEXT);
      CREATE TABLE IF NOT EXISTS scanner_late_candles(market TEXT,ts INTEGER,first_seen_at INTEGER,previous_verified_until INTEGER,PRIMARY KEY(market,ts));
    ''')
    expected=json.dumps(SOURCE_POLICY,sort_keys=True)
    row=db.execute('SELECT payload FROM source_policy WHERE id=1').fetchone()
    if row and row[0]!=expected:raise ValueError('Operational source policy mismatch')
    with db:db.execute('INSERT OR IGNORE INTO source_policy VALUES(1,?)',(expected,))

def watermark(db,now):
    w=db.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0]
    last=db.execute("SELECT MIN(last_observation) FROM scanner_state WHERE market!='KRW-BTC'").fetchone()[0]
    return w,max(0,(now//300)*300-last) if last is not None else 0

def start_session(db,now=None):
    now=int(time.time()) if now is None else now;sid=uuid.uuid4().hex
    previous=db.execute('SELECT session_id FROM scanner_sessions ORDER BY rowid DESC LIMIT 1').fetchone()
    cfg=json.loads(db.execute('SELECT payload FROM scanner_config WHERE id=1').fetchone()[0])
    progressed=db.execute("SELECT COUNT(*) FROM scanner_state WHERE market!='KRW-BTC' AND last_observation>=?",(cfg['collection_start'],)).fetchone()[0]>0
    with db:
        for row in db.execute("SELECT session_id FROM scanner_sessions WHERE ended_at IS NULL AND status='RUNNING'").fetchall():
            runtime_event(db,row['session_id'],now,'INTERRUPTED','Previous process did not record termination; actual stop time unknown')
        db.execute("UPDATE scanner_sessions SET status='INTERRUPTED' WHERE ended_at IS NULL AND status='RUNNING'")
        db.execute("UPDATE scanner_cycles SET status='INTERRUPTED' WHERE ended_at IS NULL AND status='RUNNING'")
        db.execute('INSERT INTO scanner_sessions VALUES(?,?,NULL,?,?,?)',(sid,now,'RUNNING',int(bool(previous) or progressed),previous[0] if previous else None))
        runtime_event(db,sid,now,'START','Implementation 4.1; frozen research policy unchanged')
    return sid

def runtime_event(db,sid,now,kind,reason):
    db.execute('INSERT INTO scanner_runtime_events(session_id,at,kind,details_json) VALUES(?,?,?,?)',
               (sid,now,kind,json.dumps(dict(reason=reason),ensure_ascii=False)))

def end_session(db,sid,status,reason=None):
    now=int(time.time())
    with db:
        db.execute('UPDATE scanner_sessions SET ended_at=?,status=? WHERE session_id=?',(now,status,sid))
        runtime_event(db,sid,now,'END',dict(status=status,reason=reason))

def health(db,now=None):
    """Read-only evidence of recent activity; never claims an OS process is alive."""
    now=int(time.time()) if now is None else now
    session=db.execute('SELECT * FROM scanner_sessions ORDER BY rowid DESC LIMIT 1').fetchone()
    cycle=db.execute('SELECT * FROM scanner_cycles ORDER BY cycle_id DESC LIMIT 1').fetchone()
    w,b=watermark(db,now)
    last_activity=(cycle['ended_at'] or cycle['started_at']) if cycle else None
    age=now-last_activity if last_activity is not None else None
    state='NO_SESSION' if session is None else 'STOPPED' if session['ended_at'] is not None else 'CLOCK_ANOMALY' if age is not None and age<0 else 'STALE' if age is None or age>=300 else 'RECENT_ACTIVITY_UNVERIFIED'
    return dict(operational_state=state,recorded_session=dict(session) if session else None,
                last_cycle=dict(cycle) if cycle else None,activity_age_seconds=age,
                watermark=w,watermark_age_seconds=now-w if w is not None else None,
                backlog_seconds=b,collection_errors=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')],
                process_liveness='NOT_VERIFIED',research_policy_changed=False)

def start_cycle(db,sid,now):
    w,b=watermark(db,now)
    with db:
        cur=db.execute("INSERT INTO scanner_cycles(session_id,started_at,watermark_before,backlog_before_seconds,status) VALUES(?,?,?,?,'RUNNING')",(sid,now,w,b))
    return cur.lastrowid

def end_cycle(db,cid,now,error):
    w,b=watermark(db,now)
    errors=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')]
    with db:db.execute('UPDATE scanner_cycles SET ended_at=?,watermark_after=?,backlog_after_seconds=?,status=?,api_errors_json=?,error=? WHERE cycle_id=?',
                       (now,w,b,'ERROR' if error or errors else 'COMPLETE',json.dumps(errors),error,cid))

def fingerprints(db):
    """Byte-equivalent JSON values of all existing business rows, excluding new source."""
    result={}
    for table in ('scanner_config','minute_candles','signals','signal_features','signal_outcomes','scanner_state','collection_jobs','collection_pages'):
        cols=[r[1] for r in db.execute(f'PRAGMA table_info({table})') if r[1]!='source']
        h=hashlib.sha256()
        for row in db.execute(f'SELECT {",".join(cols)} FROM {table} ORDER BY {",".join(cols)}'):
            h.update(json.dumps(tuple(row),ensure_ascii=False,allow_nan=False).encode());h.update(b'\n')
        result[table]=h.hexdigest()
    return result

def migrate(path,evidence_path):
    from . import forward_scanner_v4 as s
    path=Path(path)
    if not path.exists():raise ValueError('Existing scanner DB required')
    evidence=json.loads(Path(evidence_path).read_text(encoding='utf-8'))['signals']
    with s.exclusive(path),closing(sqlite3.connect(path)) as db:
        db.row_factory=sqlite3.Row
        if 'source' in [r[1] for r in db.execute('PRAGMA table_info(signals)')]:
            return dict(already_migrated=True,counts=dict(db.execute('SELECT source,COUNT(*) FROM signals GROUP BY source')))
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('DB integrity failed')
        # Verify every audited value, not just the ID, before applying provenance.
        for e in evidence:
            row=db.execute('SELECT * FROM signals WHERE signal_id=?',(e['signal_id'],)).fetchone()
            if not row or any(row[k]!=e[k] for k in row.keys()):raise ValueError('Audited signal changed or missing: '+e['signal_id'])
            claimed='LIVE' if e['classification']=='live_compatible_12s' else 'CATCHUP'
            if claimed!=source_for(row['signal_time'],row['detected_at']):raise ValueError('Evidence/policy conflict')
        before=fingerprints(db)
        backup=path.with_name(path.stem+f'_before_source_{time.time_ns()}.db')
        with closing(sqlite3.connect(backup)) as target:
            db.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or fingerprints(target)!=before:raise ValueError('Backup verification failed')
        try:
            db.execute('BEGIN IMMEDIATE')
            if fingerprints(db)!=before:raise ValueError('DB changed while backing up')
            db.execute("ALTER TABLE signals ADD COLUMN source TEXT NOT NULL DEFAULT 'CATCHUP' CHECK(source IN ('LIVE','CATCHUP'))")
            db.execute('DROP TRIGGER immutable_signals')
            db.execute("UPDATE signals SET source=CASE WHEN detected_at-signal_time>=0 AND detected_at-signal_time<300 THEN 'LIVE' ELSE 'CATCHUP' END")
            db.execute("CREATE TRIGGER immutable_signals BEFORE UPDATE ON signals BEGIN SELECT RAISE(ABORT,'Frozen signal'); END")
            after=fingerprints(db)
            if before!=after:raise ValueError('Existing business values changed')
            report=dict(backup=str(backup),backup_sha256=s.v3.v2.digest(backup),before=before,after=after,preserved=before==after,
                        total_counts=dict(db.execute('SELECT source,COUNT(*) FROM signals GROUP BY source')),
                        audited_counts={name:sum(source_for(e['signal_time'],e['detected_at'])==name for e in evidence) for name in ('LIVE','CATCHUP')})
            db.commit()
        except BaseException:db.rollback();raise
        schema(db)
        with db:db.execute('INSERT INTO source_migrations(completed_at,backup_path,report_json) VALUES(?,?,?)',(int(time.time()),str(backup),json.dumps(report)))
        return report
