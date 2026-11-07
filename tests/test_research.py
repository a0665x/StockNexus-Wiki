"""BDD boundaries using real L1 publication, SQLite and the production job pipeline.
The model is an explicit controlled fixture; no paid calls or invented live evidence.
"""
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from news_atlas.storage import Store
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.research import Research, canonical_ast, allowed, instant, now, taxonomy, validate_fusion
from test_server import row
from test_wiki import proposal


def fusion(b):
    claims=[{'id':'c'+str(i+1),'statement':n['statement'],'type':'reported_claim','derived_from':[n['claim_id']],'assumptions':[],'invalidating_conditions':[]} for i,n in enumerate(b['opinions'])]
    return {'claims':claims,'summary':[c['id'] for c in claims],'support':[c['id'] for c in claims],'counter':[],'narrative':[c['id'] for c in claims],'gaps':[]}

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.news=Store(Path(self.tmp.name)/'news.sqlite3');self.calls=[]
        def runner(s,j,a,c):
            self.calls.append(j['payload'].get('operation'))
            if j['payload'].get('operation')=='research_fusion':return {'proposal':fusion(a['research_bundle']),'usage':{'input_tokens':100}}
            p=proposal(a);p['nodes'][0]['summary']=a['title'];return {'proposal':p}
        self.service=WikiService(self.news,runner=runner,start_worker=False)
        self.store=self.service.store('NASDAQ:TSLA');self.research=Research(self.store)
        self.add('Data center capex demand','a')

    def add(self,title,suffix):
        article=row(title=title,suffix=suffix,day=(instant(now())-dt.timedelta(days=1)).date().isoformat())
        plan=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':[article]})
        self.service.start({'plan_id':plan['plan_id']});self.service.process(self.store)
        return article

    def query(self,**kw):return self.research.query({'query':'動能','model':'fixture',**kw})
    def complete(self,**kw):
        job=self.query(**kw);self.service.tick();status=self.research.read('job',job['job_id'])
        self.assertEqual(status['status'],'completed',status.get('error'))
        return status['payload']['run_id']
    def save(self,mode='live'):
        run=self.complete();return self.research.save({'run_id':run,'mode':mode})

    def test_vertical_l1_classification_lens_fusion_source_chain(self):
        ident=self.complete();r=self.research.read('run',ident)
        self.assertTrue(r['result']['claims']);self.assertEqual(r['result']['price_momentum']['status'],'unavailable')
        b=r['bundle'];labels={a['term_id'] for a in b['assignments']}
        self.assertTrue({'topic.data_center','driver.capex','driver.demand'}<=labels)
        for c in r['result']['claims']:
            for ref in c['derived_from']:
                n=next(n for n in b['opinions'] if n['claim_id']==ref)
                self.assertTrue(n['evidence'][0]['quote']);self.assertTrue(n['revision_id'])
        self.assertEqual(b['outcomes'],[])

    def test_polling_and_catalog_reads_do_not_reingest_news(self):
        # Given a published run, reading progress/list/classification must work
        # even when the source store is unavailable; these are committed Wiki data.
        from unittest.mock import Mock, patch
        from news_atlas.wiki.research import handle_research
        run_id=self.complete()
        with self.store.connection() as db:job_id=db.execute("SELECT id FROM research_jobs WHERE status='completed'").fetchone()[0]
        for path,ident in [('job',job_id),('runs',None),('taxonomy',None)]:
            handler=Mock();handler.command='GET'
            params={'instrument':['NASDAQ:TSLA']}
            if ident:params['id']=[ident]
            with patch.object(Research,'observe_news',side_effect=AssertionError('poll reingested entire source corpus')):
                handle_research(handler,self.service,path,params,True)
            self.assertEqual(handler.json_response.call_args.args[0],200)
        # A result's freshness check still observes source changes.
        handler=Mock();handler.command='GET'
        with patch.object(Research,'observe_news') as observe:
            handle_research(handler,self.service,'run',{'instrument':['NASDAQ:TSLA'],'id':[run_id]},True)
            observe.assert_called_once_with(self.news)

    def test_duplicate_query_uses_same_job_and_no_extra_model_call(self):
        a=self.query();b=self.query();self.assertEqual(a['job_id'],b['job_id'])
        self.service.tick();self.query();self.service.tick()
        self.assertEqual(self.calls.count('research_fusion'),1)

    def test_different_window_is_a_different_lens_even_with_same_candidates(self):
        a=self.complete(lookback_days=30);b=self.complete(lookback_days=90)
        self.assertNotEqual(a,b)
        self.assertEqual(self.research.read('run',b)['bundle']['lens']['time_policy']['lookback_days'],90)

    def test_hard_exclusion_empty_does_not_relax_or_call_model(self):
        r=self.research.read('run',self.complete(filter_ast={'op':'not','arg':{'op':'term','value':'driver.capex'}}))
        self.assertEqual(r['bundle']['opinions'],[]);self.assertEqual(r['result']['content_status'],'insufficient_evidence')
        self.assertEqual(self.calls.count('research_fusion'),0)

    def test_unknown_term_rejected_unknown_word_recalled_by_fulltext(self):
        with self.assertRaises(ValueError):self.query(filter_ast={'op':'term','value':'topic.magic'})
        self.add('Novel quux mechanism','unknown');r=self.research.read('run',self.complete(query='quux'))
        self.assertTrue(any('quux' in n['statement'] for n in r['bundle']['opinions']))

    def test_new_unreferenced_opinion_invalidates_live_and_refreshes(self):
        s=self.save();self.add('Cloud supply risk','new')
        self.assertEqual(self.research.read('lenses')['lenses'][0]['refresh_state'],'stale')
        j=self.research.refresh({'lens_id':s['id'],'expected_revision':s['revision']});self.service.tick()
        run=self.research.read('job',j['job_id'])['payload']['run_id']
        self.assertTrue(any('Cloud' in n['statement'] for n in self.research.read('run',run)['bundle']['opinions']))
        self.assertEqual(len(self.research.read('lenses')['lenses'][0]['history']),2)

    def test_saved_live_automatically_updates_once_after_new_candidate(self):
        s=self.save();self.add('Cloud capex concern','automatic')
        self.service.tick();self.service.tick()
        current=self.research.read('lenses')['lenses'][0]
        self.assertEqual(len(current['history']),2)
        self.assertNotEqual(current['run_id'],s['run_id'])
        self.assertEqual(self.calls.count('research_fusion'),2)

    def test_no_effective_change_refresh_does_not_spend_tokens(self):
        s=self.save();calls=len(self.calls)
        result=self.research.refresh({'lens_id':s['id'],'expected_revision':s['revision']})
        self.assertEqual(result['status'],'unchanged');self.assertEqual(len(self.calls),calls)

    def test_pinned_survives_new_evidence_and_cannot_refresh(self):
        s=self.save('pinned');old=self.research.read('run',s['run_id'])['bundle'];self.add('New risk','risk')
        self.assertEqual(self.research.read('run',s['run_id'])['bundle'],old)
        self.assertEqual(self.research.read('lenses')['lenses'][0]['refresh_state'],'pinned')
        with self.assertRaises(ValueError):self.research.refresh({'lens_id':s['id'],'expected_revision':s['revision']})

    def test_today_backfill_excluded_from_past_as_known(self):
        past=(instant(now())-dt.timedelta(days=1)).isoformat()
        _,b,_=self.research.prepare({'query':'動能','as_of':past})
        self.assertEqual(b['opinions'],[])

    def test_correction_never_rewrites_pinned_but_excludes_stale_source(self):
        s=self.save('pinned')
        with self.store.connection() as db:a=json.loads(db.execute('SELECT payload FROM articles').fetchone()[0])
        from news_atlas.wiki.store import capture
        changed=row(title='Corrected demand claim',suffix='a',day=(instant(now())-dt.timedelta(days=1)).date().isoformat());self.store.ingest([capture(changed)])
        _,b,_=self.research.prepare({'query':'動能'})
        self.assertGreater(b['manifest']['epochs']['pending'],0)
        self.assertEqual(b['opinions'],[])
        self.assertTrue(self.research.read('run',s['run_id'])['result']['claims'])

    def test_failure_retains_last_success_and_no_auto_retry(self):
        s=self.save();self.add('New risk','new')
        j=self.research.refresh({'lens_id':s['id'],'expected_revision':s['revision']})
        def fail(*a):raise RuntimeError('fixture unavailable')
        self.service.runner=fail;self.service.tick();self.service.tick()
        self.assertEqual(self.research.read('job',j['job_id'])['status'],'failed')
        current=self.research.read('lenses')['lenses'][0]
        self.assertEqual(current['run_id'],s['run_id']);self.assertEqual(current['refresh_state'],'failed')

    def test_cas_conflict_never_overwrites_lens(self):
        s=self.save();self.add('New risk','new')
        j=self.research.refresh({'lens_id':s['id'],'expected_revision':s['revision']})
        with self.store.connection() as db:
            changed=self.research._lens(db,s['id']);changed['revision']='user-changed';self.research._save(db,changed)
        self.service.tick();self.assertEqual(self.research.read('job',j['job_id'])['status'],'failed')
        self.assertEqual(self.research.read('lenses')['lenses'][0]['run_id'],s['run_id'])

    def test_owner_stock_isolation_and_no_l2_ingestion(self):
        with self.assertRaises(ValueError):self.query(owner='someone')
        before=self.store.graph()['version'];r=self.complete()
        self.assertEqual(self.store.graph()['version'],before)
        other=Research(self.service.store('NASDAQ:AMD'))
        with self.assertRaises(ValueError):other.read('run',r)
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM articles').fetchone()[0],1)

    def test_invalid_reference_numeric_and_unregistered_summary_rejected(self):
        _,b,_=self.research.prepare({'query':'動能'});valid=fusion(b)
        for modify in [lambda p:p['claims'][0].update(derived_from=['absent']),lambda p:p['claims'][0].update(statement='Returns 99999%'),lambda p:p.update(summary=['unregistered']),lambda p:p['claims'][0].update(statement='敘事正在轉強')]:
            bad=copy.deepcopy(valid);modify(bad)
            with self.assertRaises(ValueError):validate_fusion(bad,b)

    def test_live_time_policy_moves_and_does_not_pin_initial_cutoff(self):
        s=self.save();self.assertEqual(s['lens']['time_policy']['cutoff_mode'],'rolling_now')
        with self.store.connection() as db:
            s['checked_at']='2000-01-01T00:00:00+00:00';self.research._save(db,s)
        self.assertEqual(self.research.read('lenses')['lenses'][0]['refresh_state'],'stale')

    def test_taxonomy_edit_cas_and_invalidation(self):
        self.save();t=self.research.read('taxonomy');t['terms'][0]['aliases'].append('server farm')
        new=self.research.update_taxonomy({'expected_revision':t['revision_id'],'terms':t['terms']})
        self.assertNotEqual(t['revision_id'],new['revision_id'])
        self.assertEqual(self.research.read('lenses')['lenses'][0]['refresh_state'],'stale')
        with self.assertRaises(ValueError):self.research.update_taxonomy({'expected_revision':t['revision_id'],'terms':t['terms']})

    def test_unsupported_fusion_inference_is_never_published(self):
        def runner(store,job,article,context):
            if job['payload']['operation']=='research_review':return {'proposal':{'assessment':'revise','checked_claim_ids':['c1'],'issues':[{'claim_id':'c1','reason':'unsupported','severity':'error'}]}}
            p=fusion(article['research_bundle']);p['claims'][0].update(type='inference',statement='條件推論',assumptions=['前提成立'],invalidating_conditions=['前提撤回'])
            return {'proposal':p}
        self.service.runner=runner;j=self.query();self.service.tick()
        self.assertEqual(self.research.read('job',j['job_id'])['status'],'failed')
        with self.store.connection() as db:self.assertEqual(db.execute("SELECT count(*) FROM research_objects WHERE kind='run'").fetchone()[0],0)

    def test_retraction_does_not_rewrite_history_and_invalidates_live(self):
        saved=self.save();old=self.research.read('run',saved['run_id'])
        rev=old['bundle']['opinions'][0]['evidence'][0]['revision_id']
        self.research.source_status({'revision_id':rev,'status':'retracted','reason':'fixture correction'})
        self.assertEqual(self.research.read('lenses')['lenses'][0]['refresh_state'],'stale')
        self.assertEqual(self.research.prepare({'query':'動能'})[1]['opinions'],[])
        self.assertEqual(self.research.read('run',saved['run_id'])['result'],old['result'])

    def test_restart_of_paid_live_job_requires_manual_retry(self):
        saved=self.save();self.add('New risk','restart')
        job=self.research.refresh({'lens_id':saved['id'],'expected_revision':saved['revision']})
        with self.store.connection() as db:db.execute("UPDATE research_jobs SET status='running' WHERE id=?",(job['job_id'],))
        calls=len(self.calls)
        restarted=WikiService(self.news,runner=self.service.runner,start_worker=False)
        restarted.tick();restarted.tick()
        self.assertEqual(len(self.calls),calls)
        self.assertEqual(self.research.read('lenses')['lenses'][0]['refresh_state'],'failed')
        self.assertEqual(self.research.read('lenses')['lenses'][0]['run_id'],saved['run_id'])

    def test_candidate_alias_does_not_create_new_canonical_term(self):
        self.assertEqual(self.research.candidate({'text':'capex','facet':'driver'})['status'],'mapped')
        self.assertEqual(self.research.candidate({'text':'unknown concept','facet':'topic'})['status'],'candidate')
        self.assertFalse(any(t['label']=='unknown concept' for t in self.research.read('taxonomy')['terms']))

    def test_boolean_ast_depth_conflicts_and_explicit_text_exclusion(self):
        ast={'op':'and','args':[{'op':'or','args':[{'op':'text','value':'cloud'},{'op':'text','value':'capex'}]},{'op':'not','arg':{'op':'text','value':'risk'}}]}
        ast=canonical_ast(ast,set());self.assertTrue(allowed(ast,'capex',[]));self.assertFalse(allowed(ast,'capex risk',[]))
        with self.assertRaises(ValueError):self.query(query='only hardware')
        with self.assertRaises(ValueError):self.query(query='動能 排除 cloud',filter_ast={'op':'text','value':'capex'})
        with self.assertRaises(ValueError):self.query(required_terms=['driver.capex'])
        r=self.research.read('run',self.complete(query='動能，排除「capex」'));self.assertEqual(r['bundle']['opinions'],[])

if __name__=='__main__':unittest.main()
