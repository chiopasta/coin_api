import copy
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from coin_analysis import scanner_ntp_v46 as n
from coin_analysis import scanner_clock_v45 as c
from coin_analysis import forward_scanner_v43 as v
from tests.scanner_clock_fixtures import WINDOWS_OK


def fixture(offset=.2):
    t1=1_790_000_000.;origin=n.encode_stamp(t1);packet=bytearray(48)
    packet[0]=0x24;packet[1]=2;packet[3]=(-20)&255
    packet[4:8]=struct.pack('!i',int(.02*65536));packet[8:12]=struct.pack('!I',int(.002*65536))
    packet[16:24]=n.encode_stamp(t1-30)
    packet[24:32]=origin;packet[32:40]=n.encode_stamp(t1+offset+.02)
    packet[40:48]=n.encode_stamp(t1+offset+.021)
    return packet,origin,t1,t1+.041,.041


def measurement(offsets=None,uncertainty=.02):
    offsets=[.01]*6 if offsets is None else offsets
    now=time.time()
    return dict(rows=[dict(host=n.HOSTS[i%2],status='MEASURED',offset_seconds=x,
        uncertainty_seconds=uncertainty,error_interval_seconds=[x-uncertainty,x+uncertainty],
        local_sent_at=now-.02,local_received_at=now-.01) for i,x in enumerate(offsets)])


class NtpProtocol(unittest.TestCase):
    def test_four_timestamp_offset_delay_and_conservative_uncertainty(self):
        r=n.decode_reply(*fixture())
        self.assertAlmostEqual(r['offset_seconds'],.2,places=5)
        self.assertAlmostEqual(r['delay_seconds'],.04,places=5)
        self.assertGreater(r['uncertainty_seconds'],.032)
        self.assertAlmostEqual(n.decode_stamp(n.encode_stamp(1_790_000_000.25)),1_790_000_000.25)

    def test_origin_mode_version_leap_kiss_length_and_reference_age_rejected(self):
        for field,value in [(0,0xe4),(0,0x23),(0,0x14),(1,0),(1,16)]:
            args=list(fixture());args[0][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):n.decode_reply(*args)
        for start,end,replacement in [(24,32,b'badstamp'),(16,24,b'\0'*8),(16,24,n.encode_stamp(1_790_000_000-7200)),(32,40,n.encode_stamp(1_790_000_010))]:
            args=list(fixture());args[0][start:end]=replacement
            with self.subTest(start=start),self.assertRaises(ValueError):n.decode_reply(*args)
        args=list(fixture());args[0]=args[0][:-1]
        with self.assertRaises(ValueError):n.decode_reply(*args)

    def test_wall_clock_jump_during_ntp_measurement_rejected(self):
        args=list(fixture());args[3]+=2
        with self.assertRaisesRegex(ValueError,'LOCAL_CLOCK_CHANGED'):n.decode_reply(*args)

    def test_uncertainty_inside_original_one_second_limit_and_reference_agreement(self):
        self.assertEqual(n.assess(measurement())['status'],'VERIFIED')
        self.assertEqual(n.assess(measurement([.99]*6))['reason'],'CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY')
        self.assertEqual(n.assess(measurement([0.,.2]*3))['reason'],'CLOCK_REFERENCE_DISAGREEMENT')
        self.assertEqual(n.assess(measurement([-.3,.3]*3))['reason'],'CLOCK_REFERENCE_OFFSET_OR_JITTER')
        self.assertEqual(n.assess(measurement([4.38]*6))['status'],'BLOCKED')

    def test_missing_malformed_negative_or_nonfinite_evidence_fails_closed(self):
        cases=[{},[],dict(rows='invalid'),measurement([.01]*5)]
        for bad in [float('nan'),float('inf'),-1,'bad']:
            r=measurement();r['rows'][0]['uncertainty_seconds']=bad;cases.append(r)
        r=measurement();del r['rows'][0]['offset_seconds'];cases.append(r)
        for r in cases:
            with self.subTest(r=r):self.assertEqual(n.assess(r)['status'],'BLOCKED')

    def test_packet_scope_is_fixed_six_with_no_retry(self):
        with patch.object(n,'sample',side_effect=lambda h:dict(host=h,status='UNAVAILABLE')),patch.object(n.time,'sleep'):
            r=n.probe()
        self.assertEqual([x['host'] for x in r['rows']],list(n.HOSTS)*3)
        self.assertEqual(len(r['rows']),6)

    def test_udp_timeout_is_unavailable_without_retry(self):
        with patch.object(n.socket,'socket',side_effect=TimeoutError('offline')) as socket:
            self.assertEqual(n.sample(n.HOSTS[0])['status'],'UNAVAILABLE')
        self.assertEqual(socket.call_count,1)


