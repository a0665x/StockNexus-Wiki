"""Workbench regression tests: real SQLite writes, deterministic model fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from news_atlas.storage import Store
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import capture, validate_proposal
from news_atlas.wiki.workbench import batches, usage_summary
from test_server import row
from test_wiki import proposal

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.service=WikiService(Store(Path(self.tmp.name)/'news.sqlite3'),start_worker=False)
        self.store=self.service.store('NASDAQ:TSLA');self.calls=[]
    def run_rows(self,rows,**settings):
        plan=self.service.plan(dict(instrument='NASDAQ:TSLA',model='fixture',articles=rows,**settings))
        self.service.start({'plan_id':plan['plan_id']});self.service.tick();return self.store.graph()
    def fixture(self,store,job,a,context):
        self.calls.append((a,context,job['payload']))
        p=proposal(a);p['nodes'][0]['kind']='Thesis'
        p['nodes'][0]['translations']={'en':{'title':'Earnings perspective','summary':'Interpretation, not a forecast.','rationale':'Operating evidence'},'zh-Hant':{'title':'盈餘觀點','summary':'觀點，並非預測。','rationale':'營運線索'}}
        return {'proposal':p,'usage':{'input_tokens':120,'output_tokens':30}}
    def test_batch_publishes_every_article_and_reuses_completed(self):
        self.service.runner=self.fixture
        rows=[row(suffix=str(i)) for i in range(5)]
        g=self.run_rows(rows,evidence_size=3,strategy='chronological',reasoning_effort='high')
        self.assertEqual(len(self.calls),2);self.assertEqual(g['version'],2)
        self.assertEqual(g['jobs'][0]['done'],5)
        self.assertEqual(len([n for n in g['nodes'] if n['kind']=='ArticleRevision']),5)
        self.assertEqual(self.service.coverage(self.store)['scope_done'],5)
        self.assertEqual(self.calls[0][2]['reasoning_effort'],'high')
        self.run_rows(rows,evidence_size=3);self.assertEqual(len(self.calls),2)
    def test_quotes_resolve_against_each_evidence_revision(self):
        a=capture(row(title='Tesla first result'));b=capture(row(title='Tesla second result',suffix='second'))
        p=proposal(b);nodes,edges=validate_proposal({**a,'_evidence':[a,b]},p,[])
        self.assertEqual(nodes[0]['citations'][0]['article_revision_id'],b['revision_id'])
        self.assertEqual(edges[0]['source'],b['revision_id'])
        with self.assertRaises(ValueError):validate_proposal(a,p,[])
    def test_bilingual_versions_history_and_time_filter(self):
        def run(store,job,a,context):
            p=self.fixture(store,job,a,context)['proposal'];n=p['nodes'][0]
            n['summary']='Update '+str(len(self.calls));n['title']='View '+str(len(self.calls))
            old=next((n for n in context if n['kind']=='Thesis'),None)
            if old:p['relations']=[dict(source='n1',target=old['id'],type='UPDATES',rationale='New evidence changes the premise',citations=n['citations'])]
            return {'proposal':p,'usage':{'input_tokens':120,'output_tokens':30}}
        self.service.runner=run
        for i in range(5):self.run_rows([row(title='Tesla earnings '+str(i),day='2026-01-0'+str(i+1),suffix=str(i))])
        g=self.store.graph();history=next(v for v in g['histories'].values() if v['revision_count']==5)
        self.assertEqual(history['original']['version'],1);self.assertEqual(len(history['recent_batches']),3)
        self.assertEqual(self.store.graph(version=1)['histories'][history['original']['id']]['revision_count'],1)
        self.assertEqual(g['changes'][0]['updates'],1)
        self.assertEqual(g['timeline'][0]['date'],'2026-01-01')
        filtered=self.store.graph(version=3,start='2026-01-01',end='2026-01-01',limit=1)
        self.assertEqual(filtered['total_nodes'],2);self.assertEqual(len(filtered['nodes']),1)
        self.assertIn('English' if False else 'Earnings perspective',self.store.markdown())
        self.assertIn('summary',self.calls[-1][1][0])
    def test_usage_interval_counts_cross_date_batch_once(self):
        self.service.runner=self.fixture
        self.run_rows([row(day='2026-01-01'),row(day='2026-01-02',suffix='b')],evidence_size=2)
        usage=usage_summary(self.store,'2026-01-01','2026-01-02')
        self.assertEqual(usage['reported']['input_tokens'],120);self.assertEqual(usage['calls'],1)
        self.assertEqual(usage_summary(self.store,'2025-01-01','2025-01-02')['calls'],0)
    def test_review_rejects_unrelated_new_nodes(self):
        self.service.runner=self.fixture;self.run_rows([row()]);before=self.store.graph()['version']
        self.run_rows([row()],operation='review')
        self.assertEqual(self.store.jobs()[0]['status'],'failed')
        self.assertEqual(self.store.graph()['version'],before)
    def test_root_groups_use_actual_edges_and_fusion_prefers_other_sources(self):
        rows=[capture(row(title='Tesla earnings',suffix=str(i),day='2026-01-0'+str(i+1))) for i in range(3)]
        rows[2]['provider']='google'
        group=list(batches([rows[0],rows[2]],dict(evidence_size=1,strategy='root',graph_selection={'trees':[{'articles':[{'id':a['id'],'provider':a['provider']} for a in (rows[0],rows[2])]}]})))[0]
        self.assertEqual({a['id'] for a in group},{rows[0]['id'],rows[2]['id']})
        group=list(batches(rows,dict(evidence_size=2,strategy='fusion')))[0]
        self.assertEqual(len({a['provider'] for a in group}),2)
    def test_cancelled_batch_does_not_publish(self):
        def run(store,job,a,context):
            store.cancel(job['id']);return self.fixture(store,job,a,context)
        self.service.runner=run
        g=self.run_rows([row(),row(suffix='b')],evidence_size=2)
        self.assertEqual(g['version'],0);self.assertEqual(g['nodes'],[])
    def test_merge_keeps_translations_lineage_and_receipts(self):
        import importlib.util,sqlite3
        spec=importlib.util.spec_from_file_location('merge_data',Path(__file__).parents[1]/'scripts/merge_data.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.service.runner=self.fixture;g=self.run_rows([row()])
        # Use actual CLI into a fresh data destination, then repeat (idempotent union).
        import subprocess,sys
        target=Path(self.tmp.name)/'other'/'data'
        command=[sys.executable,str(Path(__file__).parents[1]/'scripts/merge_data.py'),'--from',str(self.store.folder),'--to',str(target)]
        for _ in range(2):
            result=subprocess.run(command,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        with sqlite3.connect(target/'llm_wiki/TSLA/wiki.sqlite3') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM versions').fetchone()[0],1)
            node=json.loads(db.execute("SELECT payload FROM nodes WHERE kind='Thesis'").fetchone()[0]);self.assertIn('en',node['translations'])
            job=json.loads(db.execute('SELECT payload FROM jobs').fetchone()[0]);self.assertEqual(job['receipts'][0]['usage']['input_tokens'],120)

    def test_twenty_article_batch_and_scaled_output_validation(self):
        self.service.runner=self.fixture
        g=self.run_rows([row(title='Tesla earnings '+str(i),suffix=str(i)) for i in range(20)],evidence_size=20)
        self.assertEqual(len(self.calls),1);self.assertEqual(g['jobs'][0]['done'],20)
        article=self.calls[0][0];p=proposal(article)
        p['nodes']=[dict(p['nodes'][0],key='n'+str(i+1),title='View '+str(i)) for i in range(20)]
        self.assertEqual(len(validate_proposal(article,p,[])[0]),20)
        with self.assertRaises(ValueError):validate_proposal(article['_evidence'][0],p,[])

    def test_root_is_exact_clicked_tree_not_whole_stock_or_edge_neighbors(self):
        from news_atlas.graph_storage import GraphRepository
        repo=GraphRepository(Path(self.tmp.name)/'partition'/'news.sqlite3')
        service=WikiService(repo,start_worker=False);service.runner=self.fixture
        rows=[row(p,suffix=str(i)) for i,p in enumerate(['google','yahoo','massive','google'])]
        for a in rows:repo.for_ticker('TSLA').save(a['source']['provider'],'q',[a],[])
        repo.for_ticker('AAPL').save('google','q',[row('google',suffix='foreign')],[])
        selection={'ticker':'TSLA','trees':[{'root_id':rows[0]['id'],'title':'clicked root','articles':[{'id':a['id'],'provider':a['source']['provider']} for a in rows[:3]]}]}
        body=dict(instrument='NASDAQ:TSLA',model='fixture',strategy='root',evidence_size=1,graph_selection=selection,scope='global')
        plan=service.plan(body);self.assertEqual(plan['selected'],3)
        service.start({'plan_id':plan['plan_id']});service.tick()
        self.assertEqual(len(self.calls),1);self.assertEqual(len(self.calls[0][0]['_evidence']),3)
        self.assertEqual(service.coverage(service.store('NASDAQ:TSLA'))['scope_total'],3)
        self.assertEqual(service.plan(body)['pending'],0)
        with self.assertRaises(ValueError):service.plan({**body,'graph_selection':{'ticker':'TSLA','trees':[]}})
        with self.assertRaises(ValueError):service.plan({**body,'instrument':'NASDAQ:AAPL'})

    def test_apply_cancels_running_late_result_then_resumes_without_reextracting(self):
        import threading
        rows=[row(suffix=str(i)) for i in range(12)]
        entered=threading.Event();release=threading.Event();calls=[]
        def run(store,job,a,context):
            calls.append((job['id'],len(a['_evidence'])))
            if len(calls)==2:entered.set();release.wait(5);raise RuntimeError('old cancelled call')
            return self.fixture(store,job,a,context)
        self.service.runner=run
        body=dict(instrument='NASDAQ:TSLA',model='fixture',articles=rows,evidence_size=5)
        p=self.service.plan(body);old=self.service.start({'plan_id':p['plan_id']})['job_id']
        worker=threading.Thread(target=self.service.tick);worker.start();self.assertTrue(entered.wait(5))
        self.service.bridge_request=lambda *args,**kw: {}
        result=self.service.apply({**body,'evidence_size':10})
        self.assertTrue(result['resumed']);release.set();worker.join(5);self.assertFalse(worker.is_alive())
        self.assertTrue(self.store.config()['catch_up'])
        self.service.tick()
        self.assertEqual([n for _,n in calls],[5,5,7])
        self.assertEqual(self.service.coverage(self.store)['scope_done'],12)
        self.assertEqual(next(j['status'] for j in self.store.jobs() if j['id']==old),'cancelled')

    def test_active_apply_switches_lexical_twenty_to_exact_clicked_galaxy(self):
        import threading
        from news_atlas.search import query_key
        rows=[row(suffix=str(i)) for i in range(24)]
        self.service.news.save('massive',query_key('massive','TSLA'),rows,[])
        entered=threading.Event();release=threading.Event();calls=[]
        def run(store,job,a,context):
            calls.append((job['payload']['strategy'],{x['id'] for x in a['_evidence']}))
            if len(calls)==1:entered.set();release.wait(5)
            return self.fixture(store,job,a,context)
        self.service.runner=run
        body=dict(instrument='NASDAQ:TSLA',model='fixture',articles=rows,evidence_size=20)
        plan=self.service.plan(body);old=self.service.start({'plan_id':plan['plan_id']})['job_id']
        worker=threading.Thread(target=self.service.tick);worker.start();self.assertTrue(entered.wait(5))
        picked=rows[4:7]
        selection={'ticker':'TSLA','trees':[{'root_id':picked[0]['id'],'title':'Clicked galaxy','articles':[{'id':a['id'],'provider':'massive'} for a in picked]}]}
        self.service.bridge_request=lambda *a,**k:{}
        result=self.service.apply({**body,'strategy':'root','graph_selection':selection})
        release.set();worker.join(5);self.assertFalse(worker.is_alive());self.assertTrue(result['resumed'])
        self.service.tick()
        self.assertEqual(calls[0][0],'lexical');self.assertEqual(len(calls[0][1]),20)
        self.assertEqual(calls[1:], [('root',{a['id'] for a in picked})])
        self.assertEqual(self.store.config()['strategy'],'root')
        self.assertEqual(self.service.coverage(self.store)['scope_done'],3)
        self.assertEqual(next(j['status'] for j in self.store.jobs() if j['id']==old),'cancelled')
        self.assertEqual(self.store.graph()['version'],1) # late old result never published

    def test_cross_article_index_is_published_with_two_verifiable_endpoints(self):
        import jsonschema
        first=row(title='Tesla earnings production rose',suffix='first')
        second=row(title='Tesla earnings production follow-up',suffix='second')
        self.service.runner=self.fixture;self.run_rows([first])
        def run(store,job,a,context):
            previous=next(n for n in context if n['kind']=='ArticleRevision')
            evidence=next(n for n in a['_related_articles'] if n['revision_id']==previous['id'])
            quotes=[{'revision_id':x['revision_id'],'field':'title','quote':x['title']} for x in [a,evidence]]
            return {'proposal':{'nodes':[],'relations':[{'source':a['revision_id'],'target':previous['id'],'type':'RELATED_TO','rationale':'Follow-up on the same earnings and production event','citations':quotes}]}}
        self.service.runner=run;g=self.run_rows([second])
        edge=next(e for e in g['edges'] if e['relation_type']=='RELATED_TO')
        self.assertEqual(edge['source']['kind'],'ArticleRevision');self.assertEqual(edge['target']['kind'],'ArticleRevision')
        self.assertEqual(len(edge['evidence_refs']),2)
        scoped=self.store.context({**capture(second),'_context_revisions':[capture(second)['revision_id']]})
        self.assertNotIn(capture(first)['revision_id'],{n['id'] for n in scoped})
        schema=json.loads((Path(__file__).parents[1]/'schema/temporal-wiki.relation.schema.json').read_text())
        jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker()).validate(edge)

    def test_apply_invalid_does_not_cancel_and_idle_does_not_spend(self):
        body=dict(instrument='NASDAQ:TSLA',model='fixture',articles=[row()],evidence_size=5)
        self.assertEqual(self.service.apply(body)['status'],'saved');self.assertEqual(self.store.jobs(),[])
        p=self.service.plan(body);job=self.service.start({'plan_id':p['plan_id']})['job_id']
        with self.assertRaises(ValueError):self.service.apply({**body,'evidence_size':21})
        self.assertEqual(self.store.jobs()[0]['status'],'queued')

    def test_market_cache_is_ticker_specific_and_incomplete_return_is_null(self):
        from news_atlas.wiki.evidence import cached_market
        import sqlite3
        rows=[capture(row(day='2026-01-05')),capture(row(day='2026-01-08',suffix='late'))]
        bars=[dict(date='2026-01-'+str(d).zfill(2),close=100+d) for d in range(5,10)]
        with sqlite3.connect(str(self.service.news.path)+'.prices.sqlite3') as db:
            db.execute('CREATE TABLE series(key TEXT,payload TEXT,fetched REAL)')
            db.execute('INSERT INTO series VALUES (?,?,?)',('good',json.dumps({'ticker':'TSLA','bars':bars}),1))
            db.execute('INSERT INTO series VALUES (?,?,?)',('wrong',json.dumps({'ticker':'AAPL','bars':[dict(b,close=1000) for b in bars]}),2))
        m=cached_market(self.service.news,'NASDAQ:TSLA',rows,3)
        self.assertAlmostEqual(m[rows[0]['revision_id']]['mean_return'],sum((106+i)/105-1 for i in range(3))/3)
        self.assertIsNone(m[rows[1]['revision_id']]['mean_return'])
        article={**rows[0],'_market':m};p=proposal(article);p['nodes'][0]['assessment']={'category':'direct','rationale':'Operating channel, not proven causal','topic':'revenue','evidence':'supported'}
        node=validate_proposal(article,p,[])[0][0]
        self.assertEqual(node['market_evidence'][0]['ticker'],'TSLA')
        self.assertEqual(node['assessment']['topic'],'revenue')
