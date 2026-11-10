"""Expanded L2 sidebar localization across asynchronous runtime transitions."""
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
    rebuild(initialGraph);exportMeta.ticker='TSLA';exportMeta.instrument='NASDAQ:TSLA';window.failGraph=false;window.busyResearch=true;window.failAvailability=false;window.researchJob=null;window.failJob=false;window.graphReads=0;window.modelWrites=[];
    window.resultGraph={instrument:'NASDAQ:TSLA',version:1,versions:[{version:1}],nodes:[{id:'n',kind:'Claim',title:'Published evidence',layer:'L1',classification_terms:['topic'],classification_status:'classified'}],edges:[],total_nodes:1,taxonomy:{terms:[{id:'topic',label:'Topic',color:'#7de3bd'}]},opinion_index:[{id:'n',title:'Published evidence',dates:['2026-11-04'],classification_terms:['topic'],classification_status:'classified'}],opinion_groups:{n:['n']},changes:[{version:1,model:'fixture',created_at:'2026-11-04T00:00:00Z',added:1,relations:0,updates:0,titles:Array.from({length:20},(_,i)=>'Saved change '+i)}]};
    window.resultJob={id:'fixture',status:'running',done:0,payload:{model:'fixture',strategy:'root',stage:'compiling',revisions:['a']},usage:{}};
    const prior=fetch;window.fetch=async(url,options)=>{
     if(!url.startsWith('/api/wiki/'))return prior(url,options);
     if(options?.method&&options.method!=='GET'){modelWrites.push(url);throw Error('Unexpected model write');}
     let data={};
     if(url.includes('/research/availability?')){if(failAvailability)throw Error('fixture unavailable');data={busy:busyResearch,instruments:busyResearch?['NASDAQ:TSLA']:[],active_job:researchJob?{id:researchJob.id}:null};}
     else if(url.includes('/research/job?')){if(failJob)throw Error('fixture connection lost');data=researchJob;}
     else if(url.includes('/research/lenses?'))data={lenses:[{id:'saved',lens:{query:'我的原始研究問題',research_facets:['investment','growth']},run_id:'run2',mode:'live',refresh_state:'stale',revision:2,history:['run1','run2']}]};
     else if(url.includes('/research/taxonomy?'))data={terms:[{id:'topic.cloud',label:'雲端',color:'#7de3bd',opinion_ids:['n']}]};
     else if(url.includes('/research/runs?'))data={runs:[{id:'unsaved',lens:{query:'Valuation risk',research_facets:['valuation','risk']}},{id:'run1',lens:{query:'Historical duplicate',research_facets:['growth']}}]};
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
   page.js("$('researchOpen').click()")
   page.wait("$('researchSubmit').disabled&&$('researchAvailabilityText').textContent.includes('NASDAQ:TSLA')")
   page.js("document.querySelectorAll('#researchPanel details').forEach(d=>d.open=true)")
   page.check('saved question preserves original language',"$('researchSaved').querySelector('.research-source').textContent==='我的原始研究問題'")
   page.check('expanded English L2 sidebar includes no untranslated interface text',"!/[\\u3400-\\u9fff]/.test([...$('researchPanel').querySelectorAll('*')].filter(e=>!e.closest('.research-source')).flatMap(e=>[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent)).join(' '))")
   page.check('catalog includes completed result but not saved history duplicate',"$('researchSaved').textContent.includes('Valuation risk')&&!$('researchSaved').textContent.includes('Historical duplicate')")
   page.js("document.querySelector('[data-facet=valuation]').click()")
   page.wait("$('researchSaved').querySelectorAll('section').length===1")
   page.check('facet filters question cards without model work',"$('researchSaved').textContent.includes('Valuation risk')&&!$('researchSaved').textContent.includes('我的原始研究問題')")
   page.js("$('researchSearch').value='absent';$('researchSearch').dispatchEvent(new Event('input'))")
   page.wait("$('researchSaved').textContent.includes('No matching')")
   page.js("$('researchSearch').value='';$('researchSearch').dispatchEvent(new Event('input'));document.querySelector('#researchFacets button').click()")
   page.js("$('researchSubmitWrap').dispatchEvent(new Event('pointerenter'))")
   page.wait("!$('researchBusyTip').hidden")
   page.check('busy hover explanation is English',"$('researchBusyTip').textContent.includes('Saved L2')&&!/[\\u3400-\\u9fff]/.test($('researchBusyTip').textContent)")
   page.js("AtlasI18n.setLanguage('zh-TW')")
   page.wait("$('researchAvailabilityText').textContent.includes('L1 整理中')")
   page.js("AtlasI18n.setLanguage('en');failAvailability=true")
   page.wait("$('researchAvailabilityText').textContent.includes('reconnecting')")
   page.check('availability outage localized with retry',"$('researchBlockers').textContent.includes('Check again')&&!/[\\u3400-\\u9fff]/.test([...$('researchPanel').querySelectorAll('*')].filter(e=>!e.closest('.research-source')).flatMap(e=>[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent)).join(' '))")
   page.js("failAvailability=false;busyResearch=false")
   page.wait("!$('researchSubmit').disabled")
   page.check('recovered sidebar retains English and clears loading',"!/[\\u3400-\\u9fff]/.test([...$('researchPanel').querySelectorAll('*')].filter(e=>!e.closest('.research-source')).flatMap(e=>[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent)).join(' '))&&!$('researchStatus').textContent")
   page.js("researchJob={id:'l2-fixture',status:'queued',created_at:new Date().toISOString()}")
   page.wait("$('researchStatus').textContent.includes('waiting for the model slot')")
   page.js("researchJob.status='running'")
   page.wait("$('researchStatus').textContent.includes('integrating opinions')")
   page.check('running elapsed progress is English',"!/[\\u3400-\\u9fff]/.test([...$('researchPanel').querySelectorAll('*')].filter(e=>!e.closest('.research-source')).flatMap(e=>[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent)).join(' '))")
   page.js("AtlasI18n.setLanguage('zh-TW')")
   page.wait("$('researchStatus').textContent.includes('正在整合觀點')")
   page.js("AtlasI18n.setLanguage('en');failJob=true")
   page.wait("$('researchStatus').textContent.includes('reconnecting: fixture connection lost')")
   page.js("failJob=false;researchJob.status='interrupted';researchJob.error='fixture interrupted'")
   page.wait("$('researchStatus').textContent.includes('Previous results retained')")
   page.check('interrupted result remains localized',"!/[\\u3400-\\u9fff]/.test([...$('researchPanel').querySelectorAll('*')].filter(e=>!e.closest('.research-source')).flatMap(e=>[...e.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent)).join(' '))")
   page.check('reading and language switching never submit model work',"modelWrites.length===0")
  finally:browser.close()

if __name__=='__main__':main()
