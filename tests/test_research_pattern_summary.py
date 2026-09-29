import unittest
from coin_analysis.research_pattern_summary import summarize


def event(a,b):
    snaps=lambda x:{str(o):dict(values={'x':x},flags={'positive':None if x is None else x>0}) for o in (120,60,30,15,5)}
    return dict(snapshots=snaps(a),controls={'primary':dict(snapshots=snaps(b))})


class PatternSummaryTests(unittest.TestCase):
    def test_pairwise_missing_and_zero(self):
        r=summarize([event(0,1),event(3,None),event(None,2),event(4,2)],2)
        x=r['continuous'][0]
        self.assertEqual((x['valid_event_count'],x['valid_control_count'],x['paired_valid_count']),(3,3,2))
        self.assertEqual(x['event_median'],3)
        self.assertEqual(x['paired_event_median'],2)
        self.assertEqual(x['paired_control_median'],1.5)
        self.assertEqual(x['paired_median_difference'],.5)
        f=r['flags'][0]
        self.assertEqual((f['event_rate_pct'],f['control_rate_pct']),(50,100))

    def test_minimum_requires_valid_pairs_not_just_marginal_counts(self):
        es=[event(1,None)]*20+[event(None,1)]*20+[event(0,0)]
        x=summarize(es,20)['continuous'][0]
        self.assertEqual(x['valid_event_count'],21)
        self.assertEqual(x['paired_valid_count'],1)
        self.assertEqual(x['status'],'INSUFFICIENT_SAMPLE')


if __name__=='__main__':unittest.main()
