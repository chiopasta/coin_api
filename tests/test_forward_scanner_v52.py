"""WS ingestion, frozen detection and lifecycle boundaries; no live network."""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from coin_analysis import forward_scanner_v52 as v
from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_dashboard_v50 as dashboard
from coin_analysis import scanner_analysis_v51 as analysis


def trade(market, ts, price=100, volume=2, seq=None, stream='REALTIME'):
    return json.dumps(dict(type='trade',code=market,trade_timestamp=int(ts*1000),
        trade_price=price,trade_volume=volume,sequential_id=str(ts) if seq is None else seq,
        stream_type=stream,ask_bid='BID'))


class Catalog(unittest.TestCase):
    def test_all_787_pairs_are_partitioned_without_five_market_limit(self):
        for count in (298,489):
            rows=[dict(market=f'KRW-C{n}') for n in range(count)]
            listed=v.catalog(rows,1)
            chunks=v.subscriptions(listed)
            self.assertEqual(set().union(*map(set,chunks)),set(listed))
            self.assertTrue(all(0<len(c)<=100 for c in chunks))
            self.assertEqual(len(listed),count)
            for chunk in chunks:
                request=json.loads(v.payload(chunk))
                self.assertEqual(request[1]['codes'],chunk)
                self.assertEqual(request[2]['codes'],chunk)

    def test_only_official_status_excludes_caution_and_future_delisting_remain(self):
        rows=[dict(market='KRW-BTC',market_warning='CAUTION'),
              dict(market='KRW-ETH',is_trading_suspended=True),
              dict(market='KRW-XRP',market_state='DELISTED'),
              dict(market='KRW-AAA',delisting_date='2020-01-01T00:00:00Z'),
              dict(market='KRW-BBB',delisting_date='2099-01-01T00:00:00Z'),
              dict(market='BTC-ETH')]
        c=v.catalog(rows,1700000000)
        self.assertTrue(c['KRW-BTC']['eligible']);self.assertTrue(c['KRW-BBB']['eligible'])
        self.assertFalse(c['KRW-ETH']['eligible']);self.assertFalse(c['KRW-XRP']['eligible'])
        self.assertFalse(c['KRW-AAA']['eligible']);self.assertNotIn('BTC-ETH',c)
        self.assertEqual(c['KRW-BTC']['status_evidence'],'LIST_ONLY_STATUS_UNKNOWN')

    def test_malformed_and_duplicate_catalogs_fail_closed(self):
        for rows in ([],{},[dict(market='BTC-ETH')],[dict(market='KRW-BTC')]*2):
            with self.assertRaises(ValueError):v.catalog(rows,1)


