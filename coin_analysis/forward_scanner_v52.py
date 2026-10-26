"""Bounded public KRW WebSocket observation; frozen V4 research core.

Network threads never write SQLite. A bounded queue feeds one writer. Stream
bars are admitted only after a whole connected minute and the existing settle
delay. Disconnected/partial/late minutes stay absent pending bounded REST repair.
An explicit launch freezes its catalog; membership changes stop that dataset
rather than altering the core's frozen universe or deleting existing evidence.
"""
import argparse
from collections import Counter, OrderedDict
from contextlib import ExitStack
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import uuid

from . import forward_scanner_v43 as legacy

scanner, ops, candles = legacy.scanner, legacy.ops, legacy.candles
RUNTIME_ROOT = legacy.RUNTIME_ROOT
WS_URLS = dict(UPBIT='wss://api.upbit.com/websocket/v1',
               BITHUMB='wss://ws-api.bithumb.com/websocket/v1')
SHARD_SIZE = 100  # Conservative local batch, not a claimed exchange code limit.
MAX_CONNECT_ATTEMPTS = 3
QUEUE_SIZE = 8192
FRESH_SECONDS = 60
CATALOG_REFRESH_SECONDS = 600
MAX_FRAME_BYTES = 1024*1024


def catalog(rows, now):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Invalid/empty market catalog')
    result = {}
    for row in rows:
        market = row.get('market') if isinstance(row, dict) else None
        if not isinstance(market, str) or not re.fullmatch(r'KRW-[A-Z0-9]+', market):
            continue
        reason = exclusion(row, now)
        if market in result:
            raise ValueError('Duplicate market catalog entry')
        result[market] = dict(eligible=reason is None, reason=reason or 'PUBLIC_KRW_LISTED',
                              status_evidence='OFFICIAL_FIELDS' if any(k in row for k in
                              ('market_state','is_trading_suspended','delisting_date')) else 'LIST_ONLY_STATUS_UNKNOWN')
    if not result:
        raise ValueError('No KRW market catalog entries')
    return result


def exclusion(row, now):
    if row.get('is_trading_suspended') is True:
        return 'OFFICIAL_TRADING_SUSPENDED'
    if row.get('market_state') not in (None, '', 'ACTIVE'):
        return 'OFFICIAL_MARKET_STATE_'+str(row['market_state'])
    date = row.get('delisting_date')
    if date:
        # Future announced delisting is not the same as an already ended market.
        from datetime import datetime
        try:
            ended = datetime.fromisoformat(str(date).replace('Z','+00:00'))
            if ended.tzinfo is None:
                from datetime import timezone, timedelta
                ended = ended.replace(tzinfo=timezone(timedelta(hours=9)))
            if ended.timestamp() <= now:
                return 'OFFICIAL_DELISTED'
        except ValueError:
            return 'UNPARSEABLE_OFFICIAL_DELISTING_DATE'
    return None


def subscriptions(markets):
    markets = sorted(set(markets))
    return [markets[n:n+SHARD_SIZE] for n in range(0,len(markets),SHARD_SIZE)]


def payload(markets):
    # Both exchanges document DEFAULT and both trade/ticker in one request.
    # Request snapshots too; snapshots are status evidence, never trade input.
    return json.dumps([dict(ticket=uuid.uuid4().hex),dict(type='trade',codes=markets),
                       dict(type='ticker',codes=markets),dict(format='DEFAULT')])


