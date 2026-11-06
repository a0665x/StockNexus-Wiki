"""Regression checks for reusable pair work, including negative results and revisions."""
import tempfile
import unittest
from pathlib import Path
from test_server import row
from news_atlas.model import deduplicate, _build_relations
from news_atlas.relation_settings import settings, UNIFIED
from news_atlas.relation_cache import PairCache

class PairCacheTests(unittest.TestCase):
    def test_subset_growth_reopen_and_reorder(self):
        rows = deduplicate([row('google', suffix=str(i), symbols=['TSLA']) for i in range(9)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'pairs.sqlite3'
            with PairCache(path) as cache:
                expected = _build_relations(rows[:8])
                self.assertEqual(_build_relations(rows[:8], pair_cache=cache), expected)
                self.assertEqual(cache.computed, 28)
            with PairCache(path) as cache:
                self.assertEqual(_build_relations(rows[:4], pair_cache=cache), _build_relations(rows[:4]))
                self.assertEqual(cache.computed, 0)
                self.assertEqual(cache.hits, 6)
                self.assertEqual(_build_relations(rows, pair_cache=cache), _build_relations(rows))
                self.assertEqual(cache.computed, 8)
                self.assertEqual(_build_relations(rows[::-1], pair_cache=cache), _build_relations(rows[::-1]))
                self.assertEqual(cache.computed, 8)

    def test_negative_results_and_content_revision(self):
        rows = deduplicate([row('google', title='Unrelated weather', suffix='a'), row('google', title='Factory opens', suffix='b')])
        with tempfile.TemporaryDirectory() as tmp, PairCache(Path(tmp)/'pairs.sqlite3') as cache:
            self.assertEqual(_build_relations(rows, pair_cache=cache), [])
            self.assertEqual(_build_relations(rows, pair_cache=cache), [])
            self.assertEqual((cache.computed, cache.hits), (1, 1))
            rows[1]['title'] = rows[0]['title']
            self.assertEqual(_build_relations(rows, pair_cache=cache), _build_relations(rows))
            self.assertEqual(cache.computed, 2)

    def test_adaptive_and_neighbor_selection_reuse(self):
        rows = deduplicate([row('google', suffix=str(i), symbols=['TSLA']) for i in range(12)])
        with tempfile.TemporaryDirectory() as tmp, PairCache(Path(tmp)/'pairs.sqlite3') as cache:
            _build_relations(rows, pair_cache=cache)
            computed = cache.computed
            cfg = {**settings(), 'internal_neighbors': 1, 'coverage_first': True}
            self.assertEqual(_build_relations(rows, relation_settings=cfg, pair_cache=cache), _build_relations(rows, relation_settings=cfg))
            self.assertEqual(cache.computed, computed)
            self.assertEqual(_build_relations(rows, relation_settings=UNIFIED, pair_cache=cache), _build_relations(rows, relation_settings=UNIFIED))
            # The complete adaptive pass reuses the strict stage's pair evaluations.
            self.assertEqual(cache.computed, computed)

    def test_rule_change_invalidates_scores_and_cold_warm_match_mixed_data(self):
        rows=deduplicate([row('google' if i%2 else 'yahoo', title=['Tesla earnings grow','Weather in Taipei','Electric vehicle battery prices drop'][i%3], day=f'2026-01-{i+1:02d}', suffix=str(i), symbols=['TSLA'] if i%3==0 else []) for i in range(15)])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'pairs.sqlite3'
            with PairCache(path) as cache:
                for cfg in (settings(),{**settings(),'half_life':7},UNIFIED):
                    expected=_build_relations(rows,relation_settings=cfg)
                    before=cache.computed
                    self.assertEqual(_build_relations(rows,relation_settings=cfg,pair_cache=cache),expected)
                    self.assertGreater(cache.computed,before)
            with PairCache(path) as cache:
                for cross in (False,True):
                    for cfg in (settings(),{**settings(),'half_life':7},UNIFIED):
                        self.assertEqual(_build_relations(rows,relation_settings=cfg,cross_only=cross,pair_cache=cache),_build_relations(rows,relation_settings=cfg,cross_only=cross))
                self.assertEqual(cache.computed,0)
