"""Scope provenance, actual ledger semantics and CLI/web agreement, offline."""
import ast
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from coin_analysis import scanner_market_scope as scope
from coin_analysis import scanner_control_v410 as control
from coin_analysis import scanner_dashboard_v50 as dashboard
from coin_analysis import scanner_desktop_v50 as desktop


class MarketInventory(unittest.TestCase):
    def test_legacy_get_markets_includes_all_krw_and_does_not_apply_preload_limit(self):
        # Never import the legacy program: its top-level execution has paper
        # tracking and WebSocket side effects. Compile only the pure selector.
        source=Path('archive/scanner_v15.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='get_markets')
        rows=[dict(market=f'KRW-C{i}') for i in range(80)]+[dict(market='BTC-ETH')]
        namespace=dict(http_get=lambda _:rows)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'legacy_selector','exec'),namespace)
        for name in scope.EXCHANGES:
            self.assertEqual(sorted(namespace['get_markets'](name)),scope.krw_markets(rows))
        self.assertEqual(len(scope.krw_markets(rows)),80)

    def test_exchange_pairs_and_distinct_assets_do_not_get_added_as_if_identical(self):
        rows=dict(UPBIT=scope.receipt([dict(market='KRW-BTC'),dict(market='KRW-ETH')],100),
                  BITHUMB=scope.receipt([dict(market='KRW-BTC'),dict(market='KRW-XRP')],101))
        value=scope.inventory(rows)
        with patch.object(scope,'read_inventory',return_value=value):
            result=scope.describe(dict(status='STOPPED'),['KRW-BTC','KRW-ETH'],now=102)
            self.assertEqual(result['total']['unique'],3);self.assertEqual(result['total']['venue_pairs'],4)
            self.assertEqual(result['scan']['unique'],0)
            self.assertEqual(scope.describe({},[],now=4000)['total']['status'],'STALE')
            self.assertEqual(scope.describe({},[],now=99)['total']['status'],'STALE')

    def test_missing_or_partial_listing_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(scope,'CACHE',Path(temp)/'missing.json'):
            self.assertIsNone(scope.describe({},[])['total']['unique'])
            scope.CACHE.write_text('{"version":1,"exchanges":{}}',encoding='utf-8')
            self.assertEqual(scope.describe({},[])['total']['status'],'UNKNOWN')
        with self.assertRaises(ValueError):scope.krw_markets([])

    def test_full_market_poll_cannot_fit_current_time_or_http_limits(self):
        plan=scope.capacity(787)
        self.assertGreater(plan['one_minute_24h_requests'],1_000_000)
        self.assertGreater(plan['minimum_round_seconds'],60)
        self.assertEqual(plan['full_rounds_after_warmup'],18)
        self.assertEqual(plan['sustainable_pair_ceiling_at_one_minute'],11)
        self.assertLess(scope.capacity(10)['one_minute_24h_requests'],16000)
        self.assertEqual(control.observer.MAX_REQUESTS,16000)
        self.assertEqual(control.observer.MAX_SECONDS,86400)


class ScopeAgreement(unittest.TestCase):
    def test_closing_idle_dashboard_does_not_stop_existing_scanner(self):
        operation=dashboard.Operations(120,40)
        with patch.object(control,'stop') as stop,patch.object(desktop,'cancel_pending_start') as cancel:
            operation.close()
            stop.assert_not_called();cancel.assert_not_called()

    def test_current_cli_and_dashboard_use_same_configured_db_scope_and_separate_followup(self):
        with tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
            base=Path(temp);token='a'*32;runtime=base/'runtime';root=runtime/('console_'+token)
            for obj,name,value in [(control,'CONTROL',base/'control'),(control.observer,'RUNTIME_ROOT',runtime),
                                   (scope,'CACHE',base/'no-listing.json'),(dashboard,'ARCHIVE',base/'absent.db')]:
                stack.enter_context(patch.object(obj,name,value))
            cfg=dict(markets=control.observer.MARKETS,signal_start=86400)
            root.mkdir(parents=True);(root/'config.json').write_text('{}')
            for exchange in scope.EXCHANGES:
                db=control.observer.open_runtime(root,cfg,exchange)
                with db:
                    db.execute("INSERT INTO signals VALUES('one','KRW-ETH',86400,1,4,'cluster',86412,12,'LIVE')")
                    for minutes in (5,15):db.execute("INSERT INTO live_horizons(signal_id,minutes,status) VALUES('one',?,'PENDING')",(minutes,))
                control.observer.ops.close_cleanly(db)
            state=dict(launch_id=token,root=str(root),status='RUNNING',phase='OBSERVING',manager={},child={})
            control.state_path(state).parent.mkdir(parents=True)
            control.persist(state);control.write_metadata(control.CONTROL/'current.json',dict(launch_id=token))
            stack.enter_context(patch.object(control,'alive',return_value=True))
            cli=control.snapshot();web=dashboard.View().snapshot()['scanner']
            self.assertEqual(cli['market_scope'],web['market_scope'])
            self.assertEqual(web['market_scope']['scan'],dict(unique=5,venue_pairs=10,signal_pairs=8))
            self.assertEqual(web['market_scope']['focus']['unique'],1)
            self.assertEqual(web['market_scope']['focus']['venue_pairs'],2)
            self.assertEqual(web['market_scope']['configured_unique'],len(control.observer.MARKETS))
            self.assertIs(control.observer.MARKETS,control.observer.v42.MARKETS)
            with patch.object(control,'start',return_value=0) as start:
                self.assertEqual(desktop.main(['_scanner','--seconds','120','--max-requests','40']),0)
                self.assertEqual(start.call_args.args[:2],(120,40))


if __name__=='__main__':unittest.main()
