"""Import through the real merge CLI while HTTP and browser remain open; isolated data only."""
import json,os,signal,shutil,tempfile,subprocess,time,urllib.request,threading,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import websocket
import server
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.search import query_key
from test_server import row
from test_wiki import proposal

def main():
 with tempfile.TemporaryDirectory(prefix='wiki-workspace-browser-') as tmp:
  folder=Path(tmp);store=GraphRepository(folder/'data/news.sqlite3')
  rows=[row('massive',title='Tesla earnings '+str(i),day='2026-11-04',suffix=str(i),symbols=['TSLA']) for i in range(3)]
  store.for_ticker('TSLA').save('massive',query_key('massive','TSLA'),rows,[])
  wiki=WikiService(store,runner=lambda s,j,a,c:{'proposal':proposal(a),'usage':{}},start_worker=False)
  p=wiki.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':rows[:1]});wiki.start({'plan_id':p['plan_id']});wiki.tick();wiki.tick()
  paused=wiki.store('NASDAQ:TSLA');paused.configure({**paused.config(),'enabled':False,'catch_up':False})
  wiki.bridge_request=lambda *a,**k:{'models':[{'id':'fixture','name':'Fixture','reasoning':[{'reasoningEffort':'low'},{'reasoningEffort':'high'}]}],'default_model':'fixture','wiki_ready':True}
  http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);http.store=store;http.wiki=wiki
  url='http://127.0.0.1:'+str(http.server_port);os.environ['NEWS_ATLAS_WIKI_ORIGINS']=url
  thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
  try:
   for run in range(1):
    profile=folder/f'profile{run}';log=(folder/f'chrome{run}.log').open('w')
    chrome=subprocess.Popen([shutil.which('google-chrome') or shutil.which('chromium'),'--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1393,1131','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),url],stdout=log,stderr=log,start_new_session=True)
    try:
     for _ in range(100):
      if (profile/'DevToolsActivePort').exists():break
      time.sleep(.05)
     port=int((profile/'DevToolsActivePort').read_text().splitlines()[0]);tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
     ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'),timeout=30,suppress_origin=True);serial=0
     def js(code):
      nonlocal serial
      serial+=1;ws.send(json.dumps({'id':serial,'method':'Runtime.evaluate','params':{'expression':code,'returnByValue':True,'awaitPromise':True}}))
      while True:
       out=json.loads(ws.recv())
       if out.get('id')==serial:
        if 'exceptionDetails' in out.get('result',{}):raise RuntimeError(out)
        return out['result']['result'].get('value')
     def wait(code):
      for _ in range(150):
       if js(code):return
       time.sleep(.1)
      raise AssertionError(code+' '+str(js("document.body.innerText.slice(-800)")))
     wait("typeof AtlasRuntime!=='undefined'&&AtlasRuntime.state().counts.loaded===3")
     assert js("$('ticker').value==='NASDAQ:TSLA'&&$('ticker').checkValidity()")
     print('profile',run,'restored 3 stock news nodes',flush=True)
     js("AtlasWiki.show()")
     wait("$('wikiCounts').textContent.includes('節點')")
     js("window.newsBefore=JSON.stringify(AtlasRuntime.state());$('wikiModel').value='fixture|high';$('wikiModel').dispatchEvent(new Event('input'));$('wikiRange').value='custom';$('wikiStartDate').value='2026-11-01';$('wikiEndDate').value='2026-11-06';$('wikiStartDate').dispatchEvent(new Event('input'))")
     time.sleep(.4)
     source=GraphRepository(folder/'usb data/news.sqlite3')
     imported=WikiService(source,runner=lambda s,j,a,c:{'proposal':proposal(a),'usage':{}},start_worker=False)
     for symbol in ['NVDA','TSLA']:
      evidence=row('massive',title=symbol+' imported evidence',day='2026-11-04',suffix='import-'+symbol,symbols=[symbol])
      source.for_ticker(symbol).save('massive',query_key('massive',symbol),[evidence],[])
      plan=imported.plan({'instrument':'NASDAQ:'+symbol,'model':'fixture','articles':[evidence]});imported.start({'plan_id':plan['plan_id']});imported.tick()
     command=[str(Path(__file__).resolve().parents[1]/'merge_data.sh'),'--from',str(folder/'usb data'),'--to',str(folder/'data')]
     preview=json.loads(subprocess.check_output([*command,'--dry-run'],text=True));assert preview['dry_run']
     assert js("![...$('wikiSaved').options].some(o=>o.value==='NASDAQ:NVDA')")
     report=json.loads(subprocess.check_output(command,text=True));assert report['committed']
     wait("[...$('wikiSaved').options].some(o=>o.value==='NASDAQ:NVDA')")
     wait("$('wikiCounts').textContent.includes('版本 2')")
     assert js("$('wikiSaved').value==='NASDAQ:TSLA'&&$('wikiModel').value==='fixture|high'&&$('wikiStartDate').value==='2026-11-01'&&$('wikiEndDate').value==='2026-11-06'")
     assert js("JSON.stringify(AtlasRuntime.state())===newsBefore")
     assert http.wiki is wiki
     assert not any(j['status'] in ('queued','running') for st in wiki.stores() for j in st.jobs())
     js("$('wikiSaved').value='NASDAQ:NVDA';$('wikiSaved').dispatchEvent(new Event('change'))")
     wait("AtlasWiki.runtime.state().instrument==='NASDAQ:NVDA'&&AtlasWiki.runtime.data().nodes.some(n=>n.title.includes('NVDA imported'))")
     wait("document.querySelector('#wikiLive .wiki-worker svg')?.getBBox().width>50")
     # A second external import must not overwrite the explicit blank/new choice.
     js("$('wikiSaved').value='';$('wikiSaved').dispatchEvent(new Event('change'))")
     extra=row('massive',title='AMD additional import',day='2026-11-04',suffix='import-AMD',symbols=['AMD'])
     source.for_ticker('AMD').save('massive',query_key('massive','AMD'),[extra],[])
     extra_plan=imported.plan({'instrument':'NASDAQ:AMD','model':'fixture','articles':[extra]});imported.start({'plan_id':extra_plan['plan_id']});imported.tick()
     subprocess.check_output(command,text=True)
     wait("[...$('wikiSaved').options].some(o=>o.value==='NASDAQ:AMD')")
     assert js("$('wikiSaved').value===''")
     print('PASS live CLI import: new stock dropdown, existing version update, preserved choices/news runtime, blank new choice, HTTP SVG rendering, no restart or model calls',flush=True)
    finally:
     os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()
  finally:http.shutdown();http.server_close();wiki.close()
if __name__=='__main__':main()
