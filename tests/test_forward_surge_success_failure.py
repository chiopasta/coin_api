import unittest
from coin_analysis import forward_surge_success_failure as sf
from tests.test_surge_event_research_v2 import T, rows

class SuccessFailureTests(unittest.TestCase):
    def test_future_deletion_and_mutation_leave_features_filter_and_starts_unchanged(self):
        t=T+600*60
        data=[(ts,100+i*.01,103+i*.01,97+i*.01,100+i*.01,1000+i) for i,(ts,*_) in enumerate(rows(1000))]
        deleted=[r for r in data if r[0]<t]
        changed=[r if r[0]<t else (r[0],1.,10000.,1.,9999.,1e12) for r in data]
        def research(ds):
            panel={m:sf.v3.v2.old.Series(ds) for m in ('A','B','C','D')}
            return sf.v3.v2.old.Research(panel,[],T,T+1000*60,sf.v3.v2.old.Series(ds))
        base=research(data);expected=sf.features(base,'A',t)
        original_starts=sf.starts(base.panel['A'],T,t+1)
        self.assertTrue(original_starts)
        for ds in (deleted,changed):
            r=research(ds)
            self.assertEqual(expected,sf.features(r,'A',t))
            self.assertEqual(original_starts,sf.starts(r.panel['A'],T,t+1))
        self.assertFalse(sf.outcome(sf.v3.label_at(base.panel['A'],t,30,5)))
        self.assertTrue(sf.outcome(sf.v3.label_at(research(changed).panel['A'],t,30,5)))
        self.assertIsNone(sf.outcome(sf.v3.label_at(research(deleted).panel['A'],t,30,5)))

    def test_exploratory_formulas_and_missing(self):
        t=T+600*60;data=rows(1000)
        def get(ds):
            s=sf.v3.v2.old.Series(ds);r=sf.v3.v2.old.Research({'A':s},[],T,t,s)
            return sf.features(r,'A',t)
        f=get(data)
        self.assertEqual(f['exploratory_value5_prior25_ratio'],1)
        self.assertEqual(f['exploratory_value15_prior15_ratio'],1)
        ds=[r for r in data if r[0]!=t-600]
        f=get(ds)
        self.assertIsNone(f['exploratory_value5_prior25_ratio'])
        self.assertIsNone(f['exploratory_value15_prior15_ratio'])
        self.assertIsNone(f['position30'])

    def test_partial_hit_is_unknown(self):
        self.assertIsNone(sf.outcome(dict(value=True,complete=False)))

    def test_comparison_preserves_zero_and_equal_market_weight(self):
        data=[]
        for market,x,y in [('A',10,True)]*9+[('B',0,True)]+[('C',0,False)]*5:
            data.append(dict(market=market,t=0,features={'x':x},labels={'L1':dict(value=y,complete=True)}))
        result=sf.compare(data,'L1','x',True)
        self.assertEqual(result['success_valid_n'],10)
        self.assertAlmostEqual(result['success_mean'],5)
        self.assertEqual(result['failure_mean'],0)
        self.assertEqual(result['status'],'INSUFFICIENT_SAMPLE')

if __name__=='__main__':unittest.main()
