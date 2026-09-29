import subprocess
import sys
import unittest
from unittest.mock import patch
from coin_analysis import forward_scanner_v4_live_smoke as smoke

class LiveSmokeBoundsTests(unittest.TestCase):
    def test_requires_explicit_opt_in_without_network_or_worker(self):
        with patch.object(sys,'argv',['smoke']),patch.object(smoke.subprocess,'run') as run:
            with self.assertRaises(SystemExit):smoke.main()
            run.assert_not_called()
    def test_supervisor_uses_hard_timeout_and_propagates_exit(self):
        with patch.object(sys,'argv',['smoke','--execute-live']),patch.object(smoke.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            with self.assertRaises(SystemExit) as result:smoke.main()
            self.assertEqual(result.exception.code,0)
            self.assertEqual(run.call_args.kwargs['timeout'],180)
            self.assertIn('--worker',run.call_args.args[0])
    def test_fixed_small_scope(self):
        self.assertEqual(smoke.MARKETS,['KRW-BTC','KRW-ETH','KRW-XRP'])
        self.assertEqual(smoke.MAX_REQUESTS,20)
        self.assertLessEqual(smoke.MAX_SECONDS,600)

if __name__=='__main__':unittest.main()
