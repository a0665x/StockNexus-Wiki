"""Cross-computer union against real SQLite fixtures; no model/network calls."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from scripts.merge_data import run, connect
from news_atlas.storage import Store
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import capture, digest, WikiStore, migrate_legacy
from test_server import row
from test_wiki import proposal


class MergeDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.a=self.root/'source data';self.b=self.root/'target data'
        self.sa=GraphRepository(self.a/'news-atlas.sqlite3').for_ticker('');self.sb=GraphRepository(self.b/'news-atlas.sqlite3').for_ticker('')

    def wiki(self,store,rows):
        service=WikiService(store,runner=lambda s,j,a,c:{'proposal':proposal(a)},start_worker=False)
        p=service.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':rows})
        service.start({'plan_id':p['plan_id']});service.tick();service.tick()
        return service.store('NASDAQ:TSLA')

    def count(self,p,t):
        with sqlite3.connect(p) as d:return d.execute('SELECT count(*) FROM '+t).fetchone()[0]

    def test_news_union_conflicts_and_idempotency(self):
        shared=row(suffix='same');changed={**shared,'title':'Incoming conflicting title'}
        self.sa.save('massive','query',[changed,row(suffix='source')],[])
        self.sb.save('massive','query',[shared,row(suffix='target')],[])
        result=run(self.a,self.b)
        self.assertEqual(self.count(self.sb.path,'articles'),3)
        with sqlite3.connect(self.sb.path) as d:
            title=json.loads(d.execute('SELECT payload FROM articles WHERE id=?',(shared['id'],)).fetchone()[0])['title']
            self.assertEqual(title,shared['title']);self.assertGreater(d.execute('SELECT count(*) FROM merge_conflicts').fetchone()[0],0)
        before=self.count(self.sb.path,'merge_conflicts');run(self.a,self.b)
        self.assertEqual(self.count(self.sb.path,'articles'),3)
        self.assertEqual(self.count(self.sb.path,'merge_conflicts'),before)
        self.assertTrue((Path(result['backup'])/'before/graph/_unassigned/news-atlas.sqlite3').exists())
        self.assertTrue((Path(result['backup'])/'source/graph/_unassigned/news-atlas.sqlite3').exists())

    def test_wiki_diverged_versions_union_and_repeat(self):
        a=self.wiki(self.sa,[row(title='Source article',suffix='source')])
        b=self.wiki(self.sb,[row(title='Target article',suffix='target')])
        old=b.graph();run(self.a,self.b);g=b.graph()
        self.assertEqual(g['version'],2);self.assertEqual(len(g['nodes']),4)
        self.assertEqual(b.graph(version=1)['nodes'],old['nodes'])
        self.assertEqual(self.count(b.path,'extractions'),2)
        nodes={n['id'] for n in g['nodes']}
        for edge in g['edges']:
            self.assertIn(edge['source']['stable_id'],nodes);self.assertIn(edge['target']['stable_id'],nodes)
        run(self.a,self.b);self.assertEqual(b.graph()['version'],2)
        # Return merged knowledge to original computer without duplicating source version.
        run(self.b,self.a);self.assertEqual(a.graph()['version'],2)
        run(self.a,self.b);self.assertEqual(b.graph()['version'],2)

    def test_new_stock_is_paused_and_private_excluded(self):
        a=self.wiki(self.sa,[row()]);cfg=a.config();cfg.update(enabled=True,catch_up=True);a.configure(cfg)
        (self.a/'private').mkdir();(self.a/'private/secret').write_text('secret')
        fresh=self.root/'fresh';run(self.a,fresh)
        service=WikiService(GraphRepository(fresh/'news-atlas.sqlite3'),start_worker=False)
        b=service.store('NASDAQ:TSLA')
        self.assertFalse(b.config()['enabled']);self.assertFalse(b.config()['catch_up'])
        self.assertEqual(b.graph()['version'],1);self.assertFalse((fresh/'private').exists())

    def test_dry_run_no_target_and_no_source_changes(self):
        self.sa.save('massive','query',[row()],[])
        fresh=self.root/'not-created';before=self.sa.path.read_bytes()
        r=run(self.a,fresh,True)
        self.assertTrue(r['dry_run']);self.assertFalse(fresh.exists())
        self.assertEqual(self.sa.path.read_bytes(),before)

    def test_running_target_rejected_before_any_changes(self):
        self.wiki(self.sa,[row(suffix='a')]);b=self.wiki(self.sb,[row(suffix='b')])
        with b.connection() as d:d.execute("UPDATE jobs SET status='running'")
        self.sa.save('massive','query',[row()],[])
        with self.assertRaisesRegex(ValueError,'running/queued'):run(self.a,self.b)
        self.assertEqual(self.count(self.sb.path,'articles'),0)
        self.assertFalse((self.b/'.merge-backups').exists())

    def test_dangling_wiki_rejects_whole_preflight(self):
        a=self.wiki(self.sa,[row()]);self.sa.save('massive','query',[row()],[])
        with a.connection() as d:d.execute("UPDATE edges SET target='missing'")
        with self.assertRaisesRegex(ValueError,'dangling'):run(self.a,self.b)
        self.assertEqual(self.count(self.sb.path,'articles'),0)
        self.assertFalse((self.b/'research').exists())

    def test_integer_attempt_ids_do_not_drop_distinct_records(self):
        for path,err in [(self.sa.path,'a'),(self.sb.path,'b')]:
            with sqlite3.connect(path) as d:d.execute("INSERT INTO attempts VALUES (1,'google','q','2026-01-01','2026-01-02',1,?,0)",(err,))
        run(self.a,self.b);run(self.a,self.b)
        self.assertEqual(self.count(self.sb.path,'attempts'),2)

    def test_snapshot_collision_keeps_both_and_remaps_children(self):
        for path,name,article in [(self.sa.path,'source','a'),(self.sb.path,'target','b')]:
            with sqlite3.connect(path) as d:
                d.execute("INSERT INTO snapshots VALUES ('same',?,'2026-01-01','{}','{}')",(name,))
                d.execute("INSERT INTO snapshot_articles VALUES ('same','google',?, '{}')",(article,))
        run(self.a,self.b);run(self.a,self.b)
        with sqlite3.connect(self.sb.path) as d:
            rows=d.execute('SELECT s.name,a.article_id FROM snapshots s JOIN snapshot_articles a ON s.id=a.snapshot_id ORDER BY s.name').fetchall()
        self.assertEqual(rows,[('source','a'),('target','b')])
        run(self.b,self.a);run(self.a,self.b)
        self.assertEqual(self.count(self.sa.path,'snapshots'),2)
        self.assertEqual(self.count(self.sb.path,'snapshots'),2)

    def test_imported_running_job_never_queues_and_citations_preserved(self):
        a=self.wiki(self.sa,[row()])
        with a.connection() as d:d.execute("UPDATE jobs SET status='running'")
        run(self.a,self.b)
        service=WikiService(self.sb,start_worker=False);b=service.store('NASDAQ:TSLA')
        self.assertEqual(b.jobs()[0]['status'],'interrupted')
        for n in b.graph()['nodes']:
            for c in n.get('citations',[]):
                with b.connection() as d:
                    article=json.loads(d.execute('SELECT payload FROM articles WHERE id=?',(c['article_revision_id'],)).fetchone()[0])
                self.assertEqual(article[c['field']][c['start']:c['end']],c['quote'])

    def test_preexisting_db_backup_can_restore_original(self):
        self.sa.save('massive','q',[row(suffix='a')],[])
        self.sb.save('massive','q',[row(suffix='b')],[])
        report=run(self.a,self.b)
        before=Path(report['backup'])/'before/graph/_unassigned/news-atlas.sqlite3'
        self.assertEqual(self.count(before,'articles'),1)
        self.assertEqual(self.count(self.sb.path,'articles'),2)
        saved=json.loads((Path(report['backup'])/'report.json').read_text())
        self.assertEqual(saved['committed'],['graph/_unassigned/news-atlas.sqlite3'])

    def test_bad_citation_rejects_import_before_writes(self):
        a=self.wiki(self.sa,[row()])
        with a.connection() as db:
            r=db.execute("SELECT id,payload FROM nodes WHERE kind='Claim'").fetchone()
            n=json.loads(r['payload']);n['citations'][0]['quote']='fabricated'
            db.execute('UPDATE nodes SET payload=? WHERE id=?',(json.dumps(n),r['id']))
        with self.assertRaisesRegex(ValueError,'citation span'):run(self.a,self.b)
        self.assertFalse((self.b/'llm_wiki/TSLA/wiki.sqlite3').exists())

    def test_newer_wiki_not_silently_downgraded_by_open(self):
        a=self.wiki(self.sa,[row()])
        with a.connection() as db:db.execute('PRAGMA user_version=999')
        with self.assertRaisesRegex(ValueError,'Newer database'):WikiStore(self.a/'llm_wiki','NASDAQ:TSLA')
        with sqlite3.connect(a.path) as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],999)

    def test_imported_source_not_known_before_import(self):
        a=self.wiki(self.sa,[row()])
        with a.connection() as db:
            db.execute("UPDATE articles SET captured_at='2000-01-01T00:00:00+00:00'")
        run(self.a,self.b)
        b=WikiStore(self.b/'llm_wiki','NASDAQ:TSLA')
        with b.connection() as db:
            self.assertGreater(db.execute('SELECT captured_at FROM articles').fetchone()[0], '2026-01-01')

    def test_newer_schema_rejected(self):
        with sqlite3.connect(self.sa.path) as d:d.execute('PRAGMA user_version=999')
        with self.assertRaisesRegex(ValueError,'Newer database'):run(self.a,self.b)

    def test_single_stock_and_wiki_root_selection(self):
        a=self.wiki(self.sa,[row(suffix='a')]);b=self.wiki(self.sb,[row(suffix='b')])
        other=WikiStore(self.a/'llm_wiki','NASDAQ:GOOGL')
        report=run(a.folder,self.b)
        self.assertEqual(list(report['databases']),['llm_wiki/TSLA/wiki.sqlite3'])
        self.assertEqual(b.graph()['version'],2)
        self.assertFalse((self.b/'llm_wiki/GOOGL').exists())
        run(self.a/'llm_wiki',self.b/'llm_wiki')
        self.assertTrue((self.b/'llm_wiki/GOOGL/wiki.sqlite3').exists())
        self.assertEqual(b.graph()['version'],2)
        run(a.folder,b.folder)
        self.assertEqual(b.graph()['version'],2)
        run(a.folder,self.root/'empty'/'llm_wiki')
        self.assertTrue((self.root/'empty/llm_wiki/TSLA/wiki.sqlite3').exists())

    def test_migration_preserves_old_contents_and_legacy_import(self):
        a=self.wiki(self.sa,[row()]);original=a.graph()
        legacy=self.a/'research'/digest('NASDAQ:TSLA')[:24]
        legacy.parent.mkdir();a.folder.rename(legacy)
        run(self.a,self.b)
        self.assertTrue((self.b/'llm_wiki/TSLA/wiki.sqlite3').exists())
        migrate_legacy(self.a)
        self.assertFalse(legacy.exists())
        self.assertEqual(WikiStore(self.a/'llm_wiki','NASDAQ:TSLA').graph()['nodes'],original['nodes'])
        migrate_legacy(self.a)

    def test_same_ticker_different_market_refused(self):
        a=self.wiki(self.sa,[row()])
        WikiStore(self.b/'llm_wiki','NYSE:TSLA')
        with self.assertRaisesRegex(ValueError,'Instrument mismatch'):run(a.folder,self.b)

    def test_legacy_target_refuses_duplicate_live_database(self):
        self.wiki(self.sa,[row()]);b=self.wiki(self.sb,[row(suffix='b')])
        legacy=self.b/'research'/digest('NASDAQ:TSLA')[:24]
        legacy.parent.mkdir();b.folder.rename(legacy)
        with self.assertRaisesRegex(ValueError,'legacy research'):run(self.a,self.b)
        self.assertFalse((self.b/'llm_wiki/TSLA').exists())

    def test_same_or_nested_paths_rejected(self):
        for dest in [self.a,self.a/'child',self.root]:
            with self.assertRaises(ValueError):run(self.a,dest)

    def test_unsupported_schema_rejected(self):
        with sqlite3.connect(self.sa.path) as d:d.execute('CREATE TABLE future_schema (id TEXT)')
        with self.assertRaisesRegex(ValueError,'Unsupported tables'):run(self.a,self.b)
        self.assertEqual(self.count(self.sb.path,'articles'),0)

    def test_prices_union_without_cache_or_private(self):
        for root,key in [(self.a,'a'),(self.b,'b')]:
            with sqlite3.connect(root/'graph/_unassigned/news-atlas.sqlite3.prices.sqlite3') as d:
                d.execute('CREATE TABLE series (key TEXT PRIMARY KEY,payload TEXT NOT NULL,fetched REAL NOT NULL)')
                d.execute('INSERT INTO series VALUES (?, ?, 1)',(key,'{}'))
        (self.a/'news-atlas.sqlite3.graphs.sqlite3').write_text('excluded')
        run(self.a,self.b)
        self.assertEqual(self.count(self.b/'graph/_unassigned/news-atlas.sqlite3.prices.sqlite3','series'),2)
        self.assertFalse((self.b/'news-atlas.sqlite3.graphs.sqlite3').exists())

if __name__=='__main__':unittest.main()
