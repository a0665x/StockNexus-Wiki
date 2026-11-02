import copy
import unittest
from unittest.mock import patch
from news_atlas import model, channels

class FeatureCacheTests(unittest.TestCase):
    def test_enrichment_preserves_evidence_and_current_metadata(self):
        row=model.article('google','NVIDIA AI earnings 晶片','https://example.test/a','2026-01-01T00:00:00Z',summary='Apple and NVIDIA shares',symbols=['NVDA'])
        expected=model._enrich(row)
        model._enrichment.cache_clear()
        self.assertEqual(model.enrich(row),expected)
        changed={**row,'fetched_at':'later'}
        with patch.object(model,'_enrich',side_effect=AssertionError('recomputed')):
            result=model.enrich(changed)
        self.assertEqual(result,{**expected,'fetched_at':'later'})
        result['entities'].clear()
        self.assertEqual(model.enrich(row),expected)
        changed={**row,'title':'Tesla car','summary':'','symbols':['TSLA']}
        self.assertEqual(model.enrich(changed),model._enrich(changed))

    def test_classification_content_and_definitions_invalidate(self):
        row={'title':'NVIDIA earnings 股票','summary':'supply chain'}
        defs=channels.definitions();expected=channels._classify(row,defs)
        channels._classification.cache_clear()
        self.assertEqual(channels.classify(row,defs),expected)
        with patch.object(channels,'_classify',side_effect=AssertionError('recomputed')):
            result=channels.annotate([{**row,'id':'new'}],defs)[0]
        result['channels'].clear()
        self.assertEqual(channels.classify(row,defs),expected)
        modified=copy.deepcopy(defs);modified[0]['keywords']=['NVIDIA']
        self.assertEqual(channels.classify(row,modified),channels._classify(row,modified))
        changed={**row,'title':'unmatched','summary':''}
        self.assertEqual(channels.classify(changed,defs),channels._classify(changed,defs))
