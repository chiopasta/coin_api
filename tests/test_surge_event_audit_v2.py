import unittest

from coin_analysis.surge_event_audit_v2 import AuditedResearch, STAGES, null_reason
from coin_analysis.surge_event_research_v2 import Research, Series, extract_events
from tests.test_surge_event_research_v2 import T, rows, rally


class AuditTests(unittest.TestCase):
    def test_instrumentation_preserves_matching_and_counts_all_candidates(self):
        panel={'X':Series(rally()),'Y':Series(rows()),'Z':Series(rows())}
        events,_=extract_events('X',panel['X'],'A',T+360*60,T+1600*60)
        original=Research(panel,events,T+360*60,T+1600*60)
        audited=AuditedResearch(panel,events,T+360*60,T+1600*60)
        for event in events:
            for mode in ('primary','auxiliary'):
                self.assertEqual(original.match(event,mode),audited.match(event,mode))
                d=audited.matching_diagnostics[event['event_id']][mode]
                self.assertEqual(sum(d['first_failure'].values())+d['passed']['no_control_overlap'],d['passed']['candidates'])
                counts=[d['passed'][s] for s in STAGES]
                self.assertEqual(counts,sorted(counts,reverse=True))

    def test_missing_case_liquidity_is_distinct_from_ratio_failure(self):
        data=rally();del data[450]
        panel={'X':Series(data),'Y':Series(rows())}
        events,_=extract_events('X',panel['X'],'A',T+360*60,T+1600*60)
        r=AuditedResearch(panel,events,T+360*60,T+1600*60)
        chosen,reason=r.match(events[0],'primary')
        self.assertIsNone(chosen)
        self.assertEqual(reason,'case_preperiod_liquidity_unavailable')
        d=r.matching_diagnostics[events[0]['event_id']]['primary']
        self.assertEqual(d['first_failure'],{'case_liquidity':1})

    def test_null_reason_names_missing_window(self):
        data=rows();del data[599]
        s=Series(data)
        r=Research({'X':s},[],T,T+1600*60)
        self.assertIn('4/5',null_reason(s,T+600*60,'trade_value_5m',r,'X'))

    def test_restart_scope_differs_from_unrestricted_t0(self):
        # Characterization of the documented t0 definition issue; no policy change.
        data=rally()
        data[810]=(T+810*60,100.,100.,100.,100.,1_000_000.)
        for i in range(862,len(data)):
            data[i]=(T+i*60,135.,140.,135.,135.,1_000_000.)
        s=Series(data)
        events,_=extract_events('X',s,'A',T+360*60,T+1600*60)
        self.assertEqual(len(events),2)
        self.assertEqual(events[1]['base_price'],120)
        a,b=s.bounds(events[1]['first_hit_known_ts']-3660,events[1]['first_hit_bar_ts'])
        self.assertEqual(min(s.close[a:b]),100)


if __name__=='__main__':
    unittest.main()
