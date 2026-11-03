#!/usr/bin/env python3
"""Local News Atlas HTTP server; opt-in credentials stay outside news DBs."""
import concurrent.futures
import datetime as dt
import json
import os
import queue
import signal
import itertools
import functools
import logging
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from news_atlas.model import SCHEMA_VERSION, article, clean, timestamp, deduplicate, build_relations
from news_atlas.search import normalize_request, query_key, search_source
from news_atlas.storage import Store
from news_atlas import api, credentials, chat_proxy, price_lens
from news_atlas.graph_cache import build_cached, lookup_cached
from news_atlas.openapi import specification
from news_atlas.channels import definitions, annotate, classify, version as channel_version

cache_logger=logging.getLogger('news_atlas.graph_cache')
cache_logger.setLevel(logging.INFO)
if not cache_logger.handlers:
    cache_logger.addHandler(logging.StreamHandler())

ROOT = Path(__file__).resolve().parent


def graph_payload(rows, channels=None, relation_settings=None, include_relations=True):
    from news_atlas.relation_settings import settings
    cfg=settings(relation_settings)
    stage_times={}
    def relations_for(label, subset, cross_only=False):
        tick=time.perf_counter()
        result=build_relations(subset,cross_only=cross_only,relation_settings=cfg)
        stage_times[label]=round((time.perf_counter()-tick)*1000,2)
        return result
    channels = channels or definitions()
    all_rows = annotate(deduplicate(rows), channels)
    shown = all_rows
    source_graphs = {}
    for provider in ('google', 'yahoo', 'massive'):
        own = annotate(deduplicate([r for r in rows if r['source']['provider'] == provider]), channels)
        subset = own
        source_graphs[provider] = {'articles': subset, 'relations': relations_for(provider,subset) if include_relations else [], 'total_articles': len(own)}
    # Separate cross-source budgets preserve all existing within-source relations.
    cross = {}
    for left, right in itertools.combinations(source_graphs,2):
        a,b = source_graphs[left]['articles'],source_graphs[right]['articles']
        if not include_relations or not a or not b:
            continue
        candidates=deduplicate(a+b)
        for edge in relations_for(left+'_'+right,candidates,True):
            cross[tuple(sorted((edge['source'],edge['target'])))]={**edge,'cross_sources':[left,right]}
    combined=relations_for('combined',shown) if include_relations else []
    if include_relations:
        cache_logger.info('graph_compute_ms %s',json.dumps(stage_times))
    return {'schema_version': SCHEMA_VERSION, 'articles': shown, 'relations': combined,
            'source_graphs': source_graphs, 'cross_relations': list(cross.values()),
            'channel_definitions': channels, 'channel_version': channel_version(channels),
            'total_articles': len(all_rows), 'display_limit': None,
            'relation_settings': cfg, 'relations_pending': not include_relations,
            'relation_note': '規則關聯並非因果；分數為排序用啟發式指標，不是機率。'}

def retain_known_edges(pending, previous):
    """Keep provisional evidence only for unchanged endpoints while fresh rules run."""
    def carry(new, old):
        before={a['id']:a for a in old.get('articles',[])}
        same={a['id'] for a in new.get('articles',[]) if before.get(a['id'])==a}
        new['relations']=[e for e in old.get('relations',[]) if e['source'] in same and e['target'] in same]
        return same
    unchanged=carry(pending,previous)
    for source, group in pending['source_graphs'].items():
        carry(group,previous.get('source_graphs',{}).get(source,{}))
    pending['cross_relations']=[e for e in previous.get('cross_relations',[]) if e['source'] in unchanged and e['target'] in unchanged]
    # These are previous valid pair evidences, not the final new degree-budget selection.
    pending['relations_pending']=True
    return pending


