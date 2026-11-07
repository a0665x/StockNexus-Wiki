"""Live Chromium checks: no model jobs; isolates workspace writes; needs websocket-client."""
import json,os,signal,subprocess,tempfile,time,urllib.request,pathlib,sys
import websocket
import argparse
parser=argparse.ArgumentParser(description="Live News/Wiki interaction journey; workspace preference writes are isolated.")
parser.add_argument("--url",default="http://127.0.0.1:8765/")
parser.add_argument("--stock",default="NASDAQ:TSM")
parser.add_argument("--check-l2",action="store_true",help="Read and render an existing completed result; creates no model job.")
args=parser.parse_args()
with tempfile.TemporaryDirectory(prefix='wiki-feedback-') as tmp:
 p=pathlib.Path(tmp);log=open(p/'chrome.log','w');proc=subprocess.Popen(['/usr/bin/chromium','--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1681,1000','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+tmp,'about:blank'],stdout=log,stderr=log,start_new_session=True)
 try:
  for _ in range(100):
   if (p/'DevToolsActivePort').exists():break
   time.sleep(.05)
  port=int((p/'DevToolsActivePort').read_text().splitlines()[0]);tabs=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'));ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'),timeout=40,suppress_origin=True);serial=0
  def call(method,params=None):
   global serial
   serial+=1;ws.send(json.dumps({'id':serial,'method':method,'params':params or {}}))
   while True:
    r=json.loads(ws.recv())
    if r.get('id')==serial:return r.get('result',{})
  def js(code):
   r=call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
   if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
   return r.get('result',{}).get('value')
  def wait(code,seconds=30):
   end=time.monotonic()+seconds
   while time.monotonic()<end:
    if js(code):return
    time.sleep(.05)
   import base64
   pathlib.Path('/tmp/research-live-failure.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
   raise AssertionError(code+' '+str(js("({text:document.getElementById('wikiPanel')?.innerText.slice(-2500),errors:window.probeErrors,state:window.AtlasWiki?.runtime.state()})")))
  def click(ident):
   xy=js("(()=>{const e=document.getElementById("+json.dumps(ident)+");e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
   for kind in ['mouseMoved','mousePressed','mouseReleased']:call('Input.dispatchMouseEvent',{'type':kind,**xy,'button':'left','clickCount':1})
  call('Page.enable')
  call('Page.addScriptToEvaluateOnNewDocument',{'source':"""window.probeWrites=[];window.probeErrors=[];window.addEventListener('error',e=>probeErrors.push(e.message));window.addEventListener('unhandledrejection',e=>probeErrors.push(String(e.reason)));const realFetch=window.fetch;window.fetch=(u,o)=>{if(o?.method==='POST'&&String(u)==='/api/workspace'){probeWrites.push(String(u));return Promise.resolve(new Response('{}',{status:200}));}if(o?.method&&o.method!=='GET'&&!['/api/cache/graph','/api/graph/preview'].includes(String(u))){probeErrors.push('Unexpected write '+u);return Promise.reject(Error('UI audit blocked write'));}return realFetch(u,o)};"""})
  call('Page.navigate',{'url':args.url})
  wait("typeof AtlasWiki!=='undefined'",45)
  # Fail before interacting if the preference-write guard did not initialize.
  assert js('Array.isArray(window.probeWrites)'), 'workspace write isolation not installed'
  click('modeWiki')
  wait("!document.getElementById('wikiPanel').hidden&&[...document.getElementById('wikiSaved').options].some(o=>o.value==='NASDAQ:TSM')",90)
  def choose_stock(value):
   index=js("[...document.getElementById('wikiSaved').options].findIndex(o=>o.value==="+json.dumps(value)+")")
   assert index>=0
   click('wikiSaved')
   for key in ['Home']+['ArrowDown']*index+['Enter']:
    for event in ['keyDown','keyUp']:call('Input.dispatchKeyEvent',{'type':event,'key':key})
   wait("document.getElementById('wikiInstrument').value==="+json.dumps(value))
  choose_stock(args.stock)
  click('researchOpen')
  wait("!document.getElementById('researchPanel').hidden&&!document.getElementById('researchAvailability').classList.contains('research-working')",45)
  a=js("fetch('/api/wiki/research/availability?instrument='+encodeURIComponent("+json.dumps(args.stock)+")).then(r=>r.json())")
  if a['busy']:
   assert js("document.getElementById('researchSubmit').disabled&&!document.getElementById('researchAvailability').hidden")
   for stock in a['instruments']:assert stock in js("document.getElementById('researchAvailability').textContent")
   # True pointer navigation; all workspace writes isolated, no model operations.
   js("document.getElementById('researchQuestion').value='AI 需求與風險';document.getElementById('researchBlockers').querySelector('button').id='liveBlocker'")
   click('liveBlocker')
   wait("document.getElementById('researchPanel').hidden")
   assert js("document.getElementById('wikiInstrument').value")==a['instruments'][0]
   choose_stock(args.stock);click('researchOpen')
   wait("!document.getElementById('researchPanel').hidden&&!document.getElementById('researchAvailability').classList.contains('research-working')")
   assert js("document.getElementById('researchQuestion').value==='AI 需求與風險'")
  else:assert js("!document.getElementById('researchSubmit').disabled")
  result_counts=None
  if args.check_l2:
   print('Before L2 selection',js("({stock:document.getElementById('wikiInstrument').value,layer:document.getElementById('wikiLayer').value,loaded:AtlasWiki.runtime.data()?.instrument})"),flush=True)
   click('wikiLayer')
   for key in ['Home','ArrowDown','Enter']:
    for event in ['keyDown','keyUp']:call('Input.dispatchKeyEvent',{'type':event,'key':key})
   wait("AtlasWiki.runtime.state().research_run!==null&&AtlasWiki.graph().graphData().nodes.some(n=>n.layer==='L2')",60)
   result_counts=js("({run:AtlasWiki.runtime.state().research_run,nodes:AtlasWiki.graph().graphData().nodes.filter(n=>n.layer==='L2').length,heading:document.getElementById('researchResult').querySelector('h3').textContent})")
   expected=js("fetch('/api/wiki/research/run?instrument='+encodeURIComponent("+json.dumps(args.stock)+")+'&id='+encodeURIComponent(AtlasWiki.runtime.state().research_run)).then(r=>r.json()).then(r=>r.result.claims.length)")
   assert result_counts['nodes']==expected and expected>0,result_counts
  assert js('probeErrors.length===0'),js('probeErrors')
  import base64
  pathlib.Path('/tmp/research-availability-live.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
  report={'rendered_l2':result_counts,'availability':a,'visible_reason':js("document.getElementById('researchAvailability').textContent"),'button_disabled':js("document.getElementById('researchSubmit').disabled"),'model_actions':0,'workspace_writes_isolated':len(js('probeWrites'))}
  pathlib.Path('/tmp/research-availability-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  print('PASS live cross-stock research availability',json.dumps(report,ensure_ascii=False),flush=True)
 finally:
  os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10)
