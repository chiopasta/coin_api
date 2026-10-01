import contextlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from coin_analysis import forward_scanner_v4 as s

START=86400
MARKETS=['KRW-BTC','KRW-ETH','KRW-XRP','KRW-ADA','KRW-SOL']

def history(end):
    rows=[]
    for t in range(START-s.WARMUP,end,60):
        high=105 if START-300<=t<START+300 else 100
        # Target hit after signal; past history remains unchanged.
        if START+300<=t<START+600:high=112
        rows.append((t,100.,float(high),100.,100.,1000.))
    return rows

class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'scanner.db'
        self.db=s.connect(self.path);s.initialize(self.db,MARKETS,START)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def ingest(self,rows,end):
        with self.db:
            for m in MARKETS:
                self.db.executemany('INSERT OR IGNORE INTO minute_candles VALUES(?,?,?,?,?,?,?)',[(m,)+r for r in rows])
            self.db.execute('UPDATE scanner_state SET verified_until=?',(end,))
    def test_signal_pending_restart_and_final_outcome_immutable(self):
        self.ingest(history(START),START);s.process_observations(self.db,START,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],4)
        self.assertEqual(s.statistics(self.db,'ALL')['L1']['statuses'],{'PENDING':4})
        before=list(self.db.execute('SELECT values_json FROM signal_features'))
        self.db.close();self.db=s.connect(self.path)
        self.ingest(history(START+3600),START+3600)
        s.process_observations(self.db,START+3600,lambda _:None)
        s.evaluate_outcomes(self.db,START+3600,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],4)
        self.assertEqual(s.statistics(self.db,'ALL')['L1']['success'],4)
        self.assertEqual(s.statistics(self.db,'ALL')['L2']['success'],4)
        self.assertEqual([tuple(r) for r in before],[tuple(r) for r in self.db.execute('SELECT values_json FROM signal_features')])
        final=[tuple(r) for r in self.db.execute('SELECT * FROM signal_outcomes')]
        s.evaluate_outcomes(self.db,START+7200,lambda _:None)
        self.assertEqual(final,[tuple(r) for r in self.db.execute('SELECT * FROM signal_outcomes')])
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("UPDATE signal_outcomes SET status='FAILURE'")
        self.db.rollback()
    def test_missing_future_is_unknown_and_recoverable(self):
        data=history(START+3600);data=[r for r in data if r[0]!=START+600]
        self.ingest(data,START+3600);s.process_observations(self.db,START,lambda _:None)
        s.evaluate_outcomes(self.db,START+3600+s.GRACE,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['L1']['statuses'],{'UNKNOWN':4})
        self.assertEqual(s.statistics(self.db,'ALL')['L2']['statuses'],{'UNKNOWN':4})
        self.ingest(history(START+3600),START+3600)
        s.evaluate_outcomes(self.db,START+3600+s.GRACE,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['L1']['success'],4)
    def test_future_mutation_deletion_cannot_change_features_or_cluster_start(self):
        outcomes=[]
        for index,rows in enumerate([history(START),history(START+3600),[(r if r[0]<START else (r[0],1.,10000.,1.,9999.,1e12)) for r in history(START+3600)]]):
            with contextlib.closing(s.connect(Path(self.tmp.name)/f'leak{index}.db')) as db:
                s.initialize(db,MARKETS,START)
                with db:
                    for m in MARKETS:db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',[(m,)+r for r in rows])
                    db.execute('UPDATE scanner_state SET verified_until=?',(START+3600,))
                s.process_observations(db,START,lambda _:None)
                outcomes.append(([tuple(r) for r in db.execute('SELECT signal_id,signal_time,range_30m,cluster_id FROM signals')],
                                 [tuple(r) for r in db.execute('SELECT * FROM signal_features')]))
        self.assertEqual(outcomes[0],outcomes[1]);self.assertEqual(outcomes[0],outcomes[2])
    def test_reset_allows_new_cluster_and_null_does_not_reset(self):
        data=history(START+7200)
        data=[(t,o,105. if START+6900<=t else h,l,c,v) for t,o,h,l,c,v in data]
        self.ingest(data,START+7200);s.process_observations(self.db,START+7200,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],8)
    def test_initial_high_range_is_left_censored_not_new_signal(self):
        data=[(t,100.,105.,100.,100.,1000.) for t in range(START-s.WARMUP,START,60)]
        self.ingest(data,START);s.process_observations(self.db,START,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],0)
    def test_bounded_mock_transport_smoke_and_page_resume(self):
        data=history(START+3600)
        requests=[]
        def transport(path,params):
            self.assertEqual(path,'/v1/candles/minutes/1');self.assertEqual(params['count'],200)
            cursor=s.collector.parse(params['to']);requests.append((params['market'],cursor))
            raw=[dict(market=params['market'],candle_date_time_utc=s.collector.iso(t)[:19],opening_price=o,high_price=h,low_price=l,trade_price=c,candle_acc_trade_price=v) for t,o,h,l,c,v in reversed(data) if t<cursor][:200]
            return raw,{}
        client=s.collector.Client(transport=transport,sleep=lambda _:None,max_requests=1)
        with self.assertRaises(s.collector.CollectionBlocked):s.fetch_market(self.db,client,'KRW-BTC',START+3600)
        cursor=self.db.execute('SELECT cursor FROM collection_jobs').fetchone()[0]
        self.db.close();self.db=s.connect(self.path)
        client=s.collector.Client(transport=transport,sleep=lambda _:None,max_requests=20)
        s.cycle(self.db,client,START+3605,lambda _:None)
        self.assertEqual([r for r in requests[1:] if r[0]=='KRW-BTC'][0],('KRW-BTC',cursor))
        count=self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0]
        s.cycle(self.db,client,START+3605,lambda _:None)
        self.assertEqual(count,self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0])
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],4)
        self.assertEqual(s.statistics(self.db,'ALL')['L2']['success'],4)
    def test_existing_research_db_rejected(self):
        path=Path(self.tmp.name)/'other.db'
        with contextlib.closing(sqlite3.connect(path)) as db:db.execute('CREATE TABLE minute_candles(x)')
        before=path.read_bytes()
        with self.assertRaises(ValueError):s.connect(path)
        self.assertEqual(before,path.read_bytes())
    def test_no_early_success_and_complete_failure(self):
        data=history(START+3600)
        data=[(t,o,100. if t>=START else h,l,c,v) for t,o,h,l,c,v in data]
        self.ingest(data,START+3600);s.process_observations(self.db,START,lambda _:None)
        s.evaluate_outcomes(self.db,START+60,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['L1']['statuses'],{'PENDING':4})
        s.evaluate_outcomes(self.db,START+3600,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['L1']['statuses'],{'FAILURE':4})
        self.assertEqual(s.statistics(self.db,'ALL')['L2']['statuses'],{'FAILURE':4})
    def test_null_range_does_not_rearm_active_cluster(self):
        data=[(t,100.,105. if t>=START-300 else 100.,100.,100.,1000.) for t in range(START-s.WARMUP,START+3600,60) if t!=START+60]
        self.ingest(data,START+3600);s.process_observations(self.db,START+3600,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],4)
    def test_ip_block_stops_cycle_instead_of_repeating(self):
        class Blocked:
            def get(self,*args,**kwargs):raise s.collector.CollectionBlocked('IP blocked')
        with self.assertRaises(s.collector.CollectionBlocked):s.cycle(self.db,Blocked(),START+3605,lambda _:None)
        self.assertTrue(s.statistics(self.db,'ALL')['collection_errors'])

if __name__=='__main__':unittest.main()
