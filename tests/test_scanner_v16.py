import tempfile
from pathlib import Path
import unittest

from coin_analysis.scanner_v16 import Config, MarketState, Recorder


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(min_value=1000, min_trades=10)

    def state(self, falling=False):
        candles = [(i * 300, 130 - i if falling else 100) for i in range(24)]
        state = MarketState(candles, 7200)
        for second in range(331):
            state.ingest(7200 + second, 100, 10 if second > 300 else 1,
                         second, self.config)
        return state

    def test_burst_on_flat_trend(self):
        signal = self.state().evaluate(7530, self.config)
        self.assertIsNotNone(signal)
        self.assertEqual(signal['trend'], 'FLAT')
        self.assertAlmostEqual(signal['value_ratio'], 10)

    def test_downtrend_rejected(self):
        self.assertIsNone(self.state(falling=True).evaluate(7530, self.config))

    def test_warmup_and_stale_data_rejected(self):
        state = self.state()
        state.started = 7500
        self.assertIsNone(state.evaluate(7530, self.config))
        state.started = 7200
        self.assertIsNone(state.evaluate(7540, self.config))

    def test_duplicate_and_out_of_order_rejected(self):
        state = self.state()
        size = len(state.trades)
        self.assertFalse(state.ingest(7530, 100, 500, 330, self.config))
        self.assertFalse(state.ingest(7529, 100, 500, 999, self.config))
        self.assertEqual(len(state.trades), size)

    def test_boundary_uses_previous_price(self):
        state = MarketState([(6900, 100)], 7200)
        state.ingest(7499, 101, 1, 1, self.config)
        state.ingest(7500, 110, 1, 2, self.config)
        self.assertEqual(state.closes[-1], (7200, 101))

    def test_stale_preload_invalidates_trend(self):
        state = MarketState([(6600, 100)], 7200)
        state.ingest(7200, 100, 1, 1, self.config)
        self.assertEqual(len(state.closes), 0)

    def test_absolute_liquidity_required(self):
        self.assertIsNone(self.state().evaluate(7530, Config(min_value=1_000_000)))

    def test_restart_restores_cooldown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.db'
            recorder = Recorder(path, self.config)
            recorder.save('KRW-TEST', 7530, self.state().evaluate(7530, self.config))
            recorder.db.close()
            recorder = Recorder(path, self.config)
            self.assertEqual(recorder.last['KRW-TEST'], 7530)
            recorder.db.close()


if __name__ == '__main__':
    unittest.main()
