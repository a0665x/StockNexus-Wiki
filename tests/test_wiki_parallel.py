"""Real threaded scheduling and SQLite publication; no external model calls."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from news_atlas.storage import Store
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.store import capture
from news_atlas.wiki.workbench import settings
from test_server import row
from test_wiki import proposal


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.service=WikiService(Store(Path(self.tmp.name)/'news.sqlite3'),start_worker=False)
        self.service.bridge_request=lambda *a,**kw:{}
        self.store=self.service.store('NASDAQ:NVDA')

    def start(self, sizes=(1,1,1),workers=3):
        trees=[];rows=[]
        for n,size in enumerate(sizes):
            members=[capture(row(title=f'Unique topic {n} article {i}',suffix=f'{n}-{i}')) for i in range(size)]
            refs=[{'provider':a['provider'],'id':a['id']} for a in members]
            trees.append({'root_id':str(n),'title':f'Tree {n}','articles':refs,'targets':refs})
            rows.extend(members)
        self.rows=rows;self.store.ingest(rows)
        cfg={**settings({'workers':workers,'strategy':'root'}),'model':'fixture','enabled':False,'catch_up':False,
             'revision_ids':[a['revision_id'] for a in rows], 'graph_context_revisions':[a['revision_id'] for a in rows],
             'graph_selection':{'mode':'coverage','trees':trees},'subscriptions':[]}
        self.store.configure(cfg)
        return self.store.enqueue('fixture',revision_ids=cfg['revision_ids'])

    def test_job_history_does_not_sort_large_frozen_payloads(self):
        # Annual jobs carry megabytes of frozen evidence. A disk-backed sort
        # can exhaust the service's bounded /tmp during concurrent polling.
        with self.store.connection() as db:
            plan = db.execute('EXPLAIN QUERY PLAN SELECT * FROM jobs ORDER BY created_at DESC LIMIT 30').fetchall()
        self.assertFalse(any('TEMP B-TREE' in r[3] for r in plan), [tuple(r) for r in plan])

    def test_three_real_calls_overlap_and_publish_once_with_unequal_trees(self):
        barrier=threading.Barrier(3);seen=[];guard=threading.Lock()
        def runner(store,job,a,context):
            with guard:seen.append((a['_group']['root_id'],job['call_id']))
            barrier.wait(timeout=5)
            return {'proposal':proposal(a),'usage':{'input_tokens':10}}
        self.service.runner=runner;self.start((1,2,3))
        self.service.process(self.store,max_groups=1)
        job=self.store.jobs()[0]
        self.assertEqual(job['status'],'completed',job['error'])
        self.assertEqual(job['done'],6)
        self.assertEqual(len({i for _,i in seen}),3)
        self.assertEqual(job['usage']['input_tokens'],30)
        self.assertEqual(len(job['payload']['workers_state']),3)
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM wiki_segments').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT count(DISTINCT revision) FROM extractions').fetchone()[0],6)
        self.assertEqual(self.store.graph()['version'],3)
        from news_atlas.wiki.parallel import tree_coverage
        self.assertEqual(tree_coverage(self.store.config(),self.rows,self.rows[:1]),{'total':3,'done':2,'pending':1})

    def test_five_workers_negotiate_bridge_capacity_before_any_model_call(self):
        routes=[]
        def bridge(path,body=None,timeout=None):
            routes.append(path)
            return {'ready':True}
        self.service.bridge_request=bridge
        self.start((1,)*5,workers=5)
        self.service.process(self.store)
        self.assertEqual(routes,['/status'])
        self.assertIn('supports 1 worker',self.store.jobs()[0]['error'])
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM calls').fetchone()[0],0)

    def test_five_independent_trees_enter_bridge_together(self):
        barrier=threading.Barrier(5)
        def bridge(path,body=None,timeout=None):
            if path=='/status':return {'wiki_worker_limit':10}
            self.assertEqual(path,'/wiki/compile')
            barrier.wait(timeout=5)
            return {'proposal':{'nodes':[],'relations':[]},'usage':{}}
        self.service.bridge_request=bridge
        self.start((1,)*5,workers=5)
        self.service.process(self.store)
        job=self.store.jobs()[0]
        self.assertEqual(job['status'],'completed',job['error'])
        self.assertEqual(job['done'],5)

    def test_cancel_all_lanes_rejects_late_publication(self):
        entered=threading.Barrier(4);release=threading.Event()
        def runner(*args):
            entered.wait(timeout=5);release.wait(5)
            return {'proposal':{'nodes':[],'relations':[]},'usage':{}}
        self.service.runner=runner;self.start()
        worker=threading.Thread(target=self.service.process,args=(self.store,))
        worker.start();entered.wait(timeout=5)
        self.service.stop_maintenance({'instrument':self.store.instrument});release.set();worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.store.jobs()[0]['status'],'cancelled')
        self.assertEqual(self.store.graph()['version'],0)

    def test_slow_tree_and_timeout_do_not_block_the_backlog_or_shared_reads(self):
        # Keep one turn stuck until another lane publishes a later tree, even
        # though every tree sees the same existing interpretation.
        later_started=threading.Event()
        first_wave=threading.Barrier(3)
        seen=[]
        self.store.context=lambda _: [{'id':'old','kind':'Claim','scope':'old','title':'shared'}]
        def runner(store,job,a,c):
            root=a['_group']['root_id']
            seen.append(root)
            if root in ('0','1','2'):
                first_wave.wait(timeout=5)
            if root=='0':
                self.assertTrue(later_started.wait(5))
                raise TimeoutError('model did not respond')
            if root=='4':
                later_started.set()
            return {'proposal':proposal(a),'usage':{}}
        self.service.runner=runner
        self.service.other_work_waiting=lambda _: True
        self.start((1,)*7)
        self.service.process(self.store,max_groups=1)
        # If the scheduler yielded to the next stock after the slow lane
        # finished, let the next fair turn drain any remaining eligible trees.
        self.service.process(self.store,max_groups=1)
        job=self.store.jobs()[0]
        self.assertEqual(job['status'],'failed')
        self.assertIn('model did not respond',job['error'])
        self.assertEqual(job['done'],6)
        self.assertCountEqual(seen,map(str,range(7)))
        self.assertEqual(job['payload']['failed_trees']['0']['code'],'timeout')
        self.assertEqual(job['payload']['failed_tree_count'],1)
        self.assertEqual(job['payload']['last_tree_failure']['stage'],'compiling')

    def test_failed_tree_is_skipped_across_fair_turns_and_retried_on_explicit_resume(self):
        seen=[]
        def runner(store,job,a,c):
            root=a['_group']['root_id'];seen.append(root)
            if root=='0' and seen.count('0')==1:
                raise TimeoutError('model timeout')
            return {'proposal':proposal(a),'usage':{}}
        self.service.runner=runner
        self.start((1,)*5,workers=1)
        self.service.process(self.store,max_groups=1)
        self.assertEqual(self.store.jobs()[0]['status'],'queued')
        for _ in range(4):
            self.service.process(self.store,max_groups=1)
        self.assertEqual(self.store.jobs()[0]['status'],'failed')
        self.assertEqual(seen,['0','1','2','3','4'])
        self.store.enqueue('fixture',revision_ids=self.store.config()['revision_ids'])
        self.service.process(self.store)
        self.assertEqual(seen,['0','1','2','3','4','0'])
        self.assertEqual(self.store.jobs()[0]['status'],'completed')

    def test_racing_revisions_accept_one_update_and_publish_independent_tree(self):
        base={'id':'shared','kind':'Claim','title':'Earlier outlook','scope':'TSLA:earnings'}
        with self.store.connection() as db:
            db.execute('INSERT INTO nodes VALUES (?,?,?,?)',(base['id'],base['kind'],0,json.dumps(base)))
        self.store.context=lambda _: [base]
        concurrent=threading.Barrier(3)
        def runner(store,job,a,context):
            concurrent.wait(timeout=5)
            result=proposal(a)
            if a['_group']['root_id'] in ('0','1'):
                result['relations']=[dict(source='n1',target=base['id'],type='UPDATES',rationale='New evidence',citations=result['nodes'][0]['citations'])]
            return {'proposal':result,'usage':{'input_tokens':5}}
        self.service.runner=runner
        self.start()
        self.service.process(self.store)
        job=self.store.jobs()[0]
        self.assertEqual(job['done'],2)
        self.assertEqual(job['usage']['input_tokens'],15)
        self.assertEqual(job['payload']['last_tree_failure']['code'],'revision_conflict')
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM edges WHERE target='shared' AND json_extract(payload,'$.relation_type')='UPDATES'").fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM rejected_proposals').fetchone()[0],1)

    def test_continuous_watcher_accepts_fresh_evidence_after_an_isolated_failure(self):
        from unittest.mock import patch
        seen=[]
        def runner(store,job,a,c):
            seen.append(a['id'])
            if len(seen)==1:
                raise TimeoutError('fixture timeout')
            return {'proposal':proposal(a),'usage':{}}
        self.service.runner=runner
        self.start((1,),workers=1)
        cfg=self.store.config()
        cfg.update(enabled=True,catch_up=True,graph_universe={'ticker':'NVDA'})
        forest=cfg['graph_selection']
        self.store.configure(cfg)
        self.service.process(self.store)
        self.assertTrue(self.store.config()['enabled'])
        with patch('news_atlas.wiki.forest.prepare',return_value=(self.rows,self.rows,forest)):
            self.service.refresh(self.store)
        self.assertEqual(len(self.store.jobs()),1)
        fresh=capture(row(title='Fresh independent evidence',suffix='fresh'))
        ref={'provider':fresh['provider'],'id':fresh['id']}
        forest['trees'].append({'root_id':'fresh','title':'Fresh','articles':[ref],'targets':[ref]})
        fresh_scope=[*self.rows,fresh]
        with patch('news_atlas.wiki.forest.prepare',return_value=(fresh_scope,fresh_scope,forest)):
            self.service.refresh(self.store)
        self.service.process(self.store)
        self.assertEqual(seen,[self.rows[0]['id'],fresh['id']])
        self.assertEqual(self.store.jobs()[0]['status'],'completed')
        self.assertEqual(len(self.store.pending()),1)
        self.assertTrue(self.store.config()['enabled'])

    def test_shared_authentication_failure_stops_new_calls(self):
        from news_atlas.wiki.compiler import WikiBridgeError
        def runner(*args):
            raise WikiBridgeError('expired login','authentication')
        self.service.runner=runner
        self.start((1,)*5,workers=1)
        self.service.process(self.store)
        self.assertEqual(self.store.jobs()[0]['error'],'expired login')
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM calls').fetchone()[0],1)

    def test_published_segments_survive_explicit_resume_without_replay(self):
        calls=[]
        def runner(store,job,a,c):
            calls.append(a['_group']['part'])
            if len(calls)==2:raise RuntimeError('interrupted')
            return {'proposal':proposal(a),'usage':{}}
        self.service.runner=runner;self.start((15,),1)
        self.service.process(self.store)
        self.assertEqual(self.store.jobs()[0]['status'],'failed')
        self.assertEqual(self.store.jobs()[0]['done'],0)
        self.assertEqual(self.store.graph()['version'],1)
        calls.clear()
        def resume(store,job,a,c):
            calls.append(a['_group']['part']);return {'proposal':proposal(a),'usage':{}}
        self.service.runner=resume
        self.store.enqueue('fixture',revision_ids=self.store.config()['revision_ids'])
        self.service.process(self.store)
        self.assertEqual(calls,[2])
        self.assertEqual(self.store.jobs()[0]['done'],15)
        self.assertEqual(self.store.graph()['version'],2)

    def test_segment_checkpoints_merge_with_remapped_versions(self):
        import subprocess,sys,sqlite3
        self.service.runner=lambda store,job,a,c:{'proposal':proposal(a),'usage':{}}
        self.start();self.service.process(self.store)
        target=Path(self.tmp.name)/'merged'
        command=[sys.executable,str(Path(__file__).parents[1]/'scripts/merge_data.py'),'--from',str(self.store.folder),'--to',str(target)]
        for _ in range(2):
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        with sqlite3.connect(target/'llm_wiki/NVDA/wiki.sqlite3') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM wiki_segments').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT count(*) FROM wiki_segments s JOIN versions v ON v.version=s.version').fetchone()[0],3)

    def test_worker_limit_is_strict(self):
        for value in (0,2,11,True,'3'):
            with self.assertRaises(ValueError):settings({'workers':value})
        for value in (1,3,5,10):self.assertEqual(settings({'workers':value})['workers'],value)

if __name__=='__main__':unittest.main()
