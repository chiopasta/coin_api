"""Impact-selected checks, HTTP/UDP forbidden; no unittest discovery."""
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

from reports.scanner_v48_20261025.run_selected_tests import NAMES as PRIOR_NAMES
from reports.scanner_v49_20261025 import live
from tests import test_scanner_root_v48 as cleanup_tests

OUT=Path('reports/scanner_v49_20261025')
NAMES=['tests.test_scanner_ntp_v49','tests.test_scanner_root_v48.OwnedCleanup',
       *[n for n in PRIOR_NAMES if n!='tests.test_scanner_root_v48']]
SOURCES=['coin_analysis/forward_scanner_v43.py','coin_analysis/scanner_clock_v45.py',
    'coin_analysis/scanner_clock_v47.py','coin_analysis/scanner_ntp_v46.py','coin_analysis/scanner_ntp_v49.py',
    'reports/scanner_v49_20261025/live.py','reports/scanner_v49_20261025/analysis.py',
    'tests/test_scanner_ntp_v49.py','tests/test_scanner_root_v48.py']

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromNames(NAMES);stream=io.StringIO();began=time.monotonic()
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream),\
         patch.object(urllib.request,'urlopen',side_effect=AssertionError('Real HTTP forbidden')),\
         patch.object(socket,'socket',side_effect=AssertionError('Real UDP forbidden')),\
         patch.object(cleanup_tests,'live',live):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/'selective_tests.log').write_text(stream.getvalue(),encoding='utf8')
    value=dict(tests_run=result.testsRun,successful=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),
        skipped=len(result.skipped),elapsed_seconds=time.monotonic()-began,selected_names=NAMES,
        tested_source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES},
        cleanup_tests_target='V4.9 controller via explicit module patch',scope='Selected only; real HTTP/UDP forbidden')
    (OUT/'test_result.json').write_text(json.dumps(value,indent=2),encoding='utf8')
    print(json.dumps(value));raise SystemExit(0 if result.wasSuccessful() else 1)
