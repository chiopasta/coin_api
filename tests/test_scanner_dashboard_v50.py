"""Selected dashboard boundary tests. Only isolated fixtures and loopback HTTP."""
from contextlib import ExitStack, redirect_stdout, closing
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

from coin_analysis import scanner_dashboard_v50 as d
from coin_analysis import scanner_desktop_v50 as desktop


class DataView(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.archive=self.base/'archive.db';self.runtime=self.base/'runtime'
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(d,'ARCHIVE',self.archive))
        self.stack.enter_context(patch.object(d.control.observer,'RUNTIME_ROOT',self.runtime))
        self.state=dict(status='STOPPED',phase='TERMINAL',clock='UNKNOWN (last PASS is stale)',markets=51,
                        manager={'pid':99,'birth':123},reason=None)
        self.stack.enter_context(patch.object(d.control,'snapshot',side_effect=lambda:self.state))
        self.stack.enter_context(patch.object(d.control,'current',return_value=None))
        self.make_db(self.archive)

    def make_db(self,path,live=False):
        path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript('''CREATE TABLE signals(signal_id TEXT PRIMARY KEY,market TEXT,signal_time INTEGER,
                signal_price REAL,detected_at INTEGER,source TEXT);
                CREATE TABLE minute_candles(market TEXT,ts INTEGER,open REAL,high REAL,low REAL,close REAL,PRIMARY KEY(market,ts));
                CREATE TABLE scanner_config(id INTEGER,payload TEXT);
                CREATE TABLE signal_outcomes(signal_id TEXT,label TEXT,status TEXT,max_return REAL,
                observed_minutes INTEGER,expected_minutes INTEGER);''')
            db.execute('INSERT INTO scanner_config VALUES(1,?)',(json.dumps(dict(policy=dict(range_threshold=4))),))
            db.execute("INSERT INTO signals VALUES('saved','KRW-ETH',6000,100,6012,'LIVE')")
            db.executemany("INSERT INTO minute_candles VALUES('KRW-ETH',?,100,110,90,105)",[(t,) for t in range(4200,9600,60)])
            db.execute("INSERT INTO signal_outcomes VALUES('saved','L1','FAILURE',10,30,30)")
            if live:
                d.control.observer.v42.observation_schema(db)

    def detail(self): return d.View().detail('archive','saved')

    def test_archive_metrics_are_exact_stored_bars_and_readonly(self):
        before=self.archive.read_bytes();v=d.View();s=v.snapshot();r=v.detail('archive','saved')
        self.assertEqual(s['total'],1);self.assertEqual(s['today_live_signals'],0)
        self.assertIsNone(r['score']);self.assertEqual(r['scope'],'ARCHIVE')
        self.assertEqual(r['outcomes'][0]['status'],'FAILURE')
        for h in r['horizons']:
            self.assertEqual(h['status'],'COMPLETE');self.assertAlmostEqual(h['return_pct'],5)
            self.assertAlmostEqual(h['mfe_pct'],10);self.assertAlmostEqual(h['mae_pct'],-10)
        self.assertEqual(len(r['candles']),90);self.assertEqual(self.archive.read_bytes(),before)
        self.assertFalse(Path(str(self.archive)+'-shm').exists())
        with d.readonly(self.archive,True) as db:
            with self.assertRaises(sqlite3.OperationalError):db.execute('DELETE FROM signals')

    def test_missing_candle_never_fills_or_completes_horizon(self):
        with closing(sqlite3.connect(self.archive)) as db, db:db.execute('DELETE FROM minute_candles WHERE ts=6060')
        r=self.detail()
        self.assertEqual(len(r['candles']),89)
        self.assertTrue(all(h['status']=='NO_DATA' and h['return_pct'] is None and h['mfe_pct'] is None for h in r['horizons']))

    def test_future_candles_never_complete_or_enter_chart(self):
        with patch.object(d.time,'time',return_value=6061):r=self.detail()
        self.assertTrue(all(h['status']=='PENDING' for h in r['horizons']))
        self.assertTrue(all(c['ts']+60<=6061 for c in r['candles']))

    def test_archive_nonempty_wal_is_blocked_not_ignored(self):
        Path(str(self.archive)+'-wal').write_bytes(b'not safe to ignore')
        s=d.View().snapshot();self.assertEqual(s['total'],0);self.assertTrue(s['errors'])
        with self.assertRaises(sqlite3.DatabaseError):self.detail()

    def test_saved_live_pending_metrics_are_not_recomputed(self):
        root=self.runtime/'episode_fixture';path=root/'upbit.db';self.make_db(path,True)
        (root/'config.json').write_text('{}')
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("INSERT INTO live_horizons VALUES('saved',60,'PENDING',60,'INCOMPLETE_FUTURE',NULL,NULL,NULL,9999)")
        r=d.View().detail('episode_fixture_upbit','saved')
        self.assertEqual(r['horizons'][-1]['status'],'PENDING')
        self.assertIsNone(r['horizons'][-1]['return_pct'])
        self.assertEqual(r['horizons'][0]['status'],'NO_DATA')

    def test_live_wal_commits_are_visible_after_cache_expiry_without_db_writes(self):
        root=self.runtime/'episode_fixture';path=root/'upbit.db';self.make_db(path,True)
        (root/'config.json').write_text('{}');v=d.View();self.assertEqual(v.snapshot()['total'],2)
        with closing(sqlite3.connect(path)) as writer, writer:
            writer.execute('PRAGMA journal_mode=WAL');writer.execute("INSERT INTO signals VALUES('new_fixture','KRW-ETH',10000,100,10012,'LIVE')");writer.commit()
            v.cached_at-=5;s=v.snapshot()
            self.assertEqual(s['total'],3);self.assertIn('new_fixture',[r['signal_id'] for r in s['signals']])
            self.assertEqual(writer.execute('SELECT COUNT(*) FROM signals').fetchone()[0],2)

    def test_public_status_distinguishes_web_and_live_no_process_or_path_leak(self):
        s=d.View().snapshot();encoded=json.dumps(s)
        self.assertEqual(s['web'],'RUNNING');self.assertEqual(s['scanner']['status'],'STOPPED')
        self.assertEqual(s['scanner']['markets'],0);self.assertFalse(s['scanner']['live_collecting'])
        self.assertNotIn('manager',encoded);self.assertNotIn('birth',encoded);self.assertNotIn(str(self.base),encoded)
        self.assertEqual(s['scanner']['connections']['UPBIT']['status'],'DISCONNECTED')

    def test_blocked_and_precheck_do_not_claim_active_markets(self):
        for status,phase in [('BLOCKED','TERMINAL'),('RUNNING','PRECHECK')]:
            self.state.update(status=status,phase=phase,reason='CLOCK_BAD')
            s=d.View().snapshot()['scanner'];self.assertEqual(s['markets'],0)
            self.assertFalse(s['live_collecting']);self.assertEqual(s['reason'],'CLOCK_VERIFICATION_FAILED')

    def test_unknown_file_or_sql_identifier_cannot_enter_query(self):
        v=d.View()
        for key,sid in [('../../archive','saved'),('archive',"saved' OR 1=1"),('archive','missing')]:
            with self.assertRaises(LookupError):v.detail(key,sid)

    def test_empty_data_has_no_invented_values(self):
        self.archive.unlink();s=d.View().snapshot()
        self.assertEqual(s['signals'],[]);self.assertEqual(s['total'],0)
        self.assertEqual(s['today_live_signals'],0)

    def test_archive_filter_can_access_archive_even_after_many_newer_signals(self):
        root=self.runtime/'episode_fixture';path=root/'upbit.db';self.make_db(path,True)
        (root/'config.json').write_text('{}')
        with closing(sqlite3.connect(path)) as db, db:
            db.executemany("INSERT INTO signals VALUES(?,'KRW-ETH',12000,100,12012,'LIVE')",[(f'fixture_{i}',) for i in range(201)])
        v=d.View();self.assertFalse(any(r['scope']=='ARCHIVE' for r in v.snapshot()['signals']))
        archive=v.snapshot('ARCHIVE');self.assertEqual(len(archive['signals']),1)
        self.assertEqual(archive['signals'][0]['scope'],'ARCHIVE')
        self.assertEqual(v.snapshot('CURRENT_LIVE')['signals'],[])
        with self.assertRaises(LookupError):v.snapshot('../../')

    def test_connections_depend_on_latest_http_and_freshness(self):
        root=self.base/'ledger';root.mkdir()
        with closing(sqlite3.connect(root/'control.db')) as db, db:
            db.execute('CREATE TABLE http_attempts(seq INTEGER,exchange TEXT,status TEXT,ended_at REAL)')
            db.execute("INSERT INTO http_attempts VALUES(1,'UPBIT','200',?)",(time.time(),))
            db.execute("INSERT INTO http_attempts VALUES(2,'BITHUMB','503',?)",(time.time(),))
        s=d.View.connections(root,True)
        self.assertEqual(s['UPBIT']['status'],'CONNECTED');self.assertEqual(s['BITHUMB']['status'],'ERROR')
        with patch.object(d.time,'time',return_value=time.time()+151):
            self.assertEqual(d.View.connections(root,True)['UPBIT']['status'],'STALE')
        self.assertEqual(d.View.connections(root,False)['UPBIT']['status'],'DISCONNECTED')


