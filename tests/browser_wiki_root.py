"""Frozen Wiki root -> News reading interaction; isolated browser, no model calls."""
import json,tempfile
from pathlib import Path
from browser_relations import generate
from browser_chat_language import Browser


def main():
 with tempfile.TemporaryDirectory(prefix='wiki-root-') as tmp:
  folder=Path(tmp);html=folder/'fixture.html';generate(html)
  source=html.read_text();source=source[:source.rfind('<script>\n(async()=>{try{')]+'</body></html>';html.write_text(source)
  browser=Browser(folder/'browser')
  try:
   page=browser.page(html.as_uri());page.wait("typeof AtlasWiki!=='undefined'")
   page.js("""(()=>{
    rebuild(initialGraph);exportMeta.ticker='TSLA';exportMeta.instrument='NASDAQ:TSLA';
    const members=focusView.articles.slice(0,3);window.testTree={root_id:members[0].id,articles:members.map(a=>({id:a.article_id||a.id,provider:a.source.provider}))};
    window.testJob={id:'fixture',status:'running',done:3,usage:{},payload:{strategy:'root',revisions:['a'],model:'fixture',stage:'compiling',current_size:2,group_info:{group:9,groups:100,targets:1,context_articles:3,part:1,parts:2,root_id:testTree.root_id},graph_selection:{trees:[testTree]}}};
    window.readWrites=[];const prior=window.fetch;window.fetch=async(url,options)=>{
     if(!url.startsWith('/api/wiki/'))return prior(url,options);
     if(options?.method&&options.method!=='GET'){readWrites.push(url);throw Error('Unexpected Wiki write');}
     let data={};
     if(url.endsWith('/models'))data={models:[{id:'fixture',name:'Fixture',reasoning:[{reasoningEffort:'low'}]}],default_model:'fixture'};
     else if(url.endsWith('/status'))data={instruments:[{instrument:'NASDAQ:TSLA',version:1}],writable:true,bridge_ready:true};
     else if(url.includes('/graph?'))data={instrument:'NASDAQ:TSLA',version:1,versions:[{version:1}],nodes:[],edges:[],total_nodes:0};
     else if(url.includes('/jobs?'))data={jobs:[testJob],config:{},version:1,coverage:{scope_total:10,scope_done:3,scope_pending:7}};
     return {ok:true,json:async()=>data};
    };
    window.beforeSettings=JSON.stringify({exploration,relation:basePayload.relation_settings});
   })()""")
   page.js('AtlasWiki.show()');page.wait("document.getElementById('wikiCurrentRoot')&&!document.getElementById('wikiCurrentRoot').disabled")
   def click(ident):
    xy=page.js("(()=>{const e=document.getElementById("+json.dumps(ident)+");e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
    for kind in ('mouseMoved','mousePressed','mouseReleased'):page.call('Input.dispatchMouseEvent',{'type':kind,**xy,'button':'left','clickCount':1})
   click('wikiCurrentRoot')
   page.check('link returns to News and highlights exact frozen members',"$('wikiPanel').hidden&&wikiRootPreview!==null&&activeTrace.nodes.size===3&&lockedRoots[0]===testTree.root_id")
   page.check('reading preserves settings and never submits model work',"beforeSettings===JSON.stringify({exploration,relation:basePayload.relation_settings})&&readWrites.length===0")
   page.check('snapshot members are prioritized for rendering',"testTree.articles.every(a=>viewPriority().includes(a.id))")
   page.js("refreshFocus();renderNetwork();")
   page.check('render and focus refresh keep frozen members',"activeTrace.nodes.size===3&&wikiRootPreview!==null")
   page.js("rebuild({...basePayload},true)")
   page.check('background relation refresh preserves snapshot membership',"wikiRootPreview!==null&&activeTrace.nodes.size===3")
   page.check('current edge settings are explicitly disclosed',"$('traceStatus').textContent.includes('連線依目前新聞設定')")
   page.js("AtlasI18n.setLanguage('en')")
   page.check('snapshot notice follows language changes',"$('traceStatus').textContent.includes('frozen members')")
   # Real pointer drag on graph background must preserve the locked snapshot.
   xy=page.js("(()=>{const r=$('graph').getBoundingClientRect();return {x:r.right-20,y:r.bottom-60}})()")
   page.call('Input.dispatchMouseEvent',{'type':'mousePressed',**xy,'button':'left','clickCount':1})
   page.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':xy['x']-35,'y':xy['y']-25,'buttons':1})
   page.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':xy['x']-35,'y':xy['y']-25,'button':'left','clickCount':1})
   page.check('drag does not exit tree reading',"wikiRootPreview!==null")
   page.js("clearGraphSelection()")
   page.check('background reset leaves frozen-tree mode',"wikiRootPreview===null&&lockedRoots.length===0")
   page.js("AtlasWiki.show()");page.wait("!$('wikiPanel').hidden&&!!$('wikiCurrentRoot')")
   page.js("exportMeta.ticker='OTHER'");click('wikiCurrentRoot')
   page.check('wrong stock does not navigate or replace data',"!$('wikiPanel').hidden&&wikiRootPreview===null&&exportMeta.ticker==='OTHER'")
   page.js("exportMeta.ticker='TSLA';testTree.articles.push({id:'not-loaded',provider:'massive'});AtlasWiki.refresh()")
   page.wait("$('wikiCurrentRoot')!==null");click('wikiCurrentRoot')
   page.check('missing members do not silently show a partial tree',"!$('wikiPanel').hidden&&wikiRootPreview===null")
   page.js("testTree.articles.pop()")
   page.js("""(()=>{
    clearGraphSelection();selected=null;
    const sample=focusView.articles[0];window.budgetRows=Array.from({length:180},(_,i)=>({...sample,id:'budget-'+String(i).padStart(3,'0'),article_id:undefined,display_sources:undefined,source:{...sample.source,provider:'massive'},published_at:i<120?'2020-01-01T00:00:00Z':'2026-11-01T00:00:00Z'}));
    for(const provider of providers)$('view-'+provider).checked=provider==='massive';
    renderBudget=100;rebuild({source_graphs:{massive:{articles:budgetRows,relations:[]}},total_articles:180});
    testTree={root_id:budgetRows[119].id,articles:budgetRows.slice(0,120).map(a=>({id:a.id,provider:'massive'}))};
    testJob.payload.graph_selection.trees=[testTree];testJob.payload.group_info.root_id=testTree.root_id;
   })()""")
   page.check('test root is loaded globally but absent from low-budget rendering',"focusView.articles.length===180&&!graph.graphData().nodes.some(a=>a.id===testTree.root_id)&&renderBudget===100")
   page.js('AtlasWiki.refresh()');page.wait("!!$('wikiCurrentRoot')");click('wikiCurrentRoot')
   page.check('link renders all 120 members despite saved budget 100',"$('wikiPanel').hidden&&testTree.articles.every(a=>graph.graphData().nodes.some(n=>n.id===a.id))&&renderedCount===120&&renderBudget===100&&focusView.articles.length===180")
   page.js('clearGraphSelection()')
   page.check('exit restores saved GPU budget without reducing global data',"renderedCount===100&&renderBudget===100&&focusView.articles.length===180&&readWrites.length===0")
   page.check('no browser errors',"errors.length===0&&languageErrors.length===0")
  finally:browser.close()

if __name__=='__main__':main()
