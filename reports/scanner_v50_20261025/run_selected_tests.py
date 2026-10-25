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

from reports.scanner_v410_20261025.run_selected_tests import NAMES as OLD

OUT=Path('reports/scanner_v50_20261025')
NAMES=OLD
WEB_NAMES=['tests.test_scanner_dashboard_v50']
SOURCES=['coin_analysis/scanner_dashboard_v50.py','coin_analysis/scanner_desktop_v50.py',
    'tests/test_scanner_dashboard_v50.py',*[str(p) for p in Path('coin_analysis/dashboard_assets').iterdir()],
    'coin_analysis/scanner_control_v410.py','scripts/coin_api_entry.py','scripts/coin_api_python.cmd',
    'start_coin_api.bat','stop_coin_api.bat','status_coin_api.bat','tests/test_scanner_control_v410.py',
    'coin_analysis/forward_scanner_v43.py','coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_ntp_v49.py']

if __name__=='__main__':
    stream=io.StringIO();began=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromNames(NAMES)
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream),\
         patch.object(urllib.request,'urlopen',side_effect=AssertionError('Actual HTTP forbidden in tests')),\
         patch.object(socket,'socket',side_effect=AssertionError('Actual UDP forbidden in tests')):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    web_suite=unittest.defaultTestLoader.loadTestsFromNames(WEB_NAMES)
    with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        web_result=unittest.TextTestRunner(stream=stream,verbosity=2).run(web_suite)
    (OUT/'selective_tests.log').write_text(stream.getvalue(),encoding='utf8')
    value=dict(tests_run=result.testsRun+web_result.testsRun,successful=result.wasSuccessful() and web_result.wasSuccessful(),failures=len(result.failures)+len(web_result.failures),errors=len(result.errors)+len(web_result.errors),
        skipped=len(result.skipped),elapsed_seconds=time.monotonic()-began,selected_names=NAMES+WEB_NAMES,
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES},
        scope='Selected launcher/admission/DB safety plus isolated dashboard fixtures and loopback HTTP; no full regression or actual exchange/NTP in tests')
    (OUT/'test_result.json').write_text(json.dumps(value,indent=2),encoding='utf8')
    print(json.dumps(value));raise SystemExit(0 if value['successful'] else 1)
