"""Wiki panel geometry, resizing and persistent galaxy selection via real browser input.
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
        chrome=subprocess.Popen([os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium') or 'google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1440,1131','--remote-debugging-port=0','--remote-allow-origins=*','--allow-file-access-from-files','--user-data-dir='+str(folder/'profile'),page.as_uri()],stdout=log,stderr=log,start_new_session=True)
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
              const factory=ForceGraph3D;window.ForceGraph3D=(...args)=>{window.fixtureWikiRenderer=factory(...args);return fixtureWikiRenderer;};window.wikiCalls=[];window.planRelease=null;window.deferPlan=false;window.failGraph=false;window.deferPoll=false;window.pollRelease=null;
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
                else if(url.includes('/graph?')){if(failGraph){failGraph=false;throw Error('Temporary graph 503');}value=fixtureWiki;}
                else if(url.endsWith('/apply'))value={status:'saved',resumed:false};
                else if(url.includes('/node?'))value={...fixtureWiki.nodes[1],kind:'Thesis'};
                else if(url.endsWith('/resume'))value={config:fixtureWiki.config,coverage:fixtureWiki.coverage};
                else if(url.endsWith('/jobs'))value={job_id:'job',instrument:'NASDAQ:TSLA'};
                else if(url.includes('/jobs?')){if(deferPoll)await new Promise(r=>{pollRelease=r});value={jobs:fixtureWiki.jobs,config:fixtureWiki.config,version:1,coverage:fixtureWiki.coverage};}
                else if(url.includes('/article?'))value={title:'Fixture source',url:'https://example.test'};
                else if(url.includes('/markdown?'))value={markdown:'# fixture'};
                else throw Error('Unhandled Wiki test URL: '+url);
                return {ok:true,json:async()=>value};
              };
            })()""")
            scenario=os.environ.get('WIKI_RESPONSIVE_SCENARIO','')
            if scenario=='retry':js("failGraph=true")
            if scenario=='restore':
                js("AtlasWorkspace.state.wiki={instrument:'NASDAQ:TSLA',controls:{wikiKind:'Claim',wikiBudget:'1600',wikiLayer:'L1'}}")
            js("AtlasWiki.show()")
            time.sleep(.5)
            if scenario=='retry':
                check('initial graph failure stays explicit',"!AtlasWiki.graph()&&$('wikiStatus').textContent==='Temporary graph 503'")
                js("$('wikiBack').click();AtlasWiki.show()")
                check('re-entering retries failed graph without starting work',"!!AtlasWiki.graph()&&wikiCalls.filter(c=>c.url.includes('/graph?')).length===2&&wikiCalls.every(c=>!c.url.endsWith('/plan'))")
            if scenario=='restore':
                check('restored filters render cached data without second graph fetch',"$('wikiKind').value==='Claim'&&$('wikiBudget').value==='1600'&&fixtureWikiRenderer.graphData().nodes.length===1&&fixtureWikiRenderer.graphData().nodes[0].kind==='Claim'&&wikiCalls.filter(c=>c.url.includes('/graph?')).length===1")
                js("$('wikiKind').value='';$('wikiKind').dispatchEvent(new Event('change'))")
            time.sleep(.6)
            check('one maintenance button and no automatic planning on entry',"!$('wikiResume')&&!$('wikiStart').disabled&&wikiCalls.every(c=>!c.url.endsWith('/plan'))")
            js("window.deferPoll=true;window.pollBefore=wikiCalls.filter(c=>c.url.includes('/jobs?')).length")
            time.sleep(4.4)
            check('slow status request never overlaps a later poll',"wikiCalls.filter(c=>c.url.includes('/jobs?')).length-pollBefore===1")
            js("deferPoll=false;pollRelease?.();window.deferPlan=true")
            click('wikiStart')
            check('click immediately shows preparation and blocks double submit',"$('wikiStart').disabled&&$('wikiStart').getAttribute('aria-busy')==='true'&&$('wikiStatus').getAttribute('aria-busy')==='true'")
            click('wikiStart')
            check('one explicit plan and no model job before it resolves',"wikiCalls.filter(c=>c.url.endsWith('/plan')).length===1&&!wikiCalls.some(c=>c.url.endsWith('/jobs'))")
            js("deferPlan=false;planRelease()")
            time.sleep(.35)
            check('one click queues missing evidence and classifications',"wikiCalls.filter(c=>c.url.endsWith('/jobs')).length===1&&wikiCalls.find(c=>c.url.endsWith('/jobs')).body.classify_missing===true")
            js("window.beforeReturn=wikiCalls.filter(c=>c.url.includes('/graph?')).length;window.returnGraph=AtlasWiki.graph();$('wikiBack').click();AtlasWiki.show()")
            time.sleep(.35)
            check('returning reuses mounted graph without recomputing plan',"AtlasWiki.graph()===returnGraph&&wikiCalls.filter(c=>c.url.includes('/graph?')).length===beforeReturn&&wikiCalls.filter(c=>c.url.endsWith('/plan')).length===1")
            check('idle action never pretends to be processing',"!$('wikiStart').classList.contains('wiki-working')&&$('wikiStart').getAttribute('aria-busy')==='false'")
            # Collect the precise UI symptoms before changing implementation.
            results={}
            results['header_clear']=js("$('wikiPanel').getBoundingClientRect().top>=document.querySelector('body>header').getBoundingClientRect().bottom")
            results['send_inside']=js("(()=>{const b=$('wikichatPage').querySelector('button[type=submit]'),f=b.closest('form'),a=f.querySelector('textarea').getBoundingClientRect(),r=b.getBoundingClientRect();return !!b.querySelector('svg')&&r.top>=a.top&&r.bottom<=a.bottom&&r.right<=a.right})()")
            results['right_resize']=js("!!$('wikiResizeRight')")
            results['timeline_resize']=js("!!$('wikiResizeTimeline')")
            js("fixtureWiki.nodes.push({id:'c',kind:'Claim',title:'Unrelated',citations:[]});fixtureWiki.total_nodes=3;await AtlasWiki.refresh()")
            js("window.beforeNodes=fixtureWikiRenderer.graphData().nodes.slice();window.beforeCamera=JSON.stringify(fixtureWikiRenderer.cameraPosition());fixtureWikiRenderer.onNodeClick()(beforeNodes[0])")
            results['keep_full_graph']=js("fixtureWikiRenderer.graphData().nodes.length===3&&fixtureWikiRenderer.graphData().nodes.every((n,i)=>n===beforeNodes[i])")
            results['no_graph_buttons']=js("$('wikiCounts').querySelectorAll('button').length===0")
            print(json.dumps(results),flush=True)
            assert all(results.values()),results
            def drag_element(id,dx,dy,back=False):
                point=js(f"(()=>{{const r=$('{id}').getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}}}})()") if id!='wikiCanvas' else js("(()=>{const r=$('wikiCanvas').getBoundingClientRect();return {x:r.right-25,y:r.bottom-25}})()")
                call('Input.dispatchMouseEvent',{'type':'mouseMoved',**point})
                call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','buttons':1,'clickCount':1,**point})
                for i in (range(1,7) if dx or dy else []):
                    call('Input.dispatchMouseEvent',{'type':'mouseMoved','button':'left','buttons':1,'x':point['x']+dx*i/6,'y':point['y']+dy*i/6});time.sleep(.02)
                if back:call('Input.dispatchMouseEvent',{'type':'mouseMoved','button':'left','buttons':1,**point})
                call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,'x':point['x']+(0 if back else dx),'y':point['y']+(0 if back else dy)})
                time.sleep(.15)
            check('unrelated node remains rendered and dimmed',"fixtureWikiRenderer.graphData().nodes.find(n=>n.id==='c').wikiDim&&!fixtureWikiRenderer.graphData().nodes.find(n=>n.id==='a').wikiDim")
            check('selecting preserves camera',"JSON.stringify(fixtureWikiRenderer.cameraPosition())===beforeCamera")
            js("window.paneBefore={left:$('wikiControls').getBoundingClientRect().width,right:$('wikiSide').getBoundingClientRect().width,bottom:$('wikiLower').getBoundingClientRect().height,chart:$('wikiTimeline').querySelector('svg').getBoundingClientRect().height};window.refNodes=fixtureWikiRenderer.graphData().nodes.slice();void 0")
            drag_element('wikiResizeTimeline',0,-65)
            check('horizontal divider grows chart and keeps graph usable',"$('wikiLower').getBoundingClientRect().height>paneBefore.bottom+30&&$('wikiTimeline').querySelector('svg').getBoundingClientRect().height>paneBefore.chart+20&&$('wikiCanvas').getBoundingClientRect().height>=139")
            drag_element('wikiResizeLeft',70,0)
            check('left divider adjusts width',"$('wikiControls').getBoundingClientRect().width>paneBefore.left+50")
            drag_element('wikiResizeRight',-70,0)
            check('right divider adjusts width',"$('wikiSide').getBoundingClientRect().width>paneBefore.right+50")
            check('resizing preserves graph and selected galaxy',"fixtureWikiRenderer.graphData().nodes.every((n,i)=>n===refNodes[i])&&AtlasWiki.runtime.state().root_ids[0]==='a'")
            js("window.savedLayout=localStorage.getItem('stocknexus.wikiLayout');$('wikiBack').click();AtlasWiki.show()")
            time.sleep(.3)
            check('pane dimensions survive surface switch',"localStorage.getItem('stocknexus.wikiLayout')===savedLayout&&JSON.parse(localStorage.getItem('stocknexus.wikiRuntime')).layout.right>280")
            js("fixtureWikiRenderer.controls().staticMoving=true;fixtureWikiRenderer.cameraPosition({x:0,y:0,z:600});window.dragCamera=fixtureWikiRenderer.camera().position.toArray()")
            drag_element('wikiCanvas',-65,-30)
            check('camera drag rotates without clearing galaxy',"AtlasWiki.runtime.state().root_ids[0]==='a'&&fixtureWikiRenderer.camera().position.toArray().some((v,i)=>Math.abs(v-dragCamera[i])>1)")
            drag_element('wikiCanvas',-65,-30,True)
            check('dragging away and back still preserves selection',"AtlasWiki.runtime.state().root_ids[0]==='a'")
            drag_element('wikiCanvas',0,0)
            check('only blank click restores full brightness',"AtlasWiki.runtime.state().root_ids.length===0&&fixtureWikiRenderer.graphData().nodes.length===3&&fixtureWikiRenderer.graphData().nodes.every(n=>!n.wikiDim)")
            js("const originalChatFetch=fetch;window.chatTurns=0;window.fetch=async(url,o)=>{if(!String(url).startsWith('/api/chat/'))return originalChatFetch(url,o);if(url.endsWith('/turn')){chatTurns++;return new Response(JSON.stringify({type:'message',text:'Fixture reply'})+'\\n'+JSON.stringify({type:'done'})+'\\n');}return new Response(JSON.stringify(url.endsWith('/session')?{token:'fixture'}:{commands:[]}));};$('wikichatTab').click()")
            time.sleep(.3)
            check('airplane stays inside visible message field',"(()=>{const b=$('wikichatPage').querySelector('.chat-send'),a=$('wikichatPage').querySelector('textarea').getBoundingClientRect(),r=b.getBoundingClientRect();return r.left>a.left&&r.right<=a.right&&r.top>=a.top&&r.bottom<=a.bottom&&r.right<=innerWidth&&b.disabled})()")
            js("const input=$('wikichatPage').querySelector('textarea');input.value='Review the selected evidence';input.dispatchEvent(new Event('input'));$('wikichatPage').querySelector('.chat-send').id='fixtureSend'")
            click('fixtureSend');time.sleep(.3)
            check('airplane submits exactly one chat turn',"chatTurns===1&&$('wikichatPage').querySelectorAll('.chat-message').length===2&&$('wikichatPage').querySelector('.chat-send').disabled")
            js("AtlasI18n.setLanguage('en')")
            check('language preserves icon and accessible label',"!!$('fixtureSend').querySelector('svg')&&$('fixtureSend').getAttribute('aria-label')==='Send'")
            call('Emulation.setDeviceMetricsOverride',{'width':1238,'height':1005,'deviceScaleFactor':1,'mobile':False});time.sleep(.3)
            check('desktop bounds preserve global controls and center pane',"$('wikiPanel').getBoundingClientRect().top>=document.querySelector('body>header').getBoundingClientRect().bottom&&$('wikiSide').getBoundingClientRect().right<=innerWidth+1&&$('wikiCanvas').getBoundingClientRect().width>=259")
            # BDD: the dropdown, chart and group list share model classifications.
            js("""AtlasI18n.setLanguage('zh-TW');
              fixtureWiki.taxonomy={terms:[{id:'topic.cloud',label:'雲端',color:'#7de3bd'},{id:'analysis.fact_check',label:'查核／更正',color:'#7db6f2'},{id:'analysis.noise',label:'低相關／噪聲',color:'#d3a5ef'}]};
              fixtureWiki.nodes[1].classification_terms=['topic.cloud','analysis.fact_check'];fixtureWiki.nodes[1].classification_status='classified';
              fixtureWiki.nodes[2].classification_terms=[];fixtureWiki.nodes[2].classification_status='pending';
              fixtureWiki.nodes.push({id:'d',kind:'Claim',title:'Unclassified opinion',classification_terms:[],classification_status:'unclassified'});
              fixtureWiki.opinion_groups={b:['a','b'],c:['c'],d:['d']};
              const selectedDate=new Date(Number($('wikiRangeEnd').value)*86400000).toISOString().slice(0,10);
              fixtureWiki.opinion_index=fixtureWiki.nodes.slice(1).map(n=>({...n,dates:[selectedDate]}));fixtureWiki.total_nodes=4;
              window.writesBefore=wikiCalls.filter(c=>c.body).length;await AtlasWiki.refresh();
            """)
            check('taxonomy counts opinion groups once per label',"['topic.cloud','analysis.fact_check','__pending','__unclassified'].every(id=>Array.from($('wikiAssessment').options).some(o=>o.value===id&&o.textContent.endsWith(' · 1')))&&Array.from($('wikiAssessment').options).some(o=>o.value==='analysis.noise'&&o.textContent.endsWith(' · 0'))")
            check('chart uses model tags and explicit missing states, never legacy assessment',"Array.from($('wikiTimeline').querySelectorAll('rect[data-count]')).reduce((sum,r)=>sum+Number(r.dataset.count),0)===4&&!$('wikiTimeline').textContent.includes('直接營運')&&!$('wikiInsights').textContent.includes('間接影響')&&!!Array.from($('wikiTimeline').querySelectorAll('rect')).find(r=>r.dataset.category==='analysis.fact_check')")
            js("Array.from($('wikiTimeline').querySelectorAll('rect')).find(r=>r.dataset.category==='analysis.fact_check').id='fixtureTaxBar'")
            click('fixtureTaxBar')
            check('bar selection synchronizes dropdown graph and opinion detail',"$('wikiAssessment').value==='analysis.fact_check'&&fixtureWikiRenderer.graphData().nodes.map(n=>n.id).sort().join(',')==='a,b'&&$('wikiDetail').querySelectorAll('.wiki-viewpoint').length===1&&wikiCalls.filter(c=>c.body).length===writesBefore")
            js("$('wikiAssessment').value='';$('wikiAssessment').dispatchEvent(new Event('change'));window.toolbarBefore=document.querySelector('.wiki-toolbar').getBoundingClientRect().toJSON();window.canvasBefore=$('wikiCanvas').getBoundingClientRect().toJSON()")
            click('wikiAssessment')
            check('native dropdown opens without a second menu or layout shift',"document.activeElement===$('wikiAssessment')&&!$('wikiClassLegend')&&$('wikiAssessment').size<=1&&JSON.stringify(document.querySelector('.wiki-toolbar').getBoundingClientRect().toJSON())===JSON.stringify(toolbarBefore)&&JSON.stringify($('wikiCanvas').getBoundingClientRect().toJSON())===JSON.stringify(canvasBefore)")
            call('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
            call('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
            js("$('wikiAssessment').blur()")
            import base64
            Path('/tmp/wiki-split-desktop.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True});time.sleep(.2)
            check('mobile layout fits without resize handles',"$('wikiPanel').scrollWidth<=$('wikiPanel').clientWidth+1&&$('wikiResizeRight').getBoundingClientRect().width===0")
            js("$('wikiAssessment').scrollIntoView({block:'center'})")
            Path('/tmp/wiki-split-mobile.png').write_bytes(base64.b64decode(call('Page.captureScreenshot',{'format':'png'})['data']))
            check('mobile classification selector stays within viewport',"$('wikiAssessment').getBoundingClientRect().right<=innerWidth+1&&!$('wikiClassLegend')")
            check('no browser errors',"errors.length===0")
            print('PASS',len(checks)+len(results),'layout and physical interaction checks',flush=True)
            return 0
        finally:
            try:os.killpg(chrome.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            chrome.wait(timeout=10);time.sleep(.3);log.close()

if __name__=='__main__':sys.exit(main())
