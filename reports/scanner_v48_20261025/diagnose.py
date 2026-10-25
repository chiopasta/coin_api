"""Bounded time diagnostics. No system changes, resync, or scanner launch."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from coin_analysis import scanner_clock_v45 as clock

OUT=Path('reports/scanner_v48_20261025')


def write(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def command(argv,timeout=5):
    p=subprocess.run(argv,capture_output=True,timeout=timeout,creationflags=0x08000000)
    return dict(argv=argv,returncode=p.returncode,output=clock.decode_output(p.stdout+p.stderr))


def main(stage):
    target=OUT/f'clock_{stage}.json'
    if target.exists():raise RuntimeError('Never repeat existing bounded diagnostic')
    existing=list(OUT.glob('clock_*.json'))
    if len(existing)>=4:raise RuntimeError('Diagnostic NTP budget exhausted')
    result=clock.verify_clock();write(target.name,result)
    print(json.dumps(dict(stage=stage,status=result['status'],reason=result['reason'],windows=result.get('windows_status'),
        external=result.get('external_assessment'),samples=[{k:r.get(k) for k in ('host','status','offset_seconds','uncertainty_seconds')} for r in result.get('measurement',{}).get('rows',[])])),flush=True)
    if stage not in ('initial','ready'):return
    # Exactly three packets to the CURRENT selected source, diagnostics only.
    # Google response root dispersion can distinguish upstream from host state.
    source=result.get('windows_status',{}).get('source','').split(',')[0]
    if source!='time.google.com':
        write(f'upstream_{stage}.json',dict(status='SKIP',reason='Configured source differs from frozen Google scope',source=source))
    else:
        script="import json,time; from coin_analysis.scanner_ntp_v46 import sample; rows=[]\nfor i in range(3):\n rows.append(sample('time.google.com'))\n if i<2: time.sleep(.25)\nprint(json.dumps(dict(rows=rows,clock_changed=False)))"
        child=subprocess.run([sys.executable,'-c',script],capture_output=True,timeout=6,creationflags=0x08000000)
        if child.returncode:write(f'upstream_{stage}.json',dict(status='BLOCKED',error=clock.decode_output(child.stderr)))
        else:write(f'upstream_{stage}.json',json.loads(child.stdout))
    if stage=='initial':
        commands=[command(['w32tm','/query','/configuration']),command(['w32tm','/query','/peers','/verbose']),
            command(['sc.exe','qc','W32Time']),command(['sc.exe','qtriggerinfo','W32Time']),
            command(['reg.exe','query',r'HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config']),
            command(['reg.exe','query',r'HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'])]
        write('configuration.json',dict(at=time.time(),commands=commands,no_system_changes=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['initial','ready','recheck','post','blocked'])
    main(parser.parse_args().stage)
