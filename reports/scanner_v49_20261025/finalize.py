"""Read-only review after the single bounded V4.9 episode ends."""
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

from reports.scanner_v49_20261025.analysis import review_episode

OUT=Path('reports/scanner_v49_20261025')
ROOT=Path('data/scanner_v43_live/episode_20261025_v49')


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))


def write(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def main():
    original=read(OUT/'preflight.json')
    protected={p:sha(p)==h for p,h in original['protected_hashes'].items()}
    prior={p:sha(p)==h for p,h in original['prior_evidence_hashes'].items()}
    assert len(protected)==86 and len(prior)==138 and all(protected.values()) and all(prior.values())
    p=Path('data/forward_scanner_v4.db');wal=Path(str(p)+'-wal');assert not wal.exists() or not wal.stat().st_size
    db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        count=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        health=db.execute('PRAGMA quick_check').fetchone()[0]
    finally:db.close()
    assert count==163 and health=='ok'
    legacy=read('reports/scanner_v41_validation_20261024/legacy_reconciliation.json')
    assert legacy['counts']['STALE_OPEN']==115 and sha(legacy['source'])==legacy['source_sha256']
    frozen=['coin_analysis/forward_scanner_v4.py','coin_analysis/forward_scanner_v4_operations.py',
        'coin_analysis/scanner_candles.py','coin_analysis/forward_scanner_v42.py','coin_analysis/research_dataset_collector_v1.py',
        'coin_analysis/scanner_clock_v47.py','coin_analysis/scanner_ntp_v46.py','coin_analysis/scanner_observation_v45.py',
        'archive/scanner_v15.py','docs/forward_surge_v3_validation_policy.json','docs/research_market_validation_v1_manifest.json']
    assert not subprocess.check_output(['git','diff','8a703fb','--',*frozen],text=True).strip()
    before=subprocess.check_output(['git','show','8a703fb:coin_analysis/forward_scanner_v43.py'],text=True)
    assert Path('coin_analysis/forward_scanner_v43.py').read_text(encoding='utf8')==before.replace("OBSERVER_REVISION = '4.7'","OBSERVER_REVISION = '4.9'")
    tests=read(OUT/'test_result.json');assert tests['successful']
    assert all(sha(p)==h for p,h in tests['tested_source_sha256'].items())
    env=read(OUT/'environment_final.json');assert not env['scanners']
    inspect=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"],capture_output=True,timeout=5)
    assert inspect.returncode==0 and not json.loads(inspect.stdout.strip() or b'[]')
    baselines=[read(OUT/f'baseline_{i}.json')['result'] for i in (1,2)]
    diagnostics=[read(p) for p in sorted(OUT.glob('clock_*.json'))]
    assert len(diagnostics)<=4
    live=read(OUT/'live_result.json') if (OUT/'live_result.json').exists() else None
    review=review_episode(ROOT) if live else None
    if review:
        assert review['all_requests_public'] and review['live_http_attempts']==live['requests']<=260
        assert len(live['runs'])==2
        assert all(r['supervisor_returncode']==0 and r['supervisor_reaped'] and r['exit']['worker_reaped'] and
            not r['exit']['forced_kill'] and not r['summary']['close_errors'] for r in live['runs'])
        assert all(r['quick_check']=='ok' and r['duplicated_signals']==0 and r['candle_alignment_errors']==0 and r['score_nonnull']==0 for r in review['per_exchange'].values())
        assert sha(ROOT/'config.json')==read(OUT/'before_resume.json')['config_sha256']
        write('live_review.json',review)
    elif ROOT.exists():raise RuntimeError('Incomplete LIVE evidence; diagnose and report partial run explicitly')
    worker=[];supervisors=[]
    if ROOT.exists():
        for p in ROOT.glob('events*.jsonl'):
            for line in p.read_text(encoding='utf8').splitlines():
                row=json.loads(line)
                if row.get('kind')=='CLOCK_CHECK':worker.append(row['evidence'])
        supervisors=[read(p)['clock_admission'] for p in (ROOT/'runs').glob('*.json') if not p.name.endswith(('.summary.json','.exit.json'))]
    assert len(worker)<=8 and len(supervisors)<=2
    if live:assert all(c['status']=='VERIFIED' for c in worker+supervisors)
    all_checks=baselines+diagnostics+worker+supervisors
    attempts=[a for c in all_checks for a in c.get('measurement',{}).get('attempts',c.get('measurement',{}).get('rows',[]))]
    assert len(attempts)<=128
    write('ntp_review.json',dict(baseline_checks=baselines,paced_diagnostic_checks=diagnostics,
        worker_checks=worker,supervisor_checks=supervisors,attempts=len(attempts),
        received=sum(a['status']=='MEASURED' for a in attempts),
        failures=[a for a in attempts if a['status']!='MEASURED'],
        new_probe_attempts=[a for c in diagnostics+worker+supervisors for a in c.get('measurement',{}).get('attempts',[])],
        exact_loss_origin='UNKNOWN; spacing/rate loss is a hypothesis, no wire capture',accuracy_rules_unchanged=True))
    intervals=[dict(start=r['summary']['started_at'],end=r['summary']['ended_at'],elapsed=r['summary']['elapsed_monotonic_seconds'],
        status=r['summary']['status'],reason=r['summary']['reason'],rounds=r['summary']['completed_rounds'],requests=r['summary']['requests']) for r in live['runs']] if live else []
    duration=sum(r['elapsed'] for r in intervals);assert duration<=1200
    api=read(OUT/'api_preflight.json') if (OUT/'api_preflight.json').exists() else None
    if api:assert api['finished'] and len(api['records'])==4 and all(r['status']==200 for r in api['records'])
    write('completion_checks.json',dict(at=time.time(),infrastructure='PARTIAL',readiness_24h='NOT_READY',
        original_signals=count,original_quick_check=health,protected_count=86,protected_unchanged=protected,
        prior_count=138,prior_unchanged=prior,stale_open=115,tests=tests,
        strategy_and_original_research_unchanged=True,clock_accuracy_and_freshness_limits_unchanged=True,
        live_ran=bool(live),intervals=intervals,actual_observed_monotonic_seconds=duration,
        restart_gap_seconds=intervals[1]['start']-intervals[0]['end'] if len(intervals)==2 else None,
        new_signals=review['signals'] if review else 0,live_http_attempts=live['requests'] if live else 0,
        api_preflight_attempts=len(api['records']) if api else 0,ntp_attempts=len(attempts),
        worker_checks=len(worker),supervisor_checks=len(supervisors),active_scanners=0,
        peak_rss_bytes=max((r['summary']['peak_rss_bytes'] for r in live['runs']),default=None) if live else None,
        max_cpu_percent=max((r['summary']['max_cpu_percent'] for r in live['runs']),default=None) if live else None,
        runtime_bytes=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) if ROOT.exists() else 0,
        raw_runtime_hashes={str(p):sha(p) for p in ROOT.rglob('*') if p.is_file()} if ROOT.exists() else {},
        actual_60m='UNVERIFIED',sleep_resume='UNVERIFIED',reboot='UNVERIFIED',
        no_orders=True,no_system_changes=True,no_auto_restart=True,no_windows_shutdown=True))
    print(json.dumps(dict(status='PARTIAL',live=bool(live),signals=review['signals'] if review else 0,
        duration=duration,ntp_packets=len(attempts),protected=86,prior=138)))


if __name__=='__main__':main()
