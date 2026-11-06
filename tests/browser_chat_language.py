"""Real HTTP assets + independent Chrome tabs/profiles; deterministic chat transport.
No production data, model calls, or user browser profiles. Exercise lifecycle order,
not just a translated screenshot. Keep source/model text unchanged.
"""
import json,os,signal,shutil,subprocess,tempfile,threading,time,urllib.request,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import websocket
import server
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.search import query_key
from test_server import row
from test_wiki import proposal

class Page:
 def __init__(self,port,target):
  self.port=port;self.target=target;self.serial=0
  tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
  self.ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in tabs if t['id']==target),timeout=30,suppress_origin=True)
 def call(self,method,params=None):
  self.serial+=1;self.ws.send(json.dumps({'id':self.serial,'method':method,'params':params or {}}))
  while True:
   value=json.loads(self.ws.recv())
   if value.get('id')==self.serial:
    if 'error' in value:raise RuntimeError(value['error'])
    return value.get('result',{})
 def js(self,expression):
  value=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
  if 'exceptionDetails' in value:raise RuntimeError(value['exceptionDetails'])
  return value.get('result',{}).get('value')
 def wait(self,expression):
  for _ in range(160):
   if self.js(expression):return
   time.sleep(.06)
  raise AssertionError(expression+'\n'+str(self.js("document.querySelector('#wikichatPage')?.innerText")))
 def language(self,lang):
  self.js(f"document.getElementById('language').value={json.dumps(lang)};document.getElementById('language').dispatchEvent(new Event('change'))")
 def open_wiki(self):
  self.wait("typeof AtlasWiki!=='undefined'&&typeof AtlasRuntime!=='undefined'&&AtlasRuntime.state().counts.loaded>0")
  self.js('AtlasWiki.show()')
  self.wait("AtlasWiki.runtime.data().nodes.length>0")
 def chat(self):self.js("document.getElementById('wikichatTab').click()")
 def check(self,label,expression):
  value=self.js(expression);print(label,value,flush=True)
  assert value,label+'\n'+str(self.js("document.querySelector('#wikichatPage')?.innerText"))
 def labels(self):
  return self.js("(()=>{const p=document.querySelector('#wikichatPage');return [...p.querySelectorAll('.chat-toolbar,.chat-context,.chat-status')].map(n=>n.textContent).join(' ')+' '+p.querySelector('textarea').placeholder+' '+p.querySelector('textarea').getAttribute('aria-label')+' '+p.querySelector('.chat-send').title+' '+document.querySelector('#wikinewsTab').textContent})()")

class Browser:
 def __init__(self,folder):
  self.folder=folder;folder.mkdir();self.log=(folder/'chrome.log').open('w')
  self.proc=subprocess.Popen([os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium'),'--headless=new','--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader','--window-size=1393,1131','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(folder/'profile'),'about:blank'],stdout=self.log,stderr=self.log,start_new_session=True)
  for _ in range(100):
   if (folder/'profile/DevToolsActivePort').exists():break
   time.sleep(.05)
  self.port=int((folder/'profile/DevToolsActivePort').read_text().splitlines()[0])
  tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json'));self.first=Page(self.port,next(t['id'] for t in tabs if t['type']=='page'))
 def page(self,url,lang=None):
  id=self.first.call('Target.createTarget',{'url':'about:blank'})['targetId'];page=Page(self.port,id)
  page.call('Page.enable')
  code="window.languageErrors=[];addEventListener('error',e=>languageErrors.push(e.message));addEventListener('unhandledrejection',e=>languageErrors.push(String(e.reason)));"
  if lang is not None:code+="localStorage.setItem('graphnews.language',JSON.stringify("+json.dumps(lang)+"));"
  page.call('Page.addScriptToEvaluateOnNewDocument',{'source':code});page.call('Page.navigate',{'url':url});return page
 def close(self):os.killpg(self.proc.pid,signal.SIGTERM);self.proc.wait(timeout=10);self.log.close()

