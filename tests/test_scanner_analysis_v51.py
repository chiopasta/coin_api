"""Offline evaluation/restart and authenticated loopback control regressions."""
from contextlib import closing
from contextlib import ExitStack
import http.client
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from coin_analysis import scanner_analysis_v51 as a
from coin_analysis import scanner_dashboard_v50 as d
from coin_analysis import scanner_desktop_v50 as desktop
from tests import test_scanner_dashboard_v50 as fixtures


class Analysis(unittest.TestCase):
    make_db = fixtures.DataView.make_db
    setUp = fixtures.DataView.setUp

    def service(self):
        return a.Analysis(self.base / 'analysis.db')

    def verified(self):
        with closing(sqlite3.connect(self.archive)) as db, db:
            db.execute('CREATE TABLE scanner_state(market TEXT,verified_until INTEGER)')
            db.execute("INSERT INTO scanner_state VALUES('KRW-ETH',9600)")

    def test_engine_is_reused_source_bytes_unchanged_and_cache_saved(self):
        self.verified();before=self.archive.read_bytes();s=self.service()
        with patch.object(d.control.observer.v42,'record_metrics',wraps=d.control.observer.v42.record_metrics) as engine:
            s.refresh();engine.assert_called_once()
        r=s.report();self.assertEqual(r['summary']['total'],1)
        self.assertAlmostEqual(r['summary']['return_30m']['value'],5)
        self.assertAlmostEqual(r['summary']['rise_30m']['value'],100)
        self.assertEqual(self.archive.read_bytes(),before)
        with closing(sqlite3.connect(s.path)) as cache:
            self.assertEqual(cache.execute('SELECT COUNT(*) FROM evaluations').fetchone()[0],1)

    def test_gap_changes_denominators_without_zero_substitution(self):
        self.verified()
        with closing(sqlite3.connect(self.archive)) as db, db:
            db.execute('DELETE FROM minute_candles WHERE ts=6900')
        s=self.service();s.refresh();r=s.report()['summary']
        self.assertEqual([m['n'] for m in r['curve']],[1,1,0,0])
        self.assertIsNone(r['return_30m']['value']);self.assertIsNone(r['mfe_30m']['value'])
        self.assertEqual(s.rows[0]['horizons'][2]['status'],'INSUFFICIENT_DATA')

    def test_restart_and_new_stored_bars_finish_pending_without_source_writes(self):
        self.verified();s=self.service()
        with closing(sqlite3.connect(self.archive)) as db, db:db.execute('DELETE FROM minute_candles WHERE ts=6900')
        with patch.object(a.time,'time',return_value=6061):s.refresh()
        self.assertTrue(all(h['status']=='PENDING' for h in s.rows[0]['horizons']))
        with closing(sqlite3.connect(self.archive)) as db, db:
            db.execute("INSERT INTO minute_candles VALUES('KRW-ETH',6900,100,110,90,105)")
        restored=self.service();restored.refresh()
        self.assertEqual(restored.report()['summary']['return_30m']['n'],1)
        self.assertTrue(all(h['status']=='COMPLETE' for h in restored.rows[0]['horizons']))

    def test_due_pending_live_uses_existing_engine_but_frozen_complete_is_preserved(self):
        self.archive.unlink();root=self.runtime/'episode_fixture';path=root/'upbit.db';self.make_db(path,True)
        (root/'config.json').write_text('{}')
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE scanner_state(market TEXT,verified_until INTEGER)')
            db.execute("INSERT INTO scanner_state VALUES('KRW-ETH',9600)")
            db.execute("INSERT INTO live_horizons VALUES('saved',5,'COMPLETE',5,'FULL_FUTURE',7,11,-9,9999)")
            db.execute("INSERT INTO live_horizons VALUES('saved',30,'PENDING',2,'INCOMPLETE_FUTURE',NULL,NULL,NULL,9999)")
        before=path.read_bytes();s=self.service();s.refresh()
        r=s.report('OBSERVATION_LIVE');self.assertEqual(r['summary']['return_30m']['n'],1)
        self.assertEqual(r['signals'][0]['horizons'][0]['return_pct'],7)
        self.assertEqual(path.read_bytes(),before)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT status FROM live_horizons WHERE minutes=30').fetchone()[0],'PENDING')

    def test_missing_verified_range_never_completes_even_with_bars(self):
        self.verified()
        with closing(sqlite3.connect(self.archive)) as db, db:db.execute('UPDATE scanner_state SET verified_until=6000')
        s=self.service();s.refresh();self.assertEqual(s.report()['summary']['analyzed'],0)

    def test_all_rows_aggregate_before_pagination_and_cohorts_stay_separate(self):
        self.verified()
        with closing(sqlite3.connect(self.archive)) as db, db:
            db.executemany("INSERT INTO signals VALUES(?,'KRW-ETH',6000,100,6012,'CATCHUP')",[(f's{i}',) for i in range(205)])
        s=self.service();s.refresh();report=s.report('ALL')
        self.assertEqual(report['summary']['total'],206);self.assertEqual(report['summary']['return_30m']['n'],206)
        self.assertEqual(len(report['signals']),200);self.assertEqual(len(s.report('ALL',200)['signals']),6)
        self.assertEqual(s.report('ARCHIVE_LIVE')['summary']['total'],1)
        self.assertEqual(s.report('ARCHIVE_CATCHUP')['summary']['total'],205)
        self.assertEqual(len(report['patterns']),2)
        with self.assertRaises(LookupError):s.report('bad')

    def test_missing_metrics_have_independent_valid_counts_and_no_infinities(self):
        rows=[dict(horizons=[dict(minutes=30,status='COMPLETE',return_pct=0,mfe_pct=None,mae_pct=-2)]),
              dict(horizons=[dict(minutes=30,status='PENDING',return_pct=99,mfe_pct=99,mae_pct=-99)])]
        s=a.stats(rows)
        self.assertEqual(s['return_30m'],dict(value=0,n=1))
        self.assertEqual(s['rise_30m'],dict(value=0,n=1))
        self.assertEqual(s['mfe_30m'],dict(value=None,n=0));self.assertEqual(s['mae_30m']['n'],1)

    def test_pattern_comparison_uses_actual_saved_pattern(self):
        self.archive.unlink();root=self.runtime/'episode_fixture';path=root/'upbit.db';self.make_db(path,True)
        (root/'config.json').write_text('{}')
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("INSERT INTO live_signal_details VALUES('saved','UPBIT','DIP',NULL,'NOT_DEFINED_BY_V4',6000,100,6000,'SAVED')")
        s=self.service();s.refresh();r=s.report('OBSERVATION_LIVE')
        self.assertEqual([p['pattern'] for p in r['patterns']],['DIP'])


