import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from coin_analysis import scanner_control_v410 as c


class Control(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.control=self.base/'management';self.runtime=self.base/'runtime'
        for obj,name,value in [(c,'CONTROL',self.control),(c.observer,'RUNTIME_ROOT',self.runtime),
                               (c.observer.v42,'RUNTIME_ROOT',self.base/'locks')]:
            p=patch.object(obj,name,value);p.start();self.addCleanup(p.stop)
        self.output=io.StringIO();p=contextlib.redirect_stdout(self.output);p.__enter__();self.addCleanup(p.__exit__,None,None,None)

    def state(self,phase='OBSERVING'):
        token='a'*32;root=self.runtime/('console_'+token)
        (self.control/'launches'/token).mkdir(parents=True)
        state=dict(launch_id=token,root=str(root),manager=c.identity(os.getpid()),child=None,
            status='RUNNING',phase=phase,started_at=time.time(),elapsed_monotonic_seconds=5.,db_saved='UNKNOWN')
        c.persist(state);c.observer.write_json(self.control/'current.json',dict(launch_id=token))
        return state,root

    def databases(self,root):
        root.mkdir(parents=True)
        cfg=dict(markets=c.observer.MARKETS,signal_start=86400)
        for exchange in c.observer.v42.HOSTS:
            db=c.observer.open_runtime(root,cfg,exchange)
            with db:
                db.execute("INSERT INTO minute_candles VALUES('KRW-ETH',65040,1,1,1,1,1)")
                db.execute("INSERT INTO candle_receipts VALUES('KRW-ETH',65040,102)")
            c.observer.ops.close_cleanly(db)

    def final_files(self,root,forced=False):
        (root/'runs').mkdir()
        c.observer.write_json(root/'runs'/'one.summary.json',dict(run_id='one',close_errors={},status='STOPPED',reason='STOP_REQUESTED',requests=1))
        c.observer.write_json(root/'runs'/'one.exit.json',dict(worker_reaped=True,forced_kill=forced,worker_returncode=0))

    def test_clock_failure_preserves_blocker_and_never_creates_dataset_or_child(self):
        blocked=dict(status='BLOCKED',reason='CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE',at=time.time(),completed_at=time.time())
        with patch.object(c.observer.clock_guard,'verify_clock',return_value=blocked),patch.object(c.subprocess,'Popen') as child:
            self.assertEqual(c.start(120,80),2);child.assert_not_called()
        state=c.current();self.assertEqual(state['status'],'BLOCKED')
        self.assertFalse(c.owned_root(state).exists());self.assertIn('CLOCK_REFERENCE',self.output.getvalue())

    def test_stop_during_precheck_cancels_before_live(self):
        def verify():
            c.stop_marker(c.current()).touch()
            return dict(status='VERIFIED',at=time.time(),completed_at=time.time())
        with patch.object(c.observer.clock_guard,'verify_clock',side_effect=verify),patch.object(c.subprocess,'Popen') as child:
            self.assertEqual(c.start(120,80),0);child.assert_not_called()
        self.assertEqual(c.current()['reason'],'CANCELLED_BEFORE_LIVE')

    def test_delayed_web_start_cancellation_cannot_start_live_or_probe_clock(self):
        token='a'*32;self.control.mkdir();(self.control/('CANCEL_'+token)).touch()
        with patch.object(c.observer.clock_guard,'verify_clock') as clock,patch.object(c.subprocess,'Popen') as child:
            with self.assertRaisesRegex(RuntimeError,'START_CANCELLED'):c.start(120,80,token)
            clock.assert_not_called();child.assert_not_called()
        self.assertFalse(self.runtime.exists())

    def test_actual_manager_lock_blocks_duplicate_before_clock_probe(self):
        with c.observer.scanner.exclusive(self.control/'manager'),patch.object(c.observer.clock_guard,'verify_clock') as clock:
            with self.assertRaisesRegex(RuntimeError,'Another scanner'):c.start(120,80)
            clock.assert_not_called()

    def test_existing_observer_lock_blocks_new_launcher(self):
        with c.observer.scanner.exclusive(c.observer.v42.RUNTIME_ROOT/'observer'),patch.object(c.observer.clock_guard,'verify_clock') as clock:
            self.assertEqual(c.start(120,80),2);clock.assert_not_called()

    def test_pid_reuse_cannot_report_running_or_write_stop(self):
        state,root=self.state();state['manager']=dict(pid=1234,birth=1);c.persist(state)
        with patch.object(c,'process_birth',return_value=2):
            self.assertEqual(c.snapshot()['status'],'BLOCKED');self.assertEqual(c.stop(wait=0),0)
        self.assertFalse(c.stop_marker(state).exists());self.assertFalse(root.exists())

    def test_other_paths_and_bad_pointer_never_receive_stop(self):
        state,root=self.state();state['root']=str(self.base/'original');c.persist(state)
        with self.assertRaisesRegex(ValueError,'path rejected'):c.stop(wait=0)
        self.assertFalse((self.base/'original'/'STOP').exists())

    def test_actual_db_counts_receipts_zero_signals_and_unknown_no_signal_time(self):
        state,root=self.state();self.databases(root)
        view=c.snapshot();self.assertEqual(view['signals'],0);self.assertIsNone(view['last_signal'])
        self.assertEqual(view['collected'],102);self.assertEqual(view['markets'],5)
        self.assertGreater(view['size'],0);self.assertIn('zero is a normal',' '.join(view['warnings']))
        path=root/'upbit.db'
        db=c.observer.scanner.connect(path)
        with db:db.execute("INSERT INTO signals VALUES('fixture','KRW-ETH',86400,1,4,'cluster',86500,100,'LIVE')")
        c.observer.ops.close_cleanly(db)
        view=c.snapshot();self.assertEqual(view['signals'],1);self.assertEqual(view['last_signal'],86500)
        self.assertEqual(view['venue_pairs'],10);self.assertEqual(view['signal_pairs'],8)
        db=c.observer.scanner.connect(path)
        with db:db.execute("DELETE FROM scanner_state WHERE market='KRW-FLOCK'")
        c.observer.ops.close_cleanly(db)
        view=c.snapshot();self.assertEqual(view['venue_pairs'],9);self.assertEqual(view['signal_pairs'],7)

    def test_no_data_is_unknown_and_stale_pass_is_not_current_pass(self):
        state,root=self.state()
        view=c.snapshot();self.assertIsNone(view['signals']);self.assertIsNone(view['size'])
        self.assertEqual(c.clock_view(dict(status='VERIFIED',completed_at=time.time()-616),time.time()),'UNKNOWN (last PASS is stale)')
        self.assertEqual(c.clock_view(None,time.time()),'UNKNOWN')

    def test_precheck_duration_advances_without_using_wall_time(self):
        state,root=self.state('PRECHECK');state['started_monotonic']=time.monotonic()-6
        state['elapsed_monotonic_seconds']=0;c.persist(state)
        self.assertGreaterEqual(c.snapshot()['elapsed_monotonic_seconds'],6)

    def test_normal_close_is_saved_and_force_flag_is_never_saved(self):
        state,root=self.state();self.databases(root);self.final_files(root)
        self.assertTrue(c.saved_result(root)['ok'])
        path=root/'runs'/'one.exit.json';v=c.read_json(path);v['forced_kill']=True;c.observer.write_json(path,v)
        self.assertFalse(c.saved_result(root)['ok'])

    def test_stop_is_only_a_scoped_event_and_waits_for_final_save(self):
        state,root=self.state();self.databases(root);self.final_files(root)
        def finish():
            until=time.monotonic()+3
            while not (root/'STOP').exists() and time.monotonic()<until:time.sleep(.02)
            final=c.saved_result(root)
            state.update(status='STOPPED',phase='TERMINAL',db_saved=final['db_saved']);c.persist(state)
        thread=threading.Thread(target=finish);thread.start()
        self.assertEqual(c.stop(wait=4),0);thread.join(timeout=1)
        self.assertTrue((root/'STOP').exists());self.assertIsNotNone(c.process_birth(os.getpid()))

    def test_storage_limit_and_invalid_caps_block_without_network(self):
        with patch.object(c,'MAX_CONTROL_BYTES',0),patch.object(c.observer.clock_guard,'verify_clock') as clock:
            self.assertEqual(c.start(120,80),2);clock.assert_not_called()
        with self.assertRaises(ValueError):c.start(86401,80)


class BatEntry(unittest.TestCase):
    def test_cmd_and_powershell_work_in_korean_space_punctuation_path_without_live(self):
        project=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'한글 경로 & 괄호 (검증)!';root.mkdir()
            shutil.copytree(project/'coin_analysis',root/'coin_analysis',ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(project/'scripts',root/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
            (root/'archive').mkdir()
            shutil.copy2(project/'archive/scanner_v15.py',root/'archive/scanner_v15.py')
            from tests.test_v15_dashboard_integration import init_db
            init_db(root/'archive/crypto_scanner.db')
            for p in project.glob('*_coin_api.bat'):shutil.copy2(p,root/p.name)
            env=dict(os.environ,COIN_API_NO_PAUSE='1',COIN_API_PYTHON=sys.executable)
            for command in (['cmd','/d','/c','call',str(root/'start_coin_api.bat'),'--check'],
                            ['powershell','-NoProfile','-Command',"& '"+str(root/'start_coin_api.bat')+"' --check"],
                            ['cmd','/d','/c','call',str(root/'status_coin_api.bat')],
                            ['cmd','/d','/c','call',str(root/'stop_coin_api.bat')]):
                result=subprocess.run(command,cwd=temporary,env=env,capture_output=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stdout.decode('utf8',errors='replace')+result.stderr.decode('utf8',errors='replace'))
            self.assertFalse((root/'data'/'scanner_v43_live').exists())
            env['COIN_API_PYTHON']=str(root/'missing python.exe')
            result=subprocess.run(['cmd','/d','/c','call',str(root/'start_coin_api.bat')],env=env,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,2);self.assertIn(b'BLOCKED',result.stdout)

    def test_real_old_python_is_rejected_before_entry(self):
        old=Path('C:/Python34/python.exe')
        if not old.exists():self.skipTest('Old Python not installed on this host')
        project=Path(__file__).resolve().parent.parent
        result=subprocess.run(['cmd','/d','/c','call',str(project/'start_coin_api.bat'),'--check'],
            env=dict(os.environ,COIN_API_NO_PAUSE='1',COIN_API_PYTHON=str(old)),capture_output=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertIn(b'older than 3.11',result.stdout)

    def test_error_window_waits_for_key_unless_no_pause_is_explicit(self):
        project=Path(__file__).resolve().parent.parent
        env=dict(os.environ,COIN_API_PYTHON=str(project/'missing_python.exe'));env.pop('COIN_API_NO_PAUSE',None)
        process=subprocess.Popen(['cmd','/d','/c','call',str(project/'start_coin_api.bat')],
            env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        time.sleep(.5)
        self.assertIsNone(process.poll(),'Error console closed before pause input')
        stdout,stderr=process.communicate(b'\r\n',timeout=5)
        self.assertEqual(process.returncode,2);self.assertIn(b'BLOCKED',stdout)


if __name__=='__main__':unittest.main()
