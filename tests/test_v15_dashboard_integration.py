import ast
from contextlib import closing,ExitStack
from datetime import datetime,timedelta,timezone
import hashlib
import http.client
import json
from pathlib import Path
import runpy
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch

from coin_analysis import v15_control as c,v15_dashboard as v,v15_runtime as runtime
from coin_analysis import scanner_dashboard_v50 as web

SCRIPT=Path(__file__).resolve().parents[1]/'archive/scanner_v15.py'


def init_db(path):
    tree=ast.parse(SCRIPT.read_text(encoding='utf-8-sig'))
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='init_database')
    with closing(sqlite3.connect(path)) as db:
        ns=dict(db=db,db_lock=threading.Lock())
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(SCRIPT),'exec'),ns)
        ns['init_database']()


def fixture_config(g):
    """Same deterministic HTTP/trade inputs to direct and wrapped ORIGINAL V15."""
    now=int(time.time())
    rows=[dict(market='KRW-TEST',candle_date_time_utc=datetime.fromtimestamp(now-now%60-(i+1)*60,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'),
               trade_price=100.,candle_acc_trade_price=1000.) for i in range(120)]
    def http(url):return [dict(market='KRW-TEST')] if '/market/all' in url else rows
    g['http_get']=http
    ready=[threading.Event(),threading.Event()]
    for index,prefix in enumerate(('upbit','bithumb')):
        def run(i=index,p=prefix):
            g[p+'_open'](Mock(send=lambda _:None))
            g[p+'_message'](None,json.dumps(dict(type='trade',code='KRW-TEST',trade_price=101.,trade_volume=1.,trade_timestamp=now*1000)))
            ready[i].set()
        g['run_'+prefix]=run
    calls=[0]
    def sleep(seconds):
        if seconds==g['CHECK_INTERVAL']:
            calls[0]+=1
            if calls[0]>1:raise KeyboardInterrupt
            assert all(e.wait(2) for e in ready)
        else:time.sleep(.001)
    g['time']=Mock(wraps=g['time']);g['time'].sleep=sleep


class RuntimeEquivalence(unittest.TestCase):
    def test_direct_original_and_wrapped_original_same_inputs_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);states=[];before=SCRIPT.read_bytes();old=Path.cwd()
            import os
            for wrapped in (False,True):
                folder=base/str(wrapped);folder.mkdir();script=folder/'scanner_v15.py';script.write_bytes(before)
                root=base/'managed'/'launches'/str(wrapped);root.mkdir(parents=True)
                if wrapped:
                    self.assertEqual(runtime.execute(script,root,30,26,fixture_config),0)
                    heartbeat=json.loads((root/'heartbeat.json').read_text())
                    self.assertEqual(heartbeat['db_saved'],'CLOSED')
                    self.assertEqual(heartbeat['analyze_calls'],1)
                    self.assertEqual(heartbeat['exchanges']['UPBIT']['received'],1)
                else:
                    globals_seen={}
                    def profile(frame,event,arg):
                        if event=='call' and frame.f_code.co_filename==str(script) and frame.f_code.co_name=='init_database':
                            sys.setprofile(None);fixture_config(frame.f_globals);globals_seen.update(frame.f_globals)
                    try:
                        os.chdir(folder);sys.setprofile(profile);runpy.run_path(str(script),run_name='__main__')
                    finally:
                        sys.setprofile(None);globals_seen['db'].close();os.chdir(old)
                with closing(sqlite3.connect(folder/'crypto_scanner.db')) as db:
                    tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                    states.append({t:list(db.execute(f'SELECT * FROM "{t}"')) for t in tables})
            self.assertEqual(states[0],states[1]);self.assertEqual(SCRIPT.read_bytes(),before)


