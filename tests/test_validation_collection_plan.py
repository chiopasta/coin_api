import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from coin_analysis import research_dataset_collector_v1 as c

class ValidationPlanTests(unittest.TestCase):
    def test_frozen_manifest_dry_run_collection_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'discovery.db';source.write_bytes(b'protected')
            m=c.make_manifest(86400,2*86400,['KRW-ETH'],[])
            m['protected_source_db']=str(source)
            file=root/'manifest.json';file.write_text(json.dumps(m),encoding='utf-8')
            dest=root/'validation.db';args=['--db',str(dest),'--manifest-file',str(file)]
            with contextlib.redirect_stdout(io.StringIO()),patch.object(c,'Client') as client,patch.object(c,'select_markets') as select,patch.object(c,'collect') as collect,patch.object(c,'quality'):
                c.main(args+['--dry-run'])
                self.assertFalse(dest.exists());client.assert_not_called();select.assert_not_called();collect.assert_not_called()
                client.return_value.requests=0;client.return_value.retries=0
                c.main(args);c.main(args)
                select.assert_not_called();self.assertEqual(collect.call_count,2)
            with contextlib.closing(sqlite3.connect(dest)) as db:self.assertEqual(c.read_manifest(db),m)
            self.assertEqual(source.read_bytes(),b'protected')
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                c.main(['--db',str(source),'--manifest-file',str(file)])
            m['alts']=['KRW-XRP'];m['markets']=['KRW-BTC','KRW-XRP'];file.write_text(json.dumps(m),encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):c.main(args)

    def test_unclosed_buffer_rejected_before_client_or_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m=c.make_manifest(86400,172800,['KRW-ETH'],[])
            file=root/'manifest.json';file.write_text(json.dumps(m),encoding='utf-8');db=root/'new.db'
            with patch.object(c.time,'time',return_value=172800),patch.object(c,'Client') as client,contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):c.main(['--db',str(db),'--manifest-file',str(file)])
                client.assert_not_called();self.assertFalse(db.exists())

    def test_committed_policy_no_main_period_overlap(self):
        m=json.loads(Path('docs/research_market_validation_v1_manifest.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(m['research_start'],m['validation_policy']['discovery_reference']['end'])
        self.assertEqual(len(m['alts']),50)
        self.assertEqual(m['validation_policy']['primary_filter']['threshold'],4)
        self.assertEqual(m['research_end']-m['research_start'],14*86400)

if __name__=='__main__':unittest.main()
