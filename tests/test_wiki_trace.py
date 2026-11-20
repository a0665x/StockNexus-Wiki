"""Trace the real serial/parallel call path without paid inference."""
import json
import time
import unittest
import test_wiki_parallel
from test_wiki import proposal

class TraceTests(unittest.TestCase):
    setUp=test_wiki_parallel.ParallelTests.setUp
    start=test_wiki_parallel.ParallelTests.start
    def test_stage_log_attributes_slow_model_and_keeps_content_private(self):
        def runner(store,job,article,context):
            time.sleep(.025)
            return {'proposal':proposal(article),'usage':{'input_tokens':17,'output_tokens':9}}
        self.service.runner=runner
        job=self.start((1,),workers=1)
        self.service.process(self.store,max_groups=1)
        path=self.service.data_root/'private/wiki-trace/python.jsonl'
        self.assertTrue(path.exists(),'No durable Wiki stage log: slow model time cannot be attributed')
        rows=[json.loads(s) for s in path.read_text().splitlines()]
        ends=[r for r in rows if r['event']=='end']
        model=next(r for r in ends if r['stage']=='model_call')
        self.assertGreaterEqual(model['elapsed_ms'],20)
        self.assertEqual(model['usage']['input_tokens'],17)
        self.assertTrue(model['job_id'])
        self.assertTrue(model['call_id'])
        self.assertIn('publish',{r['stage'] for r in ends})
        self.assertNotIn('Unique topic',path.read_text())

    def test_failure_has_safe_location_and_terminal_state(self):
        def runner(*args):raise TimeoutError('secret-token and private article text')
        self.service.runner=runner;self.start((1,),workers=1)
        self.service.process(self.store,max_groups=1)
        raw=(self.service.data_root/'private/wiki-trace/python.jsonl').read_text()
        rows=[json.loads(s) for s in raw.splitlines()]
        errors=[r for r in rows if r['event']=='error' and r['stage']=='model_call']
        self.assertEqual(errors[0]['error_code'],'timeout')
        self.assertTrue(errors[0]['frames'])
        self.assertNotIn('secret-token',raw)
        self.assertTrue(any(r.get('status')=='failed' for r in rows))

    def test_rotation_parallel_lines_and_logging_failure_do_not_break_work(self):
        from unittest.mock import patch
        from concurrent.futures import ThreadPoolExecutor
        from news_atlas.wiki.trace import emit
        with patch('news_atlas.wiki.trace.MAX_BYTES',1000):
            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(lambda i:emit(self.store,'state','test',index=i),range(100)))
        folder=self.service.data_root/'private/wiki-trace'
        self.assertLessEqual(len(list(folder.glob('python.jsonl*'))),6)
        for path in folder.glob('python.jsonl*'):
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            for line in path.read_text().splitlines():json.loads(line)
        with patch('news_atlas.wiki.trace.os.open',side_effect=OSError('disk full')):
            self.service.runner=lambda s,j,a,c:{'proposal':proposal(a)}
            self.start((1,),workers=1);self.service.process(self.store,max_groups=1)
        self.assertEqual(self.store.jobs()[0]['status'],'completed')

    def test_three_workers_have_distinct_calls_in_same_job(self):
        self.service.runner=lambda s,j,a,c:{'proposal':proposal(a)}
        self.start((1,1,1),workers=3);self.service.process(self.store,max_groups=1)
        rows=[json.loads(s) for s in (self.service.data_root/'private/wiki-trace/python.jsonl').read_text().splitlines()]
        calls=[r for r in rows if r['stage']=='model_call' and r['event']=='end']
        self.assertEqual({r['worker'] for r in calls},{1,2,3})
        self.assertEqual(len({r['call_id'] for r in calls}),3)
        self.assertEqual(len({r['job_id'] for r in calls}),1)
        from scripts.wiki_trace_report import summarize
        report=summarize(self.service.data_root/'private/wiki-trace',job=calls[0]['job_id'])
        self.assertEqual(report['unfinished_spans'],[])
        self.assertEqual(report['malformed_lines'],0)

import test_research
class ResearchTraceTests(unittest.TestCase):
    setUp=test_research.ResearchTests.setUp
    add=test_research.ResearchTests.add
    query=test_research.ResearchTests.query

    def test_l2_fusion_review_and_failure_remain_separate(self):
        test_research.ResearchTests.test_unsupported_fusion_inference_is_never_published(self)
        rows=[json.loads(s) for s in (self.service.data_root/'private/wiki-trace/python.jsonl').read_text().splitlines()]
        calls=[r for r in rows if r['stage']=='model_call' and r['event']=='end' and r['operation'].startswith('research_')]
        self.assertEqual([r['operation'] for r in calls],['research_fusion','research_review'])
        self.assertEqual(len({r['job_id'] for r in calls}),1)
        self.assertEqual(len({r['call_id'] for r in calls}),2)
        self.assertTrue(any(r['event']=='error' and r['stage']=='job' and r['error_code']=='validation' for r in rows))
