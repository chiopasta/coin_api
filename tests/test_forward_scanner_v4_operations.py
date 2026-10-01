import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from coin_analysis import forward_scanner_v4 as s
from coin_analysis import forward_scanner_v4_operations as o

class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.db'
        self.db=s.connect(self.path);s.initialize(self.db,['KRW-BTC','KRW-ETH'],86400)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def seed(self):
        with self.db:
            for sid,delay in [('a',12),('b',3600)]:
                self.db.execute('INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)',(sid,'KRW-ETH',86400+(sid=='b')*300,100,4,sid,86400+(sid=='b')*300+delay,delay,o.source_for(0,delay)))
                self.db.execute('INSERT INTO signal_features VALUES(?,?,?,?,?)',(sid,86400,'{}','{}','{}'))
                self.db.execute('INSERT INTO signal_outcomes VALUES(?,?,?,?,?,?,?,?)',(sid,'L1','PENDING',None,None,0,30,None))
    def test_exact_live_interval_boundaries(self):
        self.assertEqual([o.source_for(1000,1000+x) for x in (-1,0,12,299,300,301)],['CATCHUP','LIVE','LIVE','LIVE','CATCHUP','CATCHUP'])
    def test_default_live_and_separate_all(self):
        self.seed();self.assertEqual(s.statistics(self.db)['signals'],1)
        self.assertEqual(s.statistics(self.db,'CATCHUP')['signals'],1)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],2)
        self.assertEqual(s.grouped_statistics(self.db)['default_view'],'LIVE')
    def test_restart_session_and_interrupted_cycle(self):
        first=o.start_session(self.db,100000)
        self.assertEqual(self.db.execute('SELECT restart FROM scanner_sessions').fetchone()[0],0)
        o.start_cycle(self.db,first,100000)
        second=o.start_session(self.db,100100)
        self.assertEqual(self.db.execute('SELECT status FROM scanner_sessions WHERE session_id=?',(first,)).fetchone()[0],'INTERRUPTED')
        self.assertEqual(self.db.execute('SELECT restart FROM scanner_sessions WHERE session_id=?',(second,)).fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT ended_at FROM scanner_cycles').fetchone()[0],None)
        o.end_session(self.db,second,'CLOSED')
    def legacy(self):
        self.seed()
        self.db.execute('ALTER TABLE signals DROP COLUMN source');self.db.commit()
        rows=[dict(r) for r in self.db.execute('SELECT * FROM signals')]
        for r in rows:r['classification']='live_compatible_12s' if r['signal_id']=='a' else 'catch_up_batch_1'
        file=Path(self.tmp.name)/'evidence.json';file.write_text(json.dumps(dict(signals=rows)),encoding='utf-8')
        return file
    def test_migration_backup_preserves_every_business_table_and_idempotent(self):
        evidence=self.legacy();before=o.fingerprints(self.db)
        result=o.migrate(self.path,evidence)
        self.assertTrue(result['preserved']);self.assertEqual(result['audited_counts'],{'LIVE':1,'CATCHUP':1})
        self.assertTrue(Path(result['backup']).exists());self.assertEqual(before,o.fingerprints(self.db))
        self.assertTrue(o.migrate(self.path,evidence)['already_migrated'])
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("UPDATE signals SET source='LIVE'")
        self.db.rollback()
    def test_migration_refuses_evidence_mismatch_without_mutation(self):
        evidence=self.legacy();payload=json.loads(evidence.read_text());payload['signals'][0]['signal_price']=999
        evidence.write_text(json.dumps(payload));before=o.fingerprints(self.db)
        with self.assertRaises(ValueError):o.migrate(self.path,evidence)
        self.assertEqual(before,o.fingerprints(self.db));self.assertNotIn('source',[r[1] for r in self.db.execute('PRAGMA table_info(signals)')])
    def test_cycle_api_error_log(self):
        class Blocked:
            def get(self,*a,**k):raise s.collector.CollectionBlocked('test stop')
        sid=o.start_session(self.db)
        with self.assertRaises(s.collector.CollectionBlocked):s.cycle(self.db,Blocked(),90000,lambda _:None,session_id=sid)
        row=self.db.execute('SELECT * FROM scanner_cycles').fetchone()
        self.assertEqual(row['status'],'ERROR');self.assertIn('test stop',row['api_errors_json']);self.assertIsNotNone(row['ended_at'])
    def test_catchup_generation_and_restart_keep_source(self):
        from tests.test_forward_scanner_v4 import history,START
        with self.db:
            for m in ('KRW-BTC','KRW-ETH'):
                self.db.executemany('INSERT INTO minute_candles VALUES(?,?,?,?,?,?,?)',[(m,)+r for r in history(START+3600)])
            self.db.execute('UPDATE scanner_state SET verified_until=?',(START+3600,))
        s.process_observations(self.db,START+3600,lambda _:None)
        self.assertEqual(s.statistics(self.db)['signals'],0)
        self.assertEqual(s.statistics(self.db,'CATCHUP')['signals'],1)
        self.db.close();self.db=s.connect(self.path)
        s.process_observations(self.db,START+3600,lambda _:None)
        s.evaluate_outcomes(self.db,START+3600,lambda _:None)
        self.assertEqual(s.statistics(self.db,'ALL')['signals'],1)
        self.assertEqual(s.statistics(self.db,'CATCHUP')['L2']['success'],1)
    def test_migration_rolls_back_source_and_trigger_on_postcheck_failure(self):
        evidence=self.legacy();real=o.fingerprints;calls=0
        def broken(db):
            nonlocal calls
            calls+=1
            value=real(db)
            if calls==4:value['signals']='deliberate verification failure'
            return value
        with patch.object(o,'fingerprints',side_effect=broken),self.assertRaises(ValueError):o.migrate(self.path,evidence)
        self.assertNotIn('source',[r[1] for r in self.db.execute('PRAGMA table_info(signals)')])
        self.assertIsNotNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='immutable_signals'").fetchone())

if __name__=='__main__':unittest.main()