class ReadonlyView(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'crypto.db';init_db(self.path)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(v,'catalog',return_value={'V15_CURRENT':self.path}))
        self.stack.enter_context(patch.object(c,'DATABASE',self.path))
        self.stack.enter_context(patch.object(c,'snapshot',return_value=dict(engine='V15',status='STOPPED',phase='TERMINAL')))
        self.when=datetime.now().replace(microsecond=0)-timedelta(hours=2)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("INSERT INTO signals(id,created_at,exchange,market,score,price,return_30m,max_profit_30m,max_drawdown_30m) VALUES(1,?,'UPBIT','KRW-TEST',60,100,3,4,-1)",(self.when.strftime('%Y-%m-%d %H:%M:%S'),))
            for n in range(31):
                db.execute('INSERT INTO signal_price_history VALUES(?,?,?,?,?)',(1,n,(self.when+timedelta(minutes=n)).strftime('%Y-%m-%d %H:%M:%S'),100+n/10,n/10))
            db.commit()

    def test_existing_analyzer_called_without_optimization_source_unchanged(self):
        before=self.path.read_bytes();view=v.View();module=v.analyzer()
        with patch.object(v,'analyzer',return_value=module),patch.object(module,'basic_stats',wraps=module.basic_stats) as stats,\
             patch.object(module,'grid_validation',side_effect=AssertionError('optimization forbidden')):
            result=view.report();self.assertTrue(stats.called)
        self.assertEqual(result['summary']['return_30m']['n'],1)
        self.assertEqual(result['summary']['return_30m']['value'],3)
        self.assertEqual(result['summary']['mfe_30m']['value'],4)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(view.detail('V15_CURRENT','s1')['score'],60)

    def test_missing_future_and_delayed_samples_excluded_without_overwriting_saved_values(self):
        for sql in ['DELETE FROM signal_price_history WHERE minute=10',
                    "UPDATE signal_price_history SET observed_at='2099-01-01 00:00:00' WHERE minute=30"]:
            with closing(sqlite3.connect(self.path)) as db:db.execute(sql);db.commit()
            result=v.View().report();self.assertEqual(result['summary']['return_30m']['n'],0)
            h=next(h for h in result['signals'][0]['horizons'] if h['minutes']==30)
            self.assertEqual(h['saved_values']['return_pct'],3)
            self.assertIsNone(h['return_pct'])

    def test_analyzer_missing_fails_explicitly_no_fallback(self):
        with patch.object(v,'ANALYZER',self.root/'missing.py'):
            result=v.View().report();self.assertTrue(result['errors']);self.assertEqual(result['summary']['total'],0)

    def test_default_web_has_v15_pages_and_security_without_engine_start(self):
        server=web.Server(('127.0.0.1',0),seconds=30,max_requests=26)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            for path in ('/','/analysis','/api/snapshot','/api/analysis','/api/signal?dataset=V15_CURRENT&id=s1'):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=4)
                conn.request('GET',path);response=conn.getresponse();body=response.read();conn.close()
                self.assertEqual(response.status,200,(path,body))
                self.assertIn("frame-ancestors 'none'",response.getheader('Content-Security-Policy'))
            self.assertEqual(server.engine,'V15');self.assertIs(server.operations.lifecycle,c)
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            conn.request('POST','/api/control/start','{}',{'Content-Type':'application/json','Origin':'https://evil.example'})
            response=conn.getresponse();response.read();self.assertEqual(response.status,403);conn.close()
        finally:server.shutdown();server.operations.close();server.server_close();thread.join()


class Ownership(unittest.TestCase):
    def test_stale_inventory_of_own_exited_child_is_not_external(self):
        identity=dict(pid=123,birth=456)
        with tempfile.TemporaryDirectory() as temp,patch.object(c,'FOLDER',Path(temp)),\
             patch.object(c,'current',return_value=dict(launch_id='a'*32,child=identity)),\
             patch.object(c,'inventory',return_value=[identity]),patch.object(c,'alive',return_value=False):
            self.assertEqual(c.stop()['status'],'STOPPED')

    def test_external_v15_blocks_start_and_stop_sends_no_signal(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(c,'FOLDER',Path(temp)),\
             patch.object(c,'current',return_value=None),patch.object(c,'inventory',return_value=[dict(pid=123,birth=456)]),\
             patch.object(c.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError,'DUPLICATE'):c.start(30,26)
            self.assertEqual(c.stop()['status'],'EXTERNAL_RUNNING');spawn.assert_not_called()

    def test_invalid_launch_and_missing_db_never_create_database(self):
        with self.assertRaises(ValueError):c.state_root('../../secret')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'missing.db'
            with self.assertRaisesRegex(RuntimeError,'MISSING'):c.preflight_database(path)
            self.assertFalse(path.exists())


if __name__=='__main__':unittest.main()
