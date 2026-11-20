"""A failed session is visible beside the submitted prompt and retains retry text."""
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
  window.fetch=async()=>({ok:false,status:403,json:async()=>({error:'Chat 連線未獲授權'})});
  </script><script src="'''+(root/'dist/chat-panel.js').as_uri()+'''"></script>''')
  browser=Browser(folder/'browser')
  try:
   p=browser.page(page.as_uri());p.wait("document.getElementById('chatTab')!==null")
   p.js("document.getElementById('chatTab').click();const input=document.querySelector('textarea');input.value='為什麼股價會下跌？';input.dispatchEvent(new Event('input'));document.querySelector('form').requestSubmit()")
   p.wait("document.querySelector('.chat-send-error')!==null")
   assert p.js("document.querySelector('.chat-message.user .chat-send-error').textContent.includes('未獲授權')")
   assert p.js("document.querySelector('textarea').value==='為什麼股價會下跌？'&&document.querySelector('form').getAttribute('aria-busy')==='false'")
   print('PASS rejected session: adjacent error, retained prompt, busy state cleared')
  finally:browser.close()
if __name__=='__main__':main()
