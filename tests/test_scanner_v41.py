import ast
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from coin_analysis import scanner_candles as c
from coin_analysis import forward_scanner_v4 as s
from coin_analysis import forward_scanner_v4_operations as o
from coin_analysis import legacy_open_reconciliation as r
from tests.test_forward_scanner_v4 import history, START, MARKETS


def raw(ts=0,minutes=1,market='KRW-BTC'):
    return dict(market=market,unit=minutes,candle_date_time_utc=s.collector.iso(ts)[:19],
                candle_date_time_kst=s.collector.iso(ts,s.collector.KST)[:19],
                opening_price=100.,high_price=200.,low_price=100.,trade_price=200.,
                candle_acc_trade_volume=2.,candle_acc_trade_price=300.)


class CandleGuards(unittest.TestCase):
    def test_1_5_15_close_boundaries_and_settle(self):
        for minutes in (1,5,15):
            seconds=minutes*60
            self.assertEqual(c.closed_cutoff(seconds+4.999,minutes),0)
            self.assertEqual(c.closed_cutoff(seconds+5,minutes),seconds)
            with self.assertRaises(c.CandleValidationError):c.candle(raw(0,minutes), 'KRW-BTC', minutes, seconds-1)
            self.assertEqual(c.candle(raw(0,minutes),'KRW-BTC',minutes,seconds)[0],0)

    def test_utc_kst_mismatch_and_interval(self):
        self.assertEqual(c.candle(raw(),'KRW-BTC')[0],0)
        for bad,minutes in ((dict(raw(),candle_date_time_kst='1970-01-01T00:00:00'),1),(dict(raw(),unit=5),1),(raw(60,5),5)):
            with self.assertRaises(c.CandleValidationError):c.candle(bad,'KRW-BTC',minutes)
        self.assertEqual(s.collector.parse('1970-01-01T09:00:00+09:00'),0)
        self.assertEqual(c.api_to('UPBIT',0),'1970-01-01T00:00:00+00:00')
        self.assertEqual(c.api_to('BITHUMB',0),'1970-01-01T09:00:00')

    def test_native_value_not_volume_times_close(self):
        self.assertEqual(c.candle(raw(),'KRW-BTC')[-1],300.)
        self.assertNotEqual(c.candle(raw(),'KRW-BTC')[-1],400.)
        for bad in (dict(raw(),candle_acc_trade_price=402.),dict(raw(),candle_acc_trade_volume=-1),dict(raw(),candle_acc_trade_volume=math.nan)):
            with self.assertRaises(c.CandleValidationError):c.candle(bad,'KRW-BTC')
        self.assertEqual(c.candle(dict(raw(),candle_acc_trade_price=400.9),'KRW-BTC')[-1],400.9)

    def test_invalid_duplicate_future_page(self):
        for page in ({'error':{'name':400}},['not a candle'],[raw(),raw()],[raw(60)],[dict(raw(),market='KRW-OTHER')],[dict(raw(),candle_acc_trade_price=math.nan)]):
            with self.assertRaises(c.CandleValidationError):c.validate_page(page,60,'KRW-BTC')
        self.assertEqual(len(c.validate_page([raw(120),raw(0)],180,'KRW-BTC')),2)  # sparse is preserved


