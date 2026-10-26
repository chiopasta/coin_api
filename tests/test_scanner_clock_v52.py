"""Clock cross-check policy and local API regressions, without live I/O."""
import http.client
import json
import subprocess
import threading
import time
import unittest
from unittest.mock import patch

from coin_analysis import scanner_clock_v45 as clock
from coin_analysis import scanner_clock_v47 as admission
from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_dashboard_v50 as dashboard
from coin_analysis import scanner_desktop_v50 as desktop
from tests.scanner_clock_fixtures import WINDOWS_OK, WINDOWS_KO
from tests.test_scanner_clock_v46 import measurement, fixture


def measured(offset=.003,uncertainty=.02):
    result=measurement([offset]*6,uncertainty)
    for row in result['rows']:
        row['peer']=['192.0.2.1' if row['host']==clock.ntp.HOSTS[0] else '192.0.2.2',123]
    return result


class Crosscheck(unittest.TestCase):
    def check(self,text=None,values=None,code=0,timeout=False):
        text=text if text is not None else WINDOWS_OK.replace('0.010s','7.767s')
        values=measured() if values is None else values
        replies=[subprocess.CompletedProcess([],code,text.encode('utf8'),b''),
                 subprocess.TimeoutExpired('ntp',12) if timeout else
                 subprocess.CompletedProcess([],0,json.dumps(values).encode('utf8'),b'')]
        with patch.object(clock.os,'name','nt'),patch.object(clock.subprocess,'run',side_effect=replies):
            return clock.verify_clock()

    def test_reproduced_root_failure_is_not_actual_phase_error_and_new_evidence_can_admit(self):
        for text in [WINDOWS_OK,WINDOWS_KO]:
            text=text.replace('0.010s','7.767s')
            pure=admission.windows_status(text)
            self.assertEqual(pure['reason'],'CLOCK_WINDOWS_ROOT_UNCERTAINTY')
            self.assertAlmostEqual(pure['root_distance_seconds'],7.777)
            result=self.check(text)
            self.assertEqual(result['status'],'VERIFIED')
            self.assertEqual(result['windows_status']['reason'],'CLOCK_WINDOWS_ROOT_UNCERTAINTY')
            self.assertEqual(result['warnings'],['CLOCK_WINDOWS_ROOT_UNCERTAINTY'])
            self.assertAlmostEqual(result['root_crosscheck']['max_abs_offset_plus_uncertainty_seconds'],.023)

    def test_reported_cloudflare_source_and_stratum_four_are_supported(self):
        text=WINDOWS_OK.replace('time.google.com','time.cloudflare.com').replace('Stratum: 2','Stratum: 4')
        self.assertEqual(self.check(text.replace('0.010s','7.767s'))['status'],'VERIFIED')

    def test_original_healthy_low_root_path_still_passes(self):
        result=self.check(WINDOWS_OK)
        self.assertEqual(result['status'],'VERIFIED');self.assertNotIn('root_crosscheck',result)

    def test_real_offset_plus_uncertainty_boundary_is_not_relaxed(self):
        self.assertEqual(self.check(values=measured(.98,.02))['status'],'VERIFIED')
        for offset in [1.01,-1.01,.981,-.981]:
            result=self.check(values=measured(offset,.02))
            self.assertEqual(result['status'],'BLOCKED')
            self.assertIn('CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY',result['blockers'])

    def test_uncertainty_alone_jitter_and_provider_disagreement_block(self):
        values=[measured(.003,1.01),measured(),measured()]
        for i,row in enumerate(values[1]['rows']):
            x=-.3 if i%2==0 else .3
            row.update(offset_seconds=x,error_interval_seconds=[x-.02,x+.02])
        for i,row in enumerate(values[2]['rows']):
            x=0 if i%2==0 else .2
            row.update(offset_seconds=x,error_interval_seconds=[x-.02,x+.02])
        for value in values:self.assertEqual(self.check(values=value)['status'],'BLOCKED')

    def test_windows_service_leap_error_stale_and_parse_fail_cannot_be_overridden(self):
        texts=[WINDOWS_OK.replace('Indicator: 0','Indicator: 3'),
               WINDOWS_OK.replace('Stratum: 2','Stratum: 16'),
               WINDOWS_OK.replace('Sync Error: 0','Sync Error: 5'),
               WINDOWS_OK.replace('120.0s','3600.001s'),
               WINDOWS_OK.replace('0.010s','10ms')]
        for text in texts:
            with self.subTest(text=text):self.assertEqual(self.check(text)['status'],'BLOCKED')
        self.assertEqual(self.check(code=1)['status'],'BLOCKED')
        stale=WINDOWS_OK.replace('0.010s','7.767s').replace('120.0s','3600.001s')
        self.assertEqual(self.check(stale)['reason'],'CLOCK_WINDOWS_SYNC_STALE')

    def test_non_ntp_windows_source_and_excess_delay_remain_blocked(self):
        high=WINDOWS_OK.replace('0.010s','7.767s')
        for source in ['Local CMOS Clock','Free-running System Clock','localhost','127.0.0.1']:
            self.assertEqual(self.check(high.replace('time.google.com,0x8',source))['status'],'BLOCKED')
            self.assertEqual(self.check(WINDOWS_OK.replace('time.google.com,0x8',source))['status'],'BLOCKED')
        self.assertEqual(self.check(high.replace('0.020s','2.020s'))['status'],'BLOCKED')

    def test_missing_shared_malformed_or_local_peers_cannot_crosscheck(self):
        cases=[]
        v=measured();del v['rows'][0]['peer'];cases.append(v)
        for peer in [['192.0.2.1',123],['127.0.0.1',123],['192.0.2.3',80],['not-an-ip',123]]:
            v=measured()
            for row in v['rows']:row['peer']=peer
            cases.append(v)
        for value in cases:
            result=self.check(values=value)
            self.assertEqual(result['status'],'BLOCKED')
            self.assertIn('CLOCK_REFERENCE_INDEPENDENCE_UNVERIFIED',result['blockers'])

    def test_missing_failing_invalid_and_single_provider_samples_block(self):
        values=[]
        v=measured();v['rows'].pop();values.append(v)
        for status in ['UNAVAILABLE','INVALID','NOT_ATTEMPTED']:
            v=measured();v['rows'][0]['status']=status;values.append(v)
        v=measured()
        for row in v['rows']:row['host']=clock.ntp.HOSTS[0]
        values.append(v)
        for value in values:self.assertEqual(self.check(values=value)['status'],'BLOCKED')
        self.assertEqual(self.check(timeout=True)['status'],'BLOCKED')

    def test_stale_future_and_inverted_direct_samples_are_blocked(self):
        for mode in ['stale','future','inverted']:
            v=measured()
            if mode=='stale':
                for row in v['rows']:
                    row['local_sent_at']-=30;row['local_received_at']-=30
            elif mode=='future':v['rows'][0]['local_received_at']+=2
            else:v['rows'][0]['local_sent_at']+=2
            self.assertEqual(self.check(values=v)['status'],'BLOCKED')

    def test_a_previous_pass_is_not_cached_for_next_verification(self):
        self.assertEqual(self.check()['status'],'VERIFIED')
        self.assertEqual(self.check(timeout=True)['reason'],'CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')

    def test_packet_fixed_point_values_are_seconds_without_millisecond_or_variance_conversion(self):
        row=clock.ntp.decode_reply(*fixture(.002))
        self.assertAlmostEqual(row['offset_seconds'],.002,places=5)
        self.assertAlmostEqual(row['root_delay_seconds'],.02,places=4)
        self.assertAlmostEqual(row['root_dispersion_seconds'],.002,places=4)
        self.assertGreater(row['uncertainty_seconds'],.03)
        self.assertLess(row['uncertainty_seconds'],.04)

    def test_crosschecked_pass_is_labelled_and_still_expires(self):
        result=self.check()
        self.assertIn('Windows root quality warning',control.clock_view(result,result['completed_at']))
        self.assertIn('UNKNOWN',control.clock_view(result,result['completed_at']+616))


