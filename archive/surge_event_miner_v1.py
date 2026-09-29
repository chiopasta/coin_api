#!/usr/bin/env python3
"""UPBIT KRW 5분봉 기반 대급등 사건 역추적 연구 도구.

실제 주문 기능은 없다. 6시간 저점에서 처음 2% 반등한 시점을 기준으로,
이후 크게 오른 성공군과 실패한 대조군의 사전 특징을 비교한다.
"""

import argparse
import csv
import json
import math
import random
import sqlite3
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


API_BASE = "https://api.upbit.com"
DEFAULT_DB = "surge_research.db"
DEFAULT_EVENTS_CSV = "surge_events_v1.csv"
DEFAULT_REPORT_CSV = "surge_feature_report_v1.csv"
UNIT_MINUTES = 5
REQUEST_INTERVAL = 0.13
UTC = timezone.utc


@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    value: float


FEATURES = (
    ("ret_5m", "직전 5분 수익률", "%"),
    ("ret_15m", "직전 15분 수익률", "%"),
    ("ret_60m", "직전 60분 수익률", "%"),
    ("ret_240m", "직전 4시간 수익률", "%"),
    ("range_60m", "직전 60분 고저폭", "%"),
    ("range_240m", "직전 4시간 고저폭", "%"),
    ("compression", "1시간/4시간 변동폭", "배"),
    ("value_5m_million", "현재 5분 거래대금", "백만원"),
    ("avg_value_60m_million", "평균 5분 거래대금(1h)", "백만원"),
    ("value_ratio", "현재/1시간 거래대금", "배"),
    ("value_accel", "최근15분/이전60분 거래대금", "배"),
    ("green_ratio_60m", "최근 1시간 양봉 비율", "%"),
    ("position_240m", "4시간 범위 내 종가 위치", "%"),
    ("distance_high_240m", "4시간 고점까지 거리", "%"),
    ("btc_relative_60m", "BTC 대비 1시간 상대강도", "%p"),
    ("btc_relative_240m", "BTC 대비 4시간 상대강도", "%p"),
)


def parse_utc(value):
    if value is None:
        return None
    raw = value.strip()
    if len(raw) == 10:
        raw += "T00:00:00"
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(second=0, microsecond=0)