def search_events(request, key, store):
    start_time = time.monotonic()
    by_source = {}
    cfg=request.get('relation_settings')
    channels=store.list_channels()
    for source in request['sources']:
        term = request['ticker'] if source == 'massive' else request['query']
        by_source[source] = deduplicate(store.read(source, query_key(source, term, request.get('rss_region')), request['start'], request['end']))
    cached_rows=[a for rows in by_source.values() for a in rows]
    displayed=lookup_cached(store,cached_rows,channels,cfg)
    if displayed is None:
        displayed=graph_payload(cached_rows,channels,cfg,False)
    yield {'type': 'cache', 'graph': displayed,
           'counts': {s: len(rows) for s, rows in by_source.items()},
           'message': '檢查日期覆蓋'}
    events = queue.Queue()
    def work(source):
        def progress(message):
            events.put({'type': 'status', 'source': source, **(message if isinstance(message, dict) else {'message': message})})
        try:
            if source == 'massive' and not request['ticker']:
                events.put({'type': 'source', 'source': source, 'articles': [], 'error': '未填股票代碼，已略過', 'error_code': 'missing_ticker'})
                return
            result = search_source(source, request['query'], request['ticker'], key, request['start'], request['end'], store, request['force_refresh'], progress, **({'rss_region':request['rss_region']} if request.get('rss_region') is not None else {}))
        except Exception:
            # Deliberately exclude exception text that might contain request URLs or keys.
            result = {'source': source, 'articles': by_source[source], 'error': '資料處理失敗；已保留本地結果，請稍後重試', 'error_code': 'internal'}
        events.put({'type': 'source', **result})
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for source in request['sources']:
            pool.submit(work, source)
        completed = 0
        while completed < len(request['sources']):
            try:
                event = events.get(timeout=5)
            except queue.Empty:
                yield {'type': 'heartbeat', 'elapsed': round(time.monotonic() - start_time)}
                continue
            if event['type'] == 'source':
                completed += 1
                by_source[event['source']] = event['articles']
                current_rows=[a for rows in by_source.values() for a in rows]
                updated=lookup_cached(store,current_rows,channels,cfg)
                if updated is None:
                    updated=retain_known_edges(graph_payload(current_rows,channels,cfg,False),displayed)
                displayed=updated
                event.update(completed=completed, total=len(request['sources']),graph=displayed)
            yield event
    yield {'type':'phase','phase':'relations','message':'新聞已載入，正在計算關聯','elapsed':round(time.monotonic()-start_time)}
    # One final graph calculation; stream heartbeats while it runs, keeping news visible.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as compute:
        future=compute.submit(functools.partial(build_cached,store,graph_payload),[a for rows in by_source.values() for a in rows],store.list_channels(),cfg)
        while True:
            try:
                graph=future.result(timeout=1)
                yield {'type':'graph','graph':graph}
                break
            except concurrent.futures.TimeoutError:
                yield {'type':'heartbeat','phase':'relations','elapsed':round(time.monotonic()-start_time)}
            except Exception:
                yield {'type':'graph_error','message':'關聯計算未完成；新聞已保留，可在關聯設定重試。'}
                break
    yield {'type': 'done', 'elapsed': round(time.monotonic() - start_time), 'db': store.stats()}

