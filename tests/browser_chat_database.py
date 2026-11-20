"""Database tool commands reach the same-origin API even with no graph loaded."""
import tempfile
from pathlib import Path
from browser_chat_language import Browser

def main():
 with tempfile.TemporaryDirectory() as tmp:
  folder=Path(tmp);root=Path(__file__).resolve().parents[1]
  page=folder/'test.html'
  page.write_text('''<div id="detail"></div><script>
  window.AtlasI18n={t:x=>x,format:(x,v)=>x.replace(/\\{(\\w+)\\}/g,(_,k)=>v[k]),language:()=>"zh-Hant"};
  window.AtlasRuntime={state:()=>({counts:{scope:0},scope_kind:'article',view_mode:'network'}),data:()=>({})};
  window.received=null;window.sent=false;window.apiURL='';
  window.fetch=async(url,options={})=>{const body=options.body?JSON.parse(options.body):{};let result={};
   if(String(url).includes('/api/context/')){window.apiURL=String(url);result={instrument:'NASDAQ:NVDA',items:[{id:'persisted-news'}]};}
   else if(String(url).endsWith('/status'))result={available:true};
   else if(String(url).endsWith('/session'))result={token:'fixture'};
   else if(String(url).endsWith('/sync')){if(body.ack)window.received=body.ack;else if(!window.sent){window.sent=true;result={commands:[{commandId:'db-1',kind:'read_database',params:{resource:'news',instrument:'NASDAQ:NVDA',days:7}}]};}}
   return {ok:true,status:200,json:async()=>result};};
  </script><script src="'''+(root/'dist/chat-panel.js').as_uri()+'''"></script>''')
  browser=Browser(folder/'browser')
  try:
   p=browser.page(page.as_uri());p.wait("document.getElementById('chatTab')!==null")
   p.js("document.getElementById('chatTab').click()")
   p.wait("window.received!==null")
   assert p.js("window.received.result.items[0].id==='persisted-news'")
   assert p.js("window.apiURL.startsWith('/api/context/news?')&&window.apiURL.includes('NASDAQ%3ANVDA')")
   print('PASS real Chromium: empty graph -> DB command -> same-origin GET -> result ack')
  finally:browser.close()
if __name__=='__main__':main()
