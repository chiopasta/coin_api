"""Impact-selected V4.6 suite; real network forbidden in this process."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import socket
import time
import unittest
from unittest.mock import patch
import urllib.request

OUT=Path('reports/scanner_v46_20261025')
NAMES=[
    'tests.test_scanner_clock_v46',
    'tests.test_scanner_observation_v45',
    'tests.test_forward_scanner_v43',
    'tests.test_scanner_v41.CandleGuards',
    'tests.test_scanner_v41.RuntimeRepairs.test_network_retry_resume_and_duplicate_skip',
    'tests.test_scanner_v41.RuntimeRepairs.test_os_lock_rejects_second_process_without_growing_file',
    'tests.test_forward_scanner_v4.ScannerTests.test_future_mutation_deletion_cannot_change_features_or_cluster_start',
    'tests.test_forward_scanner_v4.ScannerTests.test_signal_pending_restart_and_final_outcome_immutable',
    'tests.test_forward_scanner_v4.ScannerTests.test_missing_future_is_unknown_and_recoverable',
    'tests.test_forward_scanner_v4_operations.SourceTests.test_restart_session_and_interrupted_cycle',
    'tests.test_forward_scanner_v4_operations.SourceTests.test_clean_close_checkpoints_wal_and_preserves_values',
    'tests.test_forward_scanner_v4_operations.SourceTests.test_abrupt_exit_recovers_committed_wal_then_cleanly_closes',
]
SOURCES=['coin_analysis/forward_scanner_v43.py','coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_ntp_v46.py',
    'tests/test_scanner_clock_v46.py','tests/test_scanner_observation_v45.py','tests/test_forward_scanner_v43.py']


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames(NAMES);stream=io.StringIO();began=time.monotonic()
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream),\
         patch.object(urllib.request,'urlopen',side_effect=AssertionError('Real HTTP forbidden in selected tests')),\
         patch.object(socket,'socket',side_effect=AssertionError('Real UDP forbidden in selected tests')):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/'selective_tests.log').write_text(stream.getvalue(),encoding='utf8')
    evidence=dict(tests_run=result.testsRun,successful=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),
        skipped=len(result.skipped),seconds=time.monotonic()-began,selected_names=NAMES,
        tested_source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES},
        scope='Impact-selected; real HTTP/UDP forbidden. No full regression or backtest.')
    (OUT/'test_result.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
    print(json.dumps(evidence));raise SystemExit(0 if result.wasSuccessful() else 1)
