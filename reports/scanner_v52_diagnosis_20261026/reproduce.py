"""Offline diagnosis only. Never import/launch V15's top-level program.

All source DBs are immutable/query-only. V15 functions are extracted unchanged
with AST and run against private in-memory SQLite. V4/V52 write only a verified
new temporary directory. Prices/values come from stored real candles; no raw
trades are fabricated. This is a closed-candle projection, not a tick replay.
"""
import ast
from collections import defaultdict, deque
import contextlib
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from coin_analysis import forward_scanner_v4 as core
from coin_analysis import forward_scanner_v43 as old
from coin_analysis import forward_scanner_v52 as new

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
KST=timezone(timedelta(hours=9))


def readonly(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
    return db


def fingerprint(db, table):
    rows=[tuple(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY 1,2')]
    return dict(rows=len(rows),sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,allow_nan=False).encode()).hexdigest())


def load_v15(clock):
    tree=ast.parse((ROOT/'archive/scanner_v15.py').read_text(encoding='utf8'))
    # No imports, top-level DB connect, preload, threads or infinite loop.
    names={'init_database','confirmed_preload_points','finish_minute','price_change',
           'moving_average','moving_average_signal','golden_cross_signal','ma_trend',
           'get_volume_history','volume_ratio','calculate_score','make_reason',
           'save_signal','save_price_history','register_pullback_watch',
           'prepump_strength','is_prepump_candidate','save_prepump_event',
           'evaluate_prepump','analyze','upbit_message','bithumb_message'}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    constants={}
    for n in tree.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            try:value=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            constants[n.targets[0].id]=value
    class FixedDateTime(datetime):
        @classmethod
        def now(cls,tz=None):return datetime.fromtimestamp(clock[0],tz or KST)
        @classmethod
        def strptime(cls,text,fmt):return datetime.strptime(text,fmt).replace(tzinfo=KST)
    ns=dict(constants,datetime=FixedDateTime,timezone=timezone,math=__import__('math'),json=json,
        time=SimpleNamespace(time=lambda:clock[0]),db=sqlite3.connect(':memory:'),db_lock=threading.Lock(),
        prices={e:{} for e in ('UPBIT','BITHUMB')},
        data={e:defaultdict(lambda:deque(maxlen=120)) for e in ('UPBIT','BITHUMB')},
        minute_prices={e:defaultdict(lambda:deque(maxlen=120)) for e in ('UPBIT','BITHUMB')},
        current_volume={e:defaultdict(float) for e in ('UPBIT','BITHUMB')},
        current_minute={e:None for e in ('UPBIT','BITHUMB')},last_signal={},active_signals=[],
        active_prepumps=[],prepump_last_signal={})
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'archive/scanner_v15.py:AST-functions','exec'),ns)
    with contextlib.redirect_stdout(io.StringIO()):ns['init_database']()
    return ns


