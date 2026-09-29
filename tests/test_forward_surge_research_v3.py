import contextlib
import io
import unittest

from coin_analysis import forward_surge_research_v3 as v3
from tests.test_surge_event_research_v2 import T, rows


class ForwardTests(unittest.TestCase):
    def test_features_unchanged_when_all_future_candles_deleted_or_modified(self):
        t=T+600*60
        data=rows(1100)
        # Nonconstant history also exercises MA, ranges and nonzero returns.
        data=[(ts,100+i*.01,101+i*.01,99+i*.01,100+i*.01,1e6+i*10) for i,(ts,*_) in enumerate(data)]
        def research(data):
            panel={m:v3.v2.old.Series(data) for m in ('A','B','C','D')}
            return v3.v2.old.Research(panel,[],T,T+1100*60,v3.v2.old.Series(data))
        base=v3.features(research(data),'A',t)
        truncated=[row for row in data if row[0]<t]
        modified=[row if row[0]<t else (row[0],1.,10000.,1.,9999.,1e15) for row in data]
        self.assertEqual(base,v3.features(research(truncated),'A',t))
        self.assertEqual(base,v3.features(research(modified),'A',t))
        original=v3.label_at(v3.v2.old.Series(data),t,30,5)
        changed=v3.label_at(v3.v2.old.Series(modified),t,30,5)
        absent=v3.label_at(v3.v2.old.Series(truncated),t,30,5)
        self.assertIs(original['value'],False)
        self.assertIs(changed['value'],True)
        self.assertIsNone(absent['value'])

    def test_incomplete_nonhit_unknown_and_observed_hit_positive(self):
        t=T+600*60
        data=rows(1000);del data[610]
        self.assertIsNone(v3.label_at(v3.v2.old.Series(data),t,30,5)['value'])
        data[605]=(data[605][0],100.,110.,100.,100.,1e6)
        label=v3.label_at(v3.v2.old.Series(data),t,30,5)
        self.assertIs(label['value'],True)
        self.assertFalse(label['complete'])

    def test_label_excludes_anchor_candle_and_includes_horizon_close(self):
        t=T+600*60
        data=rows(1000)
        data[599]=(T+599*60,100.,200.,100.,100.,1e6)
        self.assertIs(v3.label_at(v3.v2.old.Series(data),t,30,5)['value'],False)
        data[629]=(T+629*60,100.,110.,100.,100.,1e6)
        self.assertIs(v3.label_at(v3.v2.old.Series(data),t,30,5)['value'],True)

    def test_clusters_fixed_first_and_transitive_overlaps(self):
        observations=[dict(market='A',t=t) for t in (0,300,1800,4000)]
        cs=v3.clusters(observations,'L1')
        self.assertEqual(len(cs),2)
        self.assertEqual([x['representative'] for x in observations],[True,False,False,True])
        self.assertEqual(cs[0]['observations'],3)

    def test_matching_is_same_time_negative_and_no_duplicate_control(self):
        start=T+600*60;end=start+600
        ordinary=rows(1100);rally=list(ordinary)
        for i in range(610,len(rally)):rally[i]=(T+i*60,130.,130.,130.,130.,1e6)
        panel={m:v3.v2.old.Series(rally if m in ('A','B') else ordinary) for m in ('A','B','C','D')}
        with contextlib.redirect_stdout(io.StringIO()):result=v3.mine(panel,v3.v2.old.Series(ordinary),start,end)
        self.assertEqual(result['observations'],8)
        for kind,g in result['groups'].items():
            used=set()
            for p in g['positive_observations']:
                if 'control_market' not in p:continue
                self.assertIn(p['control_market'],('C','D'))
                self.assertTrue(start<=p['t']<end)
                self.assertNotIn((p['control_market'],p['t']),used)
                used.add((p['control_market'],p['t']))
                h,threshold=v3.LABELS[kind]
                self.assertIs(v3.label_at(panel[p['control_market']],p['t'],h,threshold)['value'],False)

    def test_market_balancing_and_missing_zero(self):
        pairs=[dict(market='A',control_market='C',t=t) for t in range(9)]+[dict(market='B',control_market='C',t=9)]
        cache={}
        for p in pairs:
            for m,x in [(p['market'],10 if p['market']=='A' else 0),('C',0)]:
                cache[(m,p['t'])]=dict(values={'x':x},flags={'positive':bool(x)})
        ordinary=v3.compare(pairs,cache)[0];balanced=v3.compare(pairs,cache,True)[0]
        self.assertEqual(ordinary['positive_mean'],9)
        self.assertAlmostEqual(balanced['positive_mean'],5)
        self.assertEqual(balanced['valid_pairs'],10)
        self.assertEqual(balanced['status'],'INSUFFICIENT_SAMPLE')


if __name__=='__main__':unittest.main()