class RuntimeRepairs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.db'
        self.db=s.connect(self.path);s.initialize(self.db,MARKETS,START)

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def test_actual_detection_clock_prevents_false_live_after_slow_processing(self):
        with self.db:
            for market in MARKETS:self.db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',[(market,)+row for row in history(START)])
            self.db.execute('UPDATE scanner_state SET verified_until=?',(START,))
        s.process_observations(self.db,START+12,lambda _:None,detected_clock=lambda:START+301)
        self.assertEqual(s.statistics(self.db,'CATCHUP')['signals'],4)
        self.assertEqual({r[0] for r in self.db.execute('SELECT detected_at FROM signals')},{START+301})
        self.db.close();self.db=s.connect(self.path)
        s.process_observations(self.db,START+600,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],4)

    def test_rejected_data_logs_and_does_not_advance_cursor(self):
        class Bad:
            def get(self,*args,**kwargs):return [dict(raw(START-60),candle_acc_trade_price=999999)]
        sid=o.start_session(self.db,START)
        before=dict(self.db.execute("SELECT * FROM scanner_state WHERE market='KRW-BTC'").fetchone())
        with self.assertRaises(c.CandleValidationError):s.cycle(self.db,Bad(),START+5,lambda _:None,sid)
        state=dict(self.db.execute("SELECT * FROM scanner_state WHERE market='KRW-BTC'").fetchone())
        self.assertEqual(state['verified_until'],before['verified_until'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT cursor FROM collection_jobs').fetchone()[0],START)
        cycle=self.db.execute('SELECT * FROM scanner_cycles').fetchone()
        self.assertEqual(cycle['status'],'ERROR');self.assertIn('CandleValidationError',cycle['error'])

    def test_http_200_error_payload_is_fatal_and_preserves_job(self):
        client=s.collector.Client(transport=lambda *args:({'error':{'name':400}},{}),sleep=lambda _:None)
        with self.assertRaises(c.CandleValidationError):s.cycle(self.db,client,START+5,lambda _:None)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0],1)

    def test_network_retry_resume_and_duplicate_skip(self):
        seen=[]
        def transport(path,params):
            seen.append(params['to'])
            if len(seen)==1:raise urllib.error.URLError('simulated disconnect')
            cursor=s.collector.parse(params['to'])
            return [raw(t,market=params['market']) for t in range(cursor-60,cursor-12001,-60)],{}
        client=s.collector.Client(transport=transport,sleep=lambda _:None,max_requests=5)
        s.fetch_market(self.db,client,'KRW-BTC',START)
        self.assertEqual(seen[0],seen[1]);self.assertEqual(client.retries,1)
        count=self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0]
        self.db.close();self.db=s.connect(self.path)
        s.fetch_market(self.db,client,'KRW-BTC',START)
        self.assertEqual(count,self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0])

    def test_confirmed_conflict_stops_without_overwrite(self):
        # Existing job overlapping a committed source candle (e.g. retried page).
        with self.db:
            self.db.execute('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',('KRW-BTC',START-60,100,200,100,200,299))
        class Client:
            def get(self,*args,**kwargs):return [raw(START-60,market=kwargs['market']),raw(START-s.WARMUP,market=kwargs['market'])]
        with self.assertRaises(s.CandleConflictError):s.cycle(self.db,Client(),START+5,lambda _:None)
        self.assertEqual(self.db.execute("SELECT trade_value FROM minute_candles WHERE market='KRW-BTC' AND ts=?",(START-60,)).fetchone()[0],299)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM collection_pages WHERE market='KRW-BTC'").fetchone()[0],0)

    def test_late_published_candle_rechecked_without_rewriting_signal(self):
        with self.db:
            self.db.execute("UPDATE scanner_state SET verified_until=?,last_observation=? WHERE market='KRW-BTC'",(START,START))
            self.db.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)',('frozen','KRW-ETH',START,100,4,'frozen',START+12,12,'LIVE'))
            self.db.execute('INSERT INTO signal_features VALUES(?,?,?,?,?)',('frozen',START,'{"ma5":null}','{}','{}'))
        saved=[tuple(row) for row in self.db.execute('SELECT * FROM signal_features')]
        requests=[]
        class Client:
            def get(self,*args,**kwargs):
                requests.append(kwargs)
                return [raw(t) for t in (START,START-60,START-120)]
        s.fetch_market(self.db,Client(),'KRW-BTC',START+60)
        self.assertIsNotNone(self.db.execute('SELECT * FROM minute_candles WHERE market=? AND ts=?',('KRW-BTC',START-60)).fetchone())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM scanner_late_candles').fetchone()[0],2)
        self.assertEqual(saved,[tuple(row) for row in self.db.execute('SELECT * FROM signal_features')])
        self.assertEqual(self.db.execute("SELECT last_observation FROM scanner_state WHERE market='KRW-BTC'").fetchone()[0],START)
        self.db.close();self.db=s.connect(self.path)
        s.fetch_market(self.db,Client(),'KRW-BTC',START+60)
        self.assertEqual(len(requests),1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM scanner_late_candles').fetchone()[0],2)

    def test_health_and_stop_reason_preserved_after_restart(self):
        first=o.start_session(self.db,START);o.start_cycle(self.db,first,START)
        self.assertEqual(o.health(self.db,START+301)['operational_state'],'STALE')
        self.db.close();self.db=s.connect(self.path)
        second=o.start_session(self.db,START+400)
        self.assertEqual(self.db.execute('SELECT status FROM scanner_sessions WHERE session_id=?',(first,)).fetchone()[0],'INTERRUPTED')
        self.assertIsNone(self.db.execute('SELECT ended_at FROM scanner_sessions WHERE session_id=?',(first,)).fetchone()[0])
        o.end_session(self.db,second,'ERROR',reason='bounded test cause')
        self.assertEqual(o.health(self.db)['operational_state'],'STOPPED')
        self.assertIn('bounded test cause',self.db.execute("SELECT details_json FROM scanner_runtime_events WHERE kind='END'").fetchone()[0])

    def test_os_lock_rejects_second_process_without_growing_file(self):
        code='import sys; from coin_analysis.forward_scanner_v4 import exclusive\nwith exclusive(sys.argv[1]): pass'
        with s.exclusive(self.path):
            size=Path(str(self.path)+'.lock').stat().st_size
            result=subprocess.run([sys.executable,'-c',code,str(self.path)],capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0);self.assertIn('Another scanner owns this DB',result.stderr)
        with s.exclusive(self.path):pass
        self.assertEqual(Path(str(self.path)+'.lock').stat().st_size,size)

    def test_old_schema_upgrade_preserves_existing_business_tables(self):
        self.db.execute('DROP TABLE scanner_runtime_events')
        self.db.execute('DROP TABLE scanner_late_candles');self.db.commit()
        before=o.full_fingerprints(self.db)
        self.db.close();self.db=s.connect(self.path)
        after=o.full_fingerprints(self.db)
        self.assertEqual(before,{name:after[name] for name in before})
        self.assertEqual(after['scanner_runtime_events']['rows'],0)
        self.assertEqual(after['scanner_late_candles']['rows'],0)


def archive_functions():
    names={'confirmed_preload_points','load_upbit_candles','load_bithumb_candles','finish_minute','upbit_message','bithumb_message'}
    tree=ast.parse(Path('archive/scanner_v15.py').read_text(encoding='utf8'))
    ns=dict(json=json,math=math,datetime=datetime,timezone=timezone,
            prices={e:{'KRW-X':100.} for e in ('UPBIT','BITHUMB')},
            current_minute={e:0 for e in ('UPBIT','BITHUMB')},
            current_volume={e:defaultdict(float,{'KRW-X':10.}) for e in ('UPBIT','BITHUMB')},
            data={e:defaultdict(deque) for e in ('UPBIT','BITHUMB')},
            minute_prices={e:defaultdict(deque) for e in ('UPBIT','BITHUMB')})
    exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'archive_selected_only','exec'),ns)
    return ns


