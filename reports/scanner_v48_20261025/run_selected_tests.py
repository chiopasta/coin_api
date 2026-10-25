"""Narrow V4.8 clock/observation safety checks. Actual network forbidden."""
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

OUT=Path('reports/scanner_v48_20261025')
NAMES=['tests.test_scanner_root_v48','tests.test_scanner_clock_v47','tests.test_scanner_clock_v46',
    'tests.test_forward_scanner_v43',
    'tests.test_scanner_v41.CandleGuards',
    'tests.test_scanner_v41.RuntimeRepairs.test_os_lock_rejects_second_process_without_growing_file',
    'tests.test_forward_scanner_v4.ScannerTests.test_future_mutation_deletion_cannot_change_features_or_cluster_start',
    'tests.test_forward_scanner_v4.ScannerTests.test_signal_pending_restart_and_final_outcome_immutable',
    'tests.test_scanner_observation_v45.Prices.test_pending_60m_endpoint_survives_real_disk_close_reopen',
    'tests.test_forward_scanner_v4_operations.SourceTests.test_abrupt_exit_recovers_committed_wal_then_cleanly_closes']
SOURCES=['coin_analysis/forward_scanner_v43.py','coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_clock_v47.py',
    'coin_analysis/scanner_ntp_v46.py','reports/scanner_v48_20261025/trend.py','reports/scanner_v48_20261025/live.py',
    'reports/scanner_v48_20261025/analysis.py','tests/test_scanner_root_v48.py']


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames(NAMES);stream=io.StringIO();began=time.monotonic()
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream),\
         patch.object(urllib.request,'urlopen',side_effect=AssertionError('Real HTTP forbidden in selected tests')),\
         patch.object(socket,'socket',side_effect=AssertionError('Real UDP forbidden in selected tests')):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/'selective_tests.log').write_text(stream.getvalue(),encoding='utf8')
    payload=dict(tests_run=result.testsRun,successful=result.wasSuccessful(),errors=len(result.errors),failures=len(result.failures),
        skipped=len(result.skipped),elapsed_seconds=time.monotonic()-began,selected_names=NAMES,
        tested_source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES},
        scope='Impact-selected; no full regression/backtest; real HTTP/UDP forbidden')
    (OUT/'test_result.json').write_text(json.dumps(payload,indent=2),encoding='utf8')
    print(json.dumps(payload));raise SystemExit(0 if result.wasSuccessful() else 1)
