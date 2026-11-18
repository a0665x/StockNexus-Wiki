"""Merge two independent research histories through the CLI; exercise the local HTTP workflow."""
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile
import unittest

from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.research import Research
import test_agent_workflow
from test_research import fusion
from test_server import row
from test_wiki import proposal

ROOT=Path(__file__).resolve().parents[1]

class MergeComparisonTests(unittest.TestCase):
    request=test_agent_workflow.AgentWorkflowTests.request
    stock='NASDAQ:TSLA'

    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.folder=Path(tmp.name)
        self.model_calls=[]
        self.verdict='conflicting'
        self.refs=['1.1','2.1']

    def workspace(self,name,statement):
        folder=self.folder/name/'data'
        repo=GraphRepository(folder/'news-atlas.sqlite3')
        article=row(title=statement,suffix=name.replace(' ','-'),day=(dt.date.today()-dt.timedelta(days=1)).isoformat())
        repo.for_ticker('TSLA').save('massive','tsla',[article],[])
        def runner(store,job,article,context):
            op=job['payload']['operation']
            if op=='research_fusion':return {'proposal':fusion(article['research_bundle'])}
            if op=='compare_viewpoints':
                self.model_calls.append(op)
                return {'proposal':{'verdict':self.verdict,'reason':'Evidence applies to the stated period',
                        'summary':'Conditional comparison','citations':self.refs}}
            value=proposal(article);value['nodes'][0]['summary']=article['title']
            return {'proposal':value}
        service=WikiService(repo,runner=runner,start_worker=False)
        store=service.store(self.stock);preview=service.plan({'instrument':self.stock,'articles':[article],'model':'fixture'})
        service.start({'plan_id':preview['plan_id']});service.tick();service.tick()
        research=Research(store)
        job=research.query({'query':'overview','model':'fixture'})
        research.process(service)
        run_id=research.read('job',job['job_id'])['payload']['run_id']
        return folder,repo,service,research,run_id

    def cli(self,source,target,*opts):
        output=subprocess.check_output([str(ROOT/'merge_data.sh'),'--from',str(source),'--to',str(target),*opts],text=True)
        return json.loads(output)

    def test_cli_paths_and_comparison(self):
        a,_,_,_,foreign_id=self.workspace('source package','Demand is growing')
        b,repo,service,local,local_id=self.workspace('recipient','Demand is shrinking')
        self.host=SimpleNamespace(store=repo,wiki=service)
        before=local.read('run',local_id)
        original_graph=local.store.graph()
        preview=self.cli(a,b,'--dry-run')
        self.assertFalse(preview['committed'])
        self.assertIn('graph/TSLA/news-atlas.sqlite3',preview['databases'])
        self.assertIn('llm_wiki/TSLA/wiki.sqlite3',preview['databases'])
        self.cli(a/'graph/TSLA',b)
        self.assertEqual(local.store.graph()['version'],original_graph['version'])
        self.cli(a/'llm_wiki/TSLA',b);self.cli(a,b);self.cli(a,b)
        self.assertEqual(local.store.graph()['version'],2)
        self.assertEqual(local.read('run',local_id)['result'],before['result'])
        self.assertEqual(local.read('run',local_id)['bundle'],before['bundle'])
        self.assertEqual([r['id'] for r in local.read('runs')['runs']],[local_id])
        self.assertEqual(self.model_calls,[])
        prefix='/api/wiki/research/'
        rows=self.request(prefix+'comparison-candidates',instrument=self.stock)['items']
        self.assertEqual(len(rows),4)
        self.assertIn('imported',next(r['origin'] for r in rows if r['ref'].startswith('L1/') and r['title']=='Demand is growing'))
        local_ref='L2/'+local_id+'/c1';import_ref='L2/'+foreign_id+'/c1'
        self.assertIn('imported',next(r['origin'] for r in rows if r['ref']==import_ref))
        for refs,verdict in [([local_ref,import_ref],'conflicting'),([import_ref,next(r['ref'] for r in rows if r['ref'].startswith('L1/') and r['title']=='Demand is growing')],'similar')]:
            body={'instrument':self.stock,'model':'fixture','refs':refs}
            self.verdict=verdict
            first=self.request(prefix+'compare',body)
            duplicate=self.request(prefix+'compare',{**body,'refs':list(reversed(refs))})
            self.assertEqual(first,duplicate)
            service.tick()
            job=self.request(prefix+'job',instrument=self.stock,id=first['job_id'])
            self.assertEqual(job['status'],'completed',job['error'])
            report=self.request(prefix+'comparison',instrument=self.stock,id=job['payload']['comparison_id'])
            self.assertEqual(report['result']['verdict'],verdict)
            self.assertEqual({s['ref'] for s in report['inputs']},set(refs))
            self.assertEqual(self.request(prefix+'compare',body)['status'],'completed')
        self.refs=['not-in-evidence']
        failed=self.request(prefix+'compare',{**body,'reasoning_effort':'low'})
        service.tick()
        failure=self.request(prefix+'job',instrument=self.stock,id=failed['job_id'])
        self.assertEqual(failure['status'],'failed')
        self.assertNotIn('comparison_id',failure['payload'])
        self.assertEqual(len(self.model_calls),3)
        self.assertEqual(len(self.request(prefix+'comparisons',instrument=self.stock)['jobs']),3)
        self.assertEqual(local.store.graph()['version'],2)