class Streams:
    """Bounded connection attempts and queues; backpressure fails closed."""
    def __init__(self, catalogs, deadline, connect=None):
        self.catalogs, self.deadline = catalogs, deadline
        self.queue = queue.Queue(QUEUE_SIZE)
        self.stopped = threading.Event()
        self.overflow = threading.Event()
        self.threads, self.sockets = [], []
        self.lock = threading.Lock()
        self.next_connect = 0.
        self.connect = connect

    def put(self, kind, exchange, shard, value=None):
        try:
            self.queue.put_nowait((kind, exchange, shard, time.time(), value))
        except queue.Full:
            self.overflow.set(); self.stopped.set()

    def start(self):
        for exchange, markets in self.catalogs.items():
            for n, codes in enumerate(subscriptions(markets)):
                thread = threading.Thread(target=self.receive,args=(exchange,n,codes),daemon=True)
                self.threads.append(thread); thread.start()

    def receive(self, exchange, shard, codes):
        import websocket
        connect = self.connect or websocket.create_connection
        for attempt in range(MAX_CONNECT_ATTEMPTS):
            if self.stopped.is_set() or time.monotonic() >= self.deadline:
                break
            sock = None
            try:
                with self.lock:
                    wait = max(0,self.next_connect-time.monotonic())
                    if self.stopped.wait(wait):break
                    self.next_connect = time.monotonic()+.3  # Global < 5/s.
                self.put('CONNECTING',exchange,shard,dict(attempt=attempt+1,codes=codes))
                sock = connect(WS_URLS[exchange],timeout=3,enable_multithread=True,
                               skip_utf8_validation=False)
                with self.lock:self.sockets.append(sock)
                sock.send(payload(codes));sock.settimeout(1)
                self.put('SUBSCRIBED',exchange,shard,codes)
                ping = time.monotonic()
                while not self.stopped.is_set() and time.monotonic()<self.deadline:
                    try:
                        raw = sock.recv()
                    except websocket.WebSocketTimeoutException:
                        if time.monotonic()-ping>=20:
                            sock.ping();ping=time.monotonic()
                        continue
                    if not raw:raise ConnectionError('Remote closed')
                    if len(raw)>MAX_FRAME_BYTES:raise ValueError('WebSocket frame limit')
                    self.put('MESSAGE',exchange,shard,raw)
                    if time.monotonic()-ping>=20:
                        sock.ping();ping=time.monotonic()
            except Exception as exc:
                self.put('DISCONNECTED',exchange,shard,type(exc).__name__)
                if getattr(exc,'status_code',None) in (418,429):
                    self.put('BLOCKED',exchange,shard,'WS_RATE_LIMIT_OR_IP_BLOCK')
                    break
            finally:
                if sock is not None:
                    sock.close(timeout=1)
                    with self.lock:
                        if sock in self.sockets:self.sockets.remove(sock)
            if self.stopped.wait(min(2**attempt,4)):break
        self.put('EXHAUSTED',exchange,shard)

    def close(self):
        self.stopped.set()
        with self.lock:sockets=list(self.sockets)
        for sock in sockets:
            try:sock.shutdown()
            except OSError:pass
        until=time.monotonic()+5
        for thread in self.threads:thread.join(max(0,until-time.monotonic()))
        return all(not t.is_alive() for t in self.threads)


