"""Offline browser regression for narrow floating tools, chat actions, Wiki evidence context and current price horizon. No provider/model calls.
"""
import json
import os
import signal
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
import websocket
from browser_relations import generate


def main():
    with tempfile.TemporaryDirectory(prefix='atlas-view-relations-') as folder:
        folder=Path(folder);page=folder/'test.html';generate(page)
        html=page.read_text();start=html.rfind('<script>\n(async()=>{try{')
        assert start>0
        page.write_text((html[:start]+'</body></html>').replace('<script>',"<script>localStorage.setItem('graphnews.searchDraft',JSON.stringify({forceRefresh:true}));</script><script>",1))
        log=(folder/'chrome.log').open('w')
        chrome=subprocess.Popen([os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium') or 'google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--window-size=1100,1131','--remote-debugging-port=0','--remote-allow-origins=*','--allow-file-access-from-files','--user-data-dir='+str(folder/'profile'),page.as_uri()],stdout=log,stderr=log,start_new_session=True)
        try:
            portfile=folder/'profile/DevToolsActivePort'
            for _ in range(100):
                if portfile.exists():break
                time.sleep(.05)
            port=int(portfile.read_text().splitlines()[0]);targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json'))
            ws=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'),timeout=45,suppress_origin=True)
            serial=0
            def call(method,params=None):
                nonlocal serial
                serial+=1;ws.send(json.dumps({'id':serial,'method':method,'params':params or {}}))
                while True:
                    result=json.loads(ws.recv())
                    if result.get('id')==serial:
                        if 'error' in result:raise RuntimeError(result['error'])
                        return result.get('result',{})
            def js(code):
                if 'await AtlasWiki.refresh()' in code:code='(async()=>{'+code+'})()'
                result=call('Runtime.evaluate',{'expression':code,'returnByValue':True,'awaitPromise':True})
                if 'exceptionDetails' in result:raise RuntimeError(result['exceptionDetails'])
                return result.get('result',{}).get('value')
            def click(id):
                rect=js(f"(()=>{{const e=document.getElementById({json.dumps(id)});e.scrollIntoView({{block:'nearest'}});const r=e.getBoundingClientRect();return {{x:r.x+r.width/2,y:r.y+r.height/2}};}})()")
                call('Input.dispatchMouseEvent',{'type':'mouseMoved',**rect})
                call('Input.dispatchMouseEvent',{'type':'mousePressed','button':'left','clickCount':1,**rect})
                call('Input.dispatchMouseEvent',{'type':'mouseReleased','button':'left','clickCount':1,**rect});time.sleep(.12)
            for _ in range(100):
                if js("typeof relationUI!=='undefined'&&relationUI!==null"):break
                time.sleep(.05)

            checks={}
            def check(name,code):
                checks[name]=js(code);print(name,checks[name],flush=True)
            js("if(!$('timeFocusBody').hidden)$('timePanelToggle').click()")
            click('timePanelDrag')
            time.sleep(.3)
            check('narrow pane opens by physical click',"!$('timeFocusBody').hidden")
            check('expanded tool fits available stage',"(()=>{const a=$('timeFocusBar').getBoundingClientRect(),s=$('stage').getBoundingClientRect();return a.top>=s.top+100&&a.bottom<=s.bottom+1&&a.left>=s.left&&a.right<=s.right+1})()")
            check('tools remain separate',"(()=>{const a=$('timeFocusBar').getBoundingClientRect(),b=$('sourcePanel').getBoundingClientRect();return a.right<=b.left||b.right<=a.left||a.bottom<=b.top||b.bottom<=a.top})()")
            js(r"""(()=>{
             window.calls=[];const prior=fetch;window.fetch=async(url,options)=>{
              if(!url.startsWith('/api/chat/'))return prior(url,options);
              if(url.endsWith('/turn'))return new Response([{type:'message',text:'我先查看新聞。'},{type:'message',text:'[來源](https://example.test/) 結論'},{type:'done'}].map(v=>JSON.stringify(v)).join('\n')+'\n');
              return {ok:true,json:async()=>url.endsWith('/session')?{token:'fixture'}:{commands:[]}};
             };
             $('chatTab').click();document.querySelector('.chat-compose textarea').value='整理新聞';document.querySelector('.chat-compose').requestSubmit();
            })()""")
            time.sleep(.4)
            check('assistant stream has no copy buttons',"document.querySelectorAll('.chat-message.assistant').length===2&&!document.querySelector('.chat-message button')&&!!document.querySelector('.chat-message a')")
            js(r"""(()=>{
             const factory=ForceGraph3D;window.ForceGraph3D=(...args)=>{window.renderer=factory(...args);return renderer;};
             const a={id:'a',kind:'ArticleRevision',title:'Source'},b={id:'b',kind:'Claim',title:'Claim',assessment:{category:'direct'},market_evidence:[{ticker:'TSLA',horizon:3,mean_return:null,baseline_date:'2026-11-02'}]},c={id:'c',kind:'Thesis',title:'Thesis',assessment:{category:'indirect'}};
             window.fixture={instrument:'NASDAQ:TSLA',version:1,versions:[{version:1,created_at:'2026-11-06'}],total_nodes:3,nodes:[a,b,c],edges:[{source:{stable_id:'a'},target:{stable_id:'b'},relation_type:'SUPPORTS'},{source:{stable_id:'b'},target:{stable_id:'c'},relation_type:'DEPENDS_ON'}],config:{price_horizon:3},jobs:[],perspectives:{categories:{direct:1,indirect:1},index:[]}};
             const prior=fetch;window.fetch=async(url,options)=>{
              if(!url.startsWith('/api/wiki/'))return prior(url,options);calls.push(url);let v={};
              if(url.endsWith('/status'))v={instruments:[{instrument:'NASDAQ:TSLA',version:1}],bridge_ready:true};
              else if(url.endsWith('/models'))v={models:[{id:'fixture',name:'Fixture'}],default_model:'fixture'};
              else if(url.includes('/graph?'))v=fixture;
              else if(url.includes('/jobs?'))v={jobs:[],config:fixture.config,version:1};
              else if(url.includes('/node?'))v={...b,current_market:[{ticker:'TSLA',horizon:Number(new URL(url,'http://fixture').searchParams.get('price_horizon')),mean_return:null,baseline_date:'2026-11-02',as_of:'2026-11-05',available_sessions:3,required_sessions:7}]};
              return {ok:true,json:async()=>v};
             };
             $('priceHorizon').value=3;$('priceHorizon').dispatchEvent(new Event('input'));AtlasWiki.show();
            })()""")
            time.sleep(.3)
            js("$('wikiSaved').value='NASDAQ:TSLA';$('wikiSaved').dispatchEvent(new Event('change'))")
            time.sleep(.3)
            js("$('wikiAssessment').value='direct';$('wikiAssessment').dispatchEvent(new Event('change'))")
            check('category preserves real citation and dependency context',"renderer.graphData().nodes.length===3&&renderer.graphData().links.length===2")
            check('context is visually distinguished',"renderer.graphData().nodes.filter(n=>n.wikiContext).length===2")
            js("renderer.onNodeClick()(renderer.graphData().nodes.find(n=>n.id==='b'))")
            time.sleep(.3)
            check('claim click reads current seven-day data',"calls.some(u=>u.includes('/node?')&&u.includes('price_horizon=7'))")
            check('current market distinguishes available sessions and immutable evidence',"$('wikiDetail').querySelector('.wiki-market-current')?.textContent.includes('7 交易日')&&$('wikiDetail').textContent.includes('3/7')&&!!$('wikiDetail').querySelector('.wiki-market-history')")
            js("$('wikiKind').value='Claim';$('wikiKind').dispatchEvent(new Event('change'))")
            check('explicit kind filter still excludes other kinds',"renderer.graphData().nodes.every(n=>n.kind==='Claim')")
            assert all(checks.values()),checks
        finally:
            os.killpg(chrome.pid,signal.SIGTERM);chrome.wait(timeout=10);log.close()

if __name__=='__main__':main()
