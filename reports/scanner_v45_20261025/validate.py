"""Bounded offline V4.5 evidence. Original DBs opened immutable, no HTTP.

Run preflight -> compare -> selected tests -> completion. Never overwrite evidence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

from coin_analysis import scanner_clock_v45 as clock
from coin_analysis import scanner_observation_v45 as price
from coin_analysis import scanner_gap_audit_v44 as audit

OUT=Path('reports/scanner_v45_20261025')
OLD=Path('reports/scanner_v44_20261025')
ROOT=Path('data/scanner_v43_live/episode_20261024')
LEGACY=Path('reports/scanner_v41_validation_20261024/legacy_reconciliation.json')


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(name,payload):
    with (OUT/name).open('x',encoding='utf8') as stream:
        json.dump(payload,stream,ensure_ascii=False,allow_nan=False,indent=2)


def immutable(path):
    # Only stopped old snapshots with EMPTY WAL; do not silently ignore a WAL.
    wal=Path(str(path)+'-wal')
    if wal.exists() and wal.stat().st_size:
        raise ValueError('BLOCKED: nonempty original WAL; no immutable snapshot')
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    db.row_factory=sqlite3.Row
    return db


def preflight():
    manifest=json.loads(Path('reports/scanner_v41_validation_20261024/input_manifest.json').read_text())['inputs']
    protected={p:sha(p) for p in manifest}
    assert len(protected)==86 and all(protected[p]==r['sha256'] for p,r in manifest.items())
    files={str(p):sha(p) for folder in ('data/scanner_v42_live/episode_20261024_supported',
           str(ROOT),'data/scanner_v44_audit/20261025',str(OLD)) for p in Path(folder).rglob('*') if p.is_file()}
    legacy=json.loads(LEGACY.read_text());assert legacy['counts']['STALE_OPEN']==115
    files[str(LEGACY)]=sha(LEGACY);files[legacy['source']]=sha(legacy['source'])
    assert files[legacy['source']]==legacy['source_sha256']
    write('preflight.json',dict(at=time.time(),baseline_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        protected_hashes=protected,prior_evidence_hashes=files,
        bounds=dict(exchange_api_calls=0,scanner_seconds=0,clock_reference='time.windows.com',
                    clock_max_samples=3,clock_max_seconds=15,no_clock_or_service_change=True),
        clock=clock.verify_clock()))


def compare():
    old=json.loads((OLD/'final_summary.json').read_text())
    probe=json.loads((OLD/'probe.json').read_text());validated=audit.source_evidence(probe)
    asof=max(r['received_at'] for r in probe['records'])
    rows=[];grids=[];forward=[];unique={}
    for exchange in audit.observer.v42.HOSTS:
        source=immutable(ROOT/(exchange.lower()+'.db'));db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        try:
            source.backup(db);price.schema(db)
            before=audit.observer.ops.full_fingerprints(source)
            for gap in old['unique_missing_minutes']:
                if gap['exchange']!=exchange:continue
                m,ts=gap['market'],gap['ts'];proof=validated[(exchange,m)]
                assert not proof['errors'] and proof['candle_range_verified']
                cause=audit.classify_gap(ts,asof,api_absence_confirmed=(proof['lower']<=ts<proof['upper'] and ts not in proof['minute']),trade_evidence=proof['trades'])
                assert cause=='NO_TRADE'
                known=max(r['received_at'] for r in probe['records'] if r['exchange']==exchange and r['params']['market']==m)
                with db:db.execute('INSERT INTO no_trade_evidence_v45 VALUES(?,?,?,?)',
                    (m,ts,known,json.dumps(dict(probe_sha256=sha(OLD/'probe.json'),basis='V44 independently reconciled ticks and native candles'))))
            for win in old['per_exchange'][exchange]['windows']:
                m,t=win['market'],win['t'];points=[]
                for ts in range(t-1800,t,60):
                    current=price.price_point(db,m,ts+60,asof)
                    contemporaneous=price.price_point(db,m,ts+60,t+win['processing_lag_seconds'])
                    row=dict(exchange=exchange,market=m,grid_t=t,ts=ts,retrospective=current,
                             contemporaneous_status=contemporaneous['status'])
                    points.append(row);rows.append(row);unique[(exchange,m,ts)]=row
                grids.append(dict(exchange=exchange,market=m,t=t,actual_candle_complete=win['complete'],
                    price_complete_retrospective=all(p['retrospective']['status']=='AVAILABLE' for p in points),
                    contemporaneous_price_complete=all(p['contemporaneous_status']=='AVAILABLE' for p in points),
                    unavailable=Counter(p['retrospective']['reason'] for p in points if p['retrospective']['status']!='AVAILABLE')))
                verified=db.execute('SELECT verified_until FROM scanner_state WHERE market=?',(m,)).fetchone()[0]
                stamps={r[0] for r in db.execute('SELECT ts FROM minute_candles WHERE market=?',(m,))}
                for minutes in (30,60):
                    endpoint=price.price_point(db,m,t+minutes*60,asof)
                    if verified<t+minutes*60:endpoint.update(status='UNAVAILABLE',reason='FORWARD_RANGE_NOT_COLLECTED',price=None)
                    full=audit.forward_readiness(t,minutes,asof,verified,stamps)
                    forward.append(dict(exchange=exchange,market=m,t=t,minutes=minutes,
                        actual_path_status=full['status'],actual_path_reason=full['reason'],endpoint=endpoint))
            after=audit.observer.ops.full_fingerprints(db)
            assert all(after[table]==value for table,value in before.items())
            assert before==audit.observer.ops.full_fingerprints(source)
        finally:db.close();source.close()
    result=dict(at=time.time(),knowledge_asof=asof,retrospective_only=True,policy=price.POLICY,
        price_age_upper_bound_seconds=price.MAX_PRICE_AGE_SECONDS,
        actual_candle_grids=dict(numerator=sum(g['actual_candle_complete'] for g in grids),denominator=len(grids)),
        actual_candle_slots=old['after'],http=old['old_http'],
        no_trade_slots=old['cause_counts_slots']['NO_TRADE'],no_trade_unique_minutes=old['cause_counts_unique']['NO_TRADE'],
        price_slots=dict(available=sum(r['retrospective']['status']=='AVAILABLE' for r in rows),denominator=len(rows),
            derived=sum(r['retrospective']['basis']=='DERIVED_NO_TRADE_LAST_CLOSE' for r in rows),
            reasons=Counter(r['retrospective']['reason'] for r in rows if r['retrospective']['status']!='AVAILABLE'),
            contemporaneous_available=sum(r['contemporaneous_status']=='AVAILABLE' for r in rows)),
        price_unique=dict(available=sum(r['retrospective']['status']=='AVAILABLE' for r in unique.values()),denominator=len(unique)),
        price_complete_grids=dict(numerator=sum(g['price_complete_retrospective'] for g in grids),denominator=len(grids)),
        original_signals=0,actual_signal_followup_rate=None,
        diagnostic_forward={str(h):dict(denominator=16,actual_path_complete=sum(r['minutes']==h and r['actual_path_status']=='COMPLETE' for r in forward),
            price_endpoint_complete=sum(r['minutes']==h and r['endpoint']['status']=='AVAILABLE' for r in forward)) for h in (30,60)},
        grids=grids,slots=rows,diagnostic_forward_details=forward,
        original_tables_preserved=True,new_exchange_calls=0,new_live_runs=0)
    assert result['actual_candle_grids']==dict(numerator=4,denominator=16)
    write('comparison.json',result)
    print(json.dumps({k:result[k] for k in ['actual_candle_grids','price_slots','price_unique','price_complete_grids','diagnostic_forward']}))


def completion():
    before=json.loads((OUT/'preflight.json').read_text())
    protected={p:sha(p)==h for p,h in before['protected_hashes'].items()}
    prior={p:sha(p)==h for p,h in before['prior_evidence_hashes'].items()}
    assert all(protected.values()) and all(prior.values())
    db=immutable('data/forward_scanner_v4.db')
    try:
        count=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0];assert count==163
        health=db.execute('PRAGMA quick_check').fetchone()[0];assert health=='ok'
    finally:db.close()
    frozen=['coin_analysis/forward_scanner_v4.py','coin_analysis/forward_scanner_v4_operations.py',
            'coin_analysis/scanner_candles.py','coin_analysis/forward_scanner_v42.py',
            'coin_analysis/research_dataset_collector_v1.py','archive/scanner_v15.py',
            'docs/forward_surge_v3_validation_policy.json','docs/research_market_validation_v1_manifest.json']
    unchanged=not subprocess.check_output(['git','diff','44eb07d','--',*frozen],text=True).strip();assert unchanged
    tests=json.loads((OUT/'test_result.json').read_text());assert tests['successful']
    assert all(sha(p)==h for p,h in tests['tested_source_sha256'].items())
    write('completion_checks.json',dict(at=time.time(),status='PARTIAL',
        original_signals=count,original_quick_check=health,protected_input_count=len(protected),protected_unchanged=protected,
        prior_evidence_unchanged=prior,stale_open=115,frozen_detection_and_research_code_unchanged=unchanged,
        selective_tests=tests,no_exchange_api_calls=True,no_live_scanner=True,no_orders=True,no_windows_shutdown=True,
        limits=['Clock admission BLOCKED on this host','No actual 24h or OS reboot',
                'No natural signal 60m completion','Live NO_TRADE evidence ingestion SKIP; source absence stays unknown']))
    print(json.dumps(dict(signals=count,protected=len(protected),prior_files=len(prior),all_preserved=True)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['preflight','compare','completion'])
    globals()[parser.parse_args().stage]()
