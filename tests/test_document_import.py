import json
from pathlib import Path
import tempfile
import unittest

from news_atlas.documents import import_records, query

ROOT=Path(__file__).resolve().parents[1]
EXAMPLE=ROOT/'skills/stocknexus-document-import/examples/manual.jsonl'


class DocumentImportTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/'data'
        self.input=Path(temp.name)/'records.jsonl'

    def apply(self,file=EXAMPLE,source='manuals',preview=False):
        return import_records(self.root,'my_research',source,file,preview)

    def write(self,rows):
        self.input.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return self.input

    def test_preview_replay_revision_and_pinned_citation(self):
        self.assertEqual(self.apply(preview=True)['added'],3)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.apply()['undated'],3)
        self.assertEqual(self.apply()['unchanged'],3)
        self.assertEqual(len(list(self.root.rglob('*.jsonl'))),1)
        claim={'kind':'claim','id':'check','title':'Check power first','layer':'L2','question':'What first?',
               'links':[{'type':'cites','source':'manuals','id':'fan-check','revision':1}]}
        self.apply(self.write([claim]),'analysis')
        section=json.loads(EXAMPLE.read_text().splitlines()[-1])
        self.apply(self.write([{**section,'text':'Updated instructions'}]))
        self.assertEqual(query(self.root,'my_research','manuals','fan-check',1)['record']['text'],section['text'])
        current=query(self.root,'my_research','manuals')['nodes']
        self.assertEqual(next(n for n in current if n['id']=='fan-check')['revision'],2)
        self.assertEqual(query(self.root)['collections'][0]['sources'],{'manuals':3,'analysis':1})

    def test_bad_batch_and_cycle_preserve_tree(self):
        self.apply()
        rows=[json.loads(line) for line in EXAMPLE.read_text().splitlines()]
        for extra in [{'parent_id':'fan-check'}, {'parent_id':'missing'}, {'path':'../outside'},
                      {'links':[{'id':'missing','type':'supports'}]}]:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.apply(self.write([{**rows[0],**extra}]))
        self.assertTrue(all(n['revision']==1 for n in query(self.root,'my_research')['nodes']))
        self.assertEqual(self.apply(self.write([rows[0],rows[0]]))['duplicate_lines'],1)
        with self.assertRaises(ValueError):
            self.apply(self.write([rows[0],{**rows[0],'title':'different'}]))
