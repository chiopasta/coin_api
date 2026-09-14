import unittest

from coin_analysis.backtest_v16 import Candle, ProxyConfig, contiguous_runs, detect, outcome, summarize


def candles(n=200):
    return [Candle(i * 60, 100, 100, 100, 100, 10_000_000) for i in range(n)]


class BacktestTests(unittest.TestCase):
    def test_no_lookahead_and_signal_close_time(self):
        rows = candles()
        rows[120] = Candle(7200, 100, 101, 100, 101, 100_000_000)
        before = list(detect(rows[:121], ProxyConfig()))
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0][1]['signal_ts'], 7260)
        rows[121] = Candle(7260, 180, 210, 170, 200, 500_000_000)
        after = list(detect(rows, ProxyConfig()))
        self.assertEqual(before[0], after[0])

    def test_next_open_entry_and_cost(self):
        rows = candles(3)
        rows[1] = Candle(60, 110, 125, 105, 120, 1)
        result = outcome(rows, 0, 1, 0.2)
        self.assertEqual(result['entry_price'], 110)
        self.assertAlmostEqual(result['net_return_pct'], (120 / 110 - 1) * 100 - 0.2)

    def test_gap_does_not_become_a_valid_outcome(self):
        rows = candles(5)
        del rows[2]
        runs = list(contiguous_runs(rows))
        self.assertEqual([len(r) for r in runs], [2, 2])
        self.assertIsNone(outcome(runs[0], 0, 2, 0.2))

    def test_split_purges_crossing_outcome(self):
        result = outcome(candles(5), 0, 3, 0.2)
        summary = summarize([dict(signal_ts=60, outcomes={'3': result})], [3], 120)
        self.assertEqual(summary['all']['horizons']['3']['eligible'], 1)
        self.assertEqual(summary['discovery']['horizons']['3']['eligible'], 0)


if __name__ == '__main__':
    unittest.main()
