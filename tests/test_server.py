import datetime as dt
import io
import json
from pathlib import Path
import tempfile
import time
import threading
import concurrent.futures
import types
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

from news_atlas import model, providers, search
from news_atlas.storage import Store
import server


def row(provider='massive', title='Tesla earnings grow', day='2026-01-02', suffix='one', symbols=None):
    return model.article(provider, title, 'https://example.com/' + suffix, day + 'T10:00:00Z', 'Publisher', '', symbols)

def payload(rows, next_url=None):
    data = {'status':'OK','results':[{'title':r['title'],'article_url':r['url'],'published_utc':r['published_at'], 'publisher':{'name':'Publisher'},'tickers':r['symbols']} for r in rows]}
    if next_url:
        data['next_url'] = next_url
    return json.dumps(data).encode()

class ModelTests(unittest.TestCase):
    def test_normalization(self):
        a = model.article('massive', '<b>Headline</b>', 'https://example.com/a?utm_source=x#hash', '2026-01-01T18:00:00+08:00', 'Publisher', '<p>Summary</p>', ['nvda','NVDA','bad symbol'])
        self.assertEqual(a['title'], 'Headline')
        self.assertEqual(a['url'], 'https://example.com/a')
        self.assertEqual(a['symbols'], ['NVDA'])
        self.assertEqual(a['published_at'], '2026-01-01T10:00:00Z')
        self.assertIsNone(model.article('google','x','javascript:alert(1)',None))
        self.assertIsNone(model.timestamp('not a date'))

    def test_free_and_paid_cross_language_relation_has_evidence(self):
        rows = model.deduplicate([row(symbols=['TSLA']), row('google','特斯拉宣布新款電動車上市',suffix='two')])
        self.assertEqual(next(r for r in rows if r['source']['provider']=='google')['symbols'], [])
        edges = model.build_relations(rows)
        self.assertEqual(len(edges), 1)
        evidence = edges[0]['evidence'][0]
        self.assertEqual(evidence['entity'], 'TSLA')
        self.assertEqual({evidence['source']['method'], evidence['target']['method']}, {'provider_ticker','text_alias'})

    def test_no_forced_query_or_source_relation(self):
        rows = model.deduplicate([row('google','Weather today in Taipei'),row('google','A new restaurant opens',suffix='two')])
        self.assertEqual(model.build_relations(rows), [])

    def test_topic_similarity(self):
        rows = model.deduplicate([row('google','Electric vehicle battery prices drop after new research'),row('yahoo','Electric vehicle battery prices drop in Europe',suffix='two')])
        self.assertEqual(model.build_relations(rows)[0]['type'], 'shared_topic')

    def test_relation_window_and_degree(self):
        rows = model.deduplicate([row(suffix=str(i),symbols=['TSLA']) for i in range(15)])
        counts = {}
        for edge in model.build_relations(rows):
            for key in ('source','target'):
                counts[edge[key]] = counts.get(edge[key],0) + 1
        self.assertLessEqual(max(counts.values()),6)
        distant = model.deduplicate([row(), row(day='2026-04-01',suffix='two')])
        self.assertEqual(model.build_relations(distant), [])

    def test_dedup_preserves_origins(self):
        rows = model.deduplicate([row('google'),row('massive',symbols=['TSLA'])])
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['origins']),2)
        self.assertEqual(rows[0]['entities'][0]['method'],'provider_ticker')

