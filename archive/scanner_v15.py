import websocket
import json
import urllib.request
import urllib.parse
import threading
import time
import sqlite3
from collections import defaultdict, deque
from datetime import datetime


# =========================================================
# 설정
# =========================================================

HISTORY = 120

SIGNAL_SCORE = 60

COOLDOWN_MINUTES = 30

# 처음에는 50개씩 테스트
PRELOAD_COUNT = 50

CHECK_INTERVAL = 10

# 시그널 이후 가격을 몇 분 동안 저장할지
TRACK_MINUTES = 60

# V14 눌림목 가상매매 설정
ENTRY_WATCH_MINUTES = 15
DIP_ENTRY_PCT = 1.0
DIP_TP_PCT = 5.0
DIP_SL_PCT = 3.0
REBOUND_DRAWDOWN_PCT = 2.0
REBOUND_RECOVERY_PCT = 1.0
REBOUND_TP_PCT = 5.0
REBOUND_SL_PCT = 2.0
PAPER_FEE_PCT = 0.10

# V15 PRE-PUMP 설정
PREPUMP_PRICE_15M_MAX = 2.0
PREPUMP_VOL_5M_MIN = 20.0
PREPUMP_VOL_15M_MIN = 20.0
PREPUMP_VOL_60M_MIN = 10.0
PREPUMP_REPEAT_HOURS = 72
PREPUMP_COOLDOWN_MINUTES = 30
PREPUMP_TRACK_HOURS = 72
PREPUMP_CHECKPOINT_MINUTES = (180, 360, 720, 1440, 2880, 4320)

last_radar_time = 0

# =========================================================
# DB
# =========================================================

DB_FILE = "crypto_scanner.db"

db = sqlite3.connect(
    DB_FILE,
    check_same_thread=False
)

db_lock = threading.Lock()


# =========================================================
# DB 자동 업그레이드
# =========================================================

def init_database():

    with db_lock:

        cursor = db.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            created_at TEXT,

            exchange TEXT,

            market TEXT,

            score INTEGER,

            price REAL,

            price_1m REAL,

            price_5m REAL,

            price_15m REAL,

            volume_5m REAL,

            volume_15m REAL,

            volume_60m REAL,

            price_after_5m REAL,

            price_after_10m REAL,

            price_after_30m REAL,

            price_after_60m REAL,

            return_5m REAL,

            return_10m REAL,

            return_30m REAL,

            return_60m REAL,

            reason TEXT

        )
        """)

        # 시그널 발생 후 1분 단위 가격 흐름.
        # (signal_id, minute)의 UNIQUE 제약으로 중복 저장을 막는다.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_price_history (
            signal_id INTEGER NOT NULL,
            minute INTEGER NOT NULL,
            observed_at TEXT NOT NULL,
            price REAL NOT NULL,
            return_pct REAL NOT NULL,
            PRIMARY KEY (signal_id, minute),
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_signal_price_history_signal
        ON signal_price_history(signal_id, minute)
        """)

        # V14: 눌림목 진입 가상매매 결과. 실제 주문은 전혀 보내지 않는다.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pullback_paper_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER NOT NULL,
            strategy TEXT NOT NULL,
            entry_minute INTEGER NOT NULL,
            entry_at TEXT NOT NULL,
            entry_price REAL NOT NULL,
            entry_return_from_signal REAL NOT NULL,
            tp_pct REAL NOT NULL,
            sl_pct REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            exit_minute INTEGER,
            exit_at TEXT,
            exit_price REAL,
            exit_reason TEXT,
            pnl_pct REAL,
            UNIQUE(signal_id, strategy),
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pullback_paper_trades_status
        ON pullback_paper_trades(status, signal_id)
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pullback_watch (
            signal_id INTEGER PRIMARY KEY,
            started_at TEXT NOT NULL,
            FOREIGN KEY (signal_id) REFERENCES signals(id)
        )
        """)

        # V15: 급등 전조(PRE-PUMP) 이벤트와 72시간 장기 추적
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prepump_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            exchange TEXT NOT NULL,
            market TEXT NOT NULL,
            level TEXT NOT NULL,
            repeat_count INTEGER NOT NULL DEFAULT 1,
            price REAL NOT NULL,
            price_1m REAL,
            price_5m REAL,
            price_15m REAL,
            volume_5m REAL,
            volume_15m REAL,
            volume_60m REAL,
            previous_event_id INTEGER,
            previous_strength REAL,
            strength REAL,
            reason TEXT
        )
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_prepump_market_time
        ON prepump_events(exchange, market, created_at)
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS prepump_tracking (
            event_id INTEGER PRIMARY KEY,
            highest_price REAL NOT NULL,
            lowest_price REAL NOT NULL,
            max_profit_pct REAL NOT NULL DEFAULT 0,
            max_drawdown_pct REAL NOT NULL DEFAULT 0,
            last_seen_at TEXT,
            price_after_3h REAL, return_3h REAL, mfe_3h REAL, mae_3h REAL,
            price_after_6h REAL, return_6h REAL, mfe_6h REAL, mae_6h REAL,
            price_after_12h REAL, return_12h REAL, mfe_12h REAL, mae_12h REAL,
            price_after_24h REAL, return_24h REAL, mfe_24h REAL, mae_24h REAL,
            price_after_48h REAL, return_48h REAL, mfe_48h REAL, mae_48h REAL,
            price_after_72h REAL, return_72h REAL, mfe_72h REAL, mae_72h REAL,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(event_id) REFERENCES prepump_events(id)
        )
        """)

        cursor.execute(
            "PRAGMA table_info(signals)"
        )

        existing_columns = set(
            row[1]
            for row in cursor.fetchall()
        )

        required_columns = {

            "price_1m": "REAL",
            "price_5m": "REAL",
            "price_15m": "REAL",

            "volume_5m": "REAL",
            "volume_15m": "REAL",
            "volume_60m": "REAL",

            "price_after_5m": "REAL",
            "price_after_10m": "REAL",
            "price_after_30m": "REAL",
            "price_after_60m": "REAL",

            "return_5m": "REAL",
            "return_10m": "REAL",
            "return_30m": "REAL",
            "return_60m": "REAL",

            "max_profit_5m": "REAL",
            "max_profit_10m": "REAL",
            "max_profit_30m": "REAL",
            "max_profit_60m": "REAL",

            "max_drawdown_5m": "REAL",
            "max_drawdown_10m": "REAL",
            "max_drawdown_30m": "REAL",
            "max_drawdown_60m": "REAL",

            "reason": "TEXT"
        }

        for column, column_type in required_columns.items():

            if column not in existing_columns:

                print(
                    "DB 업그레이드:",
                    column,
                    "추가"
                )

                cursor.execute(
                    f"""
                    ALTER TABLE signals
                    ADD COLUMN {column} {column_type}
                    """
                )

        db.commit()

        print()
        print(
            "DATABASE READY"
        )


# =========================================================
# 데이터
# =========================================================