def main():
 with tempfile.TemporaryDirectory(prefix='atlas-chat-language-') as tmp:
  folder=Path(tmp);store=GraphRepository(folder/'data/news.sqlite3')
  rows=[row('massive',title='Tesla evidence',day='2026-11-04',suffix='language',symbols=['TSLA'])]
  store.for_ticker('TSLA').save('massive',query_key('massive','TSLA'),rows,[])
  wiki=WikiService(store,runner=lambda s,j,a,c:{'proposal':proposal(a),'usage':{}},start_worker=False)
  plan=wiki.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':rows});wiki.start({'plan_id':plan['plan_id']});wiki.tick();wiki.tick()
  wiki.bridge_request=lambda *a,**k:{'models':[{'id':'fixture','name':'Fixture','reasoning':[{'reasoningEffort':'low'}]}],'default_model':'fixture','wiki_ready':True}
  session_gate=threading.Event();session_gate.set();turn_gate=threading.Event();turn_started=threading.Event();cancel_gate=threading.Event();cancel_gate.set()
  transport={'session_calls':0,'sync_calls':0,'expire':False,'turn_calls':0,'cancelled':False,'error':None}
  class Handler(server.Handler):
   def log_message(self,*args):pass
   def do_POST(self):
    if not self.path.startswith('/api/chat/'):return super().do_POST()
    self.rfile.read(int(self.headers.get('Content-Length','0')))
    endpoint=self.path.removeprefix('/api/chat/')
    if endpoint=='session':
     transport['session_calls']+=1;token='session-'+str(transport['session_calls']);session_gate.wait(15);return self.json_response(200,{'token':token})
    if endpoint=='sync':
     transport['sync_calls']+=1
     if transport['expire']:transport['expire']=False;return self.json_response(401,{'error':'Session expired; start a new chat.'})
     return self.json_response(200,{'commands':[]})
    if endpoint=='turn':
     transport['turn_calls']+=1;transport['cancelled']=False;turn_started.set()
     self.send_response(200);self.send_header('Content-Type','application/x-ndjson');self.end_headers()
     def emit(value):self.wfile.write((json.dumps(value,ensure_ascii=False)+'\n').encode());self.wfile.flush()
     emit({'type':'status','message':'正在讀取目前新聞情境…'});turn_gate.wait(15)
     if transport['error']:emit({'type':'error','message':transport['error']})
     else:
      emit({'type':'status','message':'正在讀取新聞或操作畫面…'})
      emit({'type':'message','text':'原始中文回答與引用：新聞時間與營收上升。 [來源](https://example.test/evidence)'})
      emit({'type':'done','cancelled':transport['cancelled']})
     return
    if endpoint=='cancel':
     transport['cancelled']=True;turn_gate.set();cancel_gate.wait(15)
    return self.json_response(200,{'ok':True})
  http=server.ThreadingHTTPServer(('127.0.0.1',0),Handler);http.store=store;http.wiki=wiki
  url='http://127.0.0.1:'+str(http.server_port);os.environ['NEWS_ATLAS_WIKI_ORIGINS']=url
  threading.Thread(target=http.serve_forever,daemon=True).start();browsers=[]
  try:
   browser=Browser(folder/'browser');browsers.append(browser);page=browser.page(url)
   page.open_wiki();page.chat();page.wait("document.querySelector('#wikichatPage .chat-status').textContent.includes('已連線')")
   page.language('en');time.sleep(.9)
   page.check('English Wiki connection and scope after switch and subsequent sync',"document.querySelector('#wikichatPage .chat-status').textContent==='Connected · Using local sign-in'&&document.querySelector('#wikichatPage .chat-context').textContent.includes('nodes')&&!/[\\u3400-\\u9fff]/.test(document.querySelector('#wikichatPage .chat-context').textContent)")
   def english(target,label):
    target.check(label,"AtlasI18n.language()==='en'&&AtlasRuntime.state().language==='en'&&AtlasWiki.runtime.state().language==='en'&&document.getElementById('language').value==='en'")
    assert not any('\u3400'<=c<='\u9fff' for c in target.labels()),target.labels()
   english(page,'one language owner for News, Wiki and picker')
   page.js("window.kept={news:graph.graphData().nodes.slice(),camera:JSON.stringify(graph.cameraPosition()),model:document.getElementById('wikiModel').value,languages:document.getElementById('wikiLanguages').value,roots:JSON.stringify(AtlasWiki.runtime.state().root_ids),dates:JSON.stringify(AtlasWiki.runtime.state().date_range)};void 0")
   page.js("document.querySelector('#wikichatPage .chat-toolbar button').click()")
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='New conversation started'")
   page.language('zh-Hant')
   page.check('status round trip renders from source state',"document.querySelector('#wikichatPage .chat-status').textContent==='已開始新對話'&&document.querySelector('#wikinewsTab').textContent==='觀點詳情'")
   def submit():
    turn_gate.clear();turn_started.clear();transport['error']=None
    page.js("{const field=document.querySelector('#wikichatPage textarea');field.value='保留原始輸入';field.dispatchEvent(new Event('input'));document.querySelector('#wikichatPage form').requestSubmit()}")
    assert turn_started.wait(5)
   submit()
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='正在讀取目前新聞情境…'")
   page.language('en')
   page.check('in-flight stream status changes without restarting turn',"document.querySelector('#wikichatPage .chat-status').textContent==='Reading the current news context…'")
   turn_gate.set()
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Reply complete'")
   raw=page.js("document.querySelector('#wikichatPage .chat-messages').textContent")
   assert '原始中文回答與引用：新聞時間與營收上升。' in raw and '保留原始輸入' in raw
   page.language('zh-Hant');page.language('en')
   page.check('original messages and citations survive language round trips',"document.querySelector('#wikichatPage .chat-messages').textContent==="+json.dumps(raw))
   submit();page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Reading the current news context…'")
   cancel_gate.clear()
   page.js("document.querySelectorAll('#wikichatPage .chat-toolbar button')[1].click()")
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Reply stopped'")
   cancel_gate.set();time.sleep(.25)
   page.check('cancellation cannot overwrite completed stop status',"document.querySelectorAll('#wikichatPage .chat-toolbar button')[1].disabled&&document.querySelector('#wikichatPage .chat-status').textContent==='Reply stopped'")
   submit();transport['error']='登入已失效，請在主機執行 codex login 後重試。';turn_gate.set()
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Sign-in expired. Run codex login on the host and try again.'")
   page.language('zh-Hant')
   page.check('asynchronous error is also rerendered on language switch',"document.querySelector('#wikichatPage .chat-status').textContent==='登入已失效，請在主機執行 codex login 後重試。'")
   transport['expire']=True
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='對話連線已失效，請重新開啟 Chat。'")
   old_calls=transport['session_calls'];page.language('en');page.js("document.getElementById('wikinewsTab').click()");page.chat()
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Connected · Using local sign-in'")
   assert transport['session_calls']==old_calls+1
   english(page,'expired session reconnect keeps current language')
   page.check('language does not change knowledge settings, selection or graph geometry',"graph.graphData().nodes.every((n,i)=>n===kept.news[i])&&JSON.stringify(graph.cameraPosition())===kept.camera&&document.getElementById('wikiModel').value===kept.model&&document.getElementById('wikiLanguages').value===kept.languages&&JSON.stringify(AtlasWiki.runtime.state().root_ids)===kept.roots&&JSON.stringify(AtlasWiki.runtime.state().date_range)===kept.dates")
   # Same origin and Chrome profile: a genuinely separate URL tab shares the preference.
   second=browser.page(url+'/?window=second');second.open_wiki();second.chat()
   second.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Connected · Using local sign-in'")
   english(second,'new URL tab initializes in saved English')
   second.language('zh-Hant')
   page.wait("AtlasI18n.language()==='zh-Hant'&&document.getElementById('language').value==='zh-Hant'")
   page.check('another window updates already mounted chat and status',"document.querySelector('#wikichatPage .chat-status').textContent==='已連線 · 使用本機登入'&&document.querySelector('#wikichatPage .chat-context').textContent.includes('個節點')")
   page.language('en');second.wait("AtlasI18n.language()==='en'");english(second,'two-way window synchronization')
   # Delayed connect callback must read the language at completion, not request start.
   page.language('zh-Hant');session_gate.clear();old_calls=transport['session_calls']
   late=browser.page(url+'/?window=late');late.open_wiki();late.chat()
   for _ in range(100):
    if transport['session_calls']>old_calls:break
    time.sleep(.03)
   assert transport['session_calls']>old_calls
   late.language('en');session_gate.set()
   late.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Connected · Using local sign-in'")
   english(late,'late connection response uses newly selected English')
   # Hidden News Chat uses the same render contract when revealed later.
   late.js("document.getElementById('wikiBack').click();document.getElementById('chatTab').click()")
   late.wait("document.querySelector('#chatPage .chat-status').textContent==='Connected · Using local sign-in'")
   late.check('News Chat scope and status also stay English',"!/[\\u3400-\\u9fff]/.test(document.querySelector('#chatPage .chat-context').textContent)")
   late.open_wiki();english(late,'returning from News preserves Wiki language')
   second.call('Page.reload');second.open_wiki();second.chat()
   second.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Connected · Using local sign-in'")
   english(second,'reload reconnects in the saved language')
   # New profile has its own preference. English is present before any component mounts.
   fresh_browser=Browser(folder/'fresh-browser');browsers.append(fresh_browser);fresh=fresh_browser.page(url,lang='en')
   fresh.open_wiki();fresh.chat();fresh.wait("document.querySelector('#wikichatPage .chat-status').textContent==='Connected · Using local sign-in'")
   english(fresh,'fresh profile with saved English mounts all labels correctly')
   fresh.language('zh-Hant');time.sleep(.2)
   english(page,'separate browser profiles do not silently share UI preference')
   fresh.language('en');english(fresh,'fresh profile supports full language round trip')
   for target in [page,second,late,fresh]:target.check('no browser errors '+target.target,"languageErrors.length===0")
   assert transport['turn_calls']==3,transport
   print('PASS language lifecycle: initial mount, switch, sync, reconnect, late connect, stream, cancel/error, two URL tabs, reload, fresh profile, raw evidence and preserved data',flush=True)
  finally:
   session_gate.set();turn_gate.set();cancel_gate.set()
   for browser in browsers:browser.close()
   http.shutdown();http.server_close();wiki.close()
if __name__=='__main__':main()
