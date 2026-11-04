"""Isolated Wiki persistence/cost/contract tests; no network or model calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from news_atlas.storage import Store
from news_atlas.search import query_key
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import capture, now, encode
from test_server import row


def proposal(a):
    cite={'revision_id':a['revision_id'],'field':'title','quote':a['title']}
    return {'nodes':[{'key':'n1','kind':'Claim','title':a['title'],'summary':'來源陳述，待判讀','scope':'TSLA:earnings','citations':[cite]}],'relations':[]}

class WikiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.news=Store(Path(self.tmp.name)/'news.sqlite3');self.calls=[]
        def run(store,job,a,context):
            self.calls.append(a['revision_id']);return {'proposal':proposal(a),'usage':{'input_tokens':30,'output_tokens':20}}
        self.service=WikiService(self.news,runner=run,start_worker=False)
        self.store=self.service.store('NASDAQ:TSLA')
    def plan(self,rows=None,**kw):
        return self.service.plan(dict(instrument='NASDAQ:TSLA',model='fixture',batch_size=5,daily_limit=20,articles=rows if rows is not None else [row()],sources=['massive'],search={'ticker':'TSLA'},**kw))
    def start(self,rows=None,continuous=False):
        p=self.plan(rows);self.service.start({'plan_id':p['plan_id'],'continuous':continuous});self.service.tick();return self.store.graph()
    def test_preview_zero_calls_duplicate_start_and_cached_extraction(self):
        p=self.plan();self.assertEqual(self.calls,[]);self.assertEqual(self.store.pending('fixture'),[])
        self.service.start({'plan_id':p['plan_id']});self.service.tick()
        with self.assertRaises(ValueError):self.service.start({'plan_id':p['plan_id']})
        before=self.store.graph();self.start()
        self.assertEqual(len(self.calls),1);self.assertEqual(before['edges'],self.store.graph()['edges'])
        self.assertEqual(self.plan()['next_batch'],0)
    def test_active_job_cannot_be_reconfigured_by_second_plan(self):
        first=self.plan();self.service.start({'plan_id':first['plan_id']})
        second=self.plan()
        with self.assertRaises(ValueError):self.service.start({'plan_id':second['plan_id'],'continuous':True})
        self.assertFalse(self.store.config()['enabled'])

    def test_changed_revision_and_history_survive_reopen(self):
        first=self.start();changed=row(title='Tesla earnings decline')
        second=self.start([changed]);self.assertEqual(second['version'],2)
        self.assertEqual(self.store.graph(version=1)['nodes'],first['nodes'])
        self.assertEqual(self.store.graph(as_of=first['versions'][0]['created_at'])['edges'],first['edges'])
        reopened=WikiService(self.news,start_worker=False).store('NASDAQ:TSLA')
        self.assertEqual(reopened.graph()['edges'],second['edges'])
        self.assertNotEqual(reopened.path,self.news.path)
        self.assertEqual(self.service.store('NASDAQ:AAPL').graph()['nodes'],[])
    def test_unverifiable_citation_rolls_back_and_disables_auto(self):
        def bad(*args):
            p=proposal(args[2]);p['nodes'][0]['citations'][0]['quote']='invented quotation';return {'proposal':p}
        self.service.runner=bad;g=self.start(continuous=True)
        self.assertEqual(g['version'],0);self.assertEqual(g['edges'],[])
        self.assertEqual(g['jobs'][0]['status'],'failed');self.assertFalse(g['config']['enabled'])
    def test_cancelled_late_result_cannot_publish(self):
        def late(store,job,a,context):
            store.cancel(job['id']);return {'proposal':proposal(a)}
        self.service.runner=late;g=self.start()
        self.assertEqual(g['version'],0);self.assertEqual(g['jobs'][0]['status'],'cancelled')
    def test_daily_limit_counts_attempts_before_results(self):
        p=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','batch_size':5,'daily_limit':1,'articles':[row(suffix=str(i)) for i in range(3)]})
        self.service.start({'plan_id':p['plan_id'],'continuous':True});self.service.tick();self.service.tick()
        self.assertEqual(len(self.calls),1);self.assertEqual(self.store.jobs()[0]['status'],'budget_paused')
    def test_restart_does_not_retry_paid_interrupted_call(self):
        p=self.plan();self.service.start({'plan_id':p['plan_id'],'continuous':True})
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET status='running'")
            job=self.store.jobs()[0]
        self.assertTrue(self.store.reserve_call(job,job['payload']['revisions'][0]))
        restarted=WikiService(self.news,runner=self.service.runner,start_worker=False);restarted.tick()
        self.assertEqual(self.calls,[]);self.assertFalse(self.store.config()['enabled'])
        self.assertEqual(self.store.jobs()[0]['status'],'interrupted')
    def test_continuous_observes_only_authorized_query_and_changed_content(self):
        self.start(continuous=True)
        self.news.save('massive',query_key('massive','AAPL'),[row(suffix='unrelated')],[])
        self.service.tick();self.assertEqual(len(self.calls),1)
        self.news.save('massive',query_key('massive','TSLA'),[row(suffix='new')],[])
        self.service.tick();self.assertEqual(len(self.calls),2)
        self.service.tick();self.assertEqual(len(self.calls),2)
    def test_all_emitted_relation_types_validate_contract(self):
        import jsonschema
        schema=json.loads((Path(__file__).parents[1]/'schema/temporal-wiki.relation.schema.json').read_text())
        def all_types(store,job,a,context):
            p=proposal(a);base=p['nodes'][0]
            p['nodes']=[dict(base,key='n'+str(i),kind=kind,title='node'+str(i)) for i,kind in enumerate(['Claim','Event','Event','Thesis'],1)]
            p['relations']=[dict(source=s,target=t,type=k,rationale='原文關聯提案',citations=base['citations']) for s,t,k in [('n1','n4','SUPPORTS'),('n1','n2','CONTRADICTS'),('n1','n2','UPDATES'),('n4','n1','DEPENDS_ON'),('n2','n3','TEMPORALLY_PRECEDES'),('n1','n4','RELATED_TO')]]
            return {'proposal':p}
        self.service.runner=all_types;g=self.start()
        self.assertEqual(len(g['edges']),10)
        for edge in g['edges']:jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker()).validate(edge)
    def test_graph_does_not_decode_invisible_historical_edges(self):
        g=self.start()
        with self.store.connection() as db:
            # Intentionally invalid payload outside displayed endpoints: must never be decoded.
            db.execute('INSERT INTO edges VALUES (?,?,?,?,?)',('hidden','outside','outside',1,'invalid json'))
        self.assertEqual(self.store.graph()['edges'],g['edges'])
    def test_invalid_proposals_and_stale_plan(self):
        from news_atlas.wiki.store import validate_proposal
        a=capture(row());p=proposal(a)
        p['relations']=[{'source':'n1','target':'foreign','type':'CAUSES'}]
        with self.assertRaises(ValueError):validate_proposal(a,p,[])
        pending=self.plan();self.start()
        with self.assertRaises(ValueError):self.service.start({'plan_id':pending['plan_id']})
        with self.assertRaises(ValueError):self.service.plan({'instrument':'../escape','model':'fixture'})