class Security(unittest.TestCase):
    setUp=fixtures.HTTPBoundary.setUp
    close=fixtures.HTTPBoundary.close

    def post(self, path='/api/control/start', headers=None, body='{}'):
        h={'Host':f'127.0.0.1:{self.server.server_port}',
           'Origin':f'http://127.0.0.1:{self.server.server_port}',
           'Content-Type':'application/json','X-CSRF-Token':self.server.csrf}
        h.update(headers or {})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            conn.request('POST',path,body=body,headers=h);response=conn.getresponse()
            return response.status,response.read()
        finally:conn.close()

    def test_external_missing_null_origin_and_bad_token_cannot_control(self):
        with patch.object(self.server.operations,'request') as action:
            for h in [{'Origin':'https://evil.example'},{'Origin':'null'},
                      {'Origin':''},{'X-CSRF-Token':'bad'},{'Sec-Fetch-Site':'cross-site'},
                      {'Host':'evil.example'},{'Sec-Fetch-Site':'same-site'}]:
                self.assertEqual(self.post(headers=h)[0],403)
            action.assert_not_called()

    def test_only_exact_local_empty_json_starts_and_browser_cannot_change_limits(self):
        with patch.object(self.server.operations,'request') as action,patch.object(self.server.operations,'status',return_value={}):
            self.assertEqual(self.post()[0],202);action.assert_called_once_with('start')
            action.reset_mock()
            self.assertEqual(self.post(body='{"seconds":86400}')[0],400)
            self.assertEqual(self.post(headers={'Content-Type':'text/plain'})[0],400)
            action.assert_not_called()

    def test_read_routes_and_get_control_are_never_actions(self):
        with patch.object(self.server.operations,'request') as action:
            for path in ('/analysis','/api/control/start'):
                status,_,_=fixtures.HTTPBoundary.request(self,path)
                self.assertEqual(status,200 if path=='/analysis' else 404)
            action.assert_not_called()


