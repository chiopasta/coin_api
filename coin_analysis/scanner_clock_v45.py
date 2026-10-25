"""Read-only Windows clock admission. Never starts a service or sets the clock."""
import os
import re
import subprocess
import time

MAX_OFFSET_SECONDS = 1.0
MAX_SPREAD_SECONDS = .5
RECHECK_SECONDS = 600
MAX_WALL_DRIFT_SECONDS = 1.0


def verify_clock():
    """Service status plus three bounded external offset samples, fail closed.

    A single unauthenticated NTP reference is an operational check, not a
    metrology/security attestation. HTTP Date never substitutes for this check.
    Service failure prevents all NTP samples and exchange calls.
    """
    result = dict(at=time.time(),status='BLOCKED',reason='CLOCK_SYNC_UNVERIFIED',
                  reference='time.windows.com',max_samples=3,max_seconds=15,
                  max_offset_seconds=MAX_OFFSET_SECONDS,max_spread_seconds=MAX_SPREAD_SECONDS,
                  clock_changed=False,commands=[])
    if os.name!='nt':
        return result
    commands = [(['w32tm','/query','/status','/verbose'],3),
                (['w32tm','/stripchart','/computer:time.windows.com','/samples:3',
                  '/period:1','/dataonly'],12)]
    try:
        for command,timeout in commands:
            completed = subprocess.run(command,capture_output=True,timeout=timeout,
                                       creationflags=0x08000000)
            output = (completed.stdout+completed.stderr).decode('utf8',errors='replace')
            result['commands'].append(dict(argv=command,returncode=completed.returncode,output=output))
            if completed.returncode:
                return result
        offsets = [float(x.replace(',','.')) for x in re.findall(r'([+-]\d+[.,]\d+)s\s*$',output,re.MULTILINE)]
        result['offset_seconds'] = offsets
        if len(offsets)!=3:
            return result
        if max(abs(x) for x in offsets)>MAX_OFFSET_SECONDS or max(offsets)-min(offsets)>MAX_SPREAD_SECONDS:
            return dict(result,reason='CLOCK_REFERENCE_OFFSET_OR_JITTER')
        return dict(result,status='VERIFIED',reason='BOUNDED_EXTERNAL_OFFSET_CHECK')
    except (OSError,subprocess.TimeoutExpired) as exc:
        return dict(result,error=repr(exc))


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
