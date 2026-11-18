"""Exercise the agent's advertised operations against the HTTP handler and real SQLite."""
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import server
from news_atlas.graph_storage import GraphRepository
from news_atlas.providers import Batch
from news_atlas.wiki.compiler import WikiService
from test_server import row
from test_wiki import proposal
from test_research import fusion


class AgentWorkflowTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = GraphRepository(Path(tmp.name) / 'news-atlas.sqlite3')
        self.service = WikiService(repo, runner=self.runner, start_worker=False)
        self.host = SimpleNamespace(store=repo, wiki=self.service)

    @staticmethod
    def runner(store, job, article, context):
        if job['payload'].get('operation') == 'research_fusion':
            return {'proposal': fusion(article['research_bundle'])}
        result = proposal(article)
        result['nodes'][0]['summary'] = article['title']
        old = next((n for n in context if n['kind'] == 'Claim'), None)
        if old:
            result['relations'] = [dict(source='n1', target=old['id'], type=kind,
                rationale=article['title'], citations=result['nodes'][0]['citations'])
                for kind in ('CONTRADICTS', 'UPDATES')]
        return {'proposal': result}

    def request(self, path, body=None, **params):
        if params:
            path += '?' + urlencode(params)
        data = json.dumps(body).encode() if body is not None else b''
        method = 'POST' if body is not None else 'GET'
        raw = (f'{method} {path} HTTP/1.0\r\nHost: localhost:8765\r\nOrigin: http://localhost:8765\r\n'
               f'Content-Type: application/json\r\nContent-Length: {len(data)}\r\n\r\n').encode() + data
        output = io.BytesIO()
        conn = SimpleNamespace(makefile=lambda *_: io.BytesIO(raw), sendall=output.write)
        with patch.object(server.Handler, 'log_message'):
            server.Handler(conn, ('127.0.0.1', 1), self.host)
        head, payload = output.getvalue().split(b'\r\n\r\n', 1)
        self.assertIn(int(head.split()[1]), (200, 201, 202), payload[:500])
        if path == '/api/search':
            return [json.loads(line) for line in payload.splitlines()]
        return json.loads(payload)

    def test_stop_from_http_disables_watcher_and_cancels_queued_l1(self):
        ident='NASDAQ:TSLA'
        preview=self.request('/api/wiki/plan',dict(instrument=ident,model='fixture',articles=[row()]))
        job=self.request('/api/wiki/jobs',dict(plan_id=preview['plan_id'],continuous=True))
        with patch.object(self.service,'bridge_request'):
            self.assertEqual(self.request('/api/wiki/stop',dict(instrument=ident))['cancelled_jobs'],[job['job_id']])
        status=self.request('/api/wiki/jobs',instrument=ident)
        self.assertFalse(status['config']['enabled'] or status['config']['catch_up'])
        self.assertEqual(status['jobs'][0]['status'],'cancelled')

    def test_download_progress_publish_correct_and_read_saved_research(self):
        ident = 'NASDAQ:TSLA'
        day = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1))
        query = dict(instrument=ident, start=str(day), end=str(day), sources=['massive'])
        self.assertFalse(self.request('/api/context/catalog')['instruments'])
        self.assertTrue(self.request('/api/cache/graph', query)['coverage']['massive']['missing_ranges'])
        news = row(title='Tesla demand rises', day=str(day), suffix='original')
        batch = Batch(rows=[news], windows=[(str(day), str(day+dt.timedelta(days=1)), 'complete')])
        with patch('news_atlas.search.acquire', return_value=batch) as fetch:
            events = self.request('/api/search', query)
            fetch.assert_called_once()
        self.assertIn('status', [e['type'] for e in events])
        self.assertEqual(events[-1]['type'], 'done')
        self.assertFalse(self.request('/api/cache/graph', query)['coverage']['massive']['missing_ranges'])
        self.assertEqual(self.request('/api/context/catalog')['instruments'][0]['instrument'], ident)

        def publish(**scope):
            preview = self.request('/api/wiki/plan', dict(instrument=ident, model='fixture', **scope))
            self.request('/api/wiki/jobs', {'plan_id':preview['plan_id']})
            self.assertEqual(self.request('/api/wiki/jobs', instrument=ident)['jobs'][0]['status'], 'queued')
            self.service.tick()
            self.assertEqual(self.request('/api/wiki/jobs', instrument=ident)['jobs'][0]['status'], 'completed')

        publish(news_db=True, scope='global')
        base = self.request('/api/context/graph', instrument=ident)
        claim = next(n['id'] for n in base['items'] if n['kind']=='Claim')
        research = '/api/wiki/research/'
        job = self.request(research+'query', dict(instrument=ident, query='需求', model='fixture'))
        self.service.tick()
        run_id = self.request(research+'job', instrument=ident, id=job['job_id'])['payload']['run_id']
        original = self.request('/api/context/l2', instrument=ident, id=run_id)['bundle']
        self.assertTrue(original['opinions'])
        publish(articles=[row(title='Tesla demand falls', day=str(day), suffix='correction')])
        edges = self.request('/api/context/graph', instrument=ident, collection='edges', id=claim)
        self.assertEqual({e['relation_type'] for e in edges['items']}, {'SUPPORTS','CONTRADICTS','UPDATES'})
        historical = self.request('/api/context/graph', instrument=ident, version=base['version'])
        self.assertEqual(historical, base)
        self.assertEqual(self.request('/api/context/l2', instrument=ident, id=run_id)['bundle'],original)

    def test_graph_pages_after_render_limit(self):
        store = self.service.store('NASDAQ:TSLA')
        with store.connection() as db:
            db.executemany('INSERT INTO nodes VALUES (?,?,?,?)', [
                (str(i),'Claim',0,json.dumps({'id':str(i)})) for i in range(2401)])
        page = self.request('/api/context/graph', instrument=store.instrument, offset=2400)
        self.assertEqual(page['total'],2401)
        self.assertEqual(len(page['items']),1)
        self.assertIsNone(page['next_offset'])
