import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from coin_analysis import forward_scanner_v43 as v
from coin_analysis import scanner_clock_v45 as clock
from coin_analysis import scanner_observation_v45 as price


class Prices(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.config=dict(markets=v.MARKETS,signal_start=86400)
        self.db=v.open_runtime(self.root,self.config,'UPBIT');self.addCleanup(lambda:self.db.close())

    def candle(self,ts=86340,receipt=86405,value=100.):
        with self.db:
            self.db.execute('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',('KRW-ENA',ts,value,value,value,value,12.))
            self.db.execute('INSERT INTO candle_receipts VALUES(?,?,?)',('KRW-ENA',ts,receipt))

    def proof(self,ts=86400,known=86465):
        with self.db:self.db.execute('INSERT INTO no_trade_evidence_v45 VALUES(?,?,?,?)',('KRW-ENA',ts,known,'isolated validated fixture'))

    def point(self,end=86460,asof=86465):
        return price.price_point(self.db,'KRW-ENA',end,asof)

    def test_actual_and_derived_prices_separate_without_modifying_candles_or_values(self):
        self.candle();self.proof()
        before=v.ops.full_fingerprints(self.db)
        self.assertEqual(self.point(86400)['basis'],'ACTUAL_CANDLE_CLOSE')
        self.assertEqual(self.point()['basis'],'DERIVED_NO_TRADE_LAST_CLOSE')
        self.assertEqual(before,v.ops.full_fingerprints(self.db))
        self.assertEqual(self.db.execute('SELECT trade_value FROM minute_candles').fetchone()[0],12.)

    def test_candle_absence_and_successful_collection_do_not_prove_no_trade(self):
        self.candle()
        with self.db:self.db.execute('UPDATE scanner_state SET verified_until=90000')
        self.assertEqual(self.point()['reason'],'NO_TRADE_NOT_PROVEN_ASOF')

    def test_later_proof_and_later_receipt_cannot_leak(self):
        self.candle();self.proof(known=86466)
        self.assertEqual(self.point()['status'],'UNAVAILABLE')
        self.assertEqual(self.point(asof=86466)['status'],'AVAILABLE')
        with self.db:self.db.execute('UPDATE candle_receipts SET first_received_at=86467')
        self.assertEqual(self.point(asof=86466)['reason'],'NO_KNOWN_CONFIRMED_PRICE')

    def test_no_last_price_and_stale_price_are_unavailable(self):
        self.assertEqual(self.point()['reason'],'NO_KNOWN_CONFIRMED_PRICE')
        self.candle()
        for ts in range(86400,86700,60):self.proof(ts,known=86705)
        self.assertEqual(self.point(86640,86705)['status'],'AVAILABLE') # exact 300s upper bound
        self.assertEqual(self.point(86700,86705)['reason'],'STALE_LAST_PRICE')

    def test_open_future_and_late_actual_source_are_rejected(self):
        self.candle();self.proof()
        self.assertEqual(self.point(asof=86464.999)['status'],'PENDING')
        self.candle(86400,receipt=86470,value=999.)
        self.assertEqual(self.point()['reason'],'UNRECEIPTED_OR_LATE_SOURCE')
        self.assertEqual(self.point(asof=86470)['price'],999.)

    def seed_signal(self):
        with self.db:
            self.db.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)',('id','KRW-ENA',86400,100.,4.,'cluster',86412,12,'LIVE'))
            self.db.execute('INSERT INTO signal_features VALUES(?,?,?,?,?)',('id',86400,'{}','{}','{}'))
            self.db.execute('UPDATE scanner_state SET verified_until=90000')

    def test_30_60_endpoint_completion_is_not_frozen_full_path_label_completion(self):
        self.seed_signal();self.candle(88140,88205,101.)
        v.record_metrics(self.db,'UPBIT',88205)
        self.assertEqual(self.db.execute('SELECT status FROM price_horizons_v45 WHERE minutes=30').fetchone()[0],'COMPLETE')
        self.assertEqual(self.db.execute('SELECT status FROM price_horizons_v45 WHERE minutes=60').fetchone()[0],'PENDING')
        self.assertEqual({r[0] for r in self.db.execute('SELECT status FROM live_horizons')},{'PENDING'})
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM signal_outcomes').fetchone()[0],0)

    def test_pending_60m_endpoint_survives_real_disk_close_reopen(self):
        self.seed_signal();v.record_metrics(self.db,'UPBIT',88205)
        v.ops.close_cleanly(self.db);self.db=v.open_runtime(self.root,self.config,'UPBIT')
        self.candle(89940,90005,102.);v.record_metrics(self.db,'UPBIT',90005)
        row=self.db.execute('SELECT * FROM price_horizons_v45 WHERE minutes=60').fetchone()
        self.assertEqual(row['status'],'COMPLETE');self.assertAlmostEqual(row['return_pct'],2.)
        original=tuple(row);self.candle(90000,90065,999.)
        v.record_metrics(self.db,'UPBIT',90100)
        self.assertEqual(tuple(self.db.execute('SELECT * FROM price_horizons_v45 WHERE minutes=60').fetchone()),original)

    def test_crashed_process_recovers_pending_evidence_and_committed_wal(self):
        # Actual separate process exits without close/checkpoint; no network.
        script='''
import os,sys
from coin_analysis import forward_scanner_v43 as v
db=v.open_runtime(sys.argv[1],dict(markets=v.MARKETS,signal_start=86400),'BITHUMB')
with db:
 db.execute("INSERT INTO no_trade_evidence_v45 VALUES('KRW-ENA',86400,86465,'crash fixture')")
 db.execute("INSERT INTO price_horizons_v45 VALUES('fixture',60,'PENDING','HORIZON_NOT_REACHED',NULL,NULL,NULL,NULL,86465,'test')")
os._exit(19)
'''
        done=subprocess.run([sys.executable,'-c',script,str(self.root)],capture_output=True,timeout=10)
        self.assertEqual(done.returncode,19,done.stderr)
        other=v.open_runtime(self.root,self.config,'BITHUMB')
        try:
            self.assertEqual(other.execute('PRAGMA quick_check').fetchone()[0],'ok')
            self.assertEqual(other.execute('SELECT status FROM price_horizons_v45').fetchone()[0],'PENDING')
            self.assertEqual(other.execute('SELECT COUNT(*) FROM no_trade_evidence_v45').fetchone()[0],1)
        finally:v.ops.close_cleanly(other)

    def test_future_persisted_progress_blocks_resume(self):
        with self.db:self.db.execute('UPDATE scanner_state SET verified_until=99999')
        with self.assertRaisesRegex(ValueError,'CLOCK_PERSISTED_FUTURE'):clock.resume_continuity(self.db,90000)


