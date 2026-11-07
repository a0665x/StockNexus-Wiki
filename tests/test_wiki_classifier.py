"""BDD: model classifications belong to immutable L1, shared across graph and Lens."""
import json, unittest
import test_research
from news_atlas.wiki import classifier
from news_atlas.wiki.research import taxonomy, obj

class ClassifierTests(unittest.TestCase):
    def setUp(self):
        test_research.ResearchTests.setUp(self)
        with self.store.connection() as db:db.execute("DELETE FROM research_objects WHERE kind='classification'")
    add=test_research.ResearchTests.add

    def test_backfill_classifies_once_without_reextracting_news(self):
        with self.store.connection() as db:
            before=db.execute('SELECT count(*) FROM extractions').fetchone()[0]
            tax=taxonomy(db)
        def runner(s,j,a,c):
            self.calls.append(j['payload']['operation'])
            return {'proposal':{'opinions':[{'opinion_revision':n['id'],'labels':[{'term_id':'driver.demand','rationale':'Demand claim','confidence':'medium'}],'candidates':[],'unclassified_reason':''} for n in a['opinions']]},'usage':{'input_tokens':7}}
        self.service.runner=runner
        first=classifier.enqueue(self.store,'fixture','high')
        self.assertEqual(classifier.enqueue(self.store,'fixture','high')['job_id'],first['job_id'])
        classifier.process(self.store,self.service)
        self.assertEqual(classifier.enqueue(self.store,'fixture','high')['status'],'unchanged')
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM extractions').fetchone()[0],before)
            self.assertEqual(classifier.assignments(db,tax['revision_id'])[next(iter(classifier.assignments(db,tax['revision_id'])))]['assignments'][0]['term_id'],'driver.demand')
        self.assertEqual(self.calls.count('classify_l1'),1)

    def test_unknown_term_rejected_and_no_partial_classification_published(self):
        def runner(s,j,a,c):return {'proposal':{'opinions':[{'opinion_revision':n['id'],'labels':[{'term_id':'fake.term','rationale':'x','confidence':'high'}],'candidates':[],'unclassified_reason':''} for n in a['opinions']]}}
        self.service.runner=runner;j=classifier.enqueue(self.store,'fixture','high');classifier.process(self.store,self.service)
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT status FROM research_jobs WHERE id=?',(j['job_id'],)).fetchone()[0],'failed')
            self.assertEqual(classifier.assignments(db,taxonomy(db)['revision_id']),{})

    def test_l1_busy_blocks_new_l2_but_existing_graph_is_readable(self):
        with self.store.connection() as db:db.execute("UPDATE jobs SET status='queued'")
        with self.assertRaisesRegex(ValueError,'L1'):self.research.query({'query':'動能'})
        self.assertTrue(self.store.graph()['nodes'])

    def test_model_label_reaches_dependencies_without_labeling_unrelated_news(self):
        nodes=[{'id':'t','kind':'Thesis'},{'id':'c','kind':'Claim'},{'id':'a','kind':'ArticleRevision'},{'id':'other','kind':'ArticleRevision'}]
        edge=lambda a,b,k:{'source':{'stable_id':a},'target':{'stable_id':b},'relation_type':k}
        graph={'nodes':nodes,'edges':[edge('t','c','DEPENDS_ON'),edge('a','c','SUPPORTS'),edge('a','other','RELATED_TO')]}
        group=classifier.groups(graph)
        self.assertEqual(set(group['t']),{'t','c','a'})

    def test_cancel_classifier_preserves_published_labels_and_requires_explicit_resume(self):
        self.add('Cloud supply', 'second')
        with self.store.connection() as db:
            before=classifier.assignments(db,taxonomy(db)['revision_id'])
        self.assertTrue(before)
        self.service.bridge_request=lambda *a,**kw: {}
        queued=classifier.enqueue(self.store,'fixture','high')
        self.service.cancel({'instrument':self.store.instrument,'job_id':queued['job_id']})
        classifier.process(self.store,self.service)
        self.assertEqual(self.research.read('job',queued['job_id'])['status'],'cancelled')
        resumed=classifier.enqueue(self.store,'fixture','high')
        self.assertNotEqual(resumed['job_id'],queued['job_id'])
        def runner(s,j,a,c):
            self.service.cancel({'instrument':s.instrument,'job_id':j['id']})
            raise RuntimeError('Model aborted by user')
        self.service.runner=runner
        classifier.process(self.store,self.service)
        self.assertEqual(self.research.read('job',resumed['job_id'])['status'],'cancelled')
        with self.store.connection() as db:
            self.assertEqual(classifier.assignments(db,taxonomy(db)['revision_id']),before)
        self.assertFalse(self.store.config()['catch_up'])

    def test_unified_start_backfills_labels_when_all_news_are_already_done(self):
        with self.store.connection() as db:
            articles=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles')]
            before=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
        plan=self.service.plan({'instrument':self.store.instrument,'model':'fixture','articles':[{**a,'source':{'provider':a['provider']}} for a in articles]})
        self.assertEqual(plan['pending'],0)
        result=self.service.start({'plan_id':plan['plan_id'],'classify_missing':True})
        self.assertEqual(result['status'],'queued')
        self.assertEqual(self.research.read('job',result['job_id'])['payload']['operation'],'classify_l1')
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],before)

    def test_month_backfill_respects_inclusive_utc_window_and_reuses_assignments(self):
        from test_server import row
        dates={'start':'2026-10-07','end':'2026-11-07'}
        cases=[('before','2026-10-06T23:59:59Z'),('start','2026-10-07T00:00:00Z'),('end','2026-11-07T23:59:59Z'),('after','2026-11-08T00:00:00Z'),('unknown',None),('timezone','2026-10-07T00:30:00+08:00')]
        for title,stamp in cases:
            a=row(title=title+' demand',suffix=title);a['published_at']=stamp
            plan=self.service.plan({'instrument':self.store.instrument,'model':'fixture','articles':[a]})
            self.service.start({'plan_id':plan['plan_id']});self.service.process(self.store)
        with self.store.connection() as db:
            db.execute("DELETE FROM research_objects WHERE kind='classification'")
        queued=classifier.enqueue(self.store,'fixture','high',date_range=dates)
        payload=self.research.read('job',queued['job_id'])['payload']
        with self.store.connection() as db:
            titles={json.loads(r['payload'])['title'] for r in db.execute('SELECT id,payload FROM nodes') if r['id'] in payload['opinion_ids']}
        self.assertIn('start demand',titles);self.assertIn('end demand',titles)
        for title in ('before','after','unknown','timezone'):self.assertNotIn(title+' demand',titles)
        self.assertEqual(payload['date_range'],dates)
        self.assertEqual(classifier.enqueue(self.store,'fixture','high',date_range=dates)['job_id'],queued['job_id'])
        with self.assertRaisesRegex(ValueError,'日期範圍不同'):
            classifier.enqueue(self.store,'fixture','high',date_range={'start':'2025-10-07','end':'2026-11-07'})

    def test_unified_start_passes_month_to_backfill_and_saves_scope_without_new_extraction(self):
        with self.store.connection() as db:
            a=json.loads(db.execute('SELECT payload FROM articles LIMIT 1').fetchone()[0])
            before=db.execute('SELECT count(*) FROM extractions').fetchone()[0]
        day=a['published_at'][:10];dates={'start':day,'end':day}
        plan=self.service.plan({'instrument':self.store.instrument,'model':'fixture','articles':[{**a,'source':{'provider':a['provider']}}],'date_range':dates})
        result=self.service.start({'plan_id':plan['plan_id'],'classify_missing':True})
        self.assertEqual(self.research.read('job',result['job_id'])['payload']['date_range'],dates)
        self.assertEqual(self.store.config()['date_range'],dates)
        self.assertFalse(self.store.config()['catch_up'])
        with self.store.connection() as db:self.assertEqual(db.execute('SELECT count(*) FROM extractions').fetchone()[0],before)
