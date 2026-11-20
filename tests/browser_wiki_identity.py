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
            checks={}
            def check(name,code):
                checks[name]=js(code);print(json.dumps({'check':name,'passed':checks[name]}),flush=True)
                if not checks[name]:print(js("JSON.stringify({sameNodes:graph.graphData().nodes.every((n,i)=>n===newsBefore.nodes[i]),sameEdges:JSON.stringify(relations)===newsBefore.edges,camera:graph.cameraPosition(),oldCamera:newsBefore.camera,errors})"),flush=True)
                if not checks[name]:print(js("JSON.stringify({width:document.querySelector('.wiki-controls').getBoundingClientRect(),divider:$('wikiResizeLeft').getBoundingClientRect(),saved:localStorage.getItem('stocknexus.wikiLeftWidth'),style:$('wikiPanel').getAttribute('style')})"),flush=True)
                assert checks[name],name
            js("""(()=>{
              rebuild(initialGraph);window.newsBefore={nodes:graph.graphData().nodes.slice(),edges:JSON.stringify(relations),camera:JSON.stringify(graph.cameraPosition())};
              const factory=ForceGraph3D;window.ForceGraph3D=(...args)=>{window.fixtureWikiRenderer=factory(...args);return fixtureWikiRenderer;};window.wikiCalls=[];window.planRelease=null;window.deferPlan=false;
              window.fixtureWiki={instrument:'NASDAQ:TSLA',version:1,versions:[{version:1,created_at:'2026-11-04T00:00:00Z'}],nodes:[{id:'a',kind:'ArticleRevision',title:'Fixture evidence',summary:'Evidence only',url:'https://example.test',status:'source'},{id:'b',kind:'Claim',title:'<img src=x onerror=alert(1)> Claim',scope:'fixture',summary:'待判讀',status:'proposed',citations:[{article_revision_id:'a',field:'title',start:0,end:7,quote:'Fixture'}]}],edges:[{source:{stable_id:'a',kind:'ArticleRevision'},target:{stable_id:'b',kind:'Claim'},relation_type:'SUPPORTS',status:'proposed',rationale:'Fixture',evidence_refs:[]}],total_nodes:2,config:{enabled:false},jobs:[],truncated:false};
              fixtureWiki.coverage={instrument:'NASDAQ:TSLA',scope_total:10,scope_done:2,scope_pending:8,review_done:0,review_total:2,daily_calls:2,daily_limit:20,captured_revisions:10,extracted_revisions:2,storage:'llm_wiki/TSLA/wiki.sqlite3',subscriptions:[],rejected_responses:0,note:'分母為已確認範圍'};
              fixtureWiki.perspectives={categories:{direct:1},theses:[],total_theses:0,note:'模型局部觀點彙整，未以股價驗證'};fixtureWiki.nodes[1].assessment={category:'direct',rationale:'營運線索，未測試股價',status:'unverified'};
              const prior=window.fetch;window.fetch=async(url,options)=>{
                if(!url.startsWith('/api/wiki/'))return prior(url,options);
                wikiCalls.push({url,body:options?.body?JSON.parse(options.body):null});
                let value;
                if(url.endsWith('/models'))value={models:[{id:'gpt-6.1-sol',name:'GPT-6.1-Sol',reasoning:[{reasoningEffort:'low'},{reasoningEffort:'high'}]},{id:'fixture',name:'Fixture model'}],default_model:'gpt-6.1-sol',source:'codex model/list'};
                else if(url.endsWith('/status'))value={instruments:[{instrument:'NASDAQ:TSLA',version:1}],news_databases:[{instrument:'NASDAQ:TSLA',articles:2},{instrument:'NASDAQ:AAPL',articles:3}],writable:true,bridge_ready:true,default_model:'fixture'};
                else if(url.endsWith('/plan')){
                  if(deferPlan)await new Promise(r=>{planRelease=r});
                  const body=JSON.parse(options.body);value={plan_id:'plan',instrument:body.instrument,selected:body.articles.length,pending:1,next_batch:1,reused:0,model:body.model,daily_limit:body.daily_limit,watch_sources:[],note:'Fixture'};
                }
                else if(url.includes('/graph?'))value=fixtureWiki;
                else if(url.endsWith('/apply'))value={status:'saved',resumed:false};
                else if(url.includes('/node?'))value={...fixtureWiki.nodes[1],kind:'Thesis'};
                else if(url.endsWith('/resume'))value={config:fixtureWiki.config,coverage:fixtureWiki.coverage};
                else if(url.endsWith('/jobs'))value={job_id:'job',instrument:'NASDAQ:TSLA'};
                else if(url.includes('/jobs?'))value={jobs:fixtureWiki.jobs,config:fixtureWiki.config,version:1,coverage:fixtureWiki.coverage};
                else if(url.includes('/article?'))value={title:'Fixture source',url:'https://example.test'};
                else if(url.includes('/markdown?'))value={markdown:'# fixture'};
                else throw Error('Unhandled Wiki test URL: '+url);
                return {ok:true,json:async()=>value};
              };
            })()""")
            time.sleep(1.7)
            js("AtlasWiki.show()");time.sleep(.5)
            check('saved Wiki locks the exact stock',"$('wikiSaved').value==='NASDAQ:TSLA'&&$('wikiInstrument').disabled&&$('wikiInstrument').value==='NASDAQ:TSLA'&&$('wikiInstrument').tagName==='SELECT'")
            js("$('wikiInstrument').value='NASDAQ:AAPL';$('wikiInstrument').dispatchEvent(new Event('input'))")
            check('stock tampering cannot change a loaded Wiki',"$('wikiInstrument').value==='NASDAQ:TSLA'&&$('wikiSaved').value==='NASDAQ:TSLA'")
            js("window.switchStart=performance.now();$('wikiSaved').value='';$('wikiSaved').dispatchEvent(new Event('change'))")
            check('new mode responds immediately and clears old graph',"performance.now()-switchStart<2000&&!$('wikiInstrument').disabled&&!$('wikiInstrument').value&&fixtureWikiRenderer.graphData().nodes.length===0&&$('wikiStart').disabled")
            check('new mode lists only nonempty news DB options',"[...$('wikiInstrument').options].map(o=>o.value).join(',')===',NASDAQ:TSLA,NASDAQ:AAPL'")
            js("$('wikiInstrument').value='NASDAQ:AAPL';$('wikiInstrument').dispatchEvent(new Event('input'));window.requestBefore=wikiCalls.length")
            time.sleep(2.2)
            check('new mode polling does not load a nonexistent Wiki',"!wikiCalls.slice(requestBefore).some(c=>c.url.includes('/graph?')||c.url.includes('/jobs?'))")
            js("$('wikiStart').click()");time.sleep(.2)
            check('new Wiki plan uses chosen DB, never the previous stock evidence',"wikiCalls.some(c=>c.url.endsWith('/plan')&&c.body.instrument==='NASDAQ:AAPL'&&c.body.news_db===true&&c.body.search.ticker==='AAPL'&&c.body.articles.length===0)")
            js("$('wikiSaved').value='NASDAQ:TSLA';$('wikiSaved').dispatchEvent(new Event('change'))");time.sleep(.2)
            check('switching back restores binding',"$('wikiInstrument').disabled&&$('wikiInstrument').value==='NASDAQ:TSLA'")
            js("window.savedFetch=fetch;window.releaseOld=null;window.fetch=async(url,init)=>{if(String(url).includes('/graph?'))return new Promise(resolve=>releaseOld=()=>savedFetch(url,init).then(resolve));return savedFetch(url,init)};void AtlasWiki.refresh()")
            time.sleep(.2)
            js("$('wikiSaved').value='';$('wikiSaved').dispatchEvent(new Event('change'));$('wikiInstrument').value='NASDAQ:AAPL';$('wikiInstrument').dispatchEvent(new Event('input'));releaseOld();window.fetch=savedFetch")
            time.sleep(.2)
            check('late old graph cannot overwrite new stock selection',"$('wikiInstrument').value==='NASDAQ:AAPL'&&!$('wikiSaved').value&&fixtureWikiRenderer.graphData().nodes.length===0")
            check('no browser errors',"errors.length===0")
            print(json.dumps({'passed':len(checks),'checks':checks}),flush=True)
            return 0
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
