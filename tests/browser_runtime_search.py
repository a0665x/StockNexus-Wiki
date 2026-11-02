"""Generate an offline browser regression page using real local NVDA cache only.
Run: python3 tests/browser_runtime_search.py /tmp/graphnews-runtime-regression.html
Open the generated file in a WebGL browser; document.body.dataset.qa reports results.
No API keys, DB writes or provider requests. Cached news is never checked into the repo.
"""
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server import graph_payload
from browser_startup import served_document
from test_server import HTTPTests

def generate(destination):
    with sqlite3.connect(f'file:{ROOT / "data/news-atlas.sqlite3"}?mode=ro',uri=True) as db:
        rows=[]
        for provider in ['google','yahoo','massive']:
            records=db.execute("SELECT DISTINCT a.payload FROM articles a JOIN memberships m ON a.provider=m.provider AND a.id=m.article_id WHERE m.query_key LIKE '%:NVDA' AND a.published_at>='2025-10-28' AND a.published_at<'2026-10-29' AND a.provider=? ORDER BY a.published_at DESC",(provider,)).fetchall()
            rows.extend(json.loads(r[0]) for r in records)
    if not rows: raise SystemExit('Requires real NVDA cached news; no synthetic substitute.')
    payload=graph_payload(rows)
    harness=HTTPTests();harness.setUp()
    try:
        html,assets=served_document(harness.request)
        assert all(a['status']==200 for a in assets),assets
    finally:
        harness.tearDown()
    fixture='''<script>
window.qaErrors=[];window.addEventListener('error',e=>qaErrors.push(e.message));window.addEventListener('unhandledrejection',e=>qaErrors.push(String(e.reason)));
let acquisitionCalls=0;const fixture=PAYLOAD;
window.fetch=async(url,options)=>{
 if(url==='/api/status')return {ok:true,json:async()=>({db:{articles:fixture.total_articles}})};
 if(url==='/api/channels')return {ok:true,json:async()=>({channels:fixture.channel_definitions})};
 if(url==='/api/snapshots')return {ok:true,json:async()=>({snapshots:[]})};
 if(url==='/api/search'){acquisitionCalls++;return {ok:true,body:new ReadableStream({start(c){for(const event of [...Object.entries(fixture.source_graphs).map(([source,g])=>({type:'source',source,articles:g.articles,graph:fixture})),{type:'done',elapsed:0}])c.enqueue(new TextEncoder().encode(JSON.stringify(event)+'\\n'));c.close()}})}};
 throw Error('No server operation allowed during runtime search: '+url);
};
</script>'''.replace('PAYLOAD',json.dumps(payload).replace('</','<\\/'))
    html=html.replace('<script>',fixture+'<script>',1)
    qa='''<script>
const wait=ms=>new Promise(r=>setTimeout(r,ms)),check=(v,m)=>{if(!v)throw Error(m)};
(async()=>{try{
 $('dateCustom').click();$('query').value='NVDA';$('ticker').value='NVDA';$('start').value='2025-10-28';$('end').value='2026-10-28';$('end').dispatchEvent(new Event('input',{bubbles:true}));
 for(const p of ['google','yahoo','massive'])document.querySelector('.sources input[value='+p+']').checked=true;
 $('submit').click();await wait(1600);check(articles.length>0,'initial graph');check(acquisitionCalls===1,'one initial acquisition');
 const nodes=graph.graphData().nodes,links=graph.graphData().links,ids=articles.map(a=>a.id).join(),count=articles.length;
 const surface=$('graph'),rect=surface.getBoundingClientRect(),point=graph.graphData().nodes.map(n=>graph.graph2ScreenCoords(n.x,n.y,n.z)).find(p=>p.x>20&&p.y>20&&p.x<rect.width-20&&p.y<rect.height-20);check(point,'visible pointer target');
 surface.setPointerCapture=()=>{};surface.hasPointerCapture=()=>false;
 const pointer=(type,buttons=0)=>surface.dispatchEvent(new PointerEvent(type,{clientX:rect.left+point.x,clientY:rect.top+point.y,pointerId:10,button:0,buttons,isPrimary:true,bubbles:true,cancelable:true}));
 clearFocus();pointer('pointermove');const candidate=hovered;check(candidate&&focusRoot()===null,'hover previews without confirming');check(candidateTrace.nodes.has(candidate),'candidate tree visible');check(savedPayload().view.focus.root_ids.length===0,'preview not persisted');
 pointer('pointerdown',1);pointer('pointerup');check(focusRoot()===candidate,'tap confirms sticky candidate');document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check(focusRoot()===null,'Escape clears confirmed root');pointer('pointermove');check(focusRoot()===null&&hovered,'hover after Escape stays preview');pointer('pointerleave');await wait(180);check(hovered===null,'leaving clears candidate');

 check(['google','yahoo','massive'].every(p=>fixture.source_graphs[p].articles.length),'three real cached sources');
 check(!$('rootQuery').form&&!$('rootSearchSubmit').form&&$('rootSearchSubmit').type==='button','runtime controls must not submit any form');
 let graphWrites=0;const originalData=graph.graphData;graph.graphData=function(...args){if(args.length)graphWrites++;return originalData.apply(this,args)};
 $('rootQuery').value='IPO';$('rootLimit').value=3;$('rootSearchSubmit').click();check(!$('rootSearchSpinner').hidden&&$('rootSearchSubmit').disabled,'busy feedback');await wait(150);check($('rootSearchSpinner').hidden,'spinner clears');check($('rootSearchStatus').textContent.includes('命中'),'success feedback');
 check(lockedRoots.length>0,'IPO must recall matching cached news');const matches=lockedRoots.length;
 check(graph.graphData().nodes===nodes&&graph.graphData().links===links,'same node and edge objects');check(articles.map(a=>a.id).join()===ids,'all articles retained');
 for(let i=0;i<15;i++){await wait(40);graph.renderer().render(graph.scene(),graph.camera());}
 const pixels=$('glowCanvas').getContext('2d').getImageData(0,0,$('glowCanvas').width,$('glowCanvas').height).data;check(pixels.some((v,i)=>i%4===3&&v>0),'IPO galaxies rendered');
 const roots=lockedRoots.join();$('rootQuery').value='no-such-robot-zzzz';const enter=new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true});$('rootQuery').dispatchEvent(enter);await wait(150);
 check(enter.defaultPrevented,'Enter cannot navigate');check(lockedRoots.join()===roots&&articles.length===count,'no-match preserves forest and nodes');
 check(acquisitionCalls===1&&graphWrites===0,'no acquisition or graph replacement');check(!qaErrors.length,qaErrors.join(';'));
 $('rootQuery').value='IPO';$('rootSearchSubmit').click();await wait(150);
 const cameraBefore=JSON.stringify(graph.cameraPosition());
 const dated=nodes.find(n=>AtlasTimeline.day(n.published_at)!==null&&AtlasTimeline.day(n.published_at)>=timelineBounds.start&&AtlasTimeline.day(n.published_at)<=timelineBounds.end);
 check(dated,'dated node for time lens');
 $('timeSizeEnabled').checked=true;$('timeSizeEnabled').dispatchEvent(new Event('change'));
 $('timeFocusSlider').value=Math.round((AtlasTimeline.day(dated.published_at)-timelineBounds.start)/86400000);$('timeFocusSlider').dispatchEvent(new Event('input'));await wait(80);
 check(Math.abs(AtlasTimeline.timeScale(dated,timeFocus,timelineBounds)-2)<.001,'focused radius doubles');
 const focusRadius=dated.__threeObj?.geometry?.parameters?.radius*dated.__threeObj?.scale?.x;
 check(Number.isFinite(focusRadius),'rendered sphere geometry exists');
 $('timeSizeEnabled').checked=false;$('timeSizeEnabled').dispatchEvent(new Event('change'));await wait(80);
 check(AtlasTimeline.timeScale(dated,timeFocus,timelineBounds)===1,'disabled restores base size');
 check(Math.abs(focusRadius/(dated.__threeObj.geometry.parameters.radius*dated.__threeObj.scale.x)-2)<.001,'actual rendered radius doubles');
 check(graph.graphData().nodes===nodes&&graphWrites===0,'time lens preserves runtime graph');
 check(JSON.stringify(graph.cameraPosition())===cameraBefore,'time lens preserves camera');
 check($('timeFocusTicks').children.length===12,'12 month range has calendar month ticks');
 $('timeSizeEnabled').checked=true;$('timeSizeEnabled').dispatchEvent(new Event('change'));
 // Real SVG input path: local shoulder shaping, no peak/width sliders, undo and persistence.
 $('timeFocusSlider').value=Math.round(Number($('timeFocusSlider').max)/2);$('timeFocusSlider').dispatchEvent(new Event('input'));
 const bell=$('timeBell'),bellRect=bell.getBoundingClientRect();bell.setPointerCapture=()=>{};bell.hasPointerCapture=()=>false;
 const dragEvent=(type,x,y)=>new PointerEvent(type,{clientX:x,clientY:y,pointerId:42,button:0,buttons:type==='pointerup'?0:1,bubbles:true,cancelable:true});
 const center=AtlasTimeLens.curve(timeFocus,timelineBounds).center;
 const px=bellRect.left+bellRect.width*(12+(center+.14)*976)/1000,py=bellRect.top+bellRect.height*.65;
 const beforeShape=JSON.stringify(timeFocus),geometry=dated.__threeObj.geometry;
 $('timeBellLine').dispatchEvent(dragEvent('pointerdown',px,py));check(JSON.stringify(timeFocus)===beforeShape,'curve press preserves grab offset');
 bell.dispatchEvent(dragEvent('pointermove',px,py-25));check(timeFocus.profile?.length===129,'direct curve stroke creates profile');
 check(AtlasTimeline.profileGain(timeFocus,.14,timelineBounds)>2,'shoulder grows locally');
 check(Math.abs(AtlasTimeline.profileGain(timeFocus,0,timelineBounds)-2)<.001,'shoulder sculpt leaves focus peak unchanged');
 bell.dispatchEvent(dragEvent('pointerup',px,py-25));check(!timeLens.isDragging(),'curve drag released');
 const firstShape=JSON.stringify(timeFocus.profile);
 check(JSON.stringify(AtlasUI.read('timeFocus',{}).profile)===firstShape,'sculpted profile persisted in browser storage');
 $('timeBellUndo').click();check(JSON.stringify(timeFocus)===beforeShape,'undo restores stroke');
 $('timeBellHit').dispatchEvent(dragEvent('pointerdown',px,py));bell.dispatchEvent(dragEvent('pointermove',px+bellRect.width*.08,py));bell.dispatchEvent(dragEvent('pointerup',px+bellRect.width*.08,py));
 check(timeFocus.profile?.length===129&&AtlasTimeline.profileGain(timeFocus,.22,timelineBounds)>1.3,'horizontal-only drag widens shoulder');
 check(Math.abs(AtlasTimeline.profileGain(timeFocus,-.14,timelineBounds)-AtlasTimeline.profileGain(JSON.parse(beforeShape),-.14,timelineBounds))<.01,'horizontal width preserves opposite side');
 $('timeBellUndo').click();check(JSON.stringify(timeFocus)===beforeShape,'undo width stroke');

 check(!document.getElementById('timePeak')&&!document.getElementById('timeWidth'),'no peak or width sliders');
 // A new stroke at the focus raises it to the cap and fully compensates depth.
 const cx=bellRect.left+bellRect.width*(12+center*976)/1000;
 $('timeBellHit').dispatchEvent(dragEvent('pointerdown',cx,py));bell.dispatchEvent(dragEvent('pointermove',cx,py-bellRect.height));bell.dispatchEvent(dragEvent('pointercancel',cx,py));
 check(!timeLens.isDragging(),'curve cancel releases');graph.renderer().render(graph.scene(),graph.camera());
 check($('timePerspective').textContent.includes('100%'),'high gain full compensation');
 const cam=graph.camera(),m=cam.matrixWorld.elements,viewport=$('graph').getBoundingClientRect();
 const projected=nodes.filter(n=>Number.isFinite(n.x)&&Number.isFinite(n.y)&&Number.isFinite(n.z)).map(n=>{
   const v=cam.position.clone().set(n.x,n.y,n.z).project(cam),r=n.__threeObj.geometry.parameters.radius*n.__threeObj.scale.x;
   if(v.z<=-1||v.z>=1)return null;
   const edge=cam.position.clone().set(n.x+m[0]*r,n.y+m[1]*r,n.z+m[2]*r).project(cam);
   return Math.hypot((edge.x-v.x)*viewport.width/2,(edge.y-v.y)*viewport.height/2)/AtlasTimeline.timeScale(n,timeFocus,timelineBounds);
 }).filter(x=>x>0);
 check(projected.length>100,'visible projected nodes for compensation check');check(Math.max(...projected)/Math.min(...projected)<1.001,'screen-space radius follows Gaussian regardless of depth');
 check(dated.__threeObj.geometry===geometry,'curve changes scale without rebuilding sphere geometry');
 check(graphWrites===0&&graph.graphData().nodes===nodes,'curve keeps graph objects');check(JSON.stringify(graph.cameraPosition())===cameraBefore,'curve keeps camera');
 check(JSON.stringify(savedPayload().view.time_focus.profile)===JSON.stringify(timeFocus.profile),'sculpted curve included in snapshot');
 $('timeBellReset').click();check(timeFocus.peak===2&&timeFocus.width===.12&&!timeFocus.profile,'curve reset');
 const forestIds=[...activeTrace.nodes.keys()].sort().join(),forestRoots=lockedRoots.join();
 $('modeTimeline').click();
 check(lockedRoots.join()===forestRoots&&[...activeTrace.nodes.keys()].sort().join()===forestIds,'timeline shares selected forest');
 check($('timeline').querySelector('[data-focus-depth="0"]'),'density roots highlighted immediately');
 check($('timeline').textContent.includes('關聯'),'channel selected counts');
 const unrelated=$('timeline').querySelector('[data-focus-depth=""]');
 if(unrelated)unrelated.dispatchEvent(new PointerEvent('pointerenter'));
 check(lockedRoots.join()===forestRoots,'density hover cannot replace roots');
 check(!$('timelineStyle')&&!$('timelinePlay'),'density only, no playback controls');
 $('timelineZoomIn').click();check($('timelineZoom').value==='1.5','timeline zoom button');
 $('timelineZoomOut').click();check($('timelineZoom').value==='1','timeline zoom reset');
 check(!qaErrors.length,qaErrors.join(';'));
 $('modeNetwork').click();$('sourcePanelToggle').click();$('timeBellUndo').click();await wait(80);
 const beforePanels=graph.graphData().nodes,beforePanelWrites=graphWrites;$('timePanelToggle').click();await wait(50);
 for(const id of ['sourcePanel','timeFocusBar']){const rect=$(id).getBoundingClientRect();check(rect.width<=40&&rect.height<=40,'collapsed panel is a compact icon');}
 check(graph.graphData().nodes===beforePanels&&graphWrites===beforePanelWrites,'collapsing tools retains graph');
 document.body.dataset.qa='PASS: compact panels preserve graph, horizontal width and local sculpt/undo/cancel/persistence, depth-compensated projection, mesh reuse, actual time-size geometry, runtime identity/camera, 12 month ticks, shared timeline/density forest; hover preview, click confirmation, Escape, leave; NVDA three-source real cache -> IPO; '+count+' nodes retained; '+matches+' roots; no network, graph writes or form navigation';
 }catch(e){document.body.dataset.qa='FAIL: '+e.message+' ERRORS '+qaErrors.join(';');}finally{document.querySelectorAll('script').forEach(s=>s.remove());}})();
</script>'''
    Path(destination).write_text((qa+'</body>').join(html.rsplit('</body>',1)))
    print('Generated browser replay:',{p:len(g['articles']) for p,g in payload['source_graphs'].items()})

if __name__=='__main__': generate(sys.argv[1] if len(sys.argv)>1 else '/tmp/graphnews-runtime-regression.html')
