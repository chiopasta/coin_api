"""Impact-selected tests only. No full discovery, backtest or live network."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import time
import unittest

OUT=Path('reports/scanner_v45_20261025')
NAMES=[
    'tests.test_scanner_observation_v45',
    'tests.test_forward_scanner_v43',
    'tests.test_scanner_gap_audit_v44',
    'tests.test_scanner_v41.CandleGuards',
    'tests.test_scanner_v41.RuntimeRepairs.test_network_retry_resume_and_duplicate_skip',
    'tests.test_scanner_v41.RuntimeRepairs.test_os_lock_rejects_second_process_without_growing_file',
    'tests.test_forward_scanner_v4.ScannerTests.test_future_mutation_deletion_cannot_change_features_or_cluster_start',
    'tests.test_forward_scanner_v4.ScannerTests.test_signal_pending_restart_and_final_outcome_immutable',
    'tests.test_forward_scanner_v4.ScannerTests.test_missing_future_is_unknown_and_recoverable',
    'tests.test_forward_scanner_v4_operations.SourceTests.test_restart_session_and_interrupted_cycle',
    'tests.test_forward_scanner_v4_operations.SourceTests.test_clean_close_checkpoints_wal_and_preserves_values',
    'tests.test_forward_scanner_v4_operations.SourceTests.test_abrupt_exit_recovers_committed_wal_then_cleanly_closes',
    'tests.test_research_dataset_collector_v1.CollectorTests.test_retry_backoff_and_exhaustion',
    'tests.test_research_dataset_collector_v1.CollectorTests.test_remaining_req_and_418',
]


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames(NAMES);stream=io.StringIO();began=time.monotonic()
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/'selective_tests.log').write_text(stream.getvalue(),encoding='utf8')
    evidence=dict(tests_run=result.testsRun,successful=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),
        skipped=len(result.skipped),seconds=time.monotonic()-began,selected_names=NAMES,
        tested_source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            Path('coin_analysis/forward_scanner_v43.py'),Path('coin_analysis/scanner_clock_v45.py'),
            Path('coin_analysis/scanner_observation_v45.py'),Path('tests/test_scanner_observation_v45.py'),
            Path('tests/test_forward_scanner_v43.py')]},
        scope='Impact-selected only; no unittest discover, full regression, backtest or real exchange API')
    (OUT/'test_result.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')
    print(json.dumps(evidence));raise SystemExit(0 if result.wasSuccessful() else 1)
