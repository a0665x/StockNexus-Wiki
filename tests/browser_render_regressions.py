"""Hidden/reopened candle geometry and physical camera controls after lost keyboard focus. No provider/model calls.
"""
import json
import os
import signal
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
import websocket
from browser_relations import generate


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-view-relations-') as folder:
        folder=Path(folder);page=folder/'test.html';generate(page)
        html=page.read_text();start=html.rfind('<script>\n(async()=>{try{')
        assert start>0
        page.write_text((html[:start]+'</body></html>').replace('<script>',"<script>localStorage.setItem('graphnews.searchDraft',JSON.stringify({forceRefresh:true}));</script><script>",1))
        log=(folder/'chrome.log').open('w')
        chrome=subprocess.Popen([os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium') or 'google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1100,1131','--remote-debugging-port=0','--remote-allow-origins=*','--allow-file-access-from-files','--user-data-dir='+str(folder/'profile'),page.as_uri()],stdout=log,stderr=log,start_new_session=True)
        try:
            portfile=folder/'profile/DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():break
                time.sleep(.05)
            port=int(portfile.read_text().splitlines()[0]);targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
            ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),timeout=45,suppress_origin=True)
            serial=0
            def call(method,params=None):
                nonlocal serial
                serial+=1;ws.send(json.dumps({'id':serial,'method':method,'params':params or {}}))
                while True:
                    result=json.loads(ws.recv())
                    if result.get('id')==serial:
                        if 'error' in result:raise RuntimeError(result['error'])
                        return result.get('result',{})
            def js(code):
                if 'await AtlasWiki.refresh()' in code:code='(async()=>{'+code+'})()'
                result=call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in result:raise RuntimeError(result['exceptionDetails'])
                return result.get('result',{}).get('value')
            def click(id):
                rect=js(f"(()=>{{const e=document.getElementById({json.dumps(id)});e.scrollIntoView({{block:'nearest'}});const r=e.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}};}})()")
                call('Input.dispatchMouseEvent',{'type':'mouseMoved',**rect})
                call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**rect})
                call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,**rect});time.sleep(.12)
            for _ in range(100):
                if js("typeof relationUI!=='undefined'&&relationUI!==null"):break
                time.sleep(.05)

            js("rebuild(initialGraph);clearTimeout(fitTimer);$('timeFocusBar').style.display='none';window.probePrice=AtlasPriceChart.init($,{getState:()=>({bars:[{date:'2026-10-30',open:100,high:105,low:95,close:103},{date:'2026-11-02',open:103,high:104,low:94,close:96}],date:'2026-10-30',horizon:1,ticker:'TSLA',bounds:{start:Date.parse('2025-11-06'),end:Date.parse('2026-11-06'),startDate:'2025-11-06',endDate:'2026-11-06',days:365}}),onDate(){}});probePrice.paint();$('timeFocusBar').style.display='block'");time.sleep(.2)
            js("$('timeFocusBar').style.display='none';syncTimeFocus();$('timeFocusBar').style.display='block'")
            assert js("+$('timeBellHandle').getAttribute('rx')<=40&&+$('timeBellHandle').getAttribute('ry')<=20"),'Hidden curve handle expands over the whole plot'
            js("probePrice.paint()")
            print('CANDLE_WIDTHS',js("[...$('priceChart').querySelectorAll('g rect')].map(n=>Number(n.getAttribute('width')))"),flush=True)
            print('CONTROLS',js("({keys:graph.controls().keys,state:graph.controls().state,keyState:graph.controls().keyState,noRotate:graph.controls().noRotate})"),flush=True)
            js("$('timeFocusBar').style.display='none';window.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyD',key:'d'}));window.dispatchEvent(new Event('blur'));window.dispatchEvent(new Event('focus'))")
            print('AFTER_BLUR',js("({state:graph.controls().state,keyState:graph.controls().keyState,keys:graph.controls().keys})"),flush=True)
            assert js("$('priceChart').querySelectorAll('g rect').length===2&&[...$('priceChart').querySelectorAll('g rect')].every(n=>Number(n.getAttribute('width'))<=18)"),'Hidden chart paints oversized candlesticks'
            assert js("graph.controls().keyState===-1"),'D key survives focus loss and keeps pan mode'
            # Exercise the real pointer handler, not just the controls flags.
            js("graph.controls().staticMoving=true;graph.controls().target.set(0,0,0);graph.cameraPosition({x:0,y:0,z:600});$('graph').scrollIntoView({block:'center'});window.cameraStart=graph.camera().position.toArray();window.targetStart=graph.controls().target.toArray()")
            time.sleep(.1)
            point=js("(()=>{const r=$('graph').getBoundingClientRect();return {x:r.right-35,y:r.bottom-80}})()")
            def drag(modifiers=0):
                call('Input.dispatchMouseEvent',{'type':'mouseMoved',**point,'modifiers':modifiers})
                call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','buttons':1,'clickCount':1,**point,'modifiers':modifiers})
                for i in range(1,7):
                    call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':point['x']-i*10,'y':point['y']-i*5,'buttons':1,'button':'left','modifiers':modifiers});time.sleep(.03)
                call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':point['x']-60,'y':point['y']-30,'button':'left','clickCount':1,'modifiers':modifiers});time.sleep(.15)
            drag()
            assert js("graph.camera().position.toArray().some((v,i)=>Math.abs(v-cameraStart[i])>1)&&graph.controls().target.toArray().every((v,i)=>Math.abs(v-targetStart[i])<.01)"),'Left drag must rotate after focus loss'
            js("window.targetStart=graph.controls().target.toArray()")
            drag(2)
            assert js("graph.controls().target.toArray().some((v,i)=>Math.abs(v-targetStart[i])>1)"),'Ctrl left drag must still pan'
            js("$('timeFocusBar').style.display='block';$('timeChartStack').style.width='240px'");time.sleep(.25)
            assert js("$('priceChart').querySelectorAll('g rect').length===2&&[...$('priceChart').querySelectorAll('g rect')].every(n=>Number(n.getAttribute('width'))>0&&Number(n.getAttribute('width'))<=18)"),'Resize must keep candles bounded'
            print('PASS hidden chart, reopened chart, resize, lost-key focus, physical rotation, Ctrl pan',flush=True)
            return 0
        finally:
            os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()

if __name__=='__main__':main()