data = {

    "UPBIT": defaultdict(
        lambda: deque(
            maxlen=HISTORY
        )
    ),

    "BITHUMB": defaultdict(
        lambda: deque(
            maxlen=HISTORY
        )
    )
}


prices = {

    "UPBIT": {},

    "BITHUMB": {}
}


minute_prices = {

    "UPBIT": defaultdict(
        lambda: deque(
            maxlen=HISTORY
        )
    ),

    "BITHUMB": defaultdict(
        lambda: deque(
            maxlen=HISTORY
        )
    )
}


current_volume = {

    "UPBIT": defaultdict(float),

    "BITHUMB": defaultdict(float)
}


current_minute = {

    "UPBIT": None,

    "BITHUMB": None
}


last_signal = {}

active_signals = []
active_prepumps = []
prepump_last_signal = {}


upbit_markets = []

bithumb_markets = []


# =========================================================
# HTTP
# =========================================================

def http_get(url):

    request = urllib.request.Request(

        url,

        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )


    response = urllib.request.urlopen(
        request,
        timeout=10
    )


    return json.loads(
        response.read()
    )


# =========================================================
# 마켓
# =========================================================

def get_markets(exchange):

    if exchange == "UPBIT":

        url = (
            "https://api.upbit.com/v1/market/all"
            "?is_details=false"
        )

    else:

        url = (
            "https://api.bithumb.com/v1/market/all"
            "?isDetails=false"
        )


    result = http_get(url)


    markets = []


    for item in result:

        market = item.get(
            "market"
        )


        if market and market.startswith(
            "KRW-"
        ):

            markets.append(
                market
            )


    return markets


# =========================================================
# 업비트 과거 데이터
# =========================================================

def load_upbit_candles(market):

    try:

        params = urllib.parse.urlencode({

            "market":
            market,

            "count":
            HISTORY
        })


        url = (
            "https://api.upbit.com/v1/candles/minutes/1?"
            + params
        )


        result = http_get(url)


        result.reverse()


        for candle in result:

            close_price = candle.get(
                "trade_price"
            )

            volume = candle.get(
                "candle_acc_trade_volume",
                0
            )


            if close_price is None:

                continue


            # =====================================
            # 1분 거래대금 계산
            # 거래량 × 가격
            # =====================================

            trade_value = (
                volume
                * close_price
            )


            minute_prices[
                "UPBIT"
            ][market].append(
                close_price
            )


            data[
                "UPBIT"
            ][market].append(
                trade_value
            )


            prices[
                "UPBIT"
            ][market] = close_price


        return len(result)


    except Exception as e:

        print(
            "UPBIT CANDLE ERROR:",
            market,
            e
        )

        return 0


# =========================================================
# 빗썸 과거 데이터
# =========================================================

def load_bithumb_candles(market):

    try:

        params = urllib.parse.urlencode({

            "market":
            market,

            "count":
            HISTORY
        })


        url = (
            "https://api.bithumb.com/v1/candles/minutes/1?"
            + params
        )


        result = http_get(url)


        result.reverse()


        for candle in result:

            close_price = candle.get(
                "trade_price"
            )

            volume = candle.get(
                "candle_acc_trade_volume",
                0
            )


            if close_price is None:

                continue


            # =====================================
            # 1분 거래대금 계산
            # 거래량 × 가격
            # =====================================

            trade_value = (
                volume
                * close_price
            )


            minute_prices[
                "BITHUMB"
            ][market].append(
                close_price
            )


            data[
                "BITHUMB"
            ][market].append(
                trade_value
            )


            prices[
                "BITHUMB"
            ][market] = close_price


        return len(result)


    except Exception as e:

        print(
            "BITHUMB CANDLE ERROR:",
            market,
            e
        )

        return 0


# =========================================================
# 선로딩
# =========================================================

def preload():

    print()
    print(
        "======================================"
    )

    print(
        "HISTORICAL DATA PRELOAD"
    )

    print(
        "최근",
        HISTORY,
        "분 데이터"
    )

    print(
        "======================================"
    )


    print()
    print(
        "UPBIT preload..."
    )


    count = 0


    for market in upbit_markets:

        if count >= PRELOAD_COUNT:

            break


        result = load_upbit_candles(
            market
        )


        if result > 0:

            count += 1


            if count % 10 == 0:

                print(
                    "UPBIT:",
                    count,
                    "/",
                    PRELOAD_COUNT
                )


        time.sleep(
            0.12
        )


    print(
        "UPBIT preload complete:",
        count
    )


    print()
    print(
        "BITHUMB preload..."
    )


    count = 0


    for market in bithumb_markets:

        if count >= PRELOAD_COUNT:

            break


        result = load_bithumb_candles(
            market
        )


        if result > 0:

            count += 1


            if count % 10 == 0:

                print(
                    "BITHUMB:",
                    count,
                    "/",
                    PRELOAD_COUNT
                )


        time.sleep(
            0.12
        )


    print(
        "BITHUMB preload complete:",
        count
    )


# =========================================================
# 1분봉 확정
# =========================================================

def finish_minute(exchange):

    # -----------------------------------------
    # 현재 1분봉 확정
    # -----------------------------------------

    for market in list(
        prices[exchange].keys()
    ):

        price = prices[
            exchange
        ].get(market)

        if price is None:
            continue

        # 현재 1분 거래대금
        trade_value = current_volume[
            exchange
        ].get(
            market,
            0
        )

        # 거래대금 기록
        data[
            exchange
        ][market].append(
            trade_value
        )

        # 종가 기록
        minute_prices[
            exchange
        ][market].append(
            price
        )


    # -----------------------------------------
    # 현재 분 거래대금 초기화
    # -----------------------------------------

    current_volume[
        exchange
    ].clear()


# =========================================================
# 가격 변화
# =========================================================

def price_change(
    exchange,
    market,
    minutes
):

    history = minute_prices[
        exchange
    ].get(
        market
    )

    if not history:
        return None

    values = list(
        history
    )

    # 필요한 만큼의 완성된 1분봉이 없으면
    # 계산하지 않는다.

    if len(values) <= minutes:
        return None

    old_price = values[
        -minutes - 1
    ]

    current_price = values[-1]

    if old_price is None:
        return None

    if current_price is None:
        return None

    if old_price <= 0:
        return None

    return (
        current_price / old_price - 1
    ) * 100

    history = minute_prices[
        exchange
    ].get(
        market
    )


    if not history:

        return None


    values = list(
        history
    )


    if len(values) < minutes + 1:

        return None


    old = values[
        -minutes - 1
    ]

    new = values[-1]


    if old <= 0:

        return None


    return (
        new / old - 1
    ) * 100


# =========================================================
# 이동평균선
# =========================================================

def moving_average(exchange, market, period):

    history = minute_prices[
        exchange
    ].get(market)

    if not history:
        return None

    values = list(history)

    if len(values) < period:
        return None

    recent = values[-period:]

    if any(
        price is None or price <= 0
        for price in recent
    ):
        return None

    return sum(recent) / period


