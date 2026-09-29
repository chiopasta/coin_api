from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from coin_analysis import surge_event_research_v2_revised as v
from coin_analysis.research_market_quality import values
from tests.test_surge_event_research_v2 import T, rows, rally


class ManifestQualityTests(unittest.TestCase):
    def test_outcome_buffer_keeps_late_hit_but_excludes_buffer_anchors(self):
        data=rally()
        for i in range(1100,len(data)):
            data[i]=(T+i*60,150.,155.,150.,150.,1e6)
        s=v.old.Series(data)
        research_end=T+801*60
        raw=v.price_events('X',s,'A',T+360*60,T+1600*60)
        self.assertTrue(any(e['t0']>=research_end for e in raw))
        es,eps=v.dataset_events({'X':s},T+360*60,T+1600*60,research_end)
        self.assertTrue(es)
        self.assertTrue(any(e['target_time']>=research_end for e in es))
        self.assertTrue(all(e['t0']<research_end for e in es))
        self.assertEqual({eid for ep in eps for eid in ep['event_ids']},{e['event_id'] for e in es})
        r=v.RevisedResearch({'X':s},es,T+360*60,T+1600*60,research_end=research_end)
        self.assertIn('outside_evaluation_period',r.policy_quality('X',research_end,'A')['reasons'])
        self.assertNotIn('outside_evaluation_period',r.policy_quality('X',T+800*60,'B')['reasons'])

    def test_same_db_btc_and_utc_close_time_no_imputation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'research.db'
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE minute_candles(market,ts,open,high,low,close,trade_value)')
                db.execute('CREATE TABLE dataset_manifest(id INTEGER PRIMARY KEY,payload)')
                db.execute('INSERT INTO dataset_manifest VALUES(1,?)',(json.dumps(dict(collection_start=T,collection_end=T+600,alts=['KRW-X'])),))
                for m in ('KRW-X','KRW-BTC'):
                    db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',[(m,)+r for r in rows(10) if r[0]!=T+300])
                db.commit()
            before=path.read_bytes()
            manifest,panel,btc=v.load_manifest_dataset(path)
            self.assertEqual(set(panel),{'KRW-X'})
            self.assertEqual(len(btc.times),9)
            self.assertEqual(btc.times[0],T+60)
            self.assertIsNone(btc.price(T+360))
            self.assertEqual(before,path.read_bytes())

    def test_diagnostic_120_return_does_not_modify_v2_features(self):
        s=v.old.Series(rows())
        r=v.RevisedResearch({'X':s,'Y':s,'Z':s,'W':s},[],T,T+1600*60,s)
        ts=T+600*60
        self.assertEqual(values(r,'X',ts)['return_120m_pct'],0)
        self.assertNotIn('return_120m_pct',r.snapshot('X',ts)['values'])


if __name__=='__main__':unittest.main()
