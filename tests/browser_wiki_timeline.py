"""Exercise the Wiki timeline and comparison with trusted Chromium input."""
import json
import tempfile
import time
from pathlib import Path

from browser_chat_language import Browser
from browser_relations import generate


SETUP = """
rebuild(initialGraph);
exportMeta.instrument='NASDAQ:TSLA';exportMeta.ticker='TSLA';
window.wikiPosts=[];
const instrument='NASDAQ:TSLA', labels=['能源','需求'], terms=labels.map((label,i)=>({
 id:['energy','demand'][i],label,translations:{en:{label:['Energy','Demand'][i]}},color:['#79daba','#e4ad75'][i]
}));
const rows=Array.from({length:100},(_,i)=>{
 const date=new Date(Date.UTC(2026,7,1+i)).toISOString().slice(0,10);
 return {id:'thesis-'+i,title:'Viewpoint '+i,kind:'Thesis',dates:[date],classification_terms:[terms[i%2].id]};
});
const value={instrument,version:124,versions:[{version:124}],nodes:rows,edges:[],total_nodes:rows.length,
 taxonomy:{terms},opinion_index:rows,jobs:[],config:{enabled:false}};
const oldFetch=fetch;window.fetch=async(url,opts)=>{
 const path=String(url);
 if(path.startsWith('/api/context/graph?')){
  const offset=Number(new URL(path,'https://fixture.test').searchParams.get('offset'));
  return {ok:true,json:async()=>({version:124,total:rows.length,items:rows.slice(offset,offset+20),next_offset:offset+20<rows.length?offset+20:null})};
 }
 if(!path.startsWith('/api/wiki/'))return oldFetch(url,opts);
 if(opts?.method==='POST')wikiPosts.push(path);
 let packet={};
 if(path.endsWith('/status'))packet={instruments:[{instrument,version:124}],news_databases:[{instrument,ticker:'TSLA',articles:100}],writable:true,bridge_ready:true};
 if(path.endsWith('/models'))packet={models:[{id:'fixture',name:'Fixture'}]};
 if(path.includes('/graph?'))packet=value;
 if(path.includes('/jobs?'))packet={version:124,jobs:[],config:value.config};
 if(path.includes('/comparison-candidates?'))packet={items:rows.slice(0,2).map(n=>({origin:'L1 · v124',title:'能源與需求前景的觀點比較'.repeat(8)+n.id,ref:n.id})),next_offset:null};
 if(path.includes('/comparisons?'))packet={jobs:[{id:'j',first_statement:'能源供給與需求變化'.repeat(6),second_statement:'近期財報與資本支出'.repeat(6),comparison_id:'report'}]};
 return {ok:true,json:async()=>packet};
};
AtlasWiki.show();
"""