class StoredClient:
    def __init__(self, data):self.data=data;self.pages=0
    def get(self,path,**params):
        assert path=='/v1/candles/minutes/1' and params['count']==200
        self.pages+=1;cursor=core.collector.parse(params['to']);market=params['market']
        rows=[r for r in self.data[market] if r[0]<cursor][-200:][::-1]
        return [dict(market=market,candle_date_time_utc=datetime.fromtimestamp(r[0],timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
            unit=1,opening_price=r[1],high_price=r[2],low_price=r[3],trade_price=r[4],candle_acc_trade_price=r[5]) for r in rows]


def same_real_input():
    source=ROOT/'data/forward_scanner_v4.db';sha=hashlib.sha256(source.read_bytes()).hexdigest()
    start=core.collector.parse('2026-10-02T00:00:00+09:00');end=start+86400
    markets=list(old.MARKETS)
    with contextlib.closing(readonly(source)) as original:
        data={m:[tuple(r) for r in original.execute('SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? AND ts>=? AND ts<? ORDER BY ts',
                    (m,start-core.WARMUP-4*3600,end+3600))] for m in markets}
        original_signals=[dict(r) for r in original.execute('SELECT signal_id,market,signal_time,range_30m FROM signals WHERE signal_time>=? AND signal_time<? ORDER BY market,signal_time',(start,end)) if r['market'] in markets]
    clock=[start];v15=load_v15(clock);indices={m:0 for m in markets};legacy_calls=0;bridge_calls=0
    with tempfile.TemporaryDirectory(prefix='chio_v52_diagnosis_') as temp:
        temp=Path(temp).resolve()
        assert temp.parent==Path(tempfile.gettempdir()).resolve() and temp.name.startswith('chio_v52_diagnosis_')
        a=old.open_runtime(temp/'old',dict(markets=markets,signal_start=start),'UPBIT')
        b=old.open_runtime(temp/'v52',dict(markets=markets,signal_start=start),'UPBIT')
        listing=new.catalog([dict(market=m) for m in markets],start)
        bridge=new.Bridge(b,'UPBIT',listing)
        ca,cb=StoredClient(data),StoredClient(data)
        try:
            with patch.object(core,'process_observations',wraps=core.process_observations) as spy:
                for t in range(start-core.WARMUP,end+1,300):
                    # Same real candle pages, cutoff and detection clock in both paths.
                    core.cycle(a,ca,now=t+5,emit=lambda _:None);legacy_calls+=1
                    for market in markets:core.fetch_market(b,cb,market,core.candles.closed_cutoff(t+5))
                    bridge.evaluate(t+5);bridge_calls+=1
                    if t<start:continue
                    # V15's own preload validator projects only the contiguous
                    # trailing closed-bar data it actually accepts. No tick input,
                    # partial-minute value, synthetic gap bars or new API calls.
                    for market in markets:
                        raw=StoredClient(data).get('/v1/candles/minutes/1',market=market,to=core.collector.iso(t),count=200)[0:120]
                        points=v15['confirmed_preload_points'](raw,market,t+5)
                        v15['minute_prices']['UPBIT'][market]=deque((r[0] for r in points),maxlen=120)
                        v15['data']['UPBIT'][market]=deque((r[1] for r in points),maxlen=120)
                        if points:v15['prices']['UPBIT'][market]=points[-1][0]
                    clock[0]=t+5
                    with contextlib.redirect_stdout(io.StringIO()):v15['analyze']()
            tables=('signals','signal_features','signal_outcomes','scanner_state','minute_candles')
            compared={table:dict(old=fingerprint(a,table),v52=fingerprint(b,table)) for table in tables}
            assert all(x['old']==x['v52'] for x in compared.values())
            actual=[dict(r) for r in b.execute('SELECT signal_id,market,signal_time,range_30m FROM signals ORDER BY market,signal_time')]
            v15rows=[dict(zip(('id','created_at','market','score','price'),r)) for r in v15['db'].execute('SELECT id,created_at,market,score,price FROM signals ORDER BY id')]
            result=dict(source=str(source),source_sha256=sha,start=start,end=end,markets=markets,
                real_candles_loaded={m:len(v) for m,v in data.items()},old_cycle_calls=legacy_calls,
                bridge_evaluate_calls=bridge_calls,observations_function_calls=spy.call_count,
                old_offline_pages=ca.pages,v52_offline_pages=cb.pages,table_comparison=compared,
                v4_v52_signals=actual,original_stored_signals_in_cohort_window=original_signals,
                v15_closed_projection_signals=v15rows,
                v15_prepump_events=v15['db'].execute('SELECT COUNT(*) FROM prepump_events').fetchone()[0],
                caveat='V15 is an unchanged AST function replay on confirmed close/value projections at common 5m checkpoints. Native live V15 checks every 10s and can use current partial value/tick price; raw ticks are not stored and not fabricated. No profitability comparison.')
        finally:a.close();b.close();v15['db'].close()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
    return result


def runtime_causal_replay():
    evidence=json.loads((ROOT/'reports/scanner_v52_20261026/live_results.json').read_text(encoding='utf8'))
    result={}
    for kind in ('full','small'):
        root=Path(evidence[kind]['root']);summary=evidence[kind]['summary'];now=summary['ended_at']
        saved=json.loads((root/'ws_markets.json').read_text(encoding='utf8'))
        result[kind]={}
        for exchange in ('UPBIT','BITHUMB'):
            original=readonly(root/(exchange.lower()+'.db'));work=sqlite3.connect(':memory:');work.row_factory=sqlite3.Row
            original.backup(work);original.close()
            listed={m:dict(eligible=s['state']!='EXCLUDED',reason=s['reason']) for m,s in saved[exchange].items()}
            bridge=new.Bridge(work,exchange,listed)
            for m,s in saved[exchange].items():bridge.markets[m].update(s)
            before=fingerprint(work,'scanner_state')
            with patch.object(core,'process_observations',wraps=core.process_observations) as called,patch.object(core,'load_research',wraps=core.load_research) as load:
                bridge.evaluate(now)
                at_end=bridge.snapshot(now)
                bridge.evaluate(now+3600)
                time_only=bridge.snapshot(now+3600)
            cfg=core.config(work);watermark=work.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0]
            result[kind][exchange]=dict(start=cfg['start'],actual_end=now,watermark=watermark,
                calls=called.call_count,research_load_calls=load.call_count,
                evaluated_at_end=at_end['evaluated'],evaluated_after_time_only_plus_1h=time_only['evaluated'],
                source_30m_complete=at_end['complete_30m'],
                scanner_state_changed=before!=fingerprint(work,'scanner_state'),
                actual_ws_candle_rows=work.execute('SELECT COUNT(*) FROM ws_candles').fetchone()[0],
                pending_jobs=work.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0])
            work.close()
    return result


