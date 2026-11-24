"""HTTP snapshots and incremental updates must reconstruct the exact saved Wiki view."""
import json
import unittest
from unittest.mock import patch
import test_wiki_http
from news_atlas.wiki.store import WikiStore
from test_server import row


class ViewSyncTests(unittest.TestCase):
    setUp = test_wiki_http.WikiHTTPTests.setUp
    request = test_wiki_http.WikiHTTPTests.request
    path = 'graph?instrument=NASDAQ:TSLA&sync=1'

    def publish(self, title, suffix):
        _, plan = self.request('plan', {'instrument':self.store.instrument,'model':'fixture',
                                        'articles':[row(title=title,suffix=suffix)]})
        self.request('jobs', {'plan_id':plan['plan_id']});self.service.process(self.store)

    def test_unchanged_reads_skip_graph_build_and_later_batch_transfers_only_changes(self):
        self.publish('First evidence', 'one')
        full=self.request(self.path)[1];self.assertEqual(full.get('kind'),'full')
        since='&since='+full['token']
        with patch.object(WikiStore,'graph',side_effect=AssertionError('rebuilt unchanged view')):
            same=self.request(self.path+since)[1]
        self.assertEqual(same['kind'],'unchanged');self.assertNotIn('graph',same)
        self.publish('Later evidence','two')
        delta=self.request(self.path+since)[1];self.assertEqual(delta['kind'],'delta')
        fresh=self.request(self.path)[1]['graph']
        new_ids={n['id'] for n in fresh['nodes']}-{n['id'] for n in full['graph']['nodes']}
        self.assertTrue(new_ids)
        self.assertEqual({n['id'] for n in delta['rows']['nodes']['upsert']},new_ids)
        self.assertNotIn('jobs',fresh);self.assertNotIn('config',fresh)
        self.assertEqual(self.request(self.path+'&version=1'+since)[1]['kind'],'full')
        self.assertEqual(self.request(self.path+'&start=2024-01-01'+since)[1]['kind'],'full')

    def test_same_version_classification_or_taxonomy_changes_are_visible(self):
        self.publish('Evidence','one');base=self.request(self.path)[1]
        with self.store.connection() as db:
            from news_atlas.wiki.research import taxonomy,put
            tax=taxonomy(db);tax.update(revision_id='changed',available_at='2099-01-01T00:00:00+00:00');put(db,'taxonomy',tax,'','changed')
        changed=self.request(self.path+'&since='+base['token'])[1]
        self.assertEqual(changed['kind'],'delta');self.assertEqual(changed['set']['taxonomy']['revision_id'],'changed')
        self.assertNotEqual(base['epoch'],changed['epoch'])

    def test_compact_status_reuses_configuration_and_retains_current_frozen_worker_tree(self):
        self.publish('First evidence','one');cfg=self.store.config();cfg['enabled']=False;self.store.configure(cfg)
        with self.store.connection() as db:
            job=db.execute('SELECT id,payload FROM jobs LIMIT 1').fetchone();payload=json.loads(job['payload'])
            trees=[{'root_id':key,'title':key,'articles':[{'id':key,'provider':'massive'}]} for key in ['selected','unused']]
            payload.update(workers_state={'1':{'root_id':'selected','stage':'compiling','status':'running','bridge_call_id':'lane-call'}},graph_selection={'trees':trees})
            payload.update(failed_tree_count=1,last_tree_failure={'tree':4,'part':1,'code':'timeout'})
            db.execute("UPDATE jobs SET status='running',payload=? WHERE id=?",(json.dumps(payload),job['id']))
        self.service.bridge_request=lambda route,body,timeout:{'lane-call':{'sdk_stage':'awaiting_model','last_event_ms':125000}}
        path='jobs?instrument=NASDAQ:TSLA&view=compact';first=self.request(path)[1]
        view=first['jobs'][0]['payload'];self.assertNotIn('receipts',view);self.assertNotIn('revisions',view)
        self.assertEqual(view['workers_state']['1']['sdk_stage'],'awaiting_model')
        self.assertEqual(view['workers_state']['1']['sdk_quiet_minutes'],2)
        self.assertEqual(view['failed_tree_count'],1)
        self.assertEqual(view['last_tree_failure']['code'],'timeout')
        self.assertEqual(view['graph_selection']['trees'],trees[:1]);self.assertEqual(view['total'],1)
        same=self.request(path+'&config_token='+first['config_token'])[1];self.assertNotIn('config',same)
        self.assertEqual(same['instrument'],self.store.instrument)
        self.assertIn('coverage',same)

    def test_evicted_token_and_restarted_service_supply_a_complete_snapshot(self):
        from news_atlas.wiki.view_sync import GraphViews
        first=self.request(self.path)[1]
        for day in range(1,14):
            value=self.request(self.path+'&start=2024-01-'+str(day).zfill(2))[1]
            self.assertEqual(value['kind'],'full')
        unknown=self.request(self.path+'&since='+first['token'])[1]
        self.assertEqual(unknown['kind'],'full')
        self.assertEqual(unknown['graph'],first['graph'])
        self.service.graph_views=GraphViews()
        restarted=self.request(self.path+'&since='+unknown['token'])[1]
        self.assertEqual(restarted['kind'],'full')
        self.assertEqual(restarted['graph'],first['graph'])
