import json
import subprocess
import unittest
from unittest.mock import MagicMock,patch

from coin_analysis import scanner_ntp_v49 as n
from coin_analysis import scanner_clock_v45 as c
from tests.test_scanner_clock_v46 import measurement
from tests.scanner_clock_fixtures import WINDOWS_OK


class FakeTime:
    def __init__(self):self.value=0.
    def monotonic(self):return self.value
    def sleep(self,seconds):self.value+=seconds
    def time(self):return 1_790_000_000+self.value


class RetryPolicy(unittest.TestCase):
    def run_probe(self,failures=None,invalid=False,offset=.01,duration=.01):
        timer=FakeTime();calls=[];failures=set(failures or [])
        def sample(host,deadline):
            index=len(calls);calls.append((host,timer.value))
            timer.value+=1.2 if index in failures else duration
            if index in failures:return dict(host=host,status='UNAVAILABLE',retryable=True,error='timed out')
            if invalid:return dict(host=host,status='INVALID',retryable=False,error='ORIGIN_MISMATCH')
            return dict(host=host,status='MEASURED',retryable=False,offset_seconds=offset,
                uncertainty_seconds=.02,error_interval_seconds=[offset-.02,offset+.02],
                local_sent_at=timer.time()-.01,local_received_at=timer.time())
        with patch.object(n.time,'monotonic',timer.monotonic),patch.object(n.time,'sleep',timer.sleep),\
             patch.object(n.time,'time',timer.time),patch.object(n,'sample',side_effect=sample):
            result=n.probe()
        return result,calls

    def test_six_successes_two_providers_and_no_concurrent_or_fast_requests(self):
        r,calls=self.run_probe()
        self.assertEqual(n.assess(r)['status'],'VERIFIED');self.assertEqual(len(calls),6)
        for host in n.HOSTS:
            times=[t for h,t in calls if h==host]
            self.assertEqual(len(times),3)
            self.assertTrue(all(b-a>=2. for a,b in zip(times,times[1:])))
        self.assertTrue(all(b[1]-a[1]>=.5 for a,b in zip(calls,calls[1:])))

    def test_timeout_recovers_only_with_a_new_valid_sample_and_keeps_failure(self):
        r,calls=self.run_probe({0})
        self.assertEqual(n.assess(r)['status'],'VERIFIED')
        self.assertEqual(len(r['attempts']),7)
        self.assertEqual(r['attempts'][0]['status'],'UNAVAILABLE')
        self.assertEqual(sum(a['status']=='MEASURED' for a in r['attempts']),6)
        retried=[a for a in r['attempts'] if a['slot_id']==0]
        self.assertEqual([a['attempt_number'] for a in retried],[1,2])
        self.assertGreaterEqual(calls[2][1],3.2)

    def test_permanent_loss_never_passes_and_never_exceeds_eight_packets(self):
        r,calls=self.run_probe(set(range(8)))
        self.assertEqual(n.assess(r)['status'],'BLOCKED')
        self.assertLessEqual(len(calls),8);self.assertLessEqual(r['elapsed_monotonic_seconds'],10.5)
        self.assertTrue(all(a['attempt_number']<=2 for a in r['attempts']))

    def test_invalid_reply_is_terminal_and_not_retried(self):
        r,calls=self.run_probe(invalid=True)
        self.assertEqual(len(calls),1);self.assertEqual(r['abort_reason'],'INVALID_REPLY_NO_RETRY')
        self.assertEqual(n.assess(r)['status'],'BLOCKED')

    def test_bad_accuracy_is_preserved_without_searching_for_better_samples(self):
        r,calls=self.run_probe(offset=1.1)
        self.assertEqual(len(calls),6)
        self.assertEqual(n.assess(r)['reason'],'CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY')
        self.assertTrue(all(a['offset_seconds']==1.1 for a in r['attempts']))

    def test_scheduler_does_not_spend_a_partial_timeout_after_internal_deadline(self):
        r,calls=self.run_probe(duration=2.)
        self.assertEqual(n.assess(r)['status'],'BLOCKED')
        self.assertEqual(r['abort_reason'],'INTERNAL_TIME_BUDGET')
        self.assertLessEqual(len(calls),5)


class AttemptEvidence(unittest.TestCase):
    def test_receive_timeout_records_peer_port_request_phase_and_elapsed(self):
        sock=MagicMock();sock.__enter__.return_value=sock
        sock.getpeername.return_value=('192.0.2.1',123);sock.getsockname.return_value=('192.0.2.2',51000)
        sock.recv.side_effect=TimeoutError('timed out')
        with patch.object(n.socket,'getaddrinfo',return_value=[(2,2,17,'',('192.0.2.1',123))]),\
             patch.object(n.socket,'socket',return_value=sock):r=n.sample(n.HOSTS[0],n.time.monotonic()+10)
        self.assertEqual(r['phase'],'RECEIVE');self.assertTrue(r['retryable'])
        self.assertEqual(r['local_port'],51000);self.assertEqual(len(r['request_hex']),96)
        self.assertEqual(r['status'],'UNAVAILABLE');self.assertIn('attempt_elapsed_seconds',r)

    def test_invalid_packet_and_dns_failure_are_not_transport_retries(self):
        with patch.object(n.socket,'getaddrinfo',side_effect=OSError('DNS unavailable')):
            r=n.sample(n.HOSTS[0],n.time.monotonic()+10)
        self.assertFalse(r['retryable']);self.assertEqual(r['phase'],'DNS')
        sock=MagicMock();sock.__enter__.return_value=sock
        sock.getpeername.return_value=('192.0.2.1',123);sock.getsockname.return_value=('192.0.2.2',51000)
        sock.recv.return_value=b'invalid'
        with patch.object(n.socket,'getaddrinfo',return_value=[(2,2,17,'',('192.0.2.1',123))]),\
             patch.object(n.socket,'socket',return_value=sock):r=n.sample(n.HOSTS[0],n.time.monotonic()+10)
        self.assertEqual(r['status'],'INVALID');self.assertFalse(r['retryable']);self.assertIn('response_hex',r)


class WholeClock(unittest.TestCase):
    def test_whole_check_clock_jump_blocks_even_when_individual_samples_are_good(self):
        value=measurement()
        completed=[subprocess.CompletedProcess([],0,WINDOWS_OK.encode(),b''),
                   subprocess.CompletedProcess([],0,json.dumps(value).encode(),b'')]
        now=c.time.time()
        with patch.object(c.os,'name','nt'),patch.object(c.subprocess,'run',side_effect=completed),\
             patch.object(c.time,'time',side_effect=[now,now,now+2]):r=c.verify_clock()
        self.assertEqual(r['reason'],'CLOCK_WALL_MONOTONIC_DIVERGENCE')
        self.assertEqual(c.MAX_OFFSET_SECONDS,1.)


if __name__=='__main__':unittest.main()
