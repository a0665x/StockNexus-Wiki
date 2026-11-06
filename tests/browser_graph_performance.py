"""Real WebGL with synthetic 10k news / 40k edges through the HTTP asset fixture.
Checks bounded work and complete data, not machine-dependent timing thresholds.
Requires Chromium (or CHROME_BIN) and websocket-client. No provider/model calls.
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
    with tempfile.TemporaryDirectory(prefix='atlas-performance-') as folder:
        folder=Path(folder);page=folder/'test.html';generate(page)
        html=page.read_text();start=html.rfind('<script>\n(async()=>{try{')
        assert start>0
        page.write_text((html[:start]+'</body></html>').replace('<script>',"<script>localStorage.setItem('graphnews.searchDraft',JSON.stringify({forceRefresh:true}));</script><script>",1))
        log=(folder/'chrome.log').open('w')
        chrome=subprocess.Popen([os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium') or 'google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1440,1000','--remote-debugging-port=0','--remote-allow-origins=*','--allow-file-access-from-files','--user-data-dir='+str(folder/'profile'),page.as_uri()],stdout=log,stderr=log,start_new_session=True)
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
            checks={};metrics={}
            def check(name,code):
                checks[name]=js(code)
                print(json.dumps({'check':name,'passed':checks[name]}),flush=True)
                assert checks[name],name
            def frame():
                js("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))")
            check('real WebGL ready',"!!graph&&!graphFailure&&renderBudget===800")
            metrics['renderer']=js("(()=>{const gl=graph.renderer().getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);})()")
            metrics['initial']=js("""(()=>{relationUI.restore(AtlasRelations.defaults);const seed=initialGraph.source_graphs.google.articles[0];window.perfRows=Array.from({length:10000},(_,i)=>({...seed,id:'perf-'+i,title:'Synthetic TEST '+(i===9999?'uniqueendmarker':i),published_at:'2026-01-01T00:00:00Z',channels:[{id:'perf',name:'Synthetic',evidence:[]}],primary_channel:'perf'}));window.perfEdges=perfRows.flatMap((a,i)=>[1,2,3,4].filter(k=>i+k<perfRows.length).map(k=>({source:a.id,target:perfRows[i+k].id,weight:.9,type:'shared_entity',evidence:[]})));const start=performance.now();rebuild({source_graphs:{google:{articles:perfRows,relations:perfEdges,total_articles:perfRows.length}},channel_definitions:[{id:'perf',name:'Synthetic'}],relation_settings:AtlasRelations.defaults});return {rebuild_ms:performance.now()-start,loaded:articles.length,gpu_nodes:graph.graphData().nodes.length,gpu_edges:graph.graphData().links.length,list_buttons:$('list').querySelectorAll('[data-article-id]').length};})()""")
            print(json.dumps(metrics),flush=True)
            check('10000 retained, only 100 article buttons',"articles.length===10000&&$('list').querySelectorAll('[data-article-id]').length===100")
            check('unchanged slice does not reset graph data or physics',"(()=>{const before=graph.graphData();renderNetwork();return before.nodes===graph.graphData().nodes&&before.links===graph.graphData().links;})()")
            check('default GPU and edge caps',"graph.graphData().nodes.length===800&&graph.graphData().links.length<=2400")
            js("$('list').querySelector('input').value='100';$('list').querySelector('input').dispatchEvent(new Event('change'))")
            check('last page is accessible and bounded',"$('list').querySelector('[data-article-id=perf-9999]')!==null&&$('list').querySelectorAll('[data-article-id]').length===100")
            js("$('list').querySelector('[data-article-id=perf-9999]').click()")
            check('offscreen list selection enters bounded GPU slice',"selected==='perf-9999'&&graph.graphData().nodes.some(n=>n.id===selected)&&graph.graphData().nodes.length===800")
            js("renderArticleList(0)")
            js("AtlasRuntime.act({kind:'select_article',id:'perf-9999',revision:AtlasRuntime.state().revision})")
            check('chat can select articles beyond the current page',"selected==='perf-9999'&&articleListPage===99")
            metrics['hover']=js("""(()=>{lockedRoots=[articles[0].id];keywordLocked=true;refreshFocus();const original=activeTrace;let reused=0;const start=performance.now();for(let i=1;i<=20;i++){setHovered(articles[i]);if(activeTrace===original)reused++;}return {elapsed_ms:performance.now()-start,reuses:reused};})()""")
            check('unchanged root tree reused on all 20 hovers',"true" if metrics['hover']['reuses']==20 else "false")
            frame()
            metrics['guide']=js("""(()=>{for(const n of graph.graphData().nodes){n.x=0;n.y=0;n.z=0;}const camera=graph.camera();camera.position.set(0,0,1000);camera.lookAt(0,0,0);camera.updateMatrixWorld();const clone=camera.position.clone;let clones=0;camera.position.clone=function(){clones++;return clone.call(this);};const guide=interaction.guide(graph.graphData().nodes[0].id);camera.position.clone=clone;return {clones,found:!!guide};})()""")
            assert metrics['guide']['found'] and metrics['guide']['clones']==2,metrics['guide']
            check('single-node guide does not project 800 nodes',"true")
            js("clearFocus();$('rootQuery').value='uniqueendmarker';$('rootLimit').value='3'")
            metrics['search']=js("(async()=>{const start=performance.now();await searchRuntimeRoots();return {elapsed_ms:performance.now()-start,root:focusRoot(),scanned:rootSearchState?.scanned_articles};})()")
            check('keyword searches complete data, roots stay in budget',"focusRoot()==='perf-9999'&&articles.length===10000&&graph.graphData().nodes.length===800&&graph.graphData().nodes.some(n=>n.id==='perf-9999')")
            for budget in [100,400,800,1200,2400,800]:
                js(f"$('renderBudget').value='{budget}';$('renderBudget').dispatchEvent(new Event('change'))")
                frame()
                check(f'GPU objects and endpoints bounded at {budget}',f"(()=>{{const d=graph.graphData(),ids=new Set(d.nodes.map(n=>n.id));return !graphFailure&&d.nodes.length==={budget}&&d.links.length<={budget*3}&&d.links.every(e=>ids.has(AtlasView.endpoint(e.source))&&ids.has(AtlasView.endpoint(e.target)));}})()")
            js("setHighlightMode('category');graphChannel='perf';refreshCategory();renderNetwork();refreshFocus()")
            check('10000-member category cannot exceed GPU budget or displace selection',"categoryTrace.nodes.size===10000&&graph.graphData().nodes.length===800&&graph.graphData().nodes.some(n=>n.id===selected)")
            js("showBucket({date:'2026-01-01',articles:articles})")
            check('dense timeline bucket detail is also paged',"$('article').querySelectorAll('.bucket-list > button').length===100")
            js("showArticle(articles[9999]);setHighlightMode('root');rebuild({source_graphs:{google:{articles:perfRows.slice(0,6000),relations:[]},massive:{articles:perfRows.slice(4000),relations:[]}},relation_settings:AtlasRelations.defaults});")
            check('overlapping source results deduplicate without losing data',"articles.length===10000&&graph.graphData().nodes.length===800")
            js("$('separateSources').checked=true;$('separateSources').dispatchEvent(new Event('change'))")
            check('separate sources retain 12000 but render only 800',"articles.length===12000&&graph.graphData().nodes.length===800&&$('list').querySelectorAll('[data-article-id]').length===100")
            js("$('view-google').checked=false;$('view-google').dispatchEvent(new Event('change'))")
            check('source filtering obeys same budgets',"articles.length===6000&&graph.graphData().nodes.length===800&&graph.graphData().nodes.every(n=>n.display_provider==='massive')")
            check('export retains all filtered articles',"savedPayload().source_graphs.massive.articles.length===6000")
            check('no browser errors',"errors.length===0")
            print(json.dumps({'metrics':metrics,'checks':checks}),flush=True)
            Path('/tmp/stocknexus-graph-performance.json').write_text(json.dumps({'metrics':metrics,'checks':checks},indent=2))
            call('Browser.close');ws.close();return 0
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
