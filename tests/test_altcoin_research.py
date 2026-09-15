import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from coin_analysis.altcoin_research import analyze, evaluate_run, metrics, render, symbols
from coin_analysis.historical_breakout_lab_v1 import Candle, init_db


def candles(n=260):
    rows = [Candle(i * 60, 100, 100, 100, 100, 1_000_000) for i in range(n)]
    for i in range(120, 125):
        rows[i] = Candle(i * 60, 100, 100, 100, 100, 8_000_000)
    return rows


class AltcoinResearchTests(unittest.TestCase):
    def test_future_does_not_change_earlier_alerts(self):
        rows = candles()
        before = evaluate_run(rows, 60, 10, 10**9)
        rows[150] = Candle(9000, 100, 120, 100, 100, 1e9)
        after = evaluate_run(rows, 60, 10, 10**9)
        identity = lambda alerts: [(a['signal_ts'], a['rule'], a['features'])
                                  for a in alerts if a['signal_ts'] <= 9000]
        self.assertTrue(identity(before))
        self.assertEqual(identity(before), identity(after))
        self.assertTrue(any(a['success'] for a in after))

    def test_incomplete_future_is_not_negative_label(self):
        alerts = evaluate_run(candles(130), 60, 10, 10**9)
        self.assertTrue(alerts)
        self.assertTrue(all(a['success'] is None for a in alerts))

    def test_cross_split_alerts_are_not_scored(self):
        alerts = evaluate_run(candles(), 60, 10, 150 * 60)
        self.assertTrue(any(a['phase'] is None for a in alerts))
        for alert in alerts:
            alert['market'] = 'KRW-TEST'
        summary = metrics(alerts, [])
        for part in summary.values():
            self.assertTrue(all(m['evaluated'] == 0 for m in part.values()))

    def test_recall_requires_five_minutes_and_same_market(self):
        case = dict(market='KRW-TEST', phase='validation', anchor_ts=7200,
                    first_hit_minutes=21)
        alert = dict(market='KRW-TEST', phase='validation', rule='quiet_accumulation',
                     signal_ts=8160, complete=True, success=True)
        self.assertEqual(metrics([alert], [case])['validation']['quiet_accumulation']['missed_events'], 1)
        alert['signal_ts'] = 8100
        self.assertEqual(metrics([alert], [case])['validation']['quiet_accumulation']['recall_pct'], 100)
        alert['market'] = 'KRW-OTHER'
        self.assertEqual(metrics([alert], [case])['validation']['quiet_accumulation']['recall_pct'], 0)

    def test_database_report_excludes_majors_and_preserves_gaps(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'market.db'
            with closing(sqlite3.connect(path)) as db:
                init_db(db)
                rows = candles()
                rows[150] = Candle(9000, 100, 125, 100, 100, 1_000_000)
                for market in ('KRW-BTC', 'KRW-TEST'):
                    db.executemany('INSERT INTO minute_candles VALUES (?,?,?,?,?,?,?)',
                        [(market, 1_800_000_000 + c.ts, c.open, c.high, c.low, c.close, c.value)
                         for c in rows if c.ts != 200 * 60])
                db.commit()
            report = analyze(path, symbols('BTC'), [], 1, 60, 10)
            self.assertEqual(report['markets'], ['KRW-TEST'])
            self.assertEqual(report['coverage'][0]['runs'], 2)
            self.assertEqual(len(report['cases']), 1)
            self.assertTrue(any(a['success'] for a in report['alerts']))
            self.assertIn('알트코인', render(report))
            json.dumps(report, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
