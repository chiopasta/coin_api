"""Offline web-only BAT smoke; no NTP, exchange calls or Scanner starts.

Run only after the actual project's owned web has stopped. A copied project in
a Unicode/space path acts as another Python program during collision/STOP tests.
"""
from contextlib import closing
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_desktop_v50 as desktop

OUT=Path(__file__).resolve().parent
ROOT=control.PROJECT_ROOT
ENV=dict(os.environ,COIN_API_NO_PAUSE='1',COIN_API_PYTHON=os.sys.executable)


def bat(root,name,*args,shell='cmd'):
    path=root/(name+'_coin_api.bat');began=time.monotonic()
    if shell=='cmd':command=['cmd','/d','/c','call',str(path),*args]
    else:command=['powershell','-NoProfile','-NonInteractive','-Command',
                  '& '+"'"+str(path).replace("'","''")+"' "+' '.join(args)+'; exit $LASTEXITCODE']
    result=subprocess.run(command,env=ENV,cwd=ROOT,capture_output=True,timeout=55)
    return dict(action=name,args=args,shell=shell,exit_code=result.returncode,
                seconds=time.monotonic()-began,stdout=result.stdout.decode('utf8',errors='replace'),
                stderr=result.stderr.decode('utf8',errors='replace'))


def snapshot():
    with closing(http.client.HTTPConnection('127.0.0.1',8765,timeout=5)) as conn:
        conn.request('GET','/api/snapshot');response=conn.getresponse()
        assert response.status==200
        return json.loads(response.read())


if __name__=='__main__':
    assert desktop.web_state()['status']=='STOPPED'
    results=[]
    with tempfile.TemporaryDirectory(prefix='CHIO 한글 공백 (검증)! ') as folder:
        copied=Path(folder)/'코인 스캐너 프로젝트'
        shutil.copytree(ROOT/'coin_analysis',copied/'coin_analysis',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'scripts',copied/'scripts',ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('start','stop','status'):
            shutil.copyfile(ROOT/(name+'_coin_api.bat'),copied/(name+'_coin_api.bat'))
        try:
            results.append(bat(copied,'start','--dashboard-only','--no-browser',shell='powershell'))
            assert results[-1]['exit_code']==0,results[-1]
            empty=snapshot();assert empty['total']==0 and empty['signals']==[]
            assert empty['scanner']['status']=='STOPPED'
            results.append(bat(copied,'status'))
            results.append(bat(ROOT,'start','--dashboard-only','--no-browser'))
            assert results[-1]['exit_code']==2 and 'WEB_PORT_OR_START_FAILURE' in results[-1]['stdout']
            results.append(bat(ROOT,'stop',shell='powershell'))
            assert results[-1]['exit_code']==0
            assert snapshot()['total']==0  # Foreign listener remains available.
            results.append(bat(copied,'stop'))
            assert results[-1]['exit_code']==0
        finally:
            # Scoped graceful stop through the copy's own metadata; no PID kill.
            cleanup=bat(copied,'stop');assert cleanup['exit_code']==0,cleanup
    # Shell association dispatch uses the same .bat opening path as Explorer.
    path=str(ROOT/'start_coin_api.bat').replace("'","''")
    command=['powershell','-NoProfile','-NonInteractive','-Command',
             "$p=Start-Process -FilePath '"+path+"' -ArgumentList '--dashboard-only','--no-browser' -WindowStyle Hidden -PassThru; if (!$p.WaitForExit(10000)) { exit 3 }; exit $p.ExitCode"]
    began=time.monotonic();opened=subprocess.run(command,env=ENV,cwd=ROOT,capture_output=True,timeout=20)
    assert opened.returncode==0,opened.stderr
    actual=snapshot();assert actual['total']==163
    before=desktop.web_state()['process']
    results.append(bat(ROOT,'start','--dashboard-only','--no-browser',shell='powershell'))
    assert results[-1]['exit_code']==0
    assert desktop.web_state()['process']==before  # Reuses exact owned process.
    results.append(bat(ROOT,'status',shell='powershell'))
    value=dict(at=time.time(),success=True,results=results,unicode_space_actual_web=True,
               no_database_empty=True,foreign_port_untouched=True,foreign_python_survives_stop=True,
               shell_association_launch=True,shell_association_seconds=time.monotonic()-began,
               physical_mouse_doubleclick='UNVERIFIED',restart_original_signals=actual['total'],
               duplicate_web_same_identity=True,live_started=False,ntp_calls=0,
               final_web='RUNNING for remaining browser validation; must stop before completion')
    (OUT/'bat_smoke.json').write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k!='results'},ensure_ascii=True))