class ArchiveRepairs(unittest.TestCase):
    def test_new_minute_first_trade_does_not_change_previous_close_both_exchanges(self):
        ns=archive_functions()
        for exchange,callback in [('UPBIT','upbit_message'),('BITHUMB','bithumb_message')]:
            msg=dict(type='trade',code='KRW-X',trade_price=110.,trade_volume=2.,trade_timestamp=60000)
            ns[callback](None,json.dumps(msg))
            self.assertEqual(list(ns['minute_prices'][exchange]['KRW-X']),[100.])
            self.assertEqual(ns['current_volume'][exchange]['KRW-X'],220.)
            ns[callback](None,json.dumps(dict(msg,trade_timestamp=0,trade_price=999.)))
            self.assertEqual(ns['prices'][exchange]['KRW-X'],110.)
            self.assertEqual(list(ns['minute_prices'][exchange]['KRW-X']),[100.])

    def test_preload_native_value_and_closed_bars_gap_and_duplicates(self):
        ns=archive_functions();fn=ns['confirmed_preload_points']
        self.assertEqual(fn([raw(0),raw(60),raw(60),raw(120)],'KRW-BTC',125),[(200.,300.),(200.,300.)])
        self.assertEqual(fn([raw(0),raw(120)],'KRW-BTC',185),[(200.,300.)])
        with self.assertRaises(ValueError):fn([raw(0),dict(raw(0),trade_price=101.)],'KRW-BTC',65)
        with self.assertRaises(KeyError):fn([{k:v for k,v in raw().items() if k!='candle_acc_trade_price'}],'KRW-BTC',65)


