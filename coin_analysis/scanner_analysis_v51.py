"""Stored-price analysis, using the frozen V4.2 horizon evaluator.

Source databases are read only. Evaluation runs on small in-memory projections;
only this dashboard's derived cache is written. No collector, network or labels.
"""
from contextlib import closing
import json
import math
from pathlib import Path
import sqlite3
import threading
import time

from . import scanner_dashboard_v50 as dashboard

MINUTES = (5, 15, 30, 60)
COHORTS = ('ARCHIVE_LIVE', 'ARCHIVE_CATCHUP', 'OBSERVATION_LIVE', 'OBSERVATION_CATCHUP')


def cohort(row):
    return ('ARCHIVE_' if row['scope'] == 'ARCHIVE' else 'OBSERVATION_') + row['source']


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def evaluate(db, row, exchange, available, now):
    """Reuse record_metrics; never update the source or its frozen outcomes."""
    if 'scanner_state' not in available:
        result = dashboard.horizon_view(db, row, available)
    else:
        with closing(sqlite3.connect(':memory:')) as work:
            work.row_factory = sqlite3.Row
            work.executescript('''
                CREATE TABLE signals(signal_id TEXT,market TEXT,signal_time INTEGER,
                  signal_price REAL,detected_at INTEGER);
                CREATE TABLE minute_candles(ts INTEGER,market TEXT,high REAL,low REAL,close REAL);
                CREATE TABLE scanner_state(market TEXT,verified_until INTEGER);
            ''')
            work.execute('INSERT INTO signals VALUES(?,?,?,?,?)', tuple(row[k] for k in
                         ('signal_id', 'market', 'signal_time', 'signal_price', 'detected_at')))
            bars = db.execute('SELECT ts,market,high,low,close FROM minute_candles '
                              'WHERE market=? AND ts>=? AND ts<? AND ts+60<=? ORDER BY ts',
                              (row['market'], row['signal_time'], row['signal_time'] + 3600, now)).fetchall()
            work.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?)', map(tuple, bars))
            state = db.execute('SELECT verified_until FROM scanner_state WHERE market=?',
                               (row['market'],)).fetchone()
            work.execute('INSERT INTO scanner_state VALUES(?,?)', (row['market'], state[0] if state else 0))
            engine = dashboard.control.observer.v42
            engine.observation_schema(work)
            if 'live_horizons' in available:
                saved = db.execute('SELECT signal_id,minutes,status,observed_minutes,reason,'
                                   'return_pct,mfe_pct,mae_pct,evaluated_at FROM live_horizons '
                                   'WHERE signal_id=?', (row['signal_id'],)).fetchall()
                work.executemany('INSERT INTO live_horizons VALUES(?,?,?,?,?,?,?,?,?)', map(tuple, saved))
            work.commit()
            engine.record_metrics(work, exchange, now)
            result = [dict(r, basis='EXISTING_HORIZON_ENGINE') for r in work.execute(
                'SELECT * FROM live_horizons ORDER BY minutes')]
    output = []
    for metric in result:
        h = {k: metric.get(k) for k in ('minutes', 'status', 'return_pct', 'mfe_pct', 'mae_pct',
                                       'observed_minutes', 'basis')}
        if now < row['signal_time'] + h['minutes'] * 60:
            h.update(status='PENDING', return_pct=None, mfe_pct=None, mae_pct=None)
        elif h['status'] != 'COMPLETE':
            h.update(status='INSUFFICIENT_DATA', return_pct=None, mfe_pct=None, mae_pct=None)
        for key in ('return_pct', 'mfe_pct', 'mae_pct'):
            if not finite(h[key]):
                h[key] = None
        output.append(h)
    return output


