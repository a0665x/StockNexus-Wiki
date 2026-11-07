"""BDD: recovered legacy revisions must not provoke a paid retry loop."""
import contextlib
import json
import unittest
from unittest.mock import patch
import test_wiki as fixtures
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import capture, encode
from test_server import row

class RevisionRecoveryTests(unittest.TestCase):
    setUp=fixtures.WikiTests.setUp
    plan=fixtures.WikiTests.plan
    start=fixtures.WikiTests.start

    def test_next_context_only_offers_current_revision_and_keeps_history(self):
        seen=[]
        def runner(store,job,a,context):
            seen.append(context)
            p=fixtures.proposal(a)
            old=next((n for n in context if n['kind']=='Claim'),None)
            if old:p['relations']=[dict(source='n1',target=old['id'],type='UPDATES',rationale='Updated evidence',citations=p['nodes'][0]['citations'])]
            return {'proposal':p}
        self.service.runner=runner
        self.start([row(title='Tesla earnings first',suffix='first')])
        original=self.store.graph(version=1)
        self.start([row(title='Tesla earnings second',suffix='second')])
        context=self.store.context(capture(row(title='Tesla earnings third',suffix='third')))
        old=next(n['id'] for n in original['nodes'] if n['kind']=='Claim')
        self.assertNotIn(old,[n['id'] for n in context])
        self.assertEqual(len([n for n in context if n['kind']=='Claim']),1)
        self.assertEqual(self.store.graph(version=1)['nodes'],original['nodes'])
        self.start([row(title='Tesla earnings third',suffix='third')])
        self.assertEqual(self.store.jobs()[0]['status'],'completed')
        self.assertEqual(self.store.graph()['version'],3)

    def test_superseded_dependent_thesis_is_not_reintroduced(self):
        # Legacy graph: dependency expansion must apply the same current-revision rule.
        with self.store.connection() as db:
            for ident,kind,title in [('claim','Claim','Tesla earnings'),('old','Thesis','old unrelated'),('new','Thesis','new unrelated')]:
                db.execute('INSERT INTO nodes VALUES (?,?,?,?)',(ident,kind,0,encode(dict(id=ident,kind=kind,title=title,scope='',citations=[]))))
            for ident,source,target,relation in [('depends','old','claim','DEPENDS_ON'),('updates','new','old','UPDATES')]:
                db.execute('INSERT INTO edges VALUES (?,?,?,?,?)',(ident,source,target,0,encode({'relation_type':relation})))
        ids=[n['id'] for n in self.store.context(capture(row(title='Tesla earnings')))]
        self.assertIn('claim',ids);self.assertNotIn('old',ids)

    def test_failure_and_disable_are_visible_in_one_commit_and_restart_does_not_retry(self):
        plan=self.plan();self.service.start({'plan_id':plan['plan_id'],'continuous':True})
        original=self.store.connection;unsafe=[]
        @contextlib.contextmanager
        def observed():
            with original() as db:yield db
            with original() as db:
                failed=db.execute("SELECT 1 FROM jobs WHERE status='failed'").fetchone()
                cfg=json.loads(db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0])
                if failed and (cfg.get('catch_up') or cfg.get('enabled')):unsafe.append(cfg)
        def fail(*args):self.calls.append('failed');raise ValueError('provider failure')
        self.service.runner=fail
        with patch.object(self.store,'connection',observed):self.service.process(self.store)
        self.assertEqual(unsafe,[],'A restart must never see failed work with auto-resume enabled')
        restarted=WikiService(self.news,runner=fail,start_worker=False);restarted.tick()
        self.assertEqual(self.calls,['failed'])
        self.assertEqual(len(self.store.jobs()),1)

    def test_publish_cas_rejection_keeps_receipt_without_partial_graph_or_retry(self):
        self.start();before=self.store.graph();previous=next(n for n in before['nodes'] if n['kind']=='Claim')
        def concurrent(store,job,a,context):
            p=fixtures.proposal(a)
            p['relations']=[dict(source='n1',target=previous['id'],type='UPDATES',rationale='Updated evidence',citations=p['nodes'][0]['citations'])]
            # Simulate another committed revision after the context snapshot.
            with store.connection() as db:
                new=dict(previous,id='concurrent-node')
                db.execute('INSERT INTO nodes VALUES (?,?,?,?)',(new['id'],new['kind'],1,encode(new)))
                edge=json.loads(db.execute('SELECT payload FROM edges LIMIT 1').fetchone()[0])
                edge.update(stable_id='concurrent',revision_id='concurrent',relation_type='UPDATES',source={'stable_id':new['id'],'revision_id':new['id'],'kind':new['kind']},target={'stable_id':previous['id'],'revision_id':previous['id'],'kind':previous['kind']})
                db.execute('INSERT INTO edges VALUES (?,?,?,?,?)',('concurrent',new['id'],previous['id'],1,encode(edge)))
            return {'proposal':p,'usage':{'input_tokens':77,'output_tokens':11}}
        self.service.runner=concurrent
        self.start([row(title='Tesla earnings changed',suffix='changed')])
        job=self.store.jobs()[0]
        self.assertEqual(job['status'],'failed');self.assertEqual(job['done'],0)
        self.assertEqual(job['usage'],{'input_tokens':77,'output_tokens':11})
        self.assertEqual(job['payload']['receipts'][0]['status'],'rejected')
        self.assertEqual(self.store.graph()['version'],before['version'])
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM rejected_proposals').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM extractions').fetchone()[0],1)
        self.assertFalse(self.store.config()['catch_up'])
