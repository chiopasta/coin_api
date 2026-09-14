"""Upbit early-surge research scanner. Alerts only; never submits orders.

Run: python -m coin_analysis.scanner_v16 --markets KRW-BTC KRW-ETH
Defaults are research hypotheses, not validated trading parameters.
"""

import argparse
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import statistics
import time
import urllib.parse
import urllib.request

from .paths import DATA_DIR


@dataclass(frozen=True)
class Config:
    window: int = 30
    baseline_windows: int = 10
    value_ratio: float = 3.0
    volume_ratio: float = 3.0
    min_value: float = 30_000_000
    min_trades: int = 20
    slope_floor_pct: float = -0.10
    max_extension_pct: float = 3.0
    max_price_5m_pct: float = 3.0
    cooldown: int = 1800


def pct(new, old):
    return (new / old - 1) * 100


class MarketState:
    def __init__(self, candles, started):
        self.closes = deque(candles, maxlen=100)
        self.started = started
        self.trades = deque()
        self.ids = set()
        self.last_ts = 0
        self.last_price = None
        self.next_check = 0

    def ingest(self, ts, price, volume, trade_id, config):
        if trade_id in self.ids or ts < self.last_ts:
            return False
        bucket = int(ts // 300) * 300
        if self.last_price is None and self.closes and bucket > self.closes[-1][0] + 300:
            # REST preload may have become stale before the stream connected.
            self.closes.clear()
        # Finalize using the previous price before accepting a new bucket's trade.
        if self.last_price is not None:
            previous_bucket = int(self.last_ts // 300) * 300
            while previous_bucket < bucket:
                if not self.closes or previous_bucket > self.closes[-1][0]:
                    self.closes.append((previous_bucket, self.last_price))
                previous_bucket += 300
        self.last_ts, self.last_price = ts, price
        self.trades.append((ts, price, volume, trade_id))
        self.ids.add(trade_id)
        cutoff = ts - max(300, config.window * (config.baseline_windows + 1))
        while self.trades and self.trades[0][0] <= cutoff:
            self.ids.discard(self.trades.popleft()[3])
        return True

    def evaluate(self, now, config):
        span = config.window * (config.baseline_windows + 1)
        if now - self.started < max(300, span) or len(self.closes) < 23:
            return None
        if now - self.last_ts > 5:
            return None
        closes = [price for _, price in self.closes]
        ma20 = statistics.fmean(closes[-20:])
        old_ma20 = statistics.fmean(closes[-23:-3])
        slope = pct(ma20, old_ma20)
        extension = pct(self.last_price, ma20)
        if slope < config.slope_floor_pct or not 0 <= extension <= config.max_extension_pct:
            return None
        values = [0.0] * (config.baseline_windows + 1)
        volumes = [0.0] * len(values)
        count = 0
        old_price = None
        for ts, price, volume, _ in self.trades:
            age = now - ts
            if age >= 300:
                old_price = price
            index = int(age // config.window)
            if 0 <= index < len(values):
                values[index] += price * volume
                volumes[index] += volume
                if index == 0:
                    count += 1
        if old_price is None:
            return None
        p5 = pct(self.last_price, old_price)
        if not 0 <= p5 <= config.max_price_5m_pct:
            return None
        # Median resists a single historical burst; mean prevents a tiny baseline.
        base_value = max(statistics.median(values[1:]), statistics.fmean(values[1:]))
        base_volume = max(statistics.median(volumes[1:]), statistics.fmean(volumes[1:]))
        if base_value <= 0 or base_volume <= 0:
            return None
        rv, rq = values[0] / base_value, volumes[0] / base_volume
        if (rv < config.value_ratio or rq < config.volume_ratio
                or values[0] < config.min_value or count < config.min_trades):
            return None
        return dict(price=self.last_price, ma20=ma20, slope_pct=slope,
                    trend="UP" if slope > 0.10 else "FLAT",
                    extension_pct=extension, price_5m_pct=p5,
                    value=values[0], value_ratio=rv, volume_ratio=rq, trades=count)


def http_json(path, params=None):
    url = "https://api.upbit.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "surge-research-v16"})
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.load(response)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def preload(market):
    rows = http_json("/v1/candles/minutes/5", {"market": market, "count": 100})
    end = int(time.time() // 300) * 300
    points = {}
    for row in rows:
        ts = int(datetime.fromisoformat(row["candle_date_time_utc"])
                 .replace(tzinfo=timezone.utc).timestamp())
        if ts < end:
            points[ts] = float(row["trade_price"])
    if not points:
        raise ValueError("No completed candles")
    # No-trade intervals retain the last close, with explicit time alignment.
    result = []
    previous = points[min(points)]
    for ts in range(max(min(points), end - 100 * 300), end, 300):
        previous = points.get(ts, previous)
        result.append((ts, previous))
    return result


class Recorder:
    def __init__(self, path, config):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, ts REAL NOT NULL, market TEXT NOT NULL,
                price REAL NOT NULL, features TEXT NOT NULL, config TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations (
                event_id INTEGER NOT NULL, ts REAL NOT NULL, price REAL NOT NULL,
                return_pct REAL NOT NULL, PRIMARY KEY(event_id, ts));
        """)
        self.config = json.dumps(asdict(config), sort_keys=True)
        self.last = dict(self.db.execute("SELECT market, MAX(ts) FROM events GROUP BY market"))
        self.active = list(self.db.execute(
            "SELECT id, ts, market, price FROM events WHERE ts >= ?", (time.time() - 72 * 3600,)))
        self.observed = {}

    def save(self, market, ts, features):
        with self.db:
            cursor = self.db.execute("INSERT INTO events(ts,market,price,features,config) VALUES(?,?,?,?,?)",
                                     (ts, market, features["price"], json.dumps(features), self.config))
        self.active.append((cursor.lastrowid, ts, market, features["price"]))
        self.last[market] = ts
        print(datetime.fromtimestamp(ts).isoformat(timespec="seconds"), market,
              "EARLY", json.dumps(features), flush=True)

    def observe(self, market, ts, price):
        self.active = [item for item in self.active if ts - item[1] <= 72 * 3600]
        with self.db:
            for event_id, started, symbol, original in self.active:
                if symbol == market and ts - self.observed.get(event_id, started) >= 60:
                    self.db.execute("INSERT OR IGNORE INTO observations VALUES(?,?,?,?)",
                                    (event_id, ts, price, pct(price, original)))
                    self.observed[event_id] = ts


def run(markets, config, db_path, duration=0):
    try:
        import websocket
    except ImportError as exc:
        raise SystemExit("Install dependency: python -m pip install websocket-client") from exc
    recorder = Recorder(db_path, config)
    deadline = time.monotonic() + duration if duration else math.inf
    try:
        while time.monotonic() < deadline:
            states = {}
            for market in markets:
                if time.monotonic() >= deadline:
                    return
                try:
                    states[market] = MarketState(preload(market), time.time())
                except Exception as exc:
                    print("PRELOAD SKIPPED", market, str(exc), flush=True)
                time.sleep(0.15)
            if not states:
                raise RuntimeError("No markets loaded")
            ws = None
            try:
                ws = websocket.create_connection("wss://api.upbit.com/websocket/v1", timeout=10)
                ws.send(json.dumps([{"ticket": "early-surge-v16"},
                                    {"type": "trade", "codes": list(states), "is_only_realtime": True},
                                    {"format": "DEFAULT"}]))
                connected = time.time()
                for state in states.values():
                    state.started = connected
                print("CONNECTED", len(states), "markets; warming up for 330 seconds", flush=True)
                while time.monotonic() < deadline:
                    raw = ws.recv()
                    if not raw:
                        raise ConnectionError("Stream closed")
                    item = json.loads(raw)
                    if "error" in item:
                        raise RuntimeError(str(item["error"]))
                    if item.get("type") != "trade" or item.get("code") not in states:
                        continue
                    now = time.time()
                    ts = item["trade_timestamp"] / 1000
                    if not 0 <= now - ts <= 10:
                        continue
                    market = item["code"]
                    state = states[market]
                    price, volume = float(item["trade_price"]), float(item["trade_volume"])
                    if not all(math.isfinite(v) and v > 0 for v in (price, volume)):
                        continue
                    if not state.ingest(ts, price, volume, item["sequential_id"], config):
                        continue
                    if now < state.next_check:
                        continue
                    state.next_check = now + 5
                    recorder.observe(market, ts, price)
                    if ts - recorder.last.get(market, 0) < config.cooldown:
                        continue
                    features = state.evaluate(ts, config)
                    if features:
                        recorder.save(market, ts, features)
            except (OSError, websocket.WebSocketException, ValueError, RuntimeError) as exc:
                print("RECONNECT; history and warmup will reset:", str(exc), flush=True)
            finally:
                if ws is not None:
                    ws.close()
            time.sleep(3)
    finally:
        recorder.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markets", nargs="+", help="Default: all Upbit KRW markets")
    parser.add_argument("--db", default=str(DATA_DIR / "scanner_v16.db"))
    parser.add_argument("--value-ratio", type=float, default=3.0)
    parser.add_argument("--volume-ratio", type=float, default=3.0)
    parser.add_argument("--min-value", type=float, default=30_000_000, help="KRW per 30 seconds")
    parser.add_argument("--duration", type=int, default=0, help="Run seconds; 0 means continuous")
    args = parser.parse_args()
    if any(not math.isfinite(v) or v <= 0 for v in
           (args.value_ratio, args.volume_ratio, args.min_value)) or args.duration < 0:
        parser.error("Thresholds must be positive finite numbers; duration must be nonnegative")
    markets = args.markets or [row["market"] for row in http_json("/v1/market/all")
                              if row["market"].startswith("KRW-")]
    markets = sorted(set(m.upper() for m in markets))
    if any(not m.startswith("KRW-") for m in markets):
        parser.error("Only KRW markets are supported")
    config = Config(value_ratio=args.value_ratio, volume_ratio=args.volume_ratio,
                    min_value=args.min_value)
    print("RESEARCH / ALERTS ONLY", json.dumps(asdict(config)), flush=True)
    try:
        run(markets, config, args.db, args.duration)
    except KeyboardInterrupt:
        print("STOPPED")


if __name__ == "__main__":
    main()
