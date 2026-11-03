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
  for action in [{'kind':'set','id':'renderBudget','value':'2400'},{'kind':'click','id':'modeTimeline'},{'kind':'set','id':'timelineZoom','value':2},{'kind':'click','id':'modeNetwork'}]:
   result=js('(async()=>{const a='+json.dumps(action)+';a.revision=AtlasRuntime.state().revision;return await AtlasRuntime.act(a);})()',True)
   print('PASS: actual UI action '+action['id'],flush=True)
  assert js("(async()=>{try{await AtlasRuntime.act({revision:-1,kind:'click',id:'fit'});return false}catch{return true}})()",True)
  assert js("(async()=>{try{await AtlasRuntime.act({revision:AtlasRuntime.state().revision,kind:'set',id:'key',value:'secret'});return false}catch{return true}})()",True)
  print('PASS: stale revision and credentials control rejected',flush=True)
  if '--live' not in sys.argv:
   image=call('Page.captureScreenshot',{'format':'png'})['data'];Path('/tmp/atlas-chat-ui.png').write_bytes(base64.b64decode(image))
   raise SystemExit(0)
  js("document.querySelector('.chat-compose textarea').value='請先用工具讀取我現在的 root 選取範圍，讀取其中最多三篇新聞，用繁體中文整理兩個重點並附上來源網址。然後請實際把畫面切換到時間軸，將 timelineZoom 設為 2。';document.querySelector('.chat-compose').requestSubmit()")
  wait("document.querySelector('.chat-compose button').disabled",5)
  wait("!document.querySelector('.chat-compose button').disabled",180)
  print('CHAT STATUS:',js("document.querySelector('.chat-status').textContent"),flush=True)
  print('CHAT ANSWER:',js("Array.from(document.querySelectorAll('.chat-message.assistant')).map(e=>e.textContent).join(' | ')"),flush=True)
  state=js('AtlasRuntime.state()');print('FINAL STATE:',json.dumps({'view':state['view_mode'],'zoom':next(c['value'] for c in state['controls'] if c['id']=='timelineZoom'),'root_count':len(state['root_ids'])}),flush=True)
  image=call('Page.captureScreenshot',{'format':'png'})['data'];Path('/tmp/atlas-chat-qa.png').write_bytes(base64.b64decode(image))
  assert js("document.querySelectorAll('.chat-message.assistant').length>0"),'No real reply'
  assert state['view_mode']=='timeline','LLM did not actually change view'
  assert next(c['value'] for c in state['controls'] if c['id']=='timelineZoom')=='2'
  print('PASS: real Codex login, MCP evidence and acknowledged view controls',flush=True)
  js("document.querySelector('.chat-compose textarea').value='上一則我請你把哪個縮放控制設為多少？只回答這個數值與控制名稱。';document.querySelector('.chat-compose').requestSubmit()")
  wait("document.querySelector('.chat-compose button').disabled",5)
  wait("!document.querySelector('.chat-compose button').disabled",120)
  assert js("document.querySelectorAll('.chat-message.assistant').length>=2")
  print('PASS: continued conversation',flush=True)
  js("document.querySelector('.chat-compose textarea').value='請逐篇分析目前選取的所有新聞，先用工具逐批讀取。';document.querySelector('.chat-compose').requestSubmit()")
  wait("document.querySelector('.chat-compose button').disabled",5)
  time.sleep(2)
  js("document.querySelectorAll('.chat-toolbar button')[1].click()")
  wait("!document.querySelector('.chat-compose button').disabled",30)
  assert js("document.querySelector('.chat-status').textContent.includes('停止')")
  print('PASS: real running turn cancelled',flush=True)
  js("document.querySelector('.chat-toolbar button').click()")
  wait("document.querySelectorAll('.chat-message').length===0")
  print('PASS: new conversation resets display',flush=True)
 finally:
  os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()
