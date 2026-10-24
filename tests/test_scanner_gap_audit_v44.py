from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from coin_analysis import scanner_gap_audit_v44 as a

T=86400
M='KRW-ENA'


def tick(ts, identity, volume=1.):
    dt=datetime.fromtimestamp(ts,timezone.utc)
    return dict(market=M,timestamp=int(ts*1000),sequential_id=identity,trade_price=100.,trade_volume=volume,
        trade_date_utc=dt.strftime('%Y-%m-%d'),trade_time_utc=dt.strftime('%H:%M:%S'))


def bar(ts,value=100.):return (ts,100.,100.,100.,100.,value)


class Attribution(unittest.TestCase):
    def test_candle_absence_alone_never_confirms_no_trade(self):
        self.assertEqual(a.classify_gap(T,T+300,original_verified=True,api_absence_confirmed=True),'UNKNOWN')
    def test_independently_bounded_and_reconciled_absence(self):
        proof=dict(start=T,end=T+300,counts={},absence_verified=True)
        self.assertEqual(a.classify_gap(T,T+300,api_absence_confirmed=True,trade_evidence=proof),'NO_TRADE')
        self.assertEqual(a.classify_gap(T-60,T+300,api_absence_confirmed=True,trade_evidence=proof),'UNKNOWN')
    def test_positive_trade_in_missing_api_candle(self):
        self.assertEqual(a.classify_gap(T,T+300,api_absence_confirmed=True,trade_evidence=dict(counts={T:1})),'API_MISSING')
    def test_offered_but_not_saved_and_failed_call_are_collection_failures(self):
        self.assertEqual(a.classify_gap(T,T+300,offered_at=T+100),'COLLECTION_FAILURE')
        self.assertEqual(a.classify_gap(T,T+300,failed_collection=True),'COLLECTION_FAILURE')
        self.assertEqual(a.classify_gap(T,T+300,failed_collection=True,original_verified=True),'UNKNOWN')
    def test_later_candle_requires_original_verified_absence(self):
        self.assertEqual(a.classify_gap(T,T+300,returned_later=True,original_verified=True),'LATE_CANDLE')
        self.assertEqual(a.classify_gap(T,T+300,returned_later=True),'UNKNOWN')
    def test_future_wait_is_not_missing_lookback(self):
        self.assertEqual(a.classify_gap(T,T+59,original_verified=True),'EVALUATION_PENDING')
        self.assertEqual(a.classify_gap(T+1,T+300),'ALIGNMENT_ERROR')


