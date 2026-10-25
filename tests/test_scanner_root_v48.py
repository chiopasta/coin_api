import unittest
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import MagicMock,patch

from reports.scanner_v48_20261025.analysis import root_trend
from reports.scanner_v48_20261025 import live


def row(epoch,disp,source='time.google.com,0x8'):
    return dict(at=epoch*1024.,windows=dict(source=source,last_sync_display=str(epoch),root_dispersion_seconds=disp,
        root_distance_seconds=disp+.02,leap=0,stratum=2,last_sync_error=0))


class RootDiagnosis(unittest.TestCase):
    def test_distinct_successful_syncs_support_warmup_but_never_admit_live(self):
        result=root_trend([row(1,7.763),row(2,3.809),row(3,1.832)])
        self.assertTrue(result['consistent_with_filter_warmup'])
        self.assertEqual(len(result['epochs']),3)
        self.assertFalse(result['admits_live']);self.assertFalse(result['policy_changed'])

    def test_repeated_queries_of_same_epoch_are_not_new_ntp_samples(self):
        result=root_trend([row(1,7.763)]*20+[row(2,3.809)]*20)
        self.assertEqual(len(result['epochs']),2)
        self.assertFalse(result['consistent_with_filter_warmup'])

    def test_increasing_dispersion_source_changes_or_sync_error_do_not_support_inference(self):
        cases=[[row(1,7),row(2,8),row(3,4)],
               [row(1,7),row(2,3),row(3,1,'other')]]
        broken=[row(1,7),row(2,3),row(3,1)];broken[-1]['windows']['last_sync_error']=1;cases.append(broken)
        for rows in cases:self.assertFalse(root_trend(rows)['consistent_with_filter_warmup'])

    def test_unparsed_and_invalid_measurements_cannot_create_a_warmup_result(self):
        invalid=row(3,float('nan'));missing=row(4,1.);missing['windows']['stratum']=None
        result=root_trend([dict(at=0,windows={}),row(1,7),row(2,3),invalid,missing])
        self.assertFalse(result['consistent_with_filter_warmup'])


class OwnedCleanup(unittest.TestCase):
    def test_cleanly_finished_process_requires_no_stop_or_kill(self):
        process=MagicMock();process.poll.return_value=0
        with patch.object(live.subprocess,'run') as kill:
            self.assertFalse(live.cleanup_owned(process));kill.assert_not_called();process.wait.assert_not_called()

    def test_stop_then_reap_without_force(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(live,'ROOT',Path(folder)):
            process=MagicMock();process.poll.return_value=None;process.wait.return_value=0
            with patch.object(live.subprocess,'run') as kill:
                self.assertFalse(live.cleanup_owned(process));kill.assert_not_called()
            self.assertTrue((Path(folder)/'STOP').exists())

    def test_forced_cleanup_targets_only_owned_live_child_tree(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(live,'ROOT',Path(folder)):
            process=MagicMock();process.pid=12345;process.poll.return_value=None
            process.wait.side_effect=[subprocess.TimeoutExpired('owned',40),0]
            with patch.object(live.os,'name','nt'),patch.object(live.subprocess,'run') as kill:
                self.assertTrue(live.cleanup_owned(process))
                self.assertEqual(kill.call_args.args[0],['taskkill','/PID','12345','/T','/F'])
            self.assertEqual(process.wait.call_count,2)

if __name__=='__main__':unittest.main()