def pending_job_gate():
    """Real closed candles can accumulate while one initial job holds MIN()."""
    start=core.collector.parse('2026-10-02T00:00:00+09:00');end=start+3600
    markets=list(old.MARKETS);blocked='KRW-SAND'
    with contextlib.closing(readonly(ROOT/'data/forward_scanner_v4.db')) as source:
        data={m:[tuple(r) for r in source.execute('SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? AND ts>=? AND ts<? ORDER BY ts',
              (m,start-core.WARMUP-3600,end))] for m in markets}
    with tempfile.TemporaryDirectory(prefix='chio_v52_diagnosis_') as temp:
        temp=Path(temp).resolve();assert temp.parent==Path(tempfile.gettempdir()).resolve()
        db=old.open_runtime(temp,dict(markets=markets,signal_start=start),'UPBIT')
        try:
            bridge=new.Bridge(db,'UPBIT',new.catalog([dict(market=m) for m in markets],start))
            bridge.subscribed(0,markets,start-5)
            client=StoredClient(data)
            for market in markets:
                if market!=blocked:core.fetch_market(db,client,market,start)
            # Replay admitted closed-candle records, not invented raw trade ticks.
            # No HTTP job is serviced for the blocked market during this interval.
            for t in range(start,end+1,300):
                with db:
                    for market in markets:
                        db.executemany('INSERT OR IGNORE INTO minute_candles VALUES(?,?,?,?,?,?,?)',
                            [(market,)+r for r in data[market] if start-core.WARMUP<=r[0]<t])
                bridge.flush(t+5);bridge.evaluate(t+5)
            before=dict(evaluated=bridge.snapshot(end+5)['evaluated'],
                source_rows=db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],
                signals=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0],
                watermark=db.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0],
                pending_jobs=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0])
            assert before['evaluated']==0 and before['pending_jobs']==1
            pages_before=client.pages
            core.fetch_market(db,client,blocked,end)
            bridge.flush(end+5);bridge.evaluate(end+5)
            after=dict(evaluated=bridge.snapshot(end+5)['evaluated'],
                signals=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0],
                watermark=db.execute('SELECT MIN(verified_until) FROM scanner_state').fetchone()[0],
                pending_jobs=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0],
                real_stored_recovery_pages=client.pages-pages_before)
            assert after['evaluated']==4 and after['pending_jobs']==0 and after['signals']>0
            return dict(markets=markets,held_market=blocked,real_candle_interval=[start-core.WARMUP,end],
                        before_recovery=before,after_recovery=after,
                        purpose='Closed-candle admission/verification gate experiment, not a raw-WS replay or a production metadata override.')
        finally:db.close()


def main():
    began=time.monotonic()
    with patch.object(socket,'create_connection',side_effect=AssertionError('Network forbidden in diagnosis')),\
         patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden in diagnosis')):
        result=dict(same_real_input=same_real_input(),runtime_causal_replay=runtime_causal_replay(),pending_job_gate=pending_job_gate(),
                    elapsed_seconds=time.monotonic()-began,external_api_calls=0)
    (OUT/'reproduction_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(seconds=result['elapsed_seconds'],core_signals=len(result['same_real_input']['v4_v52_signals']),
        v15_signals=len(result['same_real_input']['v15_closed_projection_signals']),
        tables_equal=all(x['old']==x['v52'] for x in result['same_real_input']['table_comparison'].values())),ensure_ascii=False))


if __name__=='__main__':main()
