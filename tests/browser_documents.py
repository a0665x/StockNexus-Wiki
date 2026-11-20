"""Real document upload UI and SQLite; temporary data, no model or news calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

from browser_chat_language import Browser
from browser_wiki_timeline import click, key
import server
from news_atlas.documents import query
from news_atlas.graph_storage import GraphRepository


ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-documents-') as tmp:
        folder = Path(tmp)
        data = folder / 'data'
        unexpected = []

        class Handler(server.Handler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.path.startswith('/api/documents/import?'):
                    return super().do_POST()
                unexpected.append(self.path)
                self.json_response(403, {'error': 'Only document import is allowed in this test'})

        http = server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        http.store = GraphRepository(data / 'news-atlas.sqlite3')
        url = f'http://127.0.0.1:{http.server_port}'
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        browser = None
        try:
            with patch.dict(os.environ, {'NEWS_ATLAS_WIKI_ORIGINS': url}):
                browser = Browser(folder / 'browser')
                page = browser.page(url + '/documents')
                page.wait("document.querySelector('#importDocuments')?.onsubmit != null")
                page.check('document graph keeps layout guidance behind a named control',
                           "document.querySelector('#layoutNote').hidden&&!!document.querySelector('[aria-describedby=layoutNote]')")
                click(page,'button[aria-describedby=layoutNote]')
                page.check('opening layout help explains distance and leaves import idle',
                           "document.querySelector('#layoutNote').innerText.includes('遠近由布局決定')&&"
                           "!document.querySelector('#importStatus').textContent")
                key(page,'Escape',27)
                assert page.js("document.querySelector('#layoutNote').hidden")

                def upload(path, mode='apply', source='manuals'):
                    page.js("document.querySelector('[name=source]').value=" + json.dumps(source))
                    dom = page.call('DOM.getDocument')['root']['nodeId']
                    node = page.call('DOM.querySelector', {
                        'nodeId': dom, 'selector': 'input[name=records]'})['nodeId']
                    page.call('DOM.setFileInputFiles', {'nodeId': node, 'files': [str(path)]})
                    page.js(f"document.querySelector('button[value={mode}]').click()")
                    page.wait("document.querySelector('#importDocuments').ariaBusy === 'false'")
                    return page.js("document.querySelector('#importStatus').textContent")

                example = ROOT / 'skills/stocknexus-document-import/examples/manual.jsonl'
                assert '預覽（未寫入）' in upload(example, 'preview')
                assert not (data / 'graph/my_research/documents.sqlite3').exists()
                print('PASS preview leaves document storage absent', flush=True)
                assert '新增 3' in upload(example)
                page.wait("document.querySelector('#counts').textContent.startsWith('3 節點 · 2 關係')")
                assert '未變更 3' in upload(example)
                page.check('3D canvas initializes', "!!document.querySelector('#docGraph canvas') && !document.querySelector('#counts').textContent.includes('3D 無法使用')")
                print('PASS upload opens hierarchy and retry is idempotent', flush=True)

                rows = [json.loads(line) for line in example.read_text().splitlines()]
                original = rows[-1]['text']
                rows[-1]['text'] = 'Updated local fixture instructions.'
                updated = folder / 'updated.jsonl'
                updated.write_text('\n'.join(json.dumps(row) for row in rows))
                assert '更新 1' in upload(updated)
                claim = folder / 'claim.jsonl'
                claim.write_text(json.dumps({
                    'id': 'fixture-claim', 'kind': 'claim', 'title': 'Fixture L2 claim',
                    'layer': 'L2', 'question': 'What should be checked first?',
                    'links': [{'type': 'cites', 'source': 'manuals', 'id': 'fan-check', 'revision': 1}]
                }))
                assert '新增 1' in upload(claim, source='analysis')
                page.js("document.querySelector('#outline .entry').click()")
                page.js("document.querySelector('#details button').click()")
                page.wait("document.querySelector('#details pre')?.textContent === " + json.dumps(original))
                page.check('citation reads original revision after update', "document.querySelector('#details').textContent.includes('v1')")

                page.js("document.querySelector('#documentChoices input[value=manuals]').click()")
                page.wait("document.querySelector('#counts').textContent.startsWith('4 節點 · 3 關係')")
                page.js("const layers=document.querySelector('#layers');layers.value='L2';layers.dispatchEvent(new Event('change'))")
                page.wait("document.querySelector('#counts').textContent.startsWith('1 節點 · 0 關係')")
                print('PASS combined sources and L2 display filter', flush=True)

                bad = folder / 'invalid.jsonl'
                bad.write_text(example.read_text() + '\n{invalid}')
                assert 'Line ' in upload(bad)
                assert len(query(data, 'my_research')['nodes']) == 4
                assert page.js('window.languageErrors') == []
                page.call('Page.reload')
                page.wait("document.querySelector('#counts').textContent.startsWith('1 節點')")
                assert query(data, 'my_research', 'manuals', 'fan-check', 2)['record']['text'] == rows[-1]['text']
                assert not unexpected, unexpected
                assert page.js('window.languageErrors') == []
                print('PASS invalid upload preserves data; reload restores saved graph; no model writes or JS errors', flush=True)

                articles = folder / 'untitled'
                articles.mkdir()
                bodies = {
                    'note-a.txt': 'Device A stops when its cooling fan loses power.',
                    'note-b.txt': 'For Device A cooling failures, check the fan power supply.',
                    'other.txt': 'The library opens on weekdays.',
                }
                for filename, body in bodies.items():
                    (articles / filename).write_text(body, encoding='utf-8')
                export = folder / 'untitled.jsonl'
                scripts = ROOT / 'skills/stocknexus-document-import/scripts'
                subprocess.run([sys.executable, str(scripts/'convert_folder.py'), str(articles),
                                '--output', str(export)], check=True)
                records = [json.loads(line) for line in export.read_text().splitlines()]
                by_path = {record['path']: record for record in records}
                reason = 'Both passages concern Device A fan power; literal markup <b>stays text</b>.'
                by_path['note-a.txt']['links'] = [{'id': by_path['note-b.txt']['id'],
                                                  'type': 'related', 'rationale': reason}]
                export.write_text('\n'.join(json.dumps(record) for record in records))
                subprocess.run([sys.executable, str(scripts/'validate_export.py'), str(export),
                                '--input', str(articles)], check=True)
                page.js("document.querySelector('[name=collection]').value='untitled'")
                assert '新增 3' in upload(export)
                page.wait("document.querySelector('#counts').textContent.startsWith('3 節點 · 1 關係')")
                page.js("[...document.querySelectorAll('#outline .entry')].find(el=>el.textContent==='note-a').click()")
                page.check('untitled article keeps its body and unknown date',
                           "document.querySelector('#details').textContent.includes('日期未知') && document.querySelector('#details pre').textContent === " + json.dumps(bodies['note-a.txt']))
                page.check('content relation has readable literal rationale',
                           "document.querySelector('#details').textContent.includes(" + json.dumps(reason) + ") && !document.querySelector('#details b')")
                page.js("document.querySelector('#details button').click()")
                page.wait("document.querySelector('#details h2').textContent === 'note-b'")
                page.check('unrelated article remains in the same graph',
                           "[...document.querySelectorAll('#outline .entry')].some(el=>el.textContent==='other')")
                docs = browser.page(url + '/docs')
                docs.wait("!!document.querySelector('#swagger-ui .info')&&!!document.querySelector('#workbenchHelpWord')")
                click(docs,'button[aria-describedby=apiUsageHelp]')
                docs.check('API navigation exposes its help and both machine-readable contracts',
                           "document.querySelector('#apiUsageHelp').innerText.includes('快取')&&"
                           "!!document.querySelector('nav a[href=\"/openapi.json\"]')&&!!document.querySelector('nav a[href=\"/api/schema\"]')")
                assert docs.js('window.languageErrors') == []
                assert not unexpected, unexpected
                assert page.js('window.languageErrors') == []
                print('PASS heading-free, undated articles: converter -> validator -> Web upload -> explained content link', flush=True)
        finally:
            if browser:
                browser.close()
            http.shutdown()
            http.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