def stats(rows):
    def values(minutes, key):
        return [h[key] for r in rows for h in r['horizons']
                if h['minutes'] == minutes and h['status'] == 'COMPLETE' and finite(h.get(key))]

    def average(items):
        return dict(value=sum(items) / len(items) if items else None, n=len(items))

    returns = values(30, 'return_pct')
    return dict(total=len(rows), analyzed=sum(any(h['status'] == 'COMPLETE' and finite(h.get('return_pct'))
                                                for h in r['horizons']) for r in rows),
                return_30m=average(returns),
                rise_30m=dict(value=100 * sum(v > 0 for v in returns) / len(returns) if returns else None,
                              n=len(returns)),
                mfe_30m=average(values(30, 'mfe_pct')), mae_30m=average(values(30, 'mae_pct')),
                curve=[dict(minutes=m, **average(values(m, 'return_pct'))) for m in MINUTES])


class Analysis:
    def __init__(self, path=None):
        self.path = Path(path) if path else dashboard.control.DATA_DIR / 'scanner_dashboard_v50' / 'analysis.db'
        self.lock = threading.Lock()
        self.rows = []
        self.errors = ['저장된 후속 평가를 읽고 있습니다.']
        self.at = None
        self.stopped = threading.Event()
        self.thread = None

    def refresh(self):
        rows, errors = [], []
        now = int(time.time())
        for key, source in dashboard.catalog().items():
            try:
                with dashboard.readonly(source['path'], source['archive']) as db:
                    available = dashboard.tables(db)
                    for row in db.execute('SELECT * FROM signals ORDER BY detected_at DESC').fetchall():
                        value = dashboard.signal_view(db, row, key, source, None, available)
                        value['horizons'] = evaluate(db, row, source['exchange'], available, now)
                        value['cohort'] = cohort(value)
                        rows.append(value)
            except (OSError, ValueError, sqlite3.DatabaseError, TypeError):
                errors.append(f"{source['exchange']} {'연구 보관' if source['archive'] else '관측'} 자료 일부를 읽지 못했습니다.")
        rows.sort(key=lambda r: (r['detected_at'] or 0, r['dataset'], r['signal_id']), reverse=True)
        # Cache is separate from every source DB. Re-read incomplete source data
        # after restart and each refresh; no persisted PENDING is treated as final.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=.5)) as cache, cache:
            cache.execute('CREATE TABLE IF NOT EXISTS evaluations('
                          'dataset TEXT,signal_id TEXT,payload TEXT,PRIMARY KEY(dataset,signal_id))')
            for row in rows:
                payload = json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True)
                cache.execute('INSERT INTO evaluations VALUES(?,?,?) ON CONFLICT(dataset,signal_id) '
                              'DO UPDATE SET payload=excluded.payload WHERE payload!=excluded.payload',
                              (row['dataset'], row['signal_id'], payload))
        with self.lock:
            self.rows, self.errors, self.at = rows, errors, now

    def start(self):
        def run():
            while not self.stopped.is_set():
                try:
                    self.refresh()
                except Exception:
                    with self.lock:
                        self.errors = ['평가 갱신에 실패했습니다. 마지막 조회 자료입니다.']
                if self.stopped.wait(5):break
        self.thread = threading.Thread(target=run, name='stored-price-evaluation', daemon=True)
        self.thread.start()

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(10)

    def report(self, group='ARCHIVE_LIVE', offset=0):
        if group not in (*COHORTS, 'ALL') or offset < 0:
            raise LookupError('Unknown analysis group')
        with self.lock:
            rows = [r for r in self.rows if group == 'ALL' or r['cohort'] == group]
            patterns = sorted({(r['cohort'], r['pattern']) for r in rows})
            return dict(summary=stats(rows), patterns=[dict(cohort=c, pattern=p,
                        **stats([r for r in rows if r['cohort'] == c and r['pattern'] == p]))
                        for c, p in patterns], signals=rows[offset:offset + dashboard.LIMIT],
                        offset=offset, limit=dashboard.LIMIT, at=self.at, errors=list(self.errors), group=group)

    def detail(self, key, signal_id):
        result = dashboard.View().detail(key, signal_id)
        with self.lock:
            cached = next((r for r in self.rows if r['dataset'] == key and r['signal_id'] == signal_id), None)
            if cached:
                result['horizons'] = cached['horizons']
        return result
