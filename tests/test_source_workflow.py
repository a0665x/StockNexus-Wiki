import unittest
from news_atlas.search import normalize_request

class SourceWorkflowTests(unittest.TestCase):
    def test_yahoo_accepts_keywords_without_ticker(self):
        request = normalize_request({'query': '電動車電池', 'sources': ['google', 'yahoo']})
        self.assertEqual(request['ticker'], '')

    def test_uppercase_keyword_is_not_implicitly_a_ticker(self):
        request = normalize_request({'query': 'AI', 'sources': ['google']})
        self.assertEqual(request['ticker'], '')


import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from news_atlas.model import article, deduplicate, build_relations
from news_atlas.storage import Store
from news_atlas import providers, search
import server

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'atlas.sqlite3'
        self.store=Store(self.path)
        self.groups={}
        for provider in ('google','massive'):
            rows=deduplicate([article(provider,'Tesla launches new battery','https://example.com/a','2026-01-01T00:00:00Z'),article(provider,'Tesla reports battery progress','https://example.com/b','2026-01-02T00:00:00Z')])
            self.groups[provider]={'articles':rows,'relations':build_relations(rows)}
        self.payload={'name':'test view','view':{'sources':['google','massive'],'separate':True,'positions':[]},'search':{'query':'battery','massive_key':'DO_NOT_SAVE'},'source_graphs':self.groups,'cross_relations':[]}
    def tearDown(self):self.tmp.cleanup()

    def test_roundtrip_keeps_source_rows_relations_and_no_credentials(self):
        saved=self.store.save_snapshot(self.payload)
        restored=Store(self.path).load_snapshot(saved['id'])
        self.assertEqual(restored['source_graphs']['google']['relations'],self.groups['google']['relations'])
        self.assertEqual(restored['source_graphs']['massive']['articles'],self.groups['massive']['articles'])
        self.assertEqual(restored['view']['sources'],['google','massive'])
        self.assertEqual(len(self.store.list_snapshots()),1)
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshot_articles').fetchone()[0],4)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshot_relations').fetchone()[0],2)
            self.assertNotIn('DO_NOT_SAVE','\n'.join(db.iterdump()))
        self.assertEqual(self.store.stats()['articles'],0,'Saving a view must not invent source coverage/cache records')

    def test_snapshot_restores_completed_views_and_render_budget(self):
        from news_atlas.relation_settings import settings
        ids=sorted(f"{p}::{a['id']}" for p,g in self.groups.items() for a in g['articles'])
        entry={'ids':ids,'sources':['google','massive'],'separate':True,'relation_settings':settings(),
               'source_graphs':{p:{'relations':g['relations']} for p,g in self.groups.items()},'cross_relations':[]}
        self.payload['view'].update(selected_id=ids[0],highlight_mode='root',graph_channel='',render_budget=2400,relation_cache_version=1,relation_scope='view',relation_scope_ids=ids,
                                    relation_scope_sources=['google','massive'],relations_pending=False,relation_views=[entry])
        saved=self.store.save_snapshot(self.payload)
        result=Store(self.path).load_snapshot(saved['id'])
        self.assertEqual(result['view']['relation_views'],[entry])
        self.assertEqual(result['view']['render_budget'],2400)
        self.assertEqual(result['view']['selected_id'],ids[0])
        self.assertFalse(result['view']['relations_pending'])
        self.assertEqual(result['source_graphs'],self.store.load_snapshot(saved['id'])['source_graphs'])
        entry['ids']=['missing']
        with self.assertRaises(ValueError):self.store.save_snapshot(self.payload)

    def test_glow_snapshot_roundtrip_and_validation(self):
        self.payload['view']['glow']={'enabled':True,'brightness':1.4,'radius':52,'decay':.55,'background':.12}
        saved=self.store.save_snapshot(self.payload)
        result=Store(self.path).load_snapshot(saved['id'])
        self.assertEqual(result['view']['glow'],self.payload['view']['glow'])
        for key,value in [('brightness',float('nan')),('radius',500),('decay',1.1),('enabled','true')]:
            with self.subTest(key=key):
                changed={**self.payload,'view':{**self.payload['view'],'glow':{**self.payload['view']['glow'],key:value}}}
                with self.assertRaises(ValueError):self.store.save_snapshot(changed)

    def test_sculpted_time_profile_roundtrip_and_validation(self):
        focus={'enabled':True,'date':'2026-04-01','peak':2,'width':.12,'profile':[1+(i%12) for i in range(129)]}
        self.payload['view']['time_focus']=focus
        saved=self.store.save_snapshot(self.payload)
        self.assertEqual(Store(self.path).load_snapshot(saved['id'])['view']['time_focus'],focus)
        for invalid in [None,[],[2]*128,[2]*130,[True]*129,[float('inf')]*129,[float('nan')]*129,[.9]*129,[12.1]*129,{'0':2}]:
            changed={**self.payload,'view':{**self.payload['view'],'time_focus':{**focus,'profile':invalid}}}
            with self.subTest(profile=str(invalid)[:40]),self.assertRaises(ValueError):
                self.store.save_snapshot(changed)

    def test_time_focus_snapshot_roundtrip_and_validation(self):
        self.payload['view']['time_focus']={'enabled':True,'date':'2026-04-01','peak':9,'width':.08}
        saved=self.store.save_snapshot(self.payload)
        self.assertEqual(Store(self.path).load_snapshot(saved['id'])['view']['time_focus'],self.payload['view']['time_focus'])
        for invalid in [{'enabled':'yes'}, {'date':'2026-02-30'}, {'date':12}, {'date':'20260401'}, {'peak':13}, {'peak':True}, {'peak':float('nan')}, {'width':0}, {'width':.51}, []]:
            changed={**self.payload,'view':{**self.payload['view'],'time_focus':invalid}}
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):self.store.save_snapshot(changed)
        del self.payload['view']['time_focus']
        legacy=self.store.save_snapshot(self.payload)
        self.assertFalse(self.store.load_snapshot(legacy['id'])['view']['time_focus']['enabled'])
        self.payload['view']['time_focus']={'enabled':True,'date':'2026-04-01'}
        old_curve=self.store.save_snapshot(self.payload)
        self.assertEqual(self.store.load_snapshot(old_curve['id'])['view']['time_focus'],{'enabled':True,'date':'2026-04-01','peak':2,'width':.12})

    def test_wrong_source_and_dangling_edges_rejected_atomically(self):
        self.payload['source_graphs']['google']['articles'][0]['source']['provider']='yahoo'
        with self.assertRaises(ValueError):self.store.save_snapshot(self.payload)
        self.assertEqual(self.store.stats()['snapshots'],0)
        self.payload['source_graphs']['google']['articles'][0]['source']['provider']='google'
        self.payload['source_graphs']['google']['relations'][0]['source']='missing'
        with self.assertRaises(ValueError):self.store.save_snapshot(self.payload)
        self.assertEqual(self.store.stats()['snapshots'],0)

    def test_graph_keeps_independent_free_source_edges(self):
        payload=server.graph_payload([a for g in self.groups.values() for a in g['articles']])
        self.assertTrue(payload['source_graphs']['google']['relations'])
        self.assertTrue(payload['source_graphs']['massive']['relations'])

    def test_yahoo_keyword_is_preserved_in_rss_query(self):
        with patch.object(providers,'fetch',return_value=b'<rss><channel/></rss>') as fetch:
            providers.acquire('yahoo','battery research','',[('2026-01-01','2026-01-02')])
        from urllib.parse import urlsplit,parse_qs
        query=parse_qs(urlsplit(fetch.call_args.args[0]).query)['q'][0]
        self.assertIn('battery research',query)
        self.assertIn('site:finance.yahoo.com',query)

    def test_progress_distinguishes_cached_and_new_ids(self):
        existing=self.groups['massive']['articles'][0]
        new=self.groups['massive']['articles'][1]
        key=search.query_key('massive','TSLA')
        self.store.save('massive',key,[existing],[])
        events=[]
        def acquire(source,term,key,gaps,progress):
            progress({'phase':'fetching','article_ids':[existing['id'],new['id']],'requests':1})
            return providers.Batch(rows=[existing,new],windows=[('2026-01-01','2026-01-03','complete')])
        with patch.object(search,'acquire',side_effect=acquire):
            result=search.search_source('massive','','TSLA','key','2026-01-01','2026-01-03',self.store,progress=events.append)
        counts=next(e for e in events if isinstance(e,dict))
        self.assertEqual((counts['cached'],counts['new'],counts['total']),(1,1,2))
        self.assertEqual(result['cache']['new_articles'],1)

if __name__ == '__main__': unittest.main()
