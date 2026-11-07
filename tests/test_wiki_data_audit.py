"""BDD: inspect real stored formats before maintaining a selected stock/month."""
import json
from pathlib import Path
import sqlite3
import unittest
import test_research
from scripts.wiki_data_audit import audit

class WikiDataAuditTests(unittest.TestCase):
    setUp=test_research.ResearchTests.setUp
    add=test_research.ResearchTests.add

    def test_compatible_legacy_omissions_are_not_deleted_or_rewritten(self):
        with self.store.connection() as db:
            db.execute("UPDATE nodes SET payload=json_remove(payload,'$.opinion_metadata','$.translations') WHERE kind!='ArticleRevision'")
            before=db.execute('SELECT id,payload FROM nodes ORDER BY id').fetchall()
        result=audit(self.store.path,self.store.instrument)
        self.assertTrue(result['ready'],result)
        self.assertGreater(result['legacy']['missing_opinion_metadata'],0)
        with self.store.connection() as db:self.assertEqual([tuple(r) for r in before],[tuple(r) for r in db.execute('SELECT id,payload FROM nodes ORDER BY id')])

    def test_source_corruption_is_blocked_without_inventing_a_repair(self):
        with self.store.connection() as db:
            r=db.execute('SELECT id,payload FROM articles LIMIT 1').fetchone();a=json.loads(r['payload']);a['title']='Tampered source';db.execute('UPDATE articles SET payload=? WHERE id=?',(json.dumps(a),r['id']))
        result=audit(self.store.path,self.store.instrument)
        self.assertFalse(result['ready'])
        self.assertIn('article_hash',result['errors']);self.assertIn('citation_span_hash',result['errors'])

    def test_wrong_stock_future_schema_and_missing_database_fail_closed(self):
        self.assertIn('stock_identity',audit(self.store.path,'NASDAQ:GOOGL')['errors'])
        with self.store.connection() as db:db.execute('PRAGMA user_version=99')
        self.assertIn('future_schema',audit(self.store.path,self.store.instrument)['errors'])
        missing=Path(self.tmp.name)/'missing.sqlite3'
        with self.assertRaises(sqlite3.OperationalError):audit(missing,self.store.instrument)
        self.assertFalse(missing.exists())