class Bridge:
    """One exchange, one SQLite writer, event time separate from receipt time."""
    def __init__(self, db, exchange, listed):
        self.db, self.exchange, self.listed = db, exchange, listed
        self.markets = {m:dict(state='REGISTERED' if v['eligible'] else 'EXCLUDED',
                             reason=v['reason'],last_received=None,last_exchange=None,
                             subscribed=False,confirmed=False,shard=None)
                        for m,v in listed.items()}
        self.shards, self.bars, self.seen = {}, {}, OrderedDict()
        self.counters = Counter()
        self.repair = set()
        self.gaps = {}
        db.executescript('''
          CREATE TABLE IF NOT EXISTS ws_candles(market TEXT,ts INTEGER,volume REAL,
            received_at REAL,exchange_at REAL,basis TEXT,PRIMARY KEY(market,ts));
          CREATE TABLE IF NOT EXISTS ws_signal_provenance(signal_id TEXT PRIMARY KEY,
            exchange TEXT,received_at REAL,exchange_at REAL,receive_delay REAL,
            evaluation_delay REAL,quality TEXT);
        ''')

    def subscribed(self, shard, markets, now):
        self.shards[shard] = dict(status='CONNECTED',since=now,at=now,codes=markets)
        for market in markets:
            self.markets[market].update(subscribed=True,confirmed=False,shard=shard,
                                       state='SUBSCRIBED',last_received=None)
            self.repair.add(market)
            state=self.db.execute('SELECT verified_until FROM scanner_state WHERE market=?',(market,)).fetchone()
            end=candles.closed_cutoff(now)
            self.gaps[market]=(end,math.ceil(now/60)*60)
            if state[0]<end:
                with self.db:
                    self.db.execute('INSERT OR IGNORE INTO collection_jobs VALUES(?,?,?,?)',
                        (market,state[0],end,end))

    def disconnect(self, shard, now):
        self.counters['disconnects']+=1
        info=self.shards.get(shard,dict(codes=[]))
        info.update(status='DISCONNECTED',at=now);self.shards[shard]=info
        for market in info['codes']:
            self.markets[market].update(subscribed=False,confirmed=False,state='STALE')
            self.repair.add(market)
            for key in list(self.bars):
                if key[0]==market:del self.bars[key]

    def message(self, raw, received):
        self.counters['messages']+=1
        self.counters['bytes']+=len(raw)
        row=json.loads(raw)
        if not isinstance(row,dict) or row.get('error'):
            raise ValueError('WebSocket error/schema')
        if row.get('status')=='UP':return
        kind=row.get('type');market=row.get('code')
        if kind not in ('trade','ticker') or market not in self.markets:
            raise ValueError('Unexpected message type/market')
        state=self.markets[market]
        reason=exclusion(row,received)
        if reason:
            state.update(state='EXCLUDED',reason=reason);self.listed[market]['eligible']=False
            return
        if not self.listed[market]['eligible']:
            if kind=='ticker' and row.get('market_state')=='ACTIVE' and row.get('is_trading_suspended') is False:
                self.listed[market]['eligible']=True
                state.update(state='SUBSCRIBED',reason='OFFICIAL_TRADING_RESUMED')
                self.repair.add(market)
                verified=self.db.execute('SELECT verified_until FROM scanner_state WHERE market=?',(market,)).fetchone()
                if verified is None:return  # Initially excluded: next frozen dataset required.
                self.gaps[market]=(verified[0],math.ceil(received/60)*60)
            else:return
        price,volume=float(row['trade_price']),float(row['trade_volume'])
        exchange_at=float(row['trade_timestamp'])/1000
        if not all(math.isfinite(v) for v in (price,volume,exchange_at)) or price<=0 or volume<0:
            raise ValueError('Invalid trade price/volume/timestamp')
        # No KST date arithmetic or guessed timestamp correction.
        if exchange_at>received+legacy.clock_guard.MAX_OFFSET_SECONDS:
            raise ValueError('Future exchange trade timestamp')
        state['confirmed']=True
        if state['state']!='BLOCKED' and 0<=received-exchange_at<=FRESH_SECONDS:
            state.update(state='ACTIVE',last_received=received,last_exchange=exchange_at)
        if kind!='trade' or row.get('stream_type')!='REALTIME':return
        key=(market,str(row['sequential_id']))
        signature=(exchange_at,price,volume,row.get('ask_bid'))
        if key in self.seen:
            if self.seen[key]!=signature:
                raise ValueError('Conflicting trade ID')
            self.counters['duplicates']+=1;return
        self.seen[key]=signature
        if len(self.seen)>100000:self.seen.popitem(last=False)
        minute=int(exchange_at)//60*60
        shard=self.shards.get(state['shard'])
        if not shard or shard['status']!='CONNECTED':return
        # First connected partial minute cannot prove a complete OHLCV bar.
        if minute < math.ceil(shard['since']/60)*60:
            self.counters['partial_trades']+=1;return
        cutoff=candles.closed_cutoff(received)
        if minute<cutoff:
            self.counters['late_trades']+=1;self.repair.add(market)
            state.update(state='BLOCKED',reason='LATE_TRADE_AFTER_SETTLE')
            return
        if state['state']=='BLOCKED':return
        bar=self.bars.get((market,minute))
        p,v=Decimal(str(row['trade_price'])),Decimal(str(row['trade_volume']))
        if bar is None:
            self.bars[market,minute]=dict(open=p,high=p,low=p,close=p,value=p*v,volume=v,
                first=exchange_at,last=exchange_at,received=received)
        else:
            if exchange_at<bar['last']:self.counters['out_of_order']+=1
            if exchange_at<bar['first']:bar.update(open=p,first=exchange_at)
            if exchange_at>=bar['last']:bar.update(close=p,last=exchange_at)
            bar.update(high=max(bar['high'],p),low=min(bar['low'],p),
                       value=bar['value']+p*v,volume=bar['volume']+v,received=received)

    def flush(self, now):
        cutoff=candles.closed_cutoff(now)
        with self.db:
            for (market,ts),bar in list(self.bars.items()):
                if ts>=cutoff:continue
                state=self.markets[market];shard=self.shards.get(state['shard'],{})
                if shard.get('status')=='CONNECTED' and state['state'] not in ('BLOCKED','EXCLUDED'):
                    values=tuple(float(bar[k]) for k in ('open','high','low','close','value'))
                    old=self.db.execute('SELECT open,high,low,close,trade_value FROM minute_candles WHERE market=? AND ts=?',(market,ts)).fetchone()
                    if old and any(abs(a-b)>max(1e-8,abs(b)*1e-8) for a,b in zip(old,values)):
                        raise scanner.CandleConflictError('REST/WS candle conflict')
                    self.db.execute('INSERT OR IGNORE INTO minute_candles VALUES(?,?,?,?,?,?,?)',(market,ts,*values))
                    self.db.execute('INSERT OR IGNORE INTO candle_receipts VALUES(?,?,?)',(market,ts,math.ceil(now)))
                    self.db.execute('INSERT OR IGNORE INTO ws_candles VALUES(?,?,?,?,?,?)',
                        (market,ts,float(bar['volume']),bar['received'],bar['last'],
                         'CONNECTED_TRADE_AGGREGATE; NO_EXCHANGE_SEQUENCE_CONTINUITY_PROOF'))
                    self.counters['closed_candles']+=1
                del self.bars[market,ts]
            # The range has been observed; absent minutes are NOT filled.
            # Disconnected markets stop the shared core watermark until recovery.
            for market,state in self.markets.items():
                shard=self.shards.get(state['shard'],{})
                if state['state']=='EXCLUDED':
                    # Operational exclusion, not a synthetic candle or range.
                    # Preserve cluster state. Do not emit signals for a suspended
                    # market or let its unavailable range stall every other pair.
                    self.db.execute('UPDATE scanner_state SET verified_until=MAX(verified_until,?),last_observation=MAX(last_observation,?) WHERE market=?',
                                    (cutoff,cutoff//300*300,market))
                    continue
                pending=self.db.execute('SELECT 1 FROM collection_jobs WHERE market=?',(market,)).fetchone()
                if not pending and state['subscribed'] and shard.get('status')=='CONNECTED' and state['state'] not in ('BLOCKED','EXCLUDED'):
                    self.db.execute('UPDATE scanner_state SET verified_until=MAX(verified_until,?) WHERE market=?',(cutoff,market))

    def schedule_gaps(self, now):
        """Repair the first partial minute only after it has actually closed."""
        for market,(start,end) in list(self.gaps.items()):
            if candles.closed_cutoff(now)<end:continue
            if self.db.execute('SELECT 1 FROM collection_jobs WHERE market=?',(market,)).fetchone():continue
            if end>start:
                with self.db:self.db.execute('INSERT INTO collection_jobs VALUES(?,?,?,?)',(market,start,end,end))
                self.repair.add(market)
            del self.gaps[market]

    def evaluate(self, now, emit=lambda _:None):
        before=dict(self.db.execute('SELECT market,last_observation FROM scanner_state'))
        scanner.process_observations(self.db,int(now),emit,detected_clock=lambda:now)
        scanner.evaluate_outcomes(self.db,int(now),emit)
        legacy.coverage(self.db,before,int(now));legacy.record_metrics(self.db,self.exchange,int(now))
        with self.db:
            for row in self.db.execute('SELECT * FROM signals WHERE signal_id NOT IN (SELECT signal_id FROM ws_signal_provenance)').fetchall():
                receipts=self.db.execute('SELECT MAX(first_received_at) FROM candle_receipts WHERE market=? AND ts<?',
                                         (row['market'],row['signal_time'])).fetchone()[0]
                last=self.db.execute('SELECT received_at,exchange_at FROM ws_candles WHERE market=? AND ts=?',
                                     (row['market'],row['signal_time']-60)).fetchone()
                self.db.execute('INSERT INTO ws_signal_provenance VALUES(?,?,?,?,?,?,?)',
                    (row['signal_id'],self.exchange,last[0] if last else receipts,last[1] if last else None,
                     last[0]-last[1] if last else None,row['delay_seconds'],
                     'FROZEN_V4_CLOSED_CANDLES; MISSING_FEATURES_REMAIN_NULL'))

    def snapshot(self, now):
        counts=Counter();evaluated=0;complete=0
        target=candles.closed_cutoff(now)//300*300
        for market,state in self.markets.items():
            status=state['state']
            if status=='ACTIVE' and (state['last_received'] is None or not 0<=now-state['last_received']<=FRESH_SECONDS):status='STALE'
            counts[status]+=1
            row=self.db.execute('SELECT last_observation FROM scanner_state WHERE market=?',(market,)).fetchone()
            if self.listed[market]['eligible'] and market!='KRW-BTC' and row and row[0]>=target and target>=scanner.config(self.db)['start']:
                evaluated+=1
                n=self.db.execute('SELECT COUNT(*) FROM minute_candles WHERE market=? AND ts>=? AND ts<?',
                                  (market,target-1800,target)).fetchone()[0]
                if n==30:complete+=1
        eligible=sum(v['eligible'] for v in self.listed.values())
        connected=sum(v['status']=='CONNECTED' for v in self.shards.values())
        return dict(eligible=eligible,listed=len(self.listed),registered=len(self.markets),
            subscription_sent=sum(s['subscribed'] for s in self.markets.values()),
            subscription_confirmed=sum(s['confirmed'] and s['subscribed'] and self.listed[m]['eligible'] for m,s in self.markets.items()),
            active=counts['ACTIVE'],stale=counts['STALE'],blocked=counts['BLOCKED'],excluded=counts['EXCLUDED'],
            evaluated=evaluated,complete_30m=complete,evaluation_target=target,
            last_received=max((s['last_received'] for s in self.markets.values() if s['last_received'] is not None),default=None),
            status='CONNECTED' if connected and connected==len(self.shards) else 'PARTIAL' if connected else 'DISCONNECTED',
            shards=len(self.shards),connected_shards=connected,counters=dict(self.counters))


class DeferredRepair(Exception):
    pass


def repair_market(bridge, budget, end, max_pages=4):
    """Reuse durable core pagination; bounded work yields to the WS queue."""
    # The caller chooses the market, persisted across pages/reconnects.
    market=next(iter(bridge.repair))
    pages=0
    def transport(path,params):
        nonlocal pages
        if pages>=max_pages:raise DeferredRepair()
        pages+=1
        return budget.request(bridge.exchange,path,params)
    client=scanner.collector.Client(transport=transport,sleep=budget.sleep)
    try:
        scanner.fetch_market(bridge.db,client,market,end)
    except DeferredRepair:
        return
    bridge.repair.discard(market)


def worker(root, run_id):
    root=Path(root).resolve()
    if root.parent!=RUNTIME_ROOT.resolve():raise ValueError('Unsafe runtime location')
    cfg=json.loads((root/'config.json').read_text(encoding='utf8'))
    if cfg['version']!='5.2_WS' or cfg['policy']!=scanner.POLICY:raise ValueError('Frozen policy mismatch')
    run=json.loads((root/'runs'/f'{run_id}.json').read_text(encoding='utf8'))
    if not 30<=run['duration_seconds']<=legacy.MAX_SECONDS or not 26<=run['max_requests']<=legacy.MAX_REQUESTS or run['deadline']!=run['created_at']+run['duration_seconds']:
        raise ValueError('Invalid launch bounds')
    began=time.time();status='BLOCKED';reason=None;budget=None;control=None;streams=None
    dbs={};bridges={};sessions={};close_errors={};per_exchange={};locks=ExitStack()
    try:
        locks.enter_context(scanner.exclusive(legacy.v42.RUNTIME_ROOT/'observer'))
        control=legacy.ledger(root/'control.db')
        budget=legacy.Budget(root,dict(cfg,markets=[]),run,control)
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:setattr(budget,'stop',True))
        budget.check()
        listings={};receipts={}
        for exchange in WS_URLS:
            rows,_=budget.request(exchange,'/v1/market/all',{})
            listings[exchange]=catalog(rows,time.time())
            receipts[exchange]=legacy.market_scope.receipt(rows,time.time())
        legacy.write_json(root/'catalog.json',dict(at=time.time(),exchanges=listings))
        legacy.write_json(root/'market_scope.json',legacy.market_scope.inventory(receipts))
        cfg['venue_markets']={e:sorted(m for m,v in rows.items() if v['eligible']) for e,rows in listings.items()}
        if cfg.get('validation_markets'):
            for exchange in cfg['venue_markets']:
                if not set(cfg['validation_markets'])<=set(cfg['venue_markets'][exchange]):
                    raise legacy.Stop('UNSUPPORTED_VALIDATION_MARKETS')
                cfg['venue_markets'][exchange]=sorted(cfg['validation_markets'])
                # Out-of-scope listed markets are not registered/subscribed in this test.
                listings[exchange]={m:listings[exchange][m] for m in cfg['validation_markets']}
        cfg['markets']=sorted(set().union(*map(set,cfg['venue_markets'].values())))
        budget.config['markets']=cfg['markets'];legacy.write_json(root/'config.json',cfg)
        for exchange,markets in cfg['venue_markets'].items():
            locks.enter_context(scanner.exclusive(root/(exchange.lower()+'.db')))
            db=legacy.open_runtime(root,dict(cfg,markets=markets),exchange)
            dbs[exchange]=db;budget.receipts[exchange]=db;sessions[exchange]=ops.start_session(db)
            bridges[exchange]=Bridge(db,exchange,listings[exchange])
            bridges[exchange].repair.update(markets)
        streams=Streams(cfg['venue_markets'],budget.monotonic_deadline);streams.start()
        next_update=0.;next_catalog=time.monotonic()+CATALOG_REFRESH_SECONDS
        last_repair=0.;repair_turn=0;refresh_after_reconnect=False
        while True:
            budget.check()
            if streams.overflow.is_set():raise legacy.Stop('WS_QUEUE_OVERFLOW')
            for _ in range(2000):
                try:kind,exchange,shard,received,value=streams.queue.get_nowait()
                except queue.Empty:break
                bridge=bridges[exchange]
                if kind=='SUBSCRIBED':bridge.subscribed(shard,value,received)
                elif kind=='DISCONNECTED':
                    bridge.disconnect(shard,received)
                    refresh_after_reconnect=True
                    budget.event('WS_DISCONNECTED',exchange=exchange,shard=shard,error=value)
                elif kind=='MESSAGE':
                    try:bridge.message(value,received)
                    except (ValueError,KeyError,TypeError,OverflowError) as exc:
                        bridge.counters['errors']+=1
                        # One invalid frame invalidates continuity; stop this run.
                        raise legacy.Stop('WS_SCHEMA_OR_QUALITY_ERROR:'+exchange+':'+str(exc)) from exc
                elif kind=='CONNECTING':
                    bridge.counters['connection_attempts']+=1
                elif kind=='EXHAUSTED':
                    if not streams.stopped.is_set():bridge.disconnect(shard,received)
                elif kind=='BLOCKED':
                    raise legacy.Stop(str(value))
            if not streams.queue.empty():continue  # Never seal ahead of queued receipts.
            now=time.time()
            for bridge in bridges.values():bridge.schedule_gaps(now)
            if time.monotonic()>=next_update:
                for bridge in bridges.values():
                    bridge.flush(now)
                    bridge.evaluate(now,lambda message:budget.event('ENGINE',message=message))
                public=dict(at=now,mode='ALL_KRW_WEBSOCKET',exchanges={e:b.snapshot(now) for e,b in bridges.items()},
                            requests=budget.requests,queue_depth=streams.queue.qsize())
                legacy.write_json(root/'ws_status.json',public)
                legacy.write_json(root/'ws_markets.json',{e:b.markets for e,b in bridges.items()})
                legacy.write_json(root/'heartbeat.json',dict(at=now,run_id=run_id,requests=budget.requests,
                    collection_errors={},rss_bytes=budget.peak_rss,cpu_percent=budget.max_cpu_percent))
                next_update=time.monotonic()+2
            # Bounded initialization / gap repair, not all-market REST polling.
            # Stop spending HTTP before the cap, retain WS collection until time/STOP.
            if time.monotonic()-last_repair>=2 and budget.remaining_seconds()>20 and budget.requests+4<=run['max_requests']:
                venues=list(bridges);bridge=bridges[venues[repair_turn%len(venues)]];repair_turn+=1
                if bridge.repair:
                    try:repair_market(bridge,budget,candles.closed_cutoff(time.time()),max_pages=1)
                    except (scanner.CandleConflictError,candles.CandleValidationError):raise
                    except legacy.Stop:raise
                    except scanner.collector.CollectionBlocked as exc:
                        raise legacy.Stop('PUBLIC_REST_BLOCKED:'+str(exc)) from exc
                    except Exception as exc:
                        bridge.counters['rest_errors']+=1
                        budget.event('REPAIR_ERROR',exchange=bridge.exchange,error=type(exc).__name__)
                    last_repair=time.monotonic()
            if refresh_after_reconnect and budget.requests+2>run['max_requests']:
                raise legacy.Stop('CATALOG_REFRESH_BUDGET_EXHAUSTED')
            if (refresh_after_reconnect or time.monotonic()>=next_catalog) and budget.requests+2<=run['max_requests']:
                for exchange in WS_URLS:
                    rows,_=budget.request(exchange,'/v1/market/all',{})
                    refreshed=catalog(rows,time.time())
                    legacy.write_json(root/('catalog_refresh_'+exchange+'.json'),dict(at=time.time(),markets=refreshed))
                    expected=set(cfg['venue_markets'][exchange])
                    current={m for m,v in refreshed.items() if v['eligible']}
                    if (not expected<=current if cfg.get('validation_markets') else current!=expected):
                        raise legacy.Stop('CATALOG_CHANGED_NEW_FROZEN_DATASET_REQUIRED')
                next_catalog=time.monotonic()+CATALOG_REFRESH_SECONDS
                refresh_after_reconnect=False
            time.sleep(.02)
    except legacy.Stop as exc:
        reason=str(exc)
        status='STOPPED' if reason=='STOP_REQUESTED' else 'BOUNDED_STOP' if reason in ('TIME_LIMIT','REQUEST_LIMIT') else 'BLOCKED'
    except Exception as exc:
        reason=type(exc).__name__+': '+str(exc)
    finally:
        if streams and not streams.close():close_errors['ws_threads']='Unconfirmed receiver shutdown'
        if bridges:
            legacy.write_json(root/'ws_status.json',dict(at=time.time(),mode='ALL_KRW_WEBSOCKET',terminal=True,
                status=status,exchanges={e:b.snapshot(time.time()) for e,b in bridges.items()},
                requests=budget.requests if budget else 0,queue_depth=streams.queue.qsize() if streams else 0))
            legacy.write_json(root/'ws_markets.json',{e:b.markets for e,b in bridges.items()})
        for exchange,db in dbs.items():
            try:
                if not (reason or '').startswith('CLOCK_'):
                    legacy.record_metrics(db,exchange,int(time.time()))
                ops.end_session(db,sessions[exchange],'STOPPED' if status in ('STOPPED','BOUNDED_STOP') else 'ERROR',reason)
                per_exchange[exchange]=dict(integrity=db.execute('PRAGMA quick_check').fetchone()[0],
                    candles=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],
                    signals=scanner.grouped_statistics(db))
                ops.close_cleanly(db)
            except Exception as exc:
                close_errors[exchange]=repr(exc)
                db.close()
        if control:control.close()
        locks.close()
        result=dict(run_id=run_id,status=status,reason=reason,requests=budget.requests if budget else 0,
            started_at=began,ended_at=time.time(),close_errors=close_errors,per_exchange=per_exchange)
        legacy.write_json(root/'runs'/f'{run_id}.summary.json',result)
        print(json.dumps(result),flush=True)
    return 0 if status in ('STOPPED','BOUNDED_STOP') and not close_errors else 1


