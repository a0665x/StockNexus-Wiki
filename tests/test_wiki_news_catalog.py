import tempfile,unittest
from pathlib import Path
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from test_server import row

class WikiNewsCatalogTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.repo=GraphRepository(Path(self.tmp.name)/'data/news-atlas.sqlite3')
  self.service=WikiService(self.repo,start_worker=False)
 def add(self,ticker,ident=None):
  s=self.repo.for_query({'ticker':ticker,'instrument':ident,'sources':[]}) if ident else self.repo.for_ticker(ticker)
  a=row('google',suffix=ticker);s.save('google','query',[a],[]);return a
 def test_only_nonempty_identified_news_databases_are_choices(self):
  self.add('AAPL','NASDAQ:AAPL');self.add('UNKNOWN');self.repo.for_ticker('EMPTY');self.add('')
  self.assertEqual(self.service.news_catalog(),[{'instrument':'NASDAQ:AAPL','ticker':'AAPL','articles':1}])
 def test_legacy_news_db_reuses_existing_wiki_identity(self):
  self.add('RDW');self.service.store('NYSE:RDW')
  self.assertEqual(self.service.news_catalog()[0]['instrument'],'NYSE:RDW')
 def test_new_wiki_reads_selected_db_not_other_news_graph(self):
  apple=self.add('AAPL','NASDAQ:AAPL');self.add('TSLA','NASDAQ:TSLA')
  plan=self.service.plan({'instrument':'NASDAQ:AAPL','news_db':True,'model':'fixture','scope':'global','strategy':'lexical','articles':[row('google',suffix='foreign')],'search':{'ticker':'TSLA'}})
  self.assertEqual(plan['selected'],1)
  self.assertEqual(self.service.plans[plan['plan_id']]['rows'][0]['id'],apple['id'])
 def test_empty_and_unidentified_db_cannot_start(self):
  with self.assertRaisesRegex(ValueError,'新聞 DB'):
   self.service.plan({'instrument':'NASDAQ:EMPTY','news_db':True,'model':'fixture','scope':'global'})
 def test_snapshot_identity_is_available_without_an_existing_wiki(self):
  a=self.add('TSLA');news=self.repo.for_ticker('TSLA')
  news.save_snapshot({'name':'test','search':{'ticker':'TSLA','instrument':'NASDAQ:TSLA'},'view':{'sources':['google'],'separate':False},'source_graphs':{'google':{'articles':[a],'relations':[]}}})
  self.assertEqual(self.service.news_catalog()[0]['instrument'],'NASDAQ:TSLA')
 def test_invalid_identity_does_not_break_other_database_choices(self):
  self.add('AAPL','NASDAQ:AAPL');s=self.repo.for_ticker('AAPL')
  with s.connection() as db:db.execute("UPDATE graph_metadata SET value='invalid' WHERE key='instrument'")
  self.assertEqual(self.service.news_catalog(),[])
 def test_database_selection_obeys_date_window(self):
  a=self.add('AAPL','NASDAQ:AAPL')
  p=self.service.plan({'instrument':'NASDAQ:AAPL','news_db':True,'model':'fixture','scope':'global','strategy':'lexical','date_range':{'start':'2020-01-01','end':'2020-01-02'}})
  self.assertEqual(p['selected'],0)
 def test_idle_model_change_preserves_scope_without_replanning(self):
  store=self.service.store('NASDAQ:AAPL');cfg=store.config()
  cfg.update(model='old',reasoning_effort='high',date_range={'start':'2025-11-14','end':'2026-11-13'},revision_ids=['kept'])
  store.configure(cfg)
  self.service.plan=lambda *_:self.fail('model-only configuration must not rebuild evidence')
  result=self.service.configure({'instrument':'NASDAQ:AAPL','enabled':False,'model':'gpt-6.1-sol','reasoning_effort':'medium'})
  self.assertEqual(result['reasoning_effort'],'medium');self.assertEqual(result['revision_ids'],['kept']);self.assertEqual(result['date_range'],cfg['date_range'])
  self.assertFalse(store.jobs())
 def test_active_job_model_change_requires_explicit_stop(self):
  store=self.service.store('NASDAQ:AAPL')
  from news_atlas.wiki.store import capture
  a=capture(row());store.ingest([a]);store.enqueue('fixture',revision_ids=[a['revision_id']])
  with self.assertRaisesRegex(ValueError,'停止'):
   self.service.configure({'instrument':'NASDAQ:AAPL','enabled':False,'reasoning_effort':'medium'})
if __name__=='__main__':unittest.main()
