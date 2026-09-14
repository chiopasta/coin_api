#!/usr/bin/env python3
"""
UPBIT KRW 1분봉 다운로드 + 박스권 압축 돌파 백테스트.

표준 라이브러리만 사용하며 실제 주문은 전송하지 않는다.
다운로드 데이터는 crypto_scanner.db와 분리된 historical_market.db에 저장한다.
"""

import argparse
import json
import math
import sqlite3
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .paths import DATA_DIR


API_BASE = "https://api.upbit.com"
DEFAULT_DB = str(DATA_DIR / "historical_market.db")
FEE_PCT = 0.10  # 왕복 수수료 가정
REQUEST_INTERVAL = 0.13  # 캔들 그룹 공식 한도 10회/초보다 여유 있게
UTC = timezone.utc


@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    value: float


@dataclass(frozen=True)
class Strategy:
    name: str
    box_minutes: int
    max_box_pct: float
    min_avg_value: float
    min_breakout_vol_ratio: float
    min_volume_ramp: float
    max_p5_pct: float
    max_p15_pct: float
    breakout_buffer_pct: float
    confirm_minutes: int


@dataclass(frozen=True)
class ExitRule:
    name: str
    tp_pct: float
    sl_pct: float
    hold_minutes: int


STRATEGIES = (
    Strategy("BOX_BASIC", 60, 3.0, 10_000_000, 2.0, 1.25, 3.0, 5.0, 0.20, 2),
    Strategy("BOX_TIGHT", 60, 2.0, 10_000_000, 2.0, 1.25, 2.0, 4.0, 0.20, 2),
    Strategy("BOX_LIQUID", 60, 3.0, 30_000_000, 2.0, 1.25, 3.0, 5.0, 0.20, 2),
    Strategy("BOX_VOLUME", 60, 3.0, 10_000_000, 3.0, 1.50, 3.0, 5.0, 0.20, 2),
)

EXIT_RULES = (
    ExitRule("TP2_SL1_H30", 2.0, 1.0, 30),
    ExitRule("TP3_SL1_H30", 3.0, 1.0, 30),
    ExitRule("TP3_SL1.5_H45", 3.0, 1.5, 45),
    ExitRule("TP4_SL1.5_H60", 4.0, 1.5, 60),
)


def parse_utc(value):
    if value is None:
        return None
    raw = value.strip()
    if len(raw) == 10:
        raw += "T00:00:00"
    raw = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).replace(second=0, microsecond=0)


