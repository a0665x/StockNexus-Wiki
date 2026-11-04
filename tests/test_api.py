import json
from unittest.mock import patch
import unittest
import test_server
from test_server import row
from news_atlas import exploration, search
from news_atlas.openapi import specification

class APIContractTests(unittest.TestCase):
    setUp=test_server.HTTPTests.setUp
    tearDown=test_server.HTTPTests.tearDown
    request=test_server.HTTPTests.request
    def post(self,path,body):
        head,data=self.request('POST',path,body)
        self.assertIn(b'200 OK',head,data)
        return json.loads(data)

    def test_all_articles_rebuild_classify_and_snapshot_over_old_limit(self):
        from news_atlas.model import article
        from news_atlas.relation_settings import DEFAULTS
        rows=[article('google','Archive item',f'https://example.test/full/{i}','2025-12-31T23:30:00Z') for i in range(1001)]
        graph=self.post('/api/graph/build',{'articles':rows,'relation_settings':{**DEFAULTS,'entity':False,'topic':False,'title':False}})
        self.assertEqual(len(graph['articles']),1001)
        self.assertIsNone(graph['display_limit'])
        classified=self.post('/api/classify',{'articles':rows*3})
        self.assertEqual(len(classified['annotations']),3003)
        body={'view':{'sources':['google'],'separate':False},'source_graphs':{'google':graph['source_graphs']['google']},'search':{}}
        head,data=self.request('POST','/api/snapshots',body)
        self.assertIn(b'201',head)
        restored=self.store.load_snapshot(json.loads(data)['id'])
        self.assertEqual(len(restored['source_graphs']['google']['articles']),1001)

    def test_contract_and_local_docs(self):
        spec=specification();names=[]
        for path,methods in spec['paths'].items():
            for method,op in methods.items():
                names.append(op['operationId']);self.assertIn('x-mcp',op)
        self.assertEqual(len(names),len(set(names)))
        self.assertEqual(len(names),30)
        self.assertIn('preview_graph',names)
        self.assertEqual(spec['paths']['/api/chat/turn']['post']['security'],[{'ChatSession':[]}])
        self.assertIn('application/x-ndjson',spec['paths']['/api/chat/turn']['post']['responses']['200']['content'])
        def walk(v):
            if isinstance(v,dict):
                if '$ref' in v:
                    node=spec
                    for part in v['$ref'].split('/')[1:]: node=node[part]
                for child in v.values(): walk(child)
            elif isinstance(v,list):
                for child in v: walk(child)
        walk(spec)
        for path in ['/docs','/openapi.json','/api/capabilities','/api/schema','/vendor/swagger-ui-bundle.js','/vendor/swagger-ui.css']:
            head,data=self.request('GET',path);self.assertIn(b'200 OK',head);self.assertTrue(data)

    def test_normalize_build_filter_timeline_and_no_write(self):
        before=self.store.stats()
        raw=[{'provider':p,'title':'Tesla earnings revenue','url':'https://example.com/'+p,'published_at':'2026-01-02T10:00:00Z'} for p in ['google','yahoo']]
        normalized=self.post('/api/normalize',{'articles':raw})
        self.assertEqual(len(normalized['articles']),2)
        graph=self.post('/api/graph/build',{'articles':normalized['articles']})
        self.assertTrue(graph['cross_relations'])
        filtered=self.post('/api/graph/filter',{'graph':graph,'filters':{'sources':['yahoo']}})
        self.assertEqual(len(filtered['articles']),1);self.assertEqual(filtered['relations'],[])
        timeline=self.post('/api/timeline',{'graph':graph})
        self.assertEqual(sum(b['count'] for b in timeline['buckets']),2)
        self.assertEqual(self.store.stats(),before)
        rejected=self.post('/api/normalize',{'articles':[dict(raw[0],published_at='invalid')]})
        self.assertEqual(len(rejected['rejected']),1)

    def test_forest_ranking_shared_nodes_and_roots_are_barriers(self):
        graph={'articles':[{'id':k,'title':title,'summary':'','source':{'provider':'google'}} for k,title in [('a','Tesla earnings'),('b','Tesla production'),('c','Other'),('d','XTesla')]],'relations':[{'id':a+b,'source':a,'target':b,'weight':.9} for a,b in [('a','b'),('a','c'),('b','c')]]}
        result=self.post('/api/graph/explore',{'graph':graph,'query':'Tesla','limit':2})
        self.assertEqual([r['id'] for r in result['roots']],['a','b'])
        self.assertEqual(result['matched_articles'],2)
        self.assertEqual(result['shared_nodes'],[{'id':'c','root_ids':['a','b']}])
        for tree in result['trees']:
            self.assertEqual(tree['nodes'][0]['depth'],0)
            self.assertNotIn('ab',tree['edge_ids'])
        chinese=exploration.rank_roots([dict(graph['articles'][0],title='台積電財報')],'台積電',1)
        self.assertEqual(chinese[1],1)
        result=self.post('/api/graph/explore',{'graph':graph,'root_ids':['a'],'exploration':{'pathMin':.95}})
        self.assertEqual(len(result['trees'][0]['nodes']),1)
        for body in [{'graph':graph,'query':'Tesla','limit':11},{'graph':graph,'root_ids':['missing']},{'graph':graph,'query':'Tesla','exploration':{'depth':7}}]:
            head,_=self.request('POST','/api/graph/explore',body);self.assertIn(b'400',head)

    def test_cache_only_and_single_json_search_and_observations(self):
        a=row();key=search.query_key('massive','TSLA')
        self.store.save('massive',key,[a],[('2026-01-01','2026-01-04','complete')])
        request={'ticker':'TSLA','sources':['massive'],'start':'2026-01-01','end':'2026-01-03'}
        with patch('news_atlas.search.acquire',side_effect=AssertionError('No network')):
            cached=self.post('/api/cache/graph',request)
            self.assertEqual(cached['network_requests'],0)
            self.assertEqual(cached['coverage']['massive']['missing_ranges'],[])
            result=self.post('/api/search/result',request)
            self.assertFalse(result['partial']);self.assertEqual(len(result['graph']['articles']),1)
        head,data=self.request('GET','/api/articles/'+a['id']);self.assertIn(b'200',head);self.assertEqual(json.loads(data)['articles'][0]['id'],a['id'])

    def test_focus_snapshot_roundtrip(self):
        from server import graph_payload
        graph=graph_payload([row()]);ident=graph['articles'][0]['id']
        body={'source_graphs':{'massive':graph['source_graphs']['massive']},'view':{'sources':['massive'],'separate':False,'focus':{'mode':'keyword','root_ids':[ident],'query':'Tesla','limit':3}}}
        clean=self.post('/api/view/validate',body)
        self.assertEqual(clean['view']['focus'],body['view']['focus']);self.assertEqual(self.store.stats()['snapshots'],0)
        head,data=self.request('POST','/api/snapshots',body);self.assertIn(b'201',head)
        saved=json.loads(data);_,data=self.request('GET','/api/snapshots/'+saved['id']);self.assertEqual(json.loads(data)['view']['focus'],body['view']['focus'])
        body['view']['focus']['root_ids']=['missing'];head,_=self.request('POST','/api/view/validate',body);self.assertIn(b'400',head)

    def test_malformed_graph_returns_400(self):
        graph={'articles':[{'id':'a','title':'Tesla','source':{'provider':'google'},'published_at':{}}],'relations':[]}
        for path in ['/api/graph/explore','/api/graph/filter','/api/timeline']:
            head,_=self.request('POST',path,{'graph':graph,'query':'Tesla'});self.assertIn(b'400',head)

    def test_browser_and_api_rank_identically(self):
        import subprocess
        rows=[{'id':'a','title':'NVIDIA robot launch','summary':'robot','symbols':['NVDA'],'source':{'provider':'massive'}},{'id':'b','title':'台積電晶片','summary':'','source':{'provider':'google'}},{'id':'c','title':'Robotics plans','summary':'robot platform','source':{'provider':'yahoo'}}]
        for query in ['robot','ＮＶＤＡ','台積電','zzzz','robot NVIDIA']:
            expected,total=exploration.rank_roots(rows,query,3)
            output=subprocess.check_output(['node','-e',"const v=require('./dist/graph-view.js');console.log(JSON.stringify(v.rankRoots(JSON.parse(process.argv[1]),process.argv[2],3)))",json.dumps(rows),query],text=True)
            actual=json.loads(output);self.assertEqual(actual['roots'],expected);self.assertEqual(actual['matched_articles'],total)
