"""Read-only scope descriptions and capacity estimates; no scanner selection.

Listing receipts come from explicit diagnostics or the observer's existing
market-list replies. Reading a dashboard never performs network discovery.
"""
import json
import math
from pathlib import Path
import re
import time

from .paths import DATA_DIR

EXCHANGES=('UPBIT','BITHUMB')
CACHE=DATA_DIR/'scanner_dashboard_v50'/'market_scope.json'
MAX_AGE_SECONDS=3600


def krw_markets(rows):
    if not isinstance(rows,list):raise ValueError('Market list must be an array')
    result=sorted({r['market'] for r in rows if isinstance(r,dict) and
                   isinstance(r.get('market'),str) and re.fullmatch(r'KRW-[A-Z0-9]+',r['market'])})
    if not result:raise ValueError('No listed KRW markets')
    return result


def receipt(rows,at):
    return dict(at=at,markets=krw_markets(rows))


def inventory(receipts):
    result={}
    for name in EXCHANGES:
        item=receipts[name];markets=krw_markets([dict(market=m) for m in item['markets']])
        at=item['at']
        if not isinstance(at,(int,float)) or not math.isfinite(at):raise ValueError('Invalid receipt time')
        result[name]=dict(at=at,markets=markets,count=len(markets))
    return dict(version=1,exchanges=result,basis='EXCHANGE_LISTED_KRW; ORDER_AVAILABILITY_NOT_EXPOSED')


def read_inventory(root=None):
    candidates=[Path(root)/'market_scope.json'] if root else []
    candidates.append(CACHE)
    for path in candidates:
        try:
            if path.stat().st_size>256*1024:continue
            value=json.loads(path.read_text(encoding='utf-8'))
            if value.get('version')!=1:continue
            return inventory(value['exchanges'])
        except (OSError,ValueError,KeyError,TypeError):continue
    return None


def describe(state,configured,root=None,now=None):
    now=time.time() if now is None else now
    active=state.get('status')=='RUNNING' and state.get('phase')=='OBSERVING'
    saved=read_inventory(root);total=dict(status='UNKNOWN',unique=None,venue_pairs=None,by_exchange={},at=None)
    if saved:
        exchanges=saved['exchanges'];oldest=min(x['at'] for x in exchanges.values())
        total=dict(status='FRESH' if 0<=now-oldest<=MAX_AGE_SECONDS else 'STALE',
                   unique=len(set().union(*(set(x['markets']) for x in exchanges.values()))),
                   venue_pairs=sum(x['count'] for x in exchanges.values()),
                   by_exchange={name:x['count'] for name,x in exchanges.items()},at=oldest,
                   basis=saved['basis'])
    return dict(mode='FIXED_OBSERVATION_COHORT',configured_unique=len(set(configured)),
        configured_venue_pairs=len(set(configured))*len(EXCHANGES),
        scan=dict(unique=state.get('markets') if active else 0,venue_pairs=state.get('venue_pairs') if active else 0,
                  signal_pairs=state.get('signal_pairs') if active else 0),
        total=total,
        focus=dict(unique=state.get('focus_markets') if active else 0,
                   venue_pairs=state.get('focus_pairs') if active else 0,
                   basis='SAVED_PENDING_FOLLOWUP_HORIZONS; NOT_A_RANKED_SUBSET'))


def capacity(venue_pairs,max_requests=16000):
    """Dense-market planning case, not a guarantee of runtime or completeness."""
    if not isinstance(venue_pairs,int) or venue_pairs<=0:raise ValueError('Positive pair count required')
    warmup=2*venue_pairs  # Existing six-hour warmup, 200 candles/page.
    checks=2;steady=venue_pairs*1440
    available=max(0,max_requests-checks-warmup)
    return dict(venue_pairs=venue_pairs,http_cap=max_requests,market_checks=checks,
        dense_warmup_requests=warmup,one_minute_24h_requests=checks+warmup+steady,
        minimum_round_seconds=max(0,venue_pairs-1)*.25,
        full_rounds_after_warmup=available//venue_pairs,
        ideal_24h_interval_seconds=86400*venue_pairs/available if available else None,
        focus_pairs_one_minute_after_full_warmup=available//1440,
        sustainable_pair_ceiling_at_one_minute=(max_requests-checks)//1442,
        assumptions='Dense 1m candles; warmup added conservatively; no retries, I/O, CPU or safety reserves; actual throughput may be lower')
