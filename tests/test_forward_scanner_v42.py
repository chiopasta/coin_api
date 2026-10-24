import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch,MagicMock

from coin_analysis import forward_scanner_v42 as v
from coin_analysis import forward_scanner_v42_review as review


class Metrics(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.db=v.scanner.connect(self.root/'test.db')
        v.scanner.initialize(self.db,v.MARKETS,86400);v.observation_schema(self.db)
        with self.db:
            self.db.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)',('id','KRW-ENA',86400,100.,4.,'cluster',86412,12,'LIVE'))
            self.db.execute('UPDATE scanner_state SET verified_until=?',(90000,))
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def ingest(self,minutes):
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO minute_candles VALUES(?,?,?,?,?,?,?)',
                [('KRW-ENA',86400+i*60,100.,102.,98.,101.,1000.) for i in range(minutes)])
    def test_pending_never_uses_incomplete_horizon(self):
        self.ingest(4);v.record_metrics(self.db,'UPBIT',86700)
        row=self.db.execute('SELECT * FROM live_horizons WHERE minutes=5').fetchone()
        self.assertEqual(row['status'],'PENDING');self.assertIsNone(row['return_pct'])
        self.assertEqual(row['observed_minutes'],4)
    def test_complete_price_metrics_and_null_score(self):
        self.ingest(5);v.record_metrics(self.db,'UPBIT',86700)
        row=self.db.execute('SELECT * FROM live_horizons WHERE minutes=5').fetchone()
        self.assertEqual(row['status'],'COMPLETE')
        self.assertAlmostEqual(row['return_pct'],1.);self.assertAlmostEqual(row['mfe_pct'],2.);self.assertAlmostEqual(row['mae_pct'],-2.)
        details=self.db.execute('SELECT * FROM live_signal_details').fetchone()
        self.assertIsNone(details['score']);self.assertEqual(details['score_status'],'NOT_DEFINED_BY_V4')
        self.assertIsNone(details['detection_price'])  # No closed post-signal bar existed at t+12.
    def test_future_in_database_cannot_complete_before_its_close(self):
        self.ingest(60);v.record_metrics(self.db,'BITHUMB',86460)
        self.assertEqual({r[0] for r in self.db.execute('SELECT status FROM live_horizons')},{'PENDING'})
    def test_restart_duplicate_and_completed_immutable(self):
        self.ingest(5);v.record_metrics(self.db,'UPBIT',86700)
        before=tuple(self.db.execute('SELECT * FROM live_horizons WHERE minutes=5').fetchone())
        self.db.close();self.db=v.scanner.connect(self.root/'test.db');v.observation_schema(self.db)
        self.ingest(15);v.record_metrics(self.db,'UPBIT',87300)
        self.assertEqual(before,tuple(self.db.execute('SELECT * FROM live_horizons WHERE minutes=5').fetchone()))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM live_horizons').fetchone()[0],4)
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("UPDATE live_horizons SET return_pct=999 WHERE minutes=5")
        self.db.rollback()


