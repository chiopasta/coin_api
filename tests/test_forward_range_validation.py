import unittest
from coin_analysis.forward_range_validation import cluster_starts, rates, direction_groups


def row(t,width,positive=False,complete=True,market='A'):
    return dict(t=t,range=width,market=market,labels={k:dict(complete=complete,value=positive) for k in ('L1','L2')},
                return_5m_pct=0.,return_15m_pct=None,trade_value_ratio=2.,drawdown30=-2.)


class RangeValidationTests(unittest.TestCase):
    def test_cluster_only_resets_on_observed_below_threshold(self):
        rows=[row(i*300,w) for i,w in enumerate([0,4,5,None,6,3,4])]
        self.assertEqual([r['t'] for r in cluster_starts(rows,4)],[300,1800])

    def test_first_signal_not_replaced_by_later_valid_label(self):
        rows=[row(0,5,True,False),row(300,6,True,True)]
        first=cluster_starts(rows,4)
        self.assertEqual(len(first),1)
        self.assertEqual(rates(first)['L1']['valid'],0)
        self.assertIsNone(rates(first)['L1']['rate_pct'])

    def test_partial_hits_and_nonhits_excluded_symmetrically(self):
        rs=[row(0,4,True),row(300,4,False),row(600,4,True,False),row(900,4,False,False)]
        r=rates(rs)['L1']
        self.assertEqual((r['valid'],r['positive'],r['excluded'],r['rate_pct']),(2,1,2,50))

    def test_discovery_purges_outcomes_across_split(self):
        r=rates([row(0,4,True),row(300,4,False)],cutoff=1800)
        self.assertEqual(r['L1']['valid'],1)
        self.assertEqual(r['L1']['positive'],1)
        self.assertEqual(r['L2']['valid'],0)

    def test_fixed_subgroups_preserve_zero_and_missing(self):
        groups=direction_groups([row(0,4)])
        self.assertEqual(len(groups['return_5m_pct_nonpositive']),1)
        self.assertEqual(len(groups['return_15m_pct_missing']),1)
        self.assertEqual(len(groups['trade_value_ratio_ge2']),1)
        self.assertEqual(len(groups['drawdown_1_to_3pct']),1)


if __name__=='__main__':unittest.main()