# =========================================================
# 이동평균선 상태
# =========================================================

def moving_average_signal(exchange, market):

    ma5 = moving_average(
        exchange,
        market,
        5
    )

    ma20 = moving_average(
        exchange,
        market,
        20
    )

    if ma5 is None or ma20 is None:
        return None

    if ma5 > ma20:
        return "BULLISH"

    elif ma5 < ma20:
        return "BEARISH"

    else:
        return "NEUTRAL"

# =========================================================
# 거래량 / 거래대금 배수
# =========================================================

# =========================================================
# 진짜 골든크로스 감지
# =========================================================

def golden_cross_signal(exchange, market):

    history = minute_prices[
        exchange
    ].get(market)

    if not history:
        return None

    values = list(history)

    # 현재 MA5 / MA20을 계산하려면
    # 최소 20개 이상의 데이터가 필요
    if len(values) < 21:
        return None

    current_ma5 = sum(
        values[-5:]
    ) / 5

    current_ma20 = sum(
        values[-20:]
    ) / 20

    # 바로 이전 시점의 MA
    previous_ma5 = sum(
        values[-6:-1]
    ) / 5

    previous_ma20 = sum(
        values[-21:-1]
    ) / 20

    # 진짜 골든크로스
    if (
        previous_ma5 <= previous_ma20
        and
        current_ma5 > current_ma20
    ):
        return "GOLDEN_CROSS"

    # 현재 이미 MA5가 위
    if current_ma5 > current_ma20:
        return "BULLISH"

    return "BEARISH"

    # =========================================================
# MA 추세
# =========================================================

def ma_trend(exchange, market):

    history = minute_prices[
        exchange
    ].get(market)

    if not history:
        return None

    values = list(history)

    if len(values) < 21:
        return None

    current_ma5 = sum(
        values[-5:]
    ) / 5

    previous_ma5 = sum(
        values[-6:-1]
    ) / 5

    if current_ma5 > previous_ma5:
        return "UP"

    elif current_ma5 < previous_ma5:
        return "DOWN"

    return "FLAT"

# =========================================================
# 현재 1분 거래대금 포함
# =========================================================

def get_volume_history(
    exchange,
    market
):

    history = list(
        data[
            exchange
        ].get(
            market,
            []
        )
    )

    current = current_volume[
        exchange
    ].get(
        market,
        0
    )

    if current > 0:

        history.append(
            current
        )

    return history


# =========================================================
# 거래대금 배수 계산 V11.5
# 현재 동일 구간 vs 직전 동일 구간
# =========================================================

def volume_ratio(exchange, market, period):

    values = get_volume_history(
        exchange,
        market
    )

    if not values:
        return None

    # 최소 2개 구간 필요
    if len(values) < period * 2:
        return None

    # =========================================
    # 현재 구간
    # =========================================

    current = sum(
        values[-period:]
    )

    # =========================================
    # 바로 이전 동일 구간
    # =========================================

    previous = sum(
        values[-period * 2:-period]
    )

    if current <= 0:
        return None

    if previous <= 0:
        return None

    # =========================================
    # 거래대금 배수
    # =========================================

    ratio = current / previous

    return ratio

# =========================================================
# 가격 상승 필터
# =========================================================

def price_momentum(exchange, market):

    change_1m = price_change(
        exchange,
        market,
        1
    )

    change_5m = price_change(
        exchange,
        market,
        5
    )

    change_15m = price_change(
        exchange,
        market,
        15
    )

    return (
        change_1m,
        change_5m,
        change_15m
    )
    # =========================================================
# 진짜 급등 후보 필터
# =========================================================

def is_real_surge_candidate(
    change_1m,
    change_5m,
    change_15m,
    vol_5m,
    vol_15m
):

    if change_1m is None:
        return False

    if change_5m is None:
        return False

    if change_15m is None:
        return False

    if vol_5m is None:
        return False

    if vol_15m is None:
        return False


    # -----------------------------------------
    # 가격이 하락하거나 움직임이 없으면 제외
    # -----------------------------------------

    if change_5m <= 0:
        return False

    if change_15m <= 0:
        return False

    # -----------------------------------------
    # 거래대금만 폭발한 경우 제외
    # -----------------------------------------

    if vol_5m < 2:
        return False

    if vol_15m < 2:
        return False

    return True
# =========================================================
# 점수
# =========================================================

def calculate_score(
    r5,
    r15,
    r60,
    p1,
    p5,
    p15
):

    score = 0


    # -----------------------------------------
    # 거래대금
    # -----------------------------------------

    if r5 is not None:

        if r5 >= 3:
            score += 10

        if r5 >= 5:
            score += 10

        if r5 >= 10:
            score += 10


    if r15 is not None:

        if r15 >= 3:
            score += 10

        if r15 >= 5:
            score += 10


    if r60 is not None:

        if r60 >= 2:
            score += 5

        if r60 >= 3:
            score += 5


    # -----------------------------------------
    # 가격
    # -----------------------------------------

    if p1 is not None:

        if p1 >= 0.3:
            score += 5

        if p1 >= 0.7:
            score += 5


    if p5 is not None:

        if p5 >= 1:
            score += 5

        if p5 >= 3:
            score += 5


    if p15 is not None:

        if p15 >= 3:
            score += 5


    # -----------------------------------------
    # 과도한 상승 감점
    # -----------------------------------------

    if p5 is not None:

        if p5 < -2:

            score -= 15


    if p15 is not None:

        if p15 >= 20:

            score -= 15

        if p15 >= 30:

            score -= 15


    return max(
        0,
        min(
            score,
            100
        )
    )


# =========================================================
# 신호 이유
# =========================================================

def make_reason(
    r5,
    r15,
    r60,
    p1,
    p5,
    p15
):

    reasons = []


    if r5 is not None and r5 >= 5:

        reasons.append(
            f"5분 거래대금 {r5:.1f}배"
        )


    if r15 is not None and r15 >= 3:

        reasons.append(
            f"15분 거래대금 {r15:.1f}배"
        )


    if r60 is not None and r60 >= 2:

        reasons.append(
            f"60분 거래대금 {r60:.1f}배"
        )


    if p1 is not None and p1 >= 0.5:

        reasons.append(
            f"1분 +{p1:.2f}%"
        )


    if p5 is not None and p5 >= 2:

        reasons.append(
            f"5분 +{p5:.2f}%"
        )


    if p15 is not None and p15 >= 3:

        reasons.append(
            f"15분 +{p15:.2f}%"
        )


    if not reasons:

        reasons.append(
            "복합 조건 충족"
        )


    return " / ".join(
        reasons
    )


# =========================================================
# DB 저장
# =========================================================