class Operations(unittest.TestCase):
    def test_stop_before_precheck_publication_cancels_delayed_start(self):
        op=d.Operations(120,80);entered=threading.Event()
        def delayed_start(seconds,requests,event):
            entered.set();self.assertTrue(event.wait(3))
            return dict(status='STOPPED',phase='TERMINAL',reason='CANCELLED_BEFORE_LIVE')
        with patch.object(d.control,'current',return_value=None),patch.object(desktop,'start_scanner',side_effect=delayed_start),patch.object(desktop,'stop_scanner',return_value=dict(status='STOPPED')):
            op.request('start');self.assertTrue(entered.wait(1));op.request('stop')
            for t in op.threads:t.join(3)
        self.assertEqual(op.result['action'],'stop');self.assertEqual(op.result['state'],'SUCCEEDED')

    def test_duplicate_and_stop_use_existing_helpers_and_keep_web_alive(self):
        op=d.Operations(120,80);entered=threading.Event();release=threading.Event()
        def start(*_):entered.set();release.wait(3);return dict(status='RUNNING',phase='OBSERVING')
        with patch.object(d.control,'current',return_value=None),patch.object(desktop,'start_scanner',side_effect=start) as helper:
            op.request('start');self.assertTrue(entered.wait(1))
            with self.assertRaises(RuntimeError):op.request('start')
            release.set();op.threads[0].join(3);helper.assert_called_once_with(120,80,op.cancel_start)
        self.assertEqual(op.result['state'],'SUCCEEDED')
        with patch.object(d.control,'current',return_value=None),patch.object(desktop,'stop_scanner',return_value=dict(status='STOPPED')) as stop,patch.object(desktop,'stop_web') as web:
            op.request('stop');op.threads[-1].join(3);self.assertTrue(stop.called);web.assert_not_called()

    def test_clock_failure_is_human_readable_and_never_claims_success(self):
        op=d.Operations(120,80)
        with patch.object(d.control,'current',return_value=None),patch.object(desktop,'start_scanner',return_value=dict(status='BLOCKED',reason='CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')):
            op.request('start');op.threads[0].join(3)
        self.assertEqual(op.result['state'],'FAILED');self.assertIn('시계 안전 검증 실패',op.result['message'])

    def test_bat_default_opens_web_only(self):
        with patch.object(desktop,'start',return_value=0) as start:
            self.assertEqual(desktop.main(['start']),0)
            self.assertTrue(start.call_args.args[2])