class ProviderTests(unittest.TestCase):
    def test_massive_pagination_and_bounds(self):
        page2 = 'https://api.massive.com:443/v2/reference/news?cursor=second&apiKey=secret'
        with patch.object(providers,'fetch',side_effect=[payload([row()],page2),payload([row(suffix='two')])]) as fetch:
            result = providers.acquire('massive','TSLA','secret',[('2026-01-01','2026-01-04')])
        self.assertEqual(len(result.rows),2)
        self.assertIn(('2026-01-01','2026-01-04','complete'),result.windows)
        params=urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args_list[0].args[0]).query)
        self.assertEqual(params['published_utc.gte'],['2026-01-01T00:00:00Z'])
        self.assertEqual(params['published_utc.lt'],['2026-01-04T00:00:00Z'])
        self.assertNotIn('apiKey', fetch.call_args_list[1].args[0])
        self.assertEqual(fetch.call_args_list[1].args[1]['Authorization'],'Bearer secret')

    def test_second_page_failure_keeps_first_without_coverage(self):
        with patch.object(providers,'fetch',side_effect=[payload([row(day='2026-01-01')],'https://api.massive.com/v2/reference/news?cursor=2'),providers.SourceError('rate_limit','429',60)]):
            result = providers.acquire('massive','TSLA','key',[('2026-01-01','2026-01-04')])
        self.assertEqual(len(result.rows),1)
        self.assertEqual(result.windows,[])
        self.assertEqual(result.error_code,'rate_limit')

    def test_partial_paging_records_only_finished_days(self):
        with patch.object(providers,'fetch',side_effect=[payload([row(day='2026-01-03')],'https://api.massive.com/v2/reference/news?cursor=2'),providers.SourceError('network','timeout')]):
            result = providers.acquire('massive','TSLA','key',[('2026-01-01','2026-01-05')])
        self.assertEqual(result.windows,[('2026-01-01','2026-01-03','complete')])
        self.assertEqual(result.error_code,'network')

    def test_pagination_external_host_rejected(self):
        with self.assertRaises(providers.SourceError):
            providers.next_massive_url('https://evil.example/steal?apiKey=secret')

    def test_missing_key_clear_error(self):
        result=providers.acquire('massive','TSLA','',[('2026-01-01','2026-01-04')])
        self.assertEqual(result.error_code,'missing_key')
        self.assertEqual(result.requests,0)

    def test_http_429_actionable(self):
        exc=urllib.error.HTTPError('https://api.massive.com',429,'Too Many',{'Retry-After':'15'},None)
        with patch('urllib.request.OpenerDirector.open',side_effect=exc):
            with self.assertRaises(providers.SourceError) as caught:
                providers.fetch('https://api.massive.com')
        self.assertEqual(caught.exception.code,'rate_limit')
        self.assertEqual(caught.exception.retry_after,15)

    def test_rss_snapshot_and_date_filter(self):
        xml=b'<rss><channel><item><title>Tesla news</title><link>https://example.com/a</link><pubDate>Fri, 02 Jan 2026 10:00:00 GMT</pubDate><source>Publisher</source></item><item><title>Unknown date</title><link>https://example.com/b</link></item></channel></rss>'
        with patch.object(providers,'fetch',return_value=xml):
            result=providers.acquire('google','Tesla','',[('2026-01-01','2026-01-04')])
        self.assertEqual(len(result.rows),1)
        self.assertEqual(result.windows,[('2026-01-01','2026-01-04','snapshot')])

    def test_capped_rss_day_not_covered(self):
        item='<item><title>Tesla</title><link>https://example.com/a</link><pubDate>Fri, 02 Jan 2026 10:00:00 GMT</pubDate></item>'
        with patch.object(providers,'fetch',return_value=('<rss><channel>'+item*100+'</channel></rss>').encode()):
            result=providers.acquire('google','Tesla','',[('2026-01-02','2026-01-03')])
        self.assertEqual(result.windows,[])
        self.assertTrue(result.warnings)

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'data'/'test.sqlite3'
        self.store=Store(self.path)
        self.key=search.query_key('massive','TSLA')
    def tearDown(self): self.tmp.cleanup()

    def test_restart_reuses_coverage_and_articles(self):
        self.store.save('massive',self.key,[row()],[('2026-01-01','2026-01-04','complete')])
        with patch.object(search,'acquire') as acquire:
            result=search.search_source('massive','','TSLA','', '2026-01-01','2026-01-04',Store(self.path))
        acquire.assert_not_called()
        self.assertEqual(len(result['articles']),1)
        self.assertTrue(result['cache']['reused'])

    def test_partial_overlap_only_fetches_missing_dates(self):
        self.store.save('massive',self.key,[row()],[('2026-01-02','2026-01-04','complete')])
        with patch.object(search,'acquire',return_value=providers.Batch(windows=[('2026-01-01','2026-01-02','complete'),('2026-01-04','2026-01-06','complete')])) as acquire:
            result=search.search_source('massive','','TSLA','key','2026-01-01','2026-01-06',self.store)
        self.assertEqual(acquire.call_args.args[3],[('2026-01-01','2026-01-02'),('2026-01-04','2026-01-06')])
        self.assertEqual(result['cache']['complete_days'],5)

    def test_article_dates_do_not_imply_coverage(self):
        self.store.save('massive',self.key,[row()],[])
        _,gaps=self.store.coverage('massive',self.key,'2026-01-01','2026-01-04')
        self.assertEqual(gaps,[('2026-01-01','2026-01-04')])

    def test_empty_complete_range_is_cached(self):
        self.store.save('massive',self.key,[],[('2026-01-01','2026-01-04','complete')])
        self.assertEqual(self.store.coverage('massive',self.key,'2026-01-01','2026-01-04')[1],[])

    def test_freshness_separates_history_and_today(self):
        now=dt.datetime(2026,1,3,12,tzinfo=dt.timezone.utc).timestamp()
        self.store.save('massive',self.key,[],[('2026-01-01','2026-01-04','complete')],now=now-600)
        _,gaps=self.store.coverage('massive',self.key,'2026-01-01','2026-01-04',now=now)
        self.assertEqual(gaps,[('2026-01-03','2026-01-04')])
        self.store.save('google','key',[],[('2026-01-01','2026-01-04','snapshot')],now=now-600)
        self.assertEqual(self.store.coverage('google','key','2026-01-01','2026-01-04',now=now)[1],[('2026-01-01','2026-01-04')])

    def test_failed_refresh_retains_cache_and_does_not_fill_gap(self):
        self.store.save('massive',self.key,[row()],[])
        with patch.object(search,'acquire',return_value=providers.Batch(error='network',error_code='network')):
            result=search.search_source('massive','','TSLA','key','2026-01-01','2026-01-04',self.store)
        self.assertEqual(len(result['articles']),1)
        self.assertEqual(result['cache']['complete_days'],0)
        self.assertTrue(result['cache']['missing_ranges'])

    def test_query_isolation_and_upsert(self):
        self.store.save('massive',self.key,[row(),row()],[])
        self.assertEqual(self.store.stats()['articles'],1)
        self.assertEqual(self.store.read('massive',search.query_key('massive','NVDA'),'2026-01-01','2026-01-04'),[])

    def test_force_refresh_and_no_key_persistence(self):
        self.store.save('massive',self.key,[row()],[('2026-01-01','2026-01-04','complete')])
        with patch.object(search,'acquire',return_value=providers.Batch()) as acquire:
            search.search_source('massive','','TSLA','DO_NOT_SAVE_THIS','2026-01-01','2026-01-04',self.store,True)
        acquire.assert_called_once()
        with self.store.connection() as db:
            dump='\n'.join(db.iterdump())
        self.assertNotIn('DO_NOT_SAVE_THIS',dump)

    def test_cooldown_prevents_repeat_rate_limit(self):
        self.store.record_attempt('massive',self.key,'2026-01-01','2026-01-04','rate_limit',60)
        with patch.object(search,'acquire') as acquire:
            result=search.search_source('massive','','TSLA','key','2026-01-01','2026-01-04',self.store)
        acquire.assert_not_called()
        self.assertEqual(result['error_code'],'rate_limit')

    def test_stream_returns_cache_then_status_and_result(self):
        self.store.save('massive',self.key,[row()],[('2026-01-01','2026-01-04','complete')])
        req=search.normalize_request({'query':'TSLA','ticker':'TSLA','sources':['massive'],'start':'2026-01-01','end':'2026-01-03'},today=dt.date(2026,1,4))
        events=list(server.search_events(req,'',self.store))
        self.assertEqual(events[0]['type'],'cache')
        self.assertEqual(len(events[0]['graph']['articles']),1)
        self.assertEqual(events[-1]['type'],'done')
        self.assertTrue(next(e for e in events if e['type']=='source')['cache']['reused'])

