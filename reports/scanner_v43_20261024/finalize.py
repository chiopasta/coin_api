"""Read-only short LIVE review; no HTTP, no old performance recomputation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

from coin_analysis import forward_scanner_v43 as v
from coin_analysis.forward_scanner_v42_review import events_at, EVENT_POLICY

OUT=Path('reports/scanner_v43_20261024')
ROOT=Path('data/scanner_v43_live/episode_20261024')


def sha(path):
    with open(path,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    if (OUT/'summary.json').exists():raise RuntimeError('Never overwrite final evidence')
    runs=sorted([json.loads(p.read_text(encoding='utf8')) for p in (ROOT/'runs').glob('*.summary.json')],key=lambda r:r['started_at'])
    assert len(runs)==2
    exits=[json.loads((ROOT/'runs'/f"{r['run_id']}.exit.json").read_text()) for r in runs]
    assert all(e['worker_reaped'] and not e['forced_kill'] for e in exits)
    assert all(not r['close_errors'] for r in runs)
    before=json.loads((OUT/'pre_resume.json').read_text())
    assert before['config_sha256']==sha(ROOT/'config.json')
    config=json.loads((ROOT/'config.json').read_text());v.validate_config(config)
    with v.ops.readonly(ROOT/'control.db') as ledger:
        http=dict(attempts=ledger.execute('SELECT COUNT(*) FROM http_attempts').fetchone()[0],
            statuses=dict(ledger.execute('SELECT status,COUNT(*) FROM http_attempts GROUP BY status')),
            per_run=dict(ledger.execute('SELECT run_id,COUNT(*) FROM http_attempts GROUP BY run_id')),
            quick_check=ledger.execute('PRAGMA quick_check').fetchone()[0])
    assert http['attempts']==sum(r['requests'] for r in runs)
    per_exchange={};backup=Path('data/backups/v43_pre_resume_20261024')
    for e in v.v42.HOSTS:
        with v.ops.readonly(ROOT/(e.lower()+'.db')) as db, v.ops.readonly(backup/(e.lower()+'.db')) as old:
            preserved={}
            for table in ('minute_candles','signals','signal_features','live_signal_details','candle_receipts','coverage_windows','signal_context','scanner_sessions','scanner_cycles','collection_pages'):
                current={tuple(r) for r in db.execute('SELECT * FROM '+table)}
                preserved[table]=all(tuple(r) in current for r in old.execute('SELECT * FROM '+table))
            assert all(preserved.values()),preserved
            states=[dict(r) for r in db.execute('SELECT * FROM scanner_state')]
            prior={r['market']:r for r in before['databases'][e]['state']}
            progress={r['market']:dict(verified_non_decreasing=r['verified_until']>=prior[r['market']]['verified_until'],
                       observation_non_decreasing=r['last_observation']>=prior[r['market']]['last_observation']) for r in states}
            assert all(all(p.values()) for p in progress.values())
            end=min(r['verified_until'] for r in states)
            signals=[dict(r) for r in db.execute('SELECT * FROM signals')]
            research=v.scanner.load_research(db,config['signal_start']-v.scanner.WARMUP,end)
            events={}
            for target in (5,10):
                eligible=0;cases=[]
                for market,series in research.panel.items():
                    r=events_at(series,[s for s in signals if s['market']==market],config['signal_start'],end,target)
                    eligible+=r['eligible_full_future_anchors'];cases.extend(dict(market=market,**x) for x in r['events'])
                events[str(target)]=dict(eligible_full_future_anchors=eligible,cases=cases,recall_pct=None if not cases else 'EXPLORATORY_ONLY')
            per_exchange[e]=dict(quick_check=db.execute('PRAGMA quick_check').fetchone()[0],
                cohort_markets=len(states),states=states,common_verified_until=end,
                candle_counts=[dict(r) for r in db.execute('SELECT market,COUNT(*) AS total,SUM(ts>=?) AS after_signal_start FROM minute_candles GROUP BY market',(config['signal_start'],))],
                coverage=[dict(r) for r in db.execute('SELECT minutes,status,COUNT(*) AS n FROM coverage_windows GROUP BY minutes,status')],
                coverage_by_market=[dict(r) for r in db.execute('SELECT market,minutes,status,COUNT(*) AS n FROM coverage_windows GROUP BY market,minutes,status')],
                signal_count=len(signals),source_counts=dict(Counter(r['source'] for r in signals)),
                signal_details=[dict(r) for r in db.execute('SELECT * FROM live_signal_details')],
                signal_context=[dict(r) for r in db.execute('SELECT * FROM signal_context')],
                horizons=[dict(r) for r in db.execute('SELECT * FROM live_horizons')],events=events,
                sessions=[dict(r) for r in db.execute('SELECT * FROM scanner_sessions ORDER BY rowid')],
                cycle_statuses=dict(db.execute('SELECT status,COUNT(*) FROM scanner_cycles GROUP BY status')),
                pending_jobs=db.execute('SELECT COUNT(*) FROM collection_jobs').fetchone()[0],
                collection_errors=[dict(r) for r in db.execute('SELECT market,last_error FROM scanner_state WHERE last_error IS NOT NULL')],
                late_candles=db.execute('SELECT COUNT(*) FROM scanner_late_candles').fetchone()[0],
                future_candles_at_stop=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts+60>?',(int(runs[-1]['ended_at']),)).fetchone()[0],
                timestamp_errors=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts%60<>0').fetchone()[0],
                duplicate_signals=db.execute('SELECT COUNT(*) FROM (SELECT market,signal_time,COUNT(*) AS n FROM signals GROUP BY market,signal_time HAVING n>1)').fetchone()[0],
                prior_append_only_rows_preserved=preserved,progress_preserved=progress)
    manifest=json.loads(Path('reports/scanner_v41_validation_20261024/input_manifest.json').read_text())
    protected={p:sha(p)==r['sha256'] for p,r in manifest['inputs'].items()};assert len(protected)==86 and all(protected.values())
    diagnosis=json.loads((OUT/'diagnosis.json').read_text())
    # WAL/SHM are SQLite coordination, not raw candle/research inputs. Preserve
    # their exact hashes too here; all old readers have already been closed.
    v42_preserved={p:sha(p)==h for p,h in diagnosis['v42_runtime_hashes'].items()}
    assert all(v42_preserved.values()),v42_preserved
    with v.ops.readonly('data/forward_scanner_v4.db') as original:
        original_count=original.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        integrity=original.execute('PRAGMA quick_check').fetchone()[0]
    assert original_count==163 and integrity=='ok'
    core_files=['coin_analysis/forward_scanner_v4.py','coin_analysis/forward_scanner_v4_operations.py','coin_analysis/scanner_candles.py','coin_analysis/forward_scanner_v42.py','coin_analysis/research_dataset_collector_v1.py','archive/scanner_v15.py']
    unchanged=not subprocess.check_output(['git','diff','--name-only','ff81f5c','--',*core_files],text=True).strip();assert unchanged
    result=dict(finalized_at=time.time(),status='PARTIAL',performance_verdict='INSUFFICIENT_DATA',
        runtime=str(ROOT),config=config,runs=runs,exits=exits,http=http,task_http_including_diagnosis=http['attempts']+diagnosis['http_attempts'],
        observed_process_seconds=sum(r['ended_at']-r['started_at'] for r in runs),
        unobserved_restart_gap_seconds=runs[1]['started_at']-runs[0]['ended_at'],
        event_policy=EVENT_POLICY,per_exchange=per_exchange,original_signals=original_count,original_quick_check=integrity,
        protected_inputs_unchanged=protected,v42_runtime_preserved=v42_preserved,frozen_code_unchanged=unchanged,
        raw_runtime_bytes=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),
        raw_runtime_hashes={str(p):sha(p) for p in ROOT.rglob('*') if p.is_file()},
        no_24h_run=True,no_orders=True,cohorts_not_merged=True,
        limitations=['Short real run; no real 60m natural signal completion unless explicitly present',
            'No full market denominator','Native absent candles remain NULL','No real reboot or sustained external outage test'])
    v.write_json(OUT/'summary.json',result)
    print(json.dumps(dict(status=result['status'],signals=sum(r['signal_count'] for r in per_exchange.values()),
        http=result['task_http_including_diagnosis'],process_seconds=result['observed_process_seconds'],
        coverage={e:r['coverage'] for e,r in per_exchange.items()})))


if __name__=='__main__':main()
