"""Browser startup smoke using resources delivered by the actual HTTP Handler.

No listening socket, API keys, external provider calls, or production DB writes.
Missing HTTP assets are omitted exactly as a failed browser resource load would be.
"""
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
import server
from test_server import HTTPTests


def served_document(request, omit=None):
    _, body = request('GET', '/')
    html = body.decode()
    assets = []
    def script(match):
        url = match.group(1)
        head, content = request('GET', url)
        status = int(head.split()[1])
        if omit and url.split('?')[0] == omit:
            status = 404
        assets.append({'url': url, 'status': status})
        if status != 200:
            return '<!-- unavailable asset: ' + url + ' -->'
        return '<script>' + content.decode().replace('</script', '<\\/script') + '</script>'
    html = re.sub(r'<script src="([^"]+)"[^>]*></script>', script, html)
    def stylesheet(match):
        url=match.group(1);head,content=request('GET',url);status=int(head.split()[1])
        assets.append({'url':url,'status':status})
        return '<style>'+content.decode()+'</style>' if status==200 else '<!-- unavailable stylesheet -->'
    html=re.sub(r'<link rel="stylesheet" href="([^"]+)"[^>]*>',stylesheet,html)
    return html, assets


def generate(destination, omit=None):
    harness = HTTPTests()
    harness.setUp()
    try:
        html, assets = served_document(harness.request, omit)
        replies = {}
        for url in ['/api/workspace', '/api/status', '/api/channels', '/api/snapshots', '/schema/news-atlas.schema.json']:
            _, content = harness.request('GET', url)
            replies[url] = json.loads(content)
        with patch.object(server, 'search_events', return_value=iter([{'type': 'done', 'elapsed': 0, 'db': harness.store.stats()}])):
            head, content = harness.request('POST', '/api/search', {'query': 'NVDA', 'sources': ['google'], 'start': '2026-10-28', 'end': '2026-10-28'})
        assert b'200 OK' in head, head
        fixture = '''<script>
window.startupErrors=[];window.addEventListener('error',e=>startupErrors.push(e.message));window.addEventListener('unhandledrejection',e=>startupErrors.push(String(e.reason)));
const startupAssets=ASSETS,startupReplies=REPLIES;let submittedSearches=0,lastSearchBody=null;
window.fetch=async(url,options)=>{
 if(url==='/api/search'){submittedSearches++;lastSearchBody=JSON.parse(options.body);return {ok:true,body:new ReadableStream({start(c){c.enqueue(new TextEncoder().encode(STREAM));c.close()}})}};
 if(url in startupReplies)return {ok:true,json:async()=>startupReplies[url]};
 throw Error('Unexpected startup request: '+url);
};
</script>'''.replace('ASSETS', json.dumps(assets)).replace('REPLIES', json.dumps(replies)).replace('STREAM', json.dumps(content.decode()))
        html = html.replace('<script>', fixture + '<script>', 1)
        qa = '''<script>
(async()=>{try{
 const wait=ms=>new Promise(r=>setTimeout(r,ms));await wait(100);
 const byId=id=>document.getElementById(id),checks={};
 byId('language').value='en';byId('language').dispatchEvent(new Event('change'));await wait(80);
 checks.language=globalThis.AtlasI18n?.language()==='en'&&document.documentElement.lang==='en';
 byId('rssRegion').value='JP';byId('rssRegion').dispatchEvent(new Event('change'));await wait(50);
 checks.regionSync=byId('yahooRegion').textContent==='JP · ja'&&AtlasUI.read('searchDraft',{}).rss_region==='JP';
 byId('dateQuick').click();byId('months-12').click();const quick=AtlasDates.quickRange(12);
 checks.quickDates=byId('start').value===quick.start&&byId('end').value===quick.end&&byId('start').readOnly;
 for(const prefix of ['sourcePanel','timePanel']){
   const panel=byId(prefix==='sourcePanel'?'sourcePanel':'timeFocusBar'),handle=byId(prefix+'Drag'),body=byId(prefix==='sourcePanel'?'sourcePanelBody':'timeFocusBody');
   byId(prefix+'Toggle').click();await wait(30);const folded=panel.getBoundingClientRect();
   checks[prefix+'Compact']=body.hidden&&folded.width<=40&&folded.height<=40;
   panel.setPointerCapture=()=>{};panel.hasPointerCapture=()=>false;
   const pointer=(name,x,y)=>new PointerEvent(name,{pointerId:7,button:0,clientX:x,clientY:y,bubbles:true,cancelable:true});
   handle.dispatchEvent(pointer('pointerdown',folded.left+18,folded.top+18));handle.dispatchEvent(pointer('pointermove',folded.left-32,folded.top-32));handle.dispatchEvent(pointer('pointerup',folded.left-32,folded.top-32));
   const moved=panel.getBoundingClientRect();checks[prefix+'Move']=Math.hypot(moved.left-folded.left,moved.top-folded.top)>5;
   handle.click();await wait(30);checks[prefix+'Expand']=!body.hidden;
   byId(prefix+'Reset').click();
 }
 const source=byId('sourcePanel'),time=byId('timeFocusBar');
 const separate=()=>{const a=source.getBoundingClientRect(),b=time.getBoundingClientRect();return a.right+7.5<=b.left||b.right+7.5<=a.left||a.bottom+7.5<=b.top||b.bottom+7.5<=a.top;};
 const dragPanel=(panel,dx,dy,target=panel)=>{panel.setPointerCapture=()=>{};panel.hasPointerCapture=()=>false;for(const [name,x,y] of [['pointerdown',0,0],['pointermove',dx,dy],['pointerup',dx,dy]])target.dispatchEvent(new PointerEvent(name,{pointerId:8,button:0,clientX:x,clientY:y,bubbles:true,cancelable:true}));};
 let before=source.getBoundingClientRect();dragPanel(source,30,20);let after=source.getBoundingClientRect();
 checks.backgroundDrag=Math.hypot(after.left-before.left,after.top-before.top)>5;
 before=source.getBoundingClientRect();dragPanel(source,100,80,byId('rootQuery'));after=source.getBoundingClientRect();checks.inputNotDragged=before.left===after.left&&before.top===after.top;
 const target=time.getBoundingClientRect();dragPanel(source,target.left-after.left,target.top-after.top);checks.expandedCollision=separate();
 for(const [id,body] of [['sourcePanelToggle','sourcePanelBody'],['timePanelToggle','timeFocusBody']])if(!byId(body).hidden)byId(id).click();
 before=source.getBoundingClientRect();const compactTarget=time.getBoundingClientRect();dragPanel(source,compactTarget.left-before.left,compactTarget.top-before.top);checks.compactCollision=separate();
 byId('sourcePanelDrag').click();await wait(30);checks.expandCollision=separate();
 byId('timePanelDrag').click();await wait(30);checks.secondExpandCollision=separate();
 byId('sourcePanelReset').click();byId('timePanelReset').click();
 if(!startupAssets.some(x=>x.status!==200)){
   const panel=byId('timeFocusBar');let round=true;
   for(const width of [310,480]){panel.style.width=width+'px';timeLens.paint();await wait(40);const dot=byId('timeBellHandle').getBoundingClientRect();round&&=Math.abs(dot.width-dot.height)<.6&&dot.width>14;}
   panel.style.width='';timeLens.paint();checks.roundHandle=round;
 }

 const stage=byId('stage'),originalStyle=stage.getAttribute('style')||'';
 stage.style.width='280px';stage.style.height='200px';byId('sourcePanelReset').click();timePanel.constrain();await wait(100);
 checks.smallStageCollision=separate();
 checks.smallStageCompact=byId('sourcePanelBody').hidden||byId('timeFocusBody').hidden;
 stage.setAttribute('style',originalStyle);timePanel.constrain();await wait(100);checks.restoredStageCollision=separate();
 byId('massiveHelpButton').click();checks.help=byId('massiveHelp').open&&byId('massiveDashboard').href==='https://massive.com/dashboard';
 byId('closeMassiveHelp').click();checks.helpClose=!byId('massiveHelp').open;
 let intercepted=false;byId('form').addEventListener('submit',e=>{intercepted=e.defaultPrevented;e.preventDefault();});
 byId('query').value='NVDA';byId('source-google').checked=true;byId('submit').click();await wait(200);
 checks.search=intercepted&&submittedSearches===1&&!byId('submit').disabled;checks.regionRequest=lastSearchBody?.rss_region==='JP';
 const missingLens=startupAssets.some(x=>x.url.split('?')[0]==='/time-lens.js'&&x.status!==200);
 if(missingLens)checks.degradedNotice=!byId('timeLensStatus').hidden&&byId('timeSizeEnabled').disabled;
 const report={checks,errors:startupErrors,failedAssets:startupAssets.filter(x=>x.status!==200)};
 document.body.dataset.qa=(Object.values(checks).every(Boolean)&&!startupErrors.length?'PASS: ':'FAIL: ')+JSON.stringify(report);
}catch(e){document.body.dataset.qa='FAIL: '+e.message+' '+JSON.stringify(startupErrors);}finally{document.querySelectorAll('script').forEach(s=>s.remove());}})();
</script>'''
        Path(destination).write_text(html.replace('</body>', qa + '</body>'))
        print(json.dumps({'assets': len(assets), 'failed': [a for a in assets if a['status'] != 200]}))
    finally:
        harness.tearDown()


if __name__ == '__main__':
    generate(sys.argv[1] if len(sys.argv) > 1 else '/tmp/graphnews-startup.html', sys.argv[2] if len(sys.argv) > 2 else None)
