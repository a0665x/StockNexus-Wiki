"""BDD: one classification vocabulary, immutable history, no paid relabel on additions."""
import copy, unittest
import test_research
from news_atlas.wiki import classifier
from news_atlas.wiki.research import taxonomy
from news_atlas.wiki.store import now

class TaxonomyViewTests(unittest.TestCase):
    setUp=test_research.ResearchTests.setUp
    add=test_research.ResearchTests.add

    def test_quality_terms_describe_analysis_without_asserting_false_news(self):
        with self.store.connection() as db:terms={t['id']:t for t in taxonomy(db)['terms']}
        self.assertIn('analysis.noise',terms)
        self.assertIn('analysis.fact_check',terms)
        self.assertIn('不代表',terms['analysis.fact_check']['definition'])
        self.assertEqual(terms['analysis.fact_check']['facet'],'analysis_dimension')

    def test_additive_terms_reuse_exact_old_assignments_without_rewriting_history(self):
        with self.store.connection() as db:
            old=taxonomy(db);before=classifier.assignments(db,old['revision_id'])
        cutoff=now();terms=copy.deepcopy(old['terms']);extra=copy.deepcopy(terms[-1]);extra.update(id='analysis.new_angle',label='New angle');terms.append(extra)
        new=self.research.update_taxonomy({'expected_revision':old['revision_id'],'terms':terms})
        with self.store.connection() as db:
            reused=classifier.assignments(db,new['revision_id'])
            self.assertEqual(set(reused),set(before))
            for ident,a in reused.items():
                self.assertEqual(a['taxonomy_revision'],old['revision_id'])
                self.assertEqual(a['assignments'],before[ident]['assignments'])
                self.assertIn('analysis.new_angle',a['unassessed_term_ids'])
            self.assertEqual(classifier.assignments(db,old['revision_id']),before)
        _,bundle,_=self.research.prepare({'query':'overview'})
        self.assertTrue(bundle['assignments'])
        self.assertTrue(all(a['taxonomy_revision']==old['revision_id'] for a in bundle['assignments']))
        self.assertIn('analysis.new_angle',bundle['manifest']['unassessed_term_ids'])
        self.assertEqual(classifier.enqueue(self.store,'fixture','high')['status'],'unchanged')
        self.assertEqual(self.store.graph(as_of=cutoff)['taxonomy']['revision_id'],old['revision_id'])
        changed=copy.deepcopy(new['terms']);changed[0]['definition']+=' changed meaning'
        revised=self.research.update_taxonomy({'expected_revision':new['revision_id'],'terms':changed})
        with self.store.connection() as db:self.assertEqual(classifier.assignments(db,revised['revision_id']),{})

    def test_chart_index_counts_opinion_roots_and_uses_the_model_labels(self):
        self.add('Unrelated title','b')
        graph=self.store.graph();index=graph['opinion_index'];nodes={n['id']:n for n in graph['nodes']}
        self.assertEqual({n['id'] for n in index},set(graph['opinion_groups']))
        self.assertTrue(index)
        for n in index:
            self.assertNotEqual(nodes[n['id']]['kind'],'ArticleRevision')
            self.assertEqual(n['classification_terms'],nodes[n['id']]['classification_terms'])
            self.assertTrue(n['dates'])
            self.assertNotIn('category',n)
