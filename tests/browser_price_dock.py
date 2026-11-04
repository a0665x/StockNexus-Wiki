"""Isolated Chrome UI QA against the running local app and existing snapshots.
Uses existing snapshots and real Massive prices/cache; may consume provider quota.
No model calls and no news DB fixture writes.
"""
import sys
import shutil
import json,os,signal,subprocess,tempfile,time,urllib.request,base64
from pathlib import Path
import websocket
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='atlas-chat-qa-') as temp:
 p=Path(temp);log=(p/'chrome.log').open('w')
 chrome=subprocess.Popen([os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium') or 'google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader','--window-size=1542,1131','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(p/'profile'),'http://127.0.0.1:8765/'],stdout=log,stderr=log,start_new_session=True)
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
  wait("typeof AtlasRuntime!=='undefined'&&!!document.getElementById('paneWorkspace')")
  js("window.qaErrors=[];window.addEventListener('error',e=>qaErrors.push(e.message));window.addEventListener('unhandledrejection',e=>qaErrors.push(String(e.reason)))")
  wait("!!document.querySelector('#snapshots button')")
  js("document.querySelector('#snapshots button').click()")
  wait('AtlasRuntime.state().counts.loaded>0',30)
  js("$('ticker').value='AAPL';$('ticker').dispatchEvent(new Event('input'));$('ticker').dispatchEvent(new Event('change'))")
  wait("document.querySelectorAll('#priceChart [data-date]').length>0",35)
  assert js("!document.getElementById('priceColors')&&!document.querySelector('[data-dock-tool]')")
  assert js("!!document.querySelector('#priceChart [data-close-line]')")
  assert js("""(()=>{const bars=priceLens.snapshot().bars,horizon=AtlasRuntime.state().price_focus.horizon,old=timeFocus.date;let count=0;for(const sign of [1,-1]){const base=bars.find(b=>{const m=AtlasPriceChart.model(bars,b.date,horizon);return m.complete&&m.means.at(-1).return*sign>0;});if(!base)continue;priceLens.clearSelection();updateTimeCurve({date:base.date});if(!$('priceLegend').querySelector('[data-direction=\"'+sign+'\"][data-active=true]'))return false;count++;}updateTimeCurve({date:old});return count===2;})()""")
  print('PASS: complete positive/negative N-day returns highlight the corresponding arrow',flush=True)
  print('PASS: real auto-loaded OHLC with overlaid price line; no color or docking controls',flush=True)
  def click(selector):
   r=js("(()=>{const e=document.querySelector("+json.dumps(selector)+");e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
   for kind in ['mousePressed','mouseReleased']:call('Input.dispatchMouseEvent',{'type':kind,**r,'button':'left','clickCount':1})
   time.sleep(.15)
  def drag_to(selector,x,y,hold=0):
   r=js("(()=>{const e=document.querySelector("+json.dumps(selector)+");e.scrollIntoView({block:'nearest'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
   call('Input.dispatchMouseEvent',{'type':'mouseMoved',**r})
   call('Input.dispatchMouseEvent',{'type':'mousePressed',**r,'button':'left','clickCount':1})
   for i in range(1,7):call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':r['x']+(x-r['x'])*i/6,'y':r['y']+(y-r['y'])*i/6,'button':'left','buttons':1})
   time.sleep(hold)
   if hold and js("!$('splitPreview').hidden"):wait("$('splitPreview').classList.contains('split-armed')",5)
   call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':x,'y':y,'button':'left','clickCount':1});time.sleep(.2)
  def rect(selector):return js("document.querySelector("+json.dumps(selector)+").getBoundingClientRect().toJSON()")
  if js("$('timeFocusBody').hidden"):click('#timePanelDrag')
  js("$('priceChart').scrollIntoView({block:'center'})")
  r=rect('#priceChart')
  js("window.beforeZoom=AtlasRuntime.state().time_focus;window.beforeStart=$('priceChart').dataset.start;window.beforeEnd=$('priceChart').dataset.end")
  call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':r['x']+r['width']/2,'y':r['y']+r['height']/2})
  wait("document.querySelectorAll('[data-crosshair]').length===2",5)
  call('Input.dispatchMouseEvent',{'type':'mouseWheel','x':r['x']+r['width']/2,'y':r['y']+r['height']/2,'deltaX':0,'deltaY':-180})
  wait("$('priceChart').dataset.start!==beforeStart||$('priceChart').dataset.end!==beforeEnd")
  assert js("JSON.stringify(AtlasRuntime.state().time_focus)===JSON.stringify(beforeZoom)"), 'Zoom must not change size evaluation'
  assert js("$('timeFocusStart').textContent===$('priceChart').dataset.start&&$('timeFocusEnd').textContent===$('priceChart').dataset.end")
  js("$('priceChart').dispatchEvent(new MouseEvent('dblclick',{bubbles:true}))")
  assert js("$('priceChart').dataset.start===beforeStart&&$('priceChart').dataset.end===beforeEnd")
  assert js("!!document.querySelector('#timeBell #priceContribution')&&!!document.querySelector('#timeBell #timeContribution')")
  print('PASS: crosshair, shared-axis wheel zoom, unchanged sizing and double-click reset',flush=True)
  js("$('timePanelDrag').scrollIntoView({block:'nearest'})")
  r=rect('[data-pane="news"]')
  drag_to('#timePanelDrag',r['x']+r['width']/2,r['y']+r['height']/2,.8)
  assert not js("AtlasDock.docked($('timeFocusBar'))"),'Center must not attach'
  js("$('timePanelDrag').scrollIntoView({block:'nearest'})")
  r=rect('[data-pane="news"]')
  drag_to('#timePanelDrag',r['x']-20,r['y']+r['height']/2,.8)
  assert not js("AtlasDock.docked($('timeFocusBar'))"),'Gap must not attach'
  js("$('timePanelDrag').scrollIntoView({block:'nearest'})")
  r=rect('[data-pane="news"]')
  drag_to('#timePanelDrag',r['x']+r['width']/2,r['y']+2)
  assert not js("AtlasDock.docked($('timeFocusBar'))"),'Fast edge pass must not attach'
  # The fast pass ends exactly on the edge. Move away before a second drag;
  # otherwise the zero-distance gesture is a click that collapses the tool.
  drag_to('#timePanelDrag',r['x']-80,r['y']+80)
  r=rect('[data-pane="news"]')
  drag_to('#timePanelDrag',r['x']+r['width']/2,r['y']+2,.85)
  if not js("AtlasDock.docked($('timeFocusBar'))"):
   Path('/tmp/wiki-price-failure.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
   print(js("JSON.stringify({dock:AtlasDock.state(),drag:$('timePanelDrag').getBoundingClientRect().toJSON()})"),flush=True)
  assert js("AtlasDock.docked($('timeFocusBar'))"),'Edge dwell should attach'
  assert js("AtlasDock.state().tree.axis")=='column'
  assert js("AtlasDock.state().tree.a.id")=='timeFocusBar'
  print('PASS: no center/gap/fast attachment; 650ms edge dwell creates top pane',flush=True)
  if js("$('sourcePanelBody').hidden"):click('#sourcePanelDrag')
  js("$('sourcePanelDrag').scrollIntoView({block:'nearest'})")
  r=rect('[data-pane="news"]');drag_to('#sourcePanelDrag',r['x']+2,r['y']+r['height']/2,.85)
  assert js("AtlasDock.docked($('sourcePanel'))")
  assert js("AtlasDock.state().tree.b.axis")=='row'
  print('PASS: left-edge split adapts independently within the remaining news pane',flush=True)
  # A compact tool intentionally uses an 88px pane, not the saved split ratio.
  if js("$('timeFocusBody').hidden"):click('#timePanelDrag')
  r=rect('.pane-workspace > .pane-split > .pane-divider');before=js('AtlasDock.state().tree.ratio')
  drag_to('.pane-workspace > .pane-split > .pane-divider',r['x']+r['width']/2,r['y']+r['height']/2+60)
  assert js('AtlasDock.state().tree.ratio')>before
  r=rect('#stage');drag_to('#sourcePanelDrag',r['x']+r['width']/2,r['y']+r['height']/2)
  assert not js("AtlasDock.docked($('sourcePanel'))")
  assert js("AtlasDock.state().tree.b.id")=='news'
  assert js("Math.abs(parseFloat(document.querySelector('[data-pane=news]').style.flexGrow)-(1-AtlasDock.state().tree.ratio))<.001"), 'Promoted pane must inherit its outer split ratio'
  if not js("$('sourcePanelBody').hidden"):click('#sourcePanelToggle')
  assert rect('#sourcePanel')['width']>=71 and rect('#sourcePanel')['height']>=71
  print('PASS: resize, drag out, split collapse and doubled compact icon',flush=True)
  js("showArticle(articles.find(a=>a.published_at?.startsWith('2026-10-'))||articles[0])")
  assert js("$('timeFocusDate').textContent.startsWith(articles.find(a=>a.id===selected).published_at.slice(0,10))")
  assert js('qaErrors')==[],js('qaErrors')
  Path('/tmp/atlas-edge-v2.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
  call('Page.reload');wait("typeof AtlasDock!=='undefined'&&document.querySelector('[data-pane=timeFocusBar]')!==null")
  assert js("AtlasDock.state().tree.a.id")=='timeFocusBar'
  print('PASS: adaptive split layout persists after reload',flush=True)
  for edge in ['right','bottom']:
   js("$('sourcePanelDrag').scrollIntoView({block:'nearest'})")
   r=rect('[data-pane="news"]')
   drag_to('#sourcePanelDrag',r['right']-2 if edge=='right' else r['x']+r['width']/2,r['y']+r['height']/2 if edge=='right' else r['bottom']-2,.85)
   assert js("AtlasDock.state().tree.b.axis")==('row' if edge=='right' else 'column')
   r=rect('#stage');drag_to('#sourcePanelDrag',r['x']+r['width']/2,r['y']+r['height']/2)
   assert js("AtlasDock.state().tree.b.id")=='news'
  print('PASS: right and bottom edge splits restore remaining pane after removal',flush=True)
 finally:
  os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()
