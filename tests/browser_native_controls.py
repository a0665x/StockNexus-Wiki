"""Real Chromium pointer/keyboard events: catch bugs hidden by element.click().
Requires google-chrome and Python websocket-client. Uses isolated HTTP fixtures.
"""
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
import websocket
from browser_relations import generate


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-native-') as folder:
        folder=Path(folder);page=folder/'test.html';generate(page)
        html=page.read_text();start=html.rfind('<script>\n(async()=>{try{')
        assert start>0
        page.write_text((html[:start]+'</body></html>').replace('<script>',"<script>localStorage.setItem('graphnews.searchDraft',JSON.stringify({forceRefresh:true}));</script><script>",1))
        log=(folder/'chrome.log').open('w')
        chrome=subprocess.Popen(['google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1440,1000','--remote-debugging-port=0','--remote-allow-origins=*','--allow-file-access-from-files','--user-data-dir='+str(folder/'profile'),page.as_uri()],stdout=log,stderr=log,start_new_session=True)
        try:
            portfile=folder/'profile/DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():break
                time.sleep(.05)
            port=int(portfile.read_text().splitlines()[0]);targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
            ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),timeout=10,suppress_origin=True)
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
                result=call('Runtime.evaluate',{'expression':code,'returnByValue':True})
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
            js('rebuild(initialGraph)');checks={}
            for prefix,body in [('sourcePanel','sourcePanelBody'),('timePanel','timeFocusBody')]:
                if not js(f"document.getElementById('{body}').hidden"):click(prefix+'Toggle')
                click(prefix+'Drag');checks[prefix+'NativeRestore']=not js(f"document.getElementById('{body}').hidden")
                # Dragging must not open the icon; the following real click must.
                click(prefix+'Toggle')
                rect=js(f"(()=>{{const r=document.getElementById('{prefix}Drag').getBoundingClientRect();return {{x:r.x+18,y:r.y+18}};}})()")
                call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**rect})
                call('Input.dispatchMouseEvent',{'type':'mouseMoved','button':'left','buttons':1,'x':rect['x']+70,'y':rect['y']+40})
                call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,'x':rect['x']+70,'y':rect['y']+40});time.sleep(.1)
                checks[prefix+'DragStaysCompact']=js(f"document.getElementById('{body}').hidden")
                click(prefix+'Drag');checks[prefix+'RestoreAfterDrag']=not js(f"document.getElementById('{body}').hidden")
            click('relationOpen')
            for key in ['entity','topic','title']:click('relation-'+key)
            click('relationApply');time.sleep(.4)
            checks['SingleApplyRetainsNodes']=js("relations.length===0&&articles.length===3")
            checks['NoVerboseSummary']=js("document.getElementById('relationStatus').hidden")
            for key in ['entity','topic','title']:click('relation-'+key)
            click('relationApply');time.sleep(.4)
            checks['AdaptiveRestored']=js("relations.length>0&&basePayload.relation_settings.adaptive===true")
            point=js("(()=>{const e=document.querySelector('[data-rule-help=adaptive]');e.scrollIntoView();const r=e.getBoundingClientRect();return {x:r.x+90,y:r.y+r.height/2};})()")
            call('Input.dispatchMouseEvent',{'type':'mouseMoved',**point});time.sleep(.6)
            checks['TooltipVisible']=js("Number(getComputedStyle(document.getElementById('relationTooltip')).opacity)>.9")
            time.sleep(2.6)
            checks['TooltipFades']=js("Number(getComputedStyle(document.getElementById('relationTooltip')).opacity)<.1")
            call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':point['x']+4,'y':point['y']});time.sleep(.6)
            checks['TooltipReturnsOnMove']=js("Number(getComputedStyle(document.getElementById('relationTooltip')).opacity)>.9")
            click('relationClose')
            js("exportMeta={start:'2025-11-03',end:'2026-11-02'};timelineCutoff=null")
            click('modeTimeline')
            checks['DensityOnly']=js("!document.getElementById('timelineStyle')&&!document.getElementById('timelinePlay')&&timelineStyle==='density'")
            checks['ZoomAtChannelRight']=js("(()=>{const a=document.getElementById('channelFilter').getBoundingClientRect(),b=document.getElementById('timelineZoom').getBoundingClientRect();return b.left>a.right&&Math.abs(b.top-a.top)<25})()")
            click('timelineZoomIn');checks['ZoomIn']=js("document.getElementById('timelineZoom').value==='1.5'&&document.getElementById('timelineZoomValue').textContent==='1.5×'")
            click('timelineZoomOut');checks['ZoomOut']=js("document.getElementById('timelineZoom').value==='1'")
            checks['CrossYearRuler']=js("document.getElementById('timeline').textContent.includes('2025')&&document.getElementById('timeline').textContent.includes('2026')")
            click('manageChannels');time.sleep(.6);checks['CustomChannelEntry']=js("document.getElementById('channelManager').open&&document.getElementById('channelName')!==null&&document.getElementById('channelKeywords')!==null&&document.activeElement===document.getElementById('channelName')")
            checks['RefreshDefaultsOff']=js("document.getElementById('forceRefresh').checked===false")
            js("document.getElementById('color-google').value='#ffff00';document.getElementById('color-google').dispatchEvent(new Event('input'))")
            checks['ColorSaved']=js("colors.google==='#ffff00'&&AtlasUI.read('sourceColors',{}).google==='#ffff00'&&document.getElementById('view-color-google').style.backgroundColor==='rgb(255, 255, 0)'")
            click('resetSourceColors')
            checks['ColorReset']=js("colors.google===defaultColors.google")
            js("(()=>{relationUI.restore(AtlasRelations.defaults);const seed=initialGraph.source_graphs.google.articles[0];const all=Array.from({length:1201},(_,i)=>({...seed,id:i.toString(16).padStart(24,'0'),published_at:i%2?'2025-12-31T12:00:00Z':'2026-01-01T12:00:00Z'}));channelFilter='all';timelineCutoff=null;rebuild({source_graphs:{google:{articles:all,relations:[],total_articles:all.length}},relation_settings:AtlasRelations.defaults,channel_definitions:initialGraph.channel_definitions});})()")
            checks['All1201InTimeline']=js("articles.length===1201&&AtlasTimeline.density(currentView,channelDefinitions).buckets.reduce((n,b)=>n+b.articles.length,0)===1201")
            click('modeNetwork');checks['Bounded3DCompleteData']=js("!!graph&&graph.graphData().nodes.length===800&&articles.length===1201")
            click('modeTimeline')
            import base64
            Path('/tmp/atlas-timeline-native.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            print(json.dumps(checks));call('Browser.close');ws.close()
            return 0 if all(checks.values()) else 1
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
