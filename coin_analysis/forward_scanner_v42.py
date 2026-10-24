"""Bounded public-candle observation using the UNCHANGED V4 engine.

Separate per-exchange runtime DBs; never uses the original forward/research DBs.
No score, orders, account APIs, auto-restart, or parameter optimization.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import ctypes
from datetime import datetime
import json
import math
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from . import forward_scanner_v4 as scanner
from . import forward_scanner_v4_operations as ops
from . import scanner_candles as candles
from .paths import DATA_DIR

RUNTIME_ROOT=DATA_DIR/'scanner_v42_live'
MARKETS=['KRW-BTC','KRW-ENA','KRW-ETH','KRW-FLOCK','KRW-SAND']
HOSTS={'UPBIT':'https://api.upbit.com','BITHUMB':'https://api.bithumb.com'}
MAX_SECONDS=900
MAX_REQUESTS=220  # Including market checks, retries and warmup pages, both venues.
MAX_DISK_BYTES=64*1024*1024
MAX_RSS_BYTES=256*1024*1024
MAX_LOG_BYTES=1024*1024


class ObservationStop(scanner.collector.CollectionBlocked):
    pass


def write_json(path,payload):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    os.replace(temporary,path)


def rss_bytes():
    if os.name=='nt':
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(key,ctypes.c_size_t) for key in (
                'PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
                'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        result=Counters();result.cb=ctypes.sizeof(result)
        ctypes.windll.kernel32.GetCurrentProcess.restype=ctypes.c_void_p
        get_memory=ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
        get_memory.restype=ctypes.c_bool
        if not get_memory(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(result),result.cb):
            raise RuntimeError('RSS guard unavailable')
        return result.WorkingSetSize
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)


class Budget:
    def __init__(self,root,config):
        self.root=Path(root);self.config=config;self.path=self.root/'events.jsonl'
        self.requests=0;self.peak_rss=0;self.next_request=0.;self.stop=False
        if self.path.exists():
            for line in self.path.read_text(encoding='utf8').splitlines():
                if json.loads(line).get('kind')=='HTTP_START':self.requests+=1

    def event(self,kind,**payload):
        row=dict(at=time.time(),kind=kind,**payload)
        line=json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n'
        if self.path.exists() and self.path.stat().st_size+len(line.encode('utf8'))>MAX_LOG_BYTES:
            raise ObservationStop('LOG_LIMIT')
        with self.path.open('a',encoding='utf8') as f:
            f.write(line);f.flush();os.fsync(f.fileno())

    def check(self):
        if self.stop or (self.root/'STOP').exists():raise ObservationStop('STOP_REQUESTED')
        if time.time()>=self.config['deadline']:raise ObservationStop('TIME_LIMIT')
        self.peak_rss=max(self.peak_rss,rss_bytes())
        if self.peak_rss>MAX_RSS_BYTES:raise ObservationStop('MEMORY_LIMIT')
        if sum(p.stat().st_size for p in self.root.iterdir() if p.is_file())>=MAX_DISK_BYTES:
            raise ObservationStop('DISK_LIMIT')

    def sleep(self,seconds):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            self.check();time.sleep(min(.5,max(0,until-time.monotonic())))

    def request(self,exchange,endpoint,params):
        self.check()
        if exchange not in HOSTS or endpoint not in ('/v1/market/all','/v1/candles/minutes/1'):
            raise ValueError('Outside public observation endpoint scope')
        params=dict(params)
        if endpoint.endswith('/1'):
            if params.get('market') not in self.config['markets'] or params.get('count')!=200:
                raise ValueError('Outside frozen market/request scope')
            params['to']=candles.api_to(exchange,scanner.collector.parse(params['to']))
        self.sleep(max(0,self.next_request-time.monotonic()))
        if self.requests>=self.config['max_requests']:raise ObservationStop('REQUEST_LIMIT')
        self.requests+=1;self.next_request=time.monotonic()+.2
        self.event('HTTP_START',exchange=exchange,endpoint=endpoint,params=params,request_number=self.requests)
        began=time.monotonic()
        try:
            url=HOSTS[exchange]+endpoint+'?'+urllib.parse.urlencode(params)
            req=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'CHIO-v4.2-observation-only/1.0'})
            with urllib.request.urlopen(req,timeout=max(.1,min(5,self.config['deadline']-time.time()))) as response:
                body=json.load(response);headers=dict(response.headers)
                if not isinstance(body,list):raise candles.CandleValidationError('API error payload instead of candle/market array')
                self.event('HTTP_END',exchange=exchange,http_status=response.status,rows=len(body),seconds=time.monotonic()-began,
                           remaining_req=response.headers.get('Remaining-Req'))
                return body,headers
        except Exception as exc:
            self.event('HTTP_ERROR',exchange=exchange,error=repr(exc),seconds=time.monotonic()-began)
            raise


def observation_schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS live_signal_details(
          signal_id TEXT PRIMARY KEY REFERENCES signals(signal_id),exchange TEXT,pattern TEXT,
          score REAL CHECK(score IS NULL),score_status TEXT,closed_asof INTEGER,
          detection_price REAL,detection_price_close_time INTEGER,price_basis TEXT);
        CREATE TABLE IF NOT EXISTS live_horizons(
          signal_id TEXT REFERENCES signals(signal_id),minutes INTEGER,status TEXT,
          observed_minutes INTEGER,reason TEXT,return_pct REAL,mfe_pct REAL,mae_pct REAL,evaluated_at INTEGER,
          PRIMARY KEY(signal_id,minutes));
        CREATE TRIGGER IF NOT EXISTS immutable_live_complete BEFORE UPDATE ON live_horizons
          WHEN OLD.status='COMPLETE' BEGIN SELECT RAISE(ABORT,'Complete observation is immutable'); END;
    ''')


def record_metrics(db,exchange,now):
    for row in db.execute('SELECT * FROM signals ORDER BY signal_time').fetchall():
        sid=row['signal_id'];t=row['signal_time'];price=row['signal_price']
        known=db.execute('SELECT ts,close FROM minute_candles WHERE market=? AND ts+60<=? ORDER BY ts DESC LIMIT 1',
                         (row['market'],row['detected_at'])).fetchone()
        with db:
            db.execute('INSERT OR IGNORE INTO live_signal_details VALUES(?,?,?,NULL,?,?,?,?,?)',
                (sid,exchange,'RANGE_30M_GE4_FIRST_CLUSTER','NOT_DEFINED_BY_V4',t,
                 known['close'] if known else None,known['ts']+60 if known else None,'LATEST_CONFIRMED_CLOSE_KNOWN_AT_DETECTION; NOT_TRADE_FILL'))
        for minutes in (5,15,30,60):
            old=db.execute('SELECT status FROM live_horizons WHERE signal_id=? AND minutes=?',(sid,minutes)).fetchone()
            if old and old[0]=='COMPLETE':continue
            end=t+minutes*60
            future=db.execute('SELECT ts,high,low,close FROM minute_candles WHERE market=? AND ts>=? AND ts<? AND ts+60<=? ORDER BY ts',
                              (row['market'],t,end,now)).fetchall()
            verified=db.execute('SELECT verified_until FROM scanner_state WHERE market=?',(row['market'],)).fetchone()[0]
            complete=now>=end and verified>=end and len(future)==minutes and all(r['ts']==t+i*60 for i,r in enumerate(future))
            status='COMPLETE' if complete else 'PENDING'
            reason='FULL_FUTURE' if complete else 'HORIZON_NOT_REACHED' if now<end else 'INCOMPLETE_FUTURE'
            values=(100*(future[-1]['close']/price-1),100*(max(r['high'] for r in future)/price-1),100*(min(r['low'] for r in future)/price-1)) if complete else (None,None,None)
            with db:
                db.execute('INSERT INTO live_horizons VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(signal_id,minutes) DO UPDATE SET status=excluded.status,observed_minutes=excluded.observed_minutes,reason=excluded.reason,return_pct=excluded.return_pct,mfe_pct=excluded.mfe_pct,mae_pct=excluded.mae_pct,evaluated_at=excluded.evaluated_at',
                           (sid,minutes,status,len(future),reason,*values,now))


def open_runtime(root,config,exchange):
    db=scanner.connect(Path(root)/(exchange.lower()+'.db'))
    try:
        scanner.initialize(db,config['markets'],config['signal_start'])
        observation_schema(db)
    except BaseException:db.close();raise
    return db


def backup_runtime(db,path):
    if path.exists():return
    backup=sqlite3.connect(path)
    try:
        db.backup(backup)
        if backup.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Runtime backup failed')
    finally:backup.close()


def worker(root):
    root=Path(root);config=json.loads((root/'config.json').read_text(encoding='utf8'))
    if root.resolve().parent!=RUNTIME_ROOT.resolve():raise ValueError('Unsafe runtime location')
    validate_config(config)
    budget=Budget(root,config);dbs={};sessions={};clients={};status='BLOCKED';reason=None
    began=time.time();cycles=0;reopened=False;last_errors={};locks=ExitStack()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:setattr(budget,'stop',True))
    try:
        locks.enter_context(scanner.exclusive(RUNTIME_ROOT/'observer'))
        for exchange in HOSTS:locks.enter_context(scanner.exclusive(root/(exchange.lower()+'.db')))
        budget.event('WORKER_START',pid=os.getpid(),config=config,process_start=began)
        for exchange in HOSTS:
            listed,_=budget.request(exchange,'/v1/market/all',{})
            supported={r['market'] for r in listed if isinstance(r,dict) and 'market' in r}
            missing=set(config['markets'])-supported
            if missing:raise ValueError(f'{exchange} fixed markets unsupported: {sorted(missing)}')
            dbs[exchange]=open_runtime(root,config,exchange)
            sessions[exchange]=ops.start_session(dbs[exchange])
            clients[exchange]=scanner.collector.Client(transport=lambda endpoint,params,e=exchange:budget.request(e,endpoint,params),sleep=budget.sleep)
        while time.time()<config['deadline']:
            budget.check()
            for exchange,db in dbs.items():
                budget.check()
                # The unmodified V4 engine controls candle admission, signal,
                # label, first cluster and LIVE/CATCHUP membership.
                scanner.cycle(db,clients[exchange],emit=lambda msg,e=exchange:budget.event('ENGINE',exchange=e,message=msg),session_id=sessions[exchange])
                record_metrics(db,exchange,int(time.time()))
                last_errors[exchange]=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')]
                if last_errors[exchange]:raise ObservationStop('COLLECTION_ERRORS; no unattended continuation')
            cycles+=1
            budget.event('ROUND_COMPLETE',round=cycles,requests=budget.requests,
                watermarks={e:db.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0] for e,db in dbs.items()})
            if not reopened:
                # Real disk close/reopen, retaining the process/DB writer locks.
                for exchange,db in list(dbs.items()):
                    before=ops.full_fingerprints(db)
                    backup_runtime(db,root/(exchange.lower()+'.bootstrap-backup.db'))
                    ops.close_cleanly(db);dbs[exchange]=open_runtime(root,config,exchange)
                    if before!=ops.full_fingerprints(dbs[exchange]):raise AssertionError('Restart changed persisted values')
                reopened=True;budget.event('DISK_REOPEN_VERIFIED',observation_gap_not_filled=True)
            until=max(1,65-time.time()%60)
            if time.time()+until>=config['deadline']:
                while time.time()<config['deadline']-.5:budget.sleep(min(.5,config['deadline']-time.time()-.5))
                break
            budget.sleep(until)
        status='FINISHED';reason='TIME_BOUND_COMPLETED'
    except ObservationStop as exc:
        reason=str(exc);status='STOPPED' if reason=='STOP_REQUESTED' else 'BOUNDED_STOP' if reason in ('TIME_LIMIT','REQUEST_LIMIT') else 'BLOCKED'
    except Exception as exc:reason=repr(exc);status='BLOCKED'
    finally:
        # No signal after shutdown is manufactured. Metrics use already collected bars.
        close_errors={};per_exchange={}
        for exchange,db in dbs.items():
            try:
                record_metrics(db,exchange,int(time.time()))
                ops.end_session(db,sessions[exchange],'CLOSED' if status=='FINISHED' else 'STOPPED' if status in ('STOPPED','BOUNDED_STOP') else 'ERROR',reason=reason)
                last_errors[exchange]=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')]
                per_exchange[exchange]=dict(stats=scanner.grouped_statistics(db),
                    candle_rows=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],
                    integrity=db.execute('PRAGMA quick_check').fetchone()[0],
                    horizons=[dict(r) for r in db.execute('SELECT minutes,status,COUNT(*) AS n FROM live_horizons GROUP BY minutes,status')],
                    late_candles=db.execute('SELECT COUNT(*) FROM scanner_late_candles').fetchone()[0])
                ops.close_cleanly(db)
            except Exception as exc:
                close_errors[exchange]=repr(exc)
                try:db.close()
                except Exception:pass
        locks.close()
        ended=time.time()
        result=dict(status=status,reason=reason,worker_pid=os.getpid(),worker_started_at=began,worker_ended_at=ended,
            elapsed_seconds=ended-began,signal_start=config['signal_start'],requests=budget.requests,
            completed_rounds=cycles,disk_reopen_verified=reopened,per_exchange=per_exchange,
            close_errors=close_errors,collection_errors=last_errors,peak_rss_bytes=budget.peak_rss,
            data_bytes=sum(p.stat().st_size for p in root.iterdir() if p.is_file()),
            no_orders=True,unattended_continuation=False,performance_verdict='INSUFFICIENT_DATA')
        write_json(root/'worker_summary.json',result)
        print(json.dumps(dict(status=status,reason=reason,requests=budget.requests,rounds=cycles,root=str(root))),flush=True)
    return 0 if status in ('FINISHED','STOPPED','BOUNDED_STOP') and not close_errors else 1


def validate_config(config):
    if config['markets']!=MARKETS or config['policy']!=scanner.POLICY:raise ValueError('Frozen observation config mismatch')
    if not 0<config['max_requests']<=MAX_REQUESTS or not 0<config['duration_seconds']<=MAX_SECONDS:
        raise ValueError('Outside observation bounds')
    if config['deadline']!=config['created_at']+config['duration_seconds']:raise ValueError('Deadline reset forbidden')


def run(root,seconds,resume=False,max_requests=MAX_REQUESTS):
    root=Path(root).resolve();base=RUNTIME_ROOT.resolve()
    if root.parent!=base:raise ValueError('Runtime must be a fresh direct child of data/scanner_v42_live')
    if not 0<seconds<=MAX_SECONDS:raise ValueError('At most 900 seconds')
    if not 0<max_requests<=MAX_REQUESTS:raise ValueError('At most 220 HTTP attempts')
    if resume:
        config=json.loads((root/'config.json').read_text(encoding='utf8'));validate_config(config)
        if time.time()>=config['deadline'] or (root/'STOP').exists():raise ValueError('Expired/stopped episode cannot resume')
    else:
        root.mkdir(parents=True,exist_ok=False)
        now=time.time();config=dict(created_at=now,duration_seconds=seconds,deadline=now+seconds,
            signal_start=(int(now)//300+1)*300,markets=MARKETS,max_requests=max_requests,
            policy=scanner.POLICY,version='4.2_OBSERVATION_WRAPPER',hosts=HOSTS,
            bootstrap='New public API warmup only; no original database input',score='NOT_DEFINED_BY_V4')
        write_json(root/'config.json',config)
    if shutil.disk_usage(root).free<256*1024*1024:raise RuntimeError('Insufficient free disk for bounded observation')
    with scanner.exclusive(base/'supervisor'):
        # A single worker, no detached descendants; watchdog reaps it on timeout.
        process=subprocess.Popen([sys.executable,'-m',__spec__.name,'--execute-live','--worker','--runtime-dir',str(root)],
                                 creationflags=0x08000000 if os.name=='nt' else 0)
        write_json(root/'supervisor.json',dict(pid=os.getpid(),worker_pid=process.pid,started_at=time.time(),hard_deadline=config['deadline']+30))
        try:returncode=process.wait(timeout=max(1,config['deadline']-time.time()+30))
        except subprocess.TimeoutExpired:
            process.kill();process.wait();returncode=124
            write_json(root/'watchdog.json',dict(status='BLOCKED',reason='HARD_TIMEOUT_KILLED_AND_REAPED',at=time.time(),pid=process.pid))
        except KeyboardInterrupt:
            (root/'STOP').touch()
            try:returncode=process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill();process.wait();returncode=124
        write_json(root/'supervisor_exit.json',dict(ended_at=time.time(),worker_returncode=returncode,worker_reaped=True,automatic_restart=False))
        return returncode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-live',action='store_true')
    parser.add_argument('--runtime-dir',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=MAX_SECONDS)
    parser.add_argument('--max-requests',type=int,default=MAX_REQUESTS)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.execute_live:parser.error('Explicit public LIVE opt-in required')
    if args.worker:return worker(args.runtime_dir)
    return run(args.runtime_dir,args.seconds,args.resume,args.max_requests)


if __name__=='__main__':raise SystemExit(main())
