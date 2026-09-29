import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from coin_analysis import research_dataset_collector_v1 as c


def raw(ts, market='KRW-BTC', value=10):
    return dict(market=market,candle_date_time_utc=c.iso(ts)[:19],opening_price=100,
                high_price=101,low_price=99,trade_price=100,candle_acc_trade_price=value)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        c.init_db(self.db)
        self.addCleanup(self.db.close)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__,None,None,None)

    def setup_range(self, start=0, end=18000):
        c.freeze(self.db,c.make_manifest(start,end,[],[],True))

    def client(self, transport):
        return c.Client(transport=transport,sleep=lambda _:None)

    def full_transport(self, path, params):
        cursor=c.parse(params['to'])
        self.assertEqual(params['count'],200)
        return [raw(t,params['market']) for t in range(cursor-60,cursor-12001,-60)], {}

    def test_cursor_resume_and_complete_skip(self):
        self.setup_range()
        client=self.client(self.full_transport)
        c.collect(self.db,client,page_budget=1)
        state=self.db.execute('SELECT * FROM collection_state').fetchone()
        self.assertEqual(state['next_cursor'],6000)
        self.assertEqual(state['status'],'RUNNING')
        self.assertEqual(state['rows_saved'],200)
        c.collect(self.db,client)
        self.assertEqual(client.requests,2)
        self.assertEqual(self.db.execute('SELECT status,rows_saved FROM collection_state').fetchone()[:],('COMPLETE',300))
        c.collect(self.db,client)
        self.assertEqual(client.requests,2)

    def test_duplicate_insert(self):
        self.setup_range(0,120)
        with self.db:
            self.db.execute('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',('KRW-BTC',0,100,101,99,100,10))
        c.collect(self.db,self.client(self.full_transport))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],2)
        self.assertEqual(self.db.execute('SELECT rows_saved FROM collection_state').fetchone()[0],1)

    def test_atomic_rollback_on_cursor_update_failure(self):
        self.setup_range(0,120)
        self.db.execute("CREATE TRIGGER reject_cursor BEFORE UPDATE OF next_cursor ON collection_state BEGIN SELECT RAISE(ABORT,'simulated crash'); END")
        c.collect(self.db,self.client(self.full_transport))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM collection_pages').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT next_cursor,status FROM collection_state').fetchone()[:],(120,'ERROR'))
        self.db.execute('DROP TRIGGER reject_cursor')
        c.collect(self.db,self.client(self.full_transport))
        self.assertEqual(self.db.execute('SELECT status FROM collection_state').fetchone()[0],'COMPLETE')

    def test_empty_response_never_complete(self):
        self.setup_range()
        c.collect(self.db,self.client(lambda *_:([],{})))
        self.assertEqual(self.db.execute('SELECT status,next_cursor FROM collection_state').fetchone()[:],('ERROR',18000))
        rows=c.quality(self.db)
        self.assertEqual(rows[0][-1],300)

    def test_cursor_stagnation(self):
        self.setup_range()
        c.collect(self.db,self.client(lambda *_:([raw(18000)],{})))
        self.assertEqual(self.db.execute('SELECT status FROM collection_state').fetchone()[0],'ERROR')

    def test_bad_pages_rejected(self):
        cases=[[raw(60,'KRW-OTHER')],[raw(0),raw(60)],[raw(60),raw(60)],
               [dict(raw(60),trade_price=float('nan'))]]
        for batch in cases:
            with self.subTest(batch=batch),self.assertRaises(ValueError):
                c.validate_page(batch,120,'KRW-BTC')

    def test_unobserved_boundary_gaps_remain_unknown(self):
        self.setup_range(0,300)
        # API only verified [180,300); [0,180) is not checked yet.
        c.collect(self.db,self.client(lambda *_:([raw(240),raw(180)],{})),page_budget=1)
        row=c.quality(self.db)[0]
        self.assertEqual(row[2:],(5,2,.4,3,1,2,0,3))

    def test_no_silent_relaxation_when_selection_insufficient(self):
        with self.assertRaisesRegex(ValueError,'0/50'):
            c.select_markets(self.client(lambda *_:([{'market':'KRW-USDT'}],{})),86400*100,50)

    def test_retry_backoff_and_exhaustion(self):
        calls=[]
        def transport(*_):
            calls.append(1)
            if len(calls)<3:
                raise urllib.error.HTTPError('test',429,'limit',{},None)
            return [],{}
        sleeps=[]
        client=c.Client(transport=transport,sleep=sleeps.append)
        self.assertEqual(client.get('/test'),[])
        self.assertEqual((client.requests,client.retries),(3,2))
        self.assertTrue(any(s>=2 for s in sleeps))
        def failing(*_):
            raise TimeoutError('timeout')
        client=self.client(failing)
        with self.assertRaises(TimeoutError):
            client.get('/test')
        self.assertEqual((client.requests,client.retries),(5,4))

    def test_remaining_req_and_418(self):
        sleeps=[]
        client=c.Client(transport=lambda *_:([],{'Remaining-Req':'group=candle; min=1800; sec=0'}),sleep=sleeps.append,clock=lambda:0)
        client.get('/test');client.get('/test')
        self.assertGreaterEqual(sleeps[-1],1.1)
        def blocked(*_):
            raise urllib.error.HTTPError('test',418,'blocked',{},None)
        client=self.client(blocked)
        with self.assertRaises(RuntimeError):client.get('/test')
        self.assertEqual(client.requests,1)

    def test_block_stops_all_markets(self):
        c.freeze(self.db,c.make_manifest(0,120,['KRW-ETH'],[],True))
        def blocked(*_):
            raise urllib.error.HTTPError('test',418,'blocked',{},None)
        client=self.client(blocked)
        c.collect(self.db,client)
        self.assertEqual(client.requests,1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM collection_state WHERE status='PENDING'").fetchone()[0],1)

    def test_quality_gaps_and_api_absence(self):
        self.setup_range(0,300)
        client=self.client(lambda *_:([raw(t) for t in (240,60,0)],{}))
        c.collect(self.db,client)
        row=c.quality(self.db)[0]
        self.assertEqual(row[2:],(5,3,.6,2,1,5,2,0))

    def test_manifest_immutable(self):
        self.setup_range()
        manifest=c.read_manifest(self.db)
        c.freeze(self.db,manifest)
        manifest['alts']=['KRW-NEW']
        with self.assertRaises(ValueError):c.freeze(self.db,manifest)

    def test_selection_uses_only_past_and_excludes_stable(self):
        start=100*86400
        def transport(path,p):
            if path.endswith('all'):
                return [{'market':m} for m in ('KRW-BTC','KRW-USDT','KRW-AAA','KRW-BBB')],{}
            self.assertLessEqual(c.parse(p['to']),start)
            self.assertNotEqual(p['market'],'KRW-USDT')
            if path.endswith('days'):
                return [raw(start-d*86400,p['market'],20 if p['market']=='KRW-BBB' else 10) for d in range(1,33)],{}
            return self.full_transport(path,p)
        alts,evidence=c.select_markets(self.client(transport),start,1)
        self.assertEqual(alts,['KRW-BBB'])
        self.assertEqual(evidence[0]['prior_24h_coverage'],1)

    def test_selection_rejects_future_response(self):
        start=100*86400
        def transport(path,p):
            if path.endswith('all'):return [{'market':'KRW-AAA'}],{}
            return [raw(start,'KRW-AAA')],{}
        with self.assertRaises(ValueError):c.select_markets(self.client(transport),start,1)

    def test_fixed_floor_value_rank_age_and_stables(self):
        start=100*86400
        values={'KRW-AAA':30,'KRW-BBB':20,'KRW-CCC':10,'KRW-YOUNG':1000}
        coverage={'KRW-AAA':.499,'KRW-BBB':.5,'KRW-CCC':1}
        def transport(path,p):
            if path.endswith('all'):
                return [{'market':m} for m in list(values)+['KRW-RLUSD','KRW-USDG','KRW-JPYC','KRW-BTC']],{}
            self.assertEqual(path,'/v1/candles/days')
            self.assertIn(p['market'],values)
            days=10 if p['market']=='KRW-YOUNG' else 32
            return [raw(start-d*86400,p['market'],values[p['market']]) for d in range(1,days+1)],{}
        def diagnostic(client,m,t):
            self.assertEqual(t,start)
            return dict(coverage=coverage[m],page_count=4,response_candles=800,unique_minutes=int(coverage[m]*1440),reached_window_start=True)
        with patch.object(c,'prior_day_coverage',side_effect=diagnostic):
            alts,evidence=c.select_markets(self.client(transport),start,2,min_coverage=.5)
            self.assertEqual(alts,['KRW-BBB','KRW-CCC'])
            self.assertEqual([e['eligible_trade_value_rank'] for e in evidence],[1,2,3])
            self.assertFalse(evidence[0]['selected'])
            self.assertTrue(evidence[1]['selected'])
            with self.assertRaises(ValueError):c.select_markets(self.client(transport),start,3,min_coverage=.5)
        manifest=c.make_manifest(start,start+86400,alts,evidence,min_coverage=.5)
        self.assertEqual(manifest['selection_time'],start)
        self.assertEqual(manifest['minimum_prior_coverage'],.5)
        c.freeze(self.db,manifest)
        modified=dict(manifest,minimum_prior_coverage=.4)
        with self.assertRaises(ValueError):c.freeze(self.db,modified)

    def test_prior_day_paginated_dense_and_sparse(self):
        start=100*86400
        lower=start-86400
        for n,expected,pages in ((1440,1.,8),(1296,.9,7),(720,.5,4)):
            with self.subTest(n=n):
                # Spread observed candles over the full day, not only one batch.
                stamps=[lower+(i*1440//n)*60 for i in range(n)]
                history=list(range(lower-200*60,lower,60))+stamps+[start,start+60]
                cursors=[]
                def transport(path,params):
                    self.assertEqual(params['count'],200)
                    cursor=c.parse(params['to'])
                    cursors.append(cursor)
                    return [raw(t) for t in sorted((t for t in history if t<cursor),reverse=True)[:200]],{}
                result=c.prior_day_coverage(self.client(transport),'KRW-BTC',start)
                self.assertEqual(result['coverage'],expected)
                self.assertEqual(result['unique_minutes'],n)
                self.assertEqual(result['expected_minutes'],1440)
                self.assertEqual(result['page_count'],pages)
                self.assertEqual(result['response_candles'],pages*200)
                self.assertTrue(result['reached_window_start'])
                self.assertEqual(cursors[0],start)
                self.assertTrue(all(a>b for a,b in zip(cursors,cursors[1:])))

    def test_prior_day_rejects_future_or_stuck_cursor(self):
        start=100*86400
        for ts in (start,start+60):
            with self.subTest(ts=ts),self.assertRaises(ValueError):
                c.prior_day_coverage(self.client(lambda *_:([raw(ts)],{})),'KRW-BTC',start)

    def test_dry_run_never_network_or_db_creation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'Client') as client,patch.object(c,'select_markets') as select,patch.object(c,'collect') as collect,contextlib.redirect_stdout(io.StringIO()) as output:
            db=Path(tmp)/'new.db'
            c.main(['--dry-run','--start','2026-09-01T00:00:00+09:00','--days','14','--alt-count','50','--db',str(db)])
            self.assertFalse(db.exists())
            client.assert_not_called()
            select.assert_not_called()
            collect.assert_not_called()
            self.assertIn('"mode": "DRY_RUN"',output.getvalue())

    def test_main_without_dry_run_selects_freezes_and_downloads_then_resumes(self):
        alts=[f'KRW-TEST{i:02}' for i in range(50)]
        start=c.parse('2026-09-01T00:00:00+09:00')
        # Only the HTTP transport and selection result are mocked; main, freeze,
        # transactions, collect, and resume execute normally in a temporary DB.
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'select_markets',return_value=(alts,[])) as select,patch.object(c.Client,'_transport',side_effect=self.full_transport) as http,patch.object(c.time,'sleep'),contextlib.redirect_stdout(io.StringIO()) as output:
            path=Path(tmp)/'new.db'
            c.main(['--db',str(path),'--start','2026-09-01T00:00:00+09:00','--days','14','--alt-count','50','--max-pages','1'])
            self.assertEqual(select.call_count,1)
            self.assertEqual(select.call_args.args[1:],(start,50,set()))
            self.assertEqual(http.call_count,1)
            self.assertEqual(http.call_args.args[1]['count'],200)
            with contextlib.closing(sqlite3.connect(path)) as db:
                before=c.read_manifest(db)
                self.assertEqual(before['alts'],alts)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],200)
                cursor=db.execute("SELECT next_cursor FROM collection_state WHERE market='KRW-BTC'").fetchone()[0]
            select.reset_mock()
            http.reset_mock()
            c.main(['--db',str(path),'--max-pages','1'])
            select.assert_not_called()
            self.assertEqual(http.call_count,1)
            self.assertEqual(c.parse(http.call_args.args[1]['to']),cursor)
            with contextlib.closing(sqlite3.connect(path)) as db:
                self.assertEqual(c.read_manifest(db),before)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],400)
            self.assertIn('"mode": "COLLECT"',output.getvalue())
            self.assertIn('"mode": "RESUME"',output.getvalue())

    def test_frozen_resume_never_reselects_and_rejects_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'frozen.db'
            with contextlib.closing(sqlite3.connect(path)) as db:
                c.init_db(db)
                c.freeze(db,c.make_manifest(86400,86400+14*86400,['KRW-AAA'],[],False))
                db.execute("UPDATE collection_state SET status='COMPLETE'")
                db.commit()
            with patch.object(c,'select_markets',side_effect=AssertionError('reselection')),patch.object(c.Client,'get',side_effect=AssertionError('network')):
                c.main(['--db',str(path)])
                with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                    c.main(['--db',str(path),'--days','7'])

    def test_existing_foreign_db_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'foreign.db'
            with contextlib.closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE original(x)')
            before=path.read_bytes()
            with patch.object(c.Client,'get',side_effect=AssertionError('network')),self.assertRaises(ValueError):
                c.main(['--db',str(path),'--start','2026-08-01T00:00:00Z'])
            self.assertEqual(path.read_bytes(),before)

    def test_crosscheck_no_price_changes(self):
        self.setup_range(0,86400)
        c.collect(self.db,self.client(self.full_transport))
        client=self.client(lambda *_:([raw(0,value=14400)],{}))
        c.crosscheck(self.db,client)
        self.assertEqual(self.db.execute('SELECT status FROM daily_crosscheck').fetchone()[0],'MATCH')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],1440)

    def test_v2_revised_reads_schema_without_event_analysis(self):
        from coin_analysis import surge_event_research_v2_revised as v2
        self.setup_range(0,120)
        c.collect(self.db,self.client(self.full_transport))
        series=v2.old.load_series(self.db,'KRW-BTC',0,120)
        self.assertEqual(len(series.times),2)
        self.assertEqual(list(series.close),[100,100])


if __name__=='__main__':unittest.main()
