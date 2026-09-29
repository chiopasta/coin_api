"""Offline planning / bounded smoke / resumable Upbit research dataset collection."""
import argparse
from contextlib import closing
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import random
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request

from .paths import DATA_DIR

UTC = timezone.utc
KST = timezone(timedelta(hours=9))
STABLES = {'USDT', 'USDC', 'DAI', 'USDS', 'TUSD', 'FDUSD', 'PYUSD', 'USDE', 'USD1', 'RLUSD', 'USDG', 'JPYC', 'EURC'}
DEFAULT_MIN_COVERAGE = .60  # Reviewed T=2026-09-01 distribution: 52 eligible; choose top 50.


class CollectionBlocked(RuntimeError):
    """A shared HTTP budget/block must stop all markets, not just one."""


def iso(ts, zone=UTC):
    return datetime.fromtimestamp(ts, zone).isoformat()


def parse(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timestamp must include Z or timezone offset')
    if dt.second or dt.microsecond:
        raise ValueError('Timestamp must be minute aligned')
    return int(dt.timestamp())


class Client:
    """One shared, sequential candle/market limiter; no network at construction."""
    def __init__(self, transport=None, sleep=time.sleep, clock=time.monotonic, max_requests=None):
        self.transport = transport or self._transport
        self.sleep, self.clock = sleep, clock
        self.next_request = 0
        self.requests = self.retries = 0
        self.max_requests = max_requests

    @staticmethod
    def _transport(path, params):
        url = 'https://api.upbit.com' + path + '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'research-dataset/1'})
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read()), dict(response.headers)

    def get(self, path, **params):
        for attempt in range(5):
            self.sleep(max(0, self.next_request - self.clock()))
            if self.max_requests is not None and self.requests >= self.max_requests:
                raise CollectionBlocked('Smoke API budget exhausted')
            self.requests += 1
            self.next_request = self.clock() + .15
            try:
                body, headers = self.transport(path, params)
                remaining = next((v for k, v in headers.items() if k.lower() == 'remaining-req'), '')
                parts = dict(p.strip().split('=', 1) for p in remaining.split(';') if '=' in p)
                if parts.get('sec', '').isdigit() and int(parts['sec']) <= 1:
                    self.next_request = max(self.next_request, self.clock() + 1.1)
                if not isinstance(body, list):
                    raise ValueError('Expected API list response')
                return body
            except (urllib.error.URLError, TimeoutError) as exc:
                code = getattr(exc, 'code', None)
                if isinstance(exc, urllib.error.HTTPError):
                    exc.close()
                if code == 418:
                    raise CollectionBlocked('IP blocked: stop; inspect Upbit block duration before resume') from exc
                if code is not None and code not in (429, 500, 502, 503, 504):
                    raise
                if attempt == 4:
                    raise
                self.retries += 1
                retry_after = getattr(exc, 'headers', {}) or {}
                try:
                    wait = float(retry_after.get('Retry-After', 0))
                except ValueError:
                    wait = 0
                self.sleep(max(wait, min(16, 2 ** attempt) + random.uniform(0, .25)))
        raise RuntimeError('Retry exhausted')


def candle(raw):
    ts = parse(raw['candle_date_time_utc'] + 'Z')
    values = tuple(float(raw[k]) for k in ('opening_price', 'high_price', 'low_price', 'trade_price', 'candle_acc_trade_price'))
    o, h, l, c, v = values
    if not all(math.isfinite(x) for x in values) or l <= 0 or not l <= min(o, c) <= max(o, c) <= h or v < 0:
        raise ValueError('Invalid OHLC/trade value')
    return (ts,) + values


def validate_page(raw, cursor, market):
    if not raw:
        raise ValueError('Empty response: requested range is unverified')
    if len(raw) > 200 or any(r.get('market') != market for r in raw):
        raise ValueError('Invalid page size/market')
    rows = [candle(r) for r in raw]
    stamps = [r[0] for r in rows]
    if len(stamps) != len(set(stamps)) or any(t >= cursor for t in stamps):
        raise ValueError('Cursor did not move strictly backwards / duplicate timestamps')
    if stamps != sorted(stamps, reverse=True):
        raise ValueError('Unordered API page')
    return rows


