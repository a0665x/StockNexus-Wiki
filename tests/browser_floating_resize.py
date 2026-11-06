"""Isolated browser regression for floating edge/corner resizing, scrolling, persistence and docking. Uses bundled assets in a generated fixture; no provider/model calls.
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
        chrome=subprocess.Popen([os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium') or 'google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1542,1131','--remote-debugging-port=0','--remote-allow-origins=*','--allow-file-access-from-files','--user-data-dir='+str(folder/'profile'),page.as_uri()],stdout=log,stderr=log,start_new_session=True)
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

            def check(label,code):
                value=js(code);print(label,value,flush=True)
                if not value:print(js("JSON.stringify({rect:$('timeFocusBar').getBoundingClientRect(),style:$('timeFocusBar').getAttribute('style'),saved:localStorage.getItem('graphnews.timePanel'),original:window.originalSize,errors})"),flush=True)
                assert value,label
            js("rebuild(initialGraph);window.before={ids:graph.graphData().nodes.map(n=>n.id),refs:graph.graphData().nodes.slice(),edges:JSON.stringify(relations),camera:JSON.stringify(graph.cameraPosition()),date:JSON.stringify(timeFocus)};void 0")
            time.sleep(.4)
            if js("$('timeFocusBody').hidden"):click('timePanelDrag')
            time.sleep(.2)
            check('expanded tools expose edge and corner resize handles',"$('timeFocusBar').querySelectorAll('[data-resize-edge]').length===8&&$('sourcePanel').querySelectorAll('[data-resize-edge]').length===8")
            def drag(edge,dx,dy,cancel=False):
                p=js("(()=>{const n=$('timeFocusBar').querySelector('[data-resize-edge='+"+json.dumps(edge)+"+']'),r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
                call('Input.dispatchMouseEvent',{'type':'mouseMoved',**p})
                call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','buttons':1,'clickCount':1,**p})
                for i in range(1,7):
                    call('Input.dispatchMouseEvent',{'type':'mouseMoved','button':'left','buttons':1,'x':p['x']+dx*i/6,'y':p['y']+dy*i/6});time.sleep(.025)
                if cancel:js("window.dispatchEvent(new Event('blur'))")
                call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,'x':p['x']+dx,'y':p['y']+dy});time.sleep(.2)
            check('opened tool remains expanded',"!$('timeFocusBody').hidden")
            js("window.originalSize=$('timeFocusBar').getBoundingClientRect().toJSON()")
            drag('se',-90,-110)
            check('corner shrinks both dimensions',"$('timeFocusBar').getBoundingClientRect().width<originalSize.width-60&&$('timeFocusBar').getBoundingClientRect().height<originalSize.height-80")
            check('body scrolls while title stays visible',"$('timeFocusBody').scrollHeight>$('timeFocusBody').clientHeight&&$('timeFocusBar').scrollHeight<=$('timeFocusBar').clientHeight+1")
            js("window.shrunk=$('timeFocusBar').getBoundingClientRect().toJSON();$('timeFocusBody').scrollTop=$('timeFocusBody').scrollHeight")
            check('header remains usable after content scroll',"$('timePanelDrag').getBoundingClientRect().top>=$('timeFocusBar').getBoundingClientRect().top")
            drag('e',40,0)
            check('single edge changes only width',"$('timeFocusBar').getBoundingClientRect().width>shrunk.width+30&&Math.abs($('timeFocusBar').getBoundingClientRect().height-shrunk.height)<1")
            js("window.edgeBefore=$('timeFocusBar').getBoundingClientRect().toJSON()")
            drag('nw',30,20)
            check('opposite corner keeps bottom and right anchored',"(()=>{const r=$('timeFocusBar').getBoundingClientRect();return r.width<edgeBefore.width-20&&r.height<edgeBefore.height-10&&Math.abs(r.bottom-edgeBefore.bottom)<2&&Math.abs(r.right-edgeBefore.right)<2})()")
            js("window.cancelSize=$('timeFocusBar').getBoundingClientRect().toJSON()")
            drag('se',35,35,True)
            check('cancel restores size',"Math.abs($('timeFocusBar').getBoundingClientRect().width-cancelSize.width)<1&&Math.abs($('timeFocusBar').getBoundingClientRect().height-cancelSize.height)<1")
            check('resizing preserves original graph objects and data',"graph.graphData().nodes.every((n,i)=>n===before.refs[i])&&JSON.stringify(relations)===before.edges&&JSON.stringify(timeFocus)===before.date")
            js("window.savedSize=JSON.parse(localStorage.getItem('graphnews.timePanel'));$('timePanelToggle').click();$('timePanelDrag').click()")
            time.sleep(.15)
            check('fold and expand retain dimensions',"Math.abs($('timeFocusBar').getBoundingClientRect().width-savedSize.width)<1&&Math.abs($('timeFocusBar').getBoundingClientRect().height-savedSize.height)<1")
            # Docking must use pane geometry, then restore floating dimensions on exit.
            js("const target=document.querySelector('[data-pane=news]').getBoundingClientRect();window.dockEvent={clientX:target.right-2,clientY:target.top+target.height/2};AtlasDock.preview(dockEvent)")
            time.sleep(.75)
            js("AtlasDock.finish($('timeFocusBar'),dockEvent)")
            check('docked tool hides floating resize handles',"AtlasDock.docked($('timeFocusBar'))&&$('timeFocusBar').querySelector('[data-resize-edge]').getBoundingClientRect().width===0")
            js("AtlasDock.undock($('timeFocusBar'))")
            time.sleep(.2)
            check('undock restores dimensions',"Math.abs($('timeFocusBar').getBoundingClientRect().width-savedSize.width)<1")
            import base64
            Path('/tmp/floating-resize.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            call('Page.reload');time.sleep(.8)
            check('reopen restores saved size',"Math.abs($('timeFocusBar').getBoundingClientRect().width-JSON.parse(localStorage.getItem('graphnews.timePanel')).width)<1")
            check('no browser errors',"errors.length===0")
            print('PASS floating resize, scroll, cancel, persistence and docking',flush=True)
        finally:
            os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()

if __name__=='__main__':main()