class TradeProof(unittest.TestCase):
    def pages(self):return [[tick(T+130,5),tick(T-10,99)]]
    def source(self):return {T+120:bar(T+120)}
    def test_sparse_trade_times_and_unordered_numeric_ids_can_be_valid(self):
        proof=a.trade_evidence(self.pages(),M,T,T+180,self.source())
        self.assertTrue(proof['absence_verified']);self.assertEqual(proof['counts'].get(T,0),0)
        self.assertEqual(proof['start'],T)
    def test_empty_or_wrong_day_or_future_page_cannot_prove_no_trade(self):
        with self.assertRaises(ValueError):a.trade_evidence([[]],M,T,T+180,{})
        wrong=tick(T+130,1);wrong['trade_date_utc']='1970-01-01'
        with self.assertRaises(ValueError):a.trade_evidence([[wrong]],M,T,T+180,self.source())
        with self.assertRaises(ValueError):a.trade_evidence([[tick(T+180,1)]],M,T,T+180,self.source())
    def test_partial_page_excludes_its_oldest_partial_minute(self):
        proof=a.trade_evidence([[tick(T+130,1),tick(T+70,2)]],M,T,T+180,{T+60:bar(T+60),T+120:bar(T+120)})
        self.assertEqual(proof['start'],T+120)
        self.assertEqual(a.classify_gap(T,T+180,api_absence_confirmed=True,trade_evidence=proof),'UNKNOWN')
    def test_native_value_contradiction_prevents_absence_claim(self):
        proof=a.trade_evidence(self.pages(),M,T,T+180,{T+120:bar(T+120,200.)})
        self.assertFalse(proof['absence_verified'])
    def test_missing_native_neighbors_cannot_anchor_wrong_date(self):
        proof=a.trade_evidence([[tick(T-100,1)]],M,T,T+180,self.source())
        self.assertFalse(proof['absence_verified'])
    def test_bithumb_id_collision_preserves_distinct_and_identical_fill_multiplicity(self):
        rows=[tick(T+130,1,1.),tick(T+130,1,1.),tick(T+130,1,2.),tick(T-10,3)]
        proof=a.trade_evidence([rows],M,T,T+180,{T+120:bar(T+120,400.)},'BITHUMB')
        self.assertTrue(proof['absence_verified']);self.assertEqual(proof['counts'][T+120],3)
        self.assertEqual(proof['reused_id_extra_rows'],2);self.assertEqual(proof['identical_payload_extra_rows'],1)
        with self.assertRaises(ValueError):a.trade_evidence([rows],M,T,T+180,self.source(),'UPBIT')
    def test_ambiguous_bithumb_pagination_stops_absence_proof(self):
        pages=[[tick(T+130,1),tick(T+70,2)],[tick(T+70,2),tick(T-10,3)]]
        with self.assertRaisesRegex(ValueError,'Ambiguous'):a.trade_evidence(pages,M,T,T+180,self.source(),'BITHUMB')
    def test_raw_evidence_hash_is_required(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'raw.json';path.write_text('[]')
            self.assertEqual(a.load_raw(dict(file=str(path),sha256=hashlib.sha256(b'[]').hexdigest())),[])
            with self.assertRaises(ValueError):a.load_raw(dict(file=str(path),sha256='wrong'))
    def test_trade_request_clock_is_exchange_specific_and_date_is_frozen_at_request(self):
        end=a.observer.scanner.collector.parse('2026-10-24T23:55:00+09:00')
        began=a.observer.scanner.collector.parse('2026-10-25T00:15:00+09:00')
        up=dict(started_at=began,params=dict(market=M,count=500,to='14:55:00'))
        bit=dict(started_at=began,params=dict(market=M,count=500,to='23:55:00',daysAgo=1))
        a.validate_trade_request(up,'UPBIT',M,end);a.validate_trade_request(bit,'BITHUMB',M,end)
        with self.assertRaises(ValueError):a.validate_trade_request(up,'BITHUMB',M,end)


class Requirements(unittest.TestCase):
    def test_native_5m_can_match_sparse_minutes_without_making_5_actual_minutes(self):
        minute={T:bar(T),T+120:bar(T+120),T+240:bar(T+240)}
        check=a.native_crosscheck(minute,{T:bar(T,300.)},T,T+300,5)[0]
        self.assertEqual(check['status'],'MATCH');self.assertEqual(check['present_minutes'],3)
        self.assertEqual(a.forward_readiness(T,5,T+300,T+300,minute)['status'],'UNKNOWN')
    def test_30m_complete_60m_pending_and_unverified_future_distinct(self):
        stamps=set(range(T,T+1800,60))
        self.assertEqual(a.forward_readiness(T,30,T+1800,T+1800,stamps)['status'],'COMPLETE')
        self.assertEqual(a.forward_readiness(T,60,T+1800,T+1800,stamps)['status'],'EVALUATION_PENDING')
        later=a.forward_readiness(T,60,T+7200,T+1800,stamps)
        self.assertEqual(later['reason'],'FORWARD_RANGE_NOT_COLLECTED')
    def test_future_in_db_does_not_make_an_unreached_horizon_complete(self):
        r=a.forward_readiness(T,60,T+60,T+3600,set(range(T,T+3600,60)))
        self.assertEqual(r['status'],'EVALUATION_PENDING');self.assertEqual(r['observed'],1)
    def test_audit_reconstructs_denominator_and_never_updates_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'runs').mkdir()
            cfg=dict(version='4.3_OBSERVATION',signal_start=T,policy=a.observer.scanner.POLICY,markets=a.observer.MARKETS)
            (root/'config.json').write_text(json.dumps(cfg));(root/'runs/r.summary.json').write_text(json.dumps(dict(ended_at=T+360)))
            originals={}
            for exchange in a.observer.v42.HOSTS:
                db=a.observer.open_runtime(root,cfg,exchange)
                with db:
                    for market in cfg['markets']:
                        db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',
                            [(market,*bar(t)) for t in range(T-1800,T+300,60) if market in ('KRW-ETH','KRW-BTC') or t!=T-60])
                    db.execute('UPDATE scanner_state SET last_observation=?,verified_until=?',(T+300,T+300))
                a.observer.coverage(db,{m:T-300 for m in cfg['markets']},T+307)
                originals[exchange]=a.observer.ops.full_fingerprints(db);a.observer.ops.close_cleanly(db)
            control=a.observer.ledger(root/'control.db');control.close()
            with patch.object(a,'source_evidence',return_value={}):r=a.audit_episode(root,{})
            self.assertEqual(r['after']['total_windows'],16);self.assertEqual(r['after']['complete_windows'],4)
            self.assertEqual(r['cause_counts_unique']['UNKNOWN'],6)
            for exchange in a.observer.v42.HOSTS:
                with a.observer.ops.readonly(root/(exchange.lower()+'.db')) as db:
                    self.assertEqual(a.observer.ops.full_fingerprints(db),originals[exchange])


if __name__=='__main__':unittest.main()
