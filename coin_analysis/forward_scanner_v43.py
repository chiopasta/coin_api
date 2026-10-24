"""Restartable, bounded public observation. Frozen V4 policy; no trading APIs.

Each explicit launch has its own deadline and request allowance. Resume retains
the dataset, pending outcomes, cluster state and cumulative HTTP audit ledger.
No scheduler, unattended relaunch, credential loading or historical DB input.
"""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

from . import forward_scanner_v42 as v42

scanner, ops, candles = v42.scanner, v42.ops, v42.candles
MARKETS = v42.MARKETS  # Same five markets; no liquidity/return-based reselection.
RUNTIME_ROOT = scanner.DATA_DIR/'scanner_v43_live'
MAX_SECONDS = 86400
MAX_REQUESTS = 16000
MAX_DISK = 256*1024*1024
MAX_RSS = 256*1024*1024
LOG_BYTES = 1024*1024
LOG_COPIES = 4
MAX_BACKLOG = 21600
ROUND_RESERVE_SECONDS = 15  # Normal ten-page poll, not a guarantee against outages.
ROUND_RESERVE_REQUESTS = 12
Stop = v42.ObservationStop
write_json = v42.write_json


def ledger(path):
    db = sqlite3.connect(path); db.row_factory = sqlite3.Row
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS http_attempts(
        seq INTEGER PRIMARY KEY,run_id TEXT,started_at REAL,exchange TEXT,
        endpoint TEXT,params_json TEXT,status TEXT,ended_at REAL,details_json TEXT);
      CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,payload TEXT);
    ''')
    if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        db.close(); raise RuntimeError('Unhealthy HTTP ledger')
    return db


class Budget(v42.Budget):
    def __init__(self, root, config, run, control):
        self.root, self.config, self.run, self.control = Path(root), dict(config, **run), run, control
        self.path = self.root/'events.jsonl'; self.stop = False
        self.requests = control.execute('SELECT COUNT(*) FROM http_attempts WHERE run_id=?',(run['run_id'],)).fetchone()[0]
        latest = control.execute('SELECT MAX(started_at) FROM http_attempts').fetchone()[0]
        self.next_request = time.monotonic()+max(0, (latest or 0)+.25-time.time())
        self.peak_rss = 0; self.max_cpu_percent = 0.; self.cpu_sample = (time.monotonic(),time.process_time())
        self.last_clock = time.time(); self.active_seq = None; self.receipts = {}

    def event(self, kind, **payload):
        if kind == 'HTTP_START':
            # Reserve BEFORE network: a crash cannot refund an attempted call.
            with self.control:
                row = self.control.execute('INSERT INTO http_attempts(run_id,started_at,exchange,endpoint,params_json,status) VALUES(?,?,?,?,?,?)',
                    (self.run['run_id'],time.time(),payload['exchange'],payload['endpoint'],json.dumps(payload['params']),'STARTED'))
                self.active_seq = row.lastrowid
        elif kind in ('HTTP_END','HTTP_ERROR') and self.active_seq is not None:
            with self.control:
                self.control.execute('UPDATE http_attempts SET status=?,ended_at=?,details_json=? WHERE seq=?',
                    (kind,time.time(),json.dumps(payload),self.active_seq))
            self.active_seq = None
        line = json.dumps(dict(at=time.time(),run_id=self.run['run_id'],kind=kind,**payload),allow_nan=False)+'\n'
        if self.path.exists() and self.path.stat().st_size+len(line.encode('utf8'))>LOG_BYTES:
            # Only this new observer's bounded telemetry rotates. DB evidence stays.
            oldest=self.root/f'events.{LOG_COPIES-1}.jsonl'
            if oldest.exists():oldest.unlink()
            for n in range(LOG_COPIES-2,0,-1):
                source=self.root/f'events.{n}.jsonl'
                if source.exists():os.replace(source,self.root/f'events.{n+1}.jsonl')
            os.replace(self.path,self.root/'events.1.jsonl')
        with self.path.open('a',encoding='utf8') as stream:
            stream.write(line);stream.flush()

    def check(self):
        now=time.time()
        if self.stop or (self.root/'STOP').exists():raise Stop('STOP_REQUESTED')
        if now+2<self.last_clock:raise Stop('CLOCK_MOVED_BACKWARDS')
        self.last_clock=now
        if now>=self.config['deadline']:raise Stop('TIME_LIMIT')
        self.peak_rss=max(self.peak_rss,v42.rss_bytes())
        if self.peak_rss>MAX_RSS:raise Stop('MEMORY_LIMIT')
        if sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())>=MAX_DISK:raise Stop('DISK_LIMIT')
        if shutil.disk_usage(self.root).free<256*1024*1024:raise Stop('FREE_DISK_LIMIT')
        wall,cpu=self.cpu_sample;elapsed=time.monotonic()-wall
        if elapsed>=10:
            load=100*(time.process_time()-cpu)/elapsed
            self.max_cpu_percent=max(self.max_cpu_percent,load)
            self.cpu_sample=(time.monotonic(),time.process_time())
            if load>60:raise Stop('CPU_LIMIT_SINGLE_CORE_10S')

    def request(self, exchange, endpoint, params):
        # v4.2 transport allows only market/all and 1-minute PUBLIC candles.
        body,headers=super().request(exchange,endpoint,params)
        self.next_request=max(self.next_request,time.monotonic()+.25)
        if endpoint.endswith('/1'):
            rows=candles.validate_page(body,scanner.collector.parse(params['to']),params['market'])
            db=self.receipts.get(exchange)
            if db is not None:
                received=int(time.time())
                with db:
                    db.executemany('INSERT OR IGNORE INTO candle_receipts VALUES(?,?,?)',
                        [(params['market'],r[0],received) for r in rows])
        return body,headers

    def round_admission(self, bootstrap=False):
        self.check()
        seconds=30 if bootstrap else ROUND_RESERVE_SECONDS
        requests=24 if bootstrap else ROUND_RESERVE_REQUESTS
        if self.config['deadline']-time.time()<seconds:return 'ROUND_TIME_RESERVE'
        if self.config['max_requests']-self.requests<requests:return 'ROUND_REQUEST_RESERVE'
        return None


def observation_schema(db):
    v42.observation_schema(db)
    db.executescript('''
      CREATE TABLE IF NOT EXISTS candle_receipts(
        market TEXT,ts INTEGER,first_received_at INTEGER,PRIMARY KEY(market,ts));
      CREATE TABLE IF NOT EXISTS coverage_windows(
        market TEXT,t INTEGER,minutes INTEGER,observed INTEGER,status TEXT,missing_json TEXT,
        recorded_at INTEGER,PRIMARY KEY(market,t,minutes));
      CREATE TABLE IF NOT EXISTS signal_context(
        signal_id TEXT PRIMARY KEY REFERENCES signals(signal_id),pre_price_change_5m_pct REAL,
        pre_trade_value_ratio REAL,features_json TEXT,receipt_basis TEXT);
      CREATE TRIGGER IF NOT EXISTS immutable_coverage BEFORE UPDATE ON coverage_windows
        BEGIN SELECT RAISE(ABORT,'Coverage at processing time is immutable'); END;
    ''')


def open_runtime(root, config, exchange):
    db=scanner.connect(Path(root)/(exchange.lower()+'.db'))
    try:
        scanner.initialize(db,config['markets'],config['signal_start']);observation_schema(db)
    except BaseException:db.close();raise
    return db


def coverage(db, before, now):
    """Audit only: missing candles remain NULL in the unchanged core."""
    for state in db.execute("SELECT * FROM scanner_state WHERE market!='KRW-BTC'").fetchall():
        market=state['market']
        for t in range(before[market]+300,state['last_observation']+1,300):
            if t<scanner.config(db)['start']:continue
            for minutes in (1,5,15,30):
                stamps={r[0] for r in db.execute('SELECT ts FROM minute_candles WHERE market=? AND ts>=? AND ts<?',(market,t-minutes*60,t))}
                missing=sorted(set(range(t-minutes*60,t,60))-stamps)
                # verified_until is a successful paginated source-range check,
                # never a claim that every calendar minute has a trade/candle.
                status='COMPLETE' if not missing else 'SOURCE_ABSENT' if state['verified_until']>=t else 'NOT_COLLECTED'
                with db:db.execute('INSERT OR IGNORE INTO coverage_windows VALUES(?,?,?,?,?,?,?)',
                    (market,t,minutes,len(stamps),status,json.dumps(missing),now))


def record_metrics(db, exchange, now):
    # Preserve frozen features/labels and v4.2 nominal-time horizon definitions.
    new=db.execute('SELECT s.* FROM signals s LEFT JOIN live_signal_details d USING(signal_id) WHERE d.signal_id IS NULL').fetchall()
    for row in new:
        known=db.execute('SELECT c.ts,c.close FROM minute_candles c JOIN candle_receipts r USING(market,ts) WHERE c.market=? AND c.ts+60<=? AND r.first_received_at<=? ORDER BY c.ts DESC LIMIT 1',
            (row['market'],row['detected_at'],row['detected_at'])).fetchone()
        feature=db.execute('SELECT values_json FROM signal_features WHERE signal_id=?',(row['signal_id'],)).fetchone()
        values=json.loads(feature[0]) if feature else {}
        with db:
            db.execute('INSERT INTO live_signal_details VALUES(?,?,?,NULL,?,?,?,?,?)',
                (row['signal_id'],exchange,'RANGE_30M_GE4_FIRST_CLUSTER','NOT_DEFINED_BY_V4',row['signal_time'],
                 known['close'] if known else None,known['ts']+60 if known else None,'RECEIPTED_CONFIRMED_CLOSE_PROXY; SECOND_PRECISION; NOT_FILL'))
            db.execute('INSERT INTO signal_context VALUES(?,?,?,?,?)',(row['signal_id'],values.get('return_5m_pct'),
                values.get('trade_value_ratio'),json.dumps(values),'First response receipt <= actual detected_at; unknown stays NULL'))
    v42.record_metrics(db,exchange,now)


def validate_config(config):
    if config['version']!='4.3_OBSERVATION' or config['markets']!=MARKETS or config['policy']!=scanner.POLICY:
        raise ValueError('Frozen dataset config mismatch')
    if config['signal_start']%300:raise ValueError('Invalid signal start')


def worker(root, run_id):
    root=Path(root).resolve()
    if root.parent!=RUNTIME_ROOT.resolve():raise ValueError('Unsafe runtime location')
    config=json.loads((root/'config.json').read_text(encoding='utf8'));validate_config(config)
    run=json.loads((root/'runs'/f'{run_id}.json').read_text(encoding='utf8'))
    if not 0<run['duration_seconds']<=MAX_SECONDS or not 0<run['max_requests']<=MAX_REQUESTS or run['deadline']!=run['created_at']+run['duration_seconds']:
        raise ValueError('Invalid launch bounds')
    began=time.time();dbs={};sessions={};budget=None;status='BLOCKED';reason=None;rounds=0
    errors={};close_errors={};locks=ExitStack();control=None;per_exchange={}
    try:
        locks.enter_context(scanner.exclusive(v42.RUNTIME_ROOT/'observer'))
        for exchange in v42.HOSTS:locks.enter_context(scanner.exclusive(root/(exchange.lower()+'.db')))
        control=ledger(root/'control.db');budget=Budget(root,config,run,control)
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:setattr(budget,'stop',True))
        budget.check();budget.event('WORKER_START',pid=os.getpid(),bounds=run)
        for exchange in v42.HOSTS:
            dbs[exchange]=open_runtime(root,config,exchange)
            sessions[exchange]=ops.start_session(dbs[exchange])
            budget.receipts[exchange]=dbs[exchange]
            # Avoid unbounded historical catchup after long OS downtime.
            verified=dbs[exchange].execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0]
            if run['resume'] and time.time()-verified>MAX_BACKLOG:raise Stop('RESUME_BACKLOG_OVER_6H')
        for exchange in v42.HOSTS:
            listed,_=budget.request(exchange,'/v1/market/all',{})
            missing=set(MARKETS)-{r['market'] for r in listed if isinstance(r,dict) and 'market' in r}
            if missing:raise Stop(f'UNSUPPORTED_MARKETS:{exchange}:{sorted(missing)}')
        clients={e:scanner.collector.Client(transport=lambda path,params,e=e:budget.request(e,path,params),sleep=budget.sleep) for e in dbs}
        consecutive_errors=0
        while True:
            bootstrap=any(db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0]==0 for db in dbs.values())
            reserve=budget.round_admission(bootstrap)
            if reserve:reason=reserve;status='BOUNDED_STOP';break
            for exchange,db in dbs.items():
                before=dict(db.execute('SELECT market,last_observation FROM scanner_state'))
                scanner.cycle(db,clients[exchange],emit=lambda msg,e=exchange:budget.event('ENGINE',exchange=e,message=msg),session_id=sessions[exchange])
                now=int(time.time());coverage(db,before,now);record_metrics(db,exchange,now)
                errors[exchange]=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')]
            rounds+=1
            failed=any(errors.values());consecutive_errors=consecutive_errors+1 if failed else 0
            budget.event('ROUND_COMPLETE',round=rounds,errors=errors,rss_bytes=budget.peak_rss,cpu_percent=budget.max_cpu_percent,
                watermarks={e:db.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0] for e,db in dbs.items()})
            write_json(root/'heartbeat.json',dict(at=time.time(),run_id=run_id,pid=os.getpid(),rounds=rounds,requests=budget.requests,
                rss_bytes=budget.peak_rss,cpu_percent=budget.max_cpu_percent,collection_errors=errors))
            if consecutive_errors>=5:raise Stop('NETWORK_CIRCUIT_OPEN_5_ROUNDS')
            # Transient exhausted retries retain jobs. Next poll resumes them.
            wait=max(1,65-time.time()%60)
            remaining=run['deadline']-time.time()-ROUND_RESERVE_SECONDS
            if wait>=remaining:status='BOUNDED_STOP';reason='ROUND_TIME_RESERVE';break
            budget.sleep(wait)
    except Stop as exc:
        reason=str(exc);status='STOPPED' if reason=='STOP_REQUESTED' else 'BOUNDED_STOP' if reason in ('TIME_LIMIT','REQUEST_LIMIT') else 'BLOCKED'
    except Exception as exc:reason=repr(exc);status='BLOCKED'
    finally:
        for exchange,db in dbs.items():
            try:
                record_metrics(db,exchange,int(time.time()))
                if exchange in sessions:ops.end_session(db,sessions[exchange],'STOPPED' if status in ('STOPPED','BOUNDED_STOP') else 'ERROR',reason)
                errors[exchange]=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')]
                per_exchange[exchange]=dict(integrity=db.execute('PRAGMA quick_check').fetchone()[0],signals=scanner.grouped_statistics(db),
                    candles=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],pending_jobs=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0],
                    coverage=[dict(r) for r in db.execute('SELECT minutes,status,COUNT(*) AS n FROM coverage_windows GROUP BY minutes,status')],
                    horizons=[dict(r) for r in db.execute('SELECT minutes,status,COUNT(*) AS n FROM live_horizons GROUP BY minutes,status')])
                ops.close_cleanly(db)
            except Exception as exc:
                close_errors[exchange]=repr(exc)
                try:db.close()
                except Exception:pass
        if budget:
            try:budget.event('WORKER_END',status=status,reason=reason,rounds=rounds)
            except Exception as exc:close_errors['event']=repr(exc)
        if control:control.close()
        locks.close()
        result=dict(run_id=run_id,status=status,reason=reason,started_at=began,ended_at=time.time(),completed_rounds=rounds,
            requests=budget.requests if budget else 0,peak_rss_bytes=budget.peak_rss if budget else None,
            max_cpu_percent=budget.max_cpu_percent if budget else None,per_exchange=per_exchange,collection_errors=errors,
            close_errors=close_errors,no_orders=True,performance_verdict='INSUFFICIENT_DATA')
        write_json(root/'runs'/f'{run_id}.summary.json',result)
        print(json.dumps(dict(status=status,reason=reason,root=str(root),run_id=run_id)),flush=True)
    return 0 if status in ('STOPPED','BOUNDED_STOP') and not close_errors else 1


def run(root, seconds, resume=False, max_requests=MAX_REQUESTS):
    root=Path(root).resolve()
    if root.parent!=RUNTIME_ROOT.resolve():raise ValueError('Use direct child of data/scanner_v43_live')
    if not 30<=seconds<=MAX_SECONDS or not 26<=max_requests<=MAX_REQUESTS:raise ValueError('Outside bounded launch limits')
    # Same global locks as v4.2; duplicate launch cannot create/alter dataset.
    with scanner.exclusive(v42.RUNTIME_ROOT/'supervisor'):
        if resume:
            config=json.loads((root/'config.json').read_text(encoding='utf8'));validate_config(config)
            if (root/'STOP').exists():raise ValueError('Archive/remove own STOP explicitly before resume')
        else:
            root.mkdir(parents=True,exist_ok=False)
            now=time.time();config=dict(version='4.3_OBSERVATION',created_at=now,markets=MARKETS,policy=scanner.POLICY,
                signal_start=(int(now)//300+1)*300,scope='V4.2 fixed five per venue; not entire market')
            write_json(root/'config.json',config)
        if shutil.disk_usage(root).free<256*1024*1024:raise RuntimeError('Insufficient free disk')
        now=time.time();run_id=uuid.uuid4().hex
        bounds=dict(run_id=run_id,created_at=now,duration_seconds=seconds,deadline=now+seconds,
                    max_requests=max_requests,resume=resume)
        (root/'runs').mkdir(exist_ok=True);write_json(root/'runs'/f'{run_id}.json',bounds)
        with ledger(root/'control.db') as control:
            control.execute('INSERT INTO runs VALUES(?,?)',(run_id,json.dumps(bounds)))
        control.close()
        process=subprocess.Popen([sys.executable,'-m',__spec__.name,'--execute-live','--worker','--runtime-dir',str(root),'--run-id',run_id],
            creationflags=0x08000000 if os.name=='nt' else 0)
        write_json(root/'supervisor.json',dict(at=time.time(),run_id=run_id,pid=os.getpid(),worker_pid=process.pid,deadline=bounds['deadline']))
        forced=False
        try:code=process.wait(timeout=max(1,bounds['deadline']-time.time()+30))
        except (subprocess.TimeoutExpired,KeyboardInterrupt) as exc:
            (root/'STOP').touch()
            try:code=process.wait(timeout=20 if isinstance(exc,KeyboardInterrupt) else 5)
            except subprocess.TimeoutExpired:process.kill();process.wait();code=124;forced=True
        write_json(root/'runs'/f'{run_id}.exit.json',dict(at=time.time(),run_id=run_id,worker_reaped=True,
            worker_returncode=code,forced_kill=forced,automatic_restart=False))
        return code


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-live',action='store_true')
    parser.add_argument('--runtime-dir',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=600)
    parser.add_argument('--max-requests',type=int,default=180)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--run-id',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.execute_live:parser.error('Explicit public LIVE opt-in required')
    if args.worker:return worker(args.runtime_dir,args.run_id)
    return run(args.runtime_dir,args.seconds,args.resume,args.max_requests)


if __name__=='__main__':raise SystemExit(main())
