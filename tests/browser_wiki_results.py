"""Published results recover after failed reads; filters and resize never start models."""
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
    rebuild(initialGraph);exportMeta.ticker='TSLA';exportMeta.instrument='NASDAQ:TSLA';window.failGraph=true;window.graphReads=0;window.modelWrites=[];
    window.resultGraph={instrument:'NASDAQ:TSLA',version:1,versions:[{version:1}],nodes:[{id:'n',kind:'Claim',title:'Published evidence',layer:'L1',classification_terms:['topic'],classification_status:'classified'}],edges:[],total_nodes:1,taxonomy:{terms:[{id:'topic',label:'Topic',color:'#7de3bd'}]},opinion_index:[{id:'n',title:'Published evidence',dates:['2026-11-04'],classification_terms:['topic'],classification_status:'classified'}],opinion_groups:{n:['n']},changes:[{version:1,model:'fixture',created_at:'2026-11-04T00:00:00Z',added:1,relations:0,updates:0,titles:Array.from({length:20},(_,i)=>'Saved change '+i)}]};
    window.resultJob={id:'fixture',status:'running',done:0,payload:{model:'fixture',strategy:'root',stage:'compiling',revisions:['a']},usage:{}};
    const prior=fetch;window.fetch=async(url,options)=>{
     if(!url.startsWith('/api/wiki/'))return prior(url,options);
     if(options?.method&&options.method!=='GET'){modelWrites.push(url);throw Error('Unexpected model write');}
     let data={};
     if(url.endsWith('/models'))data={models:[{id:'fixture',name:'Fixture',reasoning:[{reasoningEffort:'low'}]}],default_model:'fixture'};
     else if(url.endsWith('/status'))data={instruments:[{instrument:'NASDAQ:TSLA',version:resultGraph.version}],writable:true,bridge_ready:true};
     else if(url.includes('/graph?')){graphReads++;if(failGraph)throw Error('fixture graph temporarily unavailable');data={...resultGraph,jobs:[resultJob],coverage:{scope_total:10,scope_done:1,scope_pending:9}};}
     else if(url.includes('/jobs?'))data={jobs:[resultJob],config:{},version:resultGraph.version,coverage:{scope_total:10,scope_done:1,scope_pending:9}};
     return {ok:true,json:async()=>data};
    };
   })()""")
   page.js('AtlasWiki.show()');page.wait('graphReads>0');page.js('failGraph=false')
   page.wait("AtlasWiki.runtime.state().counts.loaded===1")
   page.check('initial failed graph read automatically recovers',"graphReads>=2&&AtlasWiki.runtime.state().counts.visible===1")
   page.js("$('wikiAssessment').value='__pending';$('wikiAssessment').dispatchEvent(new Event('change'))")
   page.check('empty view explains published results hidden by classification',"AtlasWiki.runtime.state().counts.visible===0&&$('wikiEmpty').textContent.includes('篩選')&&!!$('wikiEmptyShowPublished')")
   page.js("$('wikiEmptyShowPublished').click()");page.wait("AtlasWiki.runtime.state().counts.visible===1")
   page.check('view published results clears display filters only',"$('wikiAssessment').value===''&&resultJob.status==='running'&&modelWrites.length===0")
   page.js("resultGraph.version=2;resultGraph.versions.unshift({version:2});resultGraph.nodes.push({...resultGraph.nodes[0],id:'n2'});resultGraph.total_nodes=2")
   page.wait("AtlasWiki.runtime.state().version===2&&AtlasWiki.runtime.state().counts.visible===2")
   page.check('published version appears while next segment is running',"resultJob.status==='running'&&$('wikiPublishedResult').textContent.includes('v2')")
   page.js("resultJob.status='cancelled'")
   page.wait("!AtlasWiki.runtime.state().busy.wiki")
   page.check('stopped work keeps published nodes',"AtlasWiki.runtime.state().counts.visible===2")
   page.js("$('wikiVersionInfo').open=true")
   page.wait("!$('wikiResizeChanges').hidden")
   rect=page.js("(()=>{const b=$('wikiResizeChanges'),r=b.getBoundingClientRect();window.oldHeight=$('wikiVersionInfo').getBoundingClientRect().height;return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
   page.call('Input.dispatchMouseEvent',{'type':'mouseMoved',**rect})
   page.call('Input.dispatchMouseEvent',{'type':'mousePressed',**rect,'button':'left','buttons':1,'clickCount':1})
   for step in range(1,7):
    page.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':rect['x'],'y':rect['y']-70*step/6,'button':'left','buttons':1});time.sleep(.02)
   page.call('Input.dispatchMouseEvent',{'type':'mouseReleased','x':rect['x'],'y':rect['y']-70,'button':'left','clickCount':1})
   page.check('changes top boundary physically moves upward',"$('wikiResizeChanges').getBoundingClientRect().y<"+str(rect['y']-30))
   page.check('dragging changes top edge upward increases scrollable height',"$('wikiVersionInfo').getBoundingClientRect().height>oldHeight+30&&getComputedStyle($('wikiVersionInfo')).overflowY==='auto'")
   page.js("window.resizedHeight=$('wikiVersionInfo').getBoundingClientRect().height;AtlasWiki.refresh()")
   page.wait("AtlasWiki.runtime.state().counts.visible===2")
   page.check('results refresh preserves expanded changes height',"$('wikiVersionInfo').open&&Math.abs($('wikiVersionInfo').getBoundingClientRect().height-resizedHeight)<2")
   page.js("window.beforeKey=Number($('wikiResizeChanges').getAttribute('aria-valuenow'));$('wikiResizeChanges').focus()")
   for kind in ('keyDown','keyUp'):page.call('Input.dispatchKeyEvent',{'type':kind,'key':'ArrowDown'})
   page.check('keyboard resize and saved geometry agree',"Number($('wikiResizeChanges').getAttribute('aria-valuenow'))===beforeKey-20&&JSON.parse(localStorage.getItem('stocknexus.wikiLayout')).changes===beforeKey-20")
   page.js("AtlasI18n.setLanguage('en')")
   page.check('new results and resize labels follow language',"$('wikiPublishedResult').textContent.includes('Published v2')&&$('wikiResizeChanges').getAttribute('aria-label')==='Resize version changes'")
   page.check('no inference calls or browser errors',"modelWrites.length===0&&errors.length===0&&languageErrors.length===0")
  finally:browser.close()

if __name__=='__main__':main()
