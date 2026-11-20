"""BDD: SQLite -> research HTTP -> browser ack -> real stdio MCP -> chat table.
Agent inference is deterministic here; this verifies transport/evidence contracts, not prediction quality.
"""
import datetime as dt,json,os,subprocess,tempfile,threading,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from browser_chat_language import Browser
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.wiki.research import Research
from news_atlas.wiki.store import now,capture
from test_server import row
from test_wiki import proposal
from test_research import fusion


def main():
 live=os.environ.get('ATLAS_BDD_LIVE')=='1' or bool(os.environ.get('ATLAS_BDD_REPLAY'))
 with tempfile.TemporaryDirectory(prefix='l2-chat-bdd-') as tmp:
  folder=Path(tmp);store=GraphRepository(folder/'news.sqlite3');calls=[]
  def runner(s,j,a,c):
   calls.append(j['payload'].get('operation'))
   if j['payload'].get('operation')=='research_fusion':
    p=fusion(a['research_bundle']);p['support']=[c['id'] for c in p['claims'] if 'BULL' in c['statement']];p['counter']=[c['id'] for c in p['claims'] if 'BEAR' in c['statement']]
   else:p=proposal(a);p['nodes'][0]['summary']=a['title']
   return {'proposal':p,'usage':{}}
  wiki=WikiService(store,runner=runner,start_worker=False)
  today=dt.date.fromisoformat(now()[:10])
  for i,(title,days) in enumerate([('BULL cloud demand expands',1),('BEAR cloud cost risk rises',2),('OLD cloud demand report',90),('FUTURE cloud demand report',-1)]):
   a=row(title=title,day=(today-dt.timedelta(days=days)).isoformat(),suffix=str(i));p=wiki.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':[a]});wiki.start({'plan_id':p['plan_id']});wiki.process(wiki.store('NASDAQ:TSLA'))
  ws=wiki.store('NASDAQ:TSLA');ws.configure({**ws.config(),'enabled':False,'catch_up':False});research=Research(ws)
  job=research.query({'query':'cloud demand risk','model':'fixture','lookback_days':120});wiki.tick();j=research.read('job',job['job_id']);assert j['status']=='completed',j;run_id=j['payload']['run_id'];run=research.read('run',run_id)
  assert len(run['bundle']['opinions'])==3;assert run['bundle']['manifest']['excluded']['outside_window']>=1
  print('PASS Given SQLite with recent, old and future news: research snapshot excludes future publications',flush=True)
  if not live:ws.ingest([capture(row(title='NEW uncatalogued demand news',day=today.isoformat(),suffix='pending'))])
  count_before=len(calls)
  wiki.bridge_request=lambda *a,**k:{'models':[{'id':'fixture','name':'Fixture','reasoning':[{'reasoningEffort':'low'}]}],'default_model':'fixture','wiki_ready':True}
  private=folder/'private';private.mkdir();sock=private/'chat.sock';audit=folder/'audit.jsonl';log=(folder/'bridge.log').open('w')
  bridge=subprocess.Popen([os.environ.get('NODE_BIN','/home/nvidia/.nvm/versions/node/v20.19.1/bin/node'),'tests/chat-research-bdd-bridge.mjs',str(sock),str(audit)],stdout=log,stderr=log)
  class Handler(server.Handler):
   def log_message(self,*a):pass
   def test_origin(self):
    # Isolated port; emulate the production facade's host allowlist without touching production.
    if self.path.startswith('/api/chat/'):
     self.headers.replace_header('Host','127.0.0.1:8765')
     if self.headers.get('Origin'):self.headers.replace_header('Origin','http://127.0.0.1:8765')
   def do_GET(self):self.test_origin();super().do_GET()
   def do_POST(self):self.test_origin();super().do_POST()
  http=server.ThreadingHTTPServer(('127.0.0.1',0),Handler);http.store=store;http.wiki=wiki;url='http://127.0.0.1:'+str(http.server_port);os.environ['NEWS_ATLAS_WIKI_ORIGINS']=url
  threading.Thread(target=http.serve_forever,daemon=True).start();browser=Browser(folder/'chrome')
  try:
   for _ in range(100):
    if sock.exists():break
    time.sleep(.05)
   assert sock.exists(),(folder/'bridge.log').read_text()
   page=browser.page(url);page.wait("typeof AtlasWiki!=='undefined'");page.js('AtlasWiki.show()');page.wait("$('wikiInstrument').value==='NASDAQ:TSLA'&&!!AtlasWiki.graph()")
   page.js('AtlasWiki.setResearch('+json.dumps(run)+','+json.dumps(run_id)+')')
   page.js("$('wikiLayer').value='L2';$('wikiLayer').dispatchEvent(new Event('change'))")
   page.wait("AtlasWiki.graph().graphData().nodes.every(n=>n.layer==='L2')")
   # No L1 rendered, but the MCP must retrieve all three DB-backed L1 premises.
   page.js("$('wikichatTab').click()")
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent.includes('已連線')")
   page.js("(()=>{const box=document.querySelector('#wikichatPage textarea');box.value='請根據近期消息與 L1+L2 的支持及反對觀點，分析未來三個交易日偏多或偏空，以及預期目標價；請用 Markdown 表格列出兩種情境、來源與日期。';box.dispatchEvent(new Event('input'));document.querySelector('#wikichatPage form').requestSubmit()})()")
   for _ in range(330 if live else 40):
    status=page.js("document.querySelector('#wikichatPage .chat-status').textContent")
    if status=='回覆完成':break
    if status.startswith('回覆失敗'):raise AssertionError(status)
    time.sleep(.5)
   assert status=='回覆完成',status
   if live:
    answer=page.js("[...document.querySelectorAll('#wikichatPage .assistant')].at(-1).textContent")
    # DOM text is asserted below; preserve the model Markdown separately for audit.
    audit_text=audit.read_text();Path('/tmp/research-chat-live-audit.jsonl').write_text(audit_text)
    items=[json.loads(x).get('live_item',{}) for x in audit_text.splitlines()]
    Path('/tmp/research-chat-live-answer.md').write_text([i['text'] for i in items if i.get('type')=='agent_message'][-1])
    assert 'read_research' in audit_text and 'mcp_tool_call' in audit_text
    assert (today-dt.timedelta(days=1)).isoformat() in answer and (today-dt.timedelta(days=2)).isoformat() in answer
    assert page.js("document.querySelectorAll('#wikichatPage table').length>0")
    assert len(calls)==count_before
    print('PASS recorded/live model final answer: MCP trace, recent source dates and rendered table; no extra compilation',flush=True)
    import base64
    Path('/tmp/research-chat-table.png').write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
    return
   page.check('Then table has semantic headers, two scenarios and dated sources',"document.querySelectorAll('#wikichatPage table thead th').length===3&&document.querySelectorAll('#wikichatPage table tbody tr').length===2&&document.querySelectorAll('#wikichatPage table a').length===2")
   page.check('Then source HTML stays inert and fenced tables stay code',"!window.injected&&!document.querySelector('#wikichatPage .assistant img')&&document.querySelector('#wikichatPage pre code').textContent.includes('<table>')")
   page.check('Then no unsupported numeric three-day target',"document.querySelector('#wikichatPage .assistant').textContent.includes('無法估計數字目標價')")
   records=[json.loads(x) for x in audit.read_text().splitlines()];r=next(x['result'] for x in records if x.get('name')=='read_research')
   assert len(r['bundle']['opinions'])==3 and r['temporal']['recent_count']==2 and r['run_id']==run_id
   print('PASS When Chat calls real stdio MCP: exact DB L2 + L1 + dated citations arrive despite L2-only rendering',flush=True)
   assert len(calls)==count_before,'Read path must not call compilation or research models'
   page.call('Emulation.setDeviceMetricsOverride',{'width':700,'height':900,'deviceScaleFactor':1,'mobile':False})
   page.check('Then table overflow stays within chat',"(()=>{const t=document.querySelector('.chat-table-scroll');return t.scrollWidth>=t.clientWidth&&t.getBoundingClientRect().width<=document.querySelector('#wikichatPage').getBoundingClientRect().width})()")
   page.check('Then browser has no runtime errors',"languageErrors.length===0")
   print('PASS BDD temporal evidence, API/MCP integration, safe responsive table; deterministic agent, no paid inference',flush=True)
  finally:
   browser.close();http.shutdown();http.server_close();bridge.terminate();bridge.wait(timeout=10);log.close()

if __name__=='__main__':main()