def save_signal(
    exchange,
    market,
    score,
    price,
    p1,
    p5,
    p15,
    r5,
    r15,
    r60,
    reason
):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    with db_lock:

        cursor = db.cursor()


        cursor.execute(
            """
            INSERT INTO signals (

                created_at,
                exchange,
                market,
                score,
                price,
                price_1m,
                price_5m,
                price_15m,
                volume_5m,
                volume_15m,
                volume_60m,
                reason

            )

            VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,

            (
                now,
                exchange,
                market,
                score,
                price,
                p1,
                p5,
                p15,
                r5,
                r15,
                r60,
                reason
            )
        )


        db.commit()


        return cursor.lastrowid


def save_price_history(signal_id, minute, price, original):

    if original is None or original <= 0 or price is None or price <= 0:
        return

    minute = max(0, min(int(minute), TRACK_MINUTES))
    result = (price / original - 1) * 100
    observed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db_lock:
        db.execute(
            """
            INSERT OR IGNORE INTO signal_price_history
                (signal_id, minute, observed_at, price, return_pct)
            VALUES (?, ?, ?, ?, ?)
            """,
            (signal_id, minute, observed_at, price, result)
        )
        db.commit()


# =========================================================
# V14 눌림목 가상매매
# =========================================================

def register_pullback_watch(signal_id):
    with db_lock:
        db.execute(
            "INSERT OR IGNORE INTO pullback_watch(signal_id, started_at) VALUES (?, ?)",
            (signal_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        db.commit()


def has_pullback_watch(signal_id):
    with db_lock:
        return db.execute(
            "SELECT 1 FROM pullback_watch WHERE signal_id = ?",
            (signal_id,)
        ).fetchone() is not None


def strategy_exists(signal_id, strategy):
    with db_lock:
        return db.execute(
            "SELECT 1 FROM pullback_paper_trades WHERE signal_id=? AND strategy=?",
            (signal_id, strategy)
        ).fetchone() is not None


def open_paper_trade(signal, strategy, minute, price, tp_pct, sl_pct):
    original = signal["price"]
    if original is None or original <= 0 or price is None or price <= 0:
        return False
    entry_return = (price / original - 1) * 100
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_lock:
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO pullback_paper_trades
                (signal_id, strategy, entry_minute, entry_at, entry_price,
                 entry_return_from_signal, tp_pct, sl_pct, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """,
            (signal["id"], strategy, minute, now_text, price,
             entry_return, tp_pct, sl_pct)
        )
        db.commit()
        created = cursor.rowcount > 0
    if created:
        print()
        print("======================================")
        print("🟢 V14 PAPER ENTRY", strategy)
        print(signal["exchange"], "|", signal["market"])
        print("ENTRY MINUTE:", minute, "| PRICE:", price)
        print("FROM SIGNAL:", f"{entry_return:+.2f}%")
        print("TP:", f"+{tp_pct:.1f}%", "| SL:", f"-{sl_pct:.1f}%")
        print("※ 가상매매 기록이며 실제 주문은 전송하지 않습니다.")
        print("======================================")
    return created


def rebuild_v14_state(signal):
    """저장된 실제 분 가격으로 고점·눌림·저점을 복구한다."""
    with db_lock:
        rows = db.execute(
            """
            SELECT minute, price FROM signal_price_history
            WHERE signal_id=? AND minute BETWEEN 0 AND ? ORDER BY minute
            """,
            (signal["id"], ENTRY_WATCH_MINUTES)
        ).fetchall()
    peak = signal["price"]
    trough = signal["price"]
    pulled_back = False
    for _, price in rows:
        if price is None or price <= 0:
            continue
        if not pulled_back:
            peak = max(peak, price)
            drawdown = (price / peak - 1) * 100
            if drawdown <= -REBOUND_DRAWDOWN_PCT:
                pulled_back = True
                trough = price
        else:
            trough = min(trough, price)
    signal["v14_peak"] = peak
    signal["v14_trough"] = trough
    signal["v14_pulled_back"] = pulled_back


def evaluate_v14_entries(signal, minute, price):
    """새로 관측한 1분 값에서만 진입 여부를 판정한다."""
    if not signal.get("v14_enabled") or minute <= 0 or minute > ENTRY_WATCH_MINUTES:
        return

    original = signal["price"]
    signal_return = (price / original - 1) * 100

    # 단순 DIP: 신호 가격 대비 -1% 도달
    if signal_return <= -DIP_ENTRY_PCT and not strategy_exists(signal["id"], "DIP_MINUS_1"):
        open_paper_trade(
            signal, "DIP_MINUS_1", minute, price, DIP_TP_PCT, DIP_SL_PCT
        )

    # REBOUND: 관찰 고점에서 -2% 눌림 후 관찰 저점에서 +1% 회복
    if not signal.get("v14_pulled_back", False):
        signal["v14_peak"] = max(signal.get("v14_peak", original), price)
        drawdown = (price / signal["v14_peak"] - 1) * 100
        if drawdown <= -REBOUND_DRAWDOWN_PCT:
            signal["v14_pulled_back"] = True
            signal["v14_trough"] = price
            print(
                "[V14 REBOUND WATCH]", signal["market"],
                f"고점 대비 {drawdown:+.2f}% — 반등 대기"
            )
    else:
        signal["v14_trough"] = min(signal.get("v14_trough", price), price)
        recovery = (price / signal["v14_trough"] - 1) * 100
        if recovery >= REBOUND_RECOVERY_PCT and not strategy_exists(signal["id"], "REBOUND_2_1"):
            open_paper_trade(
                signal, "REBOUND_2_1", minute, price,
                REBOUND_TP_PCT, REBOUND_SL_PCT
            )


def update_v14_paper_trades(signal, minute, price):
    """1분 관측값 기준으로 TP/SL을 먼저 도달한 순서대로 마감한다."""
    with db_lock:
        trades = db.execute(
            """
            SELECT id, strategy, entry_minute, entry_price, tp_pct, sl_pct
            FROM pullback_paper_trades
            WHERE signal_id=? AND status='OPEN'
            ORDER BY id
            """,
            (signal["id"],)
        ).fetchall()

    for trade_id, strategy, entry_minute, entry_price, tp_pct, sl_pct in trades:
        if minute <= entry_minute:
            continue
        raw_return = (price / entry_price - 1) * 100
        reason = None
        pnl = None
        if raw_return >= tp_pct:
            reason, pnl = "TP", tp_pct - PAPER_FEE_PCT
        elif raw_return <= -sl_pct:
            reason, pnl = "SL", -sl_pct - PAPER_FEE_PCT
        elif minute >= TRACK_MINUTES:
            reason, pnl = "TIME", raw_return - PAPER_FEE_PCT
        if reason is None:
            continue

        with db_lock:
            db.execute(
                """
                UPDATE pullback_paper_trades
                SET status='CLOSED', exit_minute=?, exit_at=?, exit_price=?,
                    exit_reason=?, pnl_pct=?
                WHERE id=? AND status='OPEN'
                """,
                (minute, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 price, reason, pnl, trade_id)
            )
            db.commit()
        print(
            "[V14 PAPER EXIT]", signal["market"], strategy,
            reason, f"{pnl:+.2f}%", f"({minute}m)"
        )


