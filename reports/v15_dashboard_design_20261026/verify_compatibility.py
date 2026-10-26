"""Offline design evidence only; never starts a scanner, analyzer main, or API.

Source DBs are SELECT-only. All V15 function writes target :memory:.
Run from repository root: python reports/v15_dashboard_design_20261026/verify_compatibility.py
"""
import ast
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import struct
import sys
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent


def extract(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def inspect_source(path, active=False):
    # No backup, dump, full integrity scan, BEGIN, retry loop, or WAL operation.
    started = time.monotonic()
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro' +
                                 ('' if active else '&immutable=1'), uri=True, timeout=.1)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.monotonic() - started > .25), 1000)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        schema = {t: [r[1] for r in db.execute(f'PRAGMA table_info("{t}")')]
                  for t in tables if t != 'sqlite_sequence'}
        counts = {t: db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                  for t in schema}
        scores = dict(db.execute('SELECT typeof(score),COUNT(*) FROM signals GROUP BY typeof(score)'))
        rows = [dict(r) for r in db.execute('SELECT * FROM signals ORDER BY id LIMIT 2000')]
        history = [dict(r) for r in db.execute('SELECT * FROM signal_price_history ORDER BY signal_id,minute LIMIT 120000')]
        paper = dict(db.execute('SELECT status,COUNT(*) FROM pullback_paper_trades GROUP BY status'))
        paper_rows = [dict(r) for r in db.execute('SELECT * FROM pullback_paper_trades ORDER BY id LIMIT 2000')]
    # Each statement has its own short read transaction; counts are not an atomic live snapshot.
    return dict(path=str(path), active=active, at=datetime.now().astimezone().isoformat(),
                elapsed_ms=round((time.monotonic()-started)*1000, 3), schema=schema,
                counts=counts, score_storage_types=scores, paper_status=paper), rows, history, paper_rows