class HTTPBoundary(unittest.TestCase):
    def setUp(self):
        self.view=Mock();self.view.snapshot.return_value=dict(web='RUNNING',signals=[])
        self.view.detail.side_effect=LookupError()
        self.server=d.Server(('127.0.0.1',0),view=self.view)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs=dict(poll_interval=.05));self.thread.start()
        self.addCleanup(self.close)

    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(3)

    def request(self,path='/',method='GET',headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            conn.request(method,path,headers=headers or {});response=conn.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:conn.close()

    def test_real_loopback_static_api_headers_and_no_writes(self):
        for path in ('/','/app.js','/style.css','/api/snapshot'):
            status,headers,body=self.request(path);self.assertEqual(status,200)
            self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
            self.assertNotIn('Access-Control-Allow-Origin',headers)
        self.assertEqual(self.request('/api/snapshot','POST')[0],405)
        self.assertEqual(self.request('/api/signal?dataset=../../secret&id=no')[0],404)
        self.assertEqual(self.request('/../scripts/coin_api_entry.py')[0],404)
        self.assertEqual(self.request('/api/snapshot',headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('/api/snapshot',headers={'Origin':'https://evil.example'})[0],403)

    def test_port_collision_never_replaces_listener_and_public_bind_rejected(self):
        with self.assertRaises(OSError):d.Server(self.server.server_address)
        self.assertEqual(self.request('/api/snapshot')[0],200)
        with self.assertRaises(ValueError):d.Server(('0.0.0.0',0))

    def test_api_failure_returns_explicit_message_without_internal_secret(self):
        self.view.snapshot.side_effect=RuntimeError('SECRET_KEY_SHOULD_NOT_LEAK')
        status,_,body=self.request('/api/snapshot');self.assertEqual(status,503)
        self.assertNotIn(b'SECRET',body)


class Desktop(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.stack=ExitStack();self.addCleanup(self.stack.close)
        for obj,name,value in [(desktop,'WEB',self.base/'web'),(desktop.control,'CONTROL',self.base/'console'),
                               (desktop.control.observer,'RUNTIME_ROOT',self.base/'runtime'),
                               (desktop.control.observer.v42,'RUNTIME_ROOT',self.base/'locks')]:
            self.stack.enter_context(patch.object(obj,name,value))
        self.output=io.StringIO();self.stack.enter_context(redirect_stdout(self.output))

    def test_bad_clock_still_opens_web_without_dataset_or_observer(self):
        blocked=dict(status='BLOCKED',reason='CLOCK_TEST_FAILURE',at=time.time(),completed_at=time.time())
        def start_existing(_):
            desktop.control.start(30,26)
            child=Mock();child.pid=os.getpid();child.poll.return_value=2;return child
        with patch.object(desktop,'ensure_web') as web,patch.object(desktop,'spawn',side_effect=start_existing) as spawn,\
             patch.object(desktop.control.observer.clock_guard,'verify_clock',return_value=blocked),\
             patch.object(desktop.control.subprocess,'Popen') as worker,patch.object(desktop.webbrowser,'open',return_value=True) as browser:
            self.assertEqual(desktop.start(30,26),2)
            web.assert_called_once();browser.assert_called_once_with(d.URL,new=2);worker.assert_not_called()
            self.assertEqual(spawn.call_args.args[0][0],'_scanner')
        self.assertFalse(desktop.control.observer.RUNTIME_ROOT.exists())

    def test_dashboard_only_never_starts_scanner_or_ntp(self):
        with patch.object(desktop,'ensure_web'),patch.object(desktop,'spawn') as child,\
             patch.object(desktop.control.observer.clock_guard,'verify_clock') as clock:
            self.assertEqual(desktop.start(30,26,True,True),0);child.assert_not_called();clock.assert_not_called()

    def test_existing_scanner_is_reused_no_duplicate_process(self):
        old=dict(manager=desktop.control.identity(os.getpid()),child=None)
        with patch.object(desktop.control,'current',return_value=old),patch.object(desktop.control,'snapshot',return_value=dict(status='RUNNING')),\
             patch.object(desktop,'ensure_web'),patch.object(desktop,'spawn') as child:
            self.assertEqual(desktop.start(30,26,no_browser=True),0);child.assert_not_called()

    def test_port_failure_never_starts_scanner(self):
        with patch.object(desktop,'ensure_web',side_effect=RuntimeError('WEB_PORT_OR_START_FAILURE')),patch.object(desktop,'spawn') as child:
            with self.assertRaisesRegex(RuntimeError,'WEB_PORT'):desktop.start(30,26)
            child.assert_not_called()

    def test_stop_uses_scoped_event_and_waits_for_identity_exit(self):
        desktop.WEB.mkdir();token='f'*32
        state=dict(status='RUNNING',token=token,process=dict(pid=10,birth=30))
        with patch.object(desktop,'web_state',return_value=state),patch.object(desktop.control,'alive',side_effect=[True,True,False,False,False,False]):
            self.assertEqual(desktop.stop_web(1),0)
        self.assertTrue(desktop.stop_path(token).exists())

    def test_recycled_pid_or_bad_token_never_receives_stop(self):
        desktop.WEB.mkdir();state=dict(status='STOPPED',token='f'*32,process=dict(pid=10,birth=30))
        with patch.object(desktop,'web_state',return_value=state),patch.object(desktop.control,'alive',return_value=False):
            self.assertEqual(desktop.stop_web(0),0)
        self.assertFalse(desktop.stop_path('f'*32).exists())
        with self.assertRaises(ValueError):desktop.stop_path('../foreign')

    def test_no_cap_override_and_check_remains_completely_offline(self):
        with patch.object(desktop,'spawn') as child,patch.object(desktop,'ensure_web') as web:
            with self.assertRaises(ValueError):desktop.start(86401,16000)
            self.assertEqual(desktop.main(['start','--check']),0)
            child.assert_not_called();web.assert_not_called()

    def test_windows_brief_reader_collision_retries_and_atomically_replaces(self):
        path=self.base/'state.json'
        desktop.control.observer.write_json(path,dict(version=1))
        errors=[]
        def writer():
            try:desktop.control.write_metadata(path,dict(version=2))
            except Exception as exc:errors.append(exc)
        with path.open('r',encoding='utf8') as reader:
            thread=threading.Thread(target=writer);thread.start()
            time.sleep(.05)
            self.assertTrue(thread.is_alive());self.assertEqual(json.load(reader),dict(version=1))
        thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(desktop.control.read_json(path),dict(version=2))

    def test_persistent_metadata_error_is_still_bounded_and_fail_closed(self):
        error=PermissionError('persistent denied');error.winerror=5;began=time.monotonic()
        with patch.object(desktop.control.observer,'write_json',side_effect=error):
            with self.assertRaises(PermissionError):desktop.control.write_metadata(self.base/'state.json',{})
        self.assertLess(time.monotonic()-began,1.)


if __name__=='__main__': unittest.main()
