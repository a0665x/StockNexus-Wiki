import unittest
import json
from news_atlas.model import article, build_relations, deduplicate
from news_atlas.relation_settings import settings, DEFAULTS, GENERAL, UNIFIED
from server import graph_payload
import test_server


def rows():
    return deduplicate([article('google','Tesla quarterly revenue earnings', 'https://example.com/tesla-a','2026-01-01T00:00:00Z'),
            article('google','Tesla quarterly revenue earnings', 'https://example.com/tesla-b','2026-01-05T00:00:00Z'),
            article('yahoo','Unrelated local garden festival','https://example.com/garden','2026-01-05T00:00:00Z')])

class RuleTests(unittest.TestCase):
    def test_defaults_and_modes(self):
        data=rows()
        baseline=build_relations(data)
        self.assertEqual(baseline,build_relations(data,relation_settings=DEFAULTS))
        self.assertEqual(baseline[0]['type'],'shared_entity')
        self.assertEqual(baseline[0]['weight'],.79)
        self.assertEqual(build_relations(data,relation_settings={'entity':False})[0]['type'],'shared_topic')
        self.assertEqual(build_relations(data,relation_settings={'entity':False,'topic':False}),[])
        title=build_relations(data,relation_settings={'entity':False,'topic':False,'title_days':5})
        self.assertEqual(title[0]['type'],'similar_title')
        self.assertEqual(build_relations(data,relation_settings={'entity':False,'topic':False,'title':False}),[])

    def test_time_and_budgets(self):
        data=rows()
        self.assertEqual(build_relations(data,relation_settings={'entity_days':3,'topic':False,'title':False}),[])
        edge=build_relations(data,relation_settings={'half_life':4})[0]
        self.assertEqual(edge['weight'],.395)
        self.assertEqual(edge['evidence'][-1]['time_factor'],.5)
        self.assertEqual(build_relations(data,relation_settings={'internal_neighbors':0}),[])
        data[1]['source']['provider']='massive'
        graph=graph_payload(data,relation_settings={'cross_neighbors':0})
        self.assertEqual(graph['cross_relations'],[])
        self.assertEqual(len(graph['articles']),3)

    def test_long_window_general_mode_keeps_evidence_and_covers_nodes(self):
        data=[r for r in rows() if 'Tesla' in r['title']];data[1]['published_at']='2026-04-01T00:00:00Z'
        self.assertEqual(build_relations(data),[])
        edge=build_relations(data,relation_settings=GENERAL)[0]
        self.assertEqual(edge['type'],'shared_entity');self.assertGreater(edge['days_apart'],30)
        self.assertTrue(edge['evidence'][0]['entity'])
        # Coverage first prevents a dense clique consuming the whole small budget.
        data=deduplicate([article('google','Tesla earnings report',f'https://example.com/{i}',f'2026-01-{i+1:02d}T00:00:00Z') for i in range(8)])
        edges=build_relations(data,relation_settings={**GENERAL,'internal_neighbors':1})
        self.assertEqual(len({e[k] for e in edges for k in ('source','target')}),8)
        self.assertEqual(settings({'entity_days':366})['entity_days'],366)
        with self.assertRaises(ValueError):settings({'entity_days':367})

    def test_adaptive_preserves_strict_edges_then_connects_isolates(self):
        data=deduplicate([article('google','Tesla earnings report',f'https://example.com/adapt-{i}',day+'T00:00:00Z') for i,day in enumerate(['2026-01-01','2026-01-02','2026-04-01'])])
        strict=build_relations(data)
        adapted=build_relations(data,relation_settings=UNIFIED)
        self.assertEqual(len(strict),1);self.assertEqual(len(adapted),2)
        self.assertTrue({e['id'] for e in strict}<={e['id'] for e in adapted})
        self.assertEqual({e['adaptive_stage'] for edge in adapted for e in edge['evidence'] if 'adaptive_stage' in e},{'strict','expanded'})
        self.assertEqual(len({edge[k] for edge in adapted for k in ('source','target')}),3)

    def test_invalid_settings(self):
        for cfg in [[],{'foo':1},{'entity':1},{'title_days':False},{'half_life':-1},{'internal_neighbors':7},{'title_similarity':float('nan')},{'topic_days':2.5}]:
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):settings(cfg)

class RuleAPITests(unittest.TestCase):
    setUp=test_server.HTTPTests.setUp
    tearDown=test_server.HTTPTests.tearDown
    request=test_server.HTTPTests.request

    def test_rebuild_keeps_isolates_no_db_writes_and_snapshots(self):
        before=self.store.stats();data=rows();original=graph_payload(data)
        cfg=settings({'entity':False,'topic':False,'title':False})
        head,body=self.request('POST','/api/graph/build',{'source_graphs':original['source_graphs'],'relation_settings':cfg})
        self.assertIn(b'200',head);rebuilt=json.loads(body)
        self.assertEqual({a['id'] for a in rebuilt['articles']},{a['id'] for a in data})
        self.assertEqual(rebuilt['relations'],[]);self.assertEqual(rebuilt['relation_settings'],cfg)
        self.assertEqual(self.store.stats(),before)
        snap={'view':{'sources':['google','yahoo'],'separate':False,'relation_settings':cfg},'source_graphs':{k:v for k,v in rebuilt['source_graphs'].items() if k!='massive'}}
        head,body=self.request('POST','/api/snapshots',snap);self.assertIn(b'201',head)
        _,body=self.request('GET','/api/snapshots/'+json.loads(body)['id'])
        self.assertEqual(json.loads(body)['view']['relation_settings'],cfg)

    def test_partition_validation_and_asset(self):
        for body in [{'source_graphs':{'bad':{'articles':[]}}},{'articles':rows(),'relation_settings':{'title_days':367}},{'source_graphs':{'yahoo':{'articles':rows()[:1]}}}]:
            head,_=self.request('POST','/api/graph/build',body);self.assertIn(b'400',head)
        head,_=self.request('GET','/relation-settings.js');self.assertIn(b'200',head)


class RelationCacheTests(unittest.TestCase):
    def test_cached_evidence_is_not_mutable_between_requests(self):
        from news_atlas.model import build_relations
        from news_atlas.relation_settings import UNIFIED
        first=build_relations(rows(),relation_settings=UNIFIED)
        expected=build_relations(rows(),relation_settings=UNIFIED)
        self.assertTrue(first)
        first[0]['evidence'].clear()
        self.assertEqual(build_relations(rows(),relation_settings=UNIFIED),expected)
