import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from coin_analysis import forward_scanner_v43 as v


class Runtime(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.config=dict(version='4.3_OBSERVATION',markets=v.MARKETS,policy=v.scanner.POLICY,signal_start=86400)
        self.run=dict(run_id='run',created_at=time.time(),duration_seconds=100,deadline=time.time()+100,max_requests=50,resume=False)
        self.control=v.ledger(self.root/'control.db');self.b=v.Budget(self.root,self.config,self.run,self.control)
    def tearDown(self):
        self.control.close();self.temp.cleanup()
    def request(self):
        return self.b.request('UPBIT','/v1/market/all',{})
    def response(self):
        r=io.StringIO('[{"market":"KRW-BTC"}]');r.headers={};r.status=200;return r
    def test_durable_attempts_survive_log_rotation_and_worker_reconstruction(self):
        with patch.object(v.v42.urllib.request,'urlopen',return_value=self.response()):self.request()
        (self.root/'events.jsonl').unlink()
        restarted=v.Budget(self.root,self.config,self.run,self.control)
        self.assertEqual(restarted.requests,1)
        self.assertEqual(self.control.execute('SELECT status FROM http_attempts').fetchone()[0],'HTTP_END')
    def test_attempt_reserved_before_failed_network_and_retry_recovers(self):
        calls=[urllib.error.URLError('offline'),self.response()]
        client=v.scanner.collector.Client(transport=lambda path,params:self.b.request('UPBIT',path,params),sleep=lambda _:None)
        with patch.object(v.v42.urllib.request,'urlopen',side_effect=calls),patch.object(self.b,'sleep'):
            result=client.get('/v1/market/all')
        self.assertEqual(result,[dict(market='KRW-BTC')]);self.assertEqual(client.retries,1)
        self.assertEqual([r[0] for r in self.control.execute('SELECT status FROM http_attempts ORDER BY seq')],['HTTP_ERROR','HTTP_END'])
    def test_order_endpoint_and_scope_rejected_without_network_or_ledger(self):
        with patch.object(v.v42.urllib.request,'urlopen') as url:
            with self.assertRaises(ValueError):self.b.request('UPBIT','/v1/orders',{})
            with self.assertRaises(ValueError):self.b.request('UPBIT','/v1/candles/minutes/1',dict(market='KRW-OTHER',count=200))
        url.assert_not_called();self.assertEqual(self.control.execute('SELECT COUNT(*) FROM http_attempts').fetchone()[0],0)
    def test_stop_and_deadline_checked_before_http(self):
        (self.root/'STOP').touch()
        with patch.object(v.v42.urllib.request,'urlopen') as url,self.assertRaises(v.Stop):self.request()
        url.assert_not_called()
    def test_round_reserves_prevent_normal_boundary_partial_poll(self):
        self.b.config['deadline']=time.time()+10
        self.assertEqual(self.b.round_admission(),'ROUND_TIME_RESERVE')
        self.b.config['deadline']=time.time()+100;self.b.config['max_requests']=11
        self.assertEqual(self.b.round_admission(),'ROUND_REQUEST_RESERVE')
    def test_cpu_memory_disk_and_clock_stop_safely(self):
        self.b.cpu_sample=(time.monotonic()-11,time.process_time()-10)
        with self.assertRaisesRegex(v.Stop,'CPU_LIMIT'):self.b.check()
        self.b.cpu_sample=(time.monotonic(),time.process_time())
        with patch.object(v.v42,'rss_bytes',return_value=v.MAX_RSS+1),self.assertRaisesRegex(v.Stop,'MEMORY_LIMIT'):self.b.check()
        self.b.peak_rss=0
        with patch.object(v,'MAX_DISK',0),self.assertRaisesRegex(v.Stop,'DISK_LIMIT'):self.b.check()
        self.b.last_clock=time.time()+10
        with self.assertRaisesRegex(v.Stop,'CLOCK'):self.b.check()
    def test_rotated_logs_are_bounded_without_touching_db(self):
        with patch.object(v,'LOG_BYTES',150):
            for _ in range(40):self.b.event('TEST',text='a'*25)
        files=list(self.root.glob('events*.jsonl'))
        self.assertLessEqual(len(files),v.LOG_COPIES)
        self.assertTrue(all(p.stat().st_size<=150 for p in files))
        self.assertEqual(self.control.execute('PRAGMA quick_check').fetchone()[0],'ok')
    def test_fixed_policy_and_cohort(self):
        v.validate_config(self.config)
        with self.assertRaises(ValueError):v.validate_config(dict(self.config,markets=['KRW-BTC','KRW-XRP']))
        self.assertEqual(v.scanner.POLICY['range_threshold'],4)
        self.assertEqual(v.scanner.POLICY['step_seconds'],300)
    def test_resume_keeps_config_and_history_but_uses_explicit_new_run_budget(self):
        episode=self.root/'episode';episode.mkdir();v.write_json(episode/'config.json',self.config)
        db=v.open_runtime(episode,self.config,'UPBIT')
        with db:db.execute("UPDATE scanner_state SET last_observation=90000,active=1,cluster_id='frozen'")
        before=v.ops.full_fingerprints(db);v.ops.close_cleanly(db)
        p=MagicMock();p.pid=123;p.wait.return_value=0
        with patch.object(v,'RUNTIME_ROOT',self.root),patch.object(v.v42,'RUNTIME_ROOT',self.root/'locks'),patch.object(v.subprocess,'Popen',return_value=p):
            self.assertEqual(v.run(episode,60,True,50),0)
        db=v.open_runtime(episode,self.config,'UPBIT')
        self.assertEqual(before,v.ops.full_fingerprints(db));v.ops.close_cleanly(db)
        self.assertEqual(json.loads((episode/'config.json').read_text()),self.config)
    def test_watchdog_reaps_only_own_child_and_marks_forced(self):
        p=MagicMock();p.pid=123;p.wait.side_effect=[subprocess.TimeoutExpired('worker',1),subprocess.TimeoutExpired('worker',1),0]
        with patch.object(v,'RUNTIME_ROOT',self.root),patch.object(v.v42,'RUNTIME_ROOT',self.root/'locks'),patch.object(v.subprocess,'Popen',return_value=p):
            self.assertEqual(v.run(self.root/'episode',30,False,50),124)
        p.kill.assert_called_once()
        result=json.loads(next((self.root/'episode/runs').glob('*.exit.json')).read_text())
        self.assertTrue(result['worker_reaped']);self.assertTrue(result['forced_kill'])
    def test_duplicate_guard_precedes_dataset_mutation(self):
        with patch.object(v,'RUNTIME_ROOT',self.root),patch.object(v.v42,'RUNTIME_ROOT',self.root/'locks'):
            with v.scanner.exclusive(self.root/'locks/supervisor'):
                with self.assertRaisesRegex(RuntimeError,'Another scanner'):v.run(self.root/'new',30,False,50)
        self.assertFalse((self.root/'new').exists())

    def exercise_worker_errors(self, recover):
        episode=self.root/'worker';episode.mkdir();(episode/'runs').mkdir()
        cfg=dict(self.config,signal_start=(int(time.time())//300+1)*300)
        bounds=dict(self.run,deadline=self.run['created_at']+self.run['duration_seconds'])
        v.write_json(episode/'config.json',cfg);v.write_json(episode/'runs/run.json',bounds)
        calls=[];sleeps=[]
        def fake_cycle(db,*args,**kwargs):
            calls.append(1);round_number=(len(calls)+1)//2
            with db:db.execute('UPDATE scanner_state SET last_error=?',
                (None if recover and round_number>=2 else 'temporary network exhausted',))
        def fake_sleep(*args):
            sleeps.append(1)
            if recover and len(sleeps)==2:raise v.Stop('STOP_REQUESTED')
        with patch.object(v,'RUNTIME_ROOT',self.root),patch.object(v.v42,'RUNTIME_ROOT',self.root/'locks'),\
             patch.object(v.signal,'signal'),patch.object(v.Budget,'request',return_value=([dict(market=m) for m in v.MARKETS],{})),\
             patch.object(v.scanner,'cycle',side_effect=fake_cycle),patch.object(v.Budget,'sleep',side_effect=fake_sleep):
            code=v.worker(episode,'run')
        return code,json.loads((episode/'runs/run.summary.json').read_text()),len(calls)

    def test_transient_round_errors_clear_on_next_round_without_new_dataset(self):
        code,summary,calls=self.exercise_worker_errors(True)
        self.assertEqual(code,0);self.assertEqual(summary['completed_rounds'],2);self.assertEqual(calls,4)
        self.assertEqual(summary['collection_errors'],{'UPBIT':[],'BITHUMB':[]})

    def test_exhausted_network_recovery_opens_circuit_after_five_rounds(self):
        code,summary,calls=self.exercise_worker_errors(False)
        self.assertEqual(code,1);self.assertEqual(summary['status'],'BLOCKED')
        self.assertEqual(summary['reason'],'NETWORK_CIRCUIT_OPEN_5_ROUNDS');self.assertEqual(calls,10)


class Observation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.config=dict(markets=v.MARKETS,signal_start=86400)
        self.db=v.open_runtime(self.root,self.config,'UPBIT')
    def tearDown(self):
        self.db.close();self.temp.cleanup()
    def candles(self,n,start=86400):
        with self.db:self.db.executemany('INSERT OR IGNORE INTO minute_candles VALUES(?,?,?,?,?,?,?)',
            [('KRW-ENA',start+i*60,100.,102.,98.,101.,1000.) for i in range(n)])
    def signal(self):
        with self.db:
            self.db.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)',('id','KRW-ENA',86400,100.,4.,'cluster',86412,12,'LIVE'))
            self.db.execute('INSERT INTO signal_features VALUES(?,?,?,?,?)',('id',86400,json.dumps(dict(return_5m_pct=2.,trade_value_ratio=3.)),'{}','{}'))
            self.db.execute('UPDATE scanner_state SET verified_until=90000')
    def test_source_absence_is_not_collection_failure_or_filled_candle(self):
        before={m:86100 for m in v.MARKETS};self.candles(29,84600)
        with self.db:self.db.execute('UPDATE scanner_state SET last_observation=86400,verified_until=86400')
        v.coverage(self.db,before,86412)
        row=self.db.execute("SELECT * FROM coverage_windows WHERE market='KRW-ENA' AND minutes=30").fetchone()
        self.assertEqual(row['observed'],29);self.assertEqual(row['status'],'SOURCE_ABSENT')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],29)
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("UPDATE coverage_windows SET status='COMPLETE'")
        self.db.rollback()
    def test_not_yet_collected_distinct_from_api_absence(self):
        with self.db:self.db.execute('UPDATE scanner_state SET last_observation=86400,verified_until=86340')
        v.coverage(self.db,{m:86100 for m in v.MARKETS},86412)
        self.assertEqual({r[0] for r in self.db.execute('SELECT status FROM coverage_windows')},{'NOT_COLLECTED'})
    def test_detection_price_uses_receipt_not_future_or_late_arrival(self):
        self.signal();self.candles(1,86340);self.candles(1,86280)
        with self.db:
            self.db.execute("INSERT INTO candle_receipts VALUES('KRW-ENA',86340,86413)")
            self.db.execute("INSERT INTO candle_receipts VALUES('KRW-ENA',86280,86410)")
        v.record_metrics(self.db,'UPBIT',86420)
        row=self.db.execute('SELECT * FROM live_signal_details').fetchone()
        self.assertEqual(row['detection_price_close_time'],86340)
        context=self.db.execute('SELECT * FROM signal_context').fetchone()
        self.assertEqual(context['pre_price_change_5m_pct'],2.)
        self.assertEqual(context['pre_trade_value_ratio'],3.)
    def test_60m_pending_survives_close_resume_and_only_finishes_on_full_actual_data(self):
        self.signal();self.candles(15);v.record_metrics(self.db,'UPBIT',87300)
        self.assertEqual(self.db.execute('SELECT status FROM live_horizons WHERE minutes=60').fetchone()[0],'PENDING')
        v.ops.close_cleanly(self.db);self.db=v.open_runtime(self.root,self.config,'UPBIT')
        self.candles(60);v.record_metrics(self.db,'UPBIT',90000)
        row=self.db.execute('SELECT * FROM live_horizons WHERE minutes=60').fetchone()
        self.assertEqual(row['status'],'COMPLETE');self.assertAlmostEqual(row['return_pct'],1.)
        v.record_metrics(self.db,'UPBIT',90100)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM live_horizons').fetchone()[0],4)
    def test_future_database_cannot_complete_unreached_horizon(self):
        self.signal();self.candles(60);v.record_metrics(self.db,'UPBIT',86460)
        self.assertEqual({r[0] for r in self.db.execute('SELECT status FROM live_horizons')},{'PENDING'})


if __name__=='__main__':unittest.main()
