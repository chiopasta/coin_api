"""Small bounded read-only NTP probe, not a clock discipline client.

RFC5905 timestamp/offset/delay validation. Six packets maximum, two providers.
Caller uses a separate process timeout to also bound DNS resolution. No retries,
clock setting, credentials, orders or exchange endpoints.
"""
import json
import math
import socket
import struct
import time

HOSTS=('time.windows.com','time.cloudflare.com')
SAMPLES_PER_HOST=3
TIMEOUT_SECONDS=1.2
MAX_PROCESS_SECONDS=12
NTP_EPOCH=2208988800


def encode_stamp(unix):
    ntp=unix+NTP_EPOCH
    return struct.pack('!II',int(ntp),int((ntp-int(ntp))*2**32))


def decode_stamp(raw):
    seconds,fraction=struct.unpack('!II',raw)
    return seconds-NTP_EPOCH+fraction/2**32


def decode_reply(packet,origin,t1,t4,elapsed):
    if len(packet)!=48:raise ValueError('NTP_LENGTH_OR_UNSUPPORTED_EXTENSION')
    leap,version,mode=packet[0]>>6,(packet[0]>>3)&7,packet[0]&7
    stratum=packet[1]
    if leap!=0 or version not in (3,4) or mode!=4 or not 1<=stratum<=15:
        raise ValueError('NTP_UNSYNCHRONIZED_MODE_VERSION_OR_KISS')
    if packet[24:32]!=origin:raise ValueError('NTP_ORIGIN_MISMATCH')
    ref,t2,t3=[decode_stamp(packet[i:i+8]) for i in (16,32,40)]
    if any(packet[i:i+8]==b'\0'*8 for i in (16,32,40)) or t2>t3 or not 0<=t3-ref<=3600:
        raise ValueError('NTP_INVALID_OR_STALE_SERVER_TIMESTAMPS')
    wall_elapsed=t4-t1
    clock_difference=abs(wall_elapsed-elapsed)
    if wall_elapsed<0 or elapsed<0 or clock_difference>.01:
        raise ValueError('NTP_LOCAL_CLOCK_CHANGED_DURING_SAMPLE')
    delay=wall_elapsed-(t3-t2)
    if delay<-.001:raise ValueError('NTP_NEGATIVE_NETWORK_DELAY')
    root_delay=struct.unpack('!i',packet[4:8])[0]/65536
    root_dispersion=struct.unpack('!I',packet[8:12])[0]/65536
    precision=2.**struct.unpack('!b',packet[3:4])[0]
    offset=((t2-t1)+(t3-t4))/2
    # Conservative path asymmetry bound plus advertised reference error,
    # server precision and local wall/monotonic sampling disagreement.
    uncertainty=max(0,delay)/2+max(0,root_delay)/2+root_dispersion+precision+clock_difference+3/65536+1e-6
    if not all(math.isfinite(x) for x in (offset,uncertainty)):
        raise ValueError('NTP_NONFINITE_MEASUREMENT')
    return dict(offset_seconds=offset,uncertainty_seconds=uncertainty,
        error_interval_seconds=[offset-uncertainty,offset+uncertainty],
        delay_seconds=delay,elapsed_monotonic_seconds=elapsed,root_delay_seconds=root_delay,
        root_dispersion_seconds=root_dispersion,server_precision_seconds=precision,
        local_sampling_difference_seconds=clock_difference,stratum=stratum,
        reference_at=ref,server_received_at=t2,server_transmitted_at=t3,
        local_sent_at=t1,local_received_at=t4,
        positive_offset_means='Reference is ahead of local wall clock')


def sample(host):
    row=dict(host=host,started_at=time.time())
    try:
        # Connected UDP checks source peer; originate timestamp binds response.
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
            sock.settimeout(TIMEOUT_SECONDS);sock.connect((host,123))
            row['peer']=list(sock.getpeername())
            packet=bytearray(48);packet[0]=0x23
            mono=time.monotonic();t1=time.time();origin=encode_stamp(t1);packet[40:48]=origin
            sock.send(packet);reply=sock.recv(513)
            t4=time.time();elapsed=time.monotonic()-mono
            row.update(decode_reply(reply,origin,t1,t4,elapsed),status='MEASURED',
                       request_hex=bytes(packet).hex(),response_hex=reply.hex())
    except (OSError,ValueError,OverflowError,struct.error) as exc:
        row.update(status='UNAVAILABLE',error=str(exc))
    return row


def probe():
    began=time.monotonic();rows=[]
    for index in range(SAMPLES_PER_HOST):
        for host in HOSTS:
            rows.append(sample(host))
            if index!=SAMPLES_PER_HOST-1 or host!=HOSTS[-1]:time.sleep(.25)
    return dict(at=time.time(),hosts=list(HOSTS),samples_per_host=SAMPLES_PER_HOST,
        max_packets=6,rows=rows,elapsed_monotonic_seconds=time.monotonic()-began,
        authenticated=False,clock_modified=False)


def assess(measurement,max_offset=1.,max_spread=.5):
    """No enlarged tolerance: require entire uncertainty interval inside ±1s."""
    if not isinstance(measurement,dict):
        return dict(status='BLOCKED',reason='CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')
    rows=measurement.get('rows',[])
    if not isinstance(rows,list) or len(rows)!=6 or any(not isinstance(r,dict) or r.get('status')!='MEASURED' for r in rows):
        return dict(status='BLOCKED',reason='CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')
    try:
        for r in rows:
            offset,uncertainty=r['offset_seconds'],r['uncertainty_seconds']
            interval=r['error_interval_seconds']
            if (not all(math.isfinite(x) for x in (offset,uncertainty)) or uncertainty<0 or len(interval)!=2 or
                not math.isclose(interval[0],offset-uncertainty,rel_tol=0,abs_tol=1e-9) or
                not math.isclose(interval[1],offset+uncertainty,rel_tol=0,abs_tol=1e-9)):
                raise ValueError('Invalid interval')
    except (KeyError,TypeError,ValueError):
        return dict(status='BLOCKED',reason='CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')
    by_host={h:[r for r in rows if r.get('host')==h] for h in HOSTS}
    if any(len(samples)!=3 for samples in by_host.values()):
        return dict(status='BLOCKED',reason='CLOCK_REFERENCE_SCOPE_MISMATCH')
    if any(abs(r['offset_seconds'])+r['uncertainty_seconds']>max_offset for r in rows):
        return dict(status='BLOCKED',reason='CLOCK_REFERENCE_OFFSET_OR_UNCERTAINTY')
    offsets=[r['offset_seconds'] for r in rows]
    if max(offsets)-min(offsets)>max_spread:
        return dict(status='BLOCKED',reason='CLOCK_REFERENCE_OFFSET_OR_JITTER')
    # Two providers must have overlapping error intervals, not just small offsets.
    if max(r['error_interval_seconds'][0] for r in rows)>min(r['error_interval_seconds'][1] for r in rows):
        return dict(status='BLOCKED',reason='CLOCK_REFERENCE_DISAGREEMENT')
    return dict(status='VERIFIED',reason='TWO_PROVIDER_NTP_WITH_UNCERTAINTY')


if __name__=='__main__':print(json.dumps(probe(),allow_nan=False))
