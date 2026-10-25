import copy
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from coin_analysis import scanner_clock_v47 as a
from coin_analysis import scanner_clock_v45 as c
from coin_analysis import forward_scanner_v43 as v
from tests.scanner_clock_fixtures import WINDOWS_OK,WINDOWS_KO


def fresh(now):
    return dict(rows=[dict(host=c.ntp.HOSTS[i%2],status='MEASURED',offset_seconds=.003,
        uncertainty_seconds=.02,error_interval_seconds=[-.017,.023],
        local_sent_at=now-.1,local_received_at=now-.05) for i in range(6)])


class WindowsRoot(unittest.TestCase):
    def test_english_and_korean_status_use_relative_sync_age_and_same_distance(self):
        for text in (WINDOWS_OK,WINDOWS_KO):
            row=a.windows_status(text)
            self.assertEqual(row['status'],'VERIFIED')
            self.assertAlmostEqual(row['root_distance_seconds'],.02)
            self.assertEqual(row['sync_age_seconds'],120.)

    def test_actual_large_windows_root_dispersion_blocks_even_small_phase_offset(self):
        text=WINDOWS_KO.replace('0.010s','7.7630189s').replace('0.020s','0.0390809s')
        row=a.windows_status(text)
        self.assertEqual(row['reason'],'CLOCK_WINDOWS_ROOT_UNCERTAINTY')
        self.assertAlmostEqual(row['root_distance_seconds'],7.78255935)

    def test_delay_part_of_distance_and_exact_one_second_boundary(self):
        self.assertEqual(a.windows_status(WINDOWS_OK.replace('0.010s','0.990s'))['status'],'VERIFIED')
        self.assertEqual(a.windows_status(WINDOWS_OK.replace('0.010s','0.991s'))['reason'],'CLOCK_WINDOWS_ROOT_UNCERTAINTY')

    def test_missing_ambiguous_units_nonfinite_and_negative_fail_closed(self):
        for text in [WINDOWS_OK.replace('Root Dispersion: 0.010s\n',''),WINDOWS_OK+'Root Dispersion: 0.010s\n',
                     WINDOWS_OK.replace('0.010s','nan'),WINDOWS_OK.replace('0.010s','-0.01s'),WINDOWS_OK.replace('0.010s','10ms')]:
            with self.subTest(text=text):self.assertEqual(a.windows_status(text)['reason'],'CLOCK_WINDOWS_STATUS_UNPARSEABLE')

    def test_unsynchronized_leap_error_and_old_sync_block(self):
        for text in [WINDOWS_OK.replace('Indicator: 0','Indicator: 3'),WINDOWS_OK.replace('Stratum: 2','Stratum: 0'),
                     WINDOWS_OK.replace('Sync Error: 0','Sync Error: 5')]:
            self.assertEqual(a.windows_status(text)['reason'],'CLOCK_WINDOWS_UNSYNCHRONIZED')
        self.assertEqual(a.windows_status(WINDOWS_OK.replace('120.0s','3600.001s'))['reason'],'CLOCK_WINDOWS_SYNC_STALE')


class Freshness(unittest.TestCase):
    def test_fresh_and_stale_direct_samples(self):
        self.assertEqual(a.measurement_freshness(fresh(100.),100.)['status'],'VERIFIED')
        self.assertEqual(a.measurement_freshness(fresh(100.),116.)['reason'],'CLOCK_REFERENCE_STALE')

    def test_future_missing_or_inverted_sample_timestamps_block(self):
        values=[{},fresh(100.),fresh(100.),fresh(100.)]
        values[1]['rows'][0]['local_received_at']=102.
        values[2]['rows'][0]['local_sent_at']=101.
        del values[3]['rows'][0]['local_received_at']
        for measurement in values:self.assertEqual(a.measurement_freshness(measurement,100.)['status'],'BLOCKED')


class CombinedAdmission(unittest.TestCase):
    def completed(self,text):
        return subprocess.CompletedProcess([],0,text.encode('utf8'),b'')

    def check(self,text,measurement):
        with patch.object(c.os,'name','nt'),patch.object(c.subprocess,'run',side_effect=[self.completed(text),self.completed(json.dumps(measurement))]):
            return c.verify_clock()

    def test_external_accuracy_pass_does_not_override_large_windows_uncertainty(self):
        row=self.check(WINDOWS_OK.replace('0.010s','7.7630189s'),fresh(time.time()))
        self.assertEqual(row['external_assessment']['status'],'VERIFIED')
        self.assertEqual(row['status'],'BLOCKED')
        self.assertEqual(row['reason'],'CLOCK_WINDOWS_ROOT_UNCERTAINTY')

    def test_old_reference_blocks_even_healthy_windows_and_small_offset(self):
        row=self.check(WINDOWS_OK,fresh(time.time()-16))
        self.assertEqual(row['external_assessment']['status'],'VERIFIED')
        self.assertEqual(row['reason'],'CLOCK_REFERENCE_STALE')

    def test_all_gates_can_pass_without_relaxing_original_limits(self):
        row=self.check(WINDOWS_KO,fresh(time.time()))
        self.assertEqual(row['status'],'VERIFIED')
        self.assertEqual(c.MAX_OFFSET_SECONDS,1.)
        self.assertEqual(c.MAX_SPREAD_SECONDS,.5)

    def test_root_failure_prevents_dataset_creation_and_worker_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            blocked=dict(status='BLOCKED',reason='CLOCK_WINDOWS_ROOT_UNCERTAINTY')
            with patch.object(v,'RUNTIME_ROOT',root),patch.object(v.v42,'RUNTIME_ROOT',root/'locks'),\
                 patch.object(c,'verify_clock',return_value=blocked),patch.object(v.subprocess,'Popen') as process:
                with self.assertRaisesRegex(v.Stop,'CLOCK_WINDOWS_ROOT_UNCERTAINTY'):v.run(root/'new',60,max_requests=26)
                process.assert_not_called();self.assertFalse((root/'new').exists())


if __name__=='__main__':unittest.main()
