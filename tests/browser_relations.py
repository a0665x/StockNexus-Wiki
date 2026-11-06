"""Offline browser integration using real HTTP-served assets and graph-build responses."""
import json
from pathlib import Path
import sys
from browser_startup import served_document
import test_server
from test_relation_settings import rows
from news_atlas.relation_settings import settings, UNIFIED
import server


def generate(destination):
    harness=test_server.HTTPTests();harness.setUp()
    try:
        html,assets=served_document(harness.request)
        graph=server.graph_payload(rows())
        replies={}
        for url in ['/api/workspace','/api/status','/api/channels','/api/snapshots','/schema/news-atlas.schema.json']:
            _,body=harness.request('GET',url);replies[url]=json.loads(body)
        variants={}
        for key,cfg in [('off',{**UNIFIED,'entity':False,'topic':False,'title':False}),('unified',UNIFIED),('original',settings())]:
            head,body=harness.request('POST','/api/graph/build',{'source_graphs':graph['source_graphs'],'relation_settings':cfg})
            assert b'200' in head
            variants[key]=json.loads(body)
        fixture='''<script>
const errors=[];window.addEventListener('error',e=>errors.push(e.message));window.addEventListener('unhandledrejection',e=>errors.push(String(e.reason)));
const replies=REPLIES,variants=VARIANTS,initialGraph=GRAPH;let buildCalls=0,failBuild=false;
window.fetch=async(url,options)=>{
 if(url==='/api/graph/build'){buildCalls++;const cfg=JSON.parse(options.body).relation_settings;await new Promise(r=>setTimeout(r,200));return {ok:!failBuild,json:async()=>failBuild?{error:'deliberate test error'}:variants[!cfg.entity&&!cfg.topic&&!cfg.title?'off':cfg.adaptive?'unified':'original']};}
 if(url in replies)return {ok:true,json:async()=>replies[url]};throw Error('Unexpected request: '+url);
};</script>'''.replace('REPLIES',json.dumps(replies)).replace('VARIANTS',json.dumps(variants)).replace('GRAPH',json.dumps(graph))
        html=html.replace('<script>',fixture+'<script>',1)
        qa='''<script>
(async()=>{try{
 const wait=ms=>new Promise(r=>setTimeout(r,ms)),checks={};await wait(100);
 rebuild(initialGraph);await wait(500);const originalIds=articles.map(a=>a.id).sort().join(','),nodes=graph?.graphData().nodes.slice();
 const root=articles.find(a=>a.source.provider==='google');showArticle(root);const roots=lockedRoots.slice();
 $('relationOpen').click();checks.dialog=$('relationDialog').open;
 checks.singleApply=!document.getElementById('relationBaseline')&&!document.getElementById('relationPreset')&&!document.getElementById('relationDraftRules');
 for(const k of ['entity','topic','title'])$('relation-'+k).checked=false;
 $('relationApply').click();checks.progress=!$('relationSpinner').hidden&&!$('relationProgress').hidden&&!$('relationProgress').hasAttribute('value');await wait(400);
 checks.isolatesRetained=articles.map(a=>a.id).sort().join(',')===originalIds&&relations.length===0;
 checks.noSummary=$('relationStatus').hidden&&!$('relationStatus').textContent;
 checks.nodeIdentity=!graph||graph.graphData().nodes.every((n,i)=>n===nodes[i]);checks.roots=lockedRoots.join(',')===roots.join(',');
 checks.snapshot=savedPayload().view.relation_settings.entity===false;
 for(const k of ['entity','topic','title'])$('relation-'+k).checked=true;
 $('relationApply').click();await wait(400);const edges=relations.length;
 failBuild=true;$('relationApply').click();await wait(400);checks.failureRetainsGraph=relations.length===edges&&$('relationStatus').textContent.includes('未套用');failBuild=false;
 checks.noErrors=errors.length===0;
 document.body.dataset.qa=(Object.values(checks).every(Boolean)?'PASS: ':'FAIL: ')+JSON.stringify({checks,errors});
}catch(e){document.body.dataset.qa='FAIL: '+e.stack;}finally{document.querySelectorAll('script').forEach(s=>s.remove());}})();
</script>'''
        Path(destination).write_text(html.replace('</body>',qa+'</body>'))
        print(json.dumps({'assets':len(assets),'failed':[x for x in assets if x['status']!=200]}))
    finally:harness.tearDown()

if __name__=='__main__':generate(sys.argv[1])
