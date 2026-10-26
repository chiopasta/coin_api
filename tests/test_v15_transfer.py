from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock
import urllib.request
import zipfile

from coin_analysis import v15_transfer as t
from coin_analysis import v15_release as r


def database(path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''
        CREATE TABLE signals(id INTEGER PRIMARY KEY,created_at TEXT,exchange TEXT,
          market TEXT,score INTEGER,price REAL);
        CREATE TABLE signal_price_history(signal_id INTEGER,minute INTEGER,
          observed_at TEXT,price REAL,return_pct REAL,PRIMARY KEY(signal_id,minute));
        INSERT INTO signals VALUES(1,'2026-10-26 00:00:00','UPBIT','KRW-TEST',60,100);
        INSERT INTO signal_price_history VALUES(1,0,'2026-10-26 00:00:00',100,0);
        ''')
        db.commit()


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.db';database(self.source)

    def pack(self,name='backup'):
        return t.backup({'live':self.source},self.root/name,self.root/'identity.json')

    def test_backup_restore_source_preserved_and_no_overwrite(self):
        before=t.sha256(self.source);result=self.pack()
        manifest=result['manifest'];record=manifest['files'][0]
        self.assertEqual(record['user_version'],0)
        self.assertEqual(record['table_counts']['signals'],1)
        self.assertNotIn(str(self.root),json.dumps(manifest))
        restored=t.restore(result['zip'],result['sha256'],self.root/'restore')
        self.assertFalse(restored['automatic_merge'])
        self.assertEqual(t.sha256(self.source),before)
        with self.assertRaises(FileExistsError):t.restore(result['zip'],result['sha256'],self.root/'restore')
        with self.assertRaises(FileExistsError):self.pack()
        with self.assertRaises(ValueError):t.snapshot(self.source,self.source)

    def test_registry_identity_stable_across_snapshots(self):
        a=self.pack();b=self.pack('second')
        self.assertEqual(a['manifest']['source_pc_id'],b['manifest']['source_pc_id'])
        self.assertEqual(a['manifest']['files'][0]['source_database_id'],b['manifest']['files'][0]['source_database_id'])
        self.assertNotEqual(a['manifest']['backup_id'],b['manifest']['backup_id'])

    def test_wrong_sha_rejected_before_destination_creation(self):
        a=self.pack()
        with self.assertRaises(ValueError):t.restore(a['zip'],'0'*64,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())

    def test_zip_path_traversal_duplicate_and_crc_rejected(self):
        for index,names in enumerate([['../escape.db'],['manifest.json','manifest.json']]):
            path=self.root/f'unsafe{index}.zip'
            with zipfile.ZipFile(path,'x') as z:
                for n in names:z.writestr(n,'{}')
            with self.assertRaises(ValueError):t.restore(path,t.sha256(path),self.root/f'bad{index}')
        a=self.pack();corrupt=self.root/'corrupt.zip'
        payload=bytearray(Path(a['zip']).read_bytes());payload[70]^=0xff;corrupt.write_bytes(payload)
        with self.assertRaises((zipfile.BadZipFile,ValueError,RuntimeError)):
            t.restore(corrupt,t.sha256(corrupt),self.root/'corrupt-restore')

    def test_manifest_count_and_database_sha_tamper_quarantined(self):
        a=self.pack()
        for index,key in enumerate(['counts','sha']):
            path=self.root/f'tamper{index}.zip'
            with zipfile.ZipFile(a['zip']) as src,zipfile.ZipFile(path,'x') as dst:
                for name in src.namelist():
                    content=src.read(name)
                    if name=='manifest.json':
                        m=json.loads(content)
                        if key=='counts':m['files'][0]['table_counts']['signals']=999
                        else:m['files'][0]['sha256']='0'*64
                        content=json.dumps(m).encode()
                    dst.writestr(name,content)
            target=self.root/f'tamper-restore{index}'
            with self.assertRaises(ValueError):t.restore(path,t.sha256(path),target)
            self.assertFalse((target/'verification.json').exists())

    def test_unknown_schema_and_token_material_block_packaging(self):
        with closing(sqlite3.connect(self.source)) as db:
            db.execute('CREATE TABLE secrets(value)');db.commit()
        with self.assertRaises(ValueError):self.pack()
        self.assertFalse((self.root/'backup/v15-backup.zip').exists())
        path=self.root/'credential-fixture'
        path.write_bytes(b'prefix ghp_'+b'a'*32)
        with self.assertRaises(ValueError):t.reject_secrets(path)

    def test_online_backup_with_concurrent_wal_writer_is_consistent(self):
        with closing(sqlite3.connect(self.source)) as db:
            db.execute('PRAGMA journal_mode=WAL')
        stopped=threading.Event();ready=threading.Event();writes=[];errors=[]
        def writer():
            try:
                with closing(sqlite3.connect(self.source,timeout=.5)) as db:
                    for i in range(300):
                        if stopped.is_set():break
                        db.execute('UPDATE signals SET price=?',(100+i,))
                        db.execute('UPDATE signal_price_history SET price=?',(100+i,));db.commit()
                        writes.append(i);ready.set();time.sleep(.001)
            except Exception as exc:errors.append(type(exc).__name__)
        thread=threading.Thread(target=writer);thread.start();self.assertTrue(ready.wait(2))
        try:
            for i in range(3):
                dest=self.root/f'copy{i}.db';t.snapshot(self.source,dest)
                self.assertEqual(t.describe(dest)['integrity'],'ok')
                with closing(t.readonly(dest,True)) as db:
                    self.assertEqual(db.execute('SELECT price FROM signals').fetchone()[0],
                                     db.execute('SELECT price FROM signal_price_history').fetchone()[0])
            time.sleep(.015)
        finally:stopped.set();thread.join(2)
        self.assertFalse(thread.is_alive());self.assertFalse(errors);self.assertGreater(len(writes),2)

    def test_busy_source_aborts_with_budget_no_source_change(self):
        before=t.sha256(self.source)
        with closing(sqlite3.connect(self.source)) as db:
            db.execute('BEGIN EXCLUSIVE')
            start=time.monotonic()
            with self.assertRaises(TimeoutError):t.snapshot(self.source,self.root/'busy.db',deadline_seconds=.1)
            self.assertLess(time.monotonic()-start,1)
            db.rollback()
        self.assertEqual(t.sha256(self.source),before)

    def test_compare_colliding_ids_and_schema_never_merges(self):
        incoming=self.root/'incoming.db';t.snapshot(self.source,incoming)
        self.assertEqual(t.compare(self.source,incoming)['tables']['signals']['identical_keys'],1)
        with closing(sqlite3.connect(incoming)) as db:
            db.execute('UPDATE signals SET price=999');db.commit()
        result=t.compare(self.source,incoming)
        self.assertFalse(result['automatic_merge']);self.assertEqual(result['tables']['signals']['conflicting_keys'],1)
        with closing(sqlite3.connect(incoming)) as db:db.execute('ALTER TABLE signals ADD COLUMN extra')
        self.assertEqual(t.compare(self.source,incoming)['status'],'QUARANTINE_SCHEMA_MISMATCH')


class GitHubSafetyTests(unittest.TestCase):
    def client(self):
        client=object.__new__(r.GitHub);client.repo='owner/backups';client.api=Mock()
        return client

    def test_public_repository_blocked(self):
        client=self.client();client.api.return_value={'private':False,'visibility':'public'}
        with self.assertRaises(ValueError):client.private(write=True)
        self.assertEqual(client.api.call_count,1)

    def test_existing_release_never_replaced(self):
        client=self.client();client.api.return_value={'id':123}
        with self.assertRaises(FileExistsError):client.absent('/repos/owner/backups/releases/tags/old')
        self.assertEqual(client.api.call_args.args,('/repos/owner/backups/releases/tags/old',))

    def test_redirect_strips_authorization_and_rejects_other_hosts(self):
        req=urllib.request.Request('https://api.github.com/asset',headers={'Authorization':'Bearer fixture'})
        handler=r.SafeRedirect()
        result=handler.redirect_request(req,None,302,'redirect',{},'https://release-assets.githubusercontent.com/blob')
        self.assertIsNone(result.get_header('Authorization'))
        with self.assertRaises(ValueError):handler.redirect_request(req,None,302,'redirect',{},'https://example.org/blob')


if __name__=='__main__':unittest.main()