class Bridge(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=v.legacy.open_runtime(self.root,dict(markets=['KRW-BTC','KRW-ETH'],signal_start=86400),'UPBIT')
        self.addCleanup(self.db.close)
        self.listed=v.catalog([dict(market='KRW-BTC'),dict(market='KRW-ETH')],86400)
        self.bridge=v.Bridge(self.db,'UPBIT',self.listed)

    def subscribe(self,now=86400):
        self.bridge.subscribed(0,list(self.listed),now)
        # This helper models an already completed bootstrap range.
        with self.db:self.db.execute('DELETE FROM collection_jobs')

    def test_registered_subscribed_confirmed_active_and_stale_are_distinct(self):
        self.assertEqual(self.bridge.snapshot(86401)['active'],0)
        self.assertEqual(self.bridge.snapshot(86401)['registered'],2)
        self.subscribe()
        self.assertEqual(self.bridge.snapshot(86401)['subscription_sent'],2)
        self.assertEqual(self.bridge.snapshot(86401)['subscription_confirmed'],0)
        self.bridge.message(trade('KRW-ETH',86401),86402)
        self.assertEqual(self.bridge.snapshot(86402)['active'],1)
        self.assertEqual(self.bridge.snapshot(86402)['subscription_confirmed'],1)
        self.assertEqual(self.bridge.snapshot(86463)['active'],0)
        self.assertEqual(self.bridge.snapshot(86463)['stale'],1)

    def test_ohlcv_native_coin_volume_times_each_trade_price_not_close(self):
        self.subscribe()
        for ts,p,q in ((86410,100,2),(86430,110,3),(86420,90,4)):
            self.bridge.message(trade('KRW-ETH',ts,p,q),ts+1 if ts!=86420 else 86432)
        self.bridge.message(trade('KRW-ETH',86430,110,3),86433)
        self.bridge.flush(86464)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],0)
        self.bridge.flush(86465)
        row=self.db.execute('SELECT open,high,low,close,trade_value FROM minute_candles').fetchone()
        self.assertEqual(tuple(row),(100,110,90,110,890))
        self.assertEqual(self.db.execute('SELECT volume FROM ws_candles').fetchone()[0],9)
        self.assertEqual(self.bridge.counters['duplicates'],1)
        self.assertEqual(self.bridge.counters['out_of_order'],1)

    def test_partial_start_snapshot_and_absent_minutes_do_not_make_candles(self):
        self.subscribe(86401)
        self.bridge.message(trade('KRW-ETH',86410),86411)
        self.bridge.message(trade('KRW-ETH',86470,stream='SNAPSHOT'),86471)
        self.bridge.flush(86525)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],0)
        self.assertEqual(self.bridge.counters['partial_trades'],1)

    def test_disconnect_discards_partial_bars_and_reconnect_requests_gap_repair(self):
        self.subscribe()
        self.bridge.message(trade('KRW-ETH',86410),86411)
        self.bridge.disconnect(0,86420);self.bridge.flush(86465)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],0)
        self.assertEqual(self.bridge.snapshot(86465)['subscription_sent'],0)
        self.bridge.subscribed(0,list(self.listed),86480)
        self.assertIn('KRW-ETH',self.bridge.repair)
        self.assertTrue(self.db.execute('SELECT 1 FROM collection_jobs WHERE market=?',('KRW-ETH',)).fetchone())

    def test_late_trade_blocks_market_and_fresh_followup_does_not_clear_quality_fault(self):
        self.subscribe()
        self.bridge.message(trade('KRW-ETH',86410),86470)
        self.bridge.message(trade('KRW-ETH',86471),86472)
        self.assertEqual(self.bridge.markets['KRW-ETH']['state'],'BLOCKED')
        self.assertIn('KRW-ETH',self.bridge.repair)
        self.assertFalse(self.bridge.bars)

    def test_invalid_future_nonfinite_and_conflicting_id_are_rejected(self):
        self.subscribe()
        for raw in (trade('KRW-ETH',86500),trade('KRW-ETH',86401,price=float('nan')),
                    json.dumps(dict(error=dict(name='INVALID_PARAM')))):
            with self.assertRaises(ValueError):self.bridge.message(raw,86402)
        self.bridge.message(trade('KRW-ETH',86401,seq=7),86402)
        with self.assertRaisesRegex(ValueError,'Conflicting trade ID'):
            self.bridge.message(trade('KRW-ETH',86401,price=101,seq=7),86403)

    def test_official_ticker_suspension_excludes_and_never_inserts_ohlcv(self):
        self.subscribe()
        row=json.loads(trade('KRW-ETH',86401));row.update(type='ticker',is_trading_suspended=True)
        self.bridge.message(json.dumps(row),86402)
        self.assertEqual(self.bridge.snapshot(86402)['excluded'],1)
        self.assertEqual(self.bridge.snapshot(86402)['eligible'],1)
        self.bridge.flush(86465)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM minute_candles').fetchone()[0],0)
        self.assertEqual(self.bridge.snapshot(86465)['subscription_confirmed'],0)
        self.assertEqual(self.bridge.snapshot(86465)['registered'],2)
        self.assertEqual(self.bridge.snapshot(86465)['evaluated'],0)

    def test_exclusion_does_not_stall_other_pairs_or_change_cluster_state(self):
        self.subscribe()
        with self.db:
            self.db.execute("UPDATE scanner_state SET active=1,cluster_id='frozen' WHERE market='KRW-ETH'")
        row=json.loads(trade('KRW-ETH',86401));row.update(type='ticker',is_trading_suspended=True)
        self.bridge.message(json.dumps(row),86402);self.bridge.flush(86705)
        row=self.db.execute("SELECT * FROM scanner_state WHERE market='KRW-ETH'").fetchone()
        self.assertEqual(row['verified_until'],86700);self.assertEqual(row['last_observation'],86700)
        self.assertEqual(row['active'],1);self.assertEqual(row['cluster_id'],'frozen')
        self.bridge.evaluate(86705)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM signals').fetchone()[0],0)
        self.assertEqual(self.bridge.snapshot(86705)['evaluated'],0)

    def test_partial_minute_repair_is_scheduled_after_close_without_future_request(self):
        self.subscribe(86410)
        self.bridge.gaps['KRW-ETH']=(86400,86460)
        self.bridge.schedule_gaps(86464)
        self.assertFalse(self.db.execute('SELECT 1 FROM collection_jobs').fetchone())
        self.bridge.schedule_gaps(86465)
        row=self.db.execute("SELECT * FROM collection_jobs WHERE market='KRW-ETH'").fetchone()
        self.assertEqual((row['start'],row['end'],row['cursor']),(86400,86460,86460))

    def test_stream_bars_reach_original_signal_features_source_and_analysis_without_duplicates(self):
        # Complete past-only warmup establishes the original below4 cluster state.
        with self.db:
            for market in self.listed:
                self.db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',
                    [(market,t,100,100,100,100,1000) for t in range(64800,86400,60)])
            self.db.execute('UPDATE scanner_state SET verified_until=86400')
        self.bridge.evaluate(86400)
        self.subscribe()
        for n in range(5):
            ts=86400+60*n
            for market in self.listed:
                self.bridge.message(trade(market,ts+10,105 if market=='KRW-ETH' and n==4 else 100),ts+11)
            self.bridge.flush(ts+65)
        self.bridge.evaluate(86705)
        rows=self.db.execute('SELECT * FROM signals').fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source'],'LIVE');self.assertEqual(rows[0]['signal_time'],86700)
        self.assertEqual(rows[0]['detected_at'],86705)
        self.assertEqual(rows[0]['signal_price'],105)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM live_horizons').fetchone()[0],4)
        proof=self.db.execute('SELECT * FROM ws_signal_provenance').fetchone()
        self.assertAlmostEqual(proof['receive_delay'],1)
        self.assertEqual(proof['evaluation_delay'],5)
        before=tuple(self.db.execute('SELECT * FROM signal_features').fetchone())
        # Future candles only feed outcomes, not frozen feature rows.
        with self.db:self.db.execute("INSERT INTO minute_candles VALUES('KRW-ETH',86700,200,300,100,200,5000)")
        self.bridge.evaluate(86765)
        self.assertEqual(tuple(self.db.execute('SELECT * FROM signal_features').fetchone()),before)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM signals').fetchone()[0],1)
        self.assertEqual(self.bridge.snapshot(86705)['evaluated'],1)
        self.assertEqual(self.bridge.snapshot(86705)['complete_30m'],1)
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        source=dict(path=self.root/'upbit.db',exchange='UPBIT',archive=False,root=self.root)
        with patch.object(dashboard,'catalog',return_value={'ws_upbit':source}):
            service=analysis.Analysis(self.root/'analysis.db');service.refresh()
            self.assertEqual(service.report('ALL')['summary']['total'],1)

    def test_confirmed_rest_conflict_never_overwrites_existing_candle(self):
        self.subscribe()
        with self.db:self.db.execute("INSERT INTO minute_candles VALUES('KRW-ETH',86400,1,1,1,1,1)")
        self.bridge.message(trade('KRW-ETH',86410),86411)
        with self.assertRaises(v.scanner.CandleConflictError):self.bridge.flush(86465)
        self.assertEqual(self.db.execute("SELECT close FROM minute_candles WHERE market='KRW-ETH'").fetchone()[0],1)