def main():
    evidence = dict(at=datetime.now().astimezone().isoformat(), network_calls=0,
                    scanner_starts=0, source_db_writes=0, optimization_runs=0)
    legacy = ROOT / 'data/backups/v42_preflight_20261024/legacy.db'
    live = ROOT / 'archive/crypto_scanner.db'
    sources = []
    datasets = []
    for path, active in [(legacy, False), (live, True)]:
        if not path.exists():
            sources.append(dict(path=str(path), error='MISSING'))
            continue
        try:
            info, rows, histories, paper_rows = inspect_source(path, active)
            sources.append(info)
            datasets.append((info, rows, histories, paper_rows))
        except sqlite3.Error as exc:
            sources.append(dict(path=str(path), error=str(exc), action='No retry; source untouched'))
    evidence['sources'] = sources

    v7 = extract(Path('C:/dev/Coin_api/db_analyzer_v7.py'),
                 ['as_int', 'as_float', 'schema_check', 'load_trades', 'load_histories', 'basic_stats'],
                 dict(math=math, struct=struct))
    score = extract(ROOT/'archive/scanner_v15.py', ['calculate_score'], {})['calculate_score']
    comparisons = []
    for info, rows, histories, paper_rows in datasets:
        # Create a private projection, never give analyzer functions a source connection.
        with closing(sqlite3.connect(':memory:')) as private:
            private.row_factory = sqlite3.Row
            for table, cols in info['schema'].items():
                private.execute(f'CREATE TABLE "{table}" (' + ','.join(f'"{c}"' for c in cols) + ')')
            for table, records in [('signals', rows), ('signal_price_history', histories),
                                   ('pullback_paper_trades', paper_rows)]:
                cols = info['schema'][table]
                private.executemany(f'INSERT INTO "{table}" VALUES(' + ','.join('?' for _ in cols)+')',
                                    [tuple(r[c] for c in cols) for r in records])
            v7['schema_check'](private)
            decoded = v7['load_histories'](private)
            trades = v7['load_trades'](private)
            comparisons.append(dict(path=info['path'], v7_schema='PASS',
                                    decoded_history_signals=len(decoded), decoded_paper_trades=len(trades),
                                    v51_required_columns_missing=sorted(
                                        {'signal_id','signal_time','signal_price','detected_at','source'}-
                                        set(info['schema']['signals'])),
                                    minute_candles_missing='minute_candles' not in info['schema']))
        checked = mismatches = invalid = 0
        for r in rows:
            try:
                args = [v7['as_float'](r[k]) for k in ('volume_5m','volume_15m','volume_60m',
                                                       'price_1m','price_5m','price_15m')]
                expected = score(*args)
                actual = v7['as_int'](r['score'])
                checked += 1
                mismatches += actual != expected
            except (ValueError, TypeError, OverflowError):
                invalid += 1
        comparisons[-1].update(score_checked=checked, score_mismatches=mismatches,
                               score_invalid=invalid,
                               interpretation='Formula consistency only; not raw-feed replay or profitability evidence')

        metrics = {}
        by_id = {}
        for h in histories:
            by_id.setdefault(v7['as_int'](h['signal_id']), {})[v7['as_int'](h['minute'])] = h
        for horizon in (5,10,30,60):
            saved = paired = gaps = mismatched = 0
            for r in rows:
                ret = v7['as_float'](r[f'return_{horizon}m'])
                if ret is None or not math.isfinite(ret):
                    continue
                saved += 1
                hist = by_id.get(v7['as_int'](r['id']), {})
                if not all(m in hist for m in range(horizon+1)):
                    gaps += 1
                if horizon in hist:
                    endpoint = v7['as_float'](hist[horizon]['price'])
                    origin = v7['as_float'](r['price'])
                    if endpoint and origin and origin > 0:
                        paired += 1
                        mismatched += not math.isclose(ret, (endpoint/origin-1)*100, abs_tol=1e-8)
            metrics[str(horizon)] = dict(saved_returns=saved, endpoint_price_pairs=paired,
                                        endpoint_formula_mismatches=mismatched,
                                        saved_returns_with_missing_minute_samples=gaps)
        comparisons[-1]['surge_saved_metric_coverage'] = metrics
    evidence['compatibility'] = comparisons

    # Exact existing V15 functions with private DB and controlled clock, no top-level import.
    with closing(sqlite3.connect(':memory:')) as db:
        now = [1000000.0]
        ns = dict(db=db, db_lock=threading.Lock(), datetime=datetime,
                  time=SimpleNamespace(time=lambda:now[0]), TRACK_MINUTES=60,
                  PREPUMP_CHECKPOINT_MINUTES=(180,360,720,1440,2880,4320), PREPUMP_TRACK_HOURS=72,
                  prices={'UPBIT': {'KRW-TEST':110.0}}, active_prepumps=[], active_signals=[])
        extract(ROOT/'archive/scanner_v15.py',
                ['init_database','save_signal','save_price_history','complete_checkpoint',
                 'update_prepump_tracking','track_signals','evaluate_v14_entries',
                 'update_v14_paper_trades'], ns)
        ns['init_database']()
        sid = ns['save_signal']('UPBIT','KRW-TEST',60,100,1,2,3,10,5,2,'private fixture')
        for minute, price in [(0,100),(5,110)]:
            ns['save_price_history'](sid,minute,price,100)
        checkpoint = ns['complete_checkpoint']({'id':sid},5)
        missing_endpoint = ns['complete_checkpoint']({'id':sid},10)
        assert checkpoint is not None and math.isclose(checkpoint[0],10)
        assert missing_endpoint is None
        late_sid = ns['save_signal']('UPBIT','KRW-TEST',60,100,1,2,3,10,5,2,'late private fixture')
        late_signal = dict(id=late_sid, exchange='UPBIT',market='KRW-TEST',price=100,
                           time=now[0]-65*60,done5=False,done10=False,done30=False,done60=False,
                           last_history_minute=-1,v14_enabled=False)
        ns['active_signals'].append(late_signal)
        ns['track_signals']()
        late = db.execute('SELECT minute,price FROM signal_price_history WHERE signal_id=?',
                          (late_sid,)).fetchone()
        late_return = db.execute('SELECT return_60m FROM signals WHERE id=?',(late_sid,)).fetchone()[0]
        assert late[0] == 60 and math.isclose(late_return,10)
        db.execute('INSERT INTO prepump_tracking(event_id,highest_price,lowest_price) VALUES(1,100,100)')
        ns['active_prepumps'].append(dict(id=1,exchange='UPBIT',market='KRW-TEST',price=100,
                                        time=now[0]-7*3600,highest_price=100,lowest_price=100,done=set()))
        ns['update_prepump_tracking']()
        delayed = db.execute('SELECT return_3h,return_6h,return_12h FROM prepump_tracking').fetchone()
        assert math.isclose(delayed[0],10) and delayed[0] == delayed[1] and delayed[2] is None
        evidence['private_function_checks'] = dict(
            surge_sparse_minutes=[0,5], surge_checkpoint_5m=list(checkpoint),
            surge_missing_endpoint_10m=missing_endpoint,
            surge_first_observation_at_elapsed_minutes=65,
            surge_late_saved_minute=late[0], surge_late_saved_60m_return=late_return,
            prepump_first_observation_at_elapsed_hours=7,
            prepump_saved_returns_3h_6h_12h=list(delayed),
            result='PASS', data='SYNTHETIC private fixtures; not market performance')

    from coin_analysis import scanner_dashboard_v50 as dashboard
    with closing(sqlite3.connect(':memory:')) as private:
        private.row_factory=sqlite3.Row
        private.execute('CREATE TABLE signals(id,created_at,exchange,market,score,price)')
        private.execute("INSERT INTO signals VALUES(1,'2026-10-26 00:00:00','UPBIT','KRW-TEST',60,100)")
        try:
            dashboard.signal_view(private, private.execute('SELECT * FROM signals').fetchone(),
                                  'legacy',dict(exchange='UPBIT',archive=False,root=None),None,{'signals'})
        except (IndexError, KeyError, sqlite3.Error) as exc:
            evidence['direct_v51_view_probe'] = dict(result='EXPECTED_INCOMPATIBLE',
                                                    exception=type(exc).__name__, message=str(exc))
        else:
            raise AssertionError('Unexpected direct legacy view compatibility')
    evidence['analyzer_inventory'] = [str(p) for folder in [ROOT,Path('C:/dev/Coin_api')]
                                      for p in folder.rglob('*.py')
                                      if 'analyzer' in p.name.lower() and '__pycache__' not in p.parts]
    (OUT/'compatibility_results.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,
                                                           allow_nan=False),encoding='utf-8')
    print(json.dumps(dict(result='PASS',sources=[s.get('counts',s.get('error')) for s in sources],
                          comparisons=comparisons),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