def run(root, seconds, max_requests, validation_markets=None):
    root=Path(root).resolve()
    if root.parent!=RUNTIME_ROOT.resolve() or root.exists():raise ValueError('New isolated runtime required')
    if not 30<=seconds<=legacy.MAX_SECONDS or not 26<=max_requests<=legacy.MAX_REQUESTS:raise ValueError('Outside existing safety limits')
    if validation_markets is not None and (not 2<=len(validation_markets)<=5 or 'KRW-BTC' not in validation_markets or
           any(not re.fullmatch(r'KRW-[A-Z0-9]+',m) for m in validation_markets)):
        raise ValueError('Explicit small validation cohort requires BTC and up to four alts')
    with scanner.exclusive(legacy.v42.RUNTIME_ROOT/'supervisor'):
        evidence=legacy.clock_guard.verify_clock()
        if evidence['status']!='VERIFIED':raise legacy.Stop(evidence['reason'])
        if legacy.clock_guard.awake_seconds() is None:raise legacy.Stop('CLOCK_SUSPEND_MONITOR_UNAVAILABLE')
        root.mkdir(parents=True,exist_ok=False);(root/'runs').mkdir()
        now=time.time();run_id=uuid.uuid4().hex
        legacy.write_json(root/'config.json',dict(version='5.2_WS',policy=scanner.POLICY,
            signal_start=(int(now)//300+1)*300,created_at=now,validation_markets=validation_markets,
            scope='EXPLICIT_SMALL_VALIDATION' if validation_markets else 'ALL_PUBLIC_LISTED_KRW_WITH_OFFICIAL_STATUS_FILTER'))
        bounds=dict(run_id=run_id,created_at=now,duration_seconds=seconds,deadline=now+seconds,
                    max_requests=max_requests,resume=False,clock_admission=evidence)
        legacy.write_json(root/'runs'/f'{run_id}.json',bounds)
        process=subprocess.Popen([sys.executable,'-m',__spec__.name,'--execute-live','--worker',
            '--runtime-dir',str(root),'--run-id',run_id],creationflags=0x08000000 if os.name=='nt' else 0)
        legacy.write_json(root/'supervisor.json',dict(pid=os.getpid(),worker_pid=process.pid,run_id=run_id))
        forced=False
        try:code=process.wait(timeout=seconds+30)
        except (subprocess.TimeoutExpired,KeyboardInterrupt):
            (root/'STOP').touch()
            try:code=process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait();code=124;forced=True
        legacy.write_json(root/'runs'/f'{run_id}.exit.json',dict(worker_reaped=True,worker_returncode=code,
            forced_kill=forced,automatic_restart=False))
        return code


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-live',action='store_true')
    parser.add_argument('--runtime-dir',required=True,type=Path)
    parser.add_argument('--seconds',type=int,default=600)
    parser.add_argument('--max-requests',type=int,default=180)
    parser.add_argument('--validation-markets',nargs='+',help='Explicit 2–5 market connection test only; default ALL KRW')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--run-id',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not args.execute_live:parser.error('Explicit public LIVE opt-in required')
    return worker(args.runtime_dir,args.run_id) if args.worker else run(args.runtime_dir,args.seconds,args.max_requests,args.validation_markets)


if __name__=='__main__':raise SystemExit(main())
