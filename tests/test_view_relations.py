import datetime as dt
import json
import unittest
from unittest.mock import patch
from test_server import HTTPTests, row
from news_atlas.model import deduplicate, _build_relations
from news_atlas.preview import stream, validate
from news_atlas.relation_settings import settings, UNIFIED
from news_atlas.search import normalize_request
import server


class ViewRelationsTests(HTTPTests):
    def test_preview_matches_existing_rules_and_counts_checks(self):
        rows = [row('google',suffix=str(i),symbols=['TSLA']) for i in range(5)]
        groups={'google':{'articles':rows}}
        head, body = self.request('POST','/api/graph/preview',{'source_graphs':groups,'relation_settings':UNIFIED})
        self.assertIn(b'200',head)
        events=[json.loads(line) for line in body.splitlines()]
        result=next(e for e in events if e['type']=='result')
        self.assertEqual(result['source_graphs']['google']['relations'], _build_relations(deduplicate(rows),relation_settings=UNIFIED))
        # Strict stage visits all ten pairs; no isolated nodes require expansion.
        self.assertEqual(result['pairs_checked'],10)
        self.assertEqual(events[-1]['type'],'done')
        self.assertEqual(sum(1 for e in events if e['type']=='progress'),4)
        self.assertFalse(self.store.path.with_name(self.store.path.name+'.graphs.sqlite3').exists())

    def test_preview_reuses_persistent_pairs_and_skips_hidden_cross_work(self):
        groups={p:{'articles':[row(p,suffix=p+str(i),symbols=['TSLA']) for i in range(3)]} for p in ('google','yahoo')}
        body={'source_graphs':groups,'relation_settings':settings(),'include_cross':False}
        def result():
            _, response=self.request('POST','/api/graph/preview',body)
            return next(e for e in map(json.loads,response.splitlines()) if e['type']=='result')
        first=result(); second=result()
        self.assertEqual(first['pairs_computed'],6)
        self.assertEqual(second['pairs_computed'],0)
        self.assertEqual(second['pairs_reused'],6)
        self.assertEqual(second['cross_relations'],[])
        self.assertEqual(first['source_graphs'],second['source_graphs'])
        body['include_cross']=True
        combined=result()
        self.assertEqual(combined['pairs_computed'],9)
        self.assertEqual(combined['pairs_reused'],6)
        self.assertTrue(combined['cross_relations'])

    def test_date_windows_missing_dates_and_cross_sources(self):
        rows=[row('google',day='2026-01-01',suffix='a'),row('google',day='2026-01-02',suffix='b'),row('google',day='2026-10-01',suffix='c')]
        cfg=settings()
        events=list(stream({'google':deduplicate(rows)},cfg,'complete'))
        self.assertEqual(next(e for e in events if e['type']=='result')['pairs_checked'],1)
        rows[1]['published_at']=None
        events=list(stream({'google':deduplicate(rows)},cfg,'complete'))
        self.assertEqual(next(e for e in events if e['type']=='result')['pairs_checked'],0)
        groups={'google':deduplicate([row('google',suffix='g',symbols=['TSLA'])]),'yahoo':deduplicate([row('yahoo',suffix='y',symbols=['TSLA'])])}
        result=next(e for e in stream(groups,cfg,'complete') if e['type']=='result')
        self.assertEqual(result['pairs_checked'],1)
        self.assertEqual(result['cross_relations'][0]['cross_sources'],['google','yahoo'])

    def test_scope_cap_enforced_before_computation(self):
        rows=[row('google',suffix=str(i)) for i in range(2401)]
        with patch('news_atlas.preview._build_relations',side_effect=AssertionError('must not compute')):
            head, body=self.request('POST','/api/graph/preview',{'source_graphs':{'google':{'articles':rows}}})
        self.assertIn(b'400',head)
        self.assertIn('2400',json.loads(body)['error'])
        valid,cfg,stage=validate({'source_graphs':{'google':{'articles':rows[:2400]}}},self.store)
        self.assertEqual(len(valid['google']),2400)

    def test_browser_search_defers_all_relation_work(self):
        req=normalize_request({'query':'test','sources':['google'],'start':'2026-01-01','end':'2026-01-02','defer_relations':True},today=dt.date(2026,11,4))
        with patch.object(server,'search_source',return_value={'source':'google','articles':[row('google')]}),patch.object(server,'build_relations',side_effect=AssertionError('full graph computation')):
            events=list(server.search_events(req,'',self.store))
        self.assertEqual(events[-1]['type'],'done')
        self.assertTrue(next(e for e in events if e['type']=='source')['graph']['relations_pending'])
        self.assertFalse(any(e['type']=='phase' for e in events))

    def test_strict_preview_is_subset_of_adaptive_completion(self):
        groups={'google':deduplicate([row('google',day=day,suffix=str(i),symbols=['TSLA']) for i,day in enumerate(['2026-01-01','2026-01-02','2026-03-01'])])}
        results=[next(e for e in stream(groups,UNIFIED,stage) if e['type']=='result') for stage in ['strict','complete']]
        strict,complete=[{e['id'] for e in result['source_graphs']['google']['relations']} for result in results]
        self.assertTrue(strict < complete)

    def test_snapshot_preserves_partial_scope(self):
        graph=server.graph_payload([row('google')])
        ident=graph['articles'][0]['id']
        payload={'view':{'sources':['google'],'separate':False,'relation_scope':'view','relation_scope_ids':[ident],'relations_pending':True},'source_graphs':{'google':graph['source_graphs']['google']},'cross_relations':[]}
        head,body=self.request('POST','/api/view/validate',payload)
        self.assertIn(b'200',head)
        self.assertEqual(json.loads(body)['view']['relation_scope'],'view')
        self.assertTrue(json.loads(body)['view']['relations_pending'])
        payload['view']['relation_scope_ids']=['missing']
        self.assertIn(b'400',self.request('POST','/api/view/validate',payload)[0])

    def test_preview_failure_is_explicit_not_false_completion(self):
        with patch('news_atlas.preview._build_relations',side_effect=RuntimeError('private internal failure')):
            events=list(stream({'google':deduplicate([row('google')])},settings(),'complete'))
        self.assertEqual([e['type'] for e in events],['error','done'])
        self.assertNotIn('private',json.dumps(events))