class OpenReconciliation(unittest.TestCase):
    def trade(self):
        return dict(id=1,signal_id=1,status='OPEN',created_at='2026-09-01 00:00:00',entry_minute=1,
                    entry_price=100.,tp_pct=3.,sl_pct=1.5,exit_deadline_minute=45,pnl_pct=None)

    def test_stale_preserves_original_and_never_invents_exit_or_pnl(self):
        trade=self.trade();result=r.classify(trade,{},r.local_time('2026-10-24 00:00:00'))
        self.assertEqual(result['effective_status'],'STALE_OPEN')
        self.assertEqual(result['original'],trade);self.assertEqual(trade['status'],'OPEN')
        self.assertFalse(result['included_in_original_closed_statistics']);self.assertIsNone(result['verified_recovery'])
        self.assertEqual(r.classify(trade,{},r.local_time('2026-09-01 00:10:00'))['effective_status'],'OPEN')

    def test_candidate_requires_contiguous_timed_observations_and_is_not_closed(self):
        h={1:dict(price=100.,observed_at='2026-09-01 00:01:05'),2:dict(price=104.,observed_at='2026-09-01 00:02:05')}
        result=r.classify(self.trade(),h,r.local_time('2026-10-24 00:00:00'))
        self.assertEqual(result['recovery_status'],'CANDIDATE_ONLY_NOT_VERIFIED')
        self.assertEqual(result['effective_status'],'STALE_OPEN');self.assertIsNone(result['verified_recovery'])
        self.assertEqual(result,r.classify(self.trade(),h,r.local_time('2026-10-24 00:00:00')))
        h[2]['observed_at']='2026-09-01 00:10:05'
        self.assertEqual(r.classify(self.trade(),h,r.local_time('2026-10-24 00:00:00'))['recovery_status'],'INVALID_OBSERVATION_TIME')

    def test_closed_original_and_timezone_required(self):
        trade=dict(self.trade(),status='CLOSED',pnl_pct=-1.6)
        self.assertTrue(r.classify(trade,{},r.local_time('2026-10-24 00:00:00'))['included_in_original_closed_statistics'])
        self.assertEqual(r.local_time('2026-09-01 09:00:00'),datetime(2026,9,1,tzinfo=timezone.utc))
        self.assertEqual(r.integer((123).to_bytes(8,'little')),123)

    def test_separate_ledger_readonly_source_and_no_duplicate_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'legacy.db';output=Path(tmp)/'ledger.json'
            with sqlite3.connect(source) as db:
                db.executescript('''
                    CREATE TABLE signals(id,created_at,exchange,market);
                    CREATE TABLE pullback_paper_trades(id,signal_id,status,entry_minute,entry_price,
                      entry_return_from_signal,tp_pct,sl_pct,exit_minute,exit_price,exit_deadline_minute,pnl_pct);
                    CREATE TABLE signal_price_history(signal_id,minute,price,observed_at);
                ''')
                db.execute("INSERT INTO signals VALUES(1,'2026-09-01 00:00:00','UPBIT','KRW-X')")
                db.executemany('INSERT INTO pullback_paper_trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',[
                    (1,1,'OPEN',1,100.,-1.,3.,1.5,None,None,45,None),
                    (2,1,'CLOSED',1,100.,-1.,3.,1.5,2,98.5,45,-1.6)])
            db.close()
            before=r.digest(source)
            report=r.reconcile(source,r.local_time('2026-10-24 00:00:00'),output)
            self.assertEqual(report['counts'],{'STALE_OPEN':1,'CLOSED':1})
            self.assertEqual(report['original_closed_statistics'],{'n':1,'mean_pct':-1.6})
            self.assertEqual(before,r.digest(source))
            with self.assertRaises(FileExistsError):r.reconcile(source,r.local_time('2026-10-24 00:00:00'),output)


if __name__=='__main__':unittest.main()
