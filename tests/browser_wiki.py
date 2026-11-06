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
                else if(url.endsWith('/status'))value={instruments:[{instrument:'NASDAQ:TSLA',version:1}],writable:true,bridge_ready:true,default_model:'fixture'};
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
            time.sleep(1.7) # Let the initial News Graph fit/first-tick camera settle.
            js("newsBefore.camera=JSON.stringify(graph.cameraPosition());AtlasWiki.show()")
            check('Wiki opens independently with selected news',"!$('wikiPanel').hidden&&$('wikiSelection').textContent.includes('全局模式')&&$('wikiModel').value==='gpt-6.1-sol|low'&&$('wikiModel').tagName==='SELECT'")
            check('saved Wiki date mode and date slider restored',"$('wikiRange').value==='all'&&$('wikiStartDate').value<$('wikiEndDate').value&&$('wikiRangeStart').type==='range'")
            js("$('wikiOperation').value='review';$('wikiOperation').dispatchEvent(new Event('input'))")
            check('review cannot silently enable continuous spending',"$('wikiContinuous').disabled&&!$('wikiContinuous').checked")
            js("$('wikiOperation').value='update';$('wikiOperation').dispatchEvent(new Event('input'))")
            js("$('wikiRange').value='all';$('wikiRange').dispatchEvent(new Event('change'));$('wikiInstrument').value='NASDAQ:TSLA';$('wikiInstrument').dispatchEvent(new Event('input'));window.deferPlan=true;")
            time.sleep(.7)
            js("$('wikiModel').dispatchEvent(new Event('input'));planRelease()")
            time.sleep(.15)
            check('late preview cannot revive stale cost authorization',"$('wikiStart').disabled")
            js("window.deferPlan=false;$('wikiModel').dispatchEvent(new Event('input'))")
            time.sleep(.7)
            check('global scope and chosen dates submitted',"wikiCalls.filter(c=>c.url.endsWith('/plan')).at(-1).body.scope==='global'&&wikiCalls.filter(c=>c.url.endsWith('/plan')).at(-1).body.date_range===null")
            check('automatic preview never starts model work',"!$('wikiStart').disabled&&!wikiCalls.some(c=>c.url==='/api/wiki/jobs')&&$('wikiStatus').textContent.includes('NASDAQ:TSLA')")
            js("$('wikiStart').click()")
            time.sleep(.4)
            check('confirmed job renders separate Wiki WebGL canvas',"wikiCalls.some(c=>c.url==='/api/wiki/jobs')&&!!$('wikiCanvas').querySelector('canvas')&&$('wikiCounts').textContent.includes('節點 2 / 2')")
            check('coverage progress and stock storage visible',"$('wikiCoverage').querySelectorAll('progress').length===1&&$('wikiCoverage').textContent.includes('2/10')&&$('wikiCoverage').textContent.includes('llm_wiki/TSLA')&&!$('wikiResume').hidden")
            js("$('wikiResume').click()");time.sleep(.2)
            check('one click resume uses saved instrument only',"wikiCalls.some(c=>c.url.endsWith('/resume')&&c.body.instrument==='NASDAQ:TSLA'&&Object.keys(c.body).length===1)")
            js("fixtureWiki.jobs=[{id:'running-fixture',status:'running',done:1,created_at:new Date().toISOString(),payload:{model:'fixture',revisions:['a','b'],stage:'compiling'},usage:{}}];await AtlasWiki.refresh()")
            check('real running state drives animation and current batch',"$('wikiLive').dataset.state==='running'&&$('wikiResume').classList.contains('wiki-working')&&$('wikiLive').textContent.includes('本次工作 1/2')")
            js("fixtureWiki.jobs=[{id:'empty-fixture',status:'completed',done:0,created_at:new Date().toISOString(),payload:{model:'fixture',revisions:[]}}];fixtureWiki.coverage.daily_calls=20;await AtlasWiki.refresh()")
            check('old daily quota does not block; idle and empty jobs stay quiet',"$('wikiLive').dataset.state==='idle'&&!$('wikiResume').classList.contains('wiki-working')&&!$('wikiJobs')")
            js("fixtureWiki.jobs=[];fixtureWiki.coverage.daily_calls=2;await AtlasWiki.refresh();window.oldWikiWidth=document.querySelector('.wiki-controls').getBoundingClientRect().width")
            drag=js("(()=>{const r=$('wikiResizeLeft').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()")
            call('Input.dispatchMouseEvent',{'type':'mouseMoved',**drag})
            call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**drag})
            call('Input.dispatchMouseEvent',{'type':'mouseMoved','button':'left','buttons':1,'x':drag['x']+90,'y':drag['y']})
            call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,'x':drag['x']+90,'y':drag['y']})
            time.sleep(.2)
            check('left boundary drag widens panel and persists',"document.querySelector('.wiki-controls').getBoundingClientRect().width>oldWikiWidth+70&&Number(localStorage.getItem('stocknexus.wikiLeftWidth'))>oldWikiWidth")
            check('news nodes edges camera preserved',"graph.graphData().nodes.every((n,i)=>n===newsBefore.nodes[i])&&JSON.stringify(relations)===newsBefore.edges&&JSON.stringify(graph.cameraPosition())===newsBefore.camera")
            js("fixtureWikiRenderer.onNodeClick()(fixtureWikiRenderer.graphData().nodes.find(n=>n.kind==='Claim'))")
            check('citation and untrusted title rendered as text',"$('wikiDetail').textContent.includes('Fixture')&&!$('wikiDetail').querySelector('img')&&$('wikiDetail').textContent.includes('<img')")
            js("Array.from($('wikiDetail').querySelectorAll('button')).find(b=>b.textContent==='查看引用來源').click()")
            time.sleep(.1)
            check('frozen source retrieved for same instrument',"wikiCalls.some(c=>c.url.includes('article?instrument=NASDAQ%3ATSLA'))&&$('wikiDetail').querySelector('a')?.href==='https://example.test/'")
            check('local classification and rationale disclosed',"$('wikiDetail').textContent.includes('營運線索，未測試股價')&&$('wikiInsights').textContent.includes('直接營運')")
            js("$('wikiKind').value='Claim';$('wikiKind').dispatchEvent(new Event('change'))")
            check('Wiki node filter also restricts rendered edges',"$('wikiCounts').textContent.includes('節點 1 / 2')&&$('wikiCounts').textContent.includes('連線 0')")
            js("$('wikiKind').value='';$('wikiKind').dispatchEvent(new Event('change'));$('wikiVersion').value='1';$('wikiVersion').dispatchEvent(new Event('change'))")
            time.sleep(.15)
            check('version selection reads frozen graph',"wikiCalls.some(c=>c.url.includes('graph?')&&c.url.includes('version=1'))")
            import base64
            Path('/tmp/stocknexus-wiki-desktop.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            time.sleep(.15)
            check('mobile controls fit viewport',"$('wikiPanel').scrollWidth<=$('wikiPanel').clientWidth+1&&$('wikiStart').getBoundingClientRect().right<=innerWidth")
            Path('/tmp/stocknexus-wiki-mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
            js("AtlasI18n.setLanguage('en')");time.sleep(.2)
            check('Wiki translations use complete English labels',"$('wikiBack').textContent==='← News graph'&&$('wikiStart').textContent==='Confirm and start'&&$('wikiOperation').options[0].textContent==='Add missing evidence and revisit dependents'&&(!$('wikiSelectedCoverage').textContent||!$('wikiSelectedCoverage').textContent.includes('所選'))")
            js("$('relationOpen').click()")
            check('Wiki header opens Wiki settings',"$('wikiSettings').open&&$('wikiSettingsTitle').textContent==='Wiki settings'&&$('wikiLanguages').value==='both'")
            js("$('wikiStrategy').value='fusion';$('wikiStrategy').dispatchEvent(new Event('input'));$('wikiSettingsClose').click()")
            check('method explanation and model reasoning exposed',"$('wikiStrategyNote').textContent.includes('different sources')&&[...$('wikiModel').options].some(o=>o.value==='gpt-6.1-sol|high')")
            js("$('wikiRange').value='custom';$('wikiStartDate').value='2026-01-01';$('wikiEndDate').value='2026-01-31';$('wikiStartDate').dispatchEvent(new Event('input'))");time.sleep(.4)
            check('time interval combines with selected version',"wikiCalls.some(c=>c.url.includes('version=1')&&c.url.includes('start=2026-01-01')&&c.url.includes('end=2026-01-31'))")
            js("$('wikiStartDate').value='2026-01-01';$('wikiEndDate').value='2026-01-31';$('wikiStartDate').dispatchEvent(new Event('input'));fixtureWiki.timeline=[{date:'2026-01-01',categories:{direct:2,low:1}},{date:'2026-01-03',categories:{indirect:1}}];fixtureWiki.changes=[{version:1,model:'fixture',created_at:'2026-01-01T00:00:00Z',added:2,relations:1,updates:0,titles:['Example viewpoint']}];AtlasWiki.refresh()");time.sleep(.2)
            check('live viewpoint chart and version changes',"$('wikiTimeline').querySelectorAll('rect').length===3&&$('wikiVersionInfo').textContent.includes('Example viewpoint')")
            js("fixtureWiki.perspectives.index=[{id:'b',title:'Revenue view',date:'2026-01-01',category:'direct',topic:'revenue'},{id:'c',title:'Operations view',date:'2026-01-03',category:'indirect',topic:'operations'},{id:'d',title:'Low relevance',date:'2026-01-03',category:'low',topic:'other'}];AtlasWiki.refresh()");time.sleep(.2)
            check('category tree starts collapsed and does not dump viewpoints',"$('wikiInsights').querySelectorAll('.wiki-category').length===4&&$('wikiInsights').querySelectorAll('.wiki-viewpoint').length===0")
            js("$('wikiInsights').open=true;$('wikiInsights').querySelector('.wiki-category').open=true");time.sleep(.1)
            check('category reveals topic branches',"$('wikiInsights').querySelectorAll('.wiki-topic').length===1&&$('wikiInsights').querySelectorAll('.wiki-viewpoint').length===0")
            js("$('wikiInsights').querySelector('.wiki-topic').open=true");time.sleep(.1)
            check('topic reveals individual viewpoints',"$('wikiInsights').querySelectorAll('.wiki-viewpoint').length===1")
            js("$('wikiTimeline').querySelector('rect[data-category=direct]').dispatchEvent(new MouseEvent('click',{bubbles:true}))")
            check('bar click shows matching date and category on right',"$('wikiDetail').textContent.includes('Direct operating')&&$('wikiDetail').textContent.includes('Revenue view')&&!$('wikiDetail').textContent.includes('Operations view')")
            js("$('wikiDetail').querySelector('.wiki-viewpoint').click()");time.sleep(.1)
            check('right list opens exact version node',"wikiCalls.some(c=>c.url.includes('/node?')&&c.url.includes('version=1')&&c.url.includes('id=b'))")
            js("window.chartBefore=Number($('wikiTimeline').dataset.end)-Number($('wikiTimeline').dataset.start);const svg=$('wikiTimeline').querySelector('svg'),r=svg.getBoundingClientRect();svg.dispatchEvent(new WheelEvent('wheel',{deltaY:-100,clientX:r.left+r.width/2,cancelable:true}));")
            check('wheel zoom reduces viewport inside sidebar bounds',"Number($('wikiTimeline').dataset.end)-Number($('wikiTimeline').dataset.start)<chartBefore&&Number($('wikiTimeline').dataset.start)>=Number($('wikiRangeStart').value)&&Number($('wikiTimeline').dataset.end)<=Number($('wikiRangeEnd').value)")
            js("const svg2=$('wikiTimeline').querySelector('svg');svg2.dispatchEvent(new PointerEvent('pointerdown',{pointerId:9,button:0,clientX:400}));window.dispatchEvent(new PointerEvent('pointermove',{pointerId:9,clientX:600}));window.dispatchEvent(new PointerEvent('pointerup',{pointerId:9}));")
            check('drag pan remains clamped to selected interval',"Number($('wikiTimeline').dataset.start)>=Number($('wikiRangeStart').value)&&Number($('wikiTimeline').dataset.end)<=Number($('wikiRangeEnd').value)")
            js("$('wikiRangeStart').value=Date.parse('2026-01-03T00:00:00Z')/86400000;$('wikiRangeStart').dispatchEvent(new Event('input'))")
            check('sidebar interval resets chart and excludes older viewpoints',"Number($('wikiTimeline').dataset.start)===Number($('wikiRangeStart').value)&&!$('wikiTimeline').querySelector('rect[data-category=direct]')&&$('wikiInsights').querySelector('.wiki-category').textContent.includes('0')")
            js("$('relationOpen').click();$('wikiStrategy').value='root';$('wikiStrategy').dispatchEvent(new Event('input'))")
            check('root disables count and changed settings expose Apply',"$('wikiEvidenceSize').disabled&&!$('wikiApply').hidden&&[...$('wikiEvidenceSize').options].map(o=>o.value).join(',')==='5,10,15,20'")
            js("$('wikiStrategy').value='fusion';$('wikiStrategy').dispatchEvent(new Event('input'));$('wikiEvidenceSize').value='20';$('wikiEvidenceSize').dispatchEvent(new Event('input'));$('wikiApply').click()");time.sleep(.2)
            check('Apply submits new grouping and size without separate start',"wikiCalls.some(c=>c.url.endsWith('/apply')&&c.body.strategy==='fusion'&&c.body.evidence_size===20)&&!$('wikiSettings').open")
            js("AtlasI18n.setLanguage('zh-Hant')");time.sleep(.2)
            check('language round trip restores Chinese without partial words',"$('wikiOperation').options[0].textContent==='補新證據並檢視相依觀點'&&$('wikiBack').textContent==='← 新聞圖譜'")
            js("$('wikiInstrument').value='NASDAQ:AAPL';$('wikiInstrument').dispatchEvent(new Event('input'));window.callsBefore=wikiCalls.length;$('wikiExport').click()")
            check('stock edit clears old graph and prevents mismatched export',"$('wikiCounts').textContent==='尚未載入此股票 Wiki'&&wikiCalls.length===callsBefore&&$('wikiStart').disabled")
            js("$('wikiBack').click()")
            check('return restores original news surface',"$('wikiPanel').hidden&&JSON.stringify(relations)===newsBefore.edges&&graph.graphData().nodes.every((n,i)=>n===newsBefore.nodes[i])")
            js("exportMeta.ticker='TSLA';lockedRoots=[focusView.articles[0].id];refreshFocus();window.selectedStar=AtlasWikiContext.selection('global').graph_selection")
            check('Graph selection copies the exact clicked star members',"selectedStar.trees.length===1&&selectedStar.trees[0].root_id===lockedRoots[0]&&selectedStar.trees[0].articles.length===activeTrace.trees[0].nodes.size&&selectedStar.trees[0].articles.every(a=>[...activeTrace.trees[0].nodes.keys()].some(id=>id.split('::').at(-1)===a.id))")
            js("$('wikiModel').value='gpt-6.1-sol|high';$('wikiModel').dispatchEvent(new Event('input'));AtlasWiki.show()")
            time.sleep(.3)
            js("$('wikiModel').value='gpt-6.1-sol|high';$('wikiModel').dispatchEvent(new Event('input'));$('wikiBack').click();AtlasWiki.show()")
            time.sleep(.3)
            check('model survives News Wiki round trip',"$('wikiModel').value==='gpt-6.1-sol|high'")
            check('Wiki has independent chat context',"!!$('wikichatTab')&&AtlasWiki.runtime.state().surface==='wiki'&&AtlasRuntime.state().surface!=='wiki'")
            check('only sidebar exposes dates',"$('wikiViewStart').type==='hidden'&&$('wikiViewEnd').type==='hidden'")
            check('required identifier comes before keywords',"$('ticker').required&&!!($('ticker').compareDocumentPosition($('query'))&Node.DOCUMENT_POSITION_FOLLOWING)")
            js("$('ticker').value='NASDAQ:GOOGL';$('ticker').dispatchEvent(new Event('change'))")
            check('ticker seeds editable keyword',"$('query').value.split(',')[0]==='GOOGL'")
            js("$('wikiSaved').value='NASDAQ:TSLA';$('wikiSaved').dispatchEvent(new Event('change'))");time.sleep(.2)
            js("lockedRoots=[];refreshFocus();window.fullUniverse=AtlasWikiContext.selection('global').graph_universe;$('relationOpen').click();$('wikiStrategy').value='root';$('wikiStrategy').dispatchEvent(new Event('input'))")
            check('Graph mode needs no clicked galaxy',"!AtlasWikiContext.selection('global').graph_selection.trees.length&&fullUniverse.articles.length>0")
            check('same-stock full universe enables Graph Apply',"!$('wikiApply').disabled&&$('wikiEvidenceSize').disabled")
            js("$('wikiApply').click()");time.sleep(.2)
            check('Graph Apply sends complete universe without a clicked root',"wikiCalls.some(c=>c.url.endsWith('/apply')&&c.body.strategy==='root'&&JSON.stringify(c.body.graph_universe)===JSON.stringify(fullUniverse)&&!c.body.graph_selection)")
            js("fixtureWiki.nodes=[...fixtureWiki.nodes.slice(0,2),{id:'c',kind:'ArticleRevision',title:'Related article',citations:[]},{id:'d',kind:'Claim',title:'Related interpretation',citations:[]},{id:'e',kind:'Claim',title:'Unrelated',citations:[]}];fixtureWiki.edges=[fixtureWiki.edges[0],{id:'related',source:{stable_id:'a'},target:{stable_id:'c'},relation_type:'RELATED_TO',rationale:'Shared event',evidence_refs:[]},{id:'support-c',source:{stable_id:'c'},target:{stable_id:'d'},relation_type:'SUPPORTS',rationale:'Source quote',evidence_refs:[]}];$('wikiAssessment').value='';await AtlasWiki.refresh()");time.sleep(.2)
            js("fixtureWikiRenderer.onNodeClick()(fixtureWikiRenderer.graphData().nodes.find(n=>n.id==='a'))")
            check('click highlights connected galaxy across article revisions',"AtlasWiki.runtime.state().scope_kind==='galaxy'&&AtlasWiki.runtime.state().scope_ids.includes('d')&&!AtlasWiki.runtime.state().scope_ids.includes('e')&&fixtureWikiRenderer.graphData().nodes.length===5&&fixtureWikiRenderer.graphData().nodes.find(n=>n.id==='e').wikiDim")
            check('missing identifier blocks a new search',"(()=>{const value=$('ticker').value;$('ticker').value='';const valid=$('ticker').checkValidity();$('ticker').value=value;return !valid;})()")
            js("fixtureWiki.jobs=[{id:'fixture',status:'running',done:0,usage:{},payload:{strategy:'root',revisions:['a'],model:'fixture',stage:'compiling',group_info:{group:1,groups:2,targets:1}}}];await AtlasWiki.refresh();window.workerIcon=$('wikiLive').querySelector('.wiki-worker');window.pickAnimation=workerIcon.querySelector('.wiki-scan').getAnimations()[0]")
            time.sleep(.1)
            js("await AtlasWiki.refresh()")
            check('data scan and signal persist across status refresh',"$('wikiLive').querySelector('.wiki-worker')===workerIcon&&workerIcon.querySelector('.wiki-signal')!==null&&workerIcon.querySelector('use').getAttribute('href')==='/knowledge-mining.svg#base'&&workerIcon.querySelector('.wiki-scan').getAnimations()[0]===pickAnimation")
            Path('/tmp/wiki-mining.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
            check('reduced motion makes mining static',"getComputedStyle(workerIcon.querySelector('.wiki-scan')).animationName==='none'")
            call('Emulation.setEmulatedMedia',{'features':[]})
            check('no browser errors',"errors.length===0")
            print(json.dumps({'passed':len(checks),'checks':checks}),flush=True)
            return 0
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
