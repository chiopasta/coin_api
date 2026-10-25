"""Paced, bounded transport retries; V4.6 packet and accuracy rules unchanged.

Two providers, three measured samples each. Retain every attempt. Only receive
timeouts may retry, once per logical sample and twice overall. Never retry an
invalid reply or replace an unfavorable valid clock measurement.
"""
import json
import socket
import struct
import time

from .scanner_ntp_v46 import HOSTS, SAMPLES_PER_HOST, TIMEOUT_SECONDS, NTP_EPOCH
from .scanner_ntp_v46 import encode_stamp, decode_reply, assess

MAX_PROCESS_SECONDS=12
INTERNAL_SECONDS=10.5
MAX_ATTEMPTS=8
HOST_INTERVAL_SECONDS=2.0
GLOBAL_INTERVAL_SECONDS=.5
BACKOFF_SECONDS=2.0


def sample(host,deadline):
    began=time.monotonic()
    row=dict(host=host,started_at=time.time(),attempt_started_monotonic=began,
             timeout_seconds=TIMEOUT_SECONDS,phase='DNS')
    try:
        addresses=socket.getaddrinfo(host,123,socket.AF_INET,socket.SOCK_DGRAM)
        row.update(dns_seconds=time.monotonic()-began,
                   resolved_ipv4=sorted({a[4][0] for a in addresses}))
        if not addresses:raise OSError('No IPv4 NTP peer')
        if deadline-time.monotonic()<TIMEOUT_SECONDS:raise TimeoutError('Probe budget exhausted after DNS')
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.settimeout(TIMEOUT_SECONDS)
            row['phase']='CONNECT';sock.connect(addresses[0][4])
            row.update(peer=list(sock.getpeername()),local_port=sock.getsockname()[1])
            packet=bytearray(48);packet[0]=0x23
            mono=time.monotonic();t1=time.time();origin=encode_stamp(t1);packet[40:48]=origin
            row.update(local_sent_at=t1,request_hex=bytes(packet).hex(),phase='SEND')
            sock.send(packet);row['phase']='RECEIVE'
            reply=sock.recv(513);t4=time.time();elapsed=time.monotonic()-mono
            row.update(response_hex=reply.hex(),receive_elapsed_seconds=elapsed,phase='VALIDATE')
            row.update(decode_reply(reply,origin,t1,t4,elapsed),status='MEASURED',retryable=False,phase='COMPLETE')
    except (OSError,ValueError,OverflowError,struct.error) as exc:
        transport=isinstance(exc,OSError)
        row.update(status='UNAVAILABLE' if transport else 'INVALID',error=str(exc),
            error_type=type(exc).__name__,errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None),
            retryable=isinstance(exc,TimeoutError) and row['phase']=='RECEIVE')
    row.update(completed_at=time.time(),attempt_elapsed_seconds=time.monotonic()-began)
    return row


def probe():
    began=time.monotonic();deadline=began+INTERNAL_SECONDS
    slots=[dict(slot_id=i,host=h,tries=0,ready_after=began) for i,h in enumerate(list(HOSTS)*SAMPLES_PER_HOST)]
    pending=slots.copy();attempts=[]
    rows=[dict(host=s['host'],slot_id=s['slot_id'],status='NOT_ATTEMPTED',error='BOUNDED_PROBE_INCOMPLETE') for s in slots]
    next_host={h:began for h in HOSTS};next_global=began;abort=None
    while pending and len(attempts)<MAX_ATTEMPTS:
        eligible=lambda s:max(s['ready_after'],next_host[s['host']],next_global)
        slot=min(pending,key=lambda s:(eligible(s),s['slot_id']))
        wait=max(0,eligible(slot)-time.monotonic())
        if time.monotonic()+wait+TIMEOUT_SECONDS>deadline:
            abort='INTERNAL_TIME_BUDGET';break
        if wait:time.sleep(wait)
        if deadline-time.monotonic()<TIMEOUT_SECONDS:
            abort='INTERNAL_TIME_BUDGET';break
        row=sample(slot['host'],deadline)
        slot['tries']+=1
        row.update(slot_id=slot['slot_id'],attempt_number=slot['tries'])
        attempts.append(row);rows[slot['slot_id']]=row
        ended=time.monotonic()
        next_host[slot['host']]=ended+HOST_INTERVAL_SECONDS
        next_global=ended+GLOBAL_INTERVAL_SECONDS
        if row['status']=='INVALID':
            abort='INVALID_REPLY_NO_RETRY';break
        if row.get('retryable') and slot['tries']<2 and len(attempts)<MAX_ATTEMPTS:
            slot['ready_after']=ended+BACKOFF_SECONDS
        else:pending.remove(slot)
    return dict(at=time.time(),hosts=list(HOSTS),samples_per_host=SAMPLES_PER_HOST,
        rows=rows,attempts=attempts,max_packets=MAX_ATTEMPTS,required_samples=6,
        probe_policy='V49_PACED_RECEIVE_TIMEOUT_RETRY',host_interval_seconds=HOST_INTERVAL_SECONDS,
        global_interval_seconds=GLOBAL_INTERVAL_SECONDS,backoff_seconds=BACKOFF_SECONDS,
        internal_seconds=INTERNAL_SECONDS,abort_reason=abort,
        elapsed_monotonic_seconds=time.monotonic()-began,authenticated=False,clock_modified=False)


if __name__=='__main__':print(json.dumps(probe(),allow_nan=False))
