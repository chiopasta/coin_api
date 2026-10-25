"""Bounded read-only Windows convergence monitor. Never launches LIVE."""
import json
import re
import subprocess
import time
from pathlib import Path

from coin_analysis import scanner_clock_v45 as clock
from coin_analysis import scanner_clock_v47 as admission

OUT=Path('reports/scanner_v48_20261025')


def write(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    tmp.replace(path)


def sample():
    start=time.time();mono=time.monotonic()
    command=['w32tm','/query','/status','/verbose']
    p=subprocess.run(command,capture_output=True,timeout=3,creationflags=0x08000000)
    output=clock.decode_output(p.stdout+p.stderr)
    row=dict(at=start,received_at=time.time(),monotonic_elapsed=time.monotonic()-mono,
        returncode=p.returncode,output=output,windows=admission.windows_status(output))
    poll=re.search(r'^(?:Poll Interval|폴링 간격)\s*:\s*\d+\((\d+)s\)',output,re.MULTILINE)
    phase=re.search(r'^(?:Phase Offset|단계 오프셋)\s*:\s*([+\-\d.]+)s',output,re.MULTILINE)
    row['poll_seconds']=int(poll[1]) if poll else None
    row['phase_offset_seconds']=float(phase[1]) if phase else None
    return row


def main():
    if (OUT/'trend.json').exists():raise RuntimeError('Never repeat/overwrite prior convergence monitor')
    bounds=json.loads((OUT/'preflight.json').read_text(encoding='utf8'))['bounds']
    began=time.monotonic();rows=[];reason='TIME_BOUND';last=None
    write(OUT/'trend_started.json',dict(at=time.time(),max_seconds=bounds['local_trend_max_seconds'],
        max_queries=bounds['local_status_max_queries'],interval_seconds=bounds['local_status_interval_seconds'],
        no_ntp_packets=True,no_live=True,no_system_changes=True))
    try:
        for _ in range(bounds['local_status_max_queries']):
            if time.monotonic()-began>=bounds['local_trend_max_seconds']:break
            if (OUT/'STOP_TREND').exists():reason='OWN_STOP_MARKER';break
            row=sample();rows.append(row)
            key=(row['windows'].get('root_dispersion_seconds'),row['windows'].get('last_sync_display'))
            write(OUT/'trend.json',dict(at=time.time(),running=True,rows=rows,elapsed_monotonic=time.monotonic()-began))
            print(json.dumps(dict(at=row['at'],queries=len(rows),windows=row['windows'],changed=key!=last)),flush=True)
            last=key
            if row['returncode']!=0:reason='WINDOWS_QUERY_FAILED';break
            if row['windows']['status']=='VERIFIED':reason='WINDOWS_READY_REQUIRES_FRESH_FULL_CLOCK_CHECK';break
            if row['windows']['reason']!='CLOCK_WINDOWS_ROOT_UNCERTAINTY':reason=row['windows']['reason'];break
            until=min(began+bounds['local_trend_max_seconds'],time.monotonic()+bounds['local_status_interval_seconds'])
            while time.monotonic()<until and not (OUT/'STOP_TREND').exists():
                time.sleep(min(.5,until-time.monotonic()))
    except Exception as exc:reason='MONITOR_ERROR:'+repr(exc)
    write(OUT/'trend.json',dict(at=time.time(),running=False,reason=reason,rows=rows,
        elapsed_monotonic=time.monotonic()-began,no_live_started=True,no_system_changes=True))
    print(json.dumps(dict(reason=reason,queries=len(rows))),flush=True)


if __name__=='__main__':main()
