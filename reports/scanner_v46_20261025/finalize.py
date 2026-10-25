"""Read-only final V4.6 checks. Recheck clock once; never start LIVE."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import statistics
import subprocess
import tempfile
import time

from coin_analysis import forward_scanner_v43 as v
from coin_analysis import scanner_clock_v45 as c
from coin_analysis import scanner_ntp_v46 as n

OUT=Path('reports/scanner_v46_20261025')


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(name,value):
    with (OUT/name).open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)


def immutable(path):
    wal=Path(str(path)+'-wal')
    if wal.exists() and wal.stat().st_size:raise RuntimeError('BLOCKED: original nonempty WAL')
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    db.row_factory=sqlite3.Row
    return db


def recheck():
    write('recheck_bounds.json',dict(at=time.time(),ntp_max_packets=6,hosts=list(n.HOSTS),max_seconds=15,
        w32tm_query_only=True,exchange_http_calls=0,live_scanner_seconds=0,no_system_changes=True,
        task_max_ntp_packets_including_failed_recording=19))
    result=c.verify_clock()
    write('clock_recheck_result.json',result)  # Persist BEFORE any report parsing.
    samples=[]
    for _ in range(5):
        samples.append(dict(wall=time.time(),monotonic=time.monotonic(),awake=c.awake_seconds()))
        time.sleep(.1)
    old=json.loads((OUT/'clock_probe.json').read_text(encoding='utf8'))['ntp']
    replay=[]
    for row in old['rows']:
        replay.append(n.decode_reply(bytes.fromhex(row['response_hex']),bytes.fromhex(row['request_hex'])[40:48],
            row['local_sent_at'],row['local_received_at'],row['elapsed_monotonic_seconds']))
    comparison=[]
    for host in n.HOSTS:
        prior=[r for r in old['rows'] if r.get('host')==host and r.get('status')=='MEASURED']
        current=[r for r in result.get('measurement',{}).get('rows',[]) if r.get('host')==host and r.get('status')=='MEASURED']
        if prior and current:
            comparison.append(dict(host=host,prior_median_offset=statistics.median(r['offset_seconds'] for r in prior),
                current_median_offset=statistics.median(r['offset_seconds'] for r in current),
                local_elapsed_seconds=statistics.mean(r['local_received_at'] for r in current)-statistics.mean(r['local_received_at'] for r in prior),
                prior_max_uncertainty=max(r['uncertainty_seconds'] for r in prior),current_max_uncertainty=max(r['uncertainty_seconds'] for r in current)))
    ticks=[]
    for p in Path('data/scanner_v46_audit/20261025').glob('*ticker.json'):
        body=json.loads(p.read_text(encoding='utf8'))[0]
        named=datetime.strptime(body['trade_date']+body['trade_time'],'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).timestamp()
        ticks.append(dict(file=str(p),named_trade_utc_epoch=named,trade_timestamp=body.get('trade_timestamp'),
            numeric_trade_minus_named_seconds=body['trade_timestamp']/1000-named,
            raw_preserved=True,used_for_clock_admission=False))
    drift=(samples[-1]['wall']-samples[0]['wall'])-(samples[-1]['monotonic']-samples[0]['monotonic'])
    write('clock_recheck.json',dict(result=result,wall_monotonic_samples=samples,short_wall_monotonic_difference_seconds=drift,
        between_probes=comparison,initial_packet_replay_with_final_uncertainty_formula=replay,ticker_semantics=ticks,
        actual_sleep_test=False,live_allowed=result['status']=='VERIFIED'))
    print(json.dumps(dict(status=result['status'],reason=result['reason'],blockers=result.get('blockers'),between_probes=comparison,short_difference=drift)))


def complete():
    before=json.loads((OUT/'preflight.json').read_text(encoding='utf8'))
    protected={p:sha(p)==h for p,h in before['protected_hashes'].items()}
    prior={p:sha(p)==h for p,h in before['prior_evidence_hashes'].items()}
    assert len(protected)==86 and all(protected.values()) and all(prior.values())
    source=immutable('data/forward_scanner_v4.db')
    try:
        count=source.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        health=source.execute('PRAGMA quick_check').fetchone()[0]
        assert count==163 and health=='ok'
    finally:source.close()
    legacy=json.loads(Path('reports/scanner_v41_validation_20261024/legacy_reconciliation.json').read_text(encoding='utf8'))
    assert legacy['counts']['STALE_OPEN']==115 and sha(legacy['source'])==legacy['source_sha256']
    # Prospective DB lifecycle only, never migrate an old validation episode.
    with tempfile.TemporaryDirectory() as folder:
        db=v.open_runtime(folder,dict(markets=v.MARKETS,signal_start=86400),'UPBIT')
        try:new_health=db.execute('PRAGMA quick_check').fetchone()[0]
        finally:v.ops.close_cleanly(db)
    tests=json.loads((OUT/'test_result.json').read_text(encoding='utf8'));assert tests['successful']
    assert all(sha(p)==h for p,h in tests['tested_source_sha256'].items())
    frozen=['coin_analysis/forward_scanner_v4.py','coin_analysis/forward_scanner_v4_operations.py',
        'coin_analysis/scanner_candles.py','coin_analysis/forward_scanner_v42.py','coin_analysis/research_dataset_collector_v1.py',
        'archive/scanner_v15.py','docs/forward_surge_v3_validation_policy.json','docs/research_market_validation_v1_manifest.json',
        'coin_analysis/scanner_observation_v45.py','coin_analysis/scanner_gap_audit_v44.py']
    assert not subprocess.check_output(['git','diff','a61d0f6','--',*frozen],text=True).strip()
    clock=json.loads((OUT/'clock_recheck.json').read_text(encoding='utf8'))
    assert clock['result']['status']=='BLOCKED'  # Actual measured host; no unsafe LIVE fallback.
    raw={str(p):sha(p) for p in Path('data/scanner_v46_audit/20261025').glob('*.json')}
    exchange=json.loads((OUT/'exchange_clock.json').read_text(encoding='utf8'))
    assert all(sha(r['raw_file'])==r['raw_sha256'] for r in exchange['records'] if 'raw_sha256' in r)
    checks=dict(at=time.time(),status='PARTIAL',live_admission='BLOCKED',original_signals=count,original_quick_check=health,
        stale_open=115,protected_count=86,protected_unchanged=protected,prior_evidence_unchanged=prior,
        prospective_db_quick_check=new_health,clock=clock['result'],tests=tests,
        resource_sample=dict(rss_bytes=v.v42.rss_bytes(),free_disk_bytes=shutil.disk_usage('.').free,
            rss_limit_bytes=v.MAX_RSS,episode_limit_bytes=v.MAX_DISK,cpu_limit='60% of one core over >=10s sample'),
        exchange_diagnostic_requests=exchange['http_attempts'],exchange_diagnostic_successes=sum(r.get('status')==200 for r in exchange['records']),
        total_ntp_request_packets_upper=19,ntp_count_basis='initial 6 + w32tm 1 + non-durable recheck 6 + final 6; no tests use network',
        no_trade_live_ingestion='SKIP_CLOCK_BLOCKED_AND_UNBOUNDED_WORST_CASE_COST',no_trade_trade_api_calls=0,
        raw_hashes=raw,frozen_detection_price_policy_and_research_files_unchanged=True,
        actual_live_runs=0,new_live_signals=None,actual_60m_followup='UNVERIFIED',actual_sleep_resume='UNVERIFIED',
        no_system_changes=True,no_orders=True,no_windows_shutdown=True)
    write('completion_checks.json',checks)
    print(json.dumps(dict(status='PARTIAL',signals=count,protected=len(protected),prior_files=len(prior),tests=tests['tests_run'],all_preserved=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['recheck','complete'])
    globals()[parser.parse_args().stage]()
