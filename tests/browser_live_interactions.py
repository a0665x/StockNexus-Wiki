"""Live Chromium checks: no model jobs; isolates workspace writes; needs websocket-client."""
import json,os,signal,subprocess,tempfile,time,urllib.request,pathlib,sys
import websocket
import argparse
parser=argparse.ArgumentParser(description="Live News/Wiki interaction journey; workspace preference writes are isolated.")
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
  call('Page.addScriptToEvaluateOnNewDocument',{'source':"""window.probeWrites=[];window.probeErrors=[];window.addEventListener('error',e=>probeErrors.push(e.message));window.addEventListener('unhandledrejection',e=>probeErrors.push(String(e.reason)));const realFetch=window.fetch;window.fetch=(u,o)=>{if(o?.method==='POST'&&String(u)==='/api/workspace'){probeWrites.push(String(u));return Promise.resolve(new Response('{}',{status:200}));}if(o?.method&&o.method!=='GET'&&!['/api/cache/graph','/api/graph/preview'].includes(String(u))){probeErrors.push('Unexpected write '+u);return Promise.reject(Error('UI audit blocked write'));}return realFetch(u,o)};"""})
  call('Page.navigate',{'url':args.url})
  wait("typeof AtlasWiki!=='undefined'",45)
  # Fail before interacting if the preference-write guard did not initialize.
  assert js('Array.isArray(window.probeWrites)'), 'workspace write isolation not installed'
  records=[]
  def measure(ident,predicate):
   js("""(()=>{const id="""+json.dumps(ident)+""";window.measured=null;document.addEventListener('click',function observe(e){if(!document.getElementById(id)?.contains(e.target))return;document.removeEventListener('click',observe,true);const start=performance.now();const frame=()=>{if("""+predicate+"""){requestAnimationFrame(()=>{measured=performance.now()-start});return;}if(performance.now()-start>2000){measured=-1;return;}requestAnimationFrame(frame)};requestAnimationFrame(frame)},{capture:true})})()""")
   click(ident);wait('measured!==null',5);ms=js('measured');records.append({'button':ident,'feedback_ms':round(ms,1)});print(json.dumps(records[-1]),flush=True);assert 0<=ms<2000
  checks=[]
  def check(label,condition):
   assert js(condition),label
   checks.append(label);print('PASS '+label,flush=True)
  def choose(ident,value):
   index=js("[...document.getElementById("+json.dumps(ident)+").options].findIndex(o=>o.value==="+json.dumps(value)+")")
   assert index>=0,(ident,value)
   click(ident)
   for key in ['Home']+['ArrowDown']*index+['Enter']:
    for event in ['keyDown','keyUp']:call('Input.dispatchKeyEvent',{'type':event,'key':key})
   wait("document.getElementById("+json.dumps(ident)+").value==="+json.dumps(value))
  wait("AtlasRuntime.state().counts.loaded>0",90)
  js('window.newsCount=AtlasRuntime.state().counts.loaded;window.originalBudget=document.getElementById("renderBudget").value')
  measure('modeTimeline',"document.getElementById('modeTimeline').classList.contains('active')")
  click('timelineZoomIn');check('Timeline zoom changes its readout',"Number(document.getElementById('timelineZoom').value)>1")
  click('timelineZoomOut')
  measure('modeNetwork',"document.getElementById('modeNetwork').classList.contains('active')")
  choose('renderBudget','400');check('GPU budget preserves full news data',"AtlasRuntime.state().counts.loaded===newsCount")
  choose('renderBudget',js('originalBudget'))
  measure('relationOpen',"document.getElementById('relationDialog').open")
  click('relationClose');check('Closing settings keeps news dataset',"!document.getElementById('relationDialog').open&&AtlasRuntime.state().counts.loaded===newsCount")
  measure('modeWiki',"!document.getElementById('wikiPanel').hidden")
  wait("AtlasWiki.graph()&&AtlasWiki.graph().graphData().nodes.length>0",90)
  js('window.originalVersion=document.getElementById("wikiVersion").value;window.originalKind=document.getElementById("wikiKind").value;window.originalClass=document.getElementById("wikiAssessment").value')
  choose('wikiKind','Claim');check('Node filter renders claims only',"AtlasWiki.graph().graphData().nodes.every(n=>n.kind==='Claim')")
  choose('wikiKind',js('originalKind'))
  ids=js("[...document.getElementById('wikiAssessment').options].map(o=>o.value).filter(Boolean)")
  if ids:
   choose('wikiAssessment',ids[0]);check('Classification selection remains selected',"document.getElementById('wikiAssessment').value==="+json.dumps(ids[0]))
   choose('wikiAssessment',js('originalClass'))
  js("window.auditRunFetch=fetch;window.auditHoldRuns=true;window.auditReleaseRuns=null;window.fetch=async(u,o)=>{if(auditHoldRuns&&String(u).includes('/research/runs?'))await new Promise(r=>auditReleaseRuns=r);return auditRunFetch(u,o)}")
  choose('wikiLayer','L2');wait('auditReleaseRuns!==null',20)
  check('Slow L2 lookup has visible loading',"!document.getElementById('wikiResearchStatus').hidden&&document.getElementById('wikiResearchStatus').getAttribute('aria-busy')==='true'")
  click('researchOpen');wait("!document.getElementById('researchPanel').hidden")
  check('Opening research clears superseded loading',"document.getElementById('wikiResearchStatus').hidden")
  js('auditHoldRuns=false;auditReleaseRuns()');click('researchBack');choose('wikiLayer','L1')
  # Historical view -> latest should restore only the requested version.
  versions=js("[...document.getElementById('wikiVersion').options].map(o=>o.value).filter(Boolean)")
  if versions:
   choose('wikiVersion',versions[-1]);wait('AtlasWiki.runtime.state().version==='+versions[-1],90)
   check('Historical graph matches chosen version',"document.getElementById('wikiVersion').value==="+json.dumps(versions[-1]))
   choose('wikiVersion',js('originalVersion'));wait("document.getElementById('wikiStatus').getAttribute('aria-busy')!=='true'",90)
  choose('wikiLayer','L2')
  wait("document.getElementById('wikiResearchStatus').getAttribute('aria-busy')!=='true'",90)
  check('L2 empty/result/error is visible on the main surface',"AtlasWiki.runtime.state().research_run!==null||!document.getElementById('wikiResearchStatus').hidden")
  choose('wikiLayer','L1')
  check('Return L1 clears L2 loading and result',"document.getElementById('wikiResearchStatus').hidden&&document.getElementById('researchResult').hidden")
  measure('researchOpen',"!document.getElementById('researchPanel').hidden")
  wait("!document.getElementById('researchStatus').classList.contains('research-working')",60)
  if js('AtlasWiki.l1Busy()'):
   wait("document.getElementById('researchSubmit').disabled",10)
   rect=js("(()=>{const e=document.getElementById('researchSubmitWrap');e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
   call('Input.dispatchMouseEvent',{'type':'mouseMoved',**rect});wait("!document.getElementById('researchBusyTip').hidden",5)
   check('Busy L1 explains disabled research action',"document.getElementById('researchBusyTip').textContent.includes('停止 L1')")
  click('researchBack')
  # Take desktop and mobile captures in one verification pass.
  for width in (1681,390):
   call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':False});time.sleep(.3)
   check(str(width)+' viewport keeps Wiki within page',"document.documentElement.scrollWidth<=innerWidth+2")
   pathlib.Path('/tmp/wiki-interaction-'+str(width)+'.png').write_bytes(__import__('base64').b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
  call('Emulation.setDeviceMetricsOverride',{'width':1681,'height':1000,'deviceScaleFactor':1,'mobile':False})
  click('wikiBack');check('News remains available after all Wiki navigation',"AtlasRuntime.state().counts.loaded===newsCount")
  check('No uncaught JavaScript errors or unexpected write actions',"probeErrors.length===0")
  report={'url':args.url,'checks':checks,'measurements':records,'workspace_writes_isolated':len(js('probeWrites')),'model_actions':0}
  pathlib.Path('/tmp/wiki-interaction-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('PASS live interaction journey',json.dumps(report,ensure_ascii=False),flush=True)
 finally:
  os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=10)