class Lifecycle(unittest.TestCase):
    def test_full_queue_fails_closed_instead_of_dropping_trades_silently(self):
        streams=v.Streams({},time.monotonic()+1)
        for _ in range(v.QUEUE_SIZE+1):streams.put('MESSAGE','UPBIT',0,'x')
        self.assertTrue(streams.overflow.is_set());self.assertTrue(streams.stopped.is_set())

    def test_reconnect_is_bounded_and_restores_entire_shard_subscription(self):
        sock=Mock();sock.recv.return_value=''
        streams=v.Streams({},time.monotonic()+10,connect=Mock(return_value=sock))
        with patch.object(streams.stopped,'wait',return_value=False):
            streams.receive('BITHUMB',0,['KRW-BTC','KRW-ETH'])
        self.assertEqual(streams.connect.call_count,3)
        self.assertEqual(sock.send.call_count,3)
        for call in sock.send.call_args_list:
            self.assertEqual(json.loads(call.args[0])[1]['codes'],['KRW-BTC','KRW-ETH'])
        self.assertTrue(streams.close())

    def test_ws_rate_limit_stops_after_one_handshake_instead_of_retrying_block(self):
        class RateLimited(ConnectionError):status_code=429
        streams=v.Streams({},time.monotonic()+10,connect=Mock(side_effect=RateLimited()))
        streams.receive('UPBIT',0,['KRW-BTC','KRW-ETH'])
        self.assertEqual(streams.connect.call_count,1)
        events=[]
        while not streams.queue.empty():events.append(streams.queue.get()[0])
        self.assertIn('BLOCKED',events)

    def test_live_optin_and_clock_failure_prevent_runtime_creation(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(v,'RUNTIME_ROOT',Path(temp)),\
             patch.object(v.legacy.clock_guard,'verify_clock',return_value=dict(status='BLOCKED',reason='CLOCK_TEST')),\
             patch.object(v.scanner,'exclusive') as lock,patch.object(v.subprocess,'Popen') as child:
            root=Path(temp)/'new'
            with self.assertRaisesRegex(v.legacy.Stop,'CLOCK_TEST'):v.run(root,30,26)
            self.assertFalse(root.exists());child.assert_not_called()

    def test_supervisor_rejects_old_database_and_increased_limits_before_probe(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(v,'RUNTIME_ROOT',Path(temp)),\
             patch.object(v.legacy.clock_guard,'verify_clock') as clock:
            root=Path(temp)/'new';root.mkdir()
            with self.assertRaises(ValueError):v.run(root,30,26)
            with self.assertRaises(ValueError):v.run(Path(temp)/'another',86401,16001)
            clock.assert_not_called()


if __name__=='__main__':unittest.main()
