"""Offline admission environment and delayed process readiness regressions."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from coin_analysis import scanner_clock_v45 as clock
from coin_analysis import scanner_desktop_v50 as desktop
from tests.scanner_clock_fixtures import WINDOWS_OK
from tests.test_scanner_clock_v52 import measured


class AdmissionEnvironment(unittest.TestCase):
    def test_foreign_working_directory_uses_same_ntp_module_and_ignores_python_environment(self):
        original=Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                replies=[subprocess.CompletedProcess([],0,WINDOWS_OK.encode(),b''),
                         subprocess.CompletedProcess([],0,json.dumps(measured()).encode(),b'')]
                with patch.object(clock.subprocess,'run',side_effect=replies) as run:
                    result=clock.verify_clock()
                self.assertEqual(result['status'],'VERIFIED')
                command=run.call_args_list[1]
                self.assertEqual(command.args[0][1:],['-E','-s','-m','coin_analysis.scanner_ntp_v49'])
                self.assertEqual(command.kwargs['cwd'],clock.PROJECT_ROOT)
                self.assertFalse(result['execution']['cwd_is_project'])
                self.assertTrue(result['execution']['ntp_python_environment_ignored'])
                self.assertEqual([p['valid_samples'] for p in result['provider_summary']],[3,3])
            finally:os.chdir(original)

    def test_child_timeout_has_missing_provider_diagnostics_and_cannot_admit(self):
        with patch.object(clock.subprocess,'run',side_effect=[
            subprocess.CompletedProcess([],0,WINDOWS_OK.encode(),b''),subprocess.TimeoutExpired('ntp',13.25)]):
            result=clock.verify_clock()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['reason'],'CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')
        self.assertTrue(all(p['result']=='REQUIRED_SAMPLES_MISSING' for p in result['provider_summary']))


class Readiness(unittest.TestCase):
    def test_real_identity_readiness_after_old_35_second_limit_is_accepted(self):
        manager=MagicMock(pid=123);manager.poll.return_value=None
        elapsed=[0.]
        def current():
            if elapsed[0]==0:return None
            return dict(launch_id='a'*32,status='RUNNING',phase='OBSERVING' if elapsed[0]>=40 else 'STARTING',
                        manager={},child={})
        with tempfile.TemporaryDirectory() as temp,contextlib.ExitStack() as stack:
            for obj,name,value in [(desktop,'WEB',Path(temp)),(desktop,'spawn',manager),
                                  (desktop.control,'current',current),(desktop.control,'identity',{}),
                                  (desktop.control,'alive',True),(desktop.control,'snapshot',lambda s:s),
                                  (desktop.control,'write_metadata',None)]:
                if name in ('current','snapshot'):mock=patch.object(obj,name,side_effect=value)
                elif name=='WEB':mock=patch.object(obj,name,value)
                else:mock=patch.object(obj,name,return_value=value)
                stack.enter_context(mock)
            stack.enter_context(patch.object(desktop.time,'monotonic',side_effect=lambda:elapsed[0]))
            stack.enter_context(patch.object(desktop.time,'sleep',side_effect=lambda s:elapsed.__setitem__(0,elapsed[0]+s)))
            result=desktop.start_scanner(120,40)
        self.assertEqual(result['phase'],'OBSERVING');self.assertGreaterEqual(elapsed[0],40)


if __name__=='__main__':unittest.main()
