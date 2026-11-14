"""Behavior boundaries: cache reads must not mutate, fetch or depend on UI budgets."""
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from news_atlas.context_api import query, handle
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.research import Research, put, taxonomy
from test_server import row
from test_wiki import proposal

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.repo=GraphRepository(self.root/'news-atlas.sqlite3')
        self.news=self.repo.for_query({'ticker':'TSLA','instrument':'NASDAQ:TSLA','sources':[]})
        self.now=dt.datetime.now(dt.timezone.utc)
        self.day=(self.now-dt.timedelta(days=1)).date().isoformat()
        self.a=row(title='Tesla earnings demand',day=self.day,symbols=['TSLA'])
        self.b=row(title='Tesla demand changes',day=self.day,suffix='two',symbols=['TSLA'])
        self.news.save('massive','q',[self.a,self.b],[])
        self.service=WikiService(self.repo,runner=lambda s,j,a,c:{'proposal':proposal(a)},start_worker=False)
    def read(self,resource,**kw):
        with patch('news_atlas.providers.fetch',side_effect=AssertionError('network forbidden')):
            return query(self.root,resource,{'instrument':'NASDAQ:TSLA',**kw})
    def test_news_paginates_database_independent_of_graph(self):
        a=self.read('news',limit='1');b=self.read('news',limit='1',offset=str(a['next_offset']))
        self.assertEqual(a['total'],2);self.assertNotEqual(a['items'][0]['id'],b['items'][0]['id'])
        self.assertEqual(a['model_calls'],0)
    def test_exclusive_end_and_unknown_dates(self):
        r=self.read('news',end=self.day+'T10:00:00+00:00')
        self.assertEqual(r['total'],0)
    def test_unknown_stock_cannot_create_database_or_cross_exchange(self):
        before=list(self.root.rglob('*.sqlite3'))
        for ident in ('NASDAQ:UNKNOWN','NYSE:TSLA'):
            with self.assertRaises(FileNotFoundError):self.read('news',instrument=ident)
        self.assertEqual(before,list(self.root.rglob('*.sqlite3')))
    def test_related_has_explicit_relation_basis_and_stays_in_stock(self):
        r=self.read('related',id=self.a['id'])
        self.assertEqual(r['items'][0]['id'],self.b['id'])
        self.assertTrue(r['items'][0]['relation_evidence']['shared_symbols'])
        with self.assertRaises(FileNotFoundError):self.read('related',id='missing')
    def test_prices_missing_not_zero_and_does_not_create_cache(self):
        r=self.read('prices');self.assertEqual(r['status'],'unavailable');self.assertIsNone(r['change_percent'])
        self.assertFalse(Path(str(self.news.path)+'.prices.sqlite3').exists())
    def test_prices_ignore_foreign_ticker_and_report_actual_bounds(self):
        path=Path(str(self.news.path)+'.prices.sqlite3')
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE series(key TEXT,payload TEXT,fetched REAL)')
            for ticker,close in [('TSLA',100),('AAPL',999)]:
                bars=[{'date':(self.now-dt.timedelta(days=n)).date().isoformat(),'close':close+i*10} for i,n in enumerate((3,1))]
                db.execute('INSERT INTO series VALUES (?,?,?)',(ticker,json.dumps({'ticker':ticker,'bars':bars,'fetched_at':self.now.isoformat()}),1))
        r=self.read('prices');self.assertAlmostEqual(r['change_percent'],10);self.assertEqual(len(r['bars']),2)
    def test_bad_bounds_and_owner_rejected(self):
        for kw in ({'days':'0'},{'days':'1.5'},{'limit':'101'},{'end':'2099-01-01T00:00:00Z'},{'end':'2026-01-01'},{'owner':'someone'}):
            with self.assertRaises(ValueError):self.read('news',**kw)
    def test_l1_reads_exact_citations_without_new_model_calls(self):
        plan=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':[self.a]})
        self.service.start({'plan_id':plan['plan_id']});store=self.service.store('NASDAQ:TSLA');self.service.process(store)
        with store.connection() as db:taxonomy(db)
        before=store.path.read_bytes()
        r=self.read('l1');self.assertTrue(r['opinions']);self.assertTrue(r['opinions'][0]['evidence'][0]['url'])
        self.assertEqual(before,store.path.read_bytes())
    def test_l2_only_local_owner_and_exact_saved_snapshot(self):
        store=self.service.store('NASDAQ:TSLA')
        with store.connection() as db:
            snapshot=put(db,'snapshot',{'lens':{'instrument':'NASDAQ:TSLA','query':'demand'},'opinions':[]})
            run=put(db,'run',{'snapshot':snapshot,'result':{'claims':[]}})
            secret=put(db,'run',{'snapshot':snapshot,'result':{'claims':[]}},owner='other',ident='other-run')
        r=self.read('l2');self.assertEqual([x['id'] for x in r['items']],[run])
        self.assertEqual(self.read('l2',id=run)['bundle']['lens']['query'],'demand')
        with self.assertRaises(ValueError):self.read('l2',id=secret)
    def test_missing_taxonomy_is_not_initialized_by_read(self):
        store=self.service.store('NASDAQ:TSLA')
        with store.connection() as db:db.execute("DELETE FROM research_objects WHERE kind='taxonomy'")
        self.assertEqual(self.read('l1')['status'],'unavailable')
        with store.connection() as db:self.assertEqual(db.execute("SELECT count(*) FROM research_objects WHERE kind='taxonomy'").fetchone()[0],0)

    def test_http_access_and_openapi_are_consistent(self):
        from types import SimpleNamespace
        from news_atlas.openapi import specification
        responses=[]
        h=SimpleNamespace(path='/api/context/news?instrument=NASDAQ%3ATSLA&days=7',command='GET',client_address=('127.0.0.1',1),store=self.repo,headers={'Host':'127.0.0.1:8765'},json_response=lambda code,data:responses.append((code,data)))
        handle(h);self.assertEqual(responses[-1][0],200);self.assertEqual(responses[-1][1]['total'],2)
        h.headers['Sec-Fetch-Site']='cross-site';handle(h);self.assertEqual(responses[-1][0],403)
        del h.headers['Sec-Fetch-Site'];h.path+='&days=30';handle(h);self.assertEqual(responses[-1][0],400)
        self.assertIn('/api/context/l1',specification()['paths'])
