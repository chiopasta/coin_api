import copy
import unittest
from coin_analysis import forward_surge_independent_validation as iv

def summary():
    label=dict(valid=100,positive=20,lift=2,success_markets=4,
               without_flock=dict(lift=2),by_market={m:dict(positive=5) for m in ('KRW-FLOCK','A','B','C')})
    return dict(cluster=dict(labels={y:copy.deepcopy(label) for y in ('L1','L2')}))

class IndependentValidationTests(unittest.TestCase):
    def test_frozen_replicated_gates_and_twenty_success_boundary(self):
        s=summary();self.assertEqual(iv.decide(s),'REPLICATED')
        s['cluster']['labels']['L2']['positive']=19
        self.assertEqual(iv.decide(s),'PARTIAL')

    def test_concentration_and_excluded_market_failure(self):
        s=summary()
        for r in s['cluster']['labels'].values():r['without_flock']['lift']=1
        self.assertEqual(iv.decide(s),'FAILED')
        s=summary()
        for r in s['cluster']['labels'].values():r['success_markets']=2
        self.assertEqual(iv.decide(s),'FAILED')

    def test_missing_outcomes_not_failed_replication(self):
        s=summary();s['cluster']['labels']['L2']['valid']=0
        self.assertEqual(iv.decide(s),'DATA_INSUFFICIENT')

    def test_exclude_first6h_does_not_promote_later_cluster_observation(self):
        def row(t):
            return dict(market='A',t=t,range=5,features={k:1 for k in iv.SECONDARY},
                        labels={y:dict(value=True,complete=True) for y in ('L1','L2')})
        first=row(0);later=row(300)
        result=iv.summarize([first,later],[first],300,600)
        self.assertEqual(result['signal_observations'],1)
        self.assertEqual(result['cluster']['observations'],0)
        self.assertEqual(result['verdict'],'DATA_INSUFFICIENT')

if __name__=='__main__':unittest.main()
