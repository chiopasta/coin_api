"""Lifecycle/telemetry wrapper executing the unchanged archive V15 file.

No detection or tracking algorithm lives here. Stop is delivered only at a safe
sleep/HTTP boundary, as KeyboardInterrupt handled by V15's existing loop.
"""
import argparse
import functools
import json
import math
import os
from pathlib import Path
import runpy
import sys
import threading
import time
from types import SimpleNamespace

from . import scanner_control_v410 as utilities


def execute(script, root, seconds, max_requests, configure=None):
    root=Path(root);script=Path(script).resolve()
    stop=threading.Event();finished=threading.Event();ns={};lock=threading.Lock()
    began=time.monotonic();stats=dict(http_requests=0,last_analyze=None,analyze_calls=0,scanned_pairs=None,
        connections={e:dict(received={},subscription_sent=None,last_received=None) for e in ('UPBIT','BITHUMB')})
    reason=['STOP_REQUESTED'];installed=[False]

    def check():
        if (root/'STOP_REQUESTED').exists():stop.set()
        if time.monotonic()-began>=seconds:reason[0]='TIME_LIMIT';stop.set()
        if stop.is_set():raise KeyboardInterrupt

    def sleep(value):
        until=time.monotonic()+value
        while time.monotonic()<until:
            check();stop.wait(min(.2,max(0,until-time.monotonic())))
        check()

    def publish(terminal=False,error=None):
        with lock:
            exchanges={}
            listed_all=set();received_all=set()
            for exchange,v in stats['connections'].items():
                listed=ns.get(exchange.lower()+'_markets')
                if listed is not None:listed_all.update(listed)
                received_all.update(v['received'])
                active=sum(0<=time.time()-at<=60 for at in v['received'].values())
                last=v['last_received']
                exchanges[exchange]=dict(listed=len(listed) if listed is not None else None,
                    subscription_sent=v['subscription_sent'],received=len(v['received']),active=active,
                    last_received=last,status='CONNECTED' if not terminal and last and 0<=time.time()-last<=60
                    else 'STALE' if last and not terminal else 'DISCONNECTED' if terminal else 'UNKNOWN')
            status=dict(engine='V15',phase='TERMINAL' if terminal else 'OBSERVING' if stats['last_analyze'] else 'STARTING',
                status='BLOCKED' if error else 'STOPPED' if terminal else 'RUNNING',heartbeat=time.time(),
                started_at=started,elapsed_monotonic_seconds=time.monotonic()-began,
                http_requests=stats['http_requests'],analyze_calls=stats['analyze_calls'],
                last_analyze=stats['last_analyze'],exchanges=exchanges,
                listed_unique=len(listed_all) if any(ns.get(e.lower()+'_markets') is not None for e in exchanges) else None,
                received_unique=len(received_all),
                scanned_pairs=stats['scanned_pairs'],
                reason=error or (reason[0] if terminal else None),db_saved='CLOSED' if terminal and not error else 'WRITER_ACTIVE')
        utilities.write_metadata(root/'heartbeat.json',status)

    def install(g):
        nonlocal ns
        ns=g # Original namespace, including variables initialized later.
        g['time']=SimpleNamespace(**{k:getattr(time,k) for k in dir(time) if not k.startswith('_')})
        g['time'].sleep=sleep
        original_http=g['http_get']
        @functools.wraps(original_http)
        def http(url):
            check()
            with lock:
                if stats['http_requests']>=max_requests:
                    reason[0]='HTTP_LIMIT';stop.set();raise KeyboardInterrupt
                stats['http_requests']+=1
            return original_http(url)
        g['http_get']=http
        original_analyze=g['analyze']
        original_ratio=g['volume_ratio'];evaluated=set();analyzing=[False]
        @functools.wraps(original_ratio)
        def ratio(exchange,market,period):
            if analyzing[0] and threading.current_thread() is threading.main_thread():evaluated.add((exchange,market))
            return original_ratio(exchange,market,period)
        g['volume_ratio']=ratio
        @functools.wraps(original_analyze)
        def analyze():
            evaluated.clear();analyzing[0]=True
            try:result=original_analyze()
            finally:analyzing[0]=False
            with lock:
                stats['analyze_calls']+=1;stats['last_analyze']=time.time();stats['scanned_pairs']=len(evaluated)
            return result
        g['analyze']=analyze
        for exchange,prefix in [('UPBIT','upbit'),('BITHUMB','bithumb')]:
            original_open=g[prefix+'_open'];original_message=g[prefix+'_message']
            def opened(ws,original=original_open,e=exchange):
                result=original(ws)
                with lock:stats['connections'][e]['subscription_sent']=len(g[e.lower()+'_markets'])
                return result
            def message(ws,payload,original=original_message,e=exchange):
                result=original(ws,payload)
                try:
                    item=json.loads(payload);market=item.get('code');price=item.get('trade_price')
                    ts=item.get('trade_timestamp');volume=item.get('trade_volume')
                    valid=(item.get('type')=='trade' and isinstance(market,str) and
                        all(isinstance(v,(int,float)) and math.isfinite(v) for v in (price,ts,volume)) and
                        price>0 and volume>=0 and 0<=time.time()-ts/1000<=60 and
                        g['prices'][e].get(market)==price and g['current_minute'][e]==ts//60000)
                    if valid:
                        with lock:
                            stats['connections'][e]['received'][market]=time.time()
                            stats['connections'][e]['last_received']=time.time()
                except (ValueError,TypeError,KeyError):pass
                return result
            g[prefix+'_open']=opened;g[prefix+'_message']=message
        if configure:configure(g) # Only used by offline test harnesses, not a web option.

    def profile(frame,event,arg):
        if event=='call' and frame.f_code.co_filename==str(script) and frame.f_code.co_name=='init_database':
            sys.setprofile(None);install(frame.f_globals);installed[0]=True

    def heartbeat():
        while not finished.wait(1):
            try:publish()
            except Exception:stop.set();reason[0]='HEARTBEAT_WRITE_FAILED'

    started=time.time();worker=threading.Thread(target=heartbeat,name='v15-heartbeat',daemon=True)
    error=None;oldcwd=Path.cwd()
    try:
        with utilities.observer.scanner.exclusive(root.parent.parent/'writer'):
            os.chdir(script.parent)
            sys.setprofile(profile);worker.start()
            try:runpy.run_path(str(script),run_name='__main__')
            except KeyboardInterrupt:pass
            if not installed[0]:raise RuntimeError('V15_ENTRY_CONTRACT_CHANGED')
    except BaseException as exc:
        error=type(exc).__name__
    finally:
        sys.setprofile(None);finished.set()
        if worker.is_alive():worker.join(3)
        db=ns.get('db')
        if db is not None:
            try:
                if db.in_transaction:db.rollback()
                db.close()
            except Exception:error='DB_CLOSE_FAILED'
        os.chdir(oldcwd);publish(True,error)
    return 2 if error else 0


def main():
    from .v15_control import ROOT, SCRIPT, state_root
    p=argparse.ArgumentParser();p.add_argument('--launch',required=True)
    p.add_argument('--seconds',type=int,required=True);p.add_argument('--max-requests',type=int,required=True)
    a=p.parse_args();root=state_root(a.launch)
    if not (root/'authorized.json').is_file():raise ValueError('Unowned launch')
    if not 30<=a.seconds<=86400 or not 26<=a.max_requests<=16000:raise ValueError('Invalid budget')
    return execute(SCRIPT,root,a.seconds,a.max_requests)


if __name__=='__main__':raise SystemExit(main())
