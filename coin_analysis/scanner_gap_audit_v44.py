"""Read-only V4.3 gap attribution. No collection, candle synthesis or signals.

NO_TRADE needs an independently bounded trade-history page chain reconciled to
positive neighboring candles. Candle absence alone is only an observable fact.
All later source evidence is retrospective diagnosis, never a frozen feature.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import time

from . import forward_scanner_v43 as observer

CAUSES=('NO_TRADE','API_MISSING','COLLECTION_FAILURE','LATE_CANDLE',
        'ALIGNMENT_ERROR','EVALUATION_PENDING','UNKNOWN')


def load_raw(record):
    data=Path(record['file']).read_bytes()
    if hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Raw evidence hash mismatch')
    return json.loads(data)


def validate_trade_request(record, exchange, market, end):
    zone=observer.scanner.collector.UTC if exchange=='UPBIT' else observer.scanner.collector.KST
    target=datetime.fromtimestamp(end,zone)
    day_offset=(datetime.fromtimestamp(record['started_at'],zone).date()-target.date()).days
    params=record['params'];day_key='days_ago' if exchange=='UPBIT' else 'daysAgo'
    if (params.get('market')!=market or params.get('count')!=500 or
            params.get('to')!=target.strftime('%H:%M:%S') or params.get(day_key,0)!=day_offset):
        raise ValueError('Trade request clock/day/scope mismatch')


def classify_gap(ts, asof, *, alignment_error=False, offered_at=None,
                 original_verified=False, failed_collection=False,
                 returned_later=False, api_absence_confirmed=False,
                 trade_evidence=None):
    if alignment_error or ts%60:return 'ALIGNMENT_ERROR'
    if ts+60>asof:return 'EVALUATION_PENDING'
    if offered_at is not None and offered_at<=asof:return 'COLLECTION_FAILURE'
    if returned_later:
        return 'LATE_CANDLE' if original_verified else 'COLLECTION_FAILURE' if failed_collection else 'UNKNOWN'
    tr=trade_evidence or {}
    if api_absence_confirmed and tr.get('counts',{}).get(ts,0)>0:return 'API_MISSING'
    if (api_absence_confirmed and tr.get('absence_verified') and
            tr['start']<=ts and ts+60<=tr['end'] and tr['counts'].get(ts,0)==0):return 'NO_TRADE'
    if failed_collection and not original_verified:return 'COLLECTION_FAILURE'
    return 'UNKNOWN'


def trade_evidence(pages, market, start, end, source, exchange='UPBIT'):
    """Validate full timestamps/opaque cursor order, then corroborate tick sums.

    Sequential IDs are NOT an arithmetic sequence or clock. The observed
    Bithumb feed even reuses IDs within a page; retain row multiplicity and
    reconcile native value. That ambiguity prohibits multi-page absence proof.
    A truncated page only proves absence after its oldest fully covered minute.
    An empty page, wrong day, missing neighbors or contradictory tick totals
    cannot establish NO_TRADE.
    """
    ticks={};single_page_rows=[];previous_oldest=None;all_ids=[];payloads=[]
    for page in pages:
        if not isinstance(page,list) or not page or len(page)>500:raise ValueError('Empty/invalid trade page is not coverage proof')
        stamps=[];ids=set()
        for raw in page:
            if raw.get('market')!=market:raise ValueError('Wrong trade market')
            stamp=int(raw['timestamp']);identity=str(raw['sequential_id'])
            price=float(raw['trade_price']);volume=float(raw['trade_volume'])
            named=int(datetime.fromisoformat(raw['trade_date_utc']+'T'+raw['trade_time_utc']+'+00:00').timestamp())
            if stamp//1000!=named or stamp>=end*1000 or stamp<=0:raise ValueError('Trade UTC/cutoff mismatch')
            if not all(math.isfinite(x) and x>0 for x in (price,volume)):raise ValueError('Invalid trade price/volume')
            if identity in ids and exchange!='BITHUMB':raise ValueError('Duplicate trade ID within page')
            ids.add(identity);stamps.append(stamp)
            value=(stamp,price,volume)
            if identity in ticks and ticks[identity]!=value and exchange!='BITHUMB':raise ValueError('Conflicting duplicate trade')
            ticks[identity]=value
            single_page_rows.append(value);all_ids.append(identity);payloads.append(json.dumps(raw,sort_keys=True))
        if stamps!=sorted(stamps,reverse=True):raise ValueError('Unordered trade time')
        if previous_oldest is not None and max(stamps)>previous_oldest:raise ValueError('Trade page chain does not move back')
        previous_oldest=min(stamps)
    collisions=len(all_ids)-len(set(all_ids))
    if exchange=='BITHUMB' and len(pages)>1 and collisions:raise ValueError('Ambiguous Bithumb cursor collisions across pages')
    rows=single_page_rows if exchange=='BITHUMB' and len(pages)==1 else list(ticks.values())
    if not rows:raise ValueError('No independent trade evidence')
    low=max(start,(min(t[0] for t in rows)//60000+1)*60)
    groups=defaultdict(list)
    for stamp,price,volume in rows:
        minute=stamp//60000*60
        if low<=minute<end:groups[minute].append((price,volume))
    mismatches=[];positive=0;comparisons=[]
    for ts,bar in source.items():
        if not low<=ts<end:continue
        trades=groups.get(ts,[])
        value=math.fsum(p*q for p,q in trades)
        matches=bool(trades) and abs(value-bar[5])<=observer.candles.value_tolerance(bar[5])
        matches=matches and math.isclose(max(p for p,_ in trades),bar[2],rel_tol=1e-12,abs_tol=1e-8)
        matches=matches and math.isclose(min(p for p,_ in trades),bar[3],rel_tol=1e-12,abs_tol=1e-8)
        comparisons.append(dict(ts=ts,trades=len(trades),trade_value=value,candle_value=bar[5],matches=bool(matches)))
        if matches:positive+=1
        else:mismatches.append(ts)
    return dict(start=low,end=end,oldest_trade_ms=min(t[0] for t in rows),
        newest_trade_ms=max(t[0] for t in rows),trade_records=len(rows),distinct_ids=len(set(all_ids)),
        reused_id_extra_rows=collisions,identical_payload_extra_rows=len(payloads)-len(set(payloads)),
        unique_trades_not_proven=exchange=='BITHUMB' and bool(collisions),
        absence_verified=bool(positive) and not mismatches,positive_neighbor_checks=positive,
        contradictions=mismatches,counts={ts:len(rows) for ts,rows in groups.items()},comparisons=comparisons)


def forward_readiness(t, minutes, now, verified_until, stamps):
    end=t+minutes*60;wanted=set(range(t,end,60))
    present={ts for ts in stamps if ts+60<=now}&wanted
    if now<end:status='EVALUATION_PENDING';reason='HORIZON_NOT_REACHED'
    elif verified_until<end:status='UNKNOWN';reason='FORWARD_RANGE_NOT_COLLECTED'
    elif present!=wanted:status='UNKNOWN';reason='INCOMPLETE_FUTURE'
    else:status='COMPLETE';reason='FULL_FUTURE'
    return dict(minutes=minutes,start=t,end=end,asof=now,status=status,reason=reason,
        observed=len(present),expected=minutes,ready=status=='COMPLETE')


def native_crosscheck(minute, native, start, end, unit):
    result=[];width=unit*60
    for ts in range((start+width-1)//width*width,end//width*width,width):
        pieces=[minute[s] for s in range(ts,ts+width,60) if s in minute];bar=native.get(ts)
        if not pieces:
            result.append(dict(ts=ts,unit=unit,present_minutes=0,status='CONSISTENT_SOURCE_ABSENCE' if bar is None else 'CONFLICT'))
            continue
        if bar is None:
            result.append(dict(ts=ts,unit=unit,present_minutes=len(pieces),status='NATIVE_MISSING'));continue
        derived=(pieces[0][1],max(p[2] for p in pieces),min(p[3] for p in pieces),pieces[-1][4],math.fsum(p[5] for p in pieces))
        prices=all(math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-8) for a,b in zip(derived[:4],bar[1:5]))
        error=abs(derived[4]-bar[5]);tolerance=observer.candles.value_tolerance(bar[5])
        result.append(dict(ts=ts,unit=unit,present_minutes=len(pieces),status='MATCH' if prices and error<=tolerance else 'CONFLICT',
            absolute_value_error=error,value_tolerance=tolerance))
    return result


def source_evidence(probe):
    result={};lower=probe['limits']['window_start'];upper=probe['limits']['window_end']
    for exchange in probe['limits']['exchanges']:
        for market in probe['limits']['markets']:
            records=[r for r in probe['records'] if r['exchange']==exchange and r['params']['market']==market and 'status' in r]
            source={};validation_errors=[]
            for unit in (1,5,15):
                relevant=[r for r in records if r['endpoint']==f'/v1/candles/minutes/{unit}']
                if len(relevant)!=1:continue
                rec=relevant[0];cutoff=upper//(unit*60)*(unit*60)
                try:
                    if rec['params']['to']!=observer.candles.api_to(exchange,cutoff):raise ValueError('Wrong request clock')
                    raw=load_raw(rec)
                    rows=[observer.candles.candle(r,market,unit,cutoff) for r in raw]
                    times=[r[0] for r in rows]
                    if not rows or len(rows)>200 or times!=sorted(set(times),reverse=True):raise ValueError('Bad candle page order/duplicates')
                    source[unit]={r[0]:r for r in rows}
                except (KeyError,ValueError,TypeError,OSError) as exc:validation_errors.append(dict(unit=unit,error=str(exc)))
            minute=source.get(1,{})
            tr=None
            try:
                pages=[]
                for r in records:
                    if r['endpoint']!='/v1/trades/ticks':continue
                    validate_trade_request(r,exchange,market,upper)
                    if pages and str(r['params'].get('cursor'))!=str(pages[-1][-1]['sequential_id']):raise ValueError('Unlinked trade cursor')
                    pages.append(load_raw(r))
                tr=trade_evidence(pages,market,lower,upper,minute,exchange)
            except (KeyError,ValueError,TypeError,OSError) as exc:validation_errors.append(dict(trades_error=str(exc)))
            native=[row for unit in (5,15) for row in native_crosscheck(minute,source.get(unit,{}),lower,upper,unit) if unit in source]
            # The requested exclusive cutoff is the upper coverage bound. The
            # newest actual trade/candle need not lie at that bound.
            result[(exchange,market)]=dict(minute=minute,trades=tr,native=native,errors=validation_errors,
                candle_range_verified=bool(minute) and min(minute)<=lower,lower=lower,upper=upper)
    return result


def audit_episode(root, probe):
    audit_at=time.time()
    root=Path(root);cfg=json.loads((root/'config.json').read_text(encoding='utf8'));observer.validate_config(cfg)
    summaries=[json.loads(p.read_text()) for p in (root/'runs').glob('*.summary.json')]
    stop=max(s['ended_at'] for s in summaries)
    evidence=source_evidence(probe);result={};all_windows=[];stored_windows=[];gaps={}
    for exchange in observer.v42.HOSTS:
        with observer.ops.readonly(root/(exchange.lower()+'.db')) as db:
            states={r['market']:dict(r) for r in db.execute('SELECT * FROM scanner_state')}
            by_market={m:{r[0]:tuple(r) for r in db.execute('SELECT ts,open,high,low,close,trade_value FROM minute_candles WHERE market=? ORDER BY ts',(m,))} for m in cfg['markets']}
            receipts={(r['market'],r['ts']):r['first_received_at'] for r in db.execute('SELECT * FROM candle_receipts')}
            windows=[];evaluation_errors=[];forward=[];forward_now=[]
            for market,state in states.items():
                if market=='KRW-BTC':continue
                for t in range(cfg['signal_start'],state['last_observation']+1,300):
                    wanted=set(range(t-1800,t,60));present=wanted&by_market[market].keys();missing=sorted(wanted-present)
                    old=db.execute('SELECT * FROM coverage_windows WHERE market=? AND t=? AND minutes=30',(market,t)).fetchone()
                    if old is not None:stored_windows.append(dict(complete=old['status']=='COMPLETE'))
                    if old is None or old['observed']!=len(present) or json.loads(old['missing_json'])!=missing:
                        evaluation_errors.append(dict(market=market,t=t,issue='STORED_COVERAGE_MISMATCH_OR_ABSENT'))
                    asof=old['recorded_at'] if old else None;causes=Counter();details=[]
                    source=evidence.get((exchange,market),{})
                    for ts in missing:
                        verified=db.execute('SELECT 1 FROM collection_pages WHERE market=? AND start<=? AND end>? LIMIT 1',(market,ts,ts)).fetchone() is not None
                        source_span=source.get('candle_range_verified') and source['lower']<=ts and ts<source['upper']
                        cause=classify_gap(ts,asof if asof is not None else t,
                            original_verified=verified,offered_at=receipts.get((market,ts)),
                            api_absence_confirmed=bool(source_span and ts not in source.get('minute',{})),
                            returned_later=ts in source.get('minute',{}),trade_evidence=source.get('trades'))
                        detail=dict(exchange=exchange,market=market,ts=ts,cause=cause,processing_asof=asof,
                            original_page_verified=verified,first_response_receipt=receipts.get((market,ts)),
                            requery_source_absent=bool(source_span and ts not in source.get('minute',{})))
                        details.append(detail);causes[cause]+=1;gaps[(exchange,market,ts)]=detail
                    width=None
                    series=observer.scanner.v3.v2.old.Series(by_market[market].values())
                    high,low=series.high_low(t-1800,t)
                    if high is not None:width=100*(high/low-1)
                    if (width is not None)!=(len(present)==30):evaluation_errors.append(dict(market=market,t=t,issue='CORE_RANGE_COMPLETENESS_MISMATCH'))
                    win=dict(exchange=exchange,market=market,t=t,window_kind='LOOKBACK_30M',expected=30,observed=len(present),
                        complete=len(present)==30,missing=details,cause_counts=dict(causes),core_range_pct=width,
                        processing_lag_seconds=asof-t if asof is not None else None)
                    windows.append(win);all_windows.append(win)
                    forward.append(dict(market=market,t=t,diagnostic_grid_only=True,not_a_signal=True,
                        horizons=[forward_readiness(t,h,int(stop),state['verified_until'],by_market[market]) for h in (30,60)]))
                    forward_now.append(dict(market=market,t=t,diagnostic_grid_only=True,not_a_signal=True,
                        horizons=[forward_readiness(t,h,int(audit_at),state['verified_until'],by_market[market]) for h in (30,60)]))
            unique=[r for key,r in gaps.items() if key[0]==exchange]
            result[exchange]=dict(windows=windows,unique_gap_minutes=len(unique),
                unique_cause_counts={cause:sum(r['cause']==cause for r in unique) for cause in CAUSES},
                slot_cause_counts={cause:sum(w['cause_counts'].get(cause,0) for w in windows) for cause in CAUSES},
                affected_windows={cause:sum(cause in w['cause_counts'] for w in windows) for cause in CAUSES},
                complete_windows=sum(w['complete'] for w in windows),total_windows=len(windows),
                observed_slots=sum(w['observed'] for w in windows),expected_slots=30*len(windows),
                evaluation_errors=evaluation_errors,forward_readiness_at_stop=forward,
                forward_readiness_at_audit=forward_now,
                actual_signals=db.execute('SELECT COUNT(*) FROM signals').fetchone()[0],
                actual_signal_horizons=[dict(r) for r in db.execute('SELECT minutes,status,COUNT(*) AS n FROM live_horizons GROUP BY minutes,status')],
                quick_check=db.execute('PRAGMA quick_check').fetchone()[0],
                misaligned_candles=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts%60<>0').fetchone()[0],
                unclosed_at_stop=db.execute('SELECT COUNT(*) FROM minute_candles WHERE ts+60>?',(int(stop),)).fetchone()[0],
                native_snapshot_candle_count=len(by_market['KRW-BTC']),
                min_watermark=min(s['verified_until'] for s in states.values()))
    with observer.ops.readonly(root/'control.db') as control:
        attempts=control.execute('SELECT COUNT(*) FROM http_attempts').fetchone()[0]
        statuses=dict(control.execute('SELECT status,COUNT(*) FROM http_attempts GROUP BY status'))
        latency=[r[0] for r in control.execute('SELECT ended_at-started_at FROM http_attempts WHERE ended_at IS NOT NULL')]
    sanitized=[]
    for (exchange,market),e in evidence.items():
        sanitized.append(dict(exchange=exchange,market=market,trades=e['trades'],native=e['native'],validation_errors=e['errors'],
            requery_candle_range_verified=e['candle_range_verified'],returned_missing_original=[r['ts'] for r in gaps.values() if r['exchange']==exchange and r['market']==market and r['ts'] in e['minute']]))
    return dict(at=audit_at,classification_basis='Retrospective only; no signals/features rewritten',episode=str(root),
        observation_stop=stop,per_exchange=result,unique_missing_minutes=list(gaps.values()),source_evidence=sanitized,
        old_http=dict(attempts=attempts,statuses=statuses,success_pct=100*statuses.get('HTTP_END',0)/attempts if attempts else None,
            latency_mean_seconds=sum(latency)/len(latency) if latency else None,latency_max_seconds=max(latency,default=None)),
        before=dict(complete_windows=sum(w['complete'] for w in stored_windows),total_windows=len(stored_windows)),
        after=dict(complete_windows=sum(w['complete'] for w in all_windows),total_windows=len(all_windows),
            observed_slots=sum(w['observed'] for w in all_windows),expected_slots=30*len(all_windows)),
        cause_counts_unique={c:sum(r['cause']==c for r in gaps.values()) for c in CAUSES},
        cause_counts_slots={c:sum(w['cause_counts'].get(c,0) for w in all_windows) for c in CAUSES},
        status='PARTIAL',no_fill=True,no_live_run=True,no_original_db_write=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode',type=Path,required=True)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Never overwrite existing evidence')
    payload=audit_episode(args.episode,json.loads(args.probe.read_text(encoding='utf8')))
    # No user-controlled path may replace an original input/output database.
    if args.output.suffix.lower()!='.json' or args.output.resolve().is_relative_to(args.episode.resolve()):raise ValueError('Use a separate JSON evidence path')
    with args.output.open('x',encoding='utf8') as stream:
        json.dump(payload,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(dict(before=payload['before'],after=payload['after'],causes=payload['cause_counts_unique'])))


if __name__=='__main__':main()
