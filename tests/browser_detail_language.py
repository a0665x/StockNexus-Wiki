"""Isolated Chrome UI QA against the running local app and existing snapshots.
Run with --live to also use the signed-in model (consumes account usage).
Without --live, verifies runtime/UI contracts without model calls.
"""
import sys
import json,os,signal,subprocess,tempfile,time,urllib.request,base64
from pathlib import Path
import websocket
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='atlas-chat-qa-') as temp:
 p=Path(temp);log=(p/'chrome.log').open('w')
 chrome=subprocess.Popen(['google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader','--window-size=1542,1131','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(p/'profile'),'http://127.0.0.1:8765/'],stdout=log,stderr=log,start_new_session=True)
 try:
  for _ in range(150):
   if (p/'profile/DevToolsActivePort').exists():break
   time.sleep(.1)
  port=int((p/'profile/DevToolsActivePort').read_text().splitlines()[0]);targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
  ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),timeout=30,suppress_origin=True);serial=0
  def call(method,params=None):
   global serial
   serial+=1;ws.send(json.dumps({'id':serial,'method':method,'params':params or {}}))
   while True:
    r=json.loads(ws.recv())
    if r.get('id')==serial:
     if 'error' in r:raise RuntimeError(r['error'])
     return r.get('result',{})
  def js(code,wait=False):
   r=call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':wait})
   if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
   return r.get('result',{}).get('value')
  def wait(code,seconds=20):
   end=time.time()+seconds
   while time.time()<end:
    if js(code):return
    time.sleep(.2)
   raise RuntimeError('Timed out: '+code+'; '+str(js("document.querySelector('.chat-status')?.textContent")))
  wait("typeof AtlasRuntime!=='undefined'&&!!document.getElementById('chatTab')")
  print('PASS: real HTTP assets and runtime loaded',flush=True)
  wait("!!document.querySelector('#snapshots button')")
  js("document.querySelector('#snapshots button').click()")
  wait('AtlasRuntime.state().counts.loaded>0',30)
  js("document.getElementById('clearRoot').click();document.querySelector('#list button').click();document.getElementById('chatTab').click()")
  wait("document.querySelector('.chat-status').textContent.includes('已連線')")
  print('PASS: saved news loaded, selected root and Chat connected',flush=True)
  state=js('AtlasRuntime.state()');assert state['root_ids'];assert state['counts']['scope']>0
  js("document.getElementById('language').value='en';document.getElementById('language').dispatchEvent(new Event('change'))")
  time.sleep(.2)
  labels=js("({news:document.getElementById('newsTab').textContent,newChat:document.querySelector('.chat-toolbar button').textContent,placeholder:document.querySelector('.chat-compose textarea').placeholder})")
  print('Language labels:',labels,flush=True)
  assert labels['news']=='News details' and labels['newChat']=='New chat', 'Chat controls did not switch to English'
  js("document.getElementById('newsTab').click()")
  assert js("!!document.querySelector('#article .selected-news')"), 'Selected article lacks red frame'
  print('PASS: translated panel and selected news frame',flush=True)
  assert labels['placeholder']=='Summarize selected news, or adjust the view…'
  assert js("getComputedStyle(document.querySelector('.selected-news')).borderTopColor")=='rgb(244, 91, 105)'
  js("AtlasI18n.setLanguage('zh-Hant')")
  assert js("document.getElementById('newsTab').textContent")=='新聞詳情'
  print('PASS: reverse language switch, real red border, translated input',flush=True)
  # Only this isolated browser intercepts price evidence; no fixture writes to the DB.
  js("""globalThis.originalFetch=fetch;globalThis.priceCalls=0;globalThis.priceBodies=[];
   globalThis.fetch=async(url,options)=>{if(url!='/api/prices/lens')return originalFetch(url,options);
    priceCalls++;const b=JSON.parse(options.body);priceBodies.push(b);
    return {ok:true,json:async()=>({ticker:b.ticker,as_of:'2026-11-02',observations:Object.fromEntries(b.articles.map(a=>[a.id,{published_at:a.published_at,baseline_date:'2026-10-01',baseline_close:100,returns:{'1':.05,'3':-.05,'5':null,'7':.1}}]))})};};
   document.getElementById('ticker').value='AAPL';document.getElementById('ticker').dispatchEvent(new Event('input'));
   globalThis.beforeEdges=AtlasRuntime.data().edges.length;
   document.getElementById('priceMix').value=70;document.getElementById('priceMix').dispatchEvent(new Event('input'));document.getElementById('priceMix').dispatchEvent(new Event('change'));
  """)
  wait('AtlasRuntime.state().price_focus.complete>0')
  assert js('AtlasRuntime.state().price_focus.mix')==.7
  assert js("priceBodies[0].ticker")=='AAPL'
  js("document.getElementById('priceHorizon').value=0;document.getElementById('priceHorizon').dispatchEvent(new Event('input'))")
  assert js('AtlasRuntime.state().price_focus.horizon')==1
  assert js("document.querySelector('.price-detail').textContent.includes('+5.00%')")
  js("document.getElementById('priceHorizon').value=2;document.getElementById('priceHorizon').dispatchEvent(new Event('input'))")
  assert js('AtlasRuntime.state().price_focus.complete')==0
  assert js('priceCalls')==1
  assert js('AtlasRuntime.data().edges.length===beforeEdges')
  ratio=js("""(()=>{graph.pauseAnimation();if(!$('timeSizeEnabled').checked)$('timeSizeEnabled').click();
    $('priceMix').value=100;$('priceMix').dispatchEvent(new Event('input'));
    $('priceHorizon').value=0;$('priceHorizon').dispatchEvent(new Event('input'));timeSizer.refresh();
    const node=graph.graphData().nodes[0],up=node.__threeObj.scale.x;
    $('priceHorizon').value=1;$('priceHorizon').dispatchEvent(new Event('input'));timeSizer.refresh();
    const ratio=up/node.__threeObj.scale.x;
    $('priceMix').value=70;$('priceMix').dispatchEvent(new Event('input'));graph.resumeAnimation();return ratio;})()""")
  assert abs(ratio-16)<1e-7, ('Actual 3D mesh scale failed',ratio)
  print('PASS: actual 3D node mesh grows/shrinks with returns (16:1 ratio)',flush=True)
  js("document.getElementById('ticker').value='MSFT';document.getElementById('ticker').dispatchEvent(new Event('input'))")
  assert js('AtlasRuntime.state().price_focus.complete')==0
  assert js('AtlasRuntime.state().price_focus.ticker')=='MSFT'
  js("if(document.getElementById('timeFocusBody').hidden)document.getElementById('timePanelToggle').click()")
  time.sleep(.3)
  screenshot=call('Page.captureScreenshot',{'format':'png'})['data'];Path('/tmp/atlas-price-ui.png').write_bytes(base64.b64decode(screenshot))
  print('PASS: real controls, 70/30 mix, horizon cache, null fallback, ticker invalidation, unchanged edges',flush=True)
 finally:
  os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()
