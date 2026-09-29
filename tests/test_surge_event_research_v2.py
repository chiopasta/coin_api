from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from coin_analysis.surge_event_research_v2 import (
    Series, Research, assign_episodes, extract_events, feature_snapshot,
    open_readonly, run_research, summarize,
)

T = 1_800_000_000


def rows(n=1600):
    return [(T+i*60, 100., 100., 100., 100., 1_000_000.) for i in range(n)]


def rally():
    data = rows()
    for i in range(800, len(data)):
        data[i] = (T+i*60, 120., 125., 120., 120., 1_000_000.)
    return data


class V2Tests(unittest.TestCase):
    def test_features_ignore_future_and_include_only_closed_candles(self):
        data=rows()
        ts=T+600*60
        before=feature_snapshot(Series(data), ts)
        data[600]=(T+600*60,100.,1000.,100.,1000.,1e12)
        self.assertEqual(before,feature_snapshot(Series(data),ts))
        self.assertEqual(before,feature_snapshot(Series(data[:600]),ts))
        self.assertEqual(before['values']['ma20'],100)
        self.assertEqual(before['values']['trade_value_ratio'],1)

    def test_missing_minutes_are_not_replaced_by_rows_or_zero(self):
        data=rows()
        del data[599]
        f=feature_snapshot(Series(data),T+600*60)
        self.assertIsNone(f['values']['return_5m_pct'])
        self.assertIsNone(f['values']['ma5'])
        self.assertIsNone(f['values']['trade_value_5m'])
        self.assertIsNone(f['flags']['trade_value_double'])

    def test_breakout_excludes_current_high(self):
        data=rows()
        data[599]=(T+599*60,100.,110.,100.,105.,1_000_000.)
        f=feature_snapshot(Series(data),T+600*60)
        self.assertTrue(f['flags']['prior_high_breakout'])

    def test_events_are_price_only_and_have_separate_definitions(self):
        data=rally()
        start,end=T+360*60,T+1600*60
        all_events=[]
        for kind in ('A','B'):
            events,_=extract_events('KRW-X',Series(data),kind,start,end)
            self.assertEqual(len(events),1)
            e=events[0]
            self.assertEqual(e['first_hit_bar_ts'],T+800*60)
            self.assertLessEqual(e['t0'],e['first_hit_bar_ts'])
            changed=[(*r[:5], 900_000_000.) for r in data]
            self.assertEqual(events,extract_events('KRW-X',Series(changed),kind,start,end)[0])
            all_events.extend(events)
        assign_episodes(all_events)
        self.assertEqual(len({e['episode_id'] for e in all_events}),1)

    def test_reset_required_and_new_episode_can_be_detected(self):
        data=rally()
        for i in range(1000,1100):
            data[i]=(T+i*60,100.,100.,100.,100.,1_000_000.)
        events,_=extract_events('KRW-X',Series(data),'A',T+360*60,T+1600*60)
        self.assertEqual(len(events),2)
        self.assertGreaterEqual(events[1]['t0'],events[0]['end_ts'])

    def test_incomplete_horizon_cannot_be_a_case(self):
        events,_=extract_events('KRW-X',Series(rally()[:810]),'B',T+360*60,T+810*60)
        self.assertEqual(events,[])

    def test_controls_are_same_time_and_require_future_and_liquidity(self):
        series=Series(rally())
        events,_=extract_events('KRW-X',series,'A',T+360*60,T+1600*60)
        panel={'KRW-X':series,'KRW-Y':Series(rows()),'KRW-Z':Series(rows())}
        research=Research(panel,events,T+360*60,T+1600*60)
        e=events[0]
        control,reason=research.match(e,'primary')
        self.assertIsNone(reason)
        self.assertNotEqual(control['market'],e['market'])
        self.assertEqual(control['t0'],e['t0'])
        self.assertFalse(research.control_eligible('KRW-X',e['t0'],'A'))
        self.assertIsNone(research.snapshot('KRW-X',e['t0'])['values']['btc_relative_60m_pct'])
        self.assertIsNone(research.snapshot('KRW-X',e['t0'])['values']['alt_relative_60m_pct'])
        aux,reason=research.match(e,'auxiliary')
        self.assertIsNone(reason)
        self.assertEqual(aux['market'],e['market'])
        self.assertNotEqual(aux['t0'],e['t0'])

    def test_control_rejects_dip_then_rally_and_missing_future(self):
        data=rows()
        # Below original 100, but 80 -> 95 is itself a >10% rally.
        data[805]=(T+805*60,80.,80.,80.,80.,1_000_000.)
        data[806]=(T+806*60,95.,95.,95.,95.,1_000_000.)
        research=Research({'KRW-X':Series(data)},[],T+360*60,T+1600*60)
        self.assertFalse(research.control_eligible('KRW-X',T+800*60,'A'))
        data=rows()
        del data[810]
        research=Research({'KRW-X':Series(data)},[],T+360*60,T+1600*60)
        self.assertFalse(research.control_eligible('KRW-X',T+800*60,'A'))

    def test_market_benchmark_is_causal_and_missing_btc_is_null(self):
        ts=T+600*60
        panel={m:Series(rows()) for m in ('A','B','C','D')}
        r=Research(panel,[],T,T+1600*60,Series(rows(400)))
        f=r.snapshot('A',ts)
        self.assertEqual(f['values']['alt_relative_60m_pct'],0)
        self.assertIsNone(f['values']['btc_relative_60m_pct'])
        changed=rows()
        changed[600]=(ts,100.,900.,100.,900.,1e12)
        panel['B']=Series(changed)
        after=Research(panel,[],T,T+1600*60,Series(rows(400))).snapshot('A',ts)
        self.assertEqual(f,after)

    def test_readonly_end_to_end_and_paired_denominators(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'candles.db'
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE minute_candles (market TEXT,ts INTEGER,open REAL,high REAL,low REAL,close REAL,trade_value REAL)')
                for m,data in [('KRW-X',rally()),('KRW-Y',rows()),('KRW-Z',rows()),('KRW-W',rows())]:
                    db.executemany('INSERT INTO minute_candles VALUES (?,?,?,?,?,?,?)',[(m,*r) for r in data])
                db.commit()
            before=hashlib.sha256(path.read_bytes()).hexdigest()
            with closing(open_readonly(path)) as db:
                with self.assertRaises(sqlite3.OperationalError):
                    db.execute('DELETE FROM minute_candles')
            report=run_research(path,start=T+360*60,end=T+1600*60)
            self.assertEqual(len(report['events']),2)
            self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest())
            json.dumps(report,allow_nan=False)
            self.assertTrue(any(r['event_n'] for r in report['statistics']))
            for e in report['events']:
                for m,s in e['snapshots'].items():
                    self.assertEqual(s['asof_ts'],e['t0']-int(m)*60)
            e=report['events'][0]
            e['snapshots']['5']['flags']['ma5_above_ma20']=None
            stats=summarize([e])
            r=next(r for r in stats if r['definition']==e['definition'] and r['control_type']=='primary'
                   and r['offset_minutes']==5 and r['feature']=='ma5_above_ma20')
            self.assertEqual(r['event_n'],0)
            self.assertIsNone(r['event_rate_pct'])


if __name__ == '__main__':
    unittest.main()