def iso_utc(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def kst_text(ts):
    return datetime.fromtimestamp(ts, UTC).astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")


def pct(new, old):
    return (new / old - 1.0) * 100.0 if old else 0.0


def http_json(path, params=None, retries=5):
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "surge-event-miner/1.0"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise
            time.sleep(min(8.0, 0.7 * (2 ** attempt)))
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(min(8.0, 0.7 * (2 ** attempt)))
    raise RuntimeError("API 요청 재시도 실패")


def init_db(conn):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS candles_5m (
            market TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            trade_value REAL NOT NULL,
            PRIMARY KEY (market, ts)
        );
        CREATE INDEX IF NOT EXISTS idx_candles_5m_ts ON candles_5m(ts);
        CREATE TABLE IF NOT EXISTS download_runs_5m (
            market TEXT NOT NULL,
            start_ts INTEGER NOT NULL,
            end_ts INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            rows_seen INTEGER NOT NULL,
            PRIMARY KEY (market, start_ts, end_ts)
        );
        """
    )
    conn.commit()


def list_krw_markets():
    rows = http_json("/v1/market/all", {"isDetails": "false"})
    return sorted(r["market"] for r in rows if r.get("market", "").startswith("KRW-"))


def choose_markets(text, limit):
    if text:
        result = []
        for item in text.split(","):
            item = item.strip().upper()
            if item and not item.startswith("KRW-"):
                item = "KRW-" + item
            if item:
                result.append(item)
        return sorted(set(result))
    markets = list_krw_markets()
    return markets[:limit] if limit else markets


def candle_tuple(raw):
    dt = datetime.fromisoformat(raw["candle_date_time_utc"]).replace(tzinfo=UTC)
    return (
        int(dt.timestamp()), float(raw["opening_price"]), float(raw["high_price"]),
        float(raw["low_price"]), float(raw["trade_price"]),
        float(raw["candle_acc_trade_price"]),
    )


def range_complete(conn, market, start_ts, end_ts):
    return conn.execute(
        "SELECT 1 FROM download_runs_5m WHERE market=? AND start_ts<=? AND end_ts>=? LIMIT 1",
        (market, start_ts, end_ts),
    ).fetchone() is not None


def download_market(conn, market, start_dt, end_dt):
    start_ts, end_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    if range_complete(conn, market, start_ts, end_ts):
        return 0, True
    cursor_to = end_dt
    rows_seen = 0
    last_oldest = None
    while True:
        batch = http_json(
            f"/v1/candles/minutes/{UNIT_MINUTES}",
            {"market": market, "to": iso_utc(cursor_to), "count": 200},
        )
        time.sleep(REQUEST_INTERVAL)
        if not batch:
            break
        parsed = [candle_tuple(row) for row in batch]
        selected = [row for row in parsed if start_ts <= row[0] < end_ts]
        if selected:
            conn.executemany(
                "INSERT OR REPLACE INTO candles_5m VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(market,) + row for row in selected],
            )
            conn.commit()
            rows_seen += len(selected)
        oldest = min(row[0] for row in parsed)
        if oldest <= start_ts or oldest == last_oldest:
            break
        last_oldest = oldest
        cursor_to = datetime.fromtimestamp(oldest, UTC)
    conn.execute(
        "INSERT OR REPLACE INTO download_runs_5m VALUES (?, ?, ?, ?, ?)",
        (market, start_ts, end_ts, iso_utc(datetime.now(UTC)), rows_seen),
    )
    conn.commit()
    return rows_seen, False


def download_all(conn, markets, start_dt, end_dt):
    bars = math.ceil((end_dt - start_dt).total_seconds() / (UNIT_MINUTES * 60))
    calls = math.ceil(bars / 200) * len(markets)
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    print("=" * 120)
    print("SURGE EVENT MINER V1 — UPBIT 5분봉 다운로드")
    print("기간:", iso_utc(start_dt), "~", iso_utc(end_dt))
    print(f"시장 {len(markets)}개 | DB {db_path}")
    print(f"예상 API 호출 최대 {calls:,}회 | 이론상 최소 {calls * REQUEST_INTERVAL / 60:.1f}분")
    print("※ 중단해도 완료된 종목과 페이지는 DB에 남습니다.")
    print("=" * 120)
    failures = []
    total = 0
    for number, market in enumerate(markets, 1):
        try:
            count, skipped = download_market(conn, market, start_dt, end_dt)
            total += count
            state = "캐시 완료" if skipped else f"{count:,}행"
            print(f"[{number:>3}/{len(markets)}] {market:<13} {state}")
        except Exception as exc:
            failures.append(market)
            print(f"[{number:>3}/{len(markets)}] {market:<13} 실패: {exc}")
    print(f"다운로드 종료 | 이번 실행 {total:,}행 | 실패 {len(failures)}개")
    if failures:
        print("실패 시장:", ", ".join(failures))


def load_candles(conn, market, start_ts, end_ts):
    rows = conn.execute(
        """SELECT ts, open, high, low, close, trade_value FROM candles_5m
           WHERE market=? AND ts>=? AND ts<? ORDER BY ts""",
        (market, start_ts, end_ts),
    ).fetchall()
    return [Candle(*row) for row in rows]


def rolling_past_low(candles, bars):
    result = [None] * len(candles)
    queue = deque()
    for i in range(len(candles)):
        add = i - 1
        if add >= 0:
            while queue and candles[queue[-1]].low >= candles[add].low:
                queue.pop()
            queue.append(add)
        first = i - bars
        while queue and queue[0] < first:
            queue.popleft()
        if i >= bars and queue:
            result[i] = (candles[queue[0]].low, queue[0])
    return result


def rolling_future_high(candles, bars):
    result = [None] * len(candles)
    queue = deque()
    for i in range(len(candles) - 1, -1, -1):
        add = i + 1
        if add < len(candles):
            while queue and candles[queue[-1]].high <= candles[add].high:
                queue.pop()
            queue.append(add)
        last = i + bars
        while queue and queue[0] > last:
            queue.popleft()
        if queue:
            result[i] = candles[queue[0]].high
    return result


def mean(values):
    return statistics.fmean(values) if values else 0.0


def median(values):
    return statistics.median(values) if values else 0.0


def feature_snapshot(candles, i, btc_by_ts):
    current = candles[i]
    h1 = candles[i - 12:i]
    h4 = candles[i - 48:i]
    if len(h4) < 48 or current.ts - h4[0].ts > 50 * UNIT_MINUTES * 60:
        return None
    high1, low1 = max(c.high for c in h1), min(c.low for c in h1)
    high4, low4 = max(c.high for c in h4), min(c.low for c in h4)
    range1, range4 = pct(high1, low1), pct(high4, low4)
    avg1 = mean([c.value for c in h1])
    recent3 = mean([c.value for c in candles[i - 3:i]])
    previous12 = mean([c.value for c in candles[i - 15:i - 3]])
    btc_now = btc_by_ts.get(current.ts)
    btc_1h = btc_by_ts.get(current.ts - 12 * UNIT_MINUTES * 60)
    btc_4h = btc_by_ts.get(current.ts - 48 * UNIT_MINUTES * 60)
    btc_r1 = pct(btc_now, btc_1h) if btc_now and btc_1h else 0.0
    btc_r4 = pct(btc_now, btc_4h) if btc_now and btc_4h else 0.0
    r1 = pct(current.close, candles[i - 12].close)
    r4 = pct(current.close, candles[i - 48].close)
    return {
        "ret_5m": pct(current.close, candles[i - 1].close),
        "ret_15m": pct(current.close, candles[i - 3].close),
        "ret_60m": r1,
        "ret_240m": r4,
        "range_60m": range1,
        "range_240m": range4,
        "compression": range1 / range4 if range4 > 0 else 0.0,
        "value_5m_million": current.value / 1_000_000,
        "avg_value_60m_million": avg1 / 1_000_000,
        "value_ratio": current.value / avg1 if avg1 > 0 else 0.0,
        "value_accel": recent3 / previous12 if previous12 > 0 else 0.0,
        "green_ratio_60m": 100.0 * sum(c.close > c.open for c in h1) / 12,
        "position_240m": 100.0 * (current.close - low4) / (high4 - low4) if high4 > low4 else 50.0,
        "distance_high_240m": pct(high4, current.close),
        "btc_relative_60m": r1 - btc_r1,
        "btc_relative_240m": r4 - btc_r4,
    }


def find_triggers(candles, btc_by_ts, target_pct, horizon_hours, ignition_pct, control_ceiling):
    low_bars = 6 * 60 // UNIT_MINUTES
    horizon_bars = horizon_hours * 60 // UNIT_MINUTES
    max_horizon_bars = 12 * 60 // UNIT_MINUTES
    past_lows = rolling_past_low(candles, low_bars)
    future3 = rolling_future_high(candles, 3 * 60 // UNIT_MINUTES)
    future6 = rolling_future_high(candles, 6 * 60 // UNIT_MINUTES)
    future12 = rolling_future_high(candles, max_horizon_bars)
    chosen_future = {3: future3, 6: future6, 12: future12}[horizon_hours]
    candidates = []
    previous_above = False
    for i in range(max(48, low_bars), len(candles) - max_horizon_bars):
        if candles[i + max_horizon_bars].ts - candles[i].ts > (max_horizon_bars + 2) * UNIT_MINUTES * 60:
            continue
        past = past_lows[i]
        if not past or chosen_future[i] is None:
            continue
        base_low, low_index = past
        if base_low <= 0:
            continue
        above = candles[i].close >= base_low * (1.0 + ignition_pct / 100.0)
        if not above:
            previous_above = False
            continue
        if previous_above:
            continue
        previous_above = True
        if candles[i].ts - candles[low_index].ts > 6 * 3600:
            continue
        features = feature_snapshot(candles, i, btc_by_ts)
        if features is None:
            continue
        total_surge = pct(chosen_future[i], base_low)
        forward_from_trigger = pct(chosen_future[i], candles[i].close)
        row = {
            "ts": candles[i].ts,
            "time_kst": kst_text(candles[i].ts),
            "trigger_price": candles[i].close,
            "base_low": base_low,
            "base_age_min": (candles[i].ts - candles[low_index].ts) // 60,
            "surge_3h": pct(future3[i], base_low) if future3[i] else 0.0,
            "surge_6h": pct(future6[i], base_low) if future6[i] else 0.0,
            "surge_12h": pct(future12[i], base_low) if future12[i] else 0.0,
            "forward_from_trigger": forward_from_trigger,
            **features,
        }
        if total_surge >= target_pct:
            row["label"] = "SURGE"
        elif total_surge < control_ceiling:
            row["label"] = "CONTROL"
        else:
            continue
        candidates.append(row)
    return candidates


def deduplicate_and_match(rows, control_ratio=3, seed=42):
    events = []
    controls = []
    for market in sorted(set(r["market"] for r in rows)):
        market_rows = sorted((r for r in rows if r["market"] == market), key=lambda r: r["ts"])
        last_event = -10**18
        market_events = []
        for row in market_rows:
            if row["label"] == "SURGE" and row["ts"] - last_event >= 12 * 3600:
                market_events.append(row)
                last_event = row["ts"]
        events.extend(market_events)
        last_control = -10**18
        for row in market_rows:
            if row["label"] != "CONTROL" or row["ts"] - last_control < 3 * 3600:
                continue
            if any(abs(row["ts"] - e["ts"]) < 12 * 3600 for e in market_events):
                continue
            controls.append(row)
            last_control = row["ts"]
    limit = len(events) * control_ratio
    if len(controls) > limit > 0:
        controls = random.Random(seed).sample(controls, limit)
    return sorted(events, key=lambda r: r["ts"]), sorted(controls, key=lambda r: r["ts"])


def quantile(values, q):
    if not values:
        return 0.0
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def standardized_difference(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    pooled = math.sqrt((statistics.variance(a) + statistics.variance(b)) / 2.0)
    return (mean(a) - mean(b)) / pooled if pooled > 0 else 0.0


def feature_report(events, controls):
    report = []
    for key, title, unit in FEATURES:
        a = [float(r[key]) for r in events]
        b = [float(r[key]) for r in controls]
        report.append({
            "feature": key,
            "title": title,
            "unit": unit,
            "event_median": median(a),
            "control_median": median(b),
            "difference": median(a) - median(b),
            "standardized_difference": standardized_difference(a, b),
        })
    return sorted(report, key=lambda r: abs(r["standardized_difference"]), reverse=True)


def split_by_time(rows):
    ordered = sorted(rows, key=lambda r: r["ts"])
    cut = int(len(ordered) * 0.70)
    return ordered[:cut], ordered[cut:]


def event_rate(rows):
    return 100.0 * sum(r["label"] == "SURGE" for r in rows) / len(rows) if rows else 0.0


def stable_single_feature_rules(events, controls, report):
    all_rows = sorted(events + controls, key=lambda r: r["ts"])
    old, new = split_by_time(all_rows)
    base_old, base_new = event_rate(old), event_rate(new)
    rules = []
    for item in report:
        key = item["feature"]
        values = [float(r[key]) for r in old]
        direction = 1 if item["difference"] >= 0 else -1
        for q in (0.25, 0.50, 0.75):
            threshold = quantile(values, q)
            predicate = (lambda r, k=key, t=threshold: float(r[k]) >= t) if direction > 0 else (
                lambda r, k=key, t=threshold: float(r[k]) <= t
            )
            selected_old = [r for r in old if predicate(r)]
            selected_new = [r for r in new if predicate(r)]
            if len(selected_old) < 20 or len(selected_new) < 10:
                continue
            rate_old, rate_new = event_rate(selected_old), event_rate(selected_new)
            if rate_old > base_old and rate_new > base_new:
                rules.append({
                    "title": item["title"], "feature": key,
                    "operator": ">=" if direction > 0 else "<=", "threshold": threshold,
                    "old_n": len(selected_old), "old_rate": rate_old, "old_lift": rate_old - base_old,
                    "new_n": len(selected_new), "new_rate": rate_new, "new_lift": rate_new - base_new,
                })
    rules.sort(key=lambda r: (r["new_lift"], r["old_lift"]), reverse=True)
    return rules, base_old, base_new


def write_events_csv(path, rows):
    if not rows:
        return
    columns = [
        "label", "market", "time_kst", "ts", "trigger_price", "base_low", "base_age_min",
        "surge_3h", "surge_6h", "surge_12h", "forward_from_trigger",
    ] + [key for key, _, _ in FEATURES]
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report_csv(path, report):
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(report[0].keys()) if report else ["feature"])
        writer.writeheader()
        writer.writerows(report)


def analyze(conn, markets, start_dt, end_dt, args):
    start_ts, end_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    btc = load_candles(conn, "KRW-BTC", start_ts, end_ts)
    btc_by_ts = {c.ts: c.close for c in btc}
    all_rows = []
    candle_total = 0
    for number, market in enumerate(markets, 1):
        candles = load_candles(conn, market, start_ts, end_ts)
        candle_total += len(candles)
        if len(candles) < 300:
            continue
        rows = find_triggers(
            candles, btc_by_ts, args.target, args.horizon,
            args.ignition, args.control_ceiling,
        )
        for row in rows:
            row["market"] = market
        all_rows.extend(rows)
        if number % 30 == 0 or number == len(markets):
            print(f"사건 탐색: {number}/{len(markets)} 시장")

    events, controls = deduplicate_and_match(all_rows, args.control_ratio)
    combined = sorted(events + controls, key=lambda r: r["ts"])
    report = feature_report(events, controls)
    rules, base_old, base_new = stable_single_feature_rules(events, controls, report)
    write_events_csv(args.events_csv, combined)
    write_report_csv(args.report_csv, report)

    print("\n" + "=" * 142)
    print("SURGE EVENT MINER V1 — 대급등 코인의 초기 2% 시점 공통점")
    print("기간:", iso_utc(start_dt), "~", iso_utc(end_dt))
    print(f"시장 {len(markets)}개 | 5분봉 {candle_total:,}개")
    print(f"성공: {args.horizon}시간 내 6시간 저점 대비 +{args.target:.1f}% 이상")
    print(f"대조: 같은 초기 +{args.ignition:.1f}% 움직임 후 +{args.control_ceiling:.1f}% 미만")
    print(f"성공군 {len(events)}건 | 대조군 {len(controls)}건")
    print("=" * 142)
    print("1. 성공군과 실패군 차이가 큰 특징")
    if not report:
        print("분석할 사건이 없습니다. 기간을 늘리거나 목표 상승률을 낮춰보세요.")
    for item in report:
        print(
            f"{item['title']:<29} 성공 중앙값 {item['event_median']:>10.3f} {item['unit']:<4} | "
            f"실패 {item['control_median']:>10.3f} | 차이 {item['difference']:+9.3f} | "
            f"효과크기 {item['standardized_difference']:+.3f}"
        )

    print("\n" + "=" * 142)
    print("2. 시간순 70% 발견 → 최신 30%에서도 성공률을 높인 단일 조건")
    print(f"기본 성공률: 과거 {base_old:.1f}% | 최신 {base_new:.1f}%")
    if not rules:
        print("양쪽 구간에서 재현된 단일 조건이 없습니다.")
    for rule in rules[:12]:
        print(
            f"{rule['title']:<29} {rule['operator']} {rule['threshold']:.3f} | "
            f"과거 {rule['old_n']:>4}건 {rule['old_rate']:>5.1f}%({rule['old_lift']:+.1f}%p) | "
            f"최신 {rule['new_n']:>4}건 {rule['new_rate']:>5.1f}%({rule['new_lift']:+.1f}%p)"
        )

    print("\n" + "=" * 142)
    print("3. 가장 큰 급등 사건 상위 15개")
    for row in sorted(events, key=lambda r: r[f"surge_{args.horizon}h"], reverse=True)[:15]:
        print(
            f"{row['time_kst']} {row['market']:<12} "
            f"3h {row['surge_3h']:+6.1f}% | 6h {row['surge_6h']:+6.1f}% | "
            f"12h {row['surge_12h']:+6.1f}% | 초기신호 후 {row['forward_from_trigger']:+6.1f}%"
        )
    print("=" * 142)
    print("사건 원본:", args.events_csv)
    print("특징 보고서:", args.report_csv)
    print("※ 현재 상장 종목만 사용하므로 상장폐지 종목 생존편향이 있습니다.")
    print("※ 이 결과를 본 뒤 조건을 확정하지 말고, 다음 기간 데이터에서 다시 검증해야 합니다.")


def resolve_period(args):
    end_dt = parse_utc(args.end) or datetime.now(UTC).replace(second=0, microsecond=0)
    start_dt = parse_utc(args.start) or end_dt - timedelta(days=args.days)
    if start_dt >= end_dt:
        raise SystemExit("시작 시각은 종료 시각보다 빨라야 합니다.")
    return start_dt, end_dt


def parser():
    p = argparse.ArgumentParser(description="급등 코인의 초기 공통점을 찾는 업비트 5분봉 사건 분석기")
    p.add_argument("command", nargs="?", choices=("download", "analyze", "all"), default="all")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--start", help="UTC 시작일/시각")
    p.add_argument("--end", help="UTC 종료일/시각")
    p.add_argument("--markets", help="예: BTC,ETH,SOPH")
    p.add_argument("--limit-markets", type=int, help="속도 시험용 알파벳순 시장 제한")
    p.add_argument("--target", type=float, default=20.0, help="대급등 기준 %%")
    p.add_argument("--horizon", type=int, choices=(3, 6, 12), default=6)
    p.add_argument("--ignition", type=float, default=2.0, help="초기 움직임 기준 %%")
    p.add_argument("--control-ceiling", type=float, default=10.0, help="실패군 최대 상승률 %%")
    p.add_argument("--control-ratio", type=int, default=3, help="성공 1건당 최대 대조군 수")
    p.add_argument("--events-csv", default=DEFAULT_EVENTS_CSV)
    p.add_argument("--report-csv", default=DEFAULT_REPORT_CSV)
    return p


def main():
    args = parser().parse_args()
    if args.days <= 0 or args.target <= args.ignition or args.control_ceiling <= args.ignition:
        raise SystemExit("기간과 상승률 설정을 확인하세요.")
    start_dt, end_dt = resolve_period(args)
    conn = sqlite3.connect(args.db)
    try:
        init_db(conn)
        markets = choose_markets(args.markets, args.limit_markets)
        if "KRW-BTC" not in markets:
            markets = ["KRW-BTC"] + markets
        markets = sorted(set(markets))
        if args.command in ("download", "all"):
            download_all(conn, markets, start_dt, end_dt)
        if args.command in ("analyze", "all"):
            analyze(conn, markets, start_dt, end_dt, args)
    except KeyboardInterrupt:
        print("\n사용자 중단. 완료된 데이터는 DB에 저장되어 있습니다.")
        raise SystemExit(130)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
