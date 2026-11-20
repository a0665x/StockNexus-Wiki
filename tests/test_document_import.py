import json
import shutil
import subprocess
import sys
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

    def test_untitled_undated_articles_share_collection_with_explained_content_link(self):
        folder = self.input.parent / 'articles'
        originals = {
            'alpha/notes.txt': 'Device A stops when its cooling fan loses power.',
            'beta/notes.txt': 'For Device A cooling failures, check the fan power supply.',
            'other.txt': 'The library opens on weekdays.',
        }
        for relative, text in originals.items():
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        scripts = ROOT / 'skills/stocknexus-document-import/scripts'
        conversion = subprocess.run([sys.executable, str(scripts/'convert_folder.py'), str(folder),
                                     '--output', str(self.input)], capture_output=True, text=True)
        self.assertEqual(conversion.returncode, 0, conversion.stderr)
        rows = [json.loads(line) for line in self.input.read_text().splitlines()]
        docs = {row['path']: row for row in rows if row['kind'] == 'document'}
        self.assertEqual(set(docs), set(originals))
        self.assertEqual(len({row['id'] for row in docs.values()}), 3)
        self.assertEqual(docs['alpha/notes.txt']['title'], 'notes')
        self.assertEqual(docs['beta/notes.txt']['title'], 'notes')
        for path, row in docs.items():
            self.assertEqual(row['text'], originals[path])
            self.assertIsNone(row.get('published_at'))
            self.assertFalse(row.get('links'))  # Conversion alone invents no content relations.
        # An external agent supplies this relation after reading both source passages.
        rationale = 'Both passages address loss of power to the cooling fan of Device A.'
        docs['alpha/notes.txt']['links'] = [{'type': 'related', 'id': docs['beta/notes.txt']['id'],
                                            'rationale': rationale}]
        self.write(rows)
        validation = subprocess.run([sys.executable, str(scripts/'validate_export.py'), str(self.input),
                                     '--input', str(folder)], capture_output=True, text=True)
        self.assertEqual(validation.returncode, 0, validation.stderr)
        self.assertEqual(self.apply(self.input, preview=True)['undated'], 5)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.apply(self.input)['added'], 5)
        saved = query(self.root, 'my_research')['nodes']
        self.assertEqual(len([row for row in saved if row['kind'] == 'document']), 3)
        linked = next(row for row in saved if row['id'] == docs['alpha/notes.txt']['id'])
        self.assertEqual(linked['links'][0]['rationale'], rationale)
        self.assertEqual(self.apply(self.input)['unchanged'], 5)
        for invalid in ('', 'x' * 2001, 42):
            with self.subTest(rationale=invalid), self.assertRaises(ValueError):
                self.apply(self.write([{**docs['alpha/notes.txt'], 'links': [
                    {**docs['alpha/notes.txt']['links'][0], 'rationale': invalid}]}]))

    def test_blank_filename_label_has_fallback_without_changing_body_or_path(self):
        article = self.input.parent / '   .txt'
        article.write_text('An article without a heading or a date.', encoding='utf-8')
        scripts = ROOT / 'skills/stocknexus-document-import/scripts'
        subprocess.run([sys.executable, str(scripts/'convert_folder.py'), str(article),
                        '--output', str(self.input)], check=True)
        row = json.loads(self.input.read_text())
        self.assertEqual(row['title'], 'Untitled document')
        self.assertEqual(row['path'], article.name)
        self.assertEqual(row['text'], article.read_text())
        self.assertIsNone(row.get('published_at'))
        self.assertEqual(self.apply(self.input)['added'], 1)

    def test_web_import_preview_apply_retry_and_invalid_file(self):
        from email.message import Message
        from io import BytesIO
        from types import SimpleNamespace
        from unittest.mock import Mock
        from news_atlas.documents import handle_import

        def upload(mode, data, origin='http://localhost:8765'):
            headers = Message()
            headers['Content-Type'] = 'application/x-ndjson'
            headers['Content-Length'] = str(len(data))
            headers['Host'] = 'localhost:8765'
            headers['Origin'] = origin
            handler = SimpleNamespace(command='POST', headers=headers, client_address=('127.0.0.1', 1000),
                                      path=f'/api/documents/import?collection=research&source=notes&mode={mode}',
                                      rfile=BytesIO(data), store=SimpleNamespace(path=self.root/'news-atlas.sqlite3'),
                                      json_response=Mock())
            handle_import(handler)
            return handler.json_response.call_args.args

        data = EXAMPLE.read_bytes()
        self.assertEqual(upload('apply', data, 'https://elsewhere.example')[0], 403)
        self.assertEqual(upload('preview', data)[1]['added'], 3)
        self.assertFalse(self.root.exists())
        self.assertEqual(upload('apply', data)[1]['added'], 3)
        self.assertEqual(upload('apply', data)[1]['unchanged'], 3)
        self.assertEqual(upload('apply', data + b'{invalid}')[0], 400)
        self.assertEqual(query(self.root)['collections'], [{'id':'research','sources':{'notes':3}}])

    def test_portable_agent_handoff_then_web_compatible_import(self):
        base = self.input.parent
        skill = base / 'standalone' / 'stocknexus-document-import'
        shutil.copytree(ROOT/'stocknexus-document-import', skill)
        folder = base/'research'
        chapter = folder/'手冊'/'研究.md'
        chapter.parent.mkdir(parents=True)
        chapter.write_text('# 總論\n## 方法\n原文。\n', encoding='utf-8')
        output = base/'records.jsonl'
        def run(script, *args):
            return subprocess.run([sys.executable, '-E', str(skill/'scripts'/script), *map(str,args)],
                                  cwd=base, text=True, capture_output=True)
        def validate(source):
            return run('validate_export.py', output, '--input', source)
        for source, expected in [(chapter, 3), (folder, 4)]:
            conversion = run('convert_folder.py', source, '--output', output)
            self.assertEqual(conversion.returncode, 0, conversion.stderr)
            validation = validate(source)
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertEqual(self.apply(output, preview=True)['added'], expected)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.apply(output)['added'], 4)
        self.assertEqual(self.apply(output)['unchanged'], 4)
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        doc = next(r for r in rows if r['kind'] == 'document')
        section = next(r for r in rows if r['kind'] == 'section')
        for bad in ([*rows, rows[0]], [r for r in rows if r != doc],
                    [{**r, 'parent_id': None} if r == doc else r for r in rows],
                    [{**r, 'parent_id': None} if r == section else r for r in rows],
                    [{**r, 'parent_id': r['id']} if r == section else r for r in rows]):
            with self.subTest(bad=bad):
                output.write_text(''.join(json.dumps(r)+'\n' for r in bad))
                self.assertNotEqual(validate(folder).returncode, 0)
