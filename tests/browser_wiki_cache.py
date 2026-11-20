"""Real SQLite, HTTP, browser and News→Wiki entry. Only publication uses a fixture model."""
import json
import os
from pathlib import Path
import tempfile
import threading

import server
from browser_chat_language import Browser
from news_atlas.graph_storage import GraphRepository
from news_atlas.search import query_key
from news_atlas.wiki.compiler import WikiService
from test_server import row
from test_wiki import proposal


def main():
    with tempfile.TemporaryDirectory(prefix='wiki-cache-') as tmp:
        folder = Path(tmp)
        news = GraphRepository(folder/'data/news.sqlite3')
        calls = []
        def runner(store, job, article, context):
            calls.append(store.instrument)
            return {'proposal':proposal(article),'usage':{}}
        wiki = WikiService(news, runner=runner, start_worker=False)
        wiki.bridge_request = lambda *args, **kw: {'wiki_ready':True,'models':[{'id':'fixture','name':'Fixture'}],'default_model':'fixture'}
        def evidence(symbol, suffix):
            return row('massive',title=symbol+' evidence '+suffix, day='2026-11-04', suffix=symbol+suffix, symbols=[symbol])
        def publish(symbol, suffix):
            article=evidence(symbol,suffix)
            plan=wiki.plan({'instrument':'NASDAQ:'+symbol,'model':'fixture','articles':[article]})
            wiki.start({'plan_id':plan['plan_id']})
            wiki.process(wiki.store('NASDAQ:'+symbol))
        for symbol in ('TSLA','AAPL','MSFT'):
            news.for_ticker(symbol).save('massive',query_key('massive',symbol),[evidence(symbol,'one')],[])
        publish('TSLA','one');publish('AAPL','one')
        class Handler(server.Handler):
            def log_message(self, *args): pass
        http = server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        http.store=news;http.wiki=wiki
        url='http://127.0.0.1:'+str(http.server_port)
        os.environ['NEWS_ATLAS_WIKI_ORIGINS']=url
        threading.Thread(target=http.serve_forever,daemon=True).start()
        browser=Browser(folder/'chrome')
        try:
            page=browser.page(url)
            page.wait("typeof AtlasWiki!=='undefined'&&!workspaceRestoring")
            page.js("""window.reads=[];window.writes=[];window.holdState=false;window.holdGraph=false;
                const originalFetch=fetch;
                window.fetch=async(url,options)=>{
                 const path=String(url);if(!path.startsWith('/api/wiki/'))return originalFetch(url,options);
                 if(options?.method==='POST')writes.push(path);
                 if(path.includes('/jobs?')&&holdState)await new Promise(r=>window.releaseState=r);
                 const r=await originalFetch(url,options);
                 if(path.includes('/graph?')){
                  const v=await r.clone().json();
                  reads.push({path,kind:v.kind,stock:v.instrument,upserts:v.rows?.nodes?.upsert?.length,full:!!v.graph});
                  if(holdGraph)await new Promise(r=>window.releaseGraph=r);
                 }
                 return r;
                };void 0""")
            def confirm(symbol):
                data=json.dumps(server.graph_payload([evidence(symbol,'one')]))
                page.js('pendingSearchMeta='+json.dumps({'instrument':'NASDAQ:'+symbol,'ticker':symbol})+';acceptSearchGraph('+data+',true)')
            confirm('TSLA')
            page.js("$('ticker').value='NASDAQ:AAPL'")
            page.wait("reads.length===1")
            page.check('confirmed stock prefetched once in News despite a different draft',
                       "$('wikiPanel').hidden&&reads[0].stock==='NASDAQ:TSLA'&&reads[0].kind==='full'&&writes.length===0")
            publish('TSLA','two')
            page.js('holdState=true;void AtlasWiki.show()')
            page.wait("typeof releaseState==='function'")
            page.check('warm v1 is visible while fresh status is held',
                       "!$('wikiPanel').hidden&&AtlasWiki.runtime.state().version===1&&AtlasWiki.runtime.state().counts.visible===2")
            page.js('holdState=false;releaseState()')
            page.wait("AtlasWiki.runtime.state().version===2")
            page.check('new publication arrives as a patch',
                       "reads.length===2&&reads[1].kind==='delta'&&reads[1].upserts===2&&!reads[1].full&&AtlasWiki.runtime.state().counts.loaded===4")
            page.js("$('wikiBack').click();void AtlasWiki.show()")
            page.wait("reads.at(-1).kind==='unchanged'")
            page.check('unchanged revisit transfers no graph body', "reads.filter(r=>r.full).length===1&&writes.length===0")
            page.js("$('wikiVersion').value='1';$('wikiVersion').dispatchEvent(new Event('change'))")
            page.wait("AtlasWiki.runtime.state().version===1&&reads.at(-1).kind==='full'")
            page.js("$('wikiKind').value='Claim';$('wikiKind').dispatchEvent(new Event('change'));$('wikiBack').click()")
            page.js('holdGraph=true');confirm('AAPL');page.wait("reads.at(-1).stock==='NASDAQ:AAPL'")
            publish('AAPL','two')
            page.js('holdGraph=false')
            page.js("void AtlasWiki.show()")
            page.js("new Promise(r=>setTimeout(r,100))");page.js('releaseGraph()')
            page.wait("AtlasWiki.runtime.state().version===2&&AtlasWiki.runtime.data().nodes.some(n=>n.title.includes('AAPL'))")
            page.check('in-flight prefetch is shared and an intervening publication is caught',
                       "reads.filter(r=>r.stock==='NASDAQ:AAPL'&&r.full).length===1&&reads.some(r=>r.stock==='NASDAQ:AAPL'&&r.kind==='delta')")
            page.check('stock switch shows only the matching Wiki',
                       "AtlasWiki.runtime.state().instrument==='NASDAQ:AAPL'&&!AtlasWiki.runtime.data().nodes.some(n=>n.title.includes('TSLA'))")
            page.js("$('wikiBack').click()");confirm('TSLA')
            page.js("void AtlasWiki.show()")
            page.wait("AtlasWiki.runtime.state().instrument==='NASDAQ:TSLA'&&AtlasWiki.runtime.state().version===1&&$('wikiKind').value==='Claim'")
            page.check('return to the first stock restores its pinned version and display filter',
                       "$('wikiVersion').value==='1'&&AtlasWiki.runtime.state().counts.visible===1")
            # Hold an outgoing TSLA read through an entire navigation to AAPL.
            page.js("holdGraph=true;void AtlasWiki.refresh()")
            page.wait("typeof releaseGraph==='function'")
            page.js("$('wikiBack').click();holdGraph=false");confirm('AAPL')
            page.js("void AtlasWiki.show()");page.wait("AtlasWiki.runtime.data().nodes.some(n=>n.title.includes('AAPL'))")
            page.js("releaseGraph()")
            page.check('late old-stock response cannot replace the current view',
                       "AtlasWiki.runtime.state().instrument==='NASDAQ:AAPL'&&!AtlasWiki.runtime.data().nodes.some(n=>n.title.includes('TSLA'))")
            page.js("$('wikiBack').click()");confirm('MSFT')
            page.js("new Promise(r=>setTimeout(r,350))")
            page.check('an absent Wiki never receives a graph read or model submission',
                       "!reads.some(r=>r.stock==='NASDAQ:MSFT')&&!writes.length&&!languageErrors.length")
            page.js('void AtlasWiki.show()')
            page.wait("!$('wikiPanel').hidden&&!$('wikiSaved').value&&AtlasWiki.runtime.state().counts.loaded===0")
            page.check('opening News without a matching Wiki leaves the prior graph out of view',
                       "!AtlasWiki.runtime.data().nodes.length&&!writes.length")
            assert not (wiki.root/'MSFT/wiki.sqlite3').exists()
            assert calls==['NASDAQ:TSLA','NASDAQ:AAPL','NASDAQ:TSLA','NASDAQ:AAPL'], calls
        finally:
            browser.close();http.shutdown();http.server_close();wiki.close()


if __name__=='__main__': main()
