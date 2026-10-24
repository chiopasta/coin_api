"""Separate, read-only V14/V15 paper-trade reconciliation. Never closes trades.

Sampled-price exits are candidates only: no trade timestamp/order-book custody
exists to certify an executable exit. STALE_OPEN and candidates never enter pnl.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import struct

KST = timezone(timedelta(hours=9))


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def integer(value):
    if isinstance(value,bytes):return int.from_bytes(value,'little',signed=True)
    return int(value) if value is not None else None


def number(value):
    if isinstance(value,bytes):
        value=struct.unpack('<d' if len(value)==8 else '<f',value)[0]
    result=float(value) if value is not None else None
    if result is not None and not math.isfinite(result):raise ValueError('Nonfinite legacy value')
    return result


def local_time(value):
    parsed=datetime.fromisoformat(value)
    return parsed.replace(tzinfo=KST) if parsed.tzinfo is None else parsed


def classify(trade,history,as_of):
    """A deterministic view. Original status/exit/pnl fields are not replaced."""
    original=dict(trade)
    result=dict(trade_id=trade['id'],signal_id=trade['signal_id'],original=original,
                effective_status=trade['status'],recovery_status='NOT_APPLICABLE',
                verified_recovery=None,candidate_exit=None)
    if trade['status']!='OPEN':
        result['included_in_original_closed_statistics']=trade['status']=='CLOSED' and trade['pnl_pct'] is not None
        return result
    result['included_in_original_closed_statistics']=False
    started=local_time(trade['created_at'])
    deadline=trade['exit_deadline_minute']
    if as_of < started:
        result.update(effective_status='CLOCK_ANOMALY',recovery_status='INVALID_ASOF')
        return result
    if as_of < started+timedelta(minutes=deadline):
        result['recovery_status']='NOT_DUE'
        return result
    result.update(effective_status='STALE_OPEN',recovery_status='INCOMPLETE_OBSERVATIONS')
    entry=trade['entry_minute'];price=trade['entry_price']
    if not price or price<=0 or entry is None or not 0<entry<deadline:
        result['recovery_status']='INVALID_ENTRY';return result
    for minute in range(entry,deadline+1):
        row=history.get(minute)
        if row is None:return result
        observed=local_time(row['observed_at']);elapsed=(observed-started).total_seconds()
        if observed>as_of or not minute*60 <= elapsed < (minute+1)*60:
            result['recovery_status']='INVALID_OBSERVATION_TIME';return result
        if minute==entry:
            if not math.isclose(row['price'],price,rel_tol=1e-10,abs_tol=1e-8):
                result['recovery_status']='ENTRY_PRICE_MISMATCH';return result
            continue
        change=100*(row['price']/price-1)
        reason='TP' if change>=trade['tp_pct'] else 'SL' if change<=-trade['sl_pct'] else 'TIME' if minute==deadline else None
        if reason:
            result.update(recovery_status='CANDIDATE_ONLY_NOT_VERIFIED',candidate_exit=dict(
                minute=minute,observed_at=row['observed_at'],observed_price=row['price'],reason=reason,
                note='Sampled price/time only; actual last-trade time and independent exit custody unavailable'))
            return result
    return result


def reconcile(source,as_of,output):
    source=Path(source).resolve();output=Path(output).resolve()
    if output==source or output.suffix!='.json':raise ValueError('Separate .json output required')
    if output.exists():raise FileExistsError('Reconciliation evidence already exists')
    if as_of.tzinfo is None:raise ValueError('Explicit as-of timezone required')
    before=digest(source)
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        integrity=db.execute('PRAGMA quick_check').fetchone()[0]
        if integrity!='ok':raise ValueError('Legacy DB integrity failed')
        trades=[]
        for raw in db.execute('SELECT p.*,s.created_at,s.exchange,s.market FROM pullback_paper_trades p JOIN signals s ON s.id=p.signal_id ORDER BY p.id'):
            row=dict(raw)
            for key in ('id','signal_id','entry_minute','exit_minute','exit_deadline_minute'):row[key]=integer(row[key])
            for key in ('entry_price','entry_return_from_signal','tp_pct','sl_pct','exit_price','pnl_pct'):row[key]=number(row[key])
            trades.append(row)
        histories={}
        for row in db.execute('SELECT signal_id,minute,price,observed_at FROM signal_price_history'):
            sid,minute=integer(row['signal_id']),integer(row['minute'])
            history=histories.setdefault(sid,{})
            if minute in history:raise ValueError('Duplicate decoded signal/minute')
            history[minute]=dict(price=number(row['price']),observed_at=row['observed_at'])
    finally:db.close()
    records=[classify(t,histories.get(t['signal_id'],{}),as_of) for t in trades]
    closed=[r['original']['pnl_pct'] for r in records if r['included_in_original_closed_statistics']]
    after=digest(source)
    if before!=after:raise RuntimeError('Source changed during reconciliation; do not publish result')
    report=dict(source=str(source),source_sha256=before,source_sha256_after=after,source_preserved=True,
                as_of=as_of.isoformat(),legacy_timezone_assumption='KST for naive source clock; not authenticated',
                counts=dict(Counter(r['effective_status'] for r in records)),
                recovery_counts=dict(Counter(r['recovery_status'] for r in records)),
                original_closed_statistics=dict(n=len(closed),mean_pct=sum(closed)/len(closed) if closed else None),
                verified_recoveries=0,records=records,
                limitations='No original status changes, no new pnl, no certified exit without independent trade-time evidence.')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--as-of',required=True,help='ISO timestamp with timezone, explicit audit cutoff')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=reconcile(args.source,datetime.fromisoformat(args.as_of.replace('Z','+00:00')),args.output)
    print(json.dumps(dict(counts=report['counts'],recovery_counts=report['recovery_counts'],source_preserved=report['source_preserved'])))


if __name__=='__main__':main()
