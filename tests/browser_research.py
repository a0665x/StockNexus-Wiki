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
     def measure(ident):
      js("""(()=>{const b=document.getElementById("""+json.dumps(ident)+""");b.scrollIntoView({block:'center'});window.feedbackMs=null;b.addEventListener('click',()=>{const start=performance.now();const frame=()=>{if(b.disabled&&b.getAttribute('aria-busy')==='true'){requestAnimationFrame(()=>{feedbackMs=performance.now()-start});return;}if(performance.now()-start>2000){feedbackMs=-1;return;}requestAnimationFrame(frame)};requestAnimationFrame(frame)},{once:true,capture:true});})()""")
      point=js("(()=>{const r=document.getElementById("+json.dumps(ident)+").getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
      for kind in ['mouseMoved','mousePressed','mouseReleased']:
       nonlocal serial
       serial+=1;ws.send(json.dumps({'id':serial,'method':'Input.dispatchMouseEvent','params':{'type':kind,**point,'button':'left','clickCount':1}}))
       while json.loads(ws.recv()).get('id')!=serial:pass
      wait('feedbackMs!==null');elapsed=js('feedbackMs');print(json.dumps({'button':ident,'feedback_ms':elapsed}),flush=True);assert 0<=elapsed<2000
     def wait(code):
      for _ in range(150):
       if js(code):return
       time.sleep(.1)
      raise AssertionError(code+' '+str(js("document.body.innerText.slice(-800)")))
     wait("typeof AtlasWiki!=='undefined'")
     js("AtlasWiki.show()")
     wait("$('wikiInstrument').value==='NASDAQ:TSLA'&&$('wikiModel').options.length>0")
     wait("AtlasWiki.graph()&&AtlasWiki.graph().graphData().nodes.length>0")
     js("window.sharedWikiGraph=AtlasWiki.graph();window.originalWikiNodes=sharedWikiGraph.graphData().nodes.slice();true;")
     before_height=js("$('wikiLive').getBoundingClientRect().height")
     bar=js("(()=>{const r=$('wikiResizeLive').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
     for event,dy in [('mousePressed',0),('mouseMoved',55),('mouseReleased',55)]:
      serial+=1;ws.send(json.dumps({'id':serial,'method':'Input.dispatchMouseEvent','params':{'type':event,'x':bar['x'],'y':bar['y']+dy,'button':'left','buttons':0 if event=='mouseReleased' else 1,'clickCount':1}}))
      while json.loads(ws.recv()).get('id')!=serial:pass
     time.sleep(.2)
     assert js("$('wikiLive').getBoundingClientRect().height")>before_height+35
     assert js("AtlasWiki.graph()===sharedWikiGraph&&sharedWikiGraph.graphData().nodes[0]===originalWikiNodes[0]")
     js("$('researchOpen').click()")
     wait("!$('researchPanel').hidden&&$('researchTaxonomy').children.length>0")
     assert js("!$('researchInclude')&&!$('researchExclude')&&!$('researchTaxonomy').querySelector('input')")
     with paused.connection() as db:db.execute("UPDATE jobs SET status='queued'")
     wait("$('researchSubmit').disabled")
     js("$('researchSubmitWrap').focus()")
     time.sleep(.25);assert js("$('researchBusyTip').hidden")
     time.sleep(.4);assert js("!$('researchBusyTip').hidden&&$('researchBusyTip').textContent.includes('停止 L1')")
     assert js("fetch('/api/wiki/research/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:'NASDAQ:TSLA',query:'動能'})}).then(r=>r.status)")==400
     with paused.connection() as db:db.execute("UPDATE jobs SET status='completed'")
     wait("!$('researchSubmit').disabled")
     js("$('researchQuestion').value='動能';const fast=fetch;window.fetch=async(u,o)=>{if(o?.method==='POST'&&String(u).startsWith('/api/wiki/research/'))await new Promise(r=>setTimeout(r,2500));return fast(u,o)}")
     measure('researchSubmit')
     wait("$('researchStatus').textContent.includes('等待')")
     wiki.tick()
     wait("$('researchStatus').textContent.startsWith('研究完成')")
     assert js("$('researchResult').textContent.includes('價格動能')&&$('researchResult').textContent.includes('來源陳述')")
     js("[...$('researchResult').querySelectorAll('summary')].find(n=>n.textContent==='查看依據與條件').click()")
     assert js("!!$('researchResult').querySelector('blockquote')&&!!$('researchResult').querySelector('a[href^=\"https://\"]')")
     js("[...$('researchResult').querySelectorAll('button')].find(n=>n.textContent==='持續追蹤').id='fixtureSave'")
     measure('fixtureSave')
     wait("$('researchSaved').textContent.includes('動能')")
     js("[...$('researchSaved').querySelectorAll('button')].find(n=>n.textContent==='更新').id='fixtureRefresh'")
     measure('fixtureRefresh')
     wait("$('researchStatus').textContent.includes('證據未變')")
     before=len(wiki.store('NASDAQ:TSLA').jobs())
     js("$('researchBack').click();$('wikiBudget').value='1600';$('wikiBudget').dispatchEvent(new Event('change'));$('researchOpen').click()")
     assert len(wiki.store('NASDAQ:TSLA').jobs())==before
     # Real HTTP requests: a forged owner cannot read or create another result.
     assert js("fetch('/api/wiki/research/lenses?instrument=NASDAQ:TSLA&owner=other').then(r=>r.status)")==400
     wait("AtlasWiki.graph().graphData().nodes.some(n=>n.layer==='L2')")
     assert js("AtlasWiki.graph()===sharedWikiGraph")
     js("window.l2Node=sharedWikiGraph.graphData().nodes.find(n=>n.layer==='L2');AtlasWiki.selectNode(l2Node.id)")
     assert js("AtlasWiki.runtime.state().selected_node.layer==='L2'&&AtlasWiki.runtime.data().edges.some(e=>e.relation_type==='DERIVED_FROM')")
     assert js("sharedWikiGraph.nodeLabel()({title:'<img src=x onerror=alert(1)>',layer:'L2'}).includes('&lt;img')")
     js("$('wikiLayer').value='L2';$('wikiLayer').dispatchEvent(new Event('change'))")
     assert js("sharedWikiGraph.graphData().nodes.every(n=>n.layer==='L2')")
     js("$('wikiLayer').value='both';$('wikiLayer').dispatchEvent(new Event('change'))")
     assert js("sharedWikiGraph.graphData().nodes.some(n=>n.layer==='L1')&&sharedWikiGraph.graphData().nodes.some(n=>n.layer==='L2')")
     js("$('wikiLayer').value='L1';$('wikiLayer').dispatchEvent(new Event('change'))")
     assert js("AtlasWiki.runtime.state().selected_node===null&&AtlasWiki.runtime.state().scope_ids.every(id=>sharedWikiGraph.graphData().nodes.some(n=>n.id===id&&n.layer!=='L2'))")
     old_ids={n['id'] for n in paused.graph(version=1)['nodes']}
     p=wiki.plan({'instrument':'NASDAQ:TSLA','model':'fixture','articles':rows[1:2]});wiki.start({'plan_id':p['plan_id']});wiki.tick()
     paused.configure({**paused.config(),'enabled':False,'catch_up':False})
     # Re-entering a queued query resumes the same paid work, including a stock switch.
     js("$('researchQuestion').value='風險';$('researchForm').requestSubmit()")
     wait("$('researchStatus').textContent.includes('等待')")
     with paused.connection() as db:jobs_before=db.execute('SELECT count(*) FROM research_jobs').fetchone()[0]
     js("$('researchBack').click();$('researchOpen').click()")
     wait("$('researchSubmit').disabled&&$('researchStatus').textContent.includes('等待')")
     wiki.store('NASDAQ:AMD')
     js("$('researchBack').click();$('wikiInstrument').value='NASDAQ:AMD';$('wikiInstrument').dispatchEvent(new Event('change'));$('researchOpen').click()")
     wait("$('researchStock').textContent==='NASDAQ:AMD'")
     assert js("!$('researchResult').textContent.includes('Tesla earnings')&&!$('researchResult').textContent.includes('來源陳述')")
     js("$('researchBack').click();$('wikiInstrument').value='NASDAQ:TSLA';$('wikiInstrument').dispatchEvent(new Event('change'));$('researchOpen').click()")
     wait("$('researchSaved').textContent.includes('動能')&&$('researchSubmit').disabled")
     from news_atlas.wiki.research import Research
     Research(paused).process(wiki)
     wait("$('researchStatus').textContent.startsWith('研究完成')")
     with paused.connection() as db:assert db.execute('SELECT count(*) FROM research_jobs').fetchone()[0]==jobs_before
     assert js("sharedWikiGraph.graphData().nodes.some(n=>n.layer==='L2')")
     js("$('wikiVersion').value='1';$('wikiVersion').dispatchEvent(new Event('change'))")
     wait("AtlasWiki.runtime.state().version===1&&$('wikiLayer').value==='L1'&&AtlasWiki.runtime.data().nodes.every(n=>n.layer!=='L2')")
     assert set(js("AtlasWiki.runtime.data().nodes.map(n=>n.id)"))<=old_ids
     assert js("AtlasWiki.runtime.state().research_run===null")
     js("document.querySelector('#researchSaved button').click()")
     wait("$('researchResult').textContent.includes('來源陳述')")
     wait("AtlasWiki.runtime.state().research_run!==null&&!$('researchResult').hidden")
     assert js("$('wikiVersion').value==='1'&&AtlasWiki.runtime.state().version===1&&$('wikiCounts').textContent.includes('固定快照')")
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
