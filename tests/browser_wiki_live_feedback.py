"""Live Chromium checks: no model jobs; isolates workspace writes; needs websocket-client."""
import json,os,signal,subprocess,tempfile,time,urllib.request,pathlib,sys
import websocket
import argparse
parser=argparse.ArgumentParser(description="Read-only live Wiki click-to-frame checks; workspace preference writes are isolated.")
parser.add_argument("--url",default="http://127.0.0.1:8765/")
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
   raise AssertionError(code)
  def click(ident):
   xy=js("(()=>{const e=document.getElementById("+json.dumps(ident)+");e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
   for kind in ['mouseMoved','mousePressed','mouseReleased']:call('Input.dispatchMouseEvent',{'type':kind,**xy,'button':'left','clickCount':1})
  call('Page.enable')
  call('Page.addScriptToEvaluateOnNewDocument',{'source':"""window.probeWrites=[];const realFetch=window.fetch;window.fetch=(u,o)=>{if(o?.method==='POST'&&String(u)==='/api/workspace'){probeWrites.push(String(u));return Promise.resolve(new Response('{}',{status:200}));}return realFetch(u,o)};"""})
  call('Page.navigate',{'url':args.url})
  wait("typeof AtlasWiki!=='undefined'",45)
  # Fail before interacting if the preference-write guard did not initialize.
  assert js('Array.isArray(window.probeWrites)'), 'workspace write isolation not installed'
  records=[]
  def measure(ident,predicate):
   js("""(()=>{const id="""+json.dumps(ident)+""";window.measured=null;document.addEventListener('click',function observe(e){if(!document.getElementById(id)?.contains(e.target))return;document.removeEventListener('click',observe,true);const start=performance.now();const frame=()=>{if("""+predicate+"""){requestAnimationFrame(()=>{measured=performance.now()-start});return;}if(performance.now()-start>2000){measured=-1;return;}requestAnimationFrame(frame)};requestAnimationFrame(frame)},{capture:true})})()""")
   click(ident);wait('measured!==null',5);ms=js('measured');records.append({'button':ident,'feedback_ms':round(ms,1)});print(json.dumps(records[-1]),flush=True);assert 0<=ms<2000
  measure('modeWiki',"!document.getElementById('wikiPanel').hidden")
  wait("AtlasWiki.graph()&&AtlasWiki.graph().graphData().nodes.length>0",60)
  js("window.markdownReads=0;const originalFetch=fetch;window.fetch=async(u,o)=>{if(String(u).includes('/markdown?')){markdownReads++;await new Promise(r=>setTimeout(r,3500));}return originalFetch(u,o)}")
  for _ in range(3):
   count=js('markdownReads')
   measure('wikiExport',"document.getElementById('wikiExport').disabled&&document.getElementById('wikiExport').getAttribute('aria-busy')==='true'")
   click('wikiExport');time.sleep(2.1)
   assert js("document.getElementById('wikiExport').getAttribute('aria-busy')==='true'")
   assert js('markdownReads')==count+1
   wait("!document.getElementById('wikiExport').disabled",60)
   assert js("!document.getElementById('wikiStatus').classList.contains('error')")
   measure('relationOpen',"document.getElementById('wikiSettings').open")
   measure('wikiSettingsClose',"!document.getElementById('wikiSettings').open")
   measure('researchOpen',"!document.getElementById('researchPanel').hidden")
   measure('researchBack',"document.getElementById('researchPanel').hidden")
   measure('wikiBack',"document.getElementById('wikiPanel').hidden")
   measure('modeWiki',"!document.getElementById('wikiPanel').hidden")
  report={'url':args.url,'measurements':records,'max_feedback_ms':max(r['feedback_ms'] for r in records),'model_actions':0,'markdown_reads':js('markdownReads'),'workspace_writes_isolated':len(js('probeWrites'))}
  pathlib.Path('/tmp/wiki-live-feedback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('PASS live browser',json.dumps(report,ensure_ascii=False),flush=True)
  pathlib.Path('/tmp/wiki-button-live.png').write_bytes(__import__('base64').b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
 finally:
  os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10)
