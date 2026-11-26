"""L1 acceptance scenarios using the scheduler, a temporary stock DB and a scripted model."""
import tempfile
import unittest
from pathlib import Path

from news_atlas.storage import Store
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import capture, validate_proposal
from news_atlas.wiki.workbench import usage_summary
from news_atlas.wiki.opinions import node_evidence_and_lineage
from test_server import row
from test_wiki import proposal


def quote(article):
    return {'revision_id':article['revision_id'],'field':'title','quote':article['title']}


class L1Scenario(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service=WikiService(Store(Path(self.tmp.name)/'news.sqlite3'),start_worker=False)
        self.store=self.service.store('NASDAQ:NVDA')
        self.calls=[]
        self.respond=lambda a,c:proposal(a)

        def runner(store,job,article,context):
            self.calls.append(article)
            return {'proposal':self.respond(article,context),'usage':{'input_tokens':7}}
        self.service.runner=runner

    def ingest(self,article,**options):
        plan=self.service.plan({'instrument':self.store.instrument,'model':'fixture','articles':[article],**options})
        self.service.start({'plan_id':plan['plan_id']})
        self.service.process(self.store)
        job=self.store.jobs()[0]
        self.assertEqual(job['status'],'completed',job['error'])
        return job


class MemoryScenarios(L1Scenario):
    def thesis(self,action,base,title,reason):
        def result(article,context):
            p=proposal(article)
            if base:self.assertIn(base,[n['id'] for n in context])
            node=p['nodes'][0]
            node.update(kind='Thesis',title=title,summary=title,scope='NVDA',
                        assessment={'category':'uncertain','evidence':'supported','rationale':'The quotes describe the operating channel. Sales impact is open.'},
                        opinion_metadata={'claim_type':'hypothesis','horizon':'current quarter','conditions':[],'change_reason':reason},
                        lineage={'action':action,'compared_id':base})
            if action in ('extend','update'):
                p['relations']=[{'source':'n1','target':base,'type':'EXTENDS' if action=='extend' else 'UPDATES',
                                 'rationale':reason,'citations':[quote(article)]}]
            return p
        return result

    def test_given_a_thesis_then_branch_revise_and_open_a_distinct_topic(self):
        first='Rack deliveries depend on cooling capacity'
        self.respond=self.thesis('new_topic','',first,'A supplier reported a new cooling constraint.')
        self.ingest(row(title='NVDA supplier reports a cooling constraint',day='2026-01-02',suffix='first'))
        parent=next(n for n in self.store.graph()['nodes'] if n['kind']=='Thesis')
        self.assertEqual(parent['assessment']['evidence'],'supported')
        self.assertEqual(parent['assessment']['category'],'uncertain')
        self.respond=self.thesis('extend',parent['id'],'Cooling qualification may shift the mix of rack suppliers',
                                 'Qualification adds a supplier-mix question while the capacity constraint still applies.')
        job=self.ingest(row(title='Cooling supplier starts rack qualification',day='2026-01-03',suffix='branch'))
        self.assertEqual(job['payload']['last_decisions']['extended'],1)
        self.assertEqual(job['payload']['last_decisions']['new_topics'],0)
        graph=self.store.graph()
        child=next(n for n in graph['nodes'] if n.get('lineage',{}).get('action')=='extend')
        self.assertEqual(graph['histories'][parent['id']]['revision_count'],1)
        edge=next(e for e in graph['edges'] if e['relation_type']=='EXTENDS')
        import json,jsonschema
        schema=json.loads((Path(__file__).resolve().parents[1]/'schema/temporal-wiki.relation.schema.json').read_text())
        jsonschema.Draft202012Validator(schema,format_checker=jsonschema.FormatChecker()).validate(edge)
        self.respond=self.thesis('update',parent['id'],'Cooling capacity now covers planned rack deliveries',
                                 'New capacity removes the constraint for the planned deliveries.')
        self.ingest(row(title='NVDA supplier expands cooling capacity',day='2026-01-04',suffix='revision'))
        revised=next(n for n in self.store.graph()['nodes'] if n.get('lineage',{}).get('action')=='update')
        self.respond=self.thesis('new_topic',revised['id'],'Licensing terms may defer software renewals',
                                'Software renewals have a contractual driver independent of cooling capacity.')
        new=self.ingest(row(title='NVDA changes software renewal terms',day='2026-01-05',suffix='license'))
        self.assertEqual(new['payload']['last_decisions']['new_topics'],1)
        with self.store.connection() as db:
            links=lambda node,v:node_evidence_and_lineage(db,node,v)['lineage_links']
            self.assertEqual(links(parent,1),[])
            self.assertEqual([(l['id'],l['relation'],l['parent']) for l in links(parent,3)],
                             [(child['id'],'EXTENDS',False),(revised['id'],'UPDATES',False)])
            self.assertEqual([(l['id'],l['parent']) for l in links(child,3)],[(parent['id'],True)])
        graph=self.store.graph()
        self.assertEqual(graph['histories'][parent['id']]['revision_count'],2)
        self.assertEqual(graph['histories'][child['id']]['revision_count'],1)
        exported=self.store.markdown(lang='en')
        self.assertIn('## Viewpoint lineage',exported)
        self.assertIn(f"({child['id']} → {parent['id']})",exported)

    def test_given_two_proposals_for_the_same_child_then_keep_one_branch_with_both_sources(self):
        self.respond=self.thesis('new_topic','','New rack constraints','Cooling constrains deliveries.')
        self.ingest(row(title='Supplier reports cooling delays',suffix='original'))
        parent=next(n for n in self.store.graph()['nodes'] if n['kind']=='Thesis')
        self.respond=self.thesis('extend',parent['id'],'Qualification limits rack supply','Suppliers describe a separate qualification step.')
        self.ingest(row(title='Rack maker awaits qualification',day='2026-01-03',suffix='branch'))
        job=self.ingest(row(title='Buyer confirms rack qualification schedule',day='2026-01-04',suffix='corroborate'))
        graph=self.store.graph()
        child=next(n for n in graph['nodes'] if n.get('lineage',{}).get('action')=='extend')
        self.assertEqual(len([e for e in graph['edges'] if e['relation_type']=='EXTENDS']),1)
        self.assertEqual(len(child['corroborating_citations']),1)
        self.assertEqual(job['payload']['last_decisions']['reinforced'],1)
        self.assertEqual(job['payload']['last_decisions']['extended'],0)

    def test_given_a_prior_thesis_then_require_a_grounded_new_topic_or_one_matching_parent(self):
        article=capture(row())
        old={'id':'existing','kind':'Thesis','title':'Cooling','scope':'NVDA'}
        p=self.thesis('new_topic','','Rack orders','The supplier names a different bottleneck.')(article,[old])
        with self.assertRaisesRegex(ValueError,'closest supplied thesis'):
            validate_proposal(article,p,[old])
        p['nodes'][0]['lineage']={'action':'extend','compared_id':'existing'}
        with self.assertRaisesRegex(ValueError,'lineage relation'):
            validate_proposal(article,p,[old])
        p=self.thesis('extend','existing','Rack orders','Qualification delays extend the cooling thesis.')(article,[old])
        p['nodes'][0]['lineage']['action']='new_topic'
        with self.assertRaisesRegex(ValueError,'lineage action'):
            validate_proposal(article,p,[old])

    def test_given_two_feed_ids_for_one_original_then_link_without_a_second_turn(self):
        a=row(title='NVDA rack shipments accelerate',suffix='original')
        self.ingest(a)
        copy={**a,'id':'a'*24}
        job=self.ingest(copy)
        self.assertEqual(len(self.calls),1)
        self.assertTrue(job['payload']['last_decisions']['same_publication'])
        self.assertEqual(usage_summary(self.store)['calls'],1)
        self.assertEqual(job['done'],1)
        self.assertTrue(any(e['relation_type']=='RELATED_TO' for e in self.store.graph()['edges']))
        self.ingest({**copy,'summary':'The buyer has revised its schedule.'})
        self.assertEqual(len(self.calls),2)

    def test_given_fresh_corroboration_then_attach_quote_and_later_revise_without_rewriting_history(self):
        initial=row(title='NVDA rack shipments shifting to liquid cooling',suffix='first')
        self.ingest(initial)
        first=next(n for n in self.store.graph()['nodes'] if n['kind']=='Claim')
        later=row(title='Buyer confirms liquid cooling rack shipments',day='2026-01-03',suffix='confirm')
        new=capture(later)
        scoped=self.store.context({**new,'_evidence':[new],'_context_revisions':[new['revision_id']]})
        self.assertIn(first['id'],[n['id'] for n in scoped])
        self.assertNotIn(capture(initial)['revision_id'],[n['id'] for n in scoped])
        def corroborate(a,ctx):
            self.assertIn(first['id'],[n['id'] for n in ctx])
            return {'nodes':[],'relations':[{'source':a['revision_id'],'target':first['id'],'type':'SUPPORTS',
                    'rationale':'The buyer confirms the same shipment schedule.','citations':[quote(a)]}]}
        self.respond=corroborate
        job=self.ingest(later)
        self.assertEqual(job['payload']['last_decisions']['reinforced'],1)
        self.assertEqual(job['payload']['last_decisions']['created'],0)
        projected=next(n for n in self.store.graph(start='2026-01-03',end='2026-01-03')['nodes'] if n['id']==first['id'])
        self.assertEqual(projected['corroborating_citations'][0]['article_revision_id'],new['revision_id'])
        self.assertEqual(projected['citations'],first['citations'])
        def revise(a,ctx):
            p=proposal(a)
            p['relations']=[{'source':'n1','target':first['id'],'type':'UPDATES',
                             'rationale':'The buyer now postpones deliveries.','citations':[quote(a)]}]
            return p
        self.respond=revise
        revised=self.ingest(row(title='NVDA liquid cooling rack shipments postponed',day='2026-01-05',suffix='changed'))
        self.assertEqual(revised['payload']['last_decisions']['updated'],1)
        self.assertEqual([n for n in self.store.graph(version=1)['nodes'] if n['kind']=='Claim'],[first])
        self.assertEqual(len([n for n in self.store.graph()['nodes'] if n['kind']=='Claim']),2)

    def test_given_same_proposition_with_new_rationale_then_publish_one_identity(self):
        def repeat(a,c):
            p=proposal(a)
            p['nodes'][0].update(title='Rack deliveries',summary='Demand exceeds current rack supply.',
                                 assessment={'category':'direct','rationale':a['title']})
            return p
        self.respond=repeat
        self.ingest(row(title='Rack makers report orders',suffix='one'))
        job=self.ingest(row(title='Rack buyers confirm orders',day='2026-01-04',suffix='two'))
        self.assertEqual(job['payload']['last_decisions']['reused'],1)
        self.assertEqual(len([n for n in self.store.graph()['nodes'] if n['kind']=='Claim']),1)

    def test_given_unquoted_text_then_reject_even_an_attributed_claim(self):
        a=capture(row())
        p=proposal(a)
        p['nodes'][0]['citations'][0]['quote']='Invented certainty'
        with self.assertRaisesRegex(ValueError,'逐字'):
            validate_proposal(a,p,[])


class CompoundScenarios(L1Scenario):
    def test_given_vix_opt_in_then_only_prior_local_reports_can_support_a_joint_thesis(self):
        factor=lambda title,day:capture(row(title=title,day=day,suffix=day))
        observed=factor('VIX rose amid broad market repricing','2026-01-06')
        future=factor('VIX declined later','2026-01-09')
        stale=factor('VIX spike last month','2025-12-01')
        self.store.ingest([observed,future,stale])
        def joint(a,c):
            self.assertEqual([v['revision_id'] for v in a['_vix_news']],[observed['revision_id']])
            p=proposal(a)
            p['nodes'][0].update(kind='Thesis',title='NVDA deliveries during VIX repricing',citations=[quote(a),quote(observed)])
            return p
        self.respond=joint
        self.ingest(row(title='NVDA rack deliveries delayed',day='2026-01-08'),include_vix=True)
        graph=self.store.graph()
        thesis=next(n for n in graph['nodes'] if n['kind']=='Thesis')
        self.assertEqual(len(thesis['citations']),2)
        self.assertIn(observed['revision_id'],[n['id'] for n in graph['nodes']])
        self.assertEqual(len(self.store.known([observed,future,stale])),3)
        self.respond=lambda a,c:proposal(a)
        self.ingest(row(title='New stock filing',day='2026-01-10',suffix='solo'))
        self.assertNotIn('_vix_news',self.calls[-1])

    def test_given_only_a_vix_headline_then_reject_stock_conclusions_even_in_the_stock_feed(self):
        a=capture(row(title='VIX spikes at the open'))
        a.update(_vix_news=[],_stock_symbol='NVDA')
        p=proposal(a);p['nodes'][0].update(kind='Thesis',title='NVDA deliveries under a VIX spike')
        with self.assertRaisesRegex(ValueError,'quoted stock and VIX'):
            validate_proposal(a,p,[])

    def test_given_no_vix_quote_then_joint_thesis_fails_and_stock_only_claim_remains_valid(self):
        a=capture(row(title='NVDA changes its delivery schedule'))
        a['_vix_news']=[]
        p=proposal(a)
        validate_proposal(a,p,[])
        p['nodes'][0].update(kind='Thesis',title='NVDA weakness tracks VIX')
        with self.assertRaisesRegex(ValueError,'dated, quoted'):
            validate_proposal(a,p,[])

if __name__=='__main__':
    unittest.main()
