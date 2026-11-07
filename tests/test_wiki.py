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
    result={'nodes':[{'key':'n1','kind':'Claim','title':a['title'],'summary':'來源陳述，待判讀','scope':'TSLA:earnings','citations':[cite]}],'relations':[]}
    if a.get('_taxonomy'):
        from news_atlas.wiki.research import matches
        labels=[{'term_id':t['id'],'rationale':'Fixture classification','confidence':'low'} for t in a['_taxonomy']['terms'] if any(matches(a['title'],x) for x in t['aliases'])]
        result['nodes'][0]['classification']={'labels':labels,'candidates':[],'unclassified_reason':'' if labels else 'Fixture unclassified'}
    return result

class WikiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.news=Store(Path(self.tmp.name)/'news.sqlite3');self.calls=[]
        def run(store,job,a,context):
            self.calls.append(a['revision_id']);return {'proposal':({'nodes':[],'relations':[]} if job['payload'].get('operation')=='review' else proposal(a)),'usage':{'input_tokens':30,'output_tokens':20}}
        self.service=WikiService(self.news,runner=run,start_worker=False)
        self.store=self.service.store('NASDAQ:TSLA')
    def plan(self,rows=None,**kw):
        return self.service.plan(dict(instrument='NASDAQ:TSLA',model='fixture',batch_size=5,daily_limit=20,articles=rows if rows is not None else [row()],sources=['massive'],search={'ticker':'TSLA'},**kw))
    def start(self,rows=None,continuous=False):
        p=self.plan(rows);self.service.start({'plan_id':p['plan_id'],'continuous':continuous});self.service.tick();return self.store.graph()
    def test_invalid_temporal_relation_is_repaired_once_and_all_usage_counted(self):
        attempts=[]
        def run(store,job,a,context):
            attempts.append(job.get('repair'))
            p=proposal(a)
            p['nodes'].append(dict(p['nodes'][0],key='n2',kind='Event',title='event'))
            if len(attempts)==1:p['relations']=[dict(source='n2',target='n1',type='TEMPORALLY_PRECEDES',rationale='sequence',citations=p['nodes'][0]['citations'])]
            return {'proposal':p,'usage':{'input_tokens':10,'output_tokens':2}}
        self.service.runner=run;g=self.start()
        self.assertEqual(g['jobs'][0]['status'],'completed')
        self.assertEqual(len(attempts),2)
        self.assertIn('時間順序只能連接事件',attempts[1]['error'])
        self.assertEqual(g['jobs'][0]['usage']['input_tokens'],20)
        self.assertEqual(g['version'],1)
        self.assertFalse(any(e['relation_type']=='TEMPORALLY_PRECEDES' for e in g['edges']))

    def test_missing_relation_target_feedback_repairs_only_the_bad_edge(self):
        # Given valid new knowledge and one hallucinated existing endpoint, the
        # repair must identify that target instead of blaming every source.
        attempts=[]
        missing='node-'+'f'*64
        def run(store,job,a,context):
            feedback=(job.get('repair') or {}).get('error','');attempts.append(feedback)
            p=proposal(a);base=p['nodes'][0]
            p['nodes'].append(dict(base,key='n2',title='another supported claim'))
            valid=dict(source='n1',target='n2',type='RELATED_TO',rationale='shared evidence',citations=base['citations'])
            p['relations']=[valid,dict(valid,target=missing)]
            if 'target' in feedback and missing in feedback:p['relations'].pop()
            return {'proposal':p,'usage':{'input_tokens':10}}
        self.service.runner=run;g=self.start()
        self.assertEqual(g['jobs'][0]['status'],'completed')
        self.assertEqual(len(attempts),2)
        self.assertEqual(g['jobs'][0]['usage']['input_tokens'],20)
        self.assertEqual(g['version'],1)
        self.assertEqual(sum(e['relation_type']=='RELATED_TO' for e in g['edges']),1)
        self.assertFalse(any(missing in (e['source'],e['target']) for e in g['edges']))
        with self.store.connection() as db:
            self.assertEqual(db.execute('select count(*) from extractions').fetchone()[0],1)
            self.assertEqual(db.execute('select count(*) from rejected_proposals').fetchone()[0],1)

    def test_unrepaired_missing_target_never_publishes_or_credits_coverage(self):
        attempts=[]
        def run(store,job,a,context):
            attempts.append(1);p=proposal(a)
            p['relations']=[dict(source='n1',target='node-missing',type='RELATED_TO',rationale='unsupported endpoint',citations=p['nodes'][0]['citations'])]
            return {'proposal':p}
        self.service.runner=run;g=self.start()
        self.assertEqual(g['jobs'][0]['status'],'failed')
        self.assertEqual(len(attempts),2)
        self.assertEqual(g['version'],0)
        with self.store.connection() as db:
            self.assertEqual(db.execute('select count(*) from extractions').fetchone()[0],0)
            self.assertEqual(db.execute('select count(*) from rejected_proposals').fetchone()[0],2)

    def test_repair_stays_bounded_without_daily_quota(self):
        attempts=[]
        def bad(store,job,a,context):
            attempts.append(1);p=proposal(a);p['nodes'][0]['citations'][0]['quote']='not in source'
            return {'proposal':p,'usage':{'input_tokens':9}}
        self.service.runner=bad
        plan=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','batch_size':1,'daily_limit':1,'articles':[row()]})
        self.service.start({'plan_id':plan['plan_id']});self.service.tick()
        self.assertEqual(len(attempts),2);self.assertEqual(self.store.jobs()[0]['status'],'failed')
        self.assertEqual(self.store.jobs()[0]['usage']['input_tokens'],18);self.assertEqual(self.store.graph()['version'],0)

    def test_resume_drains_saved_scope_and_reuses_completed_articles(self):
        rows=[row(suffix=str(i)) for i in range(4)]
        self.news.save('massive',query_key('massive','TSLA'),rows,[])
        p=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','batch_size':1,'daily_limit':20,'articles':rows,'sources':['massive'],'search':{'ticker':'TSLA'}})
        self.service.start({'plan_id':p['plan_id']});self.service.tick()
        c=self.service.coverage(self.store);self.assertEqual((c['scope_done'],c['scope_total']),(4,4))
        self.service.resume({'instrument':'NASDAQ:TSLA'})
        for _ in range(5):self.service.tick()
        c=self.service.coverage(self.store);self.assertEqual(c['scope_percent'],100);self.assertEqual(len(self.calls),4)
        self.assertFalse(self.store.config()['catch_up']);self.service.resume({'instrument':'NASDAQ:TSLA'});self.service.tick();self.assertEqual(len(self.calls),4)
        self.assertTrue((self.news.path.parent/c['storage']).exists())
        newer=row(suffix='new-day');self.news.save('massive',query_key('massive','TSLA'),[newer],[])
        self.service.resume({'instrument':'NASDAQ:TSLA'});self.service.tick();self.assertEqual(len(self.calls),5)

    def test_classification_is_unverified_and_versioned(self):
        def run(store,job,a,context):
            p=proposal(a);p['nodes'][0]['kind']='Thesis';p['nodes'][0]['assessment']={'category':'direct','rationale':'Company earnings channel; returns not tested.'}
            return {'proposal':p}
        self.service.runner=run;g=self.start();n=g['perspectives']['theses'][0]
        self.assertEqual(n['assessment']['status'],'unverified');self.assertIsNone(n['assessment']['predictive_association'])
        self.assertEqual(g['perspectives']['categories']['direct'],1)
        self.assertEqual(self.store.graph(version=0)['perspectives']['total_theses'],0)

    def test_reopened_global_scope_reuses_saved_evidence_and_empty_start_preserves_config(self):
        self.start()
        p=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','scope':'global','articles':[],'sources':[],'search':{}})
        self.assertEqual(p['selected'],1);self.assertEqual(p['reused'],1)
        cfg=self.store.config();before=len(self.store.jobs())
        self.assertEqual(self.service.start({'plan_id':p['plan_id']})['status'],'noop')
        self.assertEqual(self.store.config(),cfg);self.assertEqual(len(self.store.jobs()),before)

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
    def test_legacy_limits_do_not_stop_processing(self):
        p=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','batch_size':5,'daily_limit':1,'articles':[row(suffix=str(i)) for i in range(3)]})
        self.service.start({'plan_id':p['plan_id'],'continuous':True});self.service.tick();self.service.tick()
        self.assertEqual(len(self.calls),3);self.assertEqual(self.store.jobs()[0]['status'],'completed')
        self.assertEqual(self.service.coverage(self.store)['daily_calls'],3)
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

    def test_switch_model_and_prompt_does_not_reextract(self):
        self.start()
        p=self.service.plan({'instrument':'NASDAQ:TSLA','model':'different-model','articles':[row()]})
        self.assertEqual(p['reused'],1);self.assertEqual(p['next_batch'],0)
        self.service.start({'plan_id':p['plan_id']});self.service.tick()
        self.assertEqual(len(self.calls),1)

    def test_global_date_expansion_only_fills_missing_articles(self):
        old=row(day='2025-12-02',suffix='old');recent=row(day='2026-01-02',suffix='recent')
        self.news.save('massive',query_key('massive','TSLA'),[old,recent],[])
        body={'instrument':'NASDAQ:TSLA','model':'fixture','scope':'global','search':{'ticker':'TSLA'},'sources':['massive'],'articles':[], 'date_range':{'start':'2026-01-01','end':'2026-01-31'}}
        p=self.service.plan(body);self.assertEqual(p['selected'],1)
        self.service.start({'plan_id':p['plan_id']});self.service.tick();self.assertEqual(len(self.calls),1)
        body['model']='different-model';body['date_range']['start']='2025-12-01'
        p=self.service.plan(body);self.assertEqual((p['selected'],p['pending'],p['reused']),(2,1,1))
        self.service.start({'plan_id':p['plan_id']});self.service.tick();self.assertEqual(len(self.calls),2)
        self.assertEqual(self.service.plan(body)['next_batch'],0)

    def test_narrow_plan_does_not_spend_on_outside_backlog_or_subscription(self):
        outside=row(day='2025-12-02',suffix='outside')
        self.store.ingest([capture(outside)])
        self.news.save('massive',query_key('massive','TSLA'),[outside],[])
        p=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':[row()], 'sources':['massive'],'search':{'ticker':'TSLA'},'date_range':{'start':'2026-01-01','end':'2026-01-31'}})
        self.service.start({'plan_id':p['plan_id'],'continuous':True});self.service.tick();self.service.tick()
        self.assertEqual(self.calls,[capture(row())['revision_id']])
        self.assertEqual(len(self.store.pending()),1)

    def test_review_is_explicit_bounded_and_never_continuous(self):
        first=self.start()
        p=self.plan(operation='review');self.assertEqual(p['next_batch'],1)
        with self.assertRaises(ValueError):self.service.start({'plan_id':p['plan_id'],'continuous':True})
        self.service.start({'plan_id':p['plan_id']});self.service.tick();self.service.tick()
        self.assertEqual(len(self.calls),2);self.assertEqual(self.store.graph()['version'],2)
        self.assertEqual(self.store.graph(version=1)['edges'],first['edges'])
        self.assertEqual(self.plan()['next_batch'],0)

    def test_global_context_can_retrieve_old_knowledge_beyond_latest_500(self):
        self.start()
        with self.store.connection() as db:
            for i in range(510):db.execute('INSERT INTO nodes VALUES (?,?,?,?)',(str(i),'Claim',2,encode({'id':str(i),'kind':'Claim','title':'Unrelated weather','scope':'weather'})))
        context=self.store.context(capture(row(title='Tesla earnings update',suffix='another')))
        self.assertTrue(any(n['title']=='Tesla earnings grow' for n in context))

    def test_explicit_review_can_revisit_existing_viewpoints(self):
        self.start([row(suffix=str(i)) for i in range(3)])
        body={'instrument':'NASDAQ:TSLA','model':'fixture','articles':[row(suffix=str(i)) for i in range(3)],'batch_size':1,'operation':'review'}
        for remaining in [3,3]:
            p=self.service.plan(body);self.assertEqual(p['pending'],remaining)
            self.service.start({'plan_id':p['plan_id']});self.service.tick()
        self.assertEqual(len(self.calls),9)

    def test_old_snapshot_does_not_hide_explicitly_selected_latest_revision(self):
        latest=capture(row(title='Tesla latest earnings'));old=capture(row(title='Tesla old earnings'))
        self.store.ingest([latest,old]);self.store.ingest([latest])
        self.assertEqual(self.store.pending(revision_ids=[latest['revision_id']]),[latest])

    def test_background_enqueue_cannot_override_manual_plan_scope(self):
        import threading
        from unittest.mock import patch
        self.start(continuous=True)
        new=row(suffix='new');self.news.save('massive',query_key('massive','TSLA'),[new],[])
        p=self.plan([row(suffix='manual')]);entered=threading.Event();release=threading.Event();finished=threading.Event();errors=[]
        original=self.service.subscribed
        def blocked(*args):entered.set();release.wait(3);return original(*args)
        def manual():
            try:self.service.start({'plan_id':p['plan_id']})
            except ValueError as e:errors.append(str(e))
            finally:finished.set()
        with patch.object(self.service,'subscribed',side_effect=blocked):
            bg=threading.Thread(target=self.service.refresh,args=(self.store,));bg.start();self.assertTrue(entered.wait(2))
            request=threading.Thread(target=manual);request.start()
            self.assertFalse(finished.wait(.1));release.set();bg.join(3);request.join(3)
        self.assertTrue(errors);self.assertEqual(self.store.jobs()[0]['payload']['revisions'],[capture(new)['revision_id']])