class Handler(BaseHTTPRequestHandler):
    @property
    def store(self):
        return self.server.store

    def json_response(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith('/api/chat/'):
            chat_proxy.handle(self);return
        path = urllib.parse.urlsplit(self.path).path
        if path == '/api/capabilities':
            self.json_response(200,api.capabilities());return
        if path == '/openapi.json':
            self.json_response(200,specification());return
        if path == '/api/schema':
            self.json_response(200,json.loads(api.SCHEMA_PATH.read_text()));return
        if path.startswith('/api/articles/'):
            import re
            ident=path.rsplit('/',1)[-1]
            if not re.fullmatch(r'[a-f0-9]{24}',ident):
                self.json_response(400,{'error':'文章 ID 必須是標準 24 字元 ID'});return
            with self.store.connection() as db:
                rows=db.execute('SELECT payload FROM articles WHERE id=? ORDER BY provider',(ident,)).fetchall()
            self.json_response(200 if rows else 404,{'articles':[json.loads(r['payload']) for r in rows]} if rows else {'error':'文章不存在'});return
        if path == '/api/status':
            self.json_response(200, {'schema_version': SCHEMA_VERSION, 'db': self.store.stats(), 'massive_configured': bool(credentials.load_key(self.store.path) or os.environ.get('MASSIVE_API_KEY'))})
            return
        if path == '/api/channels':
            channels = self.store.list_channels()
            self.json_response(200, {'channels':channels,'version':channel_version(channels)})
            return
        if path == '/api/snapshots':
            self.json_response(200, {'snapshots': self.store.list_snapshots()})
            return
        if path.startswith('/api/snapshots/'):
            saved = self.store.load_snapshot(path.rsplit('/',1)[-1])
            self.json_response(200 if saved else 404, saved or {'error':'快照不存在'})
            return
        files = {'/price-chart.js': ('dist/price-chart.js','text/javascript; charset=utf-8'), '/docking.js': ('dist/docking.js','text/javascript; charset=utf-8'), '/price-lens.js': ('dist/price-lens.js','text/javascript; charset=utf-8'), '/chat-panel.js': ('dist/chat-panel.js','text/javascript; charset=utf-8'), '/chat-panel.css': ('dist/chat-panel.css','text/css; charset=utf-8'), '/relation-settings.js': ('dist/relation-settings.js','text/javascript; charset=utf-8'), '/time-lens.js': ('dist/time-lens.js','text/javascript; charset=utf-8'), '/docs': ('dist/docs.html','text/html; charset=utf-8'), '/docs/': ('dist/docs.html','text/html; charset=utf-8'), '/vendor/swagger-ui-bundle.js': ('dist/vendor/swagger-ui-bundle.js','text/javascript; charset=utf-8'), '/vendor/swagger-ui.css': ('dist/vendor/swagger-ui.css','text/css; charset=utf-8'), '/interaction.js': ('dist/interaction.js','text/javascript; charset=utf-8'), '/date-range.js': ('dist/date-range.js','text/javascript; charset=utf-8'), '/glow.js': ('dist/glow.js','text/javascript; charset=utf-8'), '/i18n.js': ('dist/i18n.js','text/javascript; charset=utf-8'), '/explorer-ui.js': ('dist/explorer-ui.js','text/javascript; charset=utf-8'), '/schema/news-atlas.schema.json': ('schema/news-atlas.schema.json','application/json; charset=utf-8'), '/': ('dist/index.html', 'text/html; charset=utf-8'), '/3d-force-graph.min.js': ('dist/3d-force-graph.min.js', 'text/javascript; charset=utf-8'), '/app.js': ('dist/app.js', 'text/javascript; charset=utf-8'), '/graph-view.js': ('dist/graph-view.js', 'text/javascript; charset=utf-8'), '/timeline.js': ('dist/timeline.js', 'text/javascript; charset=utf-8')}
        if path not in files:
            self.send_error(404)
            return
        name, mime = files[path]
        data = (ROOT / name).read_bytes()
        self.send_response(200)
        for k, v in [('Content-Type', mime), ('Content-Length', str(len(data))), ('X-Content-Type-Options', 'nosniff'), ('Cache-Control', 'no-cache')]:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_DELETE(self):
        path=urllib.parse.urlsplit(self.path).path
        if path=='/api/settings/massive-key':
            try:
                credentials.forget_key(self.store.path)
                self.json_response(200,{'configured':bool(os.environ.get('MASSIVE_API_KEY'))})
            except OSError:self.json_response(500,{'error':'無法清除本機金鑰設定'})
            return
        if not path.startswith('/api/channels/custom-'):
            self.json_response(404, {'error':'自訂 channel 不存在'})
            return
        removed=self.store.delete_channel(path.rsplit('/',1)[-1])
        self.json_response(200 if removed else 404, {'channels':self.store.list_channels()} if removed else {'error':'自訂 channel 不存在'})

    def do_POST(self):
        if self.path=='/api/prices/lens':
            try:
                length=int(self.headers.get('Content-Length','0'))
                if self.headers.get('Content-Type','').split(';')[0]!='application/json' or not 0<length<=32*1024*1024:raise ValueError('Invalid price request')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('Invalid price request')
                key=body.get('massive_key') or credentials.load_key(self.store.path) or os.environ.get('MASSIVE_API_KEY','')
                if not isinstance(key,str) or len(key)>512 or any(ord(c)<32 or ord(c)>126 for c in key):raise ValueError('Invalid Massive key')
                self.json_response(200,price_lens.load(self.store,body,key))
            except (ValueError,TypeError) as error:self.json_response(400,{'error':str(error)})
            except price_lens.SourceError as error:self.json_response(502,{'error':str(error),'code':error.code})
            return
        if self.path.startswith('/api/chat/'):
            chat_proxy.handle(self);return
        if self.path not in ('/api/settings/massive-key','/api/search', '/api/search/result', '/api/snapshots', '/api/channels', '/api/classify', *api.POST_PATHS):
            self.send_error(404)
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            self.json_response(415, {'error': '需要 application/json'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= (268435456 if self.path in ('/api/snapshots','/api/classify',*api.POST_PATHS) else 16384):
                raise ValueError('搜尋內容大小錯誤')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body,dict): raise ValueError('Request body 必須是 JSON object')
            if self.path=='/api/settings/massive-key':
                try:
                    credentials.save_key(self.store.path,body.get('key'))
                    self.json_response(200,{'configured':True})
                except OSError:self.json_response(500,{'error':'無法保存本機金鑰設定'})
                return
            if self.path in api.POST_PATHS:
                self.json_response(200,api.dispatch(self.path,body,self.store,functools.partial(build_cached,self.store,graph_payload)));return
            if self.path == '/api/channels':
                saved = self.store.save_channel(body)
                self.json_response(200, {'channel':saved,'channels':self.store.list_channels()})
                return
            if self.path == '/api/classify':
                rows = body.get('articles') if isinstance(body,dict) else None
                if not isinstance(rows,list) or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) or len(r['id'])>100 or not isinstance(r.get('title'),str) or len(r['title'])>2000 or not isinstance(r.get('summary',''),str) or len(r.get('summary',''))>12000 for r in rows):
                    raise ValueError('重新分類的文章格式或數量不正確')
                channels=self.store.list_channels()
                self.json_response(200, {'annotations':[{"id":r['id'],**classify(r,channels)} for r in rows],'channels':channels,'version':channel_version(channels)})
                return
            if self.path == '/api/snapshots':
                saved = self.store.save_snapshot(body)
                self.json_response(201, {**saved, 'db': self.store.stats()})
                return
            request = normalize_request(body)
            key = str(body.get('massive_key', '')).strip() or credentials.load_key(self.store.path) or os.environ.get('MASSIVE_API_KEY', '')
            if len(key) > 512 or any(ord(c) < 32 or ord(c) > 126 for c in key):
                raise ValueError('API key 格式不正確')
        except (ValueError, TypeError, OverflowError) as exc:
            self.json_response(400, {'error': str(exc) if not isinstance(exc, json.JSONDecodeError) else '無效 JSON'})
            return
        if self.path=='/api/search/result':
            graph=None;sources=[];done={}
            for event in search_events(request,key,self.store):
                if 'graph' in event: graph=event['graph']
                if event['type']=='source': sources.append({k:v for k,v in event.items() if k not in ('graph','articles')})
                if event['type']=='done': done=event
            self.json_response(200,{'graph':graph,'sources':sources,'db':done.get('db',{}),'elapsed':done.get('elapsed',0),'partial':bool(graph and graph.get('relations_pending')) or any(s.get('error') or s.get('cache',{}).get('missing_ranges') for s in sources)})
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Accel-Buffering', 'no')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        try:
            for event in search_events(request, key, self.store):
                self.wfile.write((json.dumps(event, ensure_ascii=False) + '\n').encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

if __name__ == '__main__':
    def stop_server(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_server)
    store = Store()
    port = int(os.environ.get('PORT', '8765'))
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    server.store = store
    print(f'News Atlas: http://127.0.0.1:{port}\nListening: 0.0.0.0:{port} (LAN: http://<host-ip>:{port})\nSQLite: {store.path}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