class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'test.sqlite3')
    def tearDown(self): self.tmp.cleanup()

    def request(self, method, path, body=None):
        payload=json.dumps(body).encode() if body is not None else b''
        raw=(f'{method} {path} HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\n\r\n').encode()+payload
        class Connection:
            output=b''
            def makefile(self, *args): return io.BytesIO(raw)
            def sendall(self, data): self.output+=data
        connection=Connection()
        with patch.object(server.Handler,'log_message'):
            server.Handler(connection,('127.0.0.1',1234),types.SimpleNamespace(store=self.store))
        head,data=connection.output.split(b'\r\n\r\n',1)
        return head,data

    def test_every_script_referenced_by_homepage_is_served(self):
        from html.parser import HTMLParser
        class Scripts(HTMLParser):
            sources = None
            def __init__(self):
                super().__init__()
                self.sources = []
            def handle_starttag(self, tag, attrs):
                src = dict(attrs).get('src')
                if tag == 'script' and src:
                    self.sources.append(src)
        head, html = self.request('GET', '/')
        self.assertIn(b'200 OK', head)
        parser = Scripts()
        parser.feed(html.decode())
        self.assertTrue(parser.sources)
        for src in parser.sources:
            with self.subTest(src=src):
                head, content = self.request('GET', src)
                self.assertIn(b'200 OK', head, 'Homepage dependency is unreachable: '+src)
                self.assertIn(b'text/javascript', head)
                self.assertTrue(content)

    def test_header_serves_replaceable_png(self):
        _, html = self.request('GET', '/')
        self.assertIn(b'src="/stocknexus-wiki.png" alt="StockNexus Wiki"', html)
        head, data = self.request('GET', '/stocknexus-wiki.png')
        self.assertIn(b'200 OK', head)
        self.assertIn(b'Content-Type: image/png', head)
        self.assertIn(b'Cache-Control: no-cache', head)
        self.assertEqual(data, (Path(server.__file__).parent/'dist/stocknexus-wiki.png').read_bytes())

    def test_explorer_assets_and_schema_are_served(self):
        for path in ['/i18n.js','/explorer-ui.js','/timeline.js','/date-range.js','/interaction.js','/schema/news-atlas.schema.json']:
            head,data=self.request('GET',path)
            self.assertIn(b'200 OK',head)
            self.assertTrue(data)
        schema=json.loads(data)
        self.assertEqual(schema['$defs']['exploration']['properties']['depth']['maximum'],6)

    def test_actual_handler_streams_cached_graph_without_socket(self):
        key=search.query_key('massive','TSLA')
        self.store.save('massive',key,[row()],[('2026-01-01','2026-01-04','complete')])
        head,data=self.request('POST','/api/search',{'query':'TSLA','ticker':'TSLA','sources':['massive'],'start':'2026-01-01','end':'2026-01-03'})
        self.assertIn(b'200 OK',head)
        events=[json.loads(line) for line in data.splitlines()]
        self.assertEqual(events[0]['type'],'cache')
        self.assertEqual(events[-1]['type'],'done')
        source=next(e for e in events if e['type']=='source')
        self.assertEqual(source['graph']['articles'][0]['title'],'Tesla earnings grow')

    def test_channel_http_create_classify_update_delete(self):
        head,data=self.request('POST','/api/channels',{'name':'Robot news','keywords':['humanoid'],'match':'any'})
        self.assertIn(b'200 OK',head)
        created=json.loads(data)['channel']
        head,data=self.request('POST','/api/classify',{'articles':[{'id':'news','title':'Humanoid production orders','summary':''}]})
        annotation=json.loads(data)['annotations'][0]
        self.assertIn(created['id'],[c['id'] for c in annotation['channels']])
        self.assertEqual(annotation['id'],'news')
        head,data=self.request('POST','/api/channels',{**created,'keywords':['robot']})
        self.assertEqual(json.loads(data)['channel']['keywords'],['robot'])
        head,data=self.request('DELETE','/api/channels/'+created['id'])
        self.assertIn(b'200 OK',head)
        self.assertFalse(any(c['id']==created['id'] for c in json.loads(data)['channels']))
        head,_=self.request('DELETE','/api/channels/production')
        self.assertIn(b'404 Not Found',head)

    def test_classify_rejects_malformed_data(self):
        head,_=self.request('POST','/api/classify',{'articles':[{'title':42}]})
        self.assertIn(b'400 Bad Request',head)

    def test_snapshot_http_roundtrip(self):
        articles=model.deduplicate([row('google')])
        payload={'name':'saved','search':{'query':'Tesla'},'view':{'sources':['google'],'separate':True,'positions':[]},'source_graphs':{'google':{'articles':articles,'relations':[]}},'cross_relations':[]}
        head,data=self.request('POST','/api/snapshots',payload)
        self.assertIn(b'201 Created',head)
        ident=json.loads(data)['id']
        head,data=self.request('GET','/api/snapshots/'+ident)
        self.assertIn(b'200 OK',head)
        self.assertEqual(json.loads(data)['source_graphs']['google']['articles'],articles)
        head,data=self.request('GET','/api/snapshots')
        self.assertEqual(json.loads(data)['snapshots'][0]['id'],ident)

    def test_actual_handler_rejects_bad_source(self):
        head,data=self.request('POST','/api/search',{'query':'TSLA','sources':[{}]})
        self.assertIn(b'400 Bad Request',head)
        self.assertIn('error',json.loads(data))

    def test_database_not_served(self):
        head,_=self.request('GET','/data/news-atlas.sqlite3')
        self.assertIn(b'404 Not Found',head)

    def test_concurrent_identical_search_fills_once(self):
        entered=threading.Event()
        release=threading.Event()
        def acquire(*args):
            entered.set()
            release.wait(timeout=2)
            return providers.Batch(rows=[row()],windows=[('2026-01-01','2026-01-04','complete')])
        with patch.object(search,'acquire',side_effect=acquire) as call, concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            def run(): return search.search_source('massive','','TSLA','key','2026-01-01','2026-01-04',self.store)
            first=pool.submit(run)
            self.assertTrue(entered.wait(timeout=2))
            second=pool.submit(run)
            release.set()
            self.assertEqual(len(first.result()['articles']),1)
            self.assertEqual(len(second.result()['articles']),1)
            self.assertEqual(call.call_count,1)

class InputTests(unittest.TestCase):
    def test_ticker_is_explicit(self):
        req=search.normalize_request({'query':'Tesla','ticker':'tsla','sources':['massive','google']})
        self.assertEqual(req['ticker'],'TSLA')
    def test_keywords_not_claimed_to_be_tickers(self):
        with self.assertRaises(ValueError): search.normalize_request({'query':'electric vehicle','sources':['massive']})
    def test_invalid_sources_and_date_ranges(self):
        for body in ({'query':'TSLA','sources':[{}]}, {'query':'TSLA','ticker':'TSLA','sources':['massive'],'start':'2026-02-02','end':'2026-01-01'}):
            with self.assertRaises(ValueError): search.normalize_request(body)

if __name__ == '__main__': unittest.main()
