"""Full News universe root coverage, independent of rendered or clicked nodes."""
import unittest,tempfile,json
from pathlib import Path
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import capture
from test_server import row
from test_wiki import proposal

class ForestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.news=GraphRepository(Path(self.tmp.name)/'news.sqlite3');self.calls=[]
        def runner(store,job,a,c):
            self.calls.append(a);return {'proposal':proposal(a),'usage':{}}
        self.service=WikiService(self.news,runner=runner,start_worker=False);self.store=self.service.store('NASDAQ:TSLA')
    def body(self,rows,dates=None):
        for provider in {a['source']['provider'] for a in rows}:
            self.news.for_ticker('TSLA').save(provider,'fixture',[a for a in rows if a['source']['provider']==provider],[])
        return dict(instrument='NASDAQ:TSLA',model='fixture',strategy='root',evidence_size=5,scope='global',date_range=dates,
            graph_universe={'ticker':'TSLA','articles':[{'id':a['id'],'provider':a['source']['provider']} for a in rows]},
            graph_settings={'relation_settings':{'entity':False,'topic':False,'title':True,'title_days':366,'title_similarity':.1,'title_terms_min':2},'exploration':{'depth':2,'branchLimit':4,'maxNodes':150}})
    def test_no_clicked_root_full_tree_context_and_date_only_coverage(self):
        rows=[row(title='Tesla factory production earnings update',day='2026-01-02',suffix='old'),row(title='Tesla factory production earnings followup',day='2026-02-02',suffix='new'),row(title='Unrelated litigation court',day='2026-02-03',suffix='solo')]
        body=self.body(rows,{'start':'2026-02-01','end':'2026-02-28'})
        plan=self.service.plan(body)
        self.assertEqual(plan['selected'],2);self.assertEqual(plan['graph_selection']['mode'],'coverage')
        self.assertEqual(plan['graph_selection']['universe_articles'],3)
        self.service.start({'plan_id':plan['plan_id']});self.service.tick()
        c=self.service.coverage(self.store);self.assertEqual((c['scope_total'],c['scope_done'],c['scope_percent']),(2,2,100))
        self.assertTrue(any(capture(rows[0])['revision_id'] in {a['revision_id'] for a in c['_evidence']} for c in self.calls))
        self.assertEqual(len(self.store.known([capture(rows[0])])),1,'Outside-date context must not become processed coverage')
        self.assertEqual(self.service.plan(body)['pending'],0)
        count=len(self.calls);self.service.resume({'instrument':'NASDAQ:TSLA'});self.service.tick();self.assertEqual(len(self.calls),count)
    def test_all_unrendered_nodes_and_singletons_are_included(self):
        rows=[row(title='Unique '+str(i),suffix=str(i)) for i in range(810)]
        body=self.body(rows);body['graph_settings']['relation_settings'].update(title=False)
        p=self.service.plan(body);self.assertEqual(p['selected'],810)
        trees=p['graph_selection']['trees'];self.assertEqual(len(trees),810)
        self.assertEqual(len({a['id'] for tree in trees for a in tree['articles']}),810)
    def test_no_duplicate_tree_call_and_same_stock_boundary(self):
        rows=[row(title='Tesla factory production earnings '+str(i),suffix=str(i)) for i in range(3)]
        body=self.body(rows);p=self.service.plan(body)
        self.assertEqual(len(p['graph_selection']['trees']),1)
        self.service.start({'plan_id':p['plan_id']});self.service.tick();self.assertEqual(len(self.calls),1)
        with self.assertRaises(ValueError):self.service.plan({**body,'instrument':'NASDAQ:AAPL'})

    def test_each_sampled_tree_matches_browser_click_in_mixed_and_separate_views(self):
        import subprocess
        from news_atlas.graph_payload import graph_payload
        from news_atlas.wiki.evidence import graph_options
        rows=[row(provider=p,title='Tesla factory production earnings '+str(i),suffix=str(i)) for p in ['google','yahoo','massive'] for i in range(5)]
        body=self.body(rows)
        body['graph_settings']['exploration'].update(pathMin=0,branchLimit=3)
        cfg=graph_options(body['graph_settings'])
        graph=graph_payload(rows,self.news.for_ticker('TSLA').list_channels(),cfg['relation_settings'])
        for separate in [False,True]:
            body['graph_universe']['separate']=separate
            plan=self.service.plan(body);forest=plan['graph_selection']
            payload={'graph':graph,'cfg':cfg['exploration'],'roots':[t['root_id'] for t in forest['trees']],'separate':separate}
            js="const V=require('./dist/graph-view.js'),f=JSON.parse(require('fs').readFileSync(0,'utf8')),v=V.select(f.graph,['google','yahoo','massive'],f.separate),e=V.filterEdges(v.relations,f.cfg);console.log(JSON.stringify(f.roots.map(r=>[...V.trace(e,r,f.cfg).nodes.keys()].sort())))"
            result=subprocess.run(['node','-e',js],input=json.dumps(payload),text=True,capture_output=True,check=True)
            for tree,ids in zip(forest['trees'],json.loads(result.stdout)):
                expected=sorted({(a['provider']+'::' if separate else '')+a['id'] for a in tree['articles']})
                self.assertEqual(ids,expected)
            self.assertEqual(sum(len(t['targets']) for t in forest['trees']),len(rows))

    def test_partial_tree_failure_never_credits_unfinished_targets(self):
        rows=[row(title='Tesla factory production earnings '+str(i),suffix=str(i)) for i in range(15)]
        for a in rows:a['summary']='Factory evidence. '*650
        body=self.body(rows);body['graph_settings']['exploration'].update(branchLimit=10,depth=3,pathMin=0)
        p=self.service.plan(body);self.assertGreater(len(p['graph_selection']['trees'][0]['articles']),5)
        def fail_second(store,job,a,c):
            self.calls.append(a)
            if len(self.calls)==2:raise RuntimeError('simulated interrupted segment')
            return {'proposal':proposal(a),'usage':{}}
        self.service.runner=fail_second
        self.service.start({'plan_id':p['plan_id']});self.service.tick()
        self.assertEqual(self.store.jobs()[0]['status'],'failed')
        self.assertEqual(self.service.coverage(self.store)['scope_done'],0)
        self.assertEqual(self.store.graph()['version'],1)
        self.assertEqual(self.calls[0]['_covered_articles'],[])
        self.assertGreater(self.calls[0]['_group']['parts'],1)
        self.calls=[]
        def success(store,job,a,c):
            self.calls.append(a);return {'proposal':proposal(a),'usage':{}}
        self.service.runner=success
        self.service.resume({'instrument':'NASDAQ:TSLA'});self.service.tick()
        self.assertEqual(self.store.jobs()[0]['status'],'completed')
        self.assertEqual(self.service.coverage(self.store)['scope_done'],15)
        self.assertEqual(len({a['id'] for call in self.calls for a in call['_evidence']}),15)
        self.assertEqual(sum(len(a['_covered_articles']) for a in self.calls),15)
        # Bookkeeping can contain the whole tree, but must not inflate LLM input.
        bodies=[]
        self.service.bridge_request=lambda path,body,**kw:bodies.append(body)
        for call in self.calls:self.service.bridge(self.store,self.store.jobs()[0],call,[])
        self.assertTrue(all('_covered_articles' not in b['article'] and len(json.dumps(b))<200000 for b in bodies))

    def test_apply_switches_active_fixed_batch_to_automatic_forest(self):
        rows=[row(title='Tesla factory production earnings '+str(i),suffix=str(i)) for i in range(3)]
        body=self.body(rows)
        p=self.service.plan({**body,'strategy':'lexical','articles':rows,'evidence_size':20})
        job=self.service.start({'plan_id':p['plan_id']})['job_id']
        self.service.bridge_request=lambda *a,**k:{}
        result=self.service.apply(body)
        self.assertTrue(result['resumed'])
        self.assertEqual(next(j for j in self.store.jobs() if j['id']==job)['status'],'cancelled')
        self.service.tick()
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.store.config()['graph_selection']['mode'],'coverage')
        self.assertEqual(self.service.coverage(self.store)['scope_done'],3)

    def test_fair_scheduler_yields_only_after_all_tree_segments_publish(self):
        rows=[row(title='Tesla factory production earnings '+str(i),suffix=str(i)) for i in range(15)]
        for a in rows:a['summary']='Factory evidence. '*650
        rows.append(row(title='Isolated unrelated court ruling',suffix='isolated'))
        body=self.body(rows);body['graph_settings']['exploration'].update(branchLimit=10,depth=3,pathMin=0)
        plan=self.service.plan(body);self.service.start({'plan_id':plan['plan_id']})
        self.service.tick(max_groups=1)
        first=len(self.calls)
        self.assertGreater(first,1,'Large tree must publish all segments before yielding')
        self.assertEqual(self.store.jobs()[0]['status'],'queued')
        self.assertEqual(self.service.coverage(self.store)['scope_done'],len(plan['graph_selection']['trees'][0]['targets']))
        root=self.calls[0]['_group']['root_id']
        self.assertEqual(first,self.calls[0]['_group']['parts'])
        for _ in plan['graph_selection']['trees']:self.service.tick(max_groups=1)
        self.assertFalse(any(a['_group']['root_id']==root for a in self.calls[first:]),'Committed segments must not be replayed')
        self.assertEqual(self.store.jobs()[0]['status'],'completed')
        self.assertEqual(self.service.coverage(self.store)['scope_done'],16)

if __name__=='__main__':unittest.main()
