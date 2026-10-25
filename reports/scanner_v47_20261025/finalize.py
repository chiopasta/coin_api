"""Read-only completion checks; a blocked clock never launches observation."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time

from coin_analysis import forward_scanner_v43 as v

OUT=Path('reports/scanner_v47_20261025')


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def immutable(path):
    wal=Path(str(path)+'-wal')
    if wal.exists() and wal.stat().st_size:raise RuntimeError('Original has nonempty WAL; snapshot blocked')
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
    return db


def main():
    before=json.loads((OUT/'preflight.json').read_text(encoding='utf8'))
    protected={p:sha(p)==h for p,h in before['protected_hashes'].items()}
    prior={p:sha(p)==h for p,h in before['prior_evidence_hashes'].items()}
    assert len(protected)==86 and all(protected.values()) and all(prior.values())
    db=immutable('data/forward_scanner_v4.db')
    try:
        original_signals=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        original_health=db.execute('PRAGMA quick_check').fetchone()[0]
        assert original_signals==163 and original_health=='ok'
    finally:db.close()
    old_health={}
    for root in ['data/scanner_v42_live/episode_20261024_supported','data/scanner_v43_live/episode_20261024']:
        for path in Path(root).glob('*.db'):
            db=immutable(path)
            try:old_health[str(path)]=db.execute('PRAGMA quick_check').fetchone()[0]
            finally:db.close()
    assert all(h=='ok' for h in old_health.values())
    legacy=json.loads(Path('reports/scanner_v41_validation_20261024/legacy_reconciliation.json').read_text(encoding='utf8'))
    assert legacy['counts']['STALE_OPEN']==115 and sha(legacy['source'])==legacy['source_sha256']
    tests=json.loads((OUT/'test_result.json').read_text(encoding='utf8'));assert tests['successful']
    assert all(sha(p)==h for p,h in tests['tested_source_sha256'].items())
    clock=json.loads((OUT/'clock_final.json').read_text(encoding='utf8'))['result']
    assert clock['status']=='BLOCKED' and clock['reason']=='CLOCK_WINDOWS_ROOT_UNCERTAINTY'
    assert clock['external_assessment']['status']=='VERIFIED' and clock['measurement_freshness']['status']=='VERIFIED'
    command="@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name) | ConvertTo-Json -Compress"
    completed=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,timeout=5)
    assert completed.returncode==0
    scanners=json.loads(completed.stdout.decode('utf8')) if completed.stdout.strip() else []
    assert not scanners
    with tempfile.TemporaryDirectory() as folder:
        db=v.open_runtime(folder,dict(markets=v.MARKETS,signal_start=86400),'UPBIT')
        try:temporary_health=db.execute('PRAGMA quick_check').fetchone()[0]
        finally:v.ops.close_cleanly(db)
    prospective=Path('data/scanner_v43_live/episode_20261025_v47')
    assert not prospective.exists()
    frozen=['coin_analysis/forward_scanner_v4.py','coin_analysis/forward_scanner_v4_operations.py',
        'coin_analysis/scanner_candles.py','coin_analysis/forward_scanner_v42.py','coin_analysis/research_dataset_collector_v1.py',
        'coin_analysis/scanner_observation_v45.py','coin_analysis/scanner_ntp_v46.py','coin_analysis/scanner_gap_audit_v44.py',
        'archive/scanner_v15.py','docs/forward_surge_v3_validation_policy.json','docs/research_market_validation_v1_manifest.json']
    assert not subprocess.check_output(['git','diff','0fac7a5','--',*frozen],text=True).strip()
    decision=dict(at=time.time(),status='BLOCKED',reason=clock['reason'],live_started=False,
        clock_external_accuracy='PASS',clock_windows_root_distance='FAIL',original_db_health='PASS',
        prospective_db_lifecycle_test=temporary_health,duplicate_scanner_processes=scanners,
        api_preflight='SKIP_CLOCK_BLOCKED',real_order_access='FORBIDDEN_BY_UNCHANGED_PUBLIC_ALLOWLIST',
        resource_guard_tests='PASS',live_run_count=0,live_requests=0,new_live_signals=0,
        live_start=None,live_end=None,live_source_coverage=None,live_price_coverage=None,
        pending_30m_60m='N/A_NO_LIVE_SIGNALS',actual_restart='SKIP_CLOCK_BLOCKED',
        actual_60m_followup='UNVERIFIED',realtime_no_trade_evidence=0,retrospective_no_trade_added=0,
        new_observation_database_created=False,observation_path=str(prospective),no_system_changes=True)
    write('live_decision.json',decision)
    write('completion_checks.json',dict(at=time.time(),status='PARTIAL',clock_verdict='FAIL_WINDOWS_ROOT_UNCERTAINTY',
        external_clock_accuracy='PASS',original_signals=original_signals,original_quick_check=original_health,
        prior_db_quick_checks=old_health,protected_count=86,protected_unchanged=protected,prior_evidence_unchanged=prior,
        stale_open=115,tests=tests,active_scanners=scanners,live=decision,
        total_ntp_packets_max=12,ntp_basis='Two explicit diagnostics, each max6; no test or scanner traffic',
        exchange_calls=0,resource_sample=dict(rss_bytes=v.v42.rss_bytes(),free_disk_bytes=shutil.disk_usage('.').free,
            rss_limit=v.MAX_RSS,episode_limit=v.MAX_DISK,log_bytes=v.LOG_BYTES,log_copies=v.LOG_COPIES),
        frozen_detection_price_and_research_files_unchanged=True,no_orders=True,no_24h_run=True,no_windows_shutdown=True))
    print(json.dumps(dict(status='PARTIAL',clock=clock['reason'],signals=original_signals,protected=len(protected),prior_files=len(prior),tests=tests['tests_run'],live_runs=0)))


if __name__=='__main__':main()
