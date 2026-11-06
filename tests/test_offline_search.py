import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from news_atlas.model import article
from news_atlas.search import query_key, search_source
from news_atlas.storage import Store


class OfflineSearchTests(unittest.TestCase):
    def test_offline_returns_saved_news_even_with_gaps_and_force_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'test.sqlite3')
            row = article('google', 'Test news', 'https://example.com/news',
                          '2026-01-02T12:00:00Z', 'Example', '', [])
            store.save('google', query_key('google', 'TSLA'), [row], [])
            with patch.dict('os.environ', {'NEWS_ATLAS_CACHE_ONLY': '1'}), patch(
                'news_atlas.search.acquire', side_effect=AssertionError('Must not call provider')
            ):
                for ticker in ('TSLA', 'UNKNOWN'):
                    result = search_source('google', ticker, ticker, '',
                                           '2026-01-01', '2026-01-04', store,
                                           force_refresh=True)
                    self.assertEqual(len(result['articles']), 1 if ticker == 'TSLA' else 0)
                    self.assertEqual(result['cache']['network_requests'], 0)
                    self.assertTrue(result['cache']['offline'])
                    self.assertTrue(result['cache']['missing_ranges'])
                    self.assertTrue(result['warnings'])
