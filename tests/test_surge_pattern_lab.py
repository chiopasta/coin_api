import unittest

from coin_analysis.backtest_v16 import Candle
from coin_analysis.surge_pattern_lab import extract, features, future_highs, match_controls, phase


def rows(n=700):
    return [Candle(i * 60, 100, 100, 100, 100, 1_000_000) for i in range(n)]


class PatternTests(unittest.TestCase):
    def test_future_window_excludes_anchor_and_incomplete_tail(self):
        data = rows(5)
        data[0] = Candle(0, 100, 500, 100, 100, 1)
        data[2] = Candle(120, 100, 130, 100, 100, 1)
        self.assertEqual(future_highs(data, 2), [130, 130, 100, None, None])

    def test_features_never_read_future(self):
        data = rows()
        before = features(data, 119)
        data[120] = Candle(7200, 100, 1000, 100, 1000, 1e12)
        self.assertEqual(before, features(data, 119))
        self.assertTrue(before['ma_flat'])
        self.assertFalse(before['value_burst'])
        self.assertIsNone(features(data, 118))

    def test_event_deduplication(self):
        data = rows(300)
        data[160] = Candle(9600, 100, 130, 100, 100, 1e8)
        cases, _, eligible = extract(data, 60, 20, 10**9)
        self.assertGreater(eligible, 0)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['anchor_ts'], 7200)
        self.assertEqual(cases[0]['first_hit_minutes'], 41)

    def test_split_excludes_straddling_labels(self):
        self.assertIsNone(phase(60, 2, 180))
        self.assertEqual(phase(0, 2, 180), 'discovery')
        self.assertEqual(phase(120, 2, 180), 'validation')

    def test_control_matching_rejects_overlap_and_liquidity_mismatch(self):
        def sample(ts, value):
            return dict(anchor_ts=ts, horizon_end_ts=ts+600, phase='discovery',
                        snapshots={'0': {'mean_value_60m': value}})
        case = sample(1000, 100)
        overlap = sample(1100, 100)
        wrong_value = sample(3000, 10000)
        valid = sample(5000, 150)
        pairs = match_controls([case], [overlap, wrong_value, valid])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]['control'], valid)


if __name__ == '__main__':
    unittest.main()
