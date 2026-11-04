"""View-first scheduling and 650ms tooltips with synthetic 5637 news through the HTTP asset fixture.
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
    with tempfile.TemporaryDirectory(prefix='atlas-view-relations-') as folder:
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
                if not checks[name]:
                    print(js("JSON.stringify({calls:previewCalls.length,before:window.beforeRestore,state:viewRelationState,budget:renderBudget,savedBudget:window.savedFixture?.view.render_budget,selected,roots:lockedRoots,status:$('saveStatus').textContent,seed:!!restoredRelationSeed,restored:restoredRelationViews.length,errors})"),flush=True)
                assert checks[name],name
            def frame():
                js("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))")
            check('real WebGL ready',"!!graph&&!graphFailure&&renderBudget===800")
            js("""(()=>{
              window.previewCalls=[];window.delayPreview=20;window.failPreview=false;
              const prior=window.fetch;
              window.fetch=async(url,options)=>{
                if(url!=='/api/graph/preview')return prior(url,options);
                const body=JSON.parse(options.body);previewCalls.push(body);
                await new Promise(resolve=>setTimeout(resolve,delayPreview));
                if(failPreview)return {ok:false,status:503};
                const source_graphs={};let pairs=0;
                for(const [p,g] of Object.entries(body.source_graphs)){
                  pairs+=g.articles.length*(g.articles.length-1)/2;
                  source_graphs[p]={relations:g.articles.slice(1,body.stage==='strict'?3:5).map((a,i)=>({id:g.articles[0].id+':'+a.id,source:g.articles[0].id,target:a.id,weight:.9,type:'shared_entity',evidence:[]}))};
                }
                const events=[{type:'progress',stage:body.stage,pairs_checked:pairs,group:'fixture',nodes_checked:800,nodes_total:800},{type:'result',stage:body.stage,pairs_checked:pairs,source_graphs,cross_relations:[],relation_settings:body.relation_settings},{type:'done'}];
                return new Response(events.map(e=>JSON.stringify(e)).join('\\n')+'\\n',{headers:{'Content-Type':'application/x-ndjson'}});
              };
              const seed=initialGraph.source_graphs.google.articles[0];
              window.viewRows=Array.from({length:5637},(_,i)=>({...seed,id:'view-'+String(i).padStart(5,'0'),title:'Fixture '+i,published_at:'2026-01-01T00:00:00Z'}));
              relationUI.restore(AtlasRelations.unified);
              pendingSearchMeta={query:'fixture',sources:{}};
              acceptSearchGraph({source_graphs:{google:{articles:viewRows,relations:[],total_articles:5637}},relation_scope:'view',relations_pending:true,relation_settings:AtlasRelations.unified});
            })()""")
            def settle():
                js("new Promise((resolve,reject)=>{let n=0;const t=setInterval(()=>{if(viewRelationState.phase==='ready'){clearInterval(t);resolve(true)}else if(++n>120){clearInterval(t);reject(Error(JSON.stringify(viewRelationState)))}},50)})")
            settle()
            check('first strict then adaptive; only 800 of 5637 sent',"previewCalls.length===2&&previewCalls[0].stage==='strict'&&previewCalls[1].stage==='complete'&&previewCalls.every(c=>c.source_graphs.google.articles.length===800)&&articles.length===5637")
            check('split counts and partial snapshot',"$('activityNodesValue').textContent==='800 / 5637'&&$('activityCalculationValue').textContent.includes('319600')&&savedPayload().view.relation_scope==='view'&&!savedPayload().view.relations_pending")
            js("window.cameraBefore=JSON.stringify(graph.cameraPosition());window.oldNode=graph.graphData().nodes[0];$('renderBudget').value='2400';$('renderBudget').dispatchEvent(new Event('change'))")
            settle()
            check('2400 cap and stable camera/node identity',"previewCalls.slice(-2).every(c=>c.source_graphs.google.articles.length===2400)&&graph.graphData().nodes.length===2400&&JSON.stringify(graph.cameraPosition())===cameraBefore&&graph.graphData().nodes.includes(oldNode)")
            js("window.beforeReuse=previewCalls.length;$('renderBudget').value='800';$('renderBudget').dispatchEvent(new Event('change'))")
            settle()
            check('return to completed scope performs zero requests',"previewCalls.length===beforeReuse&&viewRelationState.cache_hit&&graph.graphData().nodes.length===800")
            js("$('renderBudget').value='2400';$('renderBudget').dispatchEvent(new Event('change'))")
            settle()
            check('larger completed scope also reused',"previewCalls.length===beforeReuse&&graph.graphData().nodes.length===2400")
            js("showArticle(articles.find(a=>a.id==='view-05636'))")
            settle()
            check('older offscreen selection enters computation',"previewCalls.at(-1).source_graphs.google.articles.some(a=>a.id==='view-05636')&&selected==='view-05636'&&lockedRoots.includes(selected)")
            js("window.beforeCalls=previewCalls.length;document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));$('renderBudget').value='400';$('renderBudget').dispatchEvent(new Event('change'))")
            time.sleep(.4)
            check('interaction holds result and adaptive admission',"previewCalls.length===beforeCalls+1&&viewRelationState.phase==='render-wait'")
            js("document.dispatchEvent(new PointerEvent('pointerup',{bubbles:true}))")
            settle()
            check('idle resumes adaptive fill',"previewCalls.length===beforeCalls+2&&graph.graphData().nodes.length===400")
            js("delayPreview=150;$('renderBudget').value='100';$('renderBudget').dispatchEvent(new Event('change'))")
            time.sleep(.07)
            js("$('renderBudget').value='200';$('renderBudget').dispatchEvent(new Event('change'))")
            settle()
            check('stale request cannot overwrite latest scope',"graph.graphData().nodes.length===200&&previewCalls.at(-1).source_graphs.google.articles.length===200")
            js("failPreview=true;$('renderBudget').value='1200';$('renderBudget').dispatchEvent(new Event('change'))")
            js("new Promise((resolve,reject)=>{let n=0;const t=setInterval(()=>{if(viewRelationState.phase==='error'){clearInterval(t);resolve(true)}else if(++n>120){clearInterval(t);reject(Error('Expected preview error'))}},50)})")
            check('failure explicit and retry available',"viewRelationState.phase==='error'&&!$('viewRelationsRetry').hidden&&articles.length===5637")
            js("failPreview=false;$('viewRelationsRetry').click()")
            settle()
            js("""(()=>{
              window.savedFixture=savedPayload();window.beforeRestore=previewCalls.length;
              const previous=window.fetch;
              window.fetch=(url,options)=>url==='/api/snapshots/cache-fixture'?Promise.resolve({ok:true,json:async()=>({...savedFixture,name:'Cache fixture',created_at:'2026-11-04T00:00:00Z'})}):previous(url,options);
            })()""")
            js("restoreSnapshot('cache-fixture')")
            settle()
            time.sleep(.15)
            check('complete snapshot restores without requests',"previewCalls.length===beforeRestore&&viewRelationState.cache_hit&&renderBudget===savedFixture.view.render_budget&&selected===savedFixture.view.selected_id")
            js("window.beforeSavedSwitch=previewCalls.length;$('renderBudget').value='200';$('renderBudget').dispatchEvent(new Event('change'))")
            settle()
            check('snapshot retains earlier completed combinations',"previewCalls.length===beforeSavedSwitch&&viewRelationState.cache_hit&&graph.graphData().nodes.length===200")
            # Hiding all sources clears selection by design; establish an unselected scope first.
            js("selected=null;clearFocus();renderNetwork()")
            settle()
            js("window.beforeToggle=previewCalls.length;$('view-google').checked=false;$('view-google').dispatchEvent(new Event('change'));$('view-google').checked=true;$('view-google').dispatchEvent(new Event('change'))")
            settle()
            check('source off and on reuses completed view',"previewCalls.length===beforeToggle&&viewRelationState.cache_hit")
            js("window.beforeNewSearch=previewCalls.length;pendingSearchMeta={query:'second search',sources:{}};handleEvent({type:'cache',graph:{source_graphs:{google:{articles:viewRows,relations:[],total_articles:5637}},relations_pending:true,relation_settings:AtlasRelations.unified}})")
            settle()
            check('new search after snapshot restarts relation work',"!restoringRelations&&previewCalls.length===beforeNewSearch+2&&currentView.relations.length>0&&viewRelationState.phase==='ready'")
            js("window.beforePartialRestore=previewCalls.length;savedFixture.view.relations_pending=true;savedFixture.view.relation_cache_version=0;savedFixture.view.relation_views=[];for(const g of Object.values(savedFixture.source_graphs))g.relations=[];savedFixture.cross_relations=[]")
            js("restoreSnapshot('cache-fixture')")
            settle()
            check('unfinished zero-edge snapshot resumes computation',"!restoringRelations&&previewCalls.length===beforePartialRestore+2&&currentView.relations.length>0&&viewRelationState.phase==='ready'")
            for label in ['Nodes','Calculation','Edges','State']:
                js("document.activeElement?.blur();$('activityCounters').dispatchEvent(new PointerEvent('pointerleave'));$('activity%sLabel').dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:200,clientY:150}))" % label)
                check(label+' tooltip not immediate',"$('activityHelp').hidden")
                time.sleep(.35)
                js("$('activity%sLabel').dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:201,clientY:150}))" % label)
                time.sleep(.35)
                check(label+' motion resets dwell',"$('activityHelp').hidden")
                time.sleep(.4)
                check(label+' tooltip after 650ms stillness',"!$('activityHelp').hidden&&$('activityHelp').textContent.length>20")
                js("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
                check(label+' escape hides',"$('activityHelp').hidden")
            js("$('activityCalculationLabel').focus()")
            check('keyboard help and describedby',"!$('activityHelp').hidden&&$('activityCalculationLabel').getAttribute('aria-describedby')==='activityHelp'")
            check('no browser errors',"errors.length===0")
            import base64
            Path('/tmp/stocknexus-view-relations.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            # Check responsive counters and tooltip bounds without changing user browser state.
            call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            js("$('activityCalculationLabel').blur();$('activityCalculationLabel').focus()")
            check('mobile tooltip fits viewport',"(()=>{const r=$('activityHelp').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.bottom<=innerHeight})()")
            print(json.dumps({'checks':checks,'passed':len(checks)}),flush=True)
            return 0
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