class Clocks(unittest.TestCase):
    def result(self,text='',code=0):
        return subprocess.CompletedProcess([],code,text.encode(),b'')

    def measurement(self,offsets=None):
        offsets=offsets or [.01]*6
        return dict(rows=[dict(host=clock.ntp.HOSTS[i%2],status='MEASURED',offset_seconds=x,
            uncertainty_seconds=.02,error_interval_seconds=[x-.02,x+.02]) for i,x in enumerate(offsets)])

    def test_service_failure_still_measures_but_cannot_admit_live(self):
        with patch.object(clock.os,'name','nt'),patch.object(clock.subprocess,'run',side_effect=[self.result(code=1),self.result(json.dumps(self.measurement()))]) as run:
            self.assertEqual(clock.verify_clock()['status'],'BLOCKED')
        self.assertEqual(run.call_count,2)

    def test_external_offset_and_jitter_and_missing_samples_fail_closed(self):
        for measurement in [self.measurement([2.]*6),self.measurement([0.,.8]*3),self.measurement([.01])]:
            with self.subTest(measurement=measurement),patch.object(clock.os,'name','nt'),patch.object(clock.subprocess,'run',side_effect=[self.result(),self.result(json.dumps(measurement))]):
                self.assertEqual(clock.verify_clock()['status'],'BLOCKED')
        with patch.object(clock.os,'name','nt'),patch.object(clock.subprocess,'run',side_effect=[self.result(),self.result(json.dumps(self.measurement()))]):
            self.assertEqual(clock.verify_clock()['status'],'VERIFIED')

    def test_clock_command_timeout_blocks(self):
        with patch.object(clock.os,'name','nt'),patch.object(clock.subprocess,'run',side_effect=subprocess.TimeoutExpired('w32tm',3)):
            self.assertEqual(clock.verify_clock()['status'],'BLOCKED')

    def budget(self,root):
        now=time.time();control=v.ledger(':memory:')
        self.addCleanup(control.close)
        return v.Budget(root,{},dict(run_id='test',created_at=now,duration_seconds=100,deadline=now+100,max_requests=26),control)

    def test_both_wall_clock_jumps_and_accumulated_slow_drift_block(self):
        with tempfile.TemporaryDirectory() as folder:
            b=self.budget(Path(folder));mono,wall=b.clock_anchor
            for jump in (-5,5):
                with patch.object(v.time,'time',return_value=wall+jump),self.assertRaisesRegex(v.Stop,'CLOCK_'):b.check()
            with patch.object(v.time,'time',return_value=wall+32),patch.object(v.time,'monotonic',return_value=mono+30),self.assertRaisesRegex(v.Stop,'CLOCK_'):b.check()

    def test_monotonic_limit_and_periodic_clock_check_before_http(self):
        with tempfile.TemporaryDirectory() as folder:
            b=self.budget(Path(folder));b.monotonic_deadline=time.monotonic()-1
            with self.assertRaisesRegex(v.Stop,'TIME_LIMIT'):b.check()
            b.monotonic_deadline=time.monotonic()+100
            b.clock_verified_at=time.monotonic()-601
            with patch.object(clock,'verify_clock',return_value=dict(status='BLOCKED',reason='CLOCK_SYNC_UNVERIFIED')),patch.object(v.v42.urllib.request,'urlopen') as url:
                with self.assertRaisesRegex(v.Stop,'CLOCK_SYNC_UNVERIFIED'):b.request('UPBIT','/v1/market/all',{})
                url.assert_not_called()

    def test_failed_preflight_never_creates_dataset_or_starts_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(v,'RUNTIME_ROOT',root),patch.object(v.v42,'RUNTIME_ROOT',root/'locks'),patch.object(clock,'verify_clock',return_value=dict(status='BLOCKED',reason='CLOCK_SYNC_UNVERIFIED')),patch.object(v.subprocess,'Popen') as process:
                with self.assertRaisesRegex(v.Stop,'CLOCK_SYNC_UNVERIFIED'):v.run(root/'new',30,max_requests=26)
                process.assert_not_called();self.assertFalse((root/'new').exists())

    def test_oversize_log_record_stops_without_exceeding_rotation_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);b=self.budget(root)
            with self.assertRaisesRegex(v.Stop,'LOG_RECORD_LIMIT'):b.event('TEST',payload='a'*v.LOG_BYTES)
            self.assertFalse((root/'events.jsonl').exists())


if __name__=='__main__':unittest.main()
