"""Wiki switching and preview authorization with synthetic evidence through the HTTP asset fixture.
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
            checks={}
            def check(name,code):
                checks[name]=js(code);print(json.dumps({'check':name,'passed':checks[name]}),flush=True)
                if not checks[name]:print(js("JSON.stringify({sameNodes:graph.graphData().nodes.every((n,i)=>n===newsBefore.nodes[i]),sameEdges:JSON.stringify(relations)===newsBefore.edges,camera:graph.cameraPosition(),oldCamera:newsBefore.camera,errors})"),flush=True)
                assert checks[name],name
            js("""(()=>{
              rebuild(initialGraph);window.newsBefore={nodes:graph.graphData().nodes.slice(),edges:JSON.stringify(relations),camera:JSON.stringify(graph.cameraPosition())};
              const factory=ForceGraph3D;window.ForceGraph3D=(...args)=>{window.fixtureWikiRenderer=factory(...args);return fixtureWikiRenderer;};window.wikiCalls=[];window.planRelease=null;window.deferPlan=false;
              window.fixtureWiki={instrument:'NASDAQ:TSLA',version:1,versions:[{version:1,created_at:'2026-11-04T00:00:00Z'}],nodes:[{id:'a',kind:'ArticleRevision',title:'Fixture evidence',summary:'Evidence only',url:'https://example.test',status:'source'},{id:'b',kind:'Claim',title:'<img src=x onerror=alert(1)> Claim',scope:'fixture',summary:'待判讀',status:'proposed',citations:[{article_revision_id:'a',field:'title',start:0,end:7,quote:'Fixture'}]}],edges:[{source:{stable_id:'a',kind:'ArticleRevision'},target:{stable_id:'b',kind:'Claim'},relation_type:'SUPPORTS',status:'proposed',rationale:'Fixture',evidence_refs:[]}],total_nodes:2,config:{enabled:false},jobs:[],truncated:false};
              const prior=window.fetch;window.fetch=async(url,options)=>{
                if(!url.startsWith('/api/wiki/'))return prior(url,options);
                wikiCalls.push({url,body:options?.body?JSON.parse(options.body):null});
                let value;
                if(url.endsWith('/models'))value={models:[{id:'gpt-6.1-sol',name:'GPT-6.1-Sol'},{id:'fixture',name:'Fixture model'}],default_model:'gpt-6.1-sol',source:'codex model/list'};
                else if(url.endsWith('/status'))value={instruments:[{instrument:'NASDAQ:TSLA',version:1}],writable:true,bridge_ready:true,default_model:'fixture'};
                else if(url.endsWith('/plan')){
                  if(deferPlan)await new Promise(r=>{planRelease=r});
                  const body=JSON.parse(options.body);value={plan_id:'plan',instrument:body.instrument,selected:body.articles.length,pending:1,next_batch:1,reused:0,model:body.model,daily_limit:body.daily_limit,watch_sources:[],note:'Fixture'};
                }
                else if(url.includes('/graph?'))value=fixtureWiki;
                else if(url.endsWith('/jobs'))value={job_id:'job',instrument:'NASDAQ:TSLA'};
                else if(url.includes('/jobs?'))value={jobs:[],config:{enabled:false},version:1};
                else if(url.includes('/article?'))value={title:'Fixture source',url:'https://example.test'};
                else if(url.includes('/markdown?'))value={markdown:'# fixture'};
                else throw Error('Unhandled Wiki test URL: '+url);
                return {ok:true,json:async()=>value};
              };
            })()""")
            time.sleep(1.7) # Let the initial News Graph fit/first-tick camera settle.
            js("newsBefore.camera=JSON.stringify(graph.cameraPosition());AtlasWiki.show()")
            check('Wiki opens independently with selected news',"!$('wikiPanel').hidden&&$('wikiSelection').textContent.includes('全局模式')&&$('wikiModel').value==='gpt-6.1-sol'&&$('wikiModel').tagName==='SELECT'")
            check('recent month preset and date slider exist',"$('wikiRange').value==='month'&&$('wikiStartDate').value<$('wikiEndDate').value&&$('wikiRangeStart').type==='range'")
            js("$('wikiOperation').value='review';$('wikiOperation').dispatchEvent(new Event('input'))")
            check('review cannot silently enable continuous spending',"$('wikiContinuous').disabled&&!$('wikiContinuous').checked")
            js("$('wikiOperation').value='update';$('wikiOperation').dispatchEvent(new Event('input'))")
            js("$('wikiRange').value='all';$('wikiRange').dispatchEvent(new Event('change'));$('wikiInstrument').value='NASDAQ:TSLA';$('wikiInstrument').dispatchEvent(new Event('input'));window.deferPlan=true;$('wikiPreview').click()")
            time.sleep(.15)
            js("$('wikiDaily').value='2';$('wikiDaily').dispatchEvent(new Event('input'));planRelease()")
            time.sleep(.15)
            check('late preview cannot revive stale cost authorization',"$('wikiStart').hidden")
            js("window.deferPlan=false;$('wikiPreview').click()")
            time.sleep(.15)
            check('global scope and chosen dates submitted',"wikiCalls.filter(c=>c.url.endsWith('/plan')).at(-1).body.scope==='global'&&wikiCalls.filter(c=>c.url.endsWith('/plan')).at(-1).body.date_range===null")
            check('explicit preview before any model job',"!$('wikiStart').hidden&&!wikiCalls.some(c=>c.url==='/api/wiki/jobs')&&$('wikiStatus').textContent.includes('NASDAQ:TSLA')")
            js("$('wikiStart').click()")
            time.sleep(.4)
            check('confirmed job renders separate Wiki WebGL canvas',"wikiCalls.some(c=>c.url==='/api/wiki/jobs')&&!!$('wikiCanvas').querySelector('canvas')&&$('wikiCounts').textContent.includes('節點 2 / 2')")
            check('news nodes edges camera preserved',"graph.graphData().nodes.every((n,i)=>n===newsBefore.nodes[i])&&JSON.stringify(relations)===newsBefore.edges&&JSON.stringify(graph.cameraPosition())===newsBefore.camera")
            js("fixtureWikiRenderer.onNodeClick()(fixtureWikiRenderer.graphData().nodes.find(n=>n.kind==='Claim'))")
            check('citation and untrusted title rendered as text',"$('wikiDetail').textContent.includes('Fixture')&&!$('wikiDetail').querySelector('img')&&$('wikiDetail').textContent.includes('<img')")
            js("$('wikiDetail').querySelector('button').click()")
            time.sleep(.1)
            check('frozen source retrieved for same instrument',"wikiCalls.some(c=>c.url.includes('article?instrument=NASDAQ%3ATSLA'))&&$('wikiDetail').querySelector('a')?.href==='https://example.test/'")
            js("$('wikiKind').value='Claim';$('wikiKind').dispatchEvent(new Event('change'))")
            check('Wiki node filter also restricts rendered edges',"$('wikiCounts').textContent.includes('節點 1 / 2')&&$('wikiCounts').textContent.includes('連線 0')")
            js("$('wikiKind').value='';$('wikiKind').dispatchEvent(new Event('change'));$('wikiVersion').value='1';$('wikiVersion').dispatchEvent(new Event('change'))")
            time.sleep(.15)
            check('version selection reads frozen graph',"wikiCalls.some(c=>c.url.includes('graph?')&&c.url.includes('version=1'))")
            import base64
            Path('/tmp/stocknexus-wiki-desktop.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            time.sleep(.15)
            check('mobile controls fit viewport',"$('wikiPanel').scrollWidth<=$('wikiPanel').clientWidth+1&&$('wikiPreview').getBoundingClientRect().right<=innerWidth")
            Path('/tmp/stocknexus-wiki-mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            js("$('wikiInstrument').value='NASDAQ:AAPL';$('wikiInstrument').dispatchEvent(new Event('input'));window.callsBefore=wikiCalls.length;$('wikiExport').click()")
            check('stock edit clears old graph and prevents mismatched export',"$('wikiCounts').textContent==='尚未載入此股票 Wiki'&&wikiCalls.length===callsBefore&&$('wikiStart').hidden")
            js("$('wikiBack').click()")
            check('return restores original news surface',"$('wikiPanel').hidden&&JSON.stringify(relations)===newsBefore.edges&&graph.graphData().nodes.every((n,i)=>n===newsBefore.nodes[i])")
            check('no browser errors',"errors.length===0")
            print(json.dumps({'passed':len(checks),'checks':checks}),flush=True)
            return 0
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
