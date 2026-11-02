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
    with tempfile.TemporaryDirectory(prefix='atlas-journeys-') as folder:
        folder=Path(folder);page=folder/'test.html';generate(page)
        html=page.read_text();start=html.rfind('<script>\n(async()=>{try{')
        assert start>0
        page.write_text((html[:start]+'</body></html>').replace('<script>',"<script>localStorage.setItem('graphnews.searchDraft',JSON.stringify({forceRefresh:true}));</script><script>",1))
        log=(folder/'chrome.log').open('w')
        chrome=subprocess.Popen(['google-chrome','--headless=new',*(['--disable-webgl'] if '--no-webgl' in sys.argv else []),'--no-sandbox','--disable-dev-shm-usage','--window-size=1440,1000','--remote-debugging-port=0','--remote-allow-origins=*','--allow-file-access-from-files','--user-data-dir='+str(folder/'profile'),page.as_uri()],stdout=log,stderr=log,start_new_session=True)
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
            checks={}
            def check(name,code):
                checks[name]=js(code)
                print(json.dumps({'action':name,'passed':checks[name]}),flush=True)
                if not checks[name]:
                    print(js("JSON.stringify({rect:$('highlightModeSwitch').getBoundingClientRect().toJSON(),panel:$('sourcePanel').getBoundingClientRect().toJSON(),scroll:document.scrollingElement.scrollTop,mode:viewMode,highlightMode,graphChannel,size:categoryTrace.nodes.size,disabled:$('rootQuery').disabled,hit:(()=>{const r=$('highlightModeSwitch').getBoundingClientRect();return document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.outerHTML})()})"))
                assert checks[name],name
            def wait_for(code):
                for _ in range(100):
                    if js(code):return
                    time.sleep(.05)
                raise AssertionError('Timed out: '+code)
            js('rebuild(initialGraph)')
            if '--no-webgl' in sys.argv:
                check('real browser rejects WebGL at startup',"!!graphFailure&&!graph&&articles.length===3")
                click('modeNetwork');wait_for("!graphRetryBusy")
                check('failure does not substitute a different renderer',"viewMode==='timeline'&&!graph&&typeof AtlasCanvasGraph==='undefined'&&articles.length===3")
                check('3D failure stays explicit and retryable',"$('modeNetwork').textContent.includes('3D')&&!$('modeNetwork').disabled&&$('activityText').textContent.includes(graphFailure.message)")
                check('no unhandled errors',"errors.length===0")
                print(json.dumps(checks));call('Browser.close');ws.close();return 0
            check('initial 3D ready',"!!graph&&!graphFailure&&renderBudget===800")
            js("window.realFetch=window.fetch;window.fetch=async(url,options)=>{if(url==='/api/graph/build'){window.pendingBuild=JSON.parse(options.body);return new Promise(r=>window.finishBuild=r);}if(url==='/api/search')return new Response(new ReadableStream({start(c){window.feed=c;}}));return realFetch(url,options);}")
            click('relationOpen');click('relation-entity');click('relationApply')
            check('applying shows progress',"relationActivity.busy&&!$('relationSpinner').hidden&&!$('activitySpinner').hidden")
            click('relationClose');click('modeTimeline')
            check('timeline usable during applying',"viewMode==='timeline'&&articles.length===3&&relationActivity.busy")
            click('modeNetwork');check('graph usable during applying',"viewMode==='network'&&graph.graphData().nodes.length===3")
            click('cancelOperation');check('cancel keeps graph',"!relationActivity.busy&&articles.length===3&&!$('activityText').textContent.includes('NaN')")
            js("finishBuild({ok:true,json:async()=>variants.off})");time.sleep(.3)
            check('late cancelled reply ignored',"relations.length>0")
            js("$('query').value='test';$('ticker').value='';$('start').value='2026-01-01';$('end').value='2026-01-31'")
            click('submit');wait_for("!!window.feed")
            check('waiting search preserves graph and gives status',"!!controller&&articles.length===3&&!$('activitySpinner').hidden")
            click('modeTimeline');click('modeNetwork')
            check('switching during source wait',"!!controller&&viewMode==='network'&&graph.graphData().nodes.length===3")
            click('relationOpen');check('apply unavailable with reason during search',"$('relationApply').disabled&&$('relationApplyText').textContent.includes('搜尋')")
            click('relationClose')
            js("window.sendEvent=e=>feed.enqueue(new TextEncoder().encode(JSON.stringify(e)+'\\n'));sendEvent({type:'cache',graph:{...initialGraph,relations_pending:true,relations:[],cross_relations:[],source_graphs:Object.fromEntries(Object.entries(initialGraph.source_graphs).map(([k,v])=>[k,{...v,relations:[]}]))}});sendEvent({type:'phase',phase:'relations'});")
            wait_for("basePayload.relations_pending===true")
            check('nodes precede edges',"graph.graphData().nodes.length===3&&relations.length===0&&searchPhase==='relations'")
            click('view-google');click('modeTimeline');click('view-google');click('modeNetwork')
            check('source toggles during edge wait',"articles.length===3&&!!controller")
            js("sendEvent({type:'graph',graph:{...initialGraph,relations_pending:false}});sendEvent({type:'done'});feed.close()")
            wait_for("controller===null")
            check('finished graph responsive',"graph.graphData().nodes.length===3&&relations.length>0&&!$('activitySpinner').hidden===false")
            click('submit');wait_for("!!controller")
            js("window.cancelledFeed=feed")
            click('cancelOperation')
            check('search cancel releases controls',"controller===null&&!$('submit').disabled&&articles.length===3")
            click('submit');wait_for("controller!==null&&feed!==cancelledFeed")
            js("cancelledFeed.enqueue(new TextEncoder().encode(JSON.stringify({type:'graph',graph:{articles:[],relations:[]}})+'\\n'));cancelledFeed.close()")
            time.sleep(.2)
            check('cancelled search cannot replace newer search',"controller!==null&&articles.length===3")
            js("sendEvent({type:'graph',graph:{...initialGraph,relations_pending:false}});sendEvent({type:'done'});feed.close()")
            wait_for("controller===null")
            js("showArticle(articles[0]);window.savedRoot=focusRoot();window.expectedIds=articles.map(a=>a.id).join();channelDefinitions=[{id:'test',name:'Test'}];basePayload.channel_definitions=channelDefinitions;for(const g of Object.values(basePayload.source_graphs))for(const a of g.articles)a.channels=[{id:'test',name:'Test',evidence:[]}];rebuild()")
            if js("$('sourcePanelBody').hidden"):click('sourcePanelDrag')
            click('highlightModeSwitch')
            js("$('graphChannel').value='test';$('graphChannel').dispatchEvent(new Event('change'))")
            check('category glow exclusive',"categoryTrace.nodes.size===3&&graphTrace()===categoryTrace&&$('rootQuery').disabled")
            js("showArticle(articles[1]);setHovered(articles[2])")
            check('category click retains root',"focusRoot()===savedRoot&&articles.map(a=>a.id).join()===expectedIds")
            click('highlightModeSwitch');check('root mode restored',"focusRoot()===savedRoot&&graphTrace()===activeTrace&&!$('rootQuery').disabled")
            js("relationUI.restore(AtlasRelations.defaults);const seed=initialGraph.source_graphs.google.articles[0];const all=Array.from({length:7106},(_,i)=>({...seed,id:String(i),published_at:'2026-01-01T00:00:00Z'}));rebuild({source_graphs:{google:{articles:all,relations:[],total_articles:all.length}},relation_settings:AtlasRelations.defaults})")
            check('7106 records bounded at initialization',"articles.length===7106&&graph.graphData().nodes.length===800&&$('activityText').textContent.includes('800/7106')")
            js("showArticle(articles[7105])")
            check('offscreen article can enter 3D',"graph.graphData().nodes.some(n=>n.id===articles[7105].id)&&graph.graphData().nodes.length===800")
            js("$('renderBudget').value='2400';$('renderBudget').dispatchEvent(new Event('change'))")
            check('2400 budget retains full news and renders requested nodes',"renderBudget===2400&&graph.graphData().nodes.length===2400&&articles.length===7106")
            js("$('renderBudget').value='800';$('renderBudget').dispatchEvent(new Event('change'))")
            js("window.lossExtension=graph.renderer().getContext().getExtension('WEBGL_lose_context');lossExtension.loseContext()")
            wait_for("graphFailure?.kind==='context-lost'")
            check('real WebGL loss lowers budget and preserves data',"viewMode==='timeline'&&renderBudget===400&&articles.length===7106&&!$('modeNetwork').disabled&&!$('retryGraph').hidden")
            click('retryGraph');wait_for("!graphRetryBusy")
            check('retry recreates real WebGL',"!!graph&&!graphFailure&&viewMode==='network'&&graph.graphData().nodes.length===400&&articles.length===7106")
            js("window.oldGraphDestructor=graph._destructor.bind(graph);graph._destructor=()=>{oldGraphDestructor();throw Error('controlled cleanup failure')}")
            click('retryGraph');wait_for("!graphRetryBusy")
            check('cleanup exception does not block retry',"!!graph&&!graphFailure&&viewMode==='network'")
            js("window.originalFactory=ForceGraph3D;ForceGraph3D=()=>{throw Error('controlled GPU unavailable')};reportGraphFailure('context-lost','controlled failure')")
            click('retryGraph');wait_for("!graphRetryBusy")
            check('persistent failure retains data without replacing 3D',"!!graphFailure&&viewMode==='timeline'&&!graph&&typeof AtlasCanvasGraph==='undefined'&&!$('modeNetwork').disabled&&articles.length===7106")
            check('failure reason visible without expanding details',"$('activityText').textContent.includes('controlled GPU unavailable')&&$('modeNetwork').textContent.includes('3D')")
            js("ForceGraph3D=originalFactory")
            click('retryGraph');wait_for("!graphRetryBusy")
            check('second retry successful at reduced budget',"!graphFailure&&viewMode==='network'&&graph.graphData().nodes.length===100")
            check('no unhandled browser errors',"errors.length===0")
            import base64
            Path('/tmp/atlas-user-journeys.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            print(json.dumps(checks));call('Browser.close');ws.close()
            return 0 if all(checks.values()) else 1
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
