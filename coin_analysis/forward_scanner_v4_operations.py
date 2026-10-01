"""Operational provenance only; no change to V3 signal/feature/label definitions."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid

SOURCE_POLICY={'version':1,'live_delay_seconds_exclusive':300,
               'rule':'LIVE iff 0 <= detected_at - signal_time < 300; otherwise CATCHUP. Fixed observation interval, not outcome optimized.'}

def source_for(t,detected):
    return 'LIVE' if 0<=detected-t<300 else 'CATCHUP'

def schema(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS source_policy(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS scanner_sessions(session_id TEXT PRIMARY KEY,started_at INTEGER,ended_at INTEGER,status TEXT,restart INTEGER,previous_session_id TEXT);
      CREATE TABLE IF NOT EXISTS scanner_cycles(cycle_id INTEGER PRIMARY KEY,session_id TEXT,started_at INTEGER,ended_at INTEGER,watermark_before INTEGER,watermark_after INTEGER,backlog_before_seconds INTEGER,backlog_after_seconds INTEGER,status TEXT,api_errors_json TEXT,error TEXT);
      CREATE TABLE IF NOT EXISTS source_migrations(id INTEGER PRIMARY KEY,completed_at INTEGER,backup_path TEXT,report_json TEXT);
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
        db.execute("UPDATE scanner_sessions SET status='INTERRUPTED' WHERE ended_at IS NULL AND status='RUNNING'")
        db.execute("UPDATE scanner_cycles SET status='INTERRUPTED' WHERE ended_at IS NULL AND status='RUNNING'")
        db.execute('INSERT INTO scanner_sessions VALUES(?,?,NULL,?,?,?)',(sid,now,'RUNNING',int(bool(previous) or progressed),previous[0] if previous else None))
    return sid

def end_session(db,sid,status):
    with db:db.execute('UPDATE scanner_sessions SET ended_at=?,status=? WHERE session_id=?',(int(time.time()),status,sid))

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
