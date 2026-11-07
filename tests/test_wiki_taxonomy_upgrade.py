"""BDD: the operator CLI respects the real same-origin API and is idempotent."""
import json, os, subprocess, sys, threading, unittest
from pathlib import Path
from unittest.mock import patch
import server
import test_research
from news_atlas.wiki.research import put,taxonomy
from news_atlas.wiki.store import now

class UpgradeTests(unittest.TestCase):
    setUp=test_research.ResearchTests.setUp
    add=test_research.ResearchTests.add

    def test_preview_apply_repeat_against_real_http_without_model_work(self):
        with self.store.connection() as db:
            tax=taxonomy(db)
            legacy={**tax,'revision_id':'legacy','available_at':now(),'terms':[t for t in tax['terms'] if t['id'] not in ('analysis.noise','analysis.fact_check')]}
            put(db,'taxonomy',legacy,'','legacy')
            revisions=db.execute("SELECT count(*) FROM research_objects WHERE kind='taxonomy'").fetchone()[0]
            jobs=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.store=self.news;http.wiki=self.service
        url='http://127.0.0.1:'+str(http.server_port);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        def cli(*extra):
            result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/wiki_taxonomy_upgrade.py'),'--url',url,'--instrument','NASDAQ:TSLA',*extra],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            return json.loads(result.stdout)
        try:
            with patch.dict(os.environ,{'NEWS_ATLAS_WIKI_ORIGINS':url}):
                self.assertEqual(cli()['status'],'preview')
                with self.store.connection() as db:self.assertEqual(taxonomy(db)['revision_id'],'legacy')
                self.assertEqual(cli('--apply')['status'],'updated')
                self.assertEqual(cli('--apply')['status'],'unchanged')
            with self.store.connection() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM research_objects WHERE kind='taxonomy'").fetchone()[0],revisions+1)
                self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],jobs)
                self.assertEqual(db.execute('SELECT count(*) FROM research_jobs').fetchone()[0],0)
        finally:http.shutdown();http.server_close();thread.join()
