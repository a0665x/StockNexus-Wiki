"""L2 argument roles, provenance, shapes and bilingual headers use saved data only."""
import tempfile,json,time
from pathlib import Path
from browser_relations import generate
from browser_chat_language import Browser


def main():
 with tempfile.TemporaryDirectory(prefix='wiki-results-') as tmp:
  folder=Path(tmp);html=folder/'fixture.html';generate(html)
  source=html.read_text();html.write_text(source[:source.rfind('<script>\n(async()=>{try{')]+'</body></html>')
  browser=Browser(folder/'browser')
  try:
   page=browser.page(html.as_uri());page.wait("typeof AtlasWiki!=='undefined'")
   page.js("""(()=>{
    rebuild(initialGraph);exportMeta.ticker='TSLA';exportMeta.instrument='NASDAQ:TSLA';window.failGraph=false;window.graphReads=0;window.modelWrites=[];
    window.resultGraph={instrument:'NASDAQ:TSLA',version:1,versions:[{version:1}],nodes:[{id:'n',kind:'Claim',title:'Published evidence',layer:'L1',classification_terms:['topic'],classification_status:'classified'}],edges:[],total_nodes:1,taxonomy:{terms:[{id:'topic',label:'Topic',color:'#7de3bd'}]},opinion_index:[{id:'n',title:'Published evidence',dates:['2026-11-04'],classification_terms:['topic'],classification_status:'classified'}],opinion_groups:{n:['n']},changes:[{version:1,model:'fixture',created_at:'2026-11-04T00:00:00Z',added:1,relations:0,updates:0,titles:Array.from({length:20},(_,i)=>'Saved change '+i)}]};
    window.resultJob={id:'fixture',status:'running',done:0,payload:{model:'fixture',strategy:'root',stage:'compiling',revisions:['a']},usage:{}};
    const prior=fetch;window.fetch=async(url,options)=>{
     if(!url.startsWith('/api/wiki/'))return prior(url,options);
     if(options?.method&&options.method!=='GET'){modelWrites.push(url);throw Error('Unexpected model write');}
     let data={};
     if(url.includes('/research/runs?'))data={runs:[]};
     else if(url.endsWith('/models'))data={models:[{id:'fixture',name:'Fixture',reasoning:[{reasoningEffort:'low'}]}],default_model:'fixture'};
     else if(url.endsWith('/status'))data={instruments:[{instrument:'NASDAQ:TSLA',version:resultGraph.version}],writable:true,bridge_ready:true};
     else if(url.includes('/graph?')){graphReads++;if(failGraph)throw Error('fixture graph temporarily unavailable');data={...resultGraph,jobs:[resultJob],coverage:{scope_total:10,scope_done:1,scope_pending:9}};}
     else if(url.includes('/jobs?'))data={jobs:[resultJob],config:{},version:resultGraph.version,coverage:{scope_total:10,scope_done:1,scope_pending:9}};
     return {ok:true,json:async()=>data};
    };
   })()""")
   page.js('AtlasWiki.show()');page.wait("AtlasWiki.runtime.state().counts.loaded===1")
   page.js("""window.runFixture={snapshot:'snapshot-1',bundle:{lens:{instrument:'NASDAQ:TSLA',query:'Growth versus risk'},opinions:[{claim_id:'l1a',revision_id:'a',kind:'Thesis',title:'Demand',statement:'Demand',labels:['topic'],evidence:[{revision_id:'news-a',quote:'Reported demand'}]},{claim_id:'l1b',revision_id:'b',kind:'Thesis',title:'Costs',statement:'Costs',labels:[],evidence:[]}]},result:{claims:[{id:'c1',statement:'Demand supports growth <img src=x onerror=alert(1)>',derived_from:['l1a'],assumptions:[],invalidating_conditions:[]},{id:'c2',statement:'Costs limit growth',derived_from:['l1b'],assumptions:[],invalidating_conditions:[]}],support:['c1'],counter:['c2']}};AtlasWiki.setResearch(runFixture,'r1');window.g=AtlasWiki.graph();""")
   page.wait("g.graphData().nodes.filter(n=>n.argument_role&&n.__threeObj?.geometry.userData.argumentRole).length===2")
   page.check('saved support and counter become distinct real 3D meshes',"(()=>{const ns=g.graphData().nodes.filter(n=>n.argument_role);return ns.find(n=>n.argument_role==='support').__threeObj.geometry.attributes.position.count===24&&ns.find(n=>n.argument_role==='counter').__threeObj.geometry.attributes.position.count===36})()")
   page.wait("document.querySelectorAll('#wikiShapeLegend img').length>0")
   page.check('legend uses real mesh images for currently rendered roles',"[...document.querySelectorAll('#wikiShapeLegend img')].filter(i=>/支持|反對/.test(i.alt)).length===2&&[...document.querySelectorAll('#wikiShapeLegend img')].every(i=>i.src.startsWith('data:image/png'))&&!$('wikiCounts').textContent.includes('青綠：')")
   page.js("AtlasWiki.selectNode('r1:argument:support')")
   page.check('support selection highlights exact claim, L1 and citation only',"(()=>{const s=AtlasWiki.runtime.state().scope_ids;return ['r1:argument:support','r1:c1','a','news-a'].every(id=>s.includes(id))&&!s.includes('r1:c2')&&!s.includes('b')&&g.graphData().nodes.find(n=>n.id==='r1:c2').wikiDim})()")
   page.check('header explains type and color and safely escapes titles',"g.nodeLabel()(g.graphData().nodes.find(n=>n.id==='r1:c1')).includes('研究觀點 L2')&&g.nodeLabel()(g.graphData().nodes.find(n=>n.id==='r1:c1')).includes('Category')===false&&g.nodeLabel()(g.graphData().nodes.find(n=>n.id==='r1:c1')).includes('&lt;img')")
   page.js("AtlasI18n.setLanguage('en')")
   page.check('language change refreshes selected branch and hover header',"$('wikiDetail').textContent.includes('Supporting arguments')&&$('wikiDetail').textContent.includes('Research question:')&&g.nodeLabel()(g.graphData().nodes.find(n=>n.id==='r1:c1')).includes('Category: Topic')")
   page.js("runFixture.result.counter=[];AtlasWiki.setResearch(runFixture,'r2')")
   page.check('no opposing role means no fabricated counter branch',"!g.graphData().nodes.some(n=>n.argument_role==='counter')")
   page.js("runFixture.result.counter=['missing'];AtlasWiki.setResearch(runFixture,'r3')")
   page.check('unknown claim reference creates no branch',"!g.graphData().nodes.some(n=>n.argument_role==='counter')")
   page.js("runFixture.result.claims[1].derived_from=['unknown'];runFixture.result.counter=['c2'];AtlasWiki.setResearch(runFixture,'r4')")
   page.check('claim without matching L1 never creates argument branch',"!g.graphData().nodes.some(n=>n.argument_role==='counter')")
   page.js("runFixture.result.counter=['c1'];AtlasWiki.setResearch(runFixture,'r5')")
   page.check('shared argument retains both saved roles without duplicating claim',"g.graphData().nodes.filter(n=>n.id==='r5:c1').length===1&&g.graphData().nodes.find(n=>n.id==='r5:c1').argument_roles.length===2")
   page.js("$('wikiLayer').value='L2';$('wikiLayer').dispatchEvent(new Event('change'))")
   page.check('L2-only still shows supported argument branches',"g.graphData().nodes.filter(n=>n.argument_role).length===2&&g.graphData().nodes.every(n=>n.layer==='L2')")
   page.js("AtlasWiki.selectNode('r5:argument:support');g.zoomToFit(0,60)")
   time.sleep(.2)
   import base64
   Path('/tmp/wiki-arguments.png').write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
   page.js("$('wikiLayer').value='L1';$('wikiLayer').dispatchEvent(new Event('change'))")
   page.wait("!$('wikiShapeLegend').textContent.includes('Supporting arguments')")
   page.check('L1 stays unmodified; navigation never calls model',"g.graphData().nodes.length===1&&!AtlasWiki.runtime.data().nodes.some(n=>n.argument_role)&&modelWrites.length===0")
   page.check('no browser runtime errors',"languageErrors.length===0")
  finally:browser.close()

if __name__=='__main__':main()
