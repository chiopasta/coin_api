"""Read-only presentation of V15 DBs using the existing V7 analyzer functions.

Stored metrics only; no detection, outcome engine, optimization or new labels.
"""
from contextlib import closing
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

from . import v15_control as control

KST=timezone(timedelta(hours=9))
ANALYZER=Path(os.environ.get('V15_ANALYZER_PATH','C:/dev/Coin_api/db_analyzer_v7.py'))
ANALYZER_SHA='9ab8f798b99992ec9149a0814cef91cf4749c074190482bd08d2a259d273b703'
GROUPS=('V15_CURRENT','V15_LEGACY')
LIMIT=200


def analyzer():
    if not ANALYZER.is_file() or hashlib.sha256(ANALYZER.read_bytes()).hexdigest()!=ANALYZER_SHA:
        raise RuntimeError('EXISTING_V7_ANALYZER_UNAVAILABLE_OR_CHANGED')
    spec=importlib.util.spec_from_file_location('_existing_v15_analyzer',ANALYZER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def catalog():
    return {'V15_CURRENT':control.DATABASE,'V15_LEGACY':Path('C:/dev/Coin_api/crypto_scanner.db')}


def timestamp(value):
    try:return datetime.strptime(value,'%Y-%m-%d %H:%M:%S').replace(tzinfo=KST).timestamp()
    except (TypeError,ValueError):return None


def finite(value):return isinstance(value,(int,float)) and math.isfinite(value)


class View:
    def __init__(self):
        self.lock=threading.RLock();self.rows=[];self.errors=[];self.at=None
        self.stopped=threading.Event();self.thread=None;self.last_refresh=0
        self.module=None;self.paper={};self.source_cache={}

    def number(self,value):
        result=self.module.as_float(value)
        return result if finite(result) else None

    def integer(self,value):return self.module.as_int(value)

    def load(self,path):
        began=time.monotonic()
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=.05)) as db:
            db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
            db.set_progress_handler(lambda:int(time.monotonic()-began>.35),1000)
            self.module.schema_check(db)
            signals=[dict(r) for r in db.execute('SELECT * FROM signals ORDER BY id')]
            history=[dict(r) for r in db.execute('SELECT * FROM signal_price_history ORDER BY signal_id,minute')]
            trades=self.module.load_trades(db)
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            events=[dict(r) for r in db.execute('SELECT e.*,t.* FROM prepump_events e JOIN prepump_tracking t ON t.event_id=e.id ORDER BY e.id')] if {'prepump_events','prepump_tracking'}<=tables else []
        return signals,history,trades,events

    def signal(self,row,group,histories,kind='SURGE'):
        t=timestamp(row['created_at']);sid=self.integer(row['id']);now=time.time()
        origin=self.number(row.get('price'));hist=histories.get(sid,{}) if kind=='SURGE' else {}
        result=dict(dataset=group,cohort=group,signal_id=('s' if kind=='SURGE' else 'p')+str(sid),
            market=row['market'],exchange=row['exchange'],signal_time=t,detected_at=t,
            detection_time_basis='SAVED_LOCAL_CREATED_AT; independent event/reference timestamp unavailable',
            timezone_basis='KST_ASSUMED_FOR_NAIVE_LOCAL_CLOCK',source='V15',engine='V15',
            scope='CURRENT_LIVE' if group=='V15_CURRENT' else 'ARCHIVE',pattern=kind if kind=='SURGE' else row['level'],
            score=self.integer(row['score']) if kind=='SURGE' else None,strength=self.number(row.get('strength')),
            signal_price=origin,detection_price=origin,reason=row.get('reason'),horizons=[],outcomes=[],
            features={k:self.number(row.get(k)) for k in ('price_1m','price_5m','price_15m','volume_5m','volume_15m','volume_60m')},
            unsupported=['independent signal reference time','pre-signal OHLC','trade execution profit','strategy optimization'])
        periods=[(n,f'{n}m') for n in (5,10,30,60)] if kind=='SURGE' else [(h*60,f'{h}h') for h in (3,6,12,24,48,72)]
        for minutes,label in periods:
            saved={key:self.number(row.get(column+'_'+label)) for key,column in
                   [('return_pct','return'),('mfe_pct','max_profit' if kind=='SURGE' else 'mfe'),
                    ('mae_pct','max_drawdown' if kind=='SURGE' else 'mae')]}
            valid=False;count=0;explanation='UNVERIFIED_CHECKPOINT_TIME' if kind!='SURGE' else 'MISSING_OR_DELAYED_SAMPLES'
            if kind=='SURGE' and t is not None and origin and origin>0:
                selected=[hist.get(n) for n in range(minutes+1)]
                count=sum(h is not None for h in selected)
                valid=count==minutes+1 and all(h['price'] and h['price']>0 and h['observed_at'] is not None and
                    n*60<=h['observed_at']-t<(n+1)*60 and h['observed_at']<=now for n,h in enumerate(selected))
                if valid:
                    endpoint=(selected[-1]['price']/origin-1)*100
                    valid=saved['return_pct'] is not None and math.isclose(saved['return_pct'],endpoint,abs_tol=1e-7)
                    explanation='STORED_SAMPLED_PRICES; trade freshness unverified' if valid else 'SAVED_ENDPOINT_MISMATCH'
                elif count<minutes+1:explanation='MISSING_SAMPLES'
                else:explanation='DELAYED_OR_INVALID_SAMPLE_TIMES'
            due=t is not None and now>=t+minutes*60
            status='PENDING' if not due else 'COMPLETE' if valid else 'INSUFFICIENT_DATA'
            result['horizons'].append(dict(minutes=minutes,status=status,observed_minutes=count,
                expected_samples=minutes+1 if kind=='SURGE' else None,basis='V15_SAVED_METRICS',reason=explanation,
                saved_values=saved,**(saved if status=='COMPLETE' else dict(return_pct=None,mfe_pct=None,mae_pct=None))))
        result['candles']=[dict(ts=h['observed_at'],close=h['price'],minute=m) for m,h in sorted(hist.items())
                           if h['observed_at'] is not None and h['observed_at']<=now and h['price'] and h['price']>0]
        result['chart_basis']='V15_OBSERVED_PRICE; no OHLC or pre-signal reconstruction'
        return result

    def refresh(self):
        with self.lock:
            if time.monotonic()-self.last_refresh<4:return
            try:self.module=analyzer()
            except Exception:
                self.errors=['기존 V7 분석기 파일이 없거나 지문이 다릅니다. 분석 연결 미지원.'];return
            rows=[];errors=[];paper={}
            for group,path in catalog().items():
                if not path.is_file():errors.append(group+' DB 없음');continue
                try:
                    wal=Path(str(path)+'-wal')
                    signature=(str(path),path.stat().st_mtime_ns,path.stat().st_size,
                               (wal.stat().st_mtime_ns,wal.stat().st_size) if wal.exists() else None)
                    cached=self.source_cache.get(group)
                    if cached and cached[0]==signature:data=cached[1]
                    else:
                        data=self.load(path);self.source_cache[group]=(signature,data)
                    signals,history,trades,events=data
                    histories={}
                    for h in history:
                        sid=self.integer(h['signal_id']);minute=self.integer(h['minute'])
                        if sid is not None and minute is not None:
                            histories.setdefault(sid,{})[minute]=dict(price=self.number(h['price']),observed_at=timestamp(h.get('observed_at')))
                    rows.extend(self.signal(s,group,histories) for s in signals)
                    rows.extend(self.signal(s,group,{},'PRE_PUMP') for s in events)
                    closed=[dict(pnl_pct=self.number(r['pnl_pct'])) for r in trades if r['status']=='CLOSED']
                    raw=self.module.basic_stats(closed)
                    paper[group]=dict(n=raw['n'] if raw else 0,mean_pct=raw['mean'] if raw else None,
                                      win_pct=raw['win'] if raw else None,open=sum(r['status']=='OPEN' for r in trades),
                                      basis='EXISTING_PAPER_RECORDS; no execution custody; OPEN excluded')
                except (Exception,SystemExit):errors.append(group+' DB 읽기 실패 · 일부 결과 누락')
            rows.sort(key=lambda r:(r['detected_at'] or 0,r['dataset'],r['signal_id']),reverse=True)
            self.rows,self.errors,self.paper=rows,errors,paper;self.at=time.time();self.last_refresh=time.monotonic()

    def start(self):
        def run():
            while not self.stopped.is_set():
                self.refresh()
                if self.stopped.wait(5):break
        self.thread=threading.Thread(target=run,name='v15-db-view',daemon=True);self.thread.start()

    def close(self):
        self.stopped.set()
        if self.thread:self.thread.join(5)

    def stats(self,rows):
        def metric(minutes,key):
            values=[dict(value=h[key]) for row in rows for h in row['horizons'] if h['minutes']==minutes and h['status']=='COMPLETE' and finite(h[key])]
            result=self.module.basic_stats(values,'value') if self.module else None
            return dict(value=result['mean'] if result else None,n=result['n'] if result else 0,
                        win=result['win'] if result else None)
        ret=metric(30,'return_pct')
        return dict(total=len(rows),analyzed=sum(any(h['status']=='COMPLETE' for h in r['horizons']) for r in rows),
            return_30m=ret,rise_30m=dict(value=ret['win'],n=ret['n']),mfe_30m=metric(30,'mfe_pct'),
            mae_30m=metric(30,'mae_pct'),curve=[dict(minutes=n,**metric(n,'return_pct')) for n in (5,10,30,60)],
            incomplete=sum(any(h['status']=='INSUFFICIENT_DATA' for h in r['horizons']) for r in rows),
            pending=sum(any(h['status']=='PENDING' for h in r['horizons']) for r in rows))

    def report(self,group='V15_CURRENT',offset=0):
        if group not in (*GROUPS,'ALL') or offset<0:raise LookupError('Invalid V15 group')
        self.refresh()
        with self.lock:
            rows=[r for r in self.rows if group=='ALL' or r['cohort']==group]
            patterns=sorted({(r['cohort'],r['pattern']) for r in rows})
            patterns=[dict(cohort=c,pattern=p,**self.stats([r for r in rows if r['cohort']==c and r['pattern']==p])) for c,p in patterns]
            bins=[]
            for cohort in sorted({r['cohort'] for r in rows}):
                for label,lo,hi in [('0~39',0,40),('40~59',40,60),('60~79',60,80),('80+',80,101)]:
                    subset=[r for r in rows if r['cohort']==cohort and r['score'] is not None and lo<=r['score']<hi]
                    if subset:bins.append(dict(cohort=cohort,pattern='SCORE '+label,**self.stats(subset)))
            summary=self.stats(rows)
            if group=='ALL':
                for key in ('return_30m','rise_30m','mfe_30m','mae_30m'):summary[key]=dict(value=None,n=0)
                summary['curve']=[dict(minutes=n,value=None,n=0) for n in (5,10,30,60)]
            return dict(summary=summary,patterns=patterns,score_groups=bins,signals=rows[offset:offset+LIMIT],
                        group=group,offset=offset,limit=LIMIT,at=self.at,errors=list(self.errors),
                        paper={g:v for g,v in self.paper.items() if group=='ALL' or g==group},
                        analyzer=dict(name='Existing db_analyzer_v7.py',sha256=ANALYZER_SHA,optimization_called=False),
                        limitations=['V15 is unvalidated','PRE-PUMP checkpoint timing/continuous chart unverified','Observed prices are not realized investment returns'])

    def snapshot(self,scope='ALL'):
        if scope not in ('ALL','CURRENT_LIVE','ARCHIVE','STORED_OBSERVATION'):raise LookupError('Invalid scope')
        self.refresh()
        state=control.snapshot()
        public={k:v for k,v in state.items() if k not in ('child','launch_id','root','processes')}
        public['connections']={e:dict(status=v['status'],at=v.get('last_received')) for e,v in state.get('exchanges',{}).items()}
        public['markets']=state.get('received_unique') if state.get('heartbeat_fresh') else None
        public['venue_pairs']=sum(v['received'] for v in state.get('exchanges',{}).values()) if state.get('heartbeat_fresh') else None
        public['collected']=max([v.get('last_received') or 0 for v in state.get('exchanges',{}).values()],default=0) or None
        public['clock']='UNSUPPORTED_V15_NO_NTP_GATE'
        public['size']=control.DATABASE.stat().st_size if control.DATABASE.exists() else None
        with self.lock:
            rows=[r for r in self.rows if scope=='ALL' or r['scope']==scope]
            today=datetime.now(KST).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
            return dict(web='RUNNING',engine='V15',scanner=public,signals=rows[:LIMIT],total=len(rows),
                today_live_signals=sum(r['cohort']=='V15_CURRENT' and r['detected_at'] is not None and r['detected_at']>=today for r in self.rows),
                errors=list(self.errors),at=time.time(),limit=LIMIT)

    def detail(self,key,signal_id):
        if key not in GROUPS or not re.fullmatch('[sp][0-9]{1,20}',signal_id):raise LookupError('Unknown V15 signal')
        self.refresh()
        with self.lock:
            result=next((r for r in self.rows if r['dataset']==key and r['signal_id']==signal_id),None)
            if result is None:raise LookupError('Unknown V15 signal')
            return result
