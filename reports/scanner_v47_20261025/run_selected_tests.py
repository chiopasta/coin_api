"""V4.7 impact-selected checks; no real exchange/NTP traffic in tests."""
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

from reports.scanner_v46_20261025.run_selected_tests import NAMES as BASE

OUT=Path('reports/scanner_v47_20261025')
NAMES=['tests.test_scanner_clock_v47',*BASE]
SOURCES=['coin_analysis/forward_scanner_v43.py','coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_clock_v47.py',
    'coin_analysis/scanner_ntp_v46.py','tests/scanner_clock_fixtures.py','tests/test_scanner_clock_v47.py',
    'tests/test_scanner_clock_v46.py','tests/test_scanner_observation_v45.py','tests/test_forward_scanner_v43.py']


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
        scope='Impact-selected only; HTTP/UDP forbidden in test process; no full regression/backtest')
    (OUT/'test_result.json').write_text(json.dumps(payload,indent=2),encoding='utf8')
    print(json.dumps(payload));raise SystemExit(0 if result.wasSuccessful() else 1)
