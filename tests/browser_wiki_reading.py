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
   page.js("resultGraph.taxonomy.terms=[{id:'topic.cloud',label:'雲端',color:'#7de3bd'}];AtlasI18n.setLanguage('en');AtlasWiki.refresh()")
   page.wait("[...$('wikiAssessment').options].some(o=>o.value==='topic.cloud')")
   page.check('English classification labels',"$('wikiAssessment').textContent.includes('Cloud')&&!$('wikiAssessment').textContent.includes('雲端')")
   page.check('English research entrance',"$('researchOpen').textContent==='Research question · L2'")
   second=browser.page(html.as_uri());second.wait("typeof AtlasWiki!=='undefined'")
   second.check('new tab restores English research label',"$('researchOpen').textContent==='Research question · L2'&&AtlasI18n.termLabel({id:'topic.cloud',label:'雲端'})==='Cloud'")
   page.js("AtlasI18n.setLanguage('zh-Hant')");second.wait("$('researchOpen').textContent==='研究問題 · L2'")
   second.check('cross-tab language switch restores Chinese',"AtlasI18n.termLabel({id:'topic.cloud',label:'雲端'})==='雲端'")
  finally:browser.close()

if __name__=='__main__':main()
