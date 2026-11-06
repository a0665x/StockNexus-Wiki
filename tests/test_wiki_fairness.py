"""BDD: each queued stock advances before a larger stock drains its backlog."""
import tempfile
import unittest
from pathlib import Path
from news_atlas.storage import Store
from news_atlas.wiki.compiler import WikiService
from test_server import row
from test_wiki import proposal

class FairnessTests(unittest.TestCase):
    def test_each_stock_advances_and_completed_evidence_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            def runner(store,job,a,context):
                calls.append((store.instrument,a['revision_id']))
                return {'proposal':proposal(a),'usage':{}}
            service=WikiService(Store(Path(tmp)/'news.sqlite3'),runner=runner,start_worker=False)
            for symbol in ['AMD','NVDA']:
                p=service.plan({'instrument':'NASDAQ:'+symbol,'model':'fixture','articles':[row(suffix=symbol+str(i)) for i in range(3)],'evidence_size':1})
                service.start({'plan_id':p['plan_id']})
            service.tick(max_groups=1)
            self.assertEqual([s for s,_ in calls],['NASDAQ:AMD','NASDAQ:NVDA'])
            for symbol in ['AMD','NVDA']:
                j=service.store('NASDAQ:'+symbol).jobs()[0]
                self.assertEqual(j['status'],'queued');self.assertEqual(j['done'],1)
            for _ in range(3):service.tick(max_groups=1)
            self.assertEqual(len(calls),6);self.assertEqual(len(set(calls)),6)
            for symbol in ['AMD','NVDA']:self.assertEqual(service.store('NASDAQ:'+symbol).jobs()[0]['status'],'completed')

    def test_review_resumes_without_calling_already_reviewed_articles(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            def runner(store,job,a,context):
                calls.append(a['revision_id'])
                return {'proposal':{'nodes':[],'relations':[]} if job['payload'].get('operation')=='review' else proposal(a),'usage':{}}
            service=WikiService(Store(Path(tmp)/'news.sqlite3'),runner=runner,start_worker=False)
            body={'instrument':'NASDAQ:AMD','model':'fixture','articles':[row(suffix=str(i)) for i in range(3)],'evidence_size':1}
            p=service.plan(body);service.start({'plan_id':p['plan_id']});service.tick()
            calls.clear();p=service.plan({**body,'operation':'review'});service.start({'plan_id':p['plan_id']})
            for _ in range(4):service.tick(max_groups=1)
            self.assertEqual(len(calls),3);self.assertEqual(len(set(calls)),3)
            self.assertEqual(service.store('NASDAQ:AMD').jobs()[0]['status'],'completed')