class Admission(unittest.TestCase):
    def result(self,value,code=0):
        raw=value.encode() if isinstance(value,str) else json.dumps(value).encode()
        return subprocess.CompletedProcess([],code,raw,b'')

    def test_large_realistic_error_exposes_service_and_measurement_blockers(self):
        with patch.object(c.os,'name','nt'),patch.object(c.subprocess,'run',side_effect=[self.result('service off',1),self.result(measurement([4.38]*6))]):
            r=c.verify_clock()
        self.assertEqual(r['status'],'BLOCKED')
        self.assertEqual(r['blockers'],['CLOCK_WINDOWS_TIME_SERVICE_UNVERIFIED','CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY'])
        self.assertEqual(len(r['measurement']['rows']),6)

    def test_child_dns_or_process_timeout_is_bounded_and_cannot_admit(self):
        with patch.object(c.os,'name','nt'),patch.object(c.subprocess,'run',side_effect=[self.result('ok'),subprocess.TimeoutExpired('probe',12)]) as run:
            self.assertEqual(c.verify_clock()['reason'],'CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')
        self.assertGreater(run.call_args.kwargs['timeout'],0)
        self.assertLessEqual(run.call_args.kwargs['timeout'],13.25)

    def test_localized_service_output_decodes_and_success_needs_actual_evidence(self):
        self.assertEqual(c.decode_output('서비스가 시작되지 않았습니다'.encode('cp949')),'서비스가 시작되지 않았습니다')
        with patch.object(c.os,'name','nt'),patch.object(c.subprocess,'run',side_effect=[self.result(WINDOWS_OK),self.result(measurement())]):
            self.assertEqual(c.verify_clock()['status'],'VERIFIED')

    def test_unbiased_windows_clock_is_available_and_non_decreasing(self):
        first=c.awake_seconds();second=c.awake_seconds()
        self.assertIsNotNone(first);self.assertGreaterEqual(second,first)


class ResumeGuards(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.addCleanup(self.temp.cleanup)
        self.control=v.ledger(self.root/'control.db');self.addCleanup(self.control.close)
        now=time.time()
        self.b=v.Budget(self.root,{},dict(run_id='test',created_at=now,duration_seconds=600,deadline=now+600,max_requests=26),self.control)
        self.b.clock_verified_at=time.monotonic()

    def test_sleep_resume_revalidates_before_network_even_if_wall_and_monotonic_agree(self):
        mono,wall=self.b.clock_anchor
        self.b.last_awake_seconds=100.
        with patch.object(v.time,'time',return_value=wall+3),patch.object(v.time,'monotonic',return_value=mono+3),\
             patch.object(c,'awake_seconds',return_value=100.1),patch.object(c,'verify_clock',return_value=dict(status='BLOCKED',reason='CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY')) as verify,\
             patch.object(v.v42.urllib.request,'urlopen') as network:
            with self.assertRaisesRegex(v.Stop,'CLOCK_REFERENCE_OFFSET'):self.b.request('UPBIT','/v1/market/all',{})
            verify.assert_called_once();network.assert_not_called()

    def test_long_check_gap_requires_new_reference(self):
        mono,wall=self.b.clock_anchor;self.b.last_awake_seconds=100.
        with patch.object(v.time,'time',return_value=wall+20),patch.object(v.time,'monotonic',return_value=mono+20),patch.object(c,'awake_seconds',return_value=120.),\
             patch.object(c,'verify_clock',return_value=dict(status='VERIFIED',reason='fixture')) as verify:
            self.b.check();verify.assert_called_once()

    def test_unavailable_suspend_monitor_blocks_http(self):
        with patch.object(c,'awake_seconds',return_value=None),patch.object(v.v42.urllib.request,'urlopen') as network:
            with self.assertRaisesRegex(v.Stop,'CLOCK_SUSPEND_MONITOR_UNAVAILABLE'):self.b.request('UPBIT','/v1/market/all',{})
            network.assert_not_called()

    def test_each_reconstructed_budget_requires_fresh_reference(self):
        new=v.Budget(self.root,{},self.b.run,self.control)
        with patch.object(c,'verify_clock',return_value=dict(status='BLOCKED',reason='CLOCK_SYNC_UNVERIFIED')) as verify:
            with self.assertRaises(v.Stop):new.check()
            verify.assert_called_once()

    def test_slow_successful_reference_check_does_not_recursively_reprobe(self):
        mono,wall=self.b.clock_anchor;elapsed=[0.]
        self.b.clock_verified_at=None;self.b.last_awake_seconds=100.
        def verify():
            elapsed[0]=11.
            return dict(status='VERIFIED',reason='fixture')
        with patch.object(v.time,'time',side_effect=lambda:wall+elapsed[0]),patch.object(v.time,'monotonic',side_effect=lambda:mono+elapsed[0]),\
             patch.object(c,'awake_seconds',side_effect=lambda:100.+elapsed[0]),patch.object(c,'verify_clock',side_effect=verify) as check:
            self.b.check();check.assert_called_once()


if __name__=='__main__':unittest.main()
