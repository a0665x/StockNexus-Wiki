"""Stock-bound documents through import, preview, scheduler, publish and historical reads."""
import io
import json
from urllib.parse import urlsplit,parse_qs
from news_atlas import documents
from news_atlas.wiki.document_evidence import PART_SIZE
from test_l1_opinion_bdd import L1Scenario
from test_server import row
from test_wiki import proposal


class DocumentScenarios(L1Scenario):
    def upload(self, records, stock=None, source='interviews', preview=False):
        return documents.import_stream(self.service.data_root,'research',source,
            io.StringIO('\n'.join(map(json.dumps,records))),preview,stock)

    def plan(self,**changes):
        return self.service.plan(dict(instrument=self.store.instrument,scope='global',model='fixture',
            date_range={'start':'2026-11-01','end':'2026-11-24'},**changes))

    def run_plan(self,plan,continuous=False):
        job=self.service.start({'plan_id':plan['plan_id'],'continuous':continuous})
        if job['job_id']:
            self.service.process(self.store)
            done=self.store.jobs()[0]
            self.assertEqual(done['status'],'completed',done['error'])
        return job

    def test_new_interview_revises_prior_opinion_with_zero_news_and_pinned_quote(self):
        def thesis(a,_):
            p=proposal(a)
            p['nodes'][0].update(kind='Thesis',title='Cooling limits rack deliveries',scope='NVDA racks')
            return p
        self.respond=thesis
        self.ingest(row(title='Cooling limits NVDA rack deliveries',day='2026-10-10'))
        parent=next(n for n in self.store.graph()['nodes'] if n['kind']=='Thesis')
        report=dict(id='cooling',kind='section',title='Cooling and rack deliveries',locator={'page':12},
                    published_at='2024-10-01',text='The supplier qualified the second cooling line.')
        self.upload([report],self.store.instrument,preview=True)
        self.assertNotIn('documents',self.plan())
        self.upload([report])
        self.assertNotIn('documents',self.plan())
        documents.bind_source(self.service.data_root,'research','interviews',self.store.instrument)
        def revise(a,context):
            self.assertIn(parent['id'],[n['id'] for n in context])
            p=proposal(a)
            cite={'revision_id':a['revision_id'],'field':'summary','quote':'qualified the second cooling line'}
            p['nodes'][0].update(kind='Thesis',title='Second line eases the cooling constraint',scope='NVDA racks',
                citations=[cite],opinion_metadata=dict(claim_type='hypothesis',horizon='current quarter',conditions=[],
                change_reason='Supplier qualified the second line.'),lineage=dict(action='update',compared_id=parent['id']))
            p['relations']=[dict(source='n1',target=parent['id'],type='UPDATES',rationale='Second line qualified.',citations=[cite])]
            return p
        self.respond=revise
        plan=self.plan()
        self.assertEqual((plan['selected'],plan['pending'],plan['documents']['pending']),(0,0,1))
        self.run_plan(plan)
        stats=self.plan()['documents']
        self.assertEqual((stats['done'],stats['pending'],stats['passages'][0]['outcomes']),(1,0,['updated']))
        self.upload([report],self.store.instrument)
        self.assertEqual(self.run_plan(self.plan())['status'],'noop')
        self.assertEqual(len(self.calls),2)
        self.upload([{**report,'text':'Management withdrew the qualification.'}])
        self.assertEqual(self.plan()['documents']['pending'],1)
        graph=self.store.graph()
        updated=next(n for n in graph['nodes'] if n.get('lineage',{}).get('action')=='update')
        cite=updated['citations'][0]
        source=next(n for n in graph['nodes'] if n['id']==cite['article_revision_id'])
        params={k:v[0] for k,v in parse_qs(urlsplit(source['url']).query).items()}
        saved=documents.query(self.service.data_root,params['collection'],params['source'],params['id'],params['revision'])
        self.assertEqual((saved['revision'],saved['record']['locator']['page']),(1,12))
        self.assertEqual(saved['record']['text'][cite['start']:cite['end']],cite['quote'])
        def check_revision(a,candidates):
            self.assertEqual(candidates[0]['id'],updated['id'])
            return {'nodes':[],'relations':[]}
        self.respond=check_revision
        self.run_plan(self.plan())
        self.assertEqual(self.plan()['documents']['passages'][0]['outcomes'],['unchanged'])

    def test_parallel_root_freezes_versions_and_reimports_only_changed_sections(self):
        base=dict(kind='section',title='Interview',text='undated interview notes')
        docs=[dict(base,id='one'),dict(base,id='two',text='🟠'*(PART_SIZE+30))]
        self.upload(docs,self.store.instrument)
        self.respond=lambda a,c:{'nodes':[],'relations':[]}
        plan=self.plan(strategy='root',workers=3)
        self.assertEqual((plan['documents']['pending'],plan['trees']['total']),(2,0))
        report=self.upload([docs[0],dict(docs[1],text='new version')])
        self.assertEqual((report['updated'],report['unchanged']),(1,1))
        self.run_plan(plan)
        self.assertTrue(all(a['document']['revision']==1 for a in self.calls))
        self.assertEqual(len(self.calls),3)
        self.service.refresh(self.store)
        self.assertFalse(any(j['status']=='queued' for j in self.store.jobs()))
        updated=self.plan(strategy='root',workers=3)
        self.assertEqual((updated['documents']['pending'],updated['documents']['done']),(1,1))
        self.run_plan(updated,continuous=True)
        self.upload([dict(base,id='three')])
        self.service.refresh(self.store)
        self.service.process(self.store)
        self.assertEqual(self.calls[-1]['document']['id'],'three')

    def test_claim_uses_only_pinned_bound_original_and_never_leaks_to_another_stock(self):
        original=dict(id='s',kind='section',title='Interview',text='Initial source passage')
        self.upload([original],self.store.instrument)
        self.upload([{**original,'text':'Corrected source passage'}])
        claim=dict(id='c',kind='claim',layer='L1',title='My conclusion',text='Unverified inference',
                   links=[dict(type='cites',id='s',source='interviews',revision=1)])
        self.upload([claim],self.store.instrument,'analysis')
        self.upload([{**original,'text':'Private work'}],None,'private')
        self.assertNotIn('documents',self.service.plan({'instrument':'NASDAQ:AMD','model':'fixture','scope':'global'}))
        self.assertNotIn('documents',self.service.plan({'instrument':self.store.instrument,'model':'fixture','scope':'focus'}))
        self.respond=lambda a,c:{'nodes':[],'relations':[]}
        self.run_plan(self.plan())
        self.assertEqual({a['summary'] for a in self.calls},{'Initial source passage','Corrected source passage'})

    def test_web_binding_of_an_existing_source_reaches_global_range_preview(self):
        import os
        import threading
        from unittest.mock import patch
        from urllib.request import Request,urlopen
        from urllib.error import HTTPError
        from urllib.parse import urlencode
        from server import Handler,ThreadingHTTPServer

        report=dict(id='call',kind='section',title='Supplier interview',text='The second line is operational.')
        self.upload([report])
        with ThreadingHTTPServer(('127.0.0.1',0),Handler) as http:
            base=f'http://127.0.0.1:{http.server_port}'
            http.store=self.service.news
            http.wiki=self.service
            thread=threading.Thread(target=http.serve_forever,daemon=True)
            thread.start()
            try:
                with patch.dict(os.environ,{'NEWS_ATLAS_WIKI_ORIGINS':base}):
                    binding='/api/documents/bind?'+urlencode(dict(collection='research',source='interviews',instrument=self.store.instrument))
                    def post(path,body,origin=base):
                        request=Request(base+path,data=json.dumps(body).encode(),
                                        headers={'Origin':origin,'Content-Type':'application/json'})
                        with urlopen(request,timeout=4) as reply:
                            return json.load(reply)
                    with self.assertRaises(HTTPError) as rejected:
                        post(binding,{},'https://elsewhere.example')
                    self.assertEqual(rejected.exception.code,403)
                    for _ in range(2):
                        self.assertEqual(post(binding,{})['instrument'],self.store.instrument)
                    with urlopen(base+'/api/documents',timeout=4) as response:
                        self.assertEqual(json.load(response)['collections'][0]['bindings'],{'interviews':[self.store.instrument]})
                    settings=dict(scope='global',instrument=self.store.instrument,strategy='root',workers=5,
                                  graph_universe={'ticker':'NVDA','articles':[]},
                                  graph_selection={'ticker':'NVDA','trees':[]})
                    counts=post('/api/wiki/range-counts',settings)
                    self.assertEqual((counts['trees']['total'],counts['documents']['pending']),(0,1))
                    self.assertEqual(counts['documents']['sources'][0]['records'],1)
                    self.assertEqual(self.store.jobs(),[])
            finally:
                http.shutdown()
                thread.join()
