"""Docker readiness must remain responsive independently of corpus size."""
import json
from pathlib import Path
import re
import threading
import unittest
from unittest.mock import Mock
from urllib.request import urlopen
import server


class HealthcheckTests(unittest.TestCase):
    def test_configured_probe_serves_without_scanning_news(self):
        # Given corpus statistics are too costly/unavailable, the actual Docker
        # probe must still check the serving process without visiting the corpus.
        dockerfile = (Path(__file__).resolve().parents[1] / 'Dockerfile').read_text()
        path = re.search(r"http://127\.0\.0\.1:8765(/[^']+)", dockerfile).group(1)
        http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        http.store = Mock()
        http.store.stats.side_effect = RuntimeError('Health probe scanned the corpus')
        worker = threading.Thread(target=http.serve_forever, daemon=True)
        worker.start()
        try:
            with urlopen(f'http://127.0.0.1:{http.server_port}{path}', timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertIsInstance(json.load(response), dict)
            http.store.stats.assert_not_called()
        finally:
            http.shutdown()
            http.server_close()
            worker.join()
