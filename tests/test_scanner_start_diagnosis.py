"""Actual ledger reader contract and local control exception evidence, offline."""
import http.client
import ctypes
from ctypes import wintypes
import errno
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock,patch

from coin_analysis import scanner_dashboard_v50 as dashboard
from coin_analysis import scanner_desktop_v50 as desktop
from coin_analysis import forward_scanner_v43 as observer
from coin_analysis import scanner_control_v410 as control


class MetadataRead(unittest.TestCase):
    def test_errno_13_without_winerror_retries_then_reads_fresh_state(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';path.write_text('{"version":2}',encoding='utf-8')
            original=Path.open;attempts=[]
            def open_file(p,*args,**kwargs):
                attempts.append(1)
                if len(attempts)<3:raise PermissionError(errno.EACCES,'sharing denied')
                return original(p,*args,**kwargs)
            with patch.object(Path,'open',open_file):self.assertEqual(control.read_json(path),dict(version=2))
            self.assertEqual(len(attempts),3)

    def test_persistent_denial_still_raises_within_half_second_and_has_no_stale_fallback(self):
        elapsed=[0.]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';path.write_text('{}',encoding='utf-8')
            with patch.object(Path,'open',side_effect=PermissionError(errno.EACCES,'persistent denial')),\
                 patch.object(control.time,'monotonic',side_effect=lambda:elapsed[0]),\
                 patch.object(control.time,'sleep',side_effect=lambda s:elapsed.__setitem__(0,elapsed[0]+s)):
                with self.assertRaises(PermissionError):control.read_json(path)
            self.assertGreaterEqual(elapsed[0],.5);self.assertLess(elapsed[0],.52)

    def test_bad_json_oversize_missing_file_and_other_errors_do_not_retry(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(control.time,'sleep') as sleep:
            path=Path(temp)/'state.json';path.write_text('invalid',encoding='utf-8')
            with self.assertRaises(json.JSONDecodeError):control.read_json(path)
            path.write_text(' '*(128*1024+1),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Metadata size'):control.read_json(path)
            with self.assertRaises(FileNotFoundError):control.read_json(Path(temp)/'missing.json')
            small=Path(temp)/'small.json';small.write_text('{}',encoding='utf-8')
            with patch.object(Path,'open',side_effect=PermissionError(errno.EPERM,'other error')):
                with self.assertRaises(PermissionError):control.read_json(small)
            sleep.assert_not_called()

    @unittest.skipUnless(os.name=='nt','Windows sharing semantics')
    def test_real_windows_share_denial_recovers_after_owned_handle_closes(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,
                                    wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';path.write_text('{"version":2}',encoding='utf-8')
            handle=kernel.CreateFileW(str(path),0x80000000,0,None,3,0x80,None)
            self.assertNotEqual(handle,wintypes.HANDLE(-1).value)
            values=[];errors=[];entered=threading.Event()
            def read():
                entered.set()
                try:values.append(control.read_json(path))
                except Exception as exc:errors.append(type(exc).__name__)
            thread=threading.Thread(target=read);thread.start()
            try:
                self.assertTrue(entered.wait(1));time.sleep(.05);self.assertTrue(thread.is_alive())
            finally:kernel.CloseHandle(handle)
            thread.join(2);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
            self.assertEqual(values,[dict(version=2)])


class ConnectionLedger(unittest.TestCase):
    def test_actual_budget_event_schema_drives_connection_and_latest_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);db=observer.ledger(root/'control.db')
            try:
                budget=object.__new__(observer.Budget)
                budget.root=root;budget.path=root/'events.jsonl';budget.control=db
                budget.run=dict(run_id='offline');budget.active_seq=None
                for exchange in observer.v42.HOSTS:
                    budget.event('HTTP_START',exchange=exchange,endpoint='/v1/market/all',params={})
                    budget.event('HTTP_END',exchange=exchange,http_status=200,rows=1)
                self.assertTrue(all(v['status']=='CONNECTED' for v in dashboard.View.connections(root,True).values()))
                budget.event('HTTP_START',exchange='UPBIT',endpoint='/v1/market/all',params={})
                budget.event('HTTP_ERROR',exchange='UPBIT',error='offline failure')
                self.assertEqual(dashboard.View.connections(root,True)['UPBIT']['status'],'ERROR')
                with db:db.execute("UPDATE http_attempts SET details_json='invalid json' WHERE exchange='BITHUMB'")
                self.assertEqual(dashboard.View.connections(root,True)['BITHUMB']['status'],'UNKNOWN')
                self.assertTrue(all(v['status']=='DISCONNECTED' for v in dashboard.View.connections(root,False).values()))
            finally:db.close()


class ControlDiagnostics(unittest.TestCase):
    def test_http_accepted_start_and_helper_error_are_distinct_and_sensitive_message_is_excluded(self):
        logger=MagicMock()
        exc=PermissionError(13,'private credential secret',r'C:\private\secret.file');exc.winerror=32
        with patch.object(dashboard.control,'current',return_value=None),\
             patch.object(dashboard.control,'snapshot',return_value=dict(status='STOPPED',phase='NO_MANAGED_RUN')),\
             patch.object(desktop,'start_scanner',side_effect=exc):
            server=dashboard.Server(('127.0.0.1',0),logger=logger,seconds=120,max_requests=40,engine='V4')
            thread=threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.05));thread.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                conn.request('POST','/api/control/start',body='{}',headers={
                    'Origin':f'http://127.0.0.1:{server.server_port}',
                    'Content-Type':'application/json','X-CSRF-Token':server.csrf})
                response=conn.getresponse();response.read();self.assertEqual(response.status,202);conn.close()
                for worker in server.operations.threads:worker.join(3)
                self.assertEqual(server.operations.status()['state'],'FAILED')
            finally:
                server.operations.close();server.analysis.close();server.shutdown();server.server_close();thread.join(3)
        rows=[json.loads(call.args[0]) for call in logger.info.call_args_list]
        error=next(row for row in rows if row['event']=='CONTROL_EXCEPTION')
        self.assertEqual(error['stage'],'START_HELPER');self.assertEqual(error['error_type'],'PermissionError')
        self.assertEqual(error['winerror'],32);self.assertEqual(error['errno'],13)
        self.assertTrue(any(row['event']=='CONTROL_HTTP_RESPONSE' and row['http_status']==202 for row in rows))
        serialized=json.dumps(rows)
        for value in ('credential','secret.file',server.csrf):self.assertNotIn(value,serialized)

    def test_readiness_timeout_keeps_specific_code_and_stop_request_has_separate_identity(self):
        logger=MagicMock();op=dashboard.Operations(120,40,logger)
        with patch.object(dashboard.control,'current',return_value=None),\
             patch.object(desktop,'start_scanner',side_effect=RuntimeError('SCANNER_START_TIMEOUT')),\
             patch.object(desktop,'stop_scanner',return_value=dict(status='STOPPED')):
            op.request('start');op.threads[0].join(3)
            self.assertIn('SCANNER_START_TIMEOUT',op.result['message'])
            op.request('stop');op.threads[-1].join(3)
        rows=[json.loads(call.args[0]) for call in logger.info.call_args_list]
        failure=next(row for row in rows if row['event']=='CONTROL_EXCEPTION')
        stop=next(row for row in rows if row['event']=='CONTROL_REQUEST' and row['action']=='stop')
        self.assertEqual(failure['code'],'SCANNER_START_TIMEOUT')
        self.assertNotEqual(failure['operation_id'],stop['operation_id'])
        self.assertEqual(op.result['state'],'SUCCEEDED')


if __name__=='__main__':unittest.main()
