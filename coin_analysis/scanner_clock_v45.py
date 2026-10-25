"""Read-only Windows clock admission. Never starts a service or sets the clock."""
import os
import ctypes
import json
import subprocess
import sys
import time

from . import scanner_ntp_v46 as ntp

MAX_OFFSET_SECONDS = 1.0
MAX_SPREAD_SECONDS = .5
RECHECK_SECONDS = 600
MAX_WALL_DRIFT_SECONDS = 1.0
MAX_CHECK_GAP_SECONDS = 10.0
SUSPEND_DIFFERENCE_SECONDS = .5


def decode_output(raw):
    try:return raw.decode('utf8')
    except UnicodeDecodeError:return raw.decode('cp949',errors='replace')


def awake_seconds():
    """Windows elapsed time excluding sleep/hibernation; no clock setting."""
    if os.name!='nt':return None
    value=ctypes.c_ulonglong()
    try:
        query=ctypes.windll.kernel32.QueryUnbiasedInterruptTime
        query.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)];query.restype=ctypes.c_bool
        if not query(ctypes.byref(value)):return None
        return value.value/10_000_000
    except (AttributeError,OSError):return None


def verify_clock():
    """V4.6: diagnose external accuracy even when Windows service is stopped.

    Admission STILL requires Windows status plus two-provider evidence inside
    the existing tolerance INCLUDING uncertainty. No time correction or offset
    compensation. Subprocess timeout also bounds DNS. NTP is unauthenticated.
    """
    result = dict(at=time.time(),status='BLOCKED',reason='CLOCK_SYNC_UNVERIFIED',
                  references=list(ntp.HOSTS),max_samples=6,max_seconds=15,clock_policy='V46_NTP_UNCERTAINTY',
                  max_offset_seconds=MAX_OFFSET_SECONDS,max_spread_seconds=MAX_SPREAD_SECONDS,
                  clock_changed=False,commands=[])
    if os.name!='nt':
        return result
    service_ok=False;blockers=[]
    try:
        command=['w32tm','/query','/status','/verbose']
        completed=subprocess.run(command,capture_output=True,timeout=3,creationflags=0x08000000)
        result['commands'].append(dict(argv=command,returncode=completed.returncode,
                                      output=decode_output(completed.stdout+completed.stderr)))
        service_ok=completed.returncode==0
    except (OSError,subprocess.TimeoutExpired) as exc:
        result['service_error']=repr(exc)
    if not service_ok:blockers.append('CLOCK_WINDOWS_TIME_SERVICE_UNVERIFIED')
    try:
        command=[sys.executable,'-m','coin_analysis.scanner_ntp_v46']
        completed=subprocess.run(command,capture_output=True,timeout=ntp.MAX_PROCESS_SECONDS,creationflags=0x08000000)
        if completed.returncode:raise ValueError('NTP probe child failed: '+decode_output(completed.stderr))
        measurement=json.loads(completed.stdout)
        result['measurement']=measurement
        assessment=ntp.assess(measurement,MAX_OFFSET_SECONDS,MAX_SPREAD_SECONDS)
    except (OSError,subprocess.TimeoutExpired,ValueError) as exc:
        result['measurement_error']=repr(exc)
        assessment=dict(status='BLOCKED',reason='CLOCK_REFERENCE_MEASUREMENT_UNAVAILABLE')
    if assessment['status']!='VERIFIED':blockers.append(assessment['reason'])
    result['blockers']=blockers
    if blockers:return dict(result,reason=blockers[-1])
    return dict(result,status='VERIFIED',reason=assessment['reason'])


def resume_continuity(db, now):
    """Reject future persisted progress, receipts, sessions or evidence."""
    queries = [('scanner_state','MAX(MAX(verified_until,last_observation))'),
               ('candle_receipts','MAX(first_received_at)'),
               ('scanner_sessions','MAX(MAX(started_at,COALESCE(ended_at,0)))'),
               ('minute_candles','MAX(ts+60)'),
               ('collection_jobs','MAX(end)'),
               ('no_trade_evidence_v45','MAX(known_at)'),
               ('price_horizons_v45','MAX(evaluated_at)')]
    for table,expression in queries:
        stamp = db.execute(f'SELECT {expression} FROM {table}').fetchone()[0]
        if stamp is not None and stamp>now+MAX_WALL_DRIFT_SECONDS:
            raise ValueError('CLOCK_PERSISTED_FUTURE:'+table)
