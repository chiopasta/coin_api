"""Paced, bounded transport retries; V4.6 packet and accuracy rules unchanged.

Two providers, three measured samples each. Retain every attempt. Only receive
timeouts may retry, twice per logical sample and twice overall. Never retry an
invalid reply or replace an unfavorable valid clock measurement.
"""
import json
import socket
import struct
import time

from .scanner_ntp_v46 import HOSTS, SAMPLES_PER_HOST, NTP_EPOCH
from .scanner_ntp_v46 import encode_stamp, decode_reply, assess

TIMEOUT_SECONDS=1.5
MAX_PROCESS_SECONDS=13.25
INTERNAL_SECONDS=12.75
MAX_ATTEMPTS=8
MAX_TOTAL_RETRIES=2
MAX_RETRIES_PER_SAMPLE=2
HOST_INTERVAL_SECONDS=2.0
GLOBAL_INTERVAL_SECONDS=.5
BACKOFF_SECONDS=2.0


def provider_summary(measurement):
    """Allowlisted operational diagnostics; no packets, addresses or OS messages."""
    measurement=measurement or {}
    result=[]
    for host in HOSTS:
        attempts=[r for r in measurement.get('attempts',[]) if r.get('host')==host]
        rows=[r for r in measurement.get('rows',[]) if r.get('host')==host]
        failures={}
        for row in attempts:
            if row.get('status')=='MEASURED':continue
            phase=row.get('phase')
            phase=phase if phase in ('DNS','CONNECT','SEND','RECEIVE','VALIDATE') else 'UNKNOWN'
            kind=row.get('error_type')
            kind=kind if kind in ('TimeoutError','gaierror','OSError','ConnectionResetError','ConnectionRefusedError','ValueError','OverflowError','error') else 'UNKNOWN'
            code=phase+'_'+kind
            failures[code]=failures.get(code,0)+1
        valid=sum(r.get('status')=='MEASURED' for r in rows)
        result.append(dict(provider=host,required_samples=SAMPLES_PER_HOST,valid_samples=valid,
            attempts=len(attempts),successful_attempts=sum(r.get('status')=='MEASURED' for r in attempts),
            failed_attempts=sum(r.get('status')!='MEASURED' for r in attempts),failure_counts=failures,
            result='COMPLETE' if valid==SAMPLES_PER_HOST else 'REQUIRED_SAMPLES_MISSING'))
    return result


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
        retries=sum(max(0,s['tries']-1) for s in slots)
        if slot['tries'] and retries>=MAX_TOTAL_RETRIES:
            pending.remove(slot);continue
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
        if row.get('retryable') and slot['tries']<=MAX_RETRIES_PER_SAMPLE and len(attempts)<MAX_ATTEMPTS:
            slot['ready_after']=ended+BACKOFF_SECONDS
        else:pending.remove(slot)
    result=dict(at=time.time(),hosts=list(HOSTS),samples_per_host=SAMPLES_PER_HOST,
        rows=rows,attempts=attempts,max_packets=MAX_ATTEMPTS,required_samples=6,
        probe_policy='V53_BOUNDED_RECEIVE_TIMEOUT_RETRY',host_interval_seconds=HOST_INTERVAL_SECONDS,
        global_interval_seconds=GLOBAL_INTERVAL_SECONDS,backoff_seconds=BACKOFF_SECONDS,
        internal_seconds=INTERNAL_SECONDS,abort_reason=abort,
        elapsed_monotonic_seconds=time.monotonic()-began,authenticated=False,clock_modified=False,
        timeout_seconds=TIMEOUT_SECONDS,max_retries_per_sample=MAX_RETRIES_PER_SAMPLE,max_total_retries=MAX_TOTAL_RETRIES)
    result['provider_summary']=provider_summary(result)
    return result


if __name__=='__main__':print(json.dumps(probe(),allow_nan=False))