class Bounds(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.config=dict(deadline=time.time()+60,max_requests=2,markets=v.MARKETS)
        self.budget=v.Budget(self.root,self.config)
    def tearDown(self):self.tmp.cleanup()
    def test_scope_never_allows_account_or_unknown_market(self):
        with self.assertRaises(ValueError):self.budget.request('UPBIT','/v1/orders',{})
        with self.assertRaises(ValueError):self.budget.request('UPBIT','/v1/candles/minutes/1',dict(market='KRW-OTHER',count=200,to=v.scanner.collector.iso(0)))
        self.assertEqual(self.budget.requests,0)
    def test_stop_file_and_deadline_prevent_network(self):
        (self.root/'STOP').touch()
        with patch.object(v.urllib.request,'urlopen') as urlopen,self.assertRaises(v.ObservationStop):self.budget.request('UPBIT','/v1/market/all',{})
        urlopen.assert_not_called()
        (self.root/'STOP').unlink();self.config['deadline']=0
        with self.assertRaises(v.ObservationStop):self.budget.check()
    def test_memory_and_disk_bounds(self):
        with patch.object(v,'rss_bytes',return_value=v.MAX_RSS_BYTES+1),self.assertRaises(v.ObservationStop):self.budget.check()
        self.budget.peak_rss=0
        (self.root/'sample').write_text('disk')
        with patch.object(v,'MAX_DISK_BYTES',1),self.assertRaises(v.ObservationStop):self.budget.check()
    def test_error_attempt_count_persisted_and_no_budget_reset(self):
        with patch.object(v.urllib.request,'urlopen',side_effect=TimeoutError('transport')):
            with self.assertRaises(TimeoutError):self.budget.request('UPBIT','/v1/market/all',{})
        restored=v.Budget(self.root,self.config)
        self.assertEqual(restored.requests,1)
        restored.requests=2
        with self.assertRaises(v.ObservationStop):restored.request('UPBIT','/v1/market/all',{})
    def test_bithumb_request_uses_kst_and_error_body_rejected(self):
        response=io.StringIO('{"error":{"name":400}}');response.status=200;response.headers={}
        with patch.object(v.urllib.request,'urlopen',return_value=response) as urlopen:
            with self.assertRaises(v.candles.CandleValidationError):self.budget.request('BITHUMB','/v1/candles/minutes/1',dict(market='KRW-BTC',count=200,to=v.scanner.collector.iso(0)))
        self.assertIn('to=1970-01-01T09%3A00%3A00',urlopen.call_args.args[0].full_url)
    def test_opt_in_before_worker_or_network(self):
        with patch.object(v.sys,'argv',['observe','--runtime-dir','unused']),patch.object(v,'run') as run:
            with self.assertRaises(SystemExit):v.main()
        run.assert_not_called()
    def test_watchdog_kills_and_reaps_only_its_worker(self):
        process=MagicMock();process.pid=123
        process.wait.side_effect=[subprocess.TimeoutExpired('worker',1),0]
        with patch.object(v,'RUNTIME_ROOT',self.root),patch.object(v.subprocess,'Popen',return_value=process):
            self.assertEqual(v.run(self.root/'episode',1),124)
        process.kill.assert_called_once();self.assertEqual(process.wait.call_count,2)
        self.assertTrue(json.loads((self.root/'episode/supervisor_exit.json').read_text())['worker_reaped'])
    def test_frozen_limits_and_original_policy(self):
        cfg=dict(markets=v.MARKETS,policy=v.scanner.POLICY,max_requests=220,duration_seconds=900,created_at=100,deadline=1000)
        v.validate_config(cfg)
        with self.assertRaises(ValueError):v.validate_config(dict(cfg,deadline=1001))
        with self.assertRaises(ValueError):v.validate_config(dict(cfg,max_requests=221))
        self.assertEqual(v.scanner.POLICY['range_threshold'],4)
        self.assertEqual(v.scanner.POLICY['step_seconds'],300)

    def test_budget_stop_summary_refreshes_final_database_errors(self):
        episode=self.root/'episode';episode.mkdir()
        now=time.time()
        cfg=dict(markets=v.MARKETS,policy=v.scanner.POLICY,max_requests=2,duration_seconds=10,
                 created_at=now,deadline=now+10,signal_start=(int(now)//300+1)*300)
        (episode/'config.json').write_text(json.dumps(cfg),encoding='utf8')
        def stopped(db,*args,**kwargs):
            with db:db.execute("UPDATE scanner_state SET last_error='TIME_LIMIT' WHERE market='KRW-FLOCK'")
            raise v.ObservationStop('TIME_LIMIT')
        with patch.object(v,'RUNTIME_ROOT',self.root),patch.object(v.signal,'signal'),\
             patch.object(v.Budget,'request',return_value=([dict(market=m) for m in v.MARKETS],{})),\
             patch.object(v.scanner,'cycle',side_effect=stopped):
            self.assertEqual(v.worker(episode),0)
        summary=json.loads((episode/'worker_summary.json').read_text(encoding='utf8'))
        self.assertEqual(summary['collection_errors']['UPBIT'],[dict(market='KRW-FLOCK',last_error='TIME_LIMIT')])
        self.assertEqual(summary['close_errors'],{})
        with v.scanner.exclusive(self.root/'observer'):pass  # Shutdown released its lock.


class EventReview(unittest.TestCase):
    def series(self,missing=False):
        return v.scanner.v3.v2.old.Series([(t,100.,106. if t>=86400+600 else 100.,100.,100.,1000.)
            for t in range(86400-60,86400+3600,60) if not (missing and t==86400+180)])
    def test_less_than_hour_is_not_a_zero_miss_rate(self):
        result=review.events_at(self.series(),[],86400,86400+900,5)
        self.assertEqual(result['eligible_full_future_anchors'],0)
        self.assertEqual(result['events'],[])
    def test_missing_future_never_counts_as_negative_or_complete(self):
        result=review.events_at(self.series(True),[],86400,90000,5)
        self.assertEqual(result['eligible_full_future_anchors'],0)
    def test_real_delivery_time_not_nominal_catchup_drives_recall(self):
        signals=[dict(source='CATCHUP',detected_at=86400),dict(source='LIVE',detected_at=86700)]
        result=review.events_at(self.series(),signals,86400,90000,5)
        self.assertEqual(len(result['events']),1)
        self.assertEqual(result['events'][0]['kind'],'chase')
    def test_reference_early_does_not_claim_true_onset(self):
        result=review.events_at(self.series(),[dict(source='LIVE',detected_at=86400)],86400,90000,5)
        self.assertEqual(result['events'][0]['kind'],'early_reference')
        self.assertIn('NOT certified onset',review.EVENT_POLICY['early_reference'])


if __name__=='__main__':unittest.main()