def restore_active_signals():
    """재시작 시 아직 60분이 지나지 않은 신호를 다시 추적한다."""

    now = time.time()
    restored = 0

    with db_lock:
        rows = db.execute(
            """
            SELECT id, created_at, exchange, market, price,
                   price_after_5m, price_after_10m,
                   price_after_30m, price_after_60m
            FROM signals
            WHERE price_after_60m IS NULL
            ORDER BY id DESC
            """
        ).fetchall()

    for row in rows:
        signal_id, created_at, exchange, market, original = row[:5]

        try:
            started = datetime.strptime(
                created_at, "%Y-%m-%d %H:%M:%S"
            ).timestamp()
        except (TypeError, ValueError):
            continue

        elapsed = now - started
        if elapsed < 0 or elapsed > TRACK_MINUTES * 60:
            continue

        with db_lock:
            history = db.execute(
                """
                SELECT minute, price
                FROM signal_price_history
                WHERE signal_id = ?
                ORDER BY minute
                """,
                (signal_id,)
            ).fetchall()

        saved_prices = [item[1] for item in history if item[1] is not None]
        highest = max([original] + saved_prices)
        lowest = min([original] + saved_prices)
        last_minute = max([item[0] for item in history], default=-1)

        restored_signal = {
            "id": signal_id,
            "exchange": exchange,
            "market": market,
            "price": original,
            "time": started,
            "highest_price": highest,
            "lowest_price": lowest,
            "done5": row[5] is not None,
            "done10": row[6] is not None,
            "done30": row[7] is not None,
            "done60": row[8] is not None,
            "last_history_minute": last_minute,
            "v14_enabled": has_pullback_watch(signal_id),
            "v14_peak": original,
            "v14_trough": original,
            "v14_pulled_back": False
        }
        if restored_signal["v14_enabled"]:
            rebuild_v14_state(restored_signal)
        active_signals.append(restored_signal)
        # 재시작 직후 같은 코인 신호가 중복 발생하지 않게 쿨다운도 복구
        last_signal[(exchange, market)] = started
        restored += 1

    print("ACTIVE SIGNALS RESTORED:", restored)


# =========================================================
# 결과 업데이트
# =========================================================

def update_result(
    signal_id,
    price_field,
    return_field,
    price,
    original
):

    if original <= 0:

        return


    result = (
        price / original - 1
    ) * 100


    with db_lock:

        db.execute(
            f"""
            UPDATE signals

            SET
                {price_field} = ?,
                {return_field} = ?

            WHERE id = ?
            """,

            (
                price,
                result,
                signal_id
            )
        )


        db.commit()


def update_metric(
    signal_id,
    column,
    value
):

    with db_lock:

        cursor = db.cursor()

        cursor.execute(
            f"""
            UPDATE signals
            SET {column} = ?
            WHERE id = ?
            """,
            (
                value,
                signal_id
            )
        )

        db.commit()

# =========================================================
# 정확한 분 기록으로 결과 확정 (V13.1)
# =========================================================

def complete_checkpoint(signal, minute):
    """해당 분의 실제 저장값이 있을 때만 결과를 기록한다."""

    column_map = {
        5: ("price_after_5m", "return_5m", "max_profit_5m", "max_drawdown_5m"),
        10: ("price_after_10m", "return_10m", "max_profit_10m", "max_drawdown_10m"),
        30: ("price_after_30m", "return_30m", "max_profit_30m", "max_drawdown_30m"),
        60: ("price_after_60m", "return_60m", "max_profit_60m", "max_drawdown_60m"),
    }

    price_field, return_field, max_field, drawdown_field = column_map[minute]

    with db_lock:
        exact = db.execute(
            """
            SELECT price, return_pct
            FROM signal_price_history
            WHERE signal_id = ? AND minute = ?
            """,
            (signal["id"], minute)
        ).fetchone()

        # 재시작 중 해당 시점을 놓쳤다면 현재가로 과거를 채우지 않는다.
        if exact is None:
            return None

        extrema = db.execute(
            """
            SELECT MAX(return_pct), MIN(return_pct)
            FROM signal_price_history
            WHERE signal_id = ? AND minute BETWEEN 0 AND ?
            """,
            (signal["id"], minute)
        ).fetchone()

        max_profit = extrema[0] if extrema[0] is not None else exact[1]
        max_drawdown = extrema[1] if extrema[1] is not None else exact[1]

        db.execute(
            f"""
            UPDATE signals
            SET {price_field} = ?, {return_field} = ?,
                {max_field} = ?, {drawdown_field} = ?
            WHERE id = ?
            """,
            (exact[0], exact[1], max_profit, max_drawdown, signal["id"])
        )
        db.commit()

    return exact[1], max_profit, max_drawdown


# =========================================================
# 결과 추적
# =========================================================

