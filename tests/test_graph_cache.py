import concurrent.futures
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from news_atlas import graph_cache
from news_atlas.model import article
import server


class GraphCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SimpleNamespace(path=Path(self.temp.name)/'news.sqlite3')
        self.rows = [article('google', 'NVIDIA earnings', 'https://example.test/'+str(i),
                             '2026-01-01T00:00:00Z', symbols=['NVDA']) for i in range(3)]

    def test_exact_result_and_restart_reuse(self):
        expected = server.graph_payload(self.rows)
        actual = graph_cache.build_cached(self.store, server.graph_payload, self.rows)
        self.assertEqual(actual, expected)
        script = '''import json,sys
from types import SimpleNamespace
from news_atlas.graph_cache import build_cached
rows=json.loads(sys.stdin.read())
def forbidden(*a,**kw):raise AssertionError('recomputed after restart')
print(json.dumps(build_cached(SimpleNamespace(path=sys.argv[1]),forbidden,rows)))
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.store.path)],
                                input=json.dumps(self.rows), text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), expected)
        actual['articles'].clear()
        self.assertEqual(graph_cache.build_cached(self.store, server.graph_payload, self.rows), expected)

    def test_content_rules_order_and_version_invalidate(self):
        with patch.object(server, 'graph_payload', wraps=server.graph_payload) as build:
            graph_cache.build_cached(self.store, build, self.rows)
            graph_cache.build_cached(self.store, build, self.rows)
            self.assertEqual(build.call_count, 1)
            changed = copy.deepcopy(self.rows); changed[0]['title'] += ' updated'
            graph_cache.build_cached(self.store, build, changed)
            graph_cache.build_cached(self.store, build, self.rows, relation_settings={'entity': False})
            graph_cache.build_cached(self.store, build, list(reversed(self.rows)))
            with patch.object(graph_cache, 'VERSION', 'next'):
                graph_cache.build_cached(self.store, build, self.rows)
            self.assertEqual(build.call_count, 5)

    def test_concurrent_identical_requests_compute_once(self):
        entered = threading.Event(); release = threading.Event(); calls = []
        def build(*args, **kwargs):
            calls.append(1); entered.set(); self.assertTrue(release.wait(3))
            return server.graph_payload(*args, **kwargs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(graph_cache.build_cached, self.store, build, self.rows) for _ in range(4)]
            self.assertTrue(entered.wait(3)); time.sleep(.1); release.set()
            results = [future.result() for future in futures]
        self.assertEqual(len(calls), 1)
        self.assertTrue(all(r == results[0] for r in results))
        results[0]['articles'].clear()
        self.assertTrue(results[1]['articles'])

    def test_failures_do_not_poison_retries_and_cache_is_optional(self):
        with self.assertRaisesRegex(RuntimeError, 'compute'):
            graph_cache.build_cached(self.store, lambda *a, **k: (_ for _ in ()).throw(RuntimeError('compute')), self.rows)
        expected = server.graph_payload(self.rows)
        with patch.object(graph_cache, '_connect', side_effect=sqlite3.OperationalError('readonly')):
            self.assertEqual(graph_cache.build_cached(self.store, server.graph_payload, self.rows), expected)
        graph_cache.build_cached(self.store, server.graph_payload, self.rows)
        path = str(self.store.path)+'.graphs.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute("UPDATE graphs SET payload=X'00'")
        self.assertEqual(graph_cache.build_cached(self.store, server.graph_payload, self.rows), expected)

    def test_disk_retention_is_bounded(self):
        path = str(self.store.path)+'.graphs.sqlite3'
        with patch.object(graph_cache, 'MAX_ENTRIES', 2), patch.object(graph_cache, 'MAX_BYTES', 8):
            for key in ['a','b','c']:
                graph_cache._write(path, key, b'1234')
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT count(*),sum(length(payload)) FROM graphs').fetchone(), (2,8))
            graph_cache._write(path, 'huge', b'123456789')
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM graphs').fetchone()[0], 2)

if __name__ == '__main__': unittest.main()
