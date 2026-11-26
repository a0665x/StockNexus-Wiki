import io
import json
import types
import unittest
from unittest.mock import patch
import test_wiki
from news_atlas.wiki.http import handle

class WikiHTTPTests(unittest.TestCase):
    setUp=test_wiki.WikiTests.setUp
    def request(self,path,body=None,origin='http://localhost:8765'):
        raw=json.dumps(body).encode();result=[]
        h=types.SimpleNamespace(server=types.SimpleNamespace(wiki=self.service),store=self.news,path='/api/wiki/'+path,command='GET' if body is None else 'POST',client_address=('127.0.0.1',1),headers={'Host':'localhost:8765','Origin':origin,'Content-Type':'application/json','Content-Length':str(len(raw))},rfile=io.BytesIO(raw),json_response=lambda code,data:result.extend([code,data]))
        handle(h);return result
    def test_write_boundary_and_unknown_read_does_not_create_database(self):
        self.assertEqual(self.request('plan',{},'https://evil.example')[0],403)
        count=len(list(self.service.root.glob('*/wiki.sqlite3')))
        self.assertEqual(self.request('graph?instrument=NASDAQ:AAPL')[0],400)
        self.assertEqual(len(list(self.service.root.glob('*/wiki.sqlite3'))),count)
    def test_plan_job_graph_article_markdown_and_cancel(self):
        from test_server import row
        code,p=self.request('plan',{'instrument':'NASDAQ:TSLA','model':'fixture','articles':[row()]})
        self.assertEqual(code,200)
        code,j=self.request('jobs',{'plan_id':p['plan_id']});self.assertEqual(code,202)
        self.service.tick()
        code,g=self.request('graph?instrument=NASDAQ:TSLA');self.assertEqual(code,200);self.assertEqual(g['version'],1)
        revision=next(n['id'] for n in g['nodes'] if n['kind']=='ArticleRevision')
        self.assertEqual(self.request('article?instrument=NASDAQ:TSLA&id='+revision)[1]['title'],row()['title'])
        self.assertIn('NASDAQ:TSLA',self.request('markdown?instrument=NASDAQ:TSLA&version=1')[1]['markdown'])
        self.assertEqual(self.request('configure',{'instrument':'NASDAQ:TSLA','enabled':False})[0],200)
        self.assertEqual(self.request('cancel',{'instrument':'NASDAQ:TSLA','job_id':j['job_id']})[0],200)

    def test_counts_use_selected_interval_without_enqueuing_or_allocating_a_plan(self):
        from test_server import row
        articles=[row(day='2026-11-01',suffix='a'),row(day='2026-11-04',suffix='b')]
        _,plan=self.request('plan',{'instrument':self.store.instrument,'model':'fixture','articles':articles[:1]})
        self.request('jobs',{'plan_id':plan['plan_id']});self.service.tick()
        plans=list(self.service.plans)
        for end,total,pending in [('2026-11-01',1,0),('2026-11-04',2,1)]:
            code,counts=self.request('range-counts',{'instrument':self.store.instrument,'scope':'loaded','articles':articles,
                                                     'date_range':{'start':'2026-11-01','end':end}})
            self.assertEqual((code,counts),(200,{'selected':total,'reused':1,'pending':pending}))
        self.assertEqual(list(self.service.plans),plans)
        self.assertEqual(len(self.store.jobs()),1)

    def test_node_refreshes_current_market_without_rewriting_generation_evidence(self):
        from test_server import row
        from news_atlas.wiki.evidence import cached_market
        import sqlite3
        _,plan=self.request('plan',{'instrument':'NASDAQ:TSLA','model':'fixture','articles':[row(day='2026-11-02')], 'price_horizon':3})
        self.request('jobs',{'plan_id':plan['plan_id']});self.service.tick()
        node=next(n for n in self.store.graph()['nodes'] if n['kind']=='Claim')
        frozen=[{'ticker':'TSLA','horizon':3,'mean_return':None,'as_of':'2026-11-04'}]
        node['market_evidence']=frozen
        with self.store.connection() as db:db.execute('UPDATE nodes SET payload=? WHERE id=?',(json.dumps(node),node['id']))
        bars=[{'date':f'2026-11-{day:02d}','close':100+day} for day in range(2,6)]
        with sqlite3.connect(str(self.news.path)+'.prices.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS series(key TEXT,payload TEXT,fetched REAL)')
            db.execute('INSERT INTO series VALUES (?,?,?)',('new',json.dumps({'ticker':'TSLA','bars':bars,'fetched_at':'2026-11-06T01:00:00Z'}),1))
        url='node?instrument=NASDAQ:TSLA&id='+node['id']
        code,seven=self.request(url+'&price_horizon=7')
        self.assertEqual(code,200)
        self.assertEqual(seven['market_evidence'],frozen)
        obs=seven['current_market'][0]
        self.assertEqual((obs['horizon'],obs['available_sessions'],obs['required_sessions']),(7,3,7))
        self.assertIsNone(obs['mean_return']);self.assertEqual(obs['as_of'],'2026-11-05')
        three=self.request(url+'&price_horizon=3')[1]['current_market'][0]
        self.assertIsNotNone(three['mean_return'])
        with self.store.connection() as db:stored=json.loads(db.execute('SELECT payload FROM nodes WHERE id=?',(node['id'],)).fetchone()[0])
        self.assertEqual(stored['market_evidence'],frozen);self.assertNotIn('current_market',stored)
        self.assertEqual(self.request(url+'&price_horizon=2')[0],400)
