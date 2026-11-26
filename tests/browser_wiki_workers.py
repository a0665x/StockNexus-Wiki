"""Worker disclosure, tree units, settings and navigation in real Chromium."""
import json,tempfile
from pathlib import Path
from browser_relations import generate
from browser_chat_language import Browser


def main():
 with tempfile.TemporaryDirectory(prefix='wiki-workers-') as tmp:
  folder=Path(tmp);html=folder/'fixture.html';generate(html)
  source=html.read_text();html.write_text(source[:source.rfind('<script>\n(async()=>{try{')]+'</body></html>')
  browser=Browser(folder/'browser')
  try:
   page=browser.page(html.as_uri());page.wait("typeof AtlasWiki!=='undefined'")
   page.js("""(()=>{
    rebuild(initialGraph);exportMeta.ticker='TSLA';exportMeta.instrument='NASDAQ:TSLA';
    const members=focusView.articles.slice(0,3);
    window.workerTrees=members.map((a,i)=>({root_id:a.id,title:'Evidence tree '+(i+1),articles:[{id:a.article_id||a.id,provider:a.source.provider}],targets:[{id:a.article_id||a.id,provider:a.source.provider}]}));
    window.workerJob={id:'fixture',status:'running',done:3,usage:{},payload:{workers:3,strategy:'root',revisions:Array(10).fill('a'),model:'gpt-6.1-sol',graph_selection:{mode:'coverage',trees:workerTrees},workers_state:Object.fromEntries(workerTrees.map((tree,i)=>[i+1,{status:'running',stage:'compiling',sdk_stage:i===1?'awaiting_model':'answer_event',sdk_quiet_minutes:0,model:'gpt-6.1-sol',root_id:tree.root_id,tree:i+1,total_trees:3,parts:4,completed_parts:i,targets:3,context_articles:4}]))}};
    window.workerWrites=[];const prior=window.fetch;window.fetch=async(url,options)=>{
     if(!url.startsWith('/api/wiki/'))return prior(url,options);
     if(options?.method&&options.method!=='GET'){workerWrites.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({status:'saved'})};}
     let data={};const cfg={workers:3,strategy:'root',model:'gpt-6.1-sol',reasoning_effort:'medium',languages:['zh-Hant','en'],graph_selection:workerJob.payload.graph_selection};
     const coverage={scope_total:9000,scope_done:1380,scope_pending:7620,trees:{total:1170,done:15,pending:1155}};
     if(url.endsWith('/models'))data={models:[{id:'gpt-6.1-sol',name:'GPT-6.1 Sol',reasoning:[{reasoningEffort:'medium'}]}]};
     else if(url.endsWith('/status'))data={instruments:[{instrument:'NASDAQ:TSLA',version:181}],writable:true,bridge_ready:true};
     else if(url.includes('/graph?'))data={instrument:'NASDAQ:TSLA',version:181,versions:[{version:181}],nodes:[],edges:[],total_nodes:0,jobs:[workerJob],config:cfg,coverage};
     else if(url.includes('/jobs?'))data={jobs:[workerJob],config:cfg,version:181,coverage};
     return {ok:true,json:async()=>data};
    };
   })()""")
   page.js('AtlasWiki.show()');page.wait("!!document.getElementById('wikiWorkerProgress')")
   def click(selector):
    xy=page.js("(()=>{const e=document.querySelector("+json.dumps(selector)+");e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
    for kind in ('mouseMoved','mousePressed','mouseReleased'):page.call('Input.dispatchMouseEvent',{'type':kind,**xy,'button':'left','clickCount':1})
   page.check('primary coverage counts completed trees; article coverage remains visible',"$('wikiCoverage').textContent.includes('15/1170')&&$('wikiCoverage').textContent.includes('1380/9000')")
   click('#wikiWorkerProgress summary')
   page.check('real pointer expands three progress rows',"$('wikiWorkerProgress').open&&document.querySelectorAll('.wiki-worker-row').length===3")
   page.check('bars use saved segments, not tree ordinals',"[...document.querySelectorAll('.wiki-worker-row progress')].every((p,i)=>p.max===4&&p.value===i)")
   page.js("workerJob.payload.workers_state[2].sdk_quiet_minutes=2;workerJob.payload.failed_tree_count=1;workerJob.payload.last_tree_failure={tree:9,part:1,code:'timeout',sdk_stage:'awaiting_model'};AtlasWiki.refresh()")
   page.wait("$('wikiWorkerProgress').textContent.includes('距上次事件 2 分鐘')")
   page.check('isolated tree failure leaves siblings active', "$('wikiLive').textContent.includes('1 棵樹待重試，其餘樹繼續整理')")
   page.check('disclosure survives refresh',"$('wikiWorkerProgress').open")
   page.js("AtlasI18n.setLanguage('en')")
   page.check('worker labels and units translate',"$('wikiCoverage').textContent.includes('News trees completed')&&$('wikiWorkerProgress').textContent.includes('Turn started, waiting for first output event')&&$('wikiWorkerProgress').textContent.includes('Tree segments saved')")
   click('.wiki-worker-row[data-worker="2"] button')
   page.check('worker root link reads exact frozen membership without writes',"$('wikiPanel').hidden&&wikiRootPreview!==null&&activeTrace.nodes.size===1&&workerWrites.length===0")
   page.js('AtlasWiki.show()');page.wait("!$('wikiPanel').hidden")
   click('#relationOpen')
   page.check('settings offer 1 3 5 10 and restore selected concurrency',"[...$('wikiWorkers').options].map(o=>o.value).join(',')==='1,3,5,10'&&$('wikiWorkers').value==='3'")
   page.js("$('wikiWorkers').value='5';$('wikiWorkers').dispatchEvent(new Event('input',{bubbles:true}))")
   page.check('concurrency change produces actionable settings',"!$('wikiApply').hidden&&!$('wikiWorkers').disabled")
   page.js("$('wikiSettings').close()")
   # Desktop and mobile are inspected in this one bounded pass.
   page.js("$('wikiLive').scrollTop=0")
   import base64
   image=page.call('Page.captureScreenshot',{'format':'png'})
   Path('/tmp/wiki-workers-desktop.png').write_bytes(base64.b64decode(image['data']))
   page.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
   page.js("$('wikiWorkerProgress').open=true;$('wikiLive').scrollTop=0")
   page.check('mobile has no horizontal page overflow',"document.documentElement.scrollWidth<=innerWidth+1")
   image=page.call('Page.captureScreenshot',{'format':'png'})
   Path('/tmp/wiki-workers-mobile.png').write_bytes(base64.b64decode(image['data']))
   page.check('no JS errors or accidental model submissions',"errors.length===0&&languageErrors.length===0&&workerWrites.length===0")
  finally:browser.close()

if __name__=='__main__':main()
