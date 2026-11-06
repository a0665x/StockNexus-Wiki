"""Ticker partitioning, migration, API routing and cross-category merge tests."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from news_atlas.storage import Store
from news_atlas.graph_storage import GraphRepository
from news_atlas.search import query_key,normalize_request
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import WikiStore
from scripts.merge_data import run
from test_server import row
import test_server
from server import search_events,graph_payload
from news_atlas import api,price_lens

class GraphStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'data';self.old=Store(self.root/'news-atlas.sqlite3')
    def snapshot(self,store,ticker,article):
        return store.save_snapshot({'view':{'sources':['google'],'separate':False},'source_graphs':{'google':{'articles':[article],'relations':[]}},'search':{'ticker':ticker,'query':'shared','rss_region':'US'}})
    def test_migration_preserves_union_and_explicit_query_associations(self):
        a=row('massive',suffix='a');b=row('massive',suffix='b');rss=row('google',suffix='g');unassigned=row('google',suffix='u')
        self.old.save('massive',query_key('massive','AAPL'),[a],[])
        self.old.save('massive',query_key('massive','TSLA'),[b],[])
        self.old.save('google',query_key('google','shared','US'),[rss],[])
        self.old.save('google',query_key('google','unknown','US'),[unassigned],[])
        saved=self.snapshot(self.old,'AAPL',rss)
        repo=GraphRepository(self.old.path)
        self.assertFalse(self.old.path.exists());self.assertEqual(repo.stats()['articles'],4)
        self.assertEqual(repo.stats()['snapshots'],1)
        self.assertEqual(repo.load_snapshot(saved['id'])['search']['ticker'],'AAPL')
        self.assertEqual(repo.for_ticker('AAPL').stats()['articles'],2)
        self.assertEqual(repo.for_ticker('TSLA').stats()['articles'],1)
        self.assertEqual(repo.for_ticker('').stats()['articles'],1)
        self.assertTrue(list((self.root/'private').glob('graph-layout-backup-*')))
        self.assertEqual(GraphRepository(self.old.path).stats(),repo.stats())
    def test_wiki_subscriptions_read_matching_graph_not_unassigned(self):
        wiki=WikiStore(self.root/'llm_wiki','NASDAQ:GOOGL')
        q=query_key('google','Google','US')
        wiki.configure({'enabled':False,'model':'fixture','subscriptions':[{'provider':'google','query_key':q,'term':'Google'}],'revision_ids':[]})
        self.old.save('google',q,[row('google',suffix='googl')],[])
        repo=GraphRepository(self.old.path);service=WikiService(repo,start_worker=False)
        self.assertEqual(service.coverage(wiki)['scope_total'],1)
        self.assertEqual(service.coverage(wiki)['storage'],'llm_wiki/GOOGL/wiki.sqlite3')
        self.assertEqual(repo.for_ticker('').stats()['articles'],0)
    def test_parallel_searches_use_distinct_stores(self):
        repo=GraphRepository(self.old.path)
        for symbol in ('AAPL','TSLA'):
            repo.for_ticker(symbol).save('google',query_key('google','same','US'),[row('google',suffix=symbol)],[])
        def search(symbol):
            req=normalize_request({'query':'same','ticker':symbol,'sources':['google'],'rss_region':'US','start':'2026-01-01','end':'2026-01-03','defer_relations':True})
            return next(search_events(req,'',repo))['graph']['articles'][0]['id']
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results=list(pool.map(search,['AAPL','TSLA']))
        self.assertEqual(results,[row('google',suffix=s)['id'] for s in ('AAPL','TSLA')])
        self.assertEqual(repo.for_ticker('').stats()['articles'],0)
    def test_graph_merge_single_all_and_category_mismatch(self):
        source=GraphRepository(self.old.path);source.for_ticker('AAPL').save('massive','q',[row()],[]);source.for_ticker('TSLA').save('massive','q',[row(suffix='t')],[])
        target=self.root.parent/'target';GraphRepository(target/'news-atlas.sqlite3')
        run(self.root/'graph/AAPL',target)
        self.assertTrue((target/'graph/AAPL/news-atlas.sqlite3').exists());self.assertFalse((target/'graph/TSLA').exists())
        run(self.root/'graph',target/'graph');run(self.root/'graph/AAPL',target/'graph/AAPL')
        self.assertTrue((target/'graph/TSLA/news-atlas.sqlite3').exists())
        with self.assertRaisesRegex(ValueError,'categories differ'):run(self.root/'graph',target/'llm_wiki')
        with self.assertRaises(ValueError):run(self.root/'graph/AAPL',target/'graph/TSLA')
    def test_old_price_key_can_be_reused_without_network(self):
        repo=GraphRepository(self.old.path);store=repo.for_ticker('AAPL')
        body={'ticker':'AAPL','articles':[{'id':'a','published_at':'2026-10-29T12:00:00Z'}]}
        now=dt.datetime(2026,11,3,12,tzinfo=dt.timezone.utc)
        raw={'status':'OK','adjusted':True,'results':[]}
        with patch.object(price_lens,'fetch',return_value=json.dumps(raw).encode()):price_lens.load(repo.for_ticker(''),body,'test',now=now)
        with patch.object(price_lens,'fetch',side_effect=AssertionError('No network')):
            result=price_lens.load(store,body,'',now=now)
        self.assertTrue(result['cached'])
    def test_all_snapshots_and_article_lookup_survive_partition(self):
        repo=GraphRepository(self.old.path)
        for symbol in ('AAPL','TSLA'):
            a=row('google',suffix=symbol);repo.for_ticker(symbol).save('google','q',[a],[]);self.snapshot(repo,symbol,a)
            self.assertEqual(len(repo.article_rows(a['id'])),1)
        self.assertEqual(len(repo.list_snapshots()),2)
        self.assertEqual(repo.path.parent,self.root)
        self.assertFalse(repo.path.exists())
    def test_http_routes_cache_build_snapshot_and_article_reads(self):
        self.store=GraphRepository(self.old.path)
        stock=self.store.for_ticker('AAPL');a=row('massive',suffix='aapl')
        stock.save('massive',query_key('massive','AAPL'),[a],[])
        body={'ticker':'AAPL','sources':['massive'],'start':'2026-01-01','end':'2026-01-03'}
        head,data=test_server.HTTPTests.request(self,'POST','/api/cache/graph',body)
        self.assertIn(b'200',head);self.assertEqual(json.loads(data)['graph']['articles'][0]['id'],a['id'])
        with patch.dict('os.environ',{'NEWS_ATLAS_CACHE_ONLY':'1'}):
            head,data=test_server.HTTPTests.request(self,'POST','/api/search/result',body)
        self.assertIn(b'200',head);self.assertEqual(json.loads(data)['graph']['articles'][0]['id'],a['id'])
        self.assertTrue(Path(str(stock.path)+'.graphs.sqlite3').exists())
        self.assertFalse(Path(str(self.store.path)+'.graphs.sqlite3').exists())
        head,data=test_server.HTTPTests.request(self,'GET','/api/articles/'+a['id'])
        self.assertIn(b'200',head);self.assertEqual(len(json.loads(data)['articles']),1)
        head,data=test_server.HTTPTests.request(self,'GET','/api/status')
        self.assertIn(b'200',head);self.assertEqual(json.loads(data)['db']['articles'],1)

    def test_explicit_search_reuses_unassigned_query_without_moving_others(self):
        self.old.save('google',query_key('google','Google','US'),[row('google')],[])
        repo=GraphRepository(self.old.path)
        req={'ticker':'GOOGL','query':'Google','rss_region':'US','sources':['google']}
        self.assertEqual(repo.for_query(req).stats()['articles'],1)
        self.assertEqual(repo.for_query(req).stats()['articles'],1)
        self.assertEqual(repo.for_ticker('AAPL').stats()['articles'],0)
        self.assertEqual(repo.stats()['articles'],1)

    def test_explicit_ticker_validation_prevents_path_escape(self):
        repo=GraphRepository(self.old.path)
        for bad in ('../../other','/tmp','A/B'):
            with self.assertRaises(ValueError):repo.for_ticker(bad)

if __name__=='__main__':unittest.main()
