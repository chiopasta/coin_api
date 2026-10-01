"""Frozen V3 forward observation recorder. Public candles only; no trading APIs."""
import argparse
from collections import Counter
from contextlib import closing, contextmanager
import json
from pathlib import Path
import sqlite3
import time

from . import research_dataset_collector_v1 as collector
from . import forward_surge_research_v3 as v3
from .paths import DATA_DIR
from . import forward_scanner_v4_operations as ops

STEP=300
WARMUP=21600
GRACE=600
LABELS={'L1':(30,5.),'L2':(60,10.)}
POLICY=dict(version=4,range_threshold=4,step_seconds=STEP,warmup_seconds=WARMUP,
            grace_seconds=GRACE,missing_range='keep cluster state',features='V3 closed candles only',
            incomplete_future='PENDING until horizon+grace then UNKNOWN; recover if later complete',
            universe='fixed KRW alts plus BTC; never auto-reselect',unknown_initial_cluster='suppress until observed below4')

def connect(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path);db.row_factory=sqlite3.Row
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables and 'scanner_config' not in tables:
        db.close();raise ValueError('Not a V4 DB; existing database preserved')
    if 'signals' in tables and 'source' not in [r[1] for r in db.execute('PRAGMA table_info(signals)')]:
        db.close();raise ValueError('Run --mode migrate before resuming this older scanner DB')
    db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS scanner_config(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS minute_candles(market TEXT,ts INTEGER,open REAL,high REAL,low REAL,close REAL,trade_value REAL,PRIMARY KEY(market,ts));
      CREATE TABLE IF NOT EXISTS scanner_state(market TEXT PRIMARY KEY,verified_until INTEGER,last_observation INTEGER,active INTEGER,cluster_id TEXT,last_error TEXT);
      CREATE TABLE IF NOT EXISTS collection_jobs(market TEXT PRIMARY KEY,start INTEGER,end INTEGER,cursor INTEGER);
      CREATE TABLE IF NOT EXISTS collection_pages(market TEXT,start INTEGER,end INTEGER,response_count INTEGER,PRIMARY KEY(market,start,end));
      CREATE TABLE IF NOT EXISTS signals(signal_id TEXT PRIMARY KEY,market TEXT,signal_time INTEGER,signal_price REAL,range_30m REAL,cluster_id TEXT UNIQUE,detected_at INTEGER,delay_seconds INTEGER,source TEXT NOT NULL CHECK(source IN ('LIVE','CATCHUP')),UNIQUE(market,signal_time));
      CREATE TABLE IF NOT EXISTS signal_features(signal_id TEXT PRIMARY KEY REFERENCES signals(signal_id),asof_time INTEGER,values_json TEXT,flags_json TEXT,observed_candidates_json TEXT);
      CREATE TABLE IF NOT EXISTS signal_outcomes(signal_id TEXT REFERENCES signals(signal_id),label TEXT,status TEXT,max_return REAL,first_target_time INTEGER,observed_minutes INTEGER,expected_minutes INTEGER,evaluated_at INTEGER,PRIMARY KEY(signal_id,label));
      CREATE TRIGGER IF NOT EXISTS immutable_features BEFORE UPDATE ON signal_features BEGIN SELECT RAISE(ABORT,'Frozen signal features'); END;
      CREATE TRIGGER IF NOT EXISTS immutable_signals BEFORE UPDATE ON signals BEGIN SELECT RAISE(ABORT,'Frozen signal'); END;
      CREATE TRIGGER IF NOT EXISTS immutable_completed_outcome BEFORE UPDATE ON signal_outcomes WHEN OLD.status IN ('SUCCESS','FAILURE') BEGIN SELECT RAISE(ABORT,'Outcome already complete'); END;
    ''')
    ops.schema(db)
    return db

def config(db):
    row=db.execute('SELECT payload FROM scanner_config WHERE id=1').fetchone()
    if not row:raise ValueError('Initialize V4 dataset first')
    cfg=json.loads(row[0])
    if cfg['policy']!=POLICY:raise ValueError('Frozen policy differs; use original code or a new DB')
    return cfg

def initialize(db,markets,start):
    markets=sorted(set(markets))
    if 'KRW-BTC' not in markets or len(markets)<2 or any(not m.startswith('KRW-') for m in markets):raise ValueError('KRW alts and BTC required')
    if start%STEP:raise ValueError('Start must be aligned to five-minute UTC grid')
    cfg=dict(policy=POLICY,markets=markets,start=start,collection_start=start-WARMUP)
    if db.execute('SELECT COUNT(*) FROM scanner_config').fetchone()[0]:
        if config(db)!=cfg:raise ValueError('Cannot change existing scanner config')
        return
    with db:
        db.execute('INSERT INTO scanner_config VALUES(1,?)',(json.dumps(cfg),))
        for m in markets:
            # Unknown initial state suppresses a left-censored ongoing burst.
            db.execute('INSERT INTO scanner_state VALUES(?,?,?,NULL,NULL,NULL)',(m,start-WARMUP,start-WARMUP-STEP))

def fetch_market(db,client,market,end):
    """Reverse pages; durable job cursor resumes from last committed page."""
    state=db.execute('SELECT * FROM scanner_state WHERE market=?',(market,)).fetchone()
    job=db.execute('SELECT * FROM collection_jobs WHERE market=?',(market,)).fetchone()
    if not job:
        if state['verified_until']>=end:return
        with db:db.execute('INSERT INTO collection_jobs VALUES(?,?,?,?)',(market,state['verified_until'],end,end))
    while True:
        job=db.execute('SELECT * FROM collection_jobs WHERE market=?',(market,)).fetchone()
        raw=client.get('/v1/candles/minutes/1',market=market,to=collector.iso(job['cursor']),count=200)
        rows=collector.validate_page(raw,job['cursor'],market);oldest=rows[-1][0]
        selected=[(market,)+r for r in rows if job['start']<=r[0]<job['end']]
        with db:
            for record in selected:
                existing=db.execute('SELECT open,high,low,close,trade_value FROM minute_candles WHERE market=? AND ts=?',record[:2]).fetchone()
                if existing and tuple(existing)!=record[2:]:raise ValueError('Conflicting confirmed candle; stop rather than overwrite')
            db.executemany('INSERT OR IGNORE INTO minute_candles VALUES(?,?,?,?,?,?,?)',selected)
            db.execute('INSERT OR IGNORE INTO collection_pages VALUES(?,?,?,?)',(market,max(oldest,job['start']),job['cursor'],len(rows)))
            if oldest<=job['start']:
                db.execute('UPDATE scanner_state SET verified_until=?,last_error=NULL WHERE market=?',(job['end'],market))
                db.execute('DELETE FROM collection_jobs WHERE market=?',(market,))
            else:db.execute('UPDATE collection_jobs SET cursor=? WHERE market=?',(oldest,market))
        if oldest<=job['start']:return

def load_research(db,start,end):
    cfg=config(db)
    series={m:v3.v2.old.Series(db.execute('SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? AND ts>=? AND ts<? ORDER BY ts',(m,start,end))) for m in cfg['markets']}
    btc=series.pop('KRW-BTC')
    return v3.v2.old.Research(series,[],start,end,btc)

def process_observations(db,now,emit=print):
    cfg=config(db);states=list(db.execute('SELECT * FROM scanner_state WHERE market<>? ORDER BY market',('KRW-BTC',)))
    watermark=db.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0]
    end=min(watermark,now//60*60)//STEP*STEP
    first=min(s['last_observation'] for s in states)+STEP
    if first>end:return
    # Bounded to unprocessed history + lookback; no whole-life in-memory reload.
    research=load_research(db,first-121*60,end)
    for t in range(first,end+1,STEP):
        for state in states:
            m=state['market'];s=research.panel[m]
            current=db.execute('SELECT * FROM scanner_state WHERE market=?',(m,)).fetchone()
            if t<=current['last_observation']:continue
            hi,lo=s.high_low(t-1800,t);width=v3.v2.old.pct(hi,lo)
            active=current['active'];cluster=current['cluster_id'];message=None
            with db:
                if width is not None and width<4:active=0;cluster=None
                elif width is not None and width>=4 and active==0:
                    active=1;cluster=v3.v2.old.identity('v4cluster',m,t)
                    if t>=cfg['start']:
                        fs=v3.features(research,m,t);signal=v3.v2.old.identity('v4signal',m,t)
                        candidates={k:fs['values'][k] for k in ('range_15m_pct','range_30m_pct','alt_relative_60m_pct')}
                        source=ops.source_for(t,now)
                        db.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)',(signal,m,t,s.price(t),width,cluster,now,max(0,now-t),source))
                        db.execute('INSERT INTO signal_features VALUES(?,?,?,?,?)',(signal,t,json.dumps(fs['values'],allow_nan=False),json.dumps(fs['flags'],allow_nan=False),json.dumps(candidates,allow_nan=False)))
                        for y,(minutes,_) in LABELS.items():db.execute('INSERT INTO signal_outcomes VALUES(?,?,?,NULL,NULL,0,?,NULL)',(signal,y,'PENDING',minutes))
                        message=f'SIGNAL {source} {m} time={collector.iso(t,collector.KST)} price={s.price(t)} range30={width:.3f}% range15={candidates["range_15m_pct"]} alt_relative60={candidates["alt_relative_60m_pct"]} delay={max(0,now-t)}s'
                db.execute('UPDATE scanner_state SET last_observation=?,active=?,cluster_id=? WHERE market=?',(t,active,cluster,m))
            if message:emit(message)
        research.feature_cache.clear();research.market_returns.clear()

def evaluate_outcomes(db,now,emit=print):
    pending=list(db.execute("SELECT s.*,o.label,o.status FROM signals s JOIN signal_outcomes o USING(signal_id) WHERE o.status IN ('PENDING','UNKNOWN')"))
    for row in pending:
        minutes,target=LABELS[row['label']];t=row['signal_time'];end=t+minutes*60
        if now<end:continue
        candles=list(db.execute('SELECT ts,high FROM minute_candles WHERE market=? AND ts>=? AND ts<? ORDER BY ts',(row['market'],t,end)))
        complete=len(candles)==minutes and all(x['ts']==t+i*60 for i,x in enumerate(candles))
        verified=db.execute('SELECT verified_until FROM scanner_state WHERE market=?',(row['market'],)).fetchone()[0]>=end
        if not complete or not verified:
            if now>=end+GRACE:
                with db:db.execute("UPDATE signal_outcomes SET status='UNKNOWN',observed_minutes=?,evaluated_at=? WHERE signal_id=? AND label=?",(len(candles),now,row['signal_id'],row['label']))
            continue
        peak=max(r['high'] for r in candles);rise=v3.v2.old.pct(peak,row['signal_price'])
        hit=next((r['ts']+60 for r in candles if v3.v2.old.pct(r['high'],row['signal_price'])>=target),None)
        status='SUCCESS' if hit is not None else 'FAILURE'
        with db:db.execute('UPDATE signal_outcomes SET status=?,max_return=?,first_target_time=?,observed_minutes=?,evaluated_at=? WHERE signal_id=? AND label=?',(status,rise,hit,len(candles),now,row['signal_id'],row['label']))
        emit(f'{row["market"]} {row["label"]} {status} signal={row["signal_id"]} max_return={rise:.3f}%')

def statistics(db,source='LIVE'):
    if source not in ('LIVE','CATCHUP','ALL'):raise ValueError('Invalid source')
    where='' if source=='ALL' else ' WHERE source=?'
    params=() if source=='ALL' else (source,)
    result=dict(source=source,signals=db.execute('SELECT COUNT(*) FROM signals'+where,params).fetchone()[0],signal_markets=db.execute('SELECT COUNT(DISTINCT market) FROM signals'+where,params).fetchone()[0])
    for y in LABELS:
        counts=dict(db.execute('SELECT o.status,COUNT(*) FROM signal_outcomes o JOIN signals s USING(signal_id) WHERE o.label=?'+('' if source=='ALL' else ' AND s.source=?')+' GROUP BY o.status',(y,)+params))
        valid=counts.get('SUCCESS',0)+counts.get('FAILURE',0)
        result[y]=dict(statuses=counts,valid=valid,success=counts.get('SUCCESS',0),rate_pct=100*counts.get('SUCCESS',0)/valid if valid else None)
    result['collection_errors']=[dict(r) for r in db.execute('SELECT market,last_error,verified_until FROM scanner_state WHERE last_error IS NOT NULL')]
    return result

def grouped_statistics(db):
    return dict(default_view='LIVE',**{source:statistics(db,source) for source in ('LIVE','CATCHUP','ALL')})

def cycle(db,client,now=None,emit=print,session_id=None):
    began=int(time.time()) if now is None else now
    cid=ops.start_cycle(db,session_id,began);error=None
    try:return _cycle(db,client,now,emit)
    except BaseException as exc:error=repr(exc);raise
    finally:ops.end_cycle(db,cid,int(time.time()) if now is None else now,error)

def _cycle(db,client,now=None,emit=print):
    live_clock=now is None
    now=int(time.time()) if now is None else now
    end=(now-5)//60*60  # settle delay; excludes all still-open minute candles
    blocked=None
    for m in config(db)['markets']:
        try:fetch_market(db,client,m,end)
        except Exception as exc:
            with db:db.execute('UPDATE scanner_state SET last_error=? WHERE market=?',(str(exc),m))
            emit(f'COLLECTION ERROR {m}: {exc}')
            if isinstance(exc,collector.CollectionBlocked):blocked=exc;break
    if live_clock:now=int(time.time())
    process_observations(db,now,emit);evaluate_outcomes(db,now,emit)
    emit(json.dumps(grouped_statistics(db),ensure_ascii=False))
    if blocked is not None:raise blocked
    return statistics(db)

@contextmanager
def exclusive(path):
    """OS-released single writer lock, including after forced process termination."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with open(str(path)+'.lock','a+b') as f:
        f.seek(0);f.write(b'0');f.flush();f.seek(0)
        try:
            if __import__('os').name=='nt':
                import msvcrt
                msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise RuntimeError('Another scanner owns this DB') from exc
        try:yield
        finally:
            f.seek(0)
            if __import__('os').name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f,fcntl.LOCK_UN)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DATA_DIR/'forward_scanner_v4.db')
    p.add_argument('--mode',choices=('init','once','run','stats','migrate'),required=True)
    p.add_argument('--source',choices=('LIVE','CATCHUP','ALL'),default='LIVE',help='Statistics view; default LIVE')
    p.add_argument('--migration-evidence',type=Path,default=Path('reports/forward_scanner_v4_delay_causes_20261001.json'))
    p.add_argument('--market-manifest',type=Path,help='Existing frozen JSON market list, no discovery DB access')
    p.add_argument('--start',help='Explicit five-minute aligned UTC/KST time; default next five-minute tick')
    p.add_argument('--max-cycles',type=int);p.add_argument('--max-requests',type=int)
    a=p.parse_args()
    if a.mode=='migrate':
        report=ops.migrate(a.db,a.migration_evidence)
        Path('reports/forward_scanner_v4_source_migration.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2));return
    if a.max_cycles is not None and a.max_cycles<=0 or a.max_requests is not None and a.max_requests<=0:p.error('Budgets must be positive')
    with exclusive(a.db),closing(connect(a.db)) as db:
        if a.mode=='init':
            if not a.market_manifest:p.error('--market-manifest is required')
            m=json.loads(a.market_manifest.read_text(encoding='utf-8'))
            start=collector.parse(a.start) if a.start else (int(time.time())//STEP+1)*STEP
            initialize(db,m['markets'],start);print(json.dumps(config(db),ensure_ascii=False,indent=2));return
        config(db)
        if a.mode=='stats':print(json.dumps(statistics(db,a.source),ensure_ascii=False,indent=2));return
        client=collector.Client(max_requests=a.max_requests);n=0
        sid=ops.start_session(db);status='CLOSED'
        try:
            while True:
                cycle(db,client,session_id=sid);n+=1
                if a.mode=='once' or a.max_cycles is not None and n>=a.max_cycles or a.max_requests is not None and client.requests>=a.max_requests:return
                time.sleep(max(1,65-time.time()%60))
        except KeyboardInterrupt:status='STOPPED';raise
        except BaseException:status='ERROR';raise
        finally:ops.end_session(db,sid,status)

if __name__=='__main__':main()
