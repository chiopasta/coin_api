"""V4.1 candle admission guards; no signal or missing-data policy changes.

Both exchanges' KRW candles expose native KRW trade value, not volume*close.
5/15-minute support here is validation only; V4 still collects 1-minute bars.
"""
import math
from . import research_dataset_collector_v1 as collector

VALUE_ABS_TOLERANCE_KRW = 1.0
VALUE_REL_TOLERANCE = 1e-8
SETTLE_SECONDS = 5


class CandleValidationError(ValueError):
    """Reject bad market data without advancing a durable cursor."""


def closed_cutoff(now, minutes=1):
    if minutes not in (1, 5, 15) or not math.isfinite(now):
        raise ValueError('Expected finite clock and 1/5/15 minute interval')
    return int((now-SETTLE_SECONDS)//(minutes*60))*(minutes*60)


def value_tolerance(value):
    return max(VALUE_ABS_TOLERANCE_KRW, abs(value)*VALUE_REL_TOLERANCE)


def api_to(exchange,utc_cutoff):
    """Exchange request clocks differ; response candle UTC remains canonical."""
    if exchange=='UPBIT':return collector.iso(utc_cutoff)
    if exchange=='BITHUMB':return collector.iso(utc_cutoff,collector.KST)[:19]
    raise ValueError('Unsupported candle exchange')


def candle(raw, market, minutes=1, closed_until=None):
    try:
        if not isinstance(raw,dict):raise ValueError('Expected candle object')
        if minutes not in (1, 5, 15) or not market.startswith('KRW-') or raw.get('market') != market:
            raise ValueError('Wrong market or interval; KRW native value required')
        row = collector.candle(raw)
        ts, _, high, low, _, value = row
        if ts % (minutes*60) or ('unit' in raw and raw['unit'] != minutes):
            raise ValueError('Candle interval/timestamp mismatch')
        if 'candle_date_time_kst' in raw:
            kst = collector.parse(raw['candle_date_time_kst']+'+09:00')
            if kst != ts:
                raise ValueError('Candle UTC/KST mismatch')
        if closed_until is not None and ts+minutes*60 > closed_until:
            raise ValueError('Unclosed candle')
        if 'candle_acc_trade_volume' in raw:
            volume = float(raw['candle_acc_trade_volume'])
            if not math.isfinite(volume) or volume < 0:
                raise ValueError('Invalid native trade volume')
            tolerance = value_tolerance(value)
            if not low*volume-tolerance <= value <= high*volume+tolerance:
                raise ValueError('Native trade value outside OHLC*volume bounds')
        return row
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise CandleValidationError(str(exc)) from exc


def validate_page(raw, cursor, market):
    try:
        if not isinstance(raw,list) or any(not isinstance(row,dict) for row in raw):
            raise ValueError('Expected candle array; error payload is not market data')
        collector.validate_page(raw, cursor, market)
        return [candle(r, market, closed_until=cursor) for r in raw]
    except (TypeError, ValueError) as exc:
        raise CandleValidationError(str(exc)) from exc
