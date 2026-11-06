import datetime as dt
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from news_atlas import model, providers, search
from news_atlas.storage import Store
import server

class YearBoundaryTests(unittest.TestCase):
    def test_graph_retains_all_articles_across_years(self):
        rows=[model.article('google','headline '+str(i),'https://example.test/'+str(i),'2026-10-01T00:00:00Z') for i in range(801)]
        rows.append(model.article('google','older headline','https://example.test/old','2025-11-03T00:00:00Z'))
        with patch('news_atlas.graph_payload.build_relations',return_value=[]):
            graph=server.graph_payload(rows)
        for selected in [graph['articles'],graph['source_graphs']['google']['articles']]:
            self.assertEqual(len(selected),len(rows))
            self.assertEqual({r['published_at'][:4] for r in selected},{'2025','2026'})

    def test_inclusive_year_end_and_utc_storage(self):
        req=search.normalize_request({'query':'boundary','sources':['google'],'start':'2025-12-31','end':'2026-01-01'},today=dt.date(2026,11,2))
        self.assertEqual((req['start'],req['end']),('2025-12-31','2026-01-02'))
        stamps=['2026-01-01T00:30:00+08:00','2025-12-31T23:30:00-05:00','2026-01-02T00:00:00Z']
        rows=[model.article('google','boundary',f'https://example.test/{i}',s) for i,s in enumerate(stamps)]
        self.assertEqual([r['published_at'] for r in rows],['2025-12-31T16:30:00Z','2026-01-01T04:30:00Z','2026-01-02T00:00:00Z'])
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.sqlite3')
            store.save('google','boundary',rows,[(req['start'],req['end'],'snapshot')])
            result=store.read('google','boundary',req['start'],req['end'])
            self.assertEqual({r['id'] for r in result},{r['id'] for r in rows[:2]})
            self.assertEqual(store.coverage('google','boundary',req['start'],req['end'])[1],[])

    def test_rss_cross_year_request_and_exact_bounds(self):
        xml=b'<rss><channel><item><title>old year</title><link>https://example.test/old</link><pubDate>Wed, 31 Dec 2025 16:00:00 GMT</pubDate></item><item><title>new year</title><link>https://example.test/new</link><pubDate>Thu, 01 Jan 2026 04:00:00 GMT</pubDate></item><item><title>outside</title><link>https://example.test/out</link><pubDate>Fri, 02 Jan 2026 00:00:00 GMT</pubDate></item></channel></rss>'
        from urllib.parse import urlsplit,parse_qs
        for source in ('google','yahoo'):
            with patch.object(providers,'fetch',return_value=xml) as fetch:
                result=providers.acquire(source,'boundary','',[('2025-12-31','2026-01-02')],rss_region='TW')
            self.assertIsNone(result.error)
            self.assertEqual({r['published_at'][:4] for r in result.rows},{'2025','2026'})
            q=parse_qs(urlsplit(fetch.call_args.args[0]).query)['q'][0]
            self.assertIn('after:2025-12-30 before:2026-01-03',q)

    def test_long_rss_queries_visit_all_months_before_dense_splits(self):
        from urllib.parse import urlsplit,parse_qs
        requests=[]
        def fetch(url,*args):
            q=parse_qs(urlsplit(url).query)['q'][0];requests.append(q)
            item='<item><title>headline</title><link>https://example.test/item</link><pubDate>Mon, 03 Nov 2025 12:00:00 GMT</pubDate></item>'
            return ('<rss><channel>'+item*100+'</channel></rss>').encode()
        with patch.object(providers,'fetch',side_effect=fetch):
            result=providers.acquire('google','NVDA','',[('2025-11-03','2026-11-03')])
        self.assertEqual(result.requests,12)
        self.assertEqual(result.error_code,'limit')
        self.assertTrue(any('after:2026-10' in q for q in requests),requests)
        self.assertEqual(result.windows,[],'capped windows must not claim coverage')

    def test_massive_cross_year_pagination_and_parameters(self):
        import json
        from urllib.parse import urlsplit,parse_qs
        def page(stamp,url,next_url=None):
            return json.dumps({'status':'OK','results':[{'title':'boundary','article_url':url,'published_utc':stamp}],**({'next_url':next_url} if next_url else {})}).encode()
        with patch.object(providers,'fetch',side_effect=[page('2025-12-31T23:59:59Z','https://example.test/old','https://api.massive.com/v2/reference/news?cursor=two'),page('2026-01-01T00:00:00Z','https://example.test/new')]) as fetch:
            result=providers.acquire('massive','NVDA','test-key',[('2025-12-31','2026-01-02')])
        self.assertEqual({r['published_at'][:4] for r in result.rows},{'2025','2026'})
        self.assertIn(('2025-12-31','2026-01-02','complete'),result.windows)
        q=parse_qs(urlsplit(fetch.call_args_list[0].args[0]).query)
        self.assertEqual(q['published_utc.gte'],['2025-12-31T00:00:00Z'])
        self.assertEqual(q['published_utc.lt'],['2026-01-02T00:00:00Z'])
        self.assertEqual(q['order'],['asc'])
