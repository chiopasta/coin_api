from contextlib import closing
from copy import deepcopy
from pathlib import Path
import unittest

from coin_analysis import surge_event_research_v2 as old
from coin_analysis.surge_event_research_v2_revised import (
    quality, baseline_at, price_events, price_episodes, RevisedResearch,
    statistics_table, analyze,
)
from tests.test_surge_event_research_v2 import rows, rally, T


class RevisedPolicyTests(unittest.TestCase):
    def test_quality_counts_edge_and_internal_gaps_without_filling(self):
        data=rows(10)
        s=old.Series([r for i,r in enumerate(data) if i not in (0,1,5,9)])
        q=quality(s,T,T+600)
        self.assertEqual((q['expected_minutes'],q['observed_minutes'],q['coverage_ratio']), (10,6,.6))
        self.assertEqual((q['longest_gap_minutes'],q['gap_count']), (2,3))
        self.assertEqual(quality(old.Series([]),T,T+600)['longest_gap_minutes'],10)

    def test_unrestricted_t0_excludes_target_and_uses_latest_tie(self):
        data=rows(200)
        data[140]=(T+140*60,82.7,82.7,82.7,82.7,1e6)
        data[150]=(T+150*60,82.7,82.7,82.7,82.7,1e6)
        data[180]=(T+180*60,20.,110.,20.,20.,1e6)
        s=old.Series(data);target=T+181*60
        i=baseline_at(s,target,60)
        self.assertEqual(s.times[i],T+151*60)
        data[181]=(T+181*60,1.,1.,1.,1.,1e6)
        self.assertEqual(i,baseline_at(old.Series(data),target,60))

    def test_ong_regression_fixture(self):
        target=old.parse_time('2026-08-20T22:46:00+09:00')
        data=[(target-60*(61-i),100.,100.,100.,100.,1e6) for i in range(70)]
        for i,r in enumerate(data):
            close_time=r[0]+60
            if close_time==old.parse_time('2026-08-20T22:06:00+09:00'):
                data[i]=(r[0],82.7,82.7,82.7,82.7,1e6)
            elif close_time==old.parse_time('2026-08-20T22:35:00+09:00'):
                data[i]=(r[0],96.7,96.7,96.7,96.7,1e6)
        s=old.Series(data);i=baseline_at(s,target,60)
        self.assertEqual(s.times[i],old.parse_time('2026-08-20T22:06:00+09:00'))
        self.assertEqual(s.close[i],82.7)

    @unittest.skipUnless(Path('data/altcoin_market.db').is_file(),'Local database not available')
    def test_ong_regression_actual_readonly_data(self):
        target=old.parse_time('2026-08-20T22:46:00+09:00')
        with closing(old.open_readonly('data/altcoin_market.db')) as db:
            s=old.load_series(db,'KRW-ONG',target-7200,target+60)
        i=baseline_at(s,target,60)
        self.assertEqual((s.times[i],s.close[i]),(old.parse_time('2026-08-20T22:06:00+09:00'),82.7))

    def test_first_hit_not_same_base_recross_and_milestones(self):
        s=old.Series(rally())
        events=price_events('X',s,'A',T+360*60,T+1600*60)
        self.assertEqual(len(events),1)
        e=events[0]
        self.assertEqual(s.times[baseline_at(s,e['target_time'],60)],e['t0'])
        self.assertEqual(e['target_time'],T+801*60)
        self.assertEqual(e['milestones']['10']['known_time'],e['target_time'])
        self.assertEqual(e['t0_from_search_start_minutes'],59)

    def test_episode_boundary_splits_overlapping_evaluation_windows(self):
        data=rows(30)
        for i in range(5,10):data[i]=(T+i*60,112.,115.,112.,112.,1e6)
        for i in range(10,15):data[i]=(T+i*60,105.,105.,105.,105.,1e6)
        for i in range(15,30):data[i]=(T+i*60,120.,123.,120.,120.,1e6)
        events=[dict(event_id='1',definition='A',t0=T,target_time=T+6*60),
                dict(event_id='2',definition='A',t0=T+14*60,target_time=T+16*60),
                dict(event_id='3',definition='B',t0=T,target_time=T+17*60)]
        episodes=price_episodes('X',old.Series(data),events,T,T+30*60)
        self.assertEqual(len(episodes),2)
        self.assertNotEqual(events[0]['episode_id'],events[1]['episode_id'])
        self.assertEqual(events[1]['episode_id'],events[2]['episode_id'])

    def test_symmetric_policy_and_observed_liquidity_mean(self):
        data=rows(1000);del data[450]
        s=old.Series(data);ts=T+800*60
        r=RevisedResearch({'X':s,'Y':s},[],T,T+1000*60,min_coverage=.8)
        self.assertEqual(r.policy_quality('X',ts,'A'),r.policy_quality('Y',ts,'A'))
        self.assertTrue(r.policy_quality('X',ts,'A')['eligible'])
        self.assertTrue(r.control_eligible('Y',ts,'A'))
        self.assertEqual(r.liquidity('X',ts),1e6)
        strict=RevisedResearch({'X':s,'Y':s},[],T,T+1000*60,min_coverage=1)
        self.assertFalse(strict.policy_quality('X',ts,'A')['eligible'])
        self.assertFalse(strict.control_eligible('Y',ts,'A'))

    def test_future_change_and_truncation_leave_feature_and_quality_unchanged(self):
        data=rows();ts=T+600*60
        panel={m:old.Series(data) for m in ('X','Y','Z','W')}
        before=deepcopy(RevisedResearch(panel,[],T,T+1600*60).snapshot('X',ts))
        data[600]=(ts,100.,1000.,100.,1000.,1e12)
        panel['X']=old.Series(data)
        after=RevisedResearch(panel,[],T,T+1600*60).snapshot('X',ts)
        self.assertEqual(before,after)
        panel['X']=old.Series(data[:600])
        self.assertEqual(before,RevisedResearch(panel,[],T,T+1600*60).snapshot('X',ts))

    def test_statistics_minimum_and_representative_filter(self):
        snap={str(m):{'flags':{k:True for k in old.FLAGS}} for m in old.OFFSETS}
        events=[dict(definition='A',is_representative=True,observation_policy={'eligible':True},snapshots=snap,
                     controls={'primary':{'snapshots':snap},'auxiliary':None}) for _ in range(19)]
        raw_only=deepcopy(events[0]);raw_only['is_representative']=False
        stats=statistics_table(events+[raw_only],20)
        row=next(r for r in stats if r['definition']=='A' and r['control_type']=='primary')
        self.assertEqual(row['total_events'],19)
        self.assertEqual(row['valid_control_count'],19)
        self.assertEqual(row['status'],'INSUFFICIENT_SAMPLE')
        self.assertIsNone(row['difference_pp'])
        self.assertEqual(statistics_table(events,19)[0]['status'],'SUFFICIENT_FOR_DESCRIPTION')

    def test_quality_does_not_change_raw_or_representative_selection(self):
        panel={m:old.Series(rally() if m=='X' else rows()) for m in ('X','Y','Z','W')}
        a=analyze(panel,T+360*60,T+1600*60,None,.8)
        b=analyze(panel,T+360*60,T+1600*60,None,1)
        identity=lambda r:[(e['event_id'],e['episode_id'],e['is_representative']) for e in r['events']]
        self.assertEqual(identity(a),identity(b))


if __name__=='__main__':unittest.main()
