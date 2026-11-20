"""Classification through the real SQLite queue with a controlled model."""
import json
import unittest
from unittest.mock import patch

import test_research
from news_atlas.wiki import classifier
from news_atlas.wiki.store import encode


class ClassificationBatchTests(unittest.TestCase):
    setUp = test_research.ResearchTests.setUp
    add = test_research.ResearchTests.add

    def queue(self, count):
        for index in range(1, count):
            self.add('Opinion '+str(index), 'batch-'+str(index))
        with self.store.connection() as db:
            db.execute("DELETE FROM research_objects WHERE kind='classification'")
        key = classifier.enqueue(self.store, 'fixture', 'medium')['job_id']
        return key, self.research.read('job', key)['payload']['opinion_ids']

    @staticmethod
    def answer(ids):
        return {'proposal':{'opinions':[{'opinion_revision':ident, 'labels':[], 'candidates':[],
                                         'unclassified_reason':'No matching terms'} for ident in ids]}}

    def run_until_terminal(self, key):
        for _ in range(12):
            classifier.process(self.store, self.service)
            job = self.research.read('job', key)
            if job['status'] != 'queued':
                return job
        self.fail('Job exhausted bounded turns without a terminal state')

    def test_shared_evidence_keeps_each_targets_exact_dependencies_and_quotes(self):
        quote = {'article_revision_id':'x', 'field':'title', 'quote':'unique verbatim evidence', 'start':0, 'end':24}
        nodes = {i:{'id':i,'title':'Title '+i,'summary':i,'citations':[quote]} for i in ['a','b','shared','other']}
        membership = {'a':['a','shared','other'], 'b':['b','shared']}
        packet = classifier.classification_batch(['a','b'], nodes, membership, {'terms':[]})
        self.assertEqual(encode(packet).count('unique verbatim evidence'), 1)
        self.assertEqual(encode(packet).count('Title shared'), 1)
        self.assertEqual([r['dependency_ids'] for r in packet['opinions']], [['shared','other'],['shared']])
        for ident, node in packet['nodes'].items():
            self.assertEqual([packet['citations'][i] for i in node['citation_ids']], nodes[ident]['citations'])

    def test_timeout_is_split_once_unrelated_work_finishes_and_explicit_resume_skips_saved(self):
        key, ids = self.queue(6)
        calls = []
        def runner(store, job, article, context):
            subset = [row['id'] for row in article['opinions']];calls.append(subset)
            if ids[0] in subset:raise TimeoutError('Wiki compilation timed out after 600 seconds')
            return self.answer(subset)
        self.service.runner = runner
        job = self.run_until_terminal(key)
        self.assertEqual(calls,[ids[:4],ids[:2],ids[2:4],ids[4:]])
        self.assertEqual((job['status'],job['payload']['done']), ('failed',4))
        self.assertEqual(set(job['payload']['failed_ids']), set(ids[:2]))
        resumed=classifier.enqueue(self.store,'fixture','medium')
        self.assertEqual(resumed['pending'],2)
        resumed_calls=[]
        def succeed(store, job, packet, context):
            target_ids=[target['id'] for target in packet['opinions']]
            resumed_calls.extend(target_ids)
            return self.answer(target_ids)
        self.service.runner=succeed
        self.assertEqual(self.run_until_terminal(resumed['job_id'])['status'],'completed')
        self.assertEqual(resumed_calls,ids[:2])
        self.assertEqual(classifier.enqueue(self.store,'fixture','medium')['status'],'unchanged')

    def test_global_error_and_cancel_do_not_schedule_recovery(self):
        key, _ = self.queue(4)
        self.service.runner=lambda *args: (_ for _ in ()).throw(RuntimeError('429 quota'))
        job=self.run_until_terminal(key)
        self.assertEqual(job['status'],'failed');self.assertEqual(job['payload']['done'],0)
        self.assertFalse(job['payload'].get('retry_batches'))

    def test_late_timeout_cannot_requeue_a_cancelled_job(self):
        key, _ = self.queue(4)
        def runner(*args):
            with patch.object(self.service,'bridge_request',return_value={}):
                self.service.cancel({'instrument':self.store.instrument,'job_id':key})
            raise TimeoutError('late timeout')
        self.service.runner=runner
        job=self.run_until_terminal(key)
        self.assertEqual(job['status'],'cancelled');self.assertFalse(job['payload'].get('retry_batches'))

    def test_invalid_parent_reply_does_not_publish_partial_labels_and_children_complete(self):
        key,ids=self.queue(4)
        calls=[]
        def runner(store, job, packet, context):
            targets=[row['id'] for row in packet['opinions']]
            calls.append(targets)
            return self.answer(targets[:1] if len(targets)>2 else targets)
        self.service.runner=runner
        classifier.process(self.store,self.service)
        job=self.research.read('job',key)
        self.assertEqual(job['payload']['retry_batches'],[ids[:2],ids[2:]])
        self.assertEqual(job['payload']['done'],0)
        # The next scheduler instance reads both child batches from SQLite.
        from news_atlas.wiki.compiler import WikiService
        self.service=WikiService(self.service.news,runner=runner,start_worker=False)
        self.assertEqual(self.run_until_terminal(key)['status'],'completed')
        self.assertEqual(calls,[ids,ids[:2],ids[2:]])

    def test_utf8_limit_excludes_only_the_oversize_target_and_keeps_the_other_work(self):
        key,ids=self.queue(3)
        with self.store.connection() as db:
            db.execute("UPDATE nodes SET payload=json_set(payload,'$.summary',?) WHERE id=?",
                       ('字'*20000,ids[0]))
        called=[]
        def runner(store, job, packet, context):
            self.assertLessEqual(len(encode(packet).encode()),classifier.PACKET_BYTES)
            targets=[row['id'] for row in packet['opinions']]
            called.extend(targets)
            return self.answer(targets)
        self.service.runner=runner
        job=self.run_until_terminal(key)
        self.assertEqual(called,ids[1:])
        self.assertEqual(job['payload']['failed_ids'],ids[:1])
        self.assertEqual(job['payload']['done'],2)
        self.assertIn('輸入上限',job['payload']['last_batch_error'])

    def test_only_repeated_translation_taxonomy_and_provenance_values_are_factored(self):
        original={'id':'a','title':'T','summary':'S','assessment':{'rationale':'R'},
                  'translations':{'zh-Hant':{'title':'T','summary':'different','rationale':'R'}},
                  'citations':[{'article_revision_id':'article-abc','content_hash':'abc','quote':'原文'},
                               {'article_revision_id':'external','content_hash':'xyz','quote':'原文'}]}
        tax={'terms':[{'id':'t','aliases':['A'],'include':['A'],'exclude':[],'status':'active'},
                      {'id':'u','aliases':[],'include':['different'],'status':'deprecated'}]}
        packet=classifier.classification_batch(['a'],{'a':original},{},tax)
        self.assertEqual(packet['nodes']['a']['translations'],{'zh-Hant':{'summary':'different'}})
        self.assertEqual(packet['taxonomy']['terms'],[{'id':'t','aliases':['A']},tax['terms'][1]])
        self.assertNotIn('content_hash',packet['citations'][0])
        self.assertEqual(packet['citations'][1],original['citations'][1])
        self.assertEqual(original['citations'][0]['content_hash'],'abc')

    def test_resume_endpoint_keeps_its_news_interval_when_enqueuing_classification(self):
        from test_server import row
        self.add('Recent second claim','recent')
        old=row(title='Outside the resumed interval',suffix='old',day='2001-02-03')
        plan=self.service.plan({'instrument':self.store.instrument,'model':'fixture','articles':[old]})
        self.service.start({'plan_id':plan['plan_id']});self.service.process(self.store)
        with self.store.connection() as db:
            db.execute("DELETE FROM research_objects WHERE kind='classification'")
        self.store.configure({**self.store.config(),'date_range':{'start':'2020-01-01','end':'2026-01-01'}})
        result=self.service.resume({'instrument':self.store.instrument})
        job=self.research.read('job',result['classification']['job_id'])
        self.assertEqual(job['payload']['date_range'],result['config']['date_range'])
        self.assertEqual(job['payload']['total'],2)
