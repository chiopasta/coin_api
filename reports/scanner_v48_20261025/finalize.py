"""Review real evidence after bounded monitoring/LIVE; no collection or repair."""
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

from coin_analysis import forward_scanner_v43 as v
from reports.scanner_v48_20261025.analysis import root_trend,review_episode

OUT=Path('reports/scanner_v48_20261025')
ROOT=Path('data/scanner_v43_live/episode_20261025_v48')


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def readonly_original(path):
    wal=Path(str(path)+'-wal')
    if wal.exists() and wal.stat().st_size:raise RuntimeError('Original WAL nonempty; immutable read blocked')
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)


def main():
    original=json.loads((OUT/'preflight.json').read_text(encoding='utf8'))
    protected={p:sha(p)==h for p,h in original['protected_hashes'].items()}
    prior={p:sha(p)==h for p,h in original['prior_evidence_hashes'].items()}
    assert len(protected)==86 and all(protected.values()) and all(prior.values())
    db=readonly_original('data/forward_scanner_v4.db')
    try:
        count=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        health=db.execute('PRAGMA quick_check').fetchone()[0]
        assert count==163 and health=='ok'
    finally:db.close()
    legacy=json.loads(Path('reports/scanner_v41_validation_20261024/legacy_reconciliation.json').read_text(encoding='utf8'))
    assert legacy['counts']['STALE_OPEN']==115 and sha(legacy['source'])==legacy['source_sha256']
    monitored=json.loads((OUT/'trend.json').read_text(encoding='utf8'))
    if monitored['running']:raise RuntimeError('Monitor still active')
    historical=json.loads(Path('reports/scanner_v47_20261025/clock_final.json').read_text(encoding='utf8'))['result']
    rows=[dict(at=historical['at'],windows=historical['windows_status']),*monitored['rows']]
    trend=root_trend(rows)
    clocks=[dict(file=p.name,**json.loads(p.read_text(encoding='utf8'))) for p in sorted(OUT.glob('clock_*.json'))]
    upstream=[dict(file=p.name,**json.loads(p.read_text(encoding='utf8'))) for p in sorted(OUT.glob('upstream_*.json'))]
    write('root_diagnosis.json',dict(at=time.time(),trend=trend,clock_checks=clocks,upstream_checks=upstream,
        interpretation='Consistent with startup/filter convergence; packet field and current offset are distinct quantities',
        exact_windows_internal_filter_state='UNVERIFIED',no_policy_relaxation=True))
    live_file=OUT/'live_result.json'
    live=json.loads(live_file.read_text(encoding='utf8')) if live_file.exists() else None
    review=review_episode(ROOT) if live else None
    if review:
        write('live_review.json',review)
        assert review['all_requests_public'] and review['live_http_attempts']==live['requests']<=260
        assert all(not r['exit']['forced_kill'] and r['exit']['worker_reaped'] and not r['summary']['close_errors'] for r in live['runs'])
        assert all(r['quick_check']=='ok' and r['duplicated_signals']==0 and r['score_nonnull']==0 for r in review['per_exchange'].values())
    tests=json.loads((OUT/'test_result.json').read_text(encoding='utf8'));assert tests['successful']
    assert all(sha(p)==h for p,h in tests['tested_source_sha256'].items())
    unchanged=['coin_analysis/forward_scanner_v4.py','coin_analysis/forward_scanner_v4_operations.py',
        'coin_analysis/scanner_candles.py','coin_analysis/forward_scanner_v42.py','coin_analysis/research_dataset_collector_v1.py',
        'coin_analysis/forward_scanner_v43.py','coin_analysis/scanner_clock_v45.py','coin_analysis/scanner_clock_v47.py',
        'coin_analysis/scanner_ntp_v46.py','coin_analysis/scanner_observation_v45.py','archive/scanner_v15.py',
        'docs/forward_surge_v3_validation_policy.json','docs/research_market_validation_v1_manifest.json']
    assert not subprocess.check_output(['git','diff','8cdc6e2','--',*unchanged],text=True).strip()
    scan=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"],capture_output=True,timeout=5)
    assert scan.returncode==0
    processes=json.loads(scan.stdout.strip() or b'[]');assert not processes
    raw={str(p):sha(p) for p in ROOT.rglob('*') if p.is_file()} if ROOT.exists() else {}
    api=json.loads((OUT/'api_preflight.json').read_text(encoding='utf8')) if (OUT/'api_preflight.json').exists() else None
    admitted=next((c for c in clocks if c['file']=='clock_recheck.json'),None)
    post=next((c for c in clocks if c['file']=='clock_post.json'),None)
    environment=json.loads((OUT/'environment_final.json').read_text(encoding='utf8'))
    assert environment['service']['State']=='Running' and environment['service']['StartMode']=='Automatic'
    assert not environment['activeScanners']
    integrity=json.loads((OUT/'db_integrity_preflight.json').read_text(encoding='utf8'))
    assert len(integrity['databases'])==4 and all(d['quick_check']=='ok' for d in integrity['databases'].values())
    assert len(clocks)<=4 and len(monitored['rows'])<=42 and monitored['elapsed_monotonic']<=2403
    if not live:
        decision=json.loads((OUT/'live_decision.json').read_text(encoding='utf8'))
        assert decision['status']=='BLOCKED' and not ROOT.exists() and api is None
    intervals=[dict(start=r['summary']['started_at'],end=r['summary']['ended_at'],
        elapsed_monotonic=r['summary']['elapsed_monotonic_seconds'],status=r['summary']['status'],reason=r['summary']['reason']) for r in live['runs']] if live else []
    actual=sum(r['elapsed_monotonic'] for r in intervals)
    if live:
        assert actual<=1200 and admitted and admitted['status']=='VERIFIED'
        assert sha(ROOT/'config.json')==json.loads((OUT/'before_resume.json').read_text(encoding='utf8'))['config_sha256']
    clocks_in_worker=[]
    if ROOT.exists():
        for path in ROOT.glob('events*.jsonl'):
            for line in path.read_text(encoding='utf8').splitlines():
                value=json.loads(line)
                if value.get('kind')=='CLOCK_CHECK':clocks_in_worker.append(value['evidence'])
    run_admissions=[json.loads(p.read_text(encoding='utf8'))['clock_admission'] for p in (ROOT/'runs').glob('*.json')
        if not (p.name.endswith('.summary.json') or p.name.endswith('.exit.json'))] if ROOT.exists() else []
    ntp_upper=6*(len(clocks)+len(clocks_in_worker)+len(run_admissions))+sum(len(u.get('rows',[])) for u in upstream)
    assert ntp_upper<=96
    if live:assert all(c['status']=='VERIFIED' for c in clocks_in_worker+run_admissions)
    write('completion_checks.json',dict(at=time.time(),status='PARTIAL',policy_changed=False,all_existing_time_limits_unchanged=True,
        windows_natural_convergence_observed=trend['consistent_with_filter_warmup'],clock_admitted=admitted['status'] if admitted else 'BLOCKED',
        post_clock=post['status'] if post else None,original_signals=count,original_quick_check=health,stale_open=115,
        final_windows_status=admitted['windows_status'] if admitted else None,service=environment['service'],
        monitor_queries=len(monitored['rows']),monitor_seconds=monitored['elapsed_monotonic'],
        independent_ntp_measured=sum(r['status']=='MEASURED' for c in clocks for r in c.get('measurement',{}).get('rows',[])),
        independent_ntp_attempts=sum(len(c.get('measurement',{}).get('rows',[])) for c in clocks),
        ntp_timeouts=[dict(file=c['file'],host=r['host'],error=r.get('error')) for c in clocks for r in c.get('measurement',{}).get('rows',[]) if r['status']!='MEASURED'],
        protected_count=86,protected_unchanged=protected,prior_evidence_unchanged=prior,tests=tests,
        live_ran=bool(live),intervals=intervals,observed_monotonic_seconds=actual,
        restart_gap_seconds=intervals[1]['start']-intervals[0]['end'] if len(intervals)==2 else None,
        new_live_signals=review['signals'] if review else 0,
        data_quality={k:review[k] for k in ('actual_source_grids','actual_source_slots','price_grids','price_slots','unknown_source_absent_slots')} if review else None,
        http_preflight_attempts=len(api['records']) if api else 0,live_http_attempts=review['live_http_attempts'] if review else 0,
        ntp_packets_upper=ntp_upper,worker_clock_checks=len(clocks_in_worker),supervisor_clock_checks=len(run_admissions),
        raw_runtime_hashes=raw,raw_runtime_bytes=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()) if ROOT.exists() else 0,
        max_rss_bytes=max((r['summary']['peak_rss_bytes'] for r in live['runs']),default=None) if live else None,
        max_cpu_percent=max((r['summary']['max_cpu_percent'] for r in live['runs']),default=None) if live else None,
        original_scanner_clock_and_research_code_unchanged=True,active_scanners=processes,
        actual_60m_completion='UNVERIFIED',actual_sleep_resume='UNVERIFIED',actual_reboot='UNVERIFIED',
        readiness_24h='NOT_READY',no_orders=True,no_system_settings_changes=True,no_windows_shutdown=True))
    print(json.dumps(dict(status='PARTIAL',live=bool(live),clock=admitted['status'] if admitted else 'BLOCKED',signals=review['signals'] if review else 0,
        original_signals=count,protected=86,prior_files=len(prior),ntp_packets_upper=ntp_upper,observed_seconds=actual)))


if __name__=='__main__':main()
