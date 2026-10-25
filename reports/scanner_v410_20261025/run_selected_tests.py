"""Only launcher and reused admission/observation safety checks; no network."""
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

from reports.scanner_v49_20261025.run_selected_tests import NAMES as OLD

OUT=Path('reports/scanner_v410_20261025')
NAMES=['tests.test_scanner_control_v410',*[n for n in OLD if n!='tests.test_scanner_root_v48.OwnedCleanup']]
SOURCES=['coin_analysis/scanner_control_v410.py','scripts/coin_api_entry.py','scripts/coin_api_python.cmd',
    'start_coin_api.bat','stop_coin_api.bat','status_coin_api.bat','tests/test_scanner_control_v410.py',
    'coin_analysis/forward_scanner_v43.py','coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_ntp_v49.py']

if __name__=='__main__':
    stream=io.StringIO();began=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromNames(NAMES)
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream),\
         patch.object(urllib.request,'urlopen',side_effect=AssertionError('Actual HTTP forbidden in tests')),\
         patch.object(socket,'socket',side_effect=AssertionError('Actual UDP forbidden in tests')):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/'selective_tests.log').write_text(stream.getvalue(),encoding='utf8')
    value=dict(tests_run=result.testsRun,successful=result.wasSuccessful(),failures=len(result.failures),errors=len(result.errors),
        skipped=len(result.skipped),elapsed_seconds=time.monotonic()-began,selected_names=NAMES,
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES},
        scope='Selected only; mock network plus actual offline BAT/CMD/PowerShell/SQLite/Windows locks')
    (OUT/'test_result.json').write_text(json.dumps(value,indent=2),encoding='utf8')
    print(json.dumps(value));raise SystemExit(0 if result.wasSuccessful() else 1)
