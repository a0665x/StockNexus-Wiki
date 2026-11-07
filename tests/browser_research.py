"""Exercise the connected L2 research workflow in real HTTP and Chrome; isolated fixtures only."""
import json,os,signal,shutil,tempfile,subprocess,time,urllib.request,threading,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import websocket
import server
from test_research import fusion
from news_atlas.wiki.store import now
import datetime as dt
from news_atlas.graph_storage import GraphRepository
from news_atlas.wiki.compiler import WikiService
from news_atlas.search import query_key
from test_server import row
from test_wiki import proposal

def main():
 with tempfile.TemporaryDirectory(prefix='wiki-workspace-browser-') as tmp:
  folder=Path(tmp);store=GraphRepository(folder/'data/news.sqlite3')
  rows=[row('massive',title='Tesla earnings '+str(i),day=(dt.date.fromisoformat(now()[:10])-dt.timedelta(days=1)).isoformat(),suffix=str(i),symbols=['TSLA']) for i in range(3)]
  store.for_ticker('TSLA').save('massive',query_key('massive','TSLA'),rows,[])
  wiki=WikiService(store,runner=lambda s,j,a,c:{'proposal':fusion(a['research_bundle']) if j['payload'].get('operation')=='research_fusion' else proposal(a),'usage':{}},start_worker=False)
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
     wait("typeof AtlasWiki!=='undefined'")
     js("AtlasWiki.show()")
     wait("$('wikiInstrument').value==='NASDAQ:TSLA'&&$('wikiModel').options.length>0")
     js("$('researchOpen').click()")
     wait("!$('researchPanel').hidden&&$('researchTaxonomy').children.length>0")
     js("$('researchQuestion').value='動能';$('researchForm').requestSubmit()")
     wait("$('researchStatus').textContent.includes('等待')")
     wiki.tick()
     wait("$('researchStatus').textContent==='研究完成'")
     assert js("$('researchResult').textContent.includes('價格動能')&&$('researchResult').textContent.includes('來源陳述')")
     js("[...$('researchResult').querySelectorAll('summary')].find(n=>n.textContent==='查看依據與條件').click()")
     assert js("$('researchResult').textContent.includes('新聞證據')")
     js("[...$('researchResult').querySelectorAll('button')].find(n=>n.textContent==='持續追蹤').click()")
     wait("$('researchSaved').textContent.includes('動能')")
     before=len(wiki.store('NASDAQ:TSLA').jobs())
     js("$('researchBack').click();$('wikiBudget').value='1600';$('wikiBudget').dispatchEvent(new Event('change'));$('researchOpen').click()")
     assert len(wiki.store('NASDAQ:TSLA').jobs())==before
     # Real HTTP requests: a forged owner cannot read or create another result.
     assert js("fetch('/api/wiki/research/lenses?instrument=NASDAQ:TSLA&owner=other').then(r=>r.status)")==400
     js("window.originalResearchGraph=ForceGraph3D;window.ForceGraph3D=(...args)=>{const factory=originalResearchGraph(...args);return (...params)=>{window.qaResearchGraph=factory(...params);return qaResearchGraph;};};[...$('researchResult').querySelectorAll('summary')].find(n=>n.textContent==='研究圖譜').click()")
     wait("window.qaResearchGraph&&qaResearchGraph.graphData().nodes.length>0")
     assert js("qaResearchGraph.nodeLabel()({title:'<img src=x onerror=alert(1)>'}).includes('&lt;img')")
     # Leaving a queued query cannot strand the submit button. No second paid job.
     js("$('researchQuestion').value='new query';$('researchForm').requestSubmit()")
     wait("$('researchSubmit').disabled")
     js("$('researchBack').click();$('researchOpen').click()")
     assert js("!$('researchSubmit').disabled")
     wiki.store('NASDAQ:AMD')
     js("$('researchBack').click();$('wikiInstrument').value='NASDAQ:AMD';$('researchOpen').click()")
     wait("$('researchStock').textContent==='NASDAQ:AMD'")
     assert js("!$('researchResult').textContent.includes('Tesla earnings')&&!$('researchResult').textContent.includes('來源陳述')")
     js("$('researchBack').click();$('wikiInstrument').value='NASDAQ:TSLA';$('researchOpen').click()")
     wait("$('researchSaved').textContent.includes('動能')")
     js("document.querySelector('#researchSaved button').click()")
     wait("$('researchResult').textContent.includes('來源陳述')")
     for width in (1393,390):
      serial+=1;ws.send(json.dumps({'id':serial,'method':'Emulation.setDeviceMetricsOverride','params':{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':False}}))
      while json.loads(ws.recv()).get('id')!=serial:pass
      time.sleep(.2)
      assert js("$('researchPanel').scrollWidth<=$('researchPanel').clientWidth+2"),width
      serial+=1;ws.send(json.dumps({'id':serial,'method':'Page.captureScreenshot','params':{'format':'png'}}))
      while True:
       result=json.loads(ws.recv())
       if result.get('id')==serial:
        import base64
        Path(f'/tmp/research-{width}.png').write_bytes(base64.b64decode(result['result']['data']));break
     print('PASS research real HTTP/Chrome: query, model fixture, sources, save live, navigation, owner rejection, desktop/mobile overflow',flush=True)
    finally:
     os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()
  finally:http.shutdown();http.server_close();wiki.close()
if __name__=='__main__':main()
