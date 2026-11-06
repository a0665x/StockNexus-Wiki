import datetime as dt
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from news_atlas.model import article
from news_atlas.search import normalize_request,query_key
from news_atlas.storage import Store
import server

class ProgressiveSearchTests(unittest.TestCase):
    def test_cached_nodes_are_emitted_before_any_relation_computation(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'fixture.sqlite3')
            store.save('google',query_key('google','test'),[article('google','Test','https://example.test/old','2025-12-31T00:00:00Z')],[])
            req=normalize_request({'query':'test','sources':['google'],'start':'2025-12-31','end':'2026-01-01'},today=dt.date(2026,11,2))
            stream=server.search_events(req,'',store)
            with patch('news_atlas.graph_payload.build_relations',side_effect=AssertionError('Relation calculation delayed the first visible news')):
                first=next(stream)
            self.assertEqual(first['type'],'cache')
            self.assertEqual(len(first['graph']['articles']),1)
            self.assertTrue(first['graph']['relations_pending'])
            stream.close()

    def test_final_relations_emit_heartbeat_and_use_requested_settings(self):
        import time
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'fixture.sqlite3')
            req=normalize_request({'query':'test','sources':['google'],'start':'2026-01-01','end':'2026-01-02','relation_settings':{'entity':False}},today=dt.date(2026,11,2))
            actual=server.graph_payload
            complete=[]
            def delayed(rows,channels=None,relation_settings=None,include_relations=True):
                if include_relations:
                    complete.append(relation_settings)
                    time.sleep(1.1)
                return actual(rows,channels,relation_settings,include_relations)
            with patch.object(server,'search_source',return_value={'source':'google','articles':[]}),patch.object(server,'graph_payload',side_effect=delayed):
                events=list(server.search_events(req,'',store))
            self.assertEqual(len(complete),1)
            self.assertFalse(complete[0]['entity'])
            self.assertTrue(any(e['type']=='heartbeat' and e.get('phase')=='relations' for e in events))
            final=next(e['graph'] for e in events if e['type']=='graph')
            self.assertFalse(final['relations_pending'])
            self.assertFalse(final['relation_settings']['entity'])
            self.assertEqual(events[-1]['type'],'done')

    def test_relation_failure_keeps_news_and_finishes_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'fixture.sqlite3')
            req=normalize_request({'query':'test','sources':['google'],'start':'2026-01-01','end':'2026-01-02'},today=dt.date(2026,11,2))
            rows=[article('google','Test','https://example.test/a','2026-01-01T00:00:00Z')]
            with patch.object(server,'search_source',return_value={'source':'google','articles':rows}),patch('news_atlas.graph_payload.build_relations',side_effect=RuntimeError('controlled failure')):
                events=list(server.search_events(req,'',store))
            self.assertEqual(next(e for e in events if e['type']=='source')['graph']['total_articles'],1)
            self.assertEqual(events[-2]['type'],'graph_error')
            self.assertEqual(events[-1]['type'],'done')

    def test_warm_edges_arrive_before_provider_work_and_survive_source_updates(self):
        from news_atlas.graph_cache import build_cached
        from news_atlas.model import deduplicate
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'fixture.sqlite3')
            rows=[article('google','NVIDIA earnings '+str(i),'https://example.test/'+str(i),'2026-01-01T00:00:00Z',symbols=['NVDA']) for i in range(3)]
            store.save('google',query_key('google','test'),rows,[])
            req=normalize_request({'query':'test','sources':['google'],'start':'2026-01-01','end':'2026-01-02'},today=dt.date(2026,11,2))
            normalized=deduplicate(store.read('google',query_key('google','test'),req['start'],req['end']))
            warm=build_cached(store,server.graph_payload,normalized,store.list_channels(),req['relation_settings'])
            with patch.object(server,'search_source',return_value={'source':'google','articles':normalized}) as provider,patch('news_atlas.graph_payload.build_relations',side_effect=AssertionError('warm edges recomputed')):
                stream=server.search_events(req,'',store)
                first=next(stream)
                self.assertEqual(first['graph'],warm)
                provider.assert_not_called()
                remaining=list(stream)
            self.assertTrue(next(e for e in remaining if e['type']=='source')['graph']['relations'])
            self.assertEqual(next(e['graph'] for e in remaining if e['type']=='graph'),warm)

    def test_partial_updates_keep_only_unchanged_endpoint_evidence(self):
        import copy
        rows=[article('google','NVIDIA earnings '+str(i),'https://example.test/'+str(i),'2026-01-01T00:00:00Z',symbols=['NVDA']) for i in range(3)]
        previous=server.graph_payload(rows)
        self.assertTrue(previous['relations'])
        pending=server.graph_payload(rows,include_relations=False)
        retained=server.retain_known_edges(pending,previous)
        self.assertEqual(retained['relations'],previous['relations'])
        self.assertTrue(retained['relations_pending'])
        changed=copy.deepcopy(rows);changed[0]['title']='Changed title'
        pending=server.retain_known_edges(server.graph_payload(changed,include_relations=False),previous)
        self.assertTrue(all(changed[0]['id'] not in (e['source'],e['target']) for e in pending['relations']))
        self.assertTrue(all(changed[0]['id'] not in (e['source'],e['target']) for e in pending['source_graphs']['google']['relations']))