def viewport(page, width, height):
    page.call('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})


def rect(page, selector):
    return page.js("document.querySelector("+json.dumps(selector)+").getBoundingClientRect().toJSON()")


def point(page, selector, x=.5, y=.5):
    target=json.dumps(selector)
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        actual=page.js(f"""(async()=>{{
          const node=document.querySelector({target});
          node.scrollIntoView({{block:'nearest',inline:'nearest',behavior:'instant'}});
          const before=node.getBoundingClientRect();
          await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
          const r=node.getBoundingClientRect(),x=r.x+r.width*{x},y=r.y+r.height*{y};
          const hit=document.elementFromPoint(x,y);
          const stable=Math.abs(before.top-r.top)<.5&&Math.abs(before.left-r.left)<.5;
          return {{x,y,ready:stable&&r.width>0&&node.contains(hit),hit:hit?.outerHTML.slice(0,180)}};
        }})()""")
        if actual['ready']:
            return {'x':actual['x'],'y':actual['y']}
        time.sleep(.05)
    raise AssertionError((selector,actual))


def mouse(page, event, pos, **extra):
    page.call('Input.dispatchMouseEvent', {'type':event, **pos, **extra})


def click(page, selector):
    pos=point(page,selector)
    mouse(page,'mouseMoved',pos)
    mouse(page,'mousePressed',pos,button='left',buttons=1,clickCount=1)
    mouse(page,'mouseReleased',pos,button='left',clickCount=1)


def drag(page, pos, dx, dy, dock=False):
    mouse(page,'mouseMoved',pos)
    mouse(page,'mousePressed',pos,button='left',buttons=1,clickCount=1)
    for step in range(1,7):
        dest={'x':pos['x']+dx*step/6,'y':pos['y']+dy*step/6}
        mouse(page,'mouseMoved',dest,button='left',buttons=1)
    if dock:
        page.wait("$('splitPreview').classList.contains('split-armed')&&!$('splitPreview').hidden")
    mouse(page,'mouseReleased',dest,button='left',clickCount=1)


def key(page, name, code):
    for event in ('keyDown','keyUp'):
        params={'type':event,'key':name,'code':name,'windowsVirtualKeyCode':code,'nativeVirtualKeyCode':code}
        if name=='Enter' and event=='keyDown':
            params['text']='\r'
        page.call('Input.dispatchKeyEvent',params)


def touch(page, start, destination=None, cancel=False):
    page.call('Emulation.setTouchEmulationEnabled',{'enabled':True})
    page.call('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[start]})
    if destination:
        for i in range(1,7):
            pos={k:start[k]+(destination[k]-start[k])*i/6 for k in ('x','y')}
            page.call('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[pos]})
    page.call('Input.dispatchTouchEvent',{'type':'touchCancel' if cancel else 'touchEnd','touchPoints':[]})


def centered_glyph(page, selector, glyph, expanded=False):
    target=json.dumps(selector+' .panel-symbol' if expanded else selector)
    result=page.js(f"""(()=>{{
      const slot=document.querySelector({target}),path=slot.querySelector('svg path');
      const box=slot.getBoundingClientRect(),ink=path.getBoundingClientRect();
      return {{dx:ink.left+ink.width/2-box.left-box.width/2,dy:ink.top+ink.height/2-box.top-box.height/2,
        width:ink.width,height:ink.height,expected:path.getAttribute('d')===AtlasUI.icon({json.dumps(glyph)}).firstChild.getAttribute('d')}};
    }})()""")
    assert result['expected'] and min(result['width'],result['height'])>10,(selector,result)
    assert abs(result['dx'])<=1 and abs(result['dy'])<=1,(selector,result)


def news_windows(page):
    stage=rect(page,'#stage')
    saved={}
    for prefix,panel,body,x,y in [
        ('sourcePanel','#sourcePanel','sourcePanelBody',20,185),('timePanel','#timeFocusBar','timeFocusBody',60,285)
    ]:
        grip='#'+prefix+'Drag'
        if page.js(f"$('{body}').hidden"):
            click(page,grip)
        glyph='database' if prefix=='sourcePanel' else 'curveLens'
        centered_glyph(page,grip,glyph,expanded=True)
        window=rect(page,panel)
        drag(page,point(page,grip),x-window['x'],y-window['y'])
        expanded=rect(page,panel)
        assert abs(expanded['x']-x)<2 and abs(expanded['y']-y)<2 and expanded['x']<stage['left']-100,expanded
        click(page,'#'+prefix+'Toggle')
        small=rect(page,grip)
        centered_glyph(page,grip,glyph)
        assert small['width']==small['height']==40,(prefix,small,page.js(f"$('{body}').hidden"))
        assert page.js(f"document.activeElement.id==='{prefix}Drag'")
        pos=point(page,grip)
        dest={'x':1100 if prefix=='sourcePanel' else 940,'y':760 if prefix=='sourcePanel' else 600}
        drag(page,pos,dest['x']-pos['x'],dest['y']-pos['y'])
        assert page.js(f"$('{body}').hidden")
        moved=rect(page,grip)
        assert abs(moved['x']+20-dest['x'])<2 and abs(moved['y']+20-dest['y'])<2,moved
        click(page,grip)
        restored=rect(page,panel)
        assert all(abs(restored[k]-expanded[k])<2 for k in ('x','y','width','height'))
        click(page,'#'+prefix+'Toggle')
        saved[grip]=rect(page,grip)
        assert abs(saved[grip]['x']-moved['x'])<2 and abs(saved[grip]['y']-moved['y'])<2
    page.call('Page.reload')
    page.wait("typeof AtlasWiki!=='undefined'")
    for selector,before in saved.items():
        after=rect(page,selector)
        assert all(abs(after[k]-before[k])<2 for k in ('x','y','width','height'))
    print('Both News windows cross the graph edge. Reopen and reload preserve separate icon and window positions.',flush=True)
    viewport(page,690,914)
    for selector in saved:
        r=rect(page,selector)
        assert 8<=r['x']<r['right']<=682 and r['height']==r['width']==44,r
        centered_glyph(page,selector,'database' if selector=='#sourcePanelDrag' else 'curveLens')
    page.check('ribbon and header actions fit the annotated 690 px viewport',
        "(()=>{const h=document.querySelector('body>header'),img=h.querySelector('img');return img.complete&&img.naturalWidth>0&&img.width>=145&&h.scrollWidth<=innerWidth&&[...h.querySelectorAll('button,select')].every(n=>n.getBoundingClientRect().right<=innerWidth)})()")
    selector='#sourcePanelDrag'
    pos=point(page,selector)
    dest={'x':130,'y':350}
    touch(page,pos,dest)
    moved=rect(page,selector)
    assert abs(moved['left']+22-dest['x'])<2 and page.js("$('sourcePanelBody').hidden"),moved
    touch(page,point(page,selector),{'x':300,'y':490},cancel=True)
    assert abs(rect(page,selector)['x']-moved['x'])<2
    touch(page,point(page,selector))
    page.wait("!$('sourcePanelBody').hidden")
    click(page,'#sourcePanelToggle')
    click(page,'#openSearch')
    click(page,'#timePanelDrag')
    assert page.js("!$('timeFocusBody').hidden")
    window=rect(page,'#timeFocusBar')
    drag(page,point(page,'#timePanelDrag'),18-window['left'],135-window['top'])
    assert rect(page,'#timeFocusBar')['left']<24
    point(page,'#timePanelToggle')  # The window remains above the open drawer.
    click(page,'#timePanelToggle')
    click(page,'#openSearch')
    page.call('Emulation.setTouchEmulationEnabled',{'enabled':False})
    viewport(page,1223,914)
    print('690 px viewport clamps both icons. Touch drag, cancellation, tap and the open News drawer work.',flush=True)


def docked_launchers(page):
    # Two real edge dwells give the detail pane a nested saved tree.
    for prefix,edge in [('timePanel','top'),('sourcePanel','left')]:
        click(page,'#'+prefix+'Drag')
        grip=point(page,'#'+prefix+'Drag')
        news=rect(page,'[data-pane="news"]')
        x=news['left']+(2 if edge=='left' else news['width']/2)
        y=news['top']+(2 if edge=='top' else news['height']/2)
        drag(page,grip,x-grip['x'],y-grip['y'],dock=True)
    tree=page.js("AtlasDock.state().tree")
    assert tree['a']['id']=='timeFocusBar' and tree['b']['a']['id']=='sourcePanel',tree
    page.call('Page.reload')
    page.wait("window.AtlasDock?.ready&&AtlasDock.docked($('sourcePanel'))&&AtlasDock.docked($('timeFocusBar'))")
    page.check('a reload keeps both expanded docked readers open',
               "!$('sourcePanelBody').hidden&&!$('timeFocusBody').hidden")
    grip=point(page,'#sourcePanelDrag')
    touch(page,grip,{'x':180,'y':390},cancel=True)
    assert page.js("AtlasDock.docked($('sourcePanel'))&&document.querySelector('[data-pane=sourcePanel]').contains($('sourcePanel'))")
    assert tree==page.js("AtlasDock.state().tree")
    page.call('Emulation.setTouchEmulationEnabled',{'enabled':False})
    for prefix in ['sourcePanel','timePanel']:
        click(page,'#'+prefix+'Toggle')
        assert page.js(f"$('newsFloatingTools').contains($('{prefix}Drag'))")
    news=rect(page,'[data-pane="news"]')
    whole=rect(page,'#paneWorkspace')
    assert all(abs(news[k]-whole[k])<2 for k in ('width','height'))
    pos=point(page,'#sourcePanelDrag')
    drag(page,pos,100-pos['x'],300-pos['y'])
    page.call('Page.reload')
    page.wait("typeof AtlasWiki!=='undefined'&&!!document.querySelector('[data-pane=sourcePanel]')")
    assert page.js("AtlasDock.state().tree")==tree
    after=rect(page,'#sourcePanelDrag')
    assert abs(after['x']+20-100)<2 and abs(after['y']+20-300)<2
    for prefix,panel in [('timePanel','timeFocusBar'),('sourcePanel','sourcePanel')]:
        click(page,'#'+prefix+'Drag')
        assert page.js(f"AtlasDock.docked($('{panel}'))&&document.querySelector('[data-pane={panel}]').contains($('{panel}'))")
    # Undock through a normal title drag and let the sibling fill its saved slot.
    pos=point(page,'#sourcePanelDrag')
    drag(page,pos,190-pos['x'],375-pos['y'])
    assert page.js("!AtlasDock.docked($('sourcePanel'))&&AtlasDock.state().tree.b.id==='news'")
    click(page,'#sourcePanelToggle')
    print('Both nested split slots release space, survive a mobile cancellation, and return after a launcher drag and reload.',flush=True)


def run(page):
    viewport(page,1223,914)
    page.wait("typeof AtlasWiki!=='undefined'")
    news_windows(page)
    docked_launchers(page)
    page.js(SETUP)
    page.wait("AtlasWiki.runtime.state().version===124")
    page.js("$('wikiRange').value='all';$('wikiRange').dispatchEvent(new Event('change'))")
    energy="#wikiTimeline [data-term=energy]"
    plot="#wikiTimeline svg"
    page.wait("!!document.querySelector('#wikiTimeline [data-term=energy]')")
    page.wait("document.querySelectorAll('#wikiTimeline rect').length>10")
    page.js("window.fullWindow=[+$('wikiTimeline').dataset.start,+$('wikiTimeline').dataset.end]")
    page.js("$('wikiKind').value='Thesis';$('wikiKind').dispatchEvent(new Event('change'))")
    pos=point(page,energy)
    mouse(page,'mouseMoved',pos)
    mouse(page,'mousePressed',pos,button='left',buttons=1,clickCount=1)
    page.js("AtlasWiki.refresh()")
    mouse(page,'mouseReleased',pos,button='left',clickCount=1)
    page.wait("$('wikiAssessment').value==='energy'")
    page.check('selecting Energy filters bars',"[...$('wikiTimeline').querySelectorAll('rect')].every(r=>r.dataset.category==='energy')")
    click(page,energy)
    page.check('selecting Energy again restores all series and toolbar', "!$('wikiAssessment').value&&!!document.querySelector('#wikiTimeline rect[data-category=demand]')")
    click(page,"#wikiTimeline [data-term=demand]")
    click(page,'#wikiTimelineReset')
    page.check('return arrow clears the category', "!$('wikiAssessment').value")
    page.check('chart filtering preserves the separate node-type choice', "$('wikiKind').value==='Thesis'")
    pos=point(page,plot)
    for _ in range(3):
        mouse(page,'mouseWheel',pos,deltaX=0,deltaY=-120)
    page.wait("(+$('wikiTimeline').dataset.end)-$('wikiTimeline').dataset.start<fullWindow[1]-fullWindow[0]")
    before=page.js("[+$('wikiTimeline').dataset.start,+$('wikiTimeline').dataset.end]")
    page.js("window.plotBeforePan=document.querySelector('#wikiTimeline svg')")
    drag(page,pos,-100,0)
    after=page.js("[+$('wikiTimeline').dataset.start,+$('wikiTimeline').dataset.end]")
    assert after[0]>before[0] and after[1]-after[0]==before[1]-before[0],(before,after)
    page.check('drag keeps the original gesture surface', "plotBeforePan===document.querySelector('#wikiTimeline svg')")
    drag(page,pos,150,0)
    page.check('reverse drag moves back without opening a bar',f"+$('wikiTimeline').dataset.start<{after[0]}&&!$('wikiAssessment').value&&!$('wikiDetail').querySelector('.wiki-viewpoint')")
    page.js("document.querySelector('#wikiTimeline svg').focus()")
    key(page,'Home',36)
    page.check('keyboard Home restores the full interval',"+$('wikiTimeline').dataset.start===fullWindow[0]&&+$('wikiTimeline').dataset.end===fullWindow[1]")
    canvas=rect(page,'#wikiCanvas')
    # Grab the actual title in the original docked view, then resize its corner.
    drag(page,point(page,'#wikiTimelineGrip'),-84,-140)
    page.wait("$('wikiTimelineTool').dataset.mode==='floating'")
    box=rect(page,'#wikiTimelineTool')
    drag(page,point(page,'#wikiTimelineGrip'),56,-28)
    moved=rect(page,'#wikiTimelineTool')
    assert moved['x']>box['x']+25 and moved['y']<box['y']-10,(box,moved)
    drag(page,point(page,"#wikiTimelineTool [data-resize-edge=se]"),68,48)
    grown=rect(page,'#wikiTimelineTool')
    assert grown['width']>moved['width']+25 and grown['height']>moved['height']+20,(moved,grown)
    click(page,energy)
    mouse(page,'mouseWheel',point(page,plot),deltaX=0,deltaY=-120)
    page.wait("+$('wikiTimeline').dataset.start>fullWindow[0]")
    filtered=page.js("$('wikiTimeline').dataset.start")
    click(page,'#wikiTimelineFold')
    icon=rect(page,'#wikiTimelineLauncher')
    centered_glyph(page,'#wikiTimelineLauncher','chart')
    assert 32<=icon['width']==icon['height']<=52 and rect(page,'#wikiCanvas')['height']>canvas['height']+50
    page.check('minimize moves focus onto the square launcher',"document.activeElement===$('wikiTimelineLauncher')")
    pos=point(page,'#wikiTimelineLauncher')
    drag(page,pos,75-pos['x'],200-pos['y'])
    moved=rect(page,'#wikiTimelineLauncher')
    assert abs(moved['x']+20-75)<2 and abs(moved['y']+20-200)<2
    page.check('moving the Wiki square across the controls keeps it minimized',
               "$('wikiTimelineTool').hidden&&$('newsFloatingTools').hidden")
    key(page,'ArrowRight',39)
    assert abs(rect(page,'#wikiTimelineLauncher')['x']-moved['x']-20)<2
    key(page,'Enter',13)
    page.wait("$('wikiTimelineTool').dataset.mode==='floating'")
    reopened=rect(page,'#wikiTimelineTool')
    assert all(abs(reopened[k]-grown[k])<2 for k in ('x','y','width','height'))
    page.check('opening remembers zoom and classification',f"$('wikiAssessment').value==='energy'&&$('wikiTimeline').dataset.start==={json.dumps(filtered)}")
    click(page,'#wikiTimelineReset')
    page.check('reset restores both scales',"!$('wikiAssessment').value&&+$('wikiTimeline').dataset.end===fullWindow[1]&&+$('wikiTimeline').dataset.start===fullWindow[0]")
    click(page,'#wikiTimeline rect[data-category=energy]')
    page.check('a real bar click opens its dated viewpoints', "$('wikiDetail').querySelectorAll('.wiki-viewpoint').length>0&&$('wikiDetail').querySelector('h3').textContent==='能源'")
    click(page,'#wikiTimelineReset')
    click(page,'#wikiTimelineFloat')
    page.wait("$('wikiTimelineTool').dataset.mode==='docked'")
    page.check('toolbar labels and selected values are centered',"[...document.querySelectorAll('.wiki-toolbar label')].every(n=>getComputedStyle(n).textAlign==='center'&&getComputedStyle(n.querySelector('select')).textAlign==='center')")
    page.check('header loads the replaceable PNG with its accessible product name',
               "(()=>{const img=document.querySelector('header h1 img');return img.complete&&img.naturalWidth>0&&img.alt==='StockNexus Wiki'&&img.clientWidth>=160})()")
    click(page,'#relationOpen')
    page.check('Wiki settings close icon is named', "$('wikiSettings').open&&$('wikiSettingsClose').title==='關閉設定'&&!!$('wikiSettingsClose').querySelector('svg')")
    click(page,'#wikiSettingsClose')
    click(page,'#wikiBrowse')
    click(page,'.wiki-archive [aria-label="下一頁"]')
    page.check('archive arrow opens the next page of evidence', "document.querySelector('.wiki-archive details summary').textContent==='Viewpoint 20'")
    click(page,'.wiki-archive [aria-label="上一頁"]')
    page.check('archive arrow returns to the first page', "document.querySelector('.wiki-archive details summary').textContent==='Viewpoint 0'")
    click(page,'.wiki-archive [aria-label="關閉 L1 瀏覽器"]')
    click(page,'#wikiCompare')
    page.wait("!!document.querySelector('.wiki-comparison select option')")
    assert 760<=rect(page,'.wiki-comparison')['width']<1190
    click(page,'.wiki-comparison [data-action=add]')
    page.check('long selected viewpoint has its own readable row', "document.querySelector('.comparison-selected p span').clientWidth>500")
    page.language('en')
    key(page,'Escape',27)
    page.wait("!document.querySelector('.wiki-comparison')")
    page.check('Escape returns focus to Compare', "document.activeElement===$('wikiCompare')")
    page.check('English icon-only reset has a name and tooltip', "$('wikiTimelineReset').getAttribute('aria-label')===$('wikiTimelineReset').title&&$('wikiTimelineReset').title.includes('Reset')&&!$('wikiTimelineReset').textContent.trim()")
    viewport(page,390,844)
    click(page,'#wikiCompare')
    mobile=rect(page,'.wiki-comparison')
    assert mobile['width']>=350 and mobile['left']>=0 and mobile['right']<=390
    page.check('phone comparison has no horizontal scroll',"document.querySelector('.wiki-comparison').scrollWidth<=document.querySelector('.wiki-comparison').clientWidth+1")
    key(page,'Escape',27)
    click(page,'#wikiTimelineFloat')
    mobile=rect(page,'#wikiTimelineTool')
    assert mobile['x']>=0 and mobile['right']<=390 and mobile['top']>=0 and mobile['bottom']<=844,mobile
    mouse(page,'mouseWheel',point(page,plot),deltaX=0,deltaY=-120)
    page.wait("+$('wikiTimeline').dataset.start>fullWindow[0]")
    start=page.js("+$('wikiTimeline').dataset.start")
    pos=point(page,plot,.6,.7)
    page.call('Emulation.setTouchEmulationEnabled',{'enabled':True})
    page.call('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[pos]})
    for dx in (8,18,35,60):
        page.call('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':pos['x']-dx,'y':pos['y']}]})
    page.call('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
    page.check('touch panning advances the zoomed dates without selecting a bar',f"+$('wikiTimeline').dataset.start>{start}&&!$('wikiAssessment').value")
    click(page,'#wikiTimelineFold')
    icon=rect(page,'#wikiTimelineLauncher')
    assert abs(icon['x']-moved['x']-20)<2
    pos=point(page,'#wikiTimelineLauncher')
    touch(page,pos,{'x':180,'y':360})
    page.js("$('wikiPanel').scrollTop=0")
    icon=rect(page,'#wikiTimelineLauncher')
    assert abs(icon['left']+22-180)<2 and abs(icon['top']+22-360)<2
    page.check('reading and all gestures use zero model writes and produce no script errors',"!wikiPosts.length&&!errors.length&&!languageErrors.length")
    page.call('Page.reload')
    page.wait("typeof AtlasWiki!=='undefined'")
    page.js(SETUP)
    page.wait("AtlasWiki.runtime.state().version===124")
    after=rect(page,'#wikiTimelineLauncher')
    assert all(abs(icon[k]-after[k])<2 for k in ('x','y','width','height'))
    page.check('a reload restores the minimized tool', "$('wikiTimelineTool').dataset.mode==='collapsed'&&!$('wikiTimelineLauncher').hidden")


def main():
    with tempfile.TemporaryDirectory(prefix='wiki-timeline-') as tmp:
        folder=Path(tmp)
        html=folder/'fixture.html'
        generate(html)
        source=html.read_text()
        html.write_text(source[:source.rindex('<script>\n(async()=>{try{')]+'</body></html>')
        browser=Browser(folder/'browser')
        try:
            run(browser.page(html.as_uri()))
        finally:
            browser.close()


if __name__=='__main__':
    main()
