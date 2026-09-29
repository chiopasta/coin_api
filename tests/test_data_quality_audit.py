"""Offline checks of calendar coverage and missing-minute arithmetic."""
import sqlite3
import unittest
from collections import Counter

from coin_analysis.data_quality_audit import day_of, day_start, gap_lengths, inventory, windows


class DataQualityAuditTests(unittest.TestCase):
    def test_kst_day_boundary(self):
        start = day_start(20000)
        self.assertEqual(day_of(start - 60), 19999)
        self.assertEqual(day_of(start), 20000)

    def test_inventory_contiguous_run_and_internal_gaps(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE minute_candles(market TEXT, ts INTEGER)')
            db.executemany('INSERT INTO minute_candles VALUES (?, ?)',
                           [('A', t) for t in (0, 60, 240, 300, 360, 540)])
            row = inventory(db)['A']
        self.assertEqual(row['count'], 6)
        self.assertEqual(row['longest_run_minutes'], 3)
        self.assertEqual(row['longest_run_start'], 240)
        self.assertEqual(row['longest_run_end'], 420)
        self.assertEqual(row['longest_gap_minutes'], 2)
        self.assertEqual(row['gap_count'], 2)

    def test_gap_lengths_include_edges_and_empty_day(self):
        self.assertEqual(list(gap_lengths([60, 180], 0, 300)), [1, 1, 1])
        self.assertEqual(list(gap_lengths([], 0, 86400)), [1440])
        self.assertEqual(list(gap_lengths(range(0, 86400, 60), 0, 86400)), [])

    def test_same_cohort_must_meet_every_daily_threshold(self):
        markets = {
            'stable': {'daily': Counter({0: 1296, 1: 1296, 2: 1296})},
            'average_only': {'daily': Counter({0: 1440, 1: 1440, 2: 1295})},
            'missing_day': {'daily': Counter({0: 1440, 2: 1440})},
        }
        row = next(r for r in windows(markets, [0, 1, 2]) if r['threshold'] == .9)
        self.assertEqual(row['markets'], ['stable'])
        self.assertEqual(row['candle_count'], 3888)


if __name__ == '__main__':
    unittest.main()
