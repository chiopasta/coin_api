"""Second and final bounded BAT start; no automatic retry after failure."""
import json
import os
from pathlib import Path
import subprocess
import time

from coin_analysis import scanner_control_v410 as c

OUT=Path('reports/scanner_v410_20261025')


def write(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)


def command(action,*args):
    result=subprocess.run(['cmd','/d','/c','call',str(c.PROJECT_ROOT/(action+'_coin_api.bat')),*args],
        cwd=c.PROJECT_ROOT.parent,env=dict(os.environ,COIN_API_NO_PAUSE='1'),capture_output=True,timeout=55)
    return dict(returncode=result.returncode,stdout=result.stdout.decode('utf8',errors='replace'),stderr=result.stderr.decode('utf8',errors='replace'))


if __name__=='__main__':
    if (OUT/'second_attempt.json').exists():raise RuntimeError('No repeated LIVE test')
    previous=c.current()['launch_id'];env=dict(os.environ,COIN_API_NO_PAUSE='1')
    with (OUT/'powershell_start.log').open('x',encoding='utf8') as log:
        process=subprocess.Popen(['powershell','-NoProfile','-Command',
            "& '"+str(c.PROJECT_ROOT/'start_coin_api.bat')+"' --seconds 120 --max-requests 80"],
            cwd=c.PROJECT_ROOT.parent,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
        ready=None;until=time.monotonic()+55;result=dict(max_seconds=120,max_requests=80,method='PowerShell invokes BAT',no_further_start=True)
        try:
            while time.monotonic()<until and process.poll() is None:
                state=c.current()
                if state['launch_id']!=previous:
                    if state['phase']=='TERMINAL':break
                    if state['phase']=='OBSERVING':ready=c.snapshot();break
                time.sleep(.5)
            if ready:
                assert ready['status']=='RUNNING' and ready['clock'].startswith('PASS')
                assert ready['signals'] is not None and ready['collected'] is not None
                write('running_snapshot.json',ready)
                token=ready['launch_id']
                duplicate=command('start','--seconds','120','--max-requests','80')
                assert duplicate['returncode']==2 and c.current()['launch_id']==token
                write('duplicate_start.json',duplicate)
                status=command('status');assert status['returncode']==0 and 'RUNNING' in status['stdout']
                write('running_status_bat.json',status)
                time.sleep(15)
                stopped=command('stop');write('stop_bat.json',stopped);assert stopped['returncode']==0
                result['live_ran']=True
            else:
                result['live_ran']=False
                result['blocked_or_not_ready']=c.snapshot()
                if process.poll() is None:write('early_stop.json',command('stop'))
            process.wait(timeout=55)
            result.update(returncode=process.returncode,final_state=c.current(),final_view=c.snapshot())
            if ready:
                assert process.returncode==0 and result['final_view']['status']=='STOPPED'
                assert result['final_view']['db_saved'].startswith('SAVED')
            write('second_attempt.json',result)
            print(json.dumps(dict(live=result['live_ran'],returncode=process.returncode,status=result['final_view']['status'])),flush=True)
        finally:
            if process.poll() is None:
                command('stop')
                process.wait(timeout=160)  # Existing 120s + supervisor cleanup, no force kill here.