class IsolatedProcessLifecycle(unittest.TestCase):
    def test_real_owned_process_readiness_stop_save_and_unrelated_process_survives(self):
        # An offline process fixture, not a LIVE admission. Production web,
        # start_scanner, identities, STOP, save checks and DB close are exercised.
        program=r'''
import os,sys,time
from pathlib import Path
from coin_analysis import scanner_control_v410 as c
c.CONTROL=Path(sys.argv[1]);c.observer.RUNTIME_ROOT=Path(sys.argv[2])
token='b'*32;root=c.observer.RUNTIME_ROOT/('console_'+token)
(c.CONTROL/'launches'/token).mkdir(parents=True);root.mkdir(parents=True)
cfg=dict(markets=c.observer.MARKETS,signal_start=86400)
dbs={e:c.observer.open_runtime(root,cfg,e) for e in c.observer.v42.HOSTS}
s=dict(launch_id=token,root=str(root),status='RUNNING',phase='OBSERVING',manager=c.identity(os.getpid()),child=c.identity(os.getpid()),clock_evidence=None,db_saved='UNKNOWN')
c.persist(s);c.write_metadata(c.CONTROL/'current.json',dict(launch_id=token))
until=time.monotonic()+15
while not (root/'STOP').exists() and time.monotonic()<until:time.sleep(.02)
for db in dbs.values():
 with db:db.execute("INSERT INTO minute_candles VALUES('KRW-ETH',86400,1,1,1,1,1)")
 c.observer.ops.close_cleanly(db)
(root/'runs').mkdir()
c.write_metadata(root/'runs/one.summary.json',dict(run_id='one',close_errors={},status='STOPPED',reason='STOP_REQUESTED',requests=0))
c.write_metadata(root/'runs/one.exit.json',dict(worker_reaped=True,forced_kill=False,worker_returncode=0))
s.update(status='STOPPED',phase='TERMINAL',**{k:v for k,v in c.saved_result(root).items() if k!='ok'});c.persist(s)
'''
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            base=Path(temp)
            for obj,name,value in [(desktop,'WEB',base/'web'),(d.control,'CONTROL',base/'control'),
                                   (d.control.observer,'RUNTIME_ROOT',base/'runtime')]:
                stack.enter_context(patch.object(obj,name,value))
            children=[]
            def spawn(_):
                child=subprocess.Popen([sys.executable,'-c',program,str(base/'control'),str(base/'runtime')],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
                children.append(child);return child
            stack.enter_context(patch.object(desktop,'spawn',side_effect=spawn))
            unrelated=subprocess.Popen([sys.executable,'-c',
                "import sys,time;from pathlib import Path;p=Path(sys.argv[1]);end=time.monotonic()+20\nwhile not p.exists() and time.monotonic()<end:time.sleep(.02)",str(base/'unrelated-stop')],creationflags=0x08000000)
            server=d.Server(('127.0.0.1',0),seconds=120,max_requests=80)
            thread=threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.05));thread.start()
            def post(action):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                try:
                    conn.request('POST','/api/control/'+action,body='{}',headers={
                        'Origin':f'http://127.0.0.1:{server.server_port}','Content-Type':'application/json','X-CSRF-Token':server.csrf})
                    response=conn.getresponse();response.read();return response.status
                finally:conn.close()
            try:
                self.assertEqual(post('start'),202)
                until=time.monotonic()+8
                while server.operations.active and time.monotonic()<until:time.sleep(.05)
                self.assertEqual(server.operations.result['state'],'SUCCEEDED')
                self.assertEqual(server.operations.status()['scanner']['phase'],'OBSERVING')
                self.assertEqual(post('start'),409)
                self.assertEqual(post('stop'),202)
                until=time.monotonic()+8
                while server.operations.active and time.monotonic()<until:time.sleep(.05)
                self.assertEqual(server.operations.result['state'],'SUCCEEDED')
                state=server.operations.status();self.assertFalse(state['process_alive'])
                self.assertTrue(state['scanner']['db_saved'].startswith('SAVED'))
                self.assertIsNone(unrelated.poll())
                self.assertTrue(thread.is_alive())
                for path in (base/'runtime').rglob('*.db'):
                    with closing(sqlite3.connect(path)) as db:
                        self.assertEqual(db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],1)
            finally:
                for root in (base/'runtime').glob('*'):
                    if root.is_dir():(root/'STOP').touch()
                for child in children:child.wait(timeout=18)
                (base/'unrelated-stop').touch();unrelated.wait(timeout=3)
                server.operations.close();server.shutdown();server.server_close();thread.join(3)


if __name__=='__main__':unittest.main()
