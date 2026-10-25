"""Separate price-only observation overlay. Never supplies V4 features/labels.

No synthetic candles, OHLC, volume, trade value, or hit/success labels. Missing
minutes require independently validated NO_TRADE evidence, known by `asof`.
"""
import math

MAX_PRICE_AGE_SECONDS = 300  # Conservative upper bound from source minute START.
POLICY = 'V45_PRICE_ONLY_300S_FROM_MINUTE_START'


def schema(db):
    db.executescript('''
      CREATE TABLE IF NOT EXISTS no_trade_evidence_v45(
        market TEXT NOT NULL,ts INTEGER NOT NULL CHECK(ts%60=0),
        known_at REAL NOT NULL CHECK(known_at>=ts+65),provenance TEXT NOT NULL,
        PRIMARY KEY(market,ts));
      CREATE TABLE IF NOT EXISTS price_horizons_v45(
        signal_id TEXT,minutes INTEGER,status TEXT,reason TEXT,price REAL,
        source_ts INTEGER,age_upper_seconds INTEGER,return_pct REAL,
        evaluated_at REAL,policy TEXT,PRIMARY KEY(signal_id,minutes));
      CREATE TRIGGER IF NOT EXISTS immutable_no_trade_v45 BEFORE UPDATE ON no_trade_evidence_v45
        BEGIN SELECT RAISE(ABORT,'NO_TRADE evidence is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS immutable_price_complete_v45 BEFORE UPDATE ON price_horizons_v45
        WHEN OLD.status='COMPLETE' BEGIN SELECT RAISE(ABORT,'Price endpoint is immutable'); END;
    ''')


def price_point(db, market, end, asof):
    """Endpoint close proxy, not an executable quote or intraminute path.

    Receipt/evidence cutoff prevents using later evidence in contemporaneous
    evaluation. `end` is the desired UTC minute close, `asof` the knowledge time.
    A candle close is only known after the existing five-second settle boundary.
    """
    if end % 60 or not math.isfinite(asof):
        raise ValueError('Expected aligned endpoint and finite knowledge clock')
    result = dict(status='UNAVAILABLE',reason=None,price=None,source_ts=None,
                  age_upper_seconds=None,basis=None,policy=POLICY)
    if asof < end + 5:
        return dict(result,status='PENDING',reason='ENDPOINT_NOT_SETTLED')
    row = db.execute('''SELECT c.ts,c.close FROM minute_candles c
        JOIN candle_receipts r USING(market,ts)
        WHERE c.market=? AND c.ts<? AND c.ts+60<=? AND r.first_received_at<=?
        ORDER BY c.ts DESC LIMIT 1''',(market,end,end,asof)).fetchone()
    if row is None:
        return dict(result,reason='NO_KNOWN_CONFIRMED_PRICE')
    ts,price = row
    age = end-ts  # Last trade can be anywhere in source minute; do not claim exact age.
    if not math.isfinite(price) or price <= 0:
        return dict(result,reason='INVALID_SOURCE_PRICE')
    if age > MAX_PRICE_AGE_SECONDS:
        return dict(result,reason='STALE_LAST_PRICE',source_ts=ts,age_upper_seconds=age)
    for missing in range(ts+60,end,60):
        # Actual-but-late data must not be reinterpreted as a no-trade minute.
        if db.execute('SELECT 1 FROM minute_candles WHERE market=? AND ts=?',(market,missing)).fetchone():
            return dict(result,reason='UNRECEIPTED_OR_LATE_SOURCE')
        proof = db.execute('SELECT known_at FROM no_trade_evidence_v45 WHERE market=? AND ts=?',
                           (market,missing)).fetchone()
        if proof is None or proof[0] > asof:
            return dict(result,reason='NO_TRADE_NOT_PROVEN_ASOF')
    return dict(result,status='AVAILABLE',reason='CONFIRMED_PRICE',price=price,
                source_ts=ts,age_upper_seconds=age,
                basis='ACTUAL_CANDLE_CLOSE' if age==60 else 'DERIVED_NO_TRADE_LAST_CLOSE')


def record_price_horizons(db, now):
    """Additional 30/60m ENDPOINT returns only; frozen outcomes stay untouched."""
    for signal in db.execute('SELECT * FROM signals').fetchall():
        for minutes in (30,60):
            old = db.execute('SELECT status FROM price_horizons_v45 WHERE signal_id=? AND minutes=?',
                             (signal['signal_id'],minutes)).fetchone()
            if old and old[0]=='COMPLETE':
                continue
            end = signal['signal_time']+minutes*60
            point = price_point(db,signal['market'],end,now)
            verified = db.execute('SELECT verified_until FROM scanner_state WHERE market=?',
                                  (signal['market'],)).fetchone()[0]
            if now>=end+5 and verified<end:
                point.update(status='UNAVAILABLE',reason='ENDPOINT_RANGE_NOT_COLLECTED',price=None)
            complete = point['status']=='AVAILABLE'
            change = 100*(point['price']/signal['signal_price']-1) if complete else None
            with db:
                db.execute('''INSERT INTO price_horizons_v45 VALUES(?,?,?,?,?,?,?,?,?,?)
                  ON CONFLICT(signal_id,minutes) DO UPDATE SET status=excluded.status,
                  reason=excluded.reason,price=excluded.price,source_ts=excluded.source_ts,
                  age_upper_seconds=excluded.age_upper_seconds,return_pct=excluded.return_pct,
                  evaluated_at=excluded.evaluated_at,policy=excluded.policy''',
                  (signal['signal_id'],minutes,'COMPLETE' if complete else 'PENDING',point['reason'],
                   point['price'],point['source_ts'],point['age_upper_seconds'],change,now,POLICY))
