"""User journeys with real HTTP-served assets, isolated transport and Chromium.
No provider calls, paid inference or production writes.
"""
import json,tempfile,base64
from pathlib import Path
from browser_relations import generate
from browser_chat_language import Browser

def main():
 with tempfile.TemporaryDirectory(prefix='wiki-unslop-') as tmp:
  folder=Path(tmp);html=folder/'fixture.html';generate(html)
  source=html.read_text();html.write_text(source[:source.rfind('<script>\n(async()=>{try{')]+'</body></html>')
  browser=Browser(folder/'browser')
  try:
   page=browser.page(html.as_uri());page.wait("typeof AtlasWiki!=='undefined'")
   setup="""(()=>{
    rebuild(initialGraph);exportMeta.ticker='TSLA';exportMeta.instrument='NASDAQ:TSLA';
    localStorage.setItem('stocknexus.wikiRuntime',JSON.stringify({instrument:'NASDAQ:AAPL',controls:{wikiVersion:'999'}}));
    window.fixtureWrites=[];window.fixtureConversations=JSON.parse(localStorage.getItem('fixture.history')||'[]');window.currentChat=null;
    const prior=fetch;window.fetch=async(url,opts)=>{
     const body=opts?.body?JSON.parse(opts.body):{};let value={};
     if(url.startsWith('/api/wiki/')){
      if(opts?.method==='POST')fixtureWrites.push({url,body});
      if(url.endsWith('/status'))value={instruments:[{instrument:'NASDAQ:TSLA',version:7},{instrument:'NASDAQ:AAPL',version:8}],news_databases:[{instrument:'NASDAQ:TSLA',ticker:'TSLA',articles:10},{instrument:'NASDAQ:AAPL',ticker:'AAPL',articles:10}],writable:true,bridge_ready:true};
      if(url.endsWith('/models'))value={models:[{id:'fixture',name:'Fixture',reasoning:[{reasoningEffort:'medium'}]}]};
      const instrument=new URL(url,'https://fixture.test').searchParams.get('instrument');
      const cfg={enabled:false,model:'fixture',reasoning_effort:'medium',strategy:'root',workers:3};
      if(url.includes('/graph?'))value={instrument,version:7,versions:[{version:7}],nodes:[],edges:[],total_nodes:0,config:cfg,jobs:[],coverage:{scope_total:9000,scope_done:1380,scope_pending:7620,trees:{total:1170,done:15,pending:1155}}};
      if(url.includes('/jobs?'))value={version:7,config:cfg,jobs:[],coverage:{scope_total:9000,scope_done:1380,scope_pending:7620,trees:{total:1170,done:15,pending:1155}}};
      if(url.endsWith('/plan')){await new Promise(r=>window.releasePlan=r);value={plan_id:'plan'};}
      if(url.endsWith('/jobs'))value={job_id:'job'};
     }else if(url.startsWith('/api/chat/')){
      if(url.endsWith('/session'))value={token:'fixture-session',owner:'fixture-owner'};
      if(url.endsWith('/models'))value={models:[{id:'fixture',name:'Fixture'}]};
      if(url.endsWith('/sync'))value={commands:[]};
      if(url.endsWith('/history'))value={conversations:fixtureConversations};
      if(url.endsWith('/reset'))currentChat=null;
      if(url.endsWith('/conversation')){const item=fixtureConversations.find(x=>x.id===body.id);if(body.action==='open'){currentChat=item.id;value={conversation:item};}else {fixtureConversations=fixtureConversations.filter(x=>x.id!==body.id);localStorage.setItem('fixture.history',JSON.stringify(fixtureConversations));value={deleted:body.id};}}
      if(url.endsWith('/turn')){
       let item=fixtureConversations.find(x=>x.id===currentChat);if(!item){currentChat='chat-'+(fixtureConversations.length+1);item={id:currentChat,title:body.message,instrument:'NASDAQ:TSLA',updated_at:'2026-11-20T04:00:00Z',messages:[]};fixtureConversations.push(item);}
       item.messages.push({role:'user',text:body.message},{role:'assistant',text:'A saved answer with [evidence](https://example.test/evidence)'});localStorage.setItem('fixture.history',JSON.stringify(fixtureConversations));
       return new Response([{type:'conversation',id:currentChat},{type:'message',text:item.messages.at(-1).text},{type:'done'}].map(x=>JSON.stringify(x)+'\\n').join(''),{headers:{'Content-Type':'application/x-ndjson'}});
      }
     }else return prior(url,opts);
     return {ok:true,json:async()=>value};
    };
   })()"""
   page.js(setup);page.js('AtlasWiki.show()');page.wait("$('wikiSaved').value==='NASDAQ:TSLA'&&$('wikiStart').disabled===false")
   page.check('News identity overrides remembered Wiki and stale version',"$('wikiSaved').value==='NASDAQ:TSLA'&&$('wikiInstrument').value==='NASDAQ:TSLA'&&$('wikiVersion').value===''&&fixtureWrites.length===0")
   page.js("$('wikiBack').click();exportMeta.ticker='AAPL';exportMeta.instrument='NASDAQ:AAPL';AtlasWiki.show()")
   page.wait("$('wikiSaved').value==='NASDAQ:AAPL'")
   page.check('returning from another News stock aligns again without model work',"$('wikiInstrument').value==='NASDAQ:AAPL'&&fixtureWrites.length===0")
   page.js("$('ticker').value='NASDAQ:NVDA';$('wikiBack').click();AtlasWiki.show()")
   page.wait("!$('wikiPanel').hidden")
   page.check('unsubmitted search draft cannot change Wiki binding',"$('wikiSaved').value==='NASDAQ:AAPL'")
   page.js("$('wikiStart').click();$('wikiStart').click()")
   page.wait("!!window.releasePlan&&$('wikiStatus').textContent.includes('秒')")
   page.check('preparation shows elapsed stage and double clicks submit once',"fixtureWrites.filter(x=>x.url.endsWith('/plan')).length===1&&$('wikiStart').disabled")
   page.js('releasePlan()');page.wait("fixtureWrites.some(x=>x.url.endsWith('/jobs'))&&!$('wikiStart').disabled")
   page.js("$('wikichatTab').click()")
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent.includes('已連線')")
   def send(text):
    page.js("(()=>{const input=document.querySelector('#wikichatPage textarea');input.value="+json.dumps(text)+";input.dispatchEvent(new Event('input'));input.form.requestSubmit();})()")
    page.wait("document.querySelector('#wikichatPage .chat-status').textContent.includes('完成')")
   send('Compare the cited evidence')
   page.js("$('wikichatHistoryToggle').click()")
   page.wait("document.querySelectorAll('#wikichatHistory .chat-history-row').length===1")
   page.check('first turn creates a named history row and delete icon',"document.querySelector('#wikichatHistory').textContent.includes('Compare the cited evidence')&&!!document.querySelector('.chat-history-delete svg')")
   page.js("[...document.querySelectorAll('#wikichatPage .chat-toolbar button')].find(x=>x.textContent==='新對話').click()")
   page.wait("document.querySelectorAll('#wikichatPage .chat-message').length===0")
   send('A second research question')
   page.js("document.querySelector('#wikichatHistory .chat-history-open').click()")
   page.wait("document.querySelector('#wikichatPage .chat-status').textContent.includes('歷史對話')")
   page.check('opening history restores messages without starting a turn',"document.querySelectorAll('#wikichatPage .chat-message').length===2&&fixtureConversations.length===2")
   send('Continue that first conversation')
   page.check('continuation appends to the selected conversation',"fixtureConversations[0].messages.length===4&&fixtureConversations.length===2")
   # Render one screenshot of the approved direction and retain a reload fixture.
   page.js("AtlasI18n.setLanguage('en')")
   page.check('history labels follow UI language without rewriting content',"$('wikichatHistoryToggle').textContent==='History'&&document.querySelector('#wikichatHistory').textContent.includes('Compare the cited evidence')")
   page.check('workbench palette is served and controls fit',"getComputedStyle(document.body).backgroundColor==='rgb(20, 22, 23)'&&document.documentElement.scrollWidth<=innerWidth+1")
   Path('/tmp/unslop-desktop.png').write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
   page.call('Page.reload');page.wait("typeof AtlasWiki!=='undefined'");page.js(setup);page.js('AtlasWiki.show()');page.wait("$('wikiSaved').value==='NASDAQ:TSLA'");page.js("$('wikichatTab').click()")
   page.wait("document.querySelectorAll('#wikichatPage .chat-message').length===4")
   page.check('reload reopens the selected persisted conversation',"document.querySelector('#wikichatPage .chat-messages').textContent.includes('Continue that first conversation')")
   page.js("$('wikichatHistoryToggle').click();window.confirm=()=>false")
   page.wait("document.querySelectorAll('.chat-history-delete').length===2")
   page.js("document.querySelector('.chat-history-delete').click()")
   page.check('cancelled deletion preserves history',"fixtureConversations.length===2")
   page.js("window.confirm=()=>true;document.querySelector('.chat-history-delete').click()")
   page.wait('fixtureConversations.length===1')
   page.check('confirmed deletion removes active messages and history row',"document.querySelectorAll('#wikichatPage .chat-message').length===0&&document.querySelectorAll('.chat-history-row').length===1")
   page.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
   page.check('mobile layout stays within viewport',"document.documentElement.scrollWidth<=innerWidth+1")
   Path('/tmp/unslop-mobile.png').write_bytes(base64.b64decode(page.call('Page.captureScreenshot',{'format':'png'})['data']))
   page.check('no JavaScript errors',"errors.length===0&&languageErrors.length===0")
  finally:browser.close()
if __name__=='__main__':main()
