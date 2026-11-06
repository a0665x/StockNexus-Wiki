import json,tempfile,unittest
from pathlib import Path
from news_atlas.storage import Store
from news_atlas.workspace import read,save
from news_atlas.search import normalize_request
from news_atlas.wiki.store import capture,validate_proposal
from test_server import row
import test_wiki

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=Store(Path(self.tmp.name)/'news.sqlite3')
    def test_independent_states_survive_new_store_and_credentials_rejected(self):
        save(self.store,'news',{'draft':{'ticker':'NASDAQ:GOOGL','query':'GOOGL, AI'}})
        save(self.store,'wiki',{'instrument':'NASDAQ:GOOGL','controls':{'wikiModel':'gpt-6.1-sol|high','wikiStrategy':'root'}})
        other=Store(self.store.path);state=read(other)
        self.assertEqual(state['news']['draft']['ticker'],'NASDAQ:GOOGL')
        self.assertEqual(state['wiki']['controls']['wikiModel'],'gpt-6.1-sol|high')
        with self.assertRaises(ValueError):save(other,'news',{'draft':{'massive_key':'secret'}})
        with self.assertRaises(ValueError):save(other,'wiki',{'controls':{'key':'secret'}})
        save(other,'wiki',{'controls':{'wikiModel':'fixture|low'}})
        self.assertEqual(read(other)['news'],state['news'])
    def test_wiki_pane_dimensions_persist_and_validate(self):
        layout={'left':350,'right':410,'bottom':320}
        save(self.store,'wiki',{'instrument':'NASDAQ:TSLA','layout':layout})
        self.assertEqual(read(Store(self.store.path))['wiki']['layout'],layout)
        for invalid in ({'left':True},{'bottom':float('nan')},{'right':float('inf')},{'left':100},{'right':900},{'bottom':0},{'extra':280},[]):
            with self.subTest(layout=invalid),self.assertRaises(ValueError):
                save(self.store,'wiki',{'layout':invalid})
        self.assertEqual(read(self.store)['wiki']['layout'],layout)

    def test_exchange_symbol_routes_to_existing_provider_symbol(self):
        req=normalize_request({'instrument':'NASDAQ:GOOGL','ticker':'GOOGL','sources':['google'],'query':''})
        self.assertEqual((req['instrument'],req['ticker'],req['query']),('NASDAQ:GOOGL','GOOGL','GOOGL'))
        with self.assertRaises(ValueError):normalize_request({'instrument':'NASDAQ:GOOGL','ticker':'TSLA','sources':['google']})
    def test_cross_article_link_requires_quotes_at_both_endpoints(self):
        a=capture(row(title='Tesla earnings rose'));b=capture(row(title='Tesla earnings follow-up',suffix='two'))
        article={**a,'_related_articles':[b]}
        ctx=[{'id':b['revision_id'],'kind':'ArticleRevision','scope':'NASDAQ:TSLA'}]
        quote=lambda x:{'revision_id':x['revision_id'],'field':'title','quote':x['title']}
        relation={'source':a['revision_id'],'target':b['revision_id'],'type':'RELATED_TO','rationale':'Same earnings report follow-up','citations':[quote(a),quote(b)]}
        ns,es=validate_proposal(article,{'nodes':[],'relations':[relation]},ctx)
        self.assertEqual(len(es),1);self.assertEqual(ns,[])
        with self.assertRaises(ValueError):validate_proposal(article,{'nodes':[],'relations':[{**relation,'citations':[quote(a)]}]},ctx)
        with self.assertRaises(ValueError):validate_proposal(article,{'nodes':[],'relations':[{**relation,'type':'SUPPORTS'}]},ctx)

class RetentionTests(unittest.TestCase):
    setUp=test_wiki.WikiTests.setUp
    def test_only_ten_checkpoints_selectable_but_original_evidence_survives(self):
        first=None
        for i in range(12):
            p=self.service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':[row(suffix=str(i))]})
            self.service.start({'plan_id':p['plan_id']});self.service.tick()
            if first is None:first=self.store.graph()['nodes'][0]['id']
        g=self.store.graph();self.assertEqual(len(g['versions']),10)
        self.assertIn(first,{n['id'] for n in g['nodes']})
        with self.assertRaises(ValueError):self.store.graph(version=1)
        self.assertEqual(self.store.graph(version=3)['version'],3)