def init_db(db):
    db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS minute_candles(
          market TEXT NOT NULL, ts INTEGER NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
          low REAL NOT NULL, close REAL NOT NULL, trade_value REAL NOT NULL,
          PRIMARY KEY(market,ts));
        CREATE INDEX IF NOT EXISTS idx_research_ts ON minute_candles(ts);
        CREATE TABLE IF NOT EXISTS dataset_manifest(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS collection_state(
          market TEXT PRIMARY KEY, requested_start INTEGER, requested_end INTEGER, next_cursor INTEGER,
          status TEXT, pages_completed INTEGER DEFAULT 0, rows_saved INTEGER DEFAULT 0,
          last_success_at TEXT, last_error TEXT);
        CREATE TABLE IF NOT EXISTS collection_pages(
          market TEXT, request_cursor INTEGER, verified_start INTEGER, verified_end INTEGER,
          response_count INTEGER, rows_inserted INTEGER, received_at TEXT,
          PRIMARY KEY(market,request_cursor));
        CREATE TABLE IF NOT EXISTS quality_daily(
          market TEXT, date TEXT, expected_minutes INTEGER, observed_candles INTEGER,
          coverage REAL, longest_gap INTEGER, gap_count INTEGER, verified_minutes INTEGER,
          api_absent_minutes INTEGER, unverified_minutes INTEGER,
          PRIMARY KEY(market,date));
        CREATE TABLE IF NOT EXISTS daily_crosscheck(
          market TEXT, utc_date TEXT, minute_trade_value REAL, day_trade_value REAL,
          relative_difference REAL, status TEXT, PRIMARY KEY(market,utc_date));
    ''')
    db.row_factory = sqlite3.Row


def read_manifest(db):
    row = db.execute('SELECT payload FROM dataset_manifest WHERE id=1').fetchone()
    return json.loads(row[0]) if row else None


def freeze(db, manifest):
    existing = read_manifest(db)
    if existing is not None:
        if existing != manifest:
            raise ValueError('Manifest is immutable; use a different DB for another dataset')
        return existing
    if db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0]:
        raise ValueError('Refusing to adopt an existing candle DB without a manifest')
    with db:
        db.execute('INSERT INTO dataset_manifest VALUES(1,?)', (json.dumps(manifest),))
        for m in manifest['markets']:
            db.execute('INSERT INTO collection_state(market,requested_start,requested_end,next_cursor,status) VALUES(?,?,?,?,?)',
                       (m, manifest['collection_start'], manifest['collection_end'], manifest['collection_end'], 'PENDING'))
    return manifest


def prior_day_coverage(client, market, start):
    """Inspect all of [T-24h,T); retain page evidence, never infer from one batch."""
    lower = start - 86400
    cursor, seen, pages = start, set(), []
    while cursor > lower:
        rows = validate_page(client.get('/v1/candles/minutes/1', market=market,
                                        to=iso(cursor), count=200), cursor, market)
        inside = {r[0] for r in rows if lower <= r[0] < start}
        seen.update(inside)
        oldest = rows[-1][0]
        pages.append(dict(request_cursor=cursor, oldest=oldest, newest=rows[0][0],
                          response_candles=len(rows), in_range_candles=len(inside)))
        cursor = oldest
    return dict(market=market, start_utc=iso(lower), end_exclusive_utc=iso(start),
                expected_minutes=1440, unique_minutes=len(seen), coverage=len(seen)/1440,
                page_count=len(pages), response_candles=sum(p['response_candles'] for p in pages),
                reached_window_start=cursor <= lower, final_cursor=cursor, pages=pages)


def select_markets(client, start, count, excluded=(), min_coverage=None):
    """Only completed UTC days and minute candles before T; current-list bias recorded."""
    day_end = start // 86400 * 86400
    min_coverage = DEFAULT_MIN_COVERAGE if min_coverage is None else min_coverage
    if not 0 < min_coverage <= 1:
        raise ValueError('min_coverage must be in (0,1]')
    candidates = client.get('/v1/market/all', isDetails='true')
    ranked = []
    stable_set = STABLES | set(excluded)
    for index, item in enumerate(candidates, 1):
        m = item['market']
        if not m.startswith('KRW-') or m == 'KRW-BTC' or m[4:] in stable_set:
            continue
        print(f'SELECTION daily [{index}/{len(candidates)}] {m}', flush=True)
        raw = client.get('/v1/candles/days', market=m, to=iso(day_end), count=32)
        if any(r.get('market') != m for r in raw):
            raise ValueError('Wrong market in daily selection response')
        rows = [candle(r) for r in raw]
        if len({r[0] for r in rows}) != len(rows) or any(r[0] % 86400 or r[0] >= day_end for r in rows):
            raise ValueError('Future daily data in selection response')
        if not rows or min(r[0] for r in rows) > start - 30 * 86400:
            continue
        recent = {r[0]: r for r in rows if day_end - 7 * 86400 <= r[0] < day_end}
        if set(recent) != set(range(day_end - 7 * 86400, day_end, 86400)):
            continue
        ranked.append((sum(r[5] for r in recent.values()) / 7, m))
    chosen, evidence = [], []
    for rank, (value, m) in enumerate(sorted(ranked, key=lambda x: (-x[0], x[1])),1):
        print(f'SELECTION continuity {m}; selected={len(chosen)}/{count}', flush=True)
        diagnostic = prior_day_coverage(client,m,start)
        coverage = diagnostic['coverage']
        evidence.append(dict(market=m,mean_daily_trade_value=value,prior_24h_coverage=coverage,
                             eligible_trade_value_rank=rank,selection_time=start,
                             applied_min_coverage=min_coverage,age_30d_pass=True,stable_excluded=False,
                             selected=coverage >= min_coverage,
                             selection_reason='Past trade-value rank; age>=30d; not stable; coverage passes fixed floor' if coverage>=min_coverage else 'Below fixed coverage floor',
                             coverage_diagnostic=diagnostic))
        if coverage >= min_coverage:
            chosen.append(m)
        print(f'SELECTION {m} prior coverage={coverage:.2%}; selected={len(chosen)}/{count}; '
              f'pages={diagnostic["page_count"]} response={diagnostic["response_candles"]} '
              f'unique={diagnostic["unique_minutes"]}/1440 reached_start={diagnostic["reached_window_start"]}', flush=True)
        if len(chosen) == count:
            break
    if len(chosen) != count:
        raise ValueError(f'Only {len(chosen)}/{count} eligible alts; criteria were not relaxed')
    return chosen, evidence


def collect(db, client, page_budget=None):
    began, pages = time.monotonic(), 0
    states = db.execute('SELECT * FROM collection_state ORDER BY market').fetchall()
    for index, state in enumerate(states, 1):
        m = state['market']
        if state['status'] == 'COMPLETE':
            continue
        try:
            while True:
                if page_budget is not None and pages >= page_budget:
                    return
                s = db.execute('SELECT * FROM collection_state WHERE market=?', (m,)).fetchone()
                cursor = s['next_cursor']
                rows = validate_page(client.get('/v1/candles/minutes/1', market=m, to=iso(cursor), count=200), cursor, m)
                oldest = rows[-1][0]
                selected = [(m,) + r for r in rows if s['requested_start'] <= r[0] < s['requested_end']]
                now = iso(int(time.time()))
                # Price rows, page evidence, and next cursor commit or roll back together.
                with db:
                    before = db.total_changes
                    db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?) ON CONFLICT(market,ts) DO NOTHING', selected)
                    inserted = db.total_changes - before
                    db.execute('INSERT INTO collection_pages VALUES(?,?,?,?,?,?,?)',
                               (m,cursor,max(oldest,s['requested_start']),cursor,len(rows),inserted,now))
                    db.execute('UPDATE collection_state SET next_cursor=?,status=?,pages_completed=pages_completed+1,rows_saved=rows_saved+?,last_success_at=?,last_error=NULL WHERE market=?',
                               (oldest,'COMPLETE' if oldest <= s['requested_start'] else 'RUNNING',inserted,now,m))
                pages += 1
                summary = db.execute("SELECT SUM(rows_saved),SUM(status='COMPLETE'),SUM(status='ERROR') FROM collection_state").fetchone()
                remaining = sum(math.ceil(max(0,r[0]-r[1])/60/200) for r in db.execute("SELECT next_cursor,requested_start FROM collection_state WHERE status!='COMPLETE'"))
                speed = pages / max(.001, time.monotonic()-began)
                print(f'[{index}/{len(states)} markets] {m} page {s["pages_completed"]+1} candles {s["rows_saved"]+inserted}; '
                      f'total={summary[0]} requests={client.requests} retries={client.retries} complete={summary[1]} errors={summary[2]} '
                      f'pages/s={speed:.2f} ETA~{remaining/speed/60:.1f}min', flush=True)
                if oldest <= s['requested_start']:
                    break
        except Exception as exc:
            with db:
                db.execute("UPDATE collection_state SET status='ERROR',last_error=? WHERE market=?", (str(exc),m))
            print(f'ERROR {m}: {exc}', flush=True)
            if isinstance(exc, CollectionBlocked):
                return


def quality(db):
    manifest = read_manifest(db)
    start, end = manifest['collection_start'], manifest['collection_end']
    result = []
    for m in manifest['markets']:
        stamps = {r[0] for r in db.execute('SELECT ts FROM minute_candles WHERE market=? AND ts>=? AND ts<?', (m,start,end))}
        intervals = db.execute('SELECT verified_start,verified_end FROM collection_pages WHERE market=?', (m,)).fetchall()
        verified = set()
        for a,b in intervals:
            verified.update(range(max(start,a),min(end,b),60))
        day = ((start+32400)//86400)*86400-32400
        while day < end:
            a,b = max(day,start),min(day+86400,end)
            grid = set(range(a,b,60))
            run = longest = gaps = 0
            for t in range(a,b,60):
                if t in stamps:
                    run = 0
                else:
                    gaps += run == 0
                    run += 1
                    longest = max(longest,run)
            n, expected = len(grid & stamps), len(grid)
            result.append((m,iso(day,KST)[:10],expected,n,n/expected,longest,gaps,
                           len(grid & verified),len((grid & verified)-stamps),len(grid-verified)))
            day += 86400
    with db:
        db.executemany('INSERT OR REPLACE INTO quality_daily VALUES(?,?,?,?,?,?,?,?,?,?)', result)
    return result


def crosscheck(db, client):
    manifest = read_manifest(db)
    start, end = manifest['collection_start'], manifest['collection_end']
    first = math.ceil(start/86400)*86400
    last = end//86400*86400
    for m in manifest['markets']:
        if db.execute('SELECT status FROM collection_state WHERE market=?',(m,)).fetchone()[0] != 'COMPLETE':
            continue
        for day in range(first,last,86400):
            raw = client.get('/v1/candles/days',market=m,to=iso(day+86400),count=1)
            rows = [candle(r) for r in raw]
            value = next((r[5] for r in rows if r[0] == day),None)
            total = db.execute('SELECT SUM(trade_value) FROM minute_candles WHERE market=? AND ts>=? AND ts<?',(m,day,day+86400)).fetchone()[0]
            diff = abs(total-value)/value if total is not None and value is not None and value>0 else None
            status = 'MATCH' if diff is not None and diff <= 1e-6 else 'MISMATCH' if diff is not None else 'UNVERIFIED'
            with db:
                db.execute('INSERT OR REPLACE INTO daily_crosscheck VALUES(?,?,?,?,?,?)',(m,iso(day)[:10],total,value,diff,status))


def make_manifest(start, end, alts, evidence, smoke=False, excluded=(), min_coverage=None):
    buffer = 0 if smoke else 21600
    min_coverage = DEFAULT_MIN_COVERAGE if min_coverage is None else min_coverage
    return dict(version=2,selection_time=start,minimum_prior_coverage=min_coverage,
                research_start=start,research_end=end,collection_start=start-buffer,
                collection_end=end+buffer,markets=['KRW-BTC']+alts,alts=alts,smoke=smoke,
                selection_evidence=evidence,excluded_stables=sorted(STABLES|set(excluded)),
                policy=f'Past 7 complete UTC days mean trade value; >={min_coverage:.0%} observed previous 24h; prior candle >=30 days old. No future returns. No automatic threshold relaxation.',
                limitation='Current market list introduces survivor bias for historical T; stable exclusion list is explicit, not exhaustive. Old candle proves prior trading, not exact listing date. Prior coverage cannot guarantee future continuity.')


def plan(manifest, count, start, end, db_path, smoke=False):
    n = len(manifest['markets']) if manifest else count+1
    a = manifest['collection_start'] if manifest else start-(0 if smoke else 21600)
    b = manifest['collection_end'] if manifest else end+(0 if smoke else 21600)
    calls = n*math.ceil((b-a)/60/200)
    return dict(db=str(db_path),markets=manifest['markets'] if manifest else ['KRW-BTC','KRW-ETH','KRW-XRP'] if smoke else f'UNSELECTED: {count} alts + BTC; selection pending',
                research_start_utc=iso(manifest['research_start'] if manifest else start),
                research_end_utc=iso(manifest['research_end'] if manifest else end),
                start_utc=iso(a),end_utc=iso(b),start_kst=iso(a,KST),end_kst=iso(b,KST),
                expected_candles=n*(b-a)//60,batch_calls=calls,
                sequential_minutes_assuming_02_to_05s_latency=[round(calls*.35/60,1),round(calls*.65/60,1)],
                selection_calls=0 if manifest or smoke else 'Additional: 1 + C daily queries + about 8*K minute queries; C candidates, K checked.',
                note='Full-range estimate, excludes retries and optional crosscheck; resume may require fewer requests.')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,default=DATA_DIR/'research_market_v1.db')
    p.add_argument('--start',help='Research start, explicit timezone required')
    p.add_argument('--days',type=int,help='Default 14 for new dataset; frozen value on resume')
    p.add_argument('--alt-count',type=int,choices=(50,75,100),help='Default 50 for new dataset')
    p.add_argument('--exclude',help='Extra stable/pegged tickers, comma separated')
    p.add_argument('--min-prior-coverage',type=float,help='Fixed prior 24h floor; frozen on resume')
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--smoke',action='store_true',help='Fixed BTC/ETH/XRP, 2h, separate DB, <=12 HTTP attempts')
    p.add_argument('--max-pages',type=int,help='Stop cleanly after this many committed pages for resume testing')
    p.add_argument('--crosscheck',action='store_true')
    p.add_argument('--manifest-file',type=Path,help='Frozen offline manifest; skips market selection, also checked on resume')
    args = p.parse_args(argv)
    supplied = json.loads(args.manifest_file.read_text(encoding='utf-8')) if args.manifest_file else None
    if supplied:
        markets=supplied['markets'];alts=supplied['alts']
        if markets != ['KRW-BTC']+alts or len(set(markets))!=len(markets) or not all(m.startswith('KRW-') for m in markets):
            p.error('Invalid frozen market list')
        if not supplied['collection_start'] <= supplied['research_start'] < supplied['research_end'] <= supplied['collection_end']:
            p.error('Invalid frozen collection interval')
        if any(supplied[k]%60 for k in ('collection_start','research_start','research_end','collection_end')):
            p.error('Frozen timestamps must be minute aligned')
        protected=supplied.get('protected_source_db')
        if protected and args.db.resolve()==Path(protected).resolve():
            p.error('Refusing to write discovery DB')
    if args.min_prior_coverage is not None and not 0 < args.min_prior_coverage <= 1:
        p.error('--min-prior-coverage must be in (0,1]')
    if args.days is not None and args.days <= 0 or args.max_pages is not None and args.max_pages <= 0:
        p.error('days/max-pages must be positive')
    if args.smoke and args.crosscheck:
        p.error('Crosscheck is disabled in the bounded smoke mode')
    if args.smoke and args.db.resolve() == (DATA_DIR/'research_market_v1.db').resolve():
        args.db = DATA_DIR/'research_market_v1_smoke.db'
    # Refuse all pre-existing non-collector DBs before any mutation.
    manifest = None
    if args.db.exists():
        with closing(sqlite3.connect(args.db.resolve().as_uri()+'?mode=ro',uri=True)) as read:
            try:
                manifest = read_manifest(read)
            except sqlite3.OperationalError as exc:
                raise ValueError('Not a collector DB; existing DB is preserved') from exc
            if manifest is None:
                raise ValueError('Existing DB has no frozen manifest; use a new DB path')
    if supplied:
        if manifest and manifest != supplied:
            p.error('Manifest file conflicts with frozen DB manifest')
        manifest=supplied
    if manifest:
        start,end = manifest['research_start'],manifest['research_end']
        if args.min_prior_coverage is not None and args.min_prior_coverage != manifest.get('minimum_prior_coverage',.95):
            p.error('--min-prior-coverage conflicts with frozen manifest')
        if bool(manifest['smoke']) != args.smoke or args.start and parse(args.start) != start:
            p.error('Arguments conflict with frozen manifest')
        if args.days is not None and args.days*86400 != end-start:
            p.error('--days conflicts with frozen manifest')
        if args.alt_count is not None and args.alt_count != len(manifest['alts']):
            p.error('--alt-count conflicts with frozen manifest')
        if args.exclude is not None and sorted(STABLES | {s.strip().upper() for s in args.exclude.split(',') if s.strip()}) != manifest['excluded_stables']:
            p.error('--exclude conflicts with frozen manifest')
    else:
        if not args.start and not args.smoke:
            p.error('--start required for a new dataset (use explicit timezone)')
        start = parse(args.start) if args.start else int(time.time())//60*60-180*60
        end = start+(120*60 if args.smoke else (args.days or 14)*86400)
    preview = plan(manifest,2 if args.smoke else (args.alt_count or 50),start,end,args.db,args.smoke)
    preview['mode'] = 'DRY_RUN' if args.dry_run else 'RESUME' if manifest else 'COLLECT'
    preview['minimum_prior_coverage'] = manifest.get('minimum_prior_coverage',.95) if manifest else args.min_prior_coverage if args.min_prior_coverage is not None else DEFAULT_MIN_COVERAGE
    closed=int(time.time())//60*60
    buffer_end=manifest['collection_end'] if manifest else end+(0 if args.smoke else 21600)
    preview.update(research_start_kst=iso(start,KST),research_end_kst=iso(end,KST),
                   closed_through_utc=iso(closed),closed_through_kst=iso(closed,KST),
                   research_complete=end<=closed,buffer_complete=buffer_end<=closed,
                   selection_policy=manifest.get('validation_market_policy','frozen manifest') if manifest else 'B: prior-only selection',
                   latest_research_end_with_6h_buffer_kst=iso(min(end,closed-21600),KST),
                   estimated_db_mb_100_to_200_bytes_per_candle=[round(preview['expected_candles']*x/1e6,1) for x in (100,200)])
    print(json.dumps(preview,ensure_ascii=False,indent=2),flush=True)
    if args.dry_run:
        print('DRY_RUN: plan only; no API requests or DB writes.', flush=True)
        return
    collection_end = manifest['collection_end'] if manifest else end+(0 if args.smoke else 21600)
    if collection_end > int(time.time())//60*60:
        p.error('End buffer is not closed yet; choose a fully historical interval')
    client = Client(max_requests=12 if args.smoke else None)
    if manifest is None:
        print('COLLECT: selecting markets before manifest creation (this can take several minutes).', flush=True)
        excluded = {s.strip().upper() for s in (args.exclude or '').split(',') if s.strip()}
        alts,evidence = (['KRW-ETH','KRW-XRP'],[]) if args.smoke else select_markets(client,start,args.alt_count or 50,excluded,min_coverage=preview['minimum_prior_coverage'])
        manifest = make_manifest(start,end,alts,evidence,args.smoke,excluded,min_coverage=preview['minimum_prior_coverage'])
    args.db.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(args.db)) as db:
        init_db(db)
        freeze(db,manifest)
        print(f'{preview["mode"]}: manifest fixed; entering batch collection for {len(manifest["markets"])} markets.', flush=True)
        try:
            collect(db,client,args.max_pages)
        finally:
            quality(db)
        if args.crosscheck:
            crosscheck(db,client)
        print(json.dumps(dict(requests=client.requests,retries=client.retries,
                             states=[dict(r) for r in db.execute('SELECT * FROM collection_state')]),indent=2))
        if db.execute("SELECT COUNT(*) FROM collection_state WHERE status='ERROR'").fetchone()[0]:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
