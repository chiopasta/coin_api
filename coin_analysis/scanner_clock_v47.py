"""Pure V4.7 admission checks. No network, clock correction or policy override."""
import math
import re

MAX_WINDOWS_SYNC_AGE_SECONDS=3600  # Same ceiling as existing NTP reference age.
MAX_MEASUREMENT_AGE_SECONDS=15    # Entire bounded clock-check duration.

LABELS={
    'leap':('Leap Indicator','윤초 조정'),
    'stratum':('Stratum','계층'),
    'root_delay':('Root Delay','루트 지연'),
    'root_dispersion':('Root Dispersion','루트 분산'),
    'sync_age':('Time since Last Good Sync Time','마지막으로 동기화한 후 지난 시간','마지막으로 동기화한 후 경과된 시간'),
    'sync_error':('Last Sync Error','마지막 동기화 오류'),
    'source':('Source','원본'),
    'last_sync':('Last Successful Sync Time','마지막으로 동기화한 시간'),
}
NUMBER=r'[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?'


def windows_status(output,limit=1.):
    """Read English/Korean verbose status; unsupported/ambiguous text blocks.

    Use relative sync age, not a locale-dependent wall-date parser. Root
    distance = dispersion + delay/2 must stay inside the original one second.
    """
    result=dict(status='BLOCKED',reason='CLOCK_WINDOWS_STATUS_UNPARSEABLE')
    try:
        fields={}
        for key,labels in LABELS.items():
            values=re.findall(r'^(?:'+'|'.join(re.escape(s) for s in labels)+r')\s*:\s*(.*?)\s*$',output,re.MULTILINE|re.IGNORECASE)
            if len(values)!=1:raise ValueError('Missing/ambiguous field: '+key)
            fields[key]=values[0]
        parsed={}
        for key in ('root_delay','root_dispersion','sync_age'):
            match=re.fullmatch('('+NUMBER+r')s',fields[key])
            if not match:raise ValueError('Missing seconds unit or malformed '+key)
            parsed[key]=float(match[1].replace(',','.'))
            if not math.isfinite(parsed[key]) or parsed[key]<0:raise ValueError('Invalid '+key)
        for key in ('leap','stratum','sync_error'):
            match=re.match(r'^(\d+)(?:\s*\(|\s*$)',fields[key])
            if not match:raise ValueError('Malformed '+key)
            parsed[key]=int(match[1])
        result.update(leap=parsed['leap'],stratum=parsed['stratum'],last_sync_error=parsed['sync_error'],
            root_delay_seconds=parsed['root_delay'],root_dispersion_seconds=parsed['root_dispersion'],
            root_distance_seconds=parsed['root_dispersion']+parsed['root_delay']/2,
            sync_age_seconds=parsed['sync_age'],source=fields['source'],last_sync_display=fields['last_sync'],
            max_sync_age_seconds=MAX_WINDOWS_SYNC_AGE_SECONDS,root_distance_limit_seconds=limit)
        if parsed['leap']!=0 or not 1<=parsed['stratum']<=15 or parsed['sync_error']!=0 or not fields['source']:
            return dict(result,reason='CLOCK_WINDOWS_UNSYNCHRONIZED')
        if result['root_distance_seconds']>limit:
            return dict(result,reason='CLOCK_WINDOWS_ROOT_UNCERTAINTY')
        if parsed['sync_age']>MAX_WINDOWS_SYNC_AGE_SECONDS:
            return dict(result,reason='CLOCK_WINDOWS_SYNC_STALE')
        return dict(result,status='VERIFIED',reason='WINDOWS_SYNC_ROOT_DISTANCE_AND_AGE')
    except (TypeError,ValueError) as exc:
        return dict(result,error=str(exc))


def measurement_freshness(measurement,now):
    result=dict(status='BLOCKED',reason='CLOCK_REFERENCE_FRESHNESS_UNVERIFIED',max_age_seconds=MAX_MEASUREMENT_AGE_SECONDS)
    try:
        rows=measurement['rows']
        if len(rows)!=6 or not math.isfinite(now):raise ValueError('Missing scope or clock')
        for row in rows:
            sent,received=row['local_sent_at'],row['local_received_at']
            if not all(math.isfinite(t) for t in (sent,received)) or sent>received or received>now+.01:
                raise ValueError('Invalid local sample timestamp')
        oldest=now-min(row['local_sent_at'] for row in rows)
        result['oldest_sample_age_seconds']=oldest
        if oldest>MAX_MEASUREMENT_AGE_SECONDS:return dict(result,reason='CLOCK_REFERENCE_STALE')
        return dict(result,status='VERIFIED',reason='FRESH_DIRECT_NTP_SAMPLES')
    except (KeyError,TypeError,ValueError) as exc:
        return dict(result,error=str(exc))