def track_signals():

    now = time.time()

    for signal in active_signals[:]:
        exchange = signal["exchange"]
        market = signal["market"]
        original = signal["price"]
        current = prices[exchange].get(market)

        if current is None:
            continue

        elapsed = now - signal["time"]
        history_minute = min(int(elapsed // 60), TRACK_MINUTES)

        # 실제로 관측한 현재 분만 저장한다. 빠진 과거 분은 채우지 않는다.
        is_new_history_minute = history_minute > signal.get("last_history_minute", -1)
        if is_new_history_minute:
            save_price_history(signal["id"], history_minute, current, original)
            signal["last_history_minute"] = history_minute
            evaluate_v14_entries(signal, history_minute, current)
            update_v14_paper_trades(signal, history_minute, current)

        checkpoints = (
            (5, "done5"),
            (10, "done10"),
            (30, "done30"),
            (60, "done60"),
        )

        for minute, done_key in checkpoints:
            if elapsed < minute * 60 or signal[done_key]:
                continue

            result = complete_checkpoint(signal, minute)
            signal[done_key] = True

            if result is None:
                print(
                    "[RESULT SKIPPED]",
                    market,
                    f"{minute}m: 재시작 중 실제 가격 기록 없음"
                )
            else:
                return_pct, max_profit, max_drawdown = result
                print(
                    "[RESULT]",
                    market,
                    f"{minute}m:",
                    f"{return_pct:+.2f}%",
                    "| MAX:",
                    f"{max_profit:+.2f}%",
                    "| DD:",
                    f"{max_drawdown:+.2f}%"
                )

        if all(signal[key] for key in ("done5", "done10", "done30", "done60")):
            active_signals.remove(signal)

# =========================================================
# LIVE SURGE RADAR TOP 10
# =========================================================

# def show_surge_radar():

#     candidates = []

#     for exchange in [
#         "UPBIT",
#         "BITHUMB"
#     ]:

#         for market in list(
#             data[exchange].keys()
#         ):

#             try:

#                 r5 = volume_ratio(
#                     exchange,
#                     market,
#                     5
#                 )

#                 r15 = volume_ratio(
#                     exchange,
#                     market,
#                     15
#                 )

#                 r60 = volume_ratio(
#                     exchange,
#                     market,
#                     60
#                 )

#                 p1 = price_change(
#                     exchange,
#                     market,
#                     1
#                 )

#                 p5 = price_change(
#                     exchange,
#                     market,
#                     5
#                 )

#                 p15 = price_change(
#                     exchange,
#                     market,
#                     15
#                 )

#                 ma_signal = moving_average_signal(
#                     exchange,
#                     market
#                 )

#                 golden_signal = golden_cross_signal(
#                     exchange,
#                     market
#                 )

#                 # 데이터 부족
#                 if (
#                     r5 is None
#                     or r15 is None
#                     or p5 is None
#                     or p15 is None
#                 ):
#                     continue

#                 # 거래대금 + 가격 기반 간단 레이더 점수
#                 radar_score = 0

#                 # 5분 거래대금
#                 if r5 >= 2:
#                     radar_score += 10

#                 if r5 >= 5:
#                     radar_score += 5

#                 if r5 >= 10:
#                     radar_score += 5

#                 # 15분 거래대금
#                 if r15 >= 2:
#                     radar_score += 10

#                 if r15 >= 5:
#                     radar_score += 5

#                 # 가격
#                 if p5 > 0:
#                     radar_score += 5

#                 if p5 >= 1:
#                     radar_score += 5

#                 if p5 >= 3:
#                     radar_score += 5

#                 # 이동평균
#                 if ma_signal == "BULLISH":
#                     radar_score += 5

#                 # 골든크로스
#                 if golden_signal == "GOLDEN_CROSS":
#                     radar_score += 10

#                 # 후보 저장
#                 candidates.append({

#                     "exchange":
#                     exchange,

#                     "market":
#                     market,

#                     "score":
#                     radar_score,

#                     "r5":
#                     r5,

#                     "r15":
#                     r15,

#                     "r60":
#                     r60,

#                     "p1":
#                     p1,

#                     "p5":
#                     p5,

#                     "p15":
#                     p15,

#                     "ma":
#                     ma_signal,

#                     "golden":
#                     golden_signal
#                 })

#             except Exception:
#                 continue

#     # 점수 높은 순
#     candidates.sort(
#         key=lambda x: x["score"],
#         reverse=True
#     )

#     top = candidates[:10]

#     print()
#     print(
#         "========================================"
#     )

#     print(
#         "📡 LIVE SURGE RADAR TOP 10"
#     )

#     print(
#         "========================================"
#     )

#     if not top:

#         print(
#             "현재 조건을 만족하는 후보가 없습니다."
#         )

#         return

#     for i, item in enumerate(
#         top,
#         1
#     ):

#         print()

#         print(
#             f"{i}. "
#             f"{item['exchange']} | "
#             f"{item['market']}"
#         )

#         print(
#             f"   RADAR SCORE: "
#             f"{item['score']}"
#         )

#         print(
#             f"   VOL 5m: "
#             f"{item['r5']:.1f}x"
#         )

#         print(
#             f"   VOL 15m: "
#             f"{item['r15']:.1f}x"
#         )

#         print(
#             f"   VOL 60m: "
#             f"{'-' if item['r60'] is None else f'{item['r60']:.1f}x'}"
#         )

#         print(
#             f"   PRICE 1m: "
#             f"{item['p1']:+.2f}%"
#         )

#         print(
#             f"   PRICE 5m: "
#             f"{item['p5']:+.2f}%"
#         )

#         print(
#             f"   PRICE 15m: "
#             f"{item['p15']:+.2f}%"
#         )

#         print(
#             f"   MA: "
#             f"{item['ma']}"
#         )

#         print(
#             f"   GOLDEN: "
#             f"{item['golden']}"
#         )

#     print()
#     print(
#         "========================================"
#     )

# =========================================================
# V15 PRE-PUMP — 급등 전조 감지 / 72시간 추적
# =========================================================

def prepump_strength(r5, r15, r60):
    """거래대금 강도를 한 숫자로 비교하기 위한 단순 지표."""
    if None in (r5, r15, r60):
        return 0.0
    return (r5 * 0.45) + (r15 * 0.40) + (r60 * 0.15)


def is_prepump_candidate(p15, r5, r15, r60):
    # EDGEX 한 종목에 맞추지 않고 넓은 1차 가설로 시작한다.
    if None in (p15, r5, r15, r60):
        return False
    return (
        p15 <= PREPUMP_PRICE_15M_MAX
        and p15 > -3.0
        and r5 >= PREPUMP_VOL_5M_MIN
        and r15 >= PREPUMP_VOL_15M_MIN
        and r60 >= PREPUMP_VOL_60M_MIN
    )


def save_prepump_event(exchange, market, price, p1, p5, p15, r5, r15, r60):
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_ts = time.time()
    strength = prepump_strength(r5, r15, r60)

    with db_lock:
        previous = db.execute(
            """
            SELECT id, created_at, repeat_count, strength
            FROM prepump_events
            WHERE exchange=? AND market=?
            ORDER BY id DESC LIMIT 1
            """,
            (exchange, market)
        ).fetchone()

        previous_id = None
        previous_strength = None
        repeat_count = 1
        level = "PRE_PUMP_WATCH"

        if previous:
            try:
                previous_ts = datetime.strptime(previous[1], "%Y-%m-%d %H:%M:%S").timestamp()
            except (TypeError, ValueError):
                previous_ts = 0

            if 0 <= now_ts - previous_ts <= PREPUMP_REPEAT_HOURS * 3600:
                previous_id = previous[0]
                repeat_count = int(previous[2] or 1) + 1
                previous_strength = previous[3]
                level = "PRE_PUMP_HOT"
                if previous_strength is not None and strength > previous_strength:
                    level = "PRE_PUMP_STRONG"

        reason = (
            f"15m {p15:+.2f}% / VOL 5m {r5:.1f}x / "
            f"15m {r15:.1f}x / 60m {r60:.1f}x / repeat {repeat_count}"
        )
        cur = db.execute(
            """
            INSERT INTO prepump_events
            (created_at, exchange, market, level, repeat_count, price,
             price_1m, price_5m, price_15m, volume_5m, volume_15m, volume_60m,
             previous_event_id, previous_strength, strength, reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (now_text, exchange, market, level, repeat_count, price,
             p1, p5, p15, r5, r15, r60,
             previous_id, previous_strength, strength, reason)
        )
        event_id = cur.lastrowid
        db.execute(
            """
            INSERT INTO prepump_tracking
            (event_id, highest_price, lowest_price, max_profit_pct,
             max_drawdown_pct, last_seen_at)
            VALUES (?, ?, ?, 0, 0, ?)
            """,
            (event_id, price, price, now_text)
        )
        db.commit()

    active_prepumps.append({
        "id": event_id, "exchange": exchange, "market": market,
        "price": price, "time": now_ts, "highest_price": price,
        "lowest_price": price, "done": set()
    })
    prepump_last_signal[(exchange, market)] = now_ts

    print()
    print("======================================")
    print("🚨 V15", level, exchange, "|", market)
    print("PRICE:", price, "| 15m:", f"{p15:+.2f}%")
    print("VOL 5m:", f"{r5:.1f}x", "| 15m:", f"{r15:.1f}x", "| 60m:", f"{r60:.1f}x")
    print("REPEAT:", repeat_count, "| STRENGTH:", f"{strength:.1f}")
    print("※ V15는 관찰 신호이며 실제 주문을 전송하지 않습니다.")
    print("======================================")


def restore_active_prepumps():
    now = time.time()
    restored = 0
    with db_lock:
        rows = db.execute(
            """
            SELECT e.id, e.created_at, e.exchange, e.market, e.price,
                   t.highest_price, t.lowest_price,
                   t.return_3h, t.return_6h, t.return_12h,
                   t.return_24h, t.return_48h, t.return_72h
            FROM prepump_events e
            JOIN prepump_tracking t ON t.event_id=e.id
            WHERE t.completed=0
            ORDER BY e.id
            """
        ).fetchall()

    checkpoints = [180, 360, 720, 1440, 2880, 4320]
    for row in rows:
        try:
            started = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S").timestamp()
        except (TypeError, ValueError):
            continue
        elapsed = now - started
        if elapsed < 0 or elapsed > PREPUMP_TRACK_HOURS * 3600 + 300:
            continue
        done = {m for m, value in zip(checkpoints, row[7:13]) if value is not None}
        active_prepumps.append({
            "id": row[0], "exchange": row[2], "market": row[3],
            "price": row[4], "time": started,
            "highest_price": row[5] or row[4], "lowest_price": row[6] or row[4],
            "done": done
        })
        prepump_last_signal[(row[2], row[3])] = max(
            prepump_last_signal.get((row[2], row[3]), 0), started
        )
        restored += 1
    print("V15 PRE-PUMP TRACKS RESTORED:", restored)


def update_prepump_tracking():
    now = time.time()
    labels = {180:"3h", 360:"6h", 720:"12h", 1440:"24h", 2880:"48h", 4320:"72h"}

    for item in active_prepumps[:]:
        current = prices[item["exchange"]].get(item["market"])
        if current is None or current <= 0:
            continue

        original = item["price"]
        item["highest_price"] = max(item["highest_price"], current)
        item["lowest_price"] = min(item["lowest_price"], current)
        mfe = (item["highest_price"] / original - 1) * 100
        mae = (item["lowest_price"] / original - 1) * 100
        elapsed_min = int((now - item["time"]) // 60)
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with db_lock:
            db.execute(
                """
                UPDATE prepump_tracking
                SET highest_price=?, lowest_price=?, max_profit_pct=?,
                    max_drawdown_pct=?, last_seen_at=?
                WHERE event_id=?
                """,
                (item["highest_price"], item["lowest_price"], mfe, mae, now_text, item["id"])
            )

            for minute in PREPUMP_CHECKPOINT_MINUTES:
                if elapsed_min < minute or minute in item["done"]:
                    continue
                label = labels[minute]
                ret = (current / original - 1) * 100
                db.execute(
                    f"""
                    UPDATE prepump_tracking
                    SET price_after_{label}=?, return_{label}=?,
                        mfe_{label}=?, mae_{label}=?
                    WHERE event_id=?
                    """,
                    (current, ret, mfe, mae, item["id"])
                )
                item["done"].add(minute)
                print("[V15 RESULT]", item["market"], label,
                      f"RETURN {ret:+.2f}% | MFE {mfe:+.2f}% | MAE {mae:+.2f}%")

            if elapsed_min >= PREPUMP_TRACK_HOURS * 60:
                db.execute("UPDATE prepump_tracking SET completed=1 WHERE event_id=?", (item["id"],))
                active_prepumps.remove(item)
            db.commit()


def evaluate_prepump(exchange, market, price, p1, p5, p15, r5, r15, r60):
    if not is_prepump_candidate(p15, r5, r15, r60):
        return
    key = (exchange, market)
    now = time.time()
    if now - prepump_last_signal.get(key, 0) < PREPUMP_COOLDOWN_MINUTES * 60:
        return
    save_prepump_event(exchange, market, price, p1, p5, p15, r5, r15, r60)


# =========================================================
# 분석
# =========================================================

def analyze():

    for exchange in [
        "UPBIT",
        "BITHUMB"
    ]:

        for market in list(
            data[exchange].keys()
        ):

            r5 = volume_ratio(
                exchange,
                market,
                5
            )

            r15 = volume_ratio(
                exchange,
                market,
                15
            )

            r60 = volume_ratio(
                exchange,
                market,
                60
            )


            p1 = price_change(
                exchange,
                market,
                1
            )

            p5 = price_change(
                exchange,
                market,
                5
            )

            p15 = price_change(
                exchange,
                market,
                15
            )

            ma5 = moving_average(
                exchange,
                market,
                5
            )

            ma20 = moving_average(
                exchange,
                market,
                20
            )

            ma_signal = moving_average_signal(
                exchange,
                market
            )

            golden_signal = golden_cross_signal(
                exchange,
                market
            )

            ma_direction = ma_trend(
                exchange,
                market
            )

            # V15 PRE-PUMP는 기존 V14 급등 필터와 독립적으로 검사한다.
            price = prices[exchange].get(market)
            if price is not None:
                evaluate_prepump(exchange, market, price, p1, p5, p15, r5, r15, r60)

            # =========================================
            # 실제 급등 후보 필터 (기존 V14 유지)
            # =========================================

            if p5 is None or p15 is None:
                continue

            if r5 is None or r15 is None:
                continue

            # 가격이 5분/15분 기준으로 상승하지 않으면 제외
            if p5 <= 0 or p15 <= 0:
                continue

            # 거래대금만 폭발하고 가격이 움직이지 않는 경우 제외
            if r5 < 2 or r15 < 2:
                continue

            score = calculate_score(

                r5,
                r15,
                r60,

                p1,
                p5,
                p15
            )


            if score < SIGNAL_SCORE:

                continue


            price = prices[
                exchange
            ].get(
                market
            )


            if price is None:

                continue


            key = (
                exchange,
                market
            )


            now = time.time()


            previous = last_signal.get(
                key,
                0
            )


            if (
                now - previous
                < COOLDOWN_MINUTES * 60
            ):

                continue


            reason = make_reason(

                r5,
                r15,
                r60,

                p1,
                p5,
                p15
            )


            signal_id = save_signal(

                exchange,
                market,

                score,
                price,

                p1,
                p5,
                p15,

                r5,
                r15,
                r60,

                reason
            )


            last_signal[
                key
            ] = now


            active_signals.append({

                "id":
                signal_id,

                "exchange":
                exchange,

                "market":
                market,

                "price":
                price,

                "time":
                now,

                "highest_price":
                price,

                "lowest_price":
                price,

                "done5":
                False,

                "done10":
                False,

                "done30":
                False,

                "done60":
                False,

                "last_history_minute":
                0,

                "v14_enabled":
                True,

                "v14_peak":
                price,

                "v14_trough":
                price,

                "v14_pulled_back":
                False
            })

            register_pullback_watch(signal_id)

            save_price_history(
                signal_id,
                0,
                price,
                price
            )


            print()
            print(
                "======================================"
            )

            print(
                "🔥🔥 NEW SURGE SIGNAL"
            )

            print(
                exchange,
                "|",
                market
            )

            print(
                "SCORE:",
                score,
                "/ 100"
            )

            print(
                "PRICE:",
                price
            )

            print(
                "1m:",
                "-" if p1 is None
                else f"{p1:+.2f}%"
            )

            print(
                "5m:",
                "-" if p5 is None
                else f"{p5:+.2f}%"
            )

            print(
                "15m:",
                "-" if p15 is None
                else f"{p15:+.2f}%"
            )

            print(
                "VOL 5m:",
                "-" if r5 is None
                else f"{r5:.1f}x"
            )

            print(
                "VOL 15m:",
                "-" if r15 is None
                else f"{r15:.1f}x"
            )

            print(
                "VOL 60m:",
                "-" if r60 is None
                else f"{r60:.1f}x"
            )

            print(
                "REASON:",
                reason
            )

            print(
                "MA5:",
                "-" if ma5 is None
                else f"{ma5:.8f}"
            )

            print(
                "MA20:",
                "-" if ma20 is None
                else f"{ma20:.8f}"
            )

            print(
                "MA SIGNAL:",
                ma_signal
            )

            print(
                "GOLDEN CROSS:",
                golden_signal
            )

            print(
                "MA5 TREND:",
                ma_direction
            )

            print(
                "DB ID:",
                signal_id
            )

            print(
                "======================================"
            )
            global last_radar_time

if time.time() - last_radar_time >= 30:

    # show_surge_radar()

    last_radar_time = time.time()


# =========================================================
# UPBIT WebSocket
# =========================================================

def upbit_open(ws):

    print(
        "UPBIT WebSocket CONNECTED"
    )


    request = [

        {
            "ticket":
            "surge-v9-upbit"
        },

        {
            "type":
            "trade",

            "codes":
            upbit_markets
        },

        {
            "format":
            "DEFAULT"
        }
    ]


    ws.send(
        json.dumps(
            request
        )
    )


def upbit_message(
    ws,
    message
):

    try:

        if isinstance(
            message,
            bytes
        ):

            message = message.decode(
                "utf-8"
            )


        item = json.loads(
            message
        )


        if item.get(
            "type"
        ) != "trade":

            return


        market = item.get(
            "code"
        )

        price = item.get(
            "trade_price"
        )

        volume = item.get(
            "trade_volume"
        )

        timestamp = item.get(
            "trade_timestamp"
        )


        if None in [
            market,
            price,
            volume,
            timestamp
        ]:

            return


        prices[
            "UPBIT"
        ][market] = price


        minute = timestamp // 60000


        if current_minute[
            "UPBIT"
        ] is None:

            current_minute[
                "UPBIT"
            ] = minute


        if minute != current_minute[
            "UPBIT"
        ]:

            finish_minute(
                "UPBIT"
            )


            current_minute[
                "UPBIT"
            ] = minute


        current_volume[
            "UPBIT"
        ][market] += (
            price * volume
        )


    except Exception as e:

        print(
            "UPBIT ERROR:",
            e
        )


# =========================================================
# BITHUMB WebSocket
# =========================================================

def bithumb_open(ws):

    print(
        "BITHUMB WebSocket CONNECTED"
    )


    request = [

        {
            "ticket":
            "surge-v9-bithumb"
        },

        {
            "type":
            "trade",

            "codes":
            bithumb_markets
        },

        {
            "format":
            "DEFAULT"
        }
    ]


    ws.send(
        json.dumps(
            request
        )
    )


def bithumb_message(
    ws,
    message
):

    try:

        if isinstance(
            message,
            bytes
        ):

            message = message.decode(
                "utf-8"
            )


        item = json.loads(
            message
        )


        if item.get(
            "type"
        ) != "trade":

            return


        market = item.get(
            "code"
        )

        price = item.get(
            "trade_price"
        )

        volume = item.get(
            "trade_volume"
        )

        timestamp = item.get(
            "trade_timestamp"
        )


        if None in [
            market,
            price,
            volume,
            timestamp
        ]:

            return


        prices[
            "BITHUMB"
        ][market] = price


        minute = timestamp // 60000


        if current_minute[
            "BITHUMB"
        ] is None:

            current_minute[
                "BITHUMB"
            ] = minute


        if minute != current_minute[
            "BITHUMB"
        ]:

            finish_minute(
                "BITHUMB"
            )


            current_minute[
                "BITHUMB"
            ] = minute


        current_volume[
            "BITHUMB"
        ][market] += (
            price * volume
        )


    except Exception as e:

        print(
            "BITHUMB ERROR:",
            e
        )


# =========================================================
# WebSocket
# =========================================================

def run_upbit():

    ws = websocket.WebSocketApp(

        "wss://api.upbit.com/"
        "websocket/v1",

        on_open=upbit_open,

        on_message=upbit_message
    )


    ws.run_forever()


def run_bithumb():

    ws = websocket.WebSocketApp(

        "wss://ws-api.bithumb.com/"
        "websocket/v1",

        on_open=bithumb_open,

        on_message=bithumb_message
    )


    ws.run_forever()


# =========================================================
# 시작
# =========================================================

print()

print(
    "======================================"
)

print(
    "      CRYPTO SURGE SCANNER V15"
)

print(
    "======================================"
)


# DB 초기화 / 업그레이드

init_database()


# 마켓

print()
print(
    "Loading UPBIT markets..."
)

upbit_markets = get_markets(
    "UPBIT"
)

print(
    "UPBIT:",
    len(upbit_markets)
)


print()
print(
    "Loading BITHUMB markets..."
)

bithumb_markets = get_markets(
    "BITHUMB"
)

print(
    "BITHUMB:",
    len(bithumb_markets)
)


# 과거 데이터

preload()

# 프로그램 재시작 전에 발생한 미완료 신호 복구
restore_active_signals()
restore_active_prepumps()


# WebSocket

threading.Thread(
    target=run_upbit,
    daemon=True
).start()


threading.Thread(
    target=run_bithumb,
    daemon=True
).start()


# =========================================================
# 메인
# =========================================================

# =========================================================
# 메인
# =========================================================

last_radar_time = 0

while True:

    try:

        time.sleep(
            CHECK_INTERVAL
        )

        analyze()

        track_signals()
        update_prepump_tracking()

        # =========================================
        # LIVE RADAR
        # 30초마다 실행
        # =========================================

        # if time.time() - last_radar_time >= 30:

            # show_surge_radar()

            # last_radar_time = time.time()

    except KeyboardInterrupt:

        print()
        print(
            "SCANNER STOPPED"
        )

        break

    except Exception as e:

        print(
            "MAIN ERROR:",
            e
        )
