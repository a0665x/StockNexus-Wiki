"""BDD: opening/polling Wiki stays readable while another connection publishes."""
import sqlite3
import unittest
from unittest.mock import patch
from news_atlas.wiki.store import WikiStore
import test_wiki_http

class WikiResponsivenessTests(unittest.TestCase):
    setUp=test_wiki_http.WikiHTTPTests.setUp
    request=test_wiki_http.WikiHTTPTests.request

    def test_status_read_during_publication_does_not_wait_for_writer(self):
        original=sqlite3.connect
        def fast(*args,**kwargs):
            kwargs['timeout']=.05
            return original(*args,**kwargs)
        with self.store.connection() as writer:
            writer.execute('BEGIN IMMEDIATE')
            with patch('sqlite3.connect',fast):
                code,result=self.request('jobs?instrument=NASDAQ:TSLA')
                self.assertEqual(code,200,result)
                self.assertEqual(len(self.service.stores()),1)

    def test_reading_initialized_store_executes_no_schema_or_metadata_writes(self):
        original=sqlite3.connect;queries=[]
        def traced(*args,**kwargs):
            db=original(*args,**kwargs);db.set_trace_callback(queries.append);return db
        with patch('sqlite3.connect',traced):
            WikiStore(self.service.root,'NASDAQ:TSLA').jobs()
        writes=[q for q in queries if q.lstrip().upper().startswith(('CREATE','INSERT','UPDATE','DELETE')) or 'user_version=' in q or 'journal_mode=' in q]
        self.assertEqual(writes,[])

    def test_coverage_reuses_unchanged_scope_but_observes_committed_changes(self):
        with patch.object(self.service,'scope_rows',wraps=self.service.scope_rows) as rows:
            self.service.coverage(self.store);self.service.coverage(self.store)
            self.assertEqual(rows.call_count,1)
            self.store.configure({**self.store.config(),'enabled':False,'date_range':{'start':'2026-01-01','end':'2026-11-07'}})
            self.service.coverage(self.store)
            self.assertEqual(rows.call_count,2)