def iso_utc(dt):
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_json(path, params=None, retries=5):
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "historical-breakout-lab/1.0"},
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
        CREATE TABLE IF NOT EXISTS minute_candles (
            market TEXT NOT NULL,
            ts INTEGER NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            trade_value REAL NOT NULL,
            PRIMARY KEY (market, ts)
        );
        CREATE INDEX IF NOT EXISTS idx_minute_candles_ts
            ON minute_candles(ts);
        CREATE TABLE IF NOT EXISTS download_runs (
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
    return sorted(row["market"] for row in rows if row.get("market", "").startswith("KRW-"))


def choose_markets(markets_text, limit_markets):
    if markets_text:
        markets = []
        for raw in markets_text.split(","):
            item = raw.strip().upper()
            if not item:
                continue
            if not item.startswith("KRW-"):
                item = "KRW-" + item
            markets.append(item)
        return sorted(set(markets))
    markets = list_krw_markets()
    if limit_markets:
        # 알파벳순 제한은 속도 확인용이다. 전략 성과 판단에는 전체 시장을 권장한다.
        markets = markets[:limit_markets]
    return markets


def candle_row(raw):
    dt = datetime.fromisoformat(raw["candle_date_time_utc"]).replace(tzinfo=UTC)
    return (
        int(dt.timestamp()),
        float(raw["opening_price"]),
        float(raw["high_price"]),
        float(raw["low_price"]),
        float(raw["trade_price"]),
        float(raw["candle_acc_trade_price"]),
    )


def range_already_complete(conn, market, start_ts, end_ts):
    return conn.execute(
        "SELECT 1 FROM download_runs WHERE market=? AND start_ts<=? AND end_ts>=? LIMIT 1",
        (market, start_ts, end_ts),
    ).fetchone() is not None


def download_market(conn, market, start_dt, end_dt):
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    if range_already_complete(conn, market, start_ts, end_ts):
        return 0, True

    cursor_to = end_dt
    rows_seen = 0
    last_oldest = None
    while True:
        batch = http_json(
            "/v1/candles/minutes/1",
            {"market": market, "to": iso_utc(cursor_to), "count": 200},
        )
        time.sleep(REQUEST_INTERVAL)
        if not batch:
            break

        parsed = [candle_row(row) for row in batch]
        selected = [row for row in parsed if start_ts <= row[0] < end_ts]
        if selected:
            conn.executemany(
                """
                INSERT OR REPLACE INTO minute_candles
                (market, ts, open, high, low, close, trade_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
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
        """
        INSERT OR REPLACE INTO download_runs
        (market, start_ts, end_ts, completed_at, rows_seen)
        VALUES (?, ?, ?, ?, ?)
        """,
        (market, start_ts, end_ts, iso_utc(datetime.now(UTC)), rows_seen),
    )
    conn.commit()
    return rows_seen, False


def download_all(conn, markets, start_dt, end_dt):
    estimated_calls = math.ceil((end_dt - start_dt).total_seconds() / 60 / 200) * len(markets)
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    print("=" * 118)
    print("UPBIT 과거 1분봉 다운로드")
    print("기간:", iso_utc(start_dt), "~", iso_utc(end_dt))
    print("시장:", len(markets), "개 | DB:", db_path)
    print(f"예상 API 호출(최대치): 약 {estimated_calls:,}회 | 최소 예상시간 약 {estimated_calls * REQUEST_INTERVAL / 60:.1f}분")
    print("※ 중단 후 같은 명령을 다시 실행해도 기존 캔들은 중복 저장되지 않습니다.")
    print("=" * 118)
    failures = []
    total = 0
    for index, market in enumerate(markets, 1):
        try:
            count, skipped = download_market(conn, market, start_dt, end_dt)
            total += count
            state = "캐시 완료" if skipped else f"{count:,}행 확인"
            print(f"[{index:>3}/{len(markets)}] {market:<12} {state}")
        except Exception as exc:
            failures.append((market, str(exc)))
            print(f"[{index:>3}/{len(markets)}] {market:<12} 실패: {exc}")
    print(f"다운로드 종료: 이번 실행 {total:,}행 | 실패 {len(failures)}개")
    if failures:
        print("실패 시장:", ", ".join(m for m, _ in failures))
        print("같은 명령을 다시 실행하면 실패한 구간을 재시도합니다.")


def load_candles(conn, market, start_ts, end_ts):
    rows = conn.execute(
        """
        SELECT ts, open, high, low, close, trade_value
        FROM minute_candles
        WHERE market=? AND ts>=? AND ts<?
        ORDER BY ts
        """,
        (market, start_ts, end_ts),
    ).fetchall()
    return [Candle(*row) for row in rows]


def pct(new, old):
    return (new / old - 1.0) * 100.0 if old else 0.0


def build_features(candles, lookback=60):
    """한 시장의 공통 롤링 값을 O(n)에 계산한다."""
    size = len(candles)
    prefix_value = [0.0] * (size + 1)
    for i, candle in enumerate(candles):
        prefix_value[i + 1] = prefix_value[i] + candle.value

    box_high = [None] * size
    box_low = [None] * size
    high_q = deque()
    low_q = deque()
    for i in range(size):
        add = i - 1
        if add >= 0:
            while high_q and candles[high_q[-1]].high <= candles[add].high:
                high_q.pop()
            high_q.append(add)
            while low_q and candles[low_q[-1]].low >= candles[add].low:
                low_q.pop()
            low_q.append(add)
        first = i - lookback
        while high_q and high_q[0] < first:
            high_q.popleft()
        while low_q and low_q[0] < first:
            low_q.popleft()
        if i >= lookback:
            box_high[i] = candles[high_q[0]].high
            box_low[i] = candles[low_q[0]].low
    return prefix_value, box_high, box_low


def window_sum(prefix, start, end):
    return prefix[end] - prefix[start]


def detect_entries(candles, strategy, features=None):
    entries = []
    last_entry_ts = -10**18
    lookback = strategy.box_minutes
    if features is None:
        features = build_features(candles, lookback)
    prefix_value, rolling_high, rolling_low = features
    for i in range(max(lookback, 20), len(candles) - strategy.confirm_minutes):
        current = candles[i]

        # 거래가 없어 생성되지 않은 캔들이 많은 종목은 60분 박스로 취급하지 않는다.
        if candles[i - 1].ts - candles[i - lookback].ts > (lookback + 5) * 60:
            continue
        if current.ts - candles[i - 1].ts > 2 * 60:
            continue
        if current.ts - last_entry_ts < 120 * 60:
            continue

        box_high = rolling_high[i]
        box_low = rolling_low[i]
        if box_low <= 0 or pct(box_high, box_low) > strategy.max_box_pct:
            continue

        avg_value_60 = window_sum(prefix_value, i - lookback, i) / lookback
        if avg_value_60 < strategy.min_avg_value:
            continue
        avg_value_20 = window_sum(prefix_value, i - 20, i) / 20.0
        avg_recent_10 = window_sum(prefix_value, i - 10, i) / 10.0
        avg_previous_10 = window_sum(prefix_value, i - 20, i - 10) / 10.0
        if avg_previous_10 <= 0 or avg_recent_10 / avg_previous_10 < strategy.min_volume_ramp:
            continue
        if avg_value_20 <= 0 or current.value / avg_value_20 < strategy.min_breakout_vol_ratio:
            continue

        if current.close < box_high * (1.0 + strategy.breakout_buffer_pct / 100.0):
            continue
        if current.ts - candles[i - 5].ts != 5 * 60:
            continue
        if current.ts - candles[i - 15].ts != 15 * 60:
            continue
        p5 = pct(current.close, candles[i - 5].close)
        p15 = pct(current.close, candles[i - 15].close)
        if p5 < 0 or p5 > strategy.max_p5_pct or p15 < 0 or p15 > strategy.max_p15_pct:
            continue

        confirm = candles[i + 1:i + 1 + strategy.confirm_minutes]
        if len(confirm) != strategy.confirm_minutes:
            continue
        if any(confirm[j].ts - current.ts != (j + 1) * 60 for j in range(len(confirm))):
            continue
        if any(c.close < box_high for c in confirm):
            continue

        entry_index = i + strategy.confirm_minutes
        entry = candles[entry_index]
        entries.append(
            {
                "entry_index": entry_index,
                "entry_ts": entry.ts,
                "entry_price": entry.close,
                "box_pct": pct(box_high, box_low),
                "p5": p5,
                "p15": p15,
                "vol_ratio": current.value / avg_value_20,
                "avg_value": avg_value_60,
            }
        )
        last_entry_ts = entry.ts
    return entries


def simulate_exit(candles, entry, rule):
    i = entry["entry_index"]
    entry_price = entry["entry_price"]
    tp_price = entry_price * (1.0 + rule.tp_pct / 100.0)
    sl_price = entry_price * (1.0 - rule.sl_pct / 100.0)
    deadline = entry["entry_ts"] + rule.hold_minutes * 60
    last_close = entry_price
    exit_ts = entry["entry_ts"]
    reason = "TIME"
    gross = 0.0

    for candle in candles[i + 1:]:
        if candle.ts > deadline:
            break
        last_close = candle.close
        exit_ts = candle.ts
        hit_tp = candle.high >= tp_price
        hit_sl = candle.low <= sl_price
        # 1분봉 안에서 둘 다 닿으면 틱 순서를 모르므로 보수적으로 SL 처리한다.
        if hit_sl:
            reason = "SL"
            gross = -rule.sl_pct
            break
        if hit_tp:
            reason = "TP"
            gross = rule.tp_pct
            break
    else:
        pass

    if reason == "TIME" and candles[-1].ts < deadline:
        return None
    if reason == "TIME":
        gross = pct(last_close, entry_price)
    return {
        "exit_ts": exit_ts,
        "reason": reason,
        "gross_pct": gross,
        "net_pct": gross - FEE_PCT,
    }


def mean_ci(values):
    if not values:
        return 0.0, 0.0
    mean = statistics.fmean(values)
    if len(values) < 2:
        return mean, 0.0
    return mean, 1.96 * statistics.stdev(values) / math.sqrt(len(values))


def max_losing_streak(rows):
    best = current = 0
    for row in sorted(rows, key=lambda x: x["entry_ts"]):
        if row["net_pct"] <= 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def stats(rows):
    values = [r["net_pct"] for r in rows]
    mean, ci = mean_ci(values)
    return {
        "n": len(rows),
        "mean": mean,
        "ci": ci,
        "sum": sum(values),
        "win": 100.0 * sum(v > 0 for v in values) / len(values) if values else 0.0,
        "tp": sum(r["reason"] == "TP" for r in rows),
        "sl": sum(r["reason"] == "SL" for r in rows),
        "time": sum(r["reason"] == "TIME" for r in rows),
        "streak": max_losing_streak(rows),
    }


def print_stat(label, rows):
    s = stats(rows)
    print(
        f"{label:<38} {s['n']:>5}건  평균 {s['mean']:+.3f}% "
        f"(95% ±{s['ci']:.3f})  누적 {s['sum']:+.2f}%  승률 {s['win']:>5.1f}%  "
        f"TP/SL/TIME {s['tp']}/{s['sl']}/{s['time']}  연패 {s['streak']}"
    )


def split_time(rows):
    ordered = sorted(rows, key=lambda x: x["entry_ts"])
    cut = int(len(ordered) * 0.70)
    return ordered[:cut], ordered[cut:]


def run_backtest(conn, markets, start_dt, end_dt):
    start_ts, end_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    detected = defaultdict(list)
    candle_counts = {}
    for index, market in enumerate(markets, 1):
        candles = load_candles(conn, market, start_ts, end_ts)
        candle_counts[market] = len(candles)
        if len(candles) < 180:
            continue
        feature_sets = {
            lookback: build_features(candles, lookback)
            for lookback in {strategy.box_minutes for strategy in STRATEGIES}
        }
        for strategy in STRATEGIES:
            for entry in detect_entries(candles, strategy, feature_sets[strategy.box_minutes]):
                entry["market"] = market
                entry["strategy"] = strategy.name
                for rule in EXIT_RULES:
                    outcome = simulate_exit(candles, entry, rule)
                    if outcome is None:
                        continue
                    row = dict(entry)
                    row.update(outcome)
                    row["exit_rule"] = rule.name
                    detected[(strategy.name, rule.name)].append(row)
        if index % 20 == 0 or index == len(markets):
            print(f"백테스트 진행: {index}/{len(markets)} 시장")

    print("\n" + "=" * 150)
    print("HISTORICAL BREAKOUT LAB V1 — 박스권 압축·거래대금 돌파")
    print("기간:", iso_utc(start_dt), "~", iso_utc(end_dt))
    print(f"시장 {len(markets)}개 | 캔들 {sum(candle_counts.values()):,}개 | 왕복비용 {FEE_PCT:.2f}% 차감")
    print("※ 현재 상장 종목의 과거 데이터만 사용하므로 상장폐지 종목 생존편향이 있습니다.")
    print("※ 기본 신호: 직전 60분 박스 + 거래대금 증가 + 상단 0.2% 돌파 + 2분 종가 유지 후 진입")
    print("=" * 150)
    print("1. 전체 결과")
    for strategy in STRATEGIES:
        for rule in EXIT_RULES:
            rows = detected[(strategy.name, rule.name)]
            print_stat(f"{strategy.name} / {rule.name}", rows)

    print("\n" + "=" * 150)
    print("2. 시간순 70% 발견구간 → 최신 30% 검증구간")
    ranked = []
    for strategy in STRATEGIES:
        for rule in EXIT_RULES:
            rows = detected[(strategy.name, rule.name)]
            old, new = split_time(rows)
            a, b = stats(old), stats(new)
            if len(old) >= 20 and len(new) >= 10:
                ranked.append((min(a["mean"], b["mean"]), strategy.name, rule.name, old, new))
    ranked.sort(reverse=True, key=lambda x: x[0])
    if not ranked:
        print("표시 기준(과거 20건·최신 10건)을 충족한 조합이 없습니다.")
    for _, strategy_name, rule_name, old, new in ranked:
        a, b = stats(old), stats(new)
        verdict = "양쪽 +" if a["mean"] > 0 and b["mean"] > 0 else "재현 실패"
        print(
            f"{strategy_name:<12} {rule_name:<16} | "
            f"과거 {a['n']:>4}건 {a['mean']:+.3f}% | "
            f"최신 {b['n']:>4}건 {b['mean']:+.3f}% | {verdict}"
        )

    print("\n" + "=" * 150)
    print("3. 자동 판정")
    survivors = []
    for _, strategy_name, rule_name, old, new in ranked:
        a, b = stats(old), stats(new)
        if a["mean"] > 0 and b["mean"] > 0 and b["n"] >= 20:
            survivors.append((b["mean"], strategy_name, rule_name, a, b))
    survivors.sort(reverse=True)
    if survivors:
        _, strategy_name, rule_name, a, b = survivors[0]
        print(f"1차 생존 후보: {strategy_name} / {rule_name}")
        print(f"과거 {a['n']}건 {a['mean']:+.3f}% | 최신 {b['n']}건 {b['mean']:+.3f}%")
        print("다음 단계: 월별·거래소별 재검증 후에만 실시간 가상매매 후보로 이동")
    else:
        print("아직 1차 생존 후보가 없습니다(양 구간 플러스 + 최신 20건 조건).")
        print("기간을 늘리되, 결과를 본 뒤 임계값을 계속 바꾸지는 마세요.")
    print("※ 1분봉 내 TP와 SL이 동시에 닿으면 SL로 처리했습니다. 슬리피지는 미반영입니다.")
    print("=" * 150)


def resolve_period(args):
    end_dt = parse_utc(args.end) or datetime.now(UTC).replace(second=0, microsecond=0)
    start_dt = parse_utc(args.start) or (end_dt - timedelta(days=args.days))
    if start_dt >= end_dt:
        raise SystemExit("시작 시각은 종료 시각보다 빨라야 합니다.")
    return start_dt, end_dt


def build_parser():
    parser = argparse.ArgumentParser(
        description="업비트 과거 1분봉 다운로드 및 박스권 돌파 백테스트"
    )
    parser.add_argument("command", nargs="?", choices=("download", "backtest", "all"), default="all")
    parser.add_argument("--db", default=DEFAULT_DB, help="과거 데이터 DB 파일")
    parser.add_argument("--days", type=int, default=30, help="--start 미지정 시 최근 일수 (기본 30)")
    parser.add_argument("--start", help="UTC 시작일/시각, 예: 2026-08-01")
    parser.add_argument("--end", help="UTC 종료일/시각, 예: 2026-09-01")
    parser.add_argument("--markets", help="쉼표 구분 종목, 예: BTC,ETH,SOPH")
    parser.add_argument("--limit-markets", type=int, help="속도 시험용 알파벳순 시장 수 제한")
    return parser


def main():
    args = build_parser().parse_args()
    if args.days <= 0:
        raise SystemExit("--days는 1 이상이어야 합니다.")
    start_dt, end_dt = resolve_period(args)
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        init_db(conn)
        markets = choose_markets(args.markets, args.limit_markets)
        if not markets:
            raise SystemExit("분석할 시장이 없습니다.")
        if args.command in ("download", "all"):
            download_all(conn, markets, start_dt, end_dt)
        if args.command in ("backtest", "all"):
            run_backtest(conn, markets, start_dt, end_dt)
    except KeyboardInterrupt:
        print("\n사용자 중단. 이미 받은 캔들은 DB에 저장되어 있습니다.")
        raise SystemExit(130)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