class LocalAPI(unittest.TestCase):
    def test_start_api_and_snapshot_report_the_actual_clock_blocker(self):
        failed=dict(status='BLOCKED',phase='TERMINAL',reason='CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY',
                    clock='FAIL: CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY')
        with patch.object(control,'current',return_value=None),patch.object(control,'snapshot',return_value=failed),\
             patch.object(dashboard,'catalog',return_value={}),\
             patch.object(desktop,'start_scanner',return_value=failed):
            server=dashboard.Server(('127.0.0.1',0),seconds=60,max_requests=26)
            worker=threading.Thread(target=server.serve_forever,kwargs=dict(poll_interval=.02));worker.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                conn.request('POST','/api/control/start',body='{}',headers={
                    'Origin':f'http://127.0.0.1:{server.server_port}',
                    'Content-Type':'application/json','X-CSRF-Token':server.csrf})
                response=conn.getresponse();response.read();self.assertEqual(response.status,202);conn.close()
                for thread in server.operations.threads:thread.join(3)
                state=server.operations.status()
                self.assertEqual(state['state'],'FAILED')
                self.assertIn('1초',state['message'])
                self.assertIn('CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY',state['message'])
                self.assertEqual(server.view.snapshot()['scanner']['reason'],failed['reason'])
                self.assertIn('불확실성',dashboard.control_message('CLOCK_WINDOWS_ROOT_UNCERTAINTY'))
                self.assertIn('필수 두 제공자',dashboard.control_message('CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE'))
            finally:
                server.operations.close();server.shutdown();server.server_close();worker.join(3)


if __name__=='__main__':unittest.main()
