"""Offline suite guard: never launch the production V15 child during tests."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

def audit(event,args):
    if event=='subprocess.Popen':
        argv=args[1]
        if 'coin_analysis.v15_runtime' in argv:
            raise RuntimeError('Production V15 subprocess forbidden in offline suite; mock its lifecycle')

sys.addaudithook(audit)
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
result=unittest.TextTestRunner(verbosity=1).run(suite)
out=Path(__file__).resolve().parent
(out/'all_tests.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),
    errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful(),
    production_v15_process_creation_guard=True),indent=2),encoding='utf-8')
raise SystemExit(0 if result.wasSuccessful() else 1)
