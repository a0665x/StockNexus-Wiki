"""Exercise contextual explanations and tool colors with real Chromium input."""
import json
import tempfile
import time
from pathlib import Path

from browser_chat_language import Browser
from browser_relations import generate
from browser_wiki_timeline import SETUP, centered_glyph, click, key, mouse, point, rect, touch, viewport


def help_button(note):
    return f'button[aria-describedby="{note}"]'


def accessible_button(page, selector):
    document=page.call('DOM.getDocument')['root']['nodeId']
    node=page.call('DOM.querySelector',{'nodeId':document,'selector':selector})['nodeId']
    entries=page.call('Accessibility.getPartialAXTree',{'nodeId':node,'fetchRelatives':False})['nodes']
    return next(entry for entry in entries if entry['role']['value']=='button')


def color(page, selector):
    return page.js(f"""(async()=>{{
      const target=document.querySelector({json.dumps(selector)});
      await new Promise(done=>requestAnimationFrame(done));
      await Promise.allSettled(target.getAnimations().map(effect=>effect.finished));
      const ctx=document.createElement('canvas').getContext('2d');
      ctx.fillStyle=getComputedStyle(target).backgroundColor;
      ctx.fillRect(0,0,1,1);return Array.from(ctx.getImageData(0,0,1,1).data);
    }})()""")


def check_color(page, selector, family, solid=False):
    red,green,blue,alpha=color(page,selector)
    order={'source':green>blue>red,'time':red>green>blue,'wiki':blue>green>red}
    assert order[family] and (alpha==255 if solid else 0<alpha<100),(selector,[red,green,blue,alpha])
    return [red,green,blue,alpha]


def uncovered(page, note):
    page.check(note+' fits the screen and is above the surrounding content',f"""(()=>{{
      const tip=$('{note}'),r=tip.getBoundingClientRect();
      return !tip.hidden&&r.width>30&&r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight&&
        tip.contains(document.elementFromPoint(r.left+r.width/2,r.top+r.height/2));
    }})()""")


def run(page):
    viewport(page,1223,914)
    page.wait("typeof AtlasWiki!=='undefined'&&!!$('workbenchHelpWord')")
    for selector in ('#dateRangeHelp','#rootQueryHelp','#searchDraftHelp'):
        assert page.js(f"document.querySelector('{selector}').hidden")
    page.check('Brand and primary actions are visible without the descriptor or routine status',
               "document.title==='StockNexus Wiki'&&!!$('workbenchHeader').querySelector('img[alt]')&&"
               "!$('workbenchHeader').innerText.includes('新聞關聯觀測台')&&!$('searchDraftStatus').innerText&&"
               "!$('rootSearchStatus').innerText&&!!$('submit').innerText")
    note='dateRangeHelp'
    trigger=help_button(note)
    ax=accessible_button(page,trigger)
    assert '資料區間' in ax['name']['value'] and '說明' in ax['name']['value']
    assert '366' in ax['description']['value']
    neutral=point(page,'.brand-artwork')
    position=point(page,'#dateRangeHelpName')
    page.js("""window.helpDwell={};
      $('dateRangeHelpName').addEventListener('pointermove',()=>helpDwell.start=performance.now());
      new MutationObserver(()=>{if(!$('dateRangeHelp').hidden)helpDwell.end=performance.now()})
        .observe($('dateRangeHelp'),{attributes:true,attributeFilter:['hidden']});""")
    mouse(page,'mouseMoved',position)
    time.sleep(.15)
    mouse(page,'mouseMoved',neutral)
    time.sleep(.65)
    assert page.js("!helpDwell.end&&$('dateRangeHelp').hidden")
    mouse(page,'mouseMoved',position)
    time.sleep(.25)
    mouse(page,'mouseMoved',{**position,'x':position['x']+2})
    before=rect(page,trigger)
    time.sleep(.38)
    assert page.js("$('dateRangeHelp').hidden")
    page.wait("helpDwell.end>helpDwell.start&&!$('dateRangeHelp').hidden")
    duration=page.js('Math.round(helpDwell.end-helpDwell.start)')
    assert duration>=595,duration
    assert rect(page,trigger)==before
    uncovered(page,note)
    box=rect(page,'#'+note)
    mouse(page,'mouseMoved',{'x':box['left']+8,'y':box['top']+8})
    time.sleep(.25)
    assert page.js("!$('dateRangeHelp').hidden")
    key(page,'Escape',27)
    assert page.js("$('dateRangeHelp').hidden")

    page.language('en')
    page.wait("$('workbenchHelpWord').textContent==='Help'")
    ax=accessible_button(page,trigger)
    assert 'Help' in ax['name']['value'] and '366' in ax['description']['value']
    page.check('English date and search tips use complete translated copy',
               """['dateRangeHelp','rootQueryHelp','searchDraftHelp'].every(id=>!!$(id).textContent.trim()&&
               !/[\u3400-\u9fff]/.test($(id).textContent))""")
    mouse(page,'mouseMoved',neutral)
    page.js("$('query').focus()")
    key(page,'Tab',9)
    assert page.js(f'document.activeElement.matches({json.dumps(trigger)})')
    page.wait("!$('dateRangeHelp').hidden")
    key(page,'Escape',27)
    key(page,'Enter',13)
    uncovered(page,note)
    key(page,'Tab',9)
    assert page.js("$('dateRangeHelp').hidden")
    colors={}
    for prefix,body,glyph,family in [
        ('sourcePanel','sourcePanelBody','database','source'),('timePanel','timeFocusBody','curveLens','time')
    ]:
        if not page.js(f"$('{body}').hidden"):
            click(page,'#'+prefix+'Toggle')
        selector='#'+prefix+'Drag'
        centered_glyph(page,selector,glyph)
        mouse(page,'mouseMoved',neutral)
        colors[family]=check_color(page,selector,family,solid=True)
    check_color(page,'#dateCustom','time')
    check_color(page,'#modeWiki','wiki')
    page.js(SETUP)
    page.wait("AtlasWiki.runtime.state().version===124")
    if page.js("$('wikiTimelineLauncher').hidden"):
        click(page,'#wikiTimelineFold')
    centered_glyph(page,'#wikiTimelineLauncher','chart')
    mouse(page,'mouseMoved',neutral)
    colors['wiki']=check_color(page,'#wikiTimelineLauncher','wiki',solid=True)
    check_color(page,'#wikiCompare','wiki')
    page.check('The visible graph includes its group count',"$('wikiGroupLabel').innerText==='100 separate groups'")
    click(page,help_button('wikiGroupHelp'))
    uncovered(page,'wikiGroupHelp')
    click(page,'.brand-artwork')
    assert page.js("$('wikiGroupHelp').hidden&&$('wikiGroupLabel').innerText==='100 separate groups'")
    page.js("$('wikiKind').value='ArticleRevision';$('wikiKind').dispatchEvent(new Event('change'))")
    page.wait("$('wikiGroups').hidden")
    page.js("$('wikiKind').value='';$('wikiKind').dispatchEvent(new Event('change'))")
    page.wait("!$('wikiGroups').hidden")
    click(page,help_button('wikiScopeHelp'))
    uncovered(page,'wikiScopeHelp')
    page.check('Article count and scope are visible while DB and tree semantics are available on request',
               """$('wikiSelection').innerText.includes('articles')&&$('wikiScope').offsetWidth>0&&
               $('wikiScopeHelp').innerText.includes('news database')&&$('wikiScopeHelp').innerText.includes('trees')""")
    page.language('zh-Hant')
    page.wait("$('wikiScopeHelp').hidden&&$('workbenchHelpWord').textContent==='說明'")
    click(page,'#relationOpen')
    page.wait("$('wikiSettings').open")
    viewport(page,390,844)
    button=help_button('wikiWorkersNote')
    page.call('Emulation.setTouchEmulationEnabled',{'enabled':True})
    pos=point(page,button)
    touch(page,pos)
    uncovered(page,'wikiWorkersNote')
    assert min(rect(page,button)[k] for k in ('width','height'))>=36
    assert '新聞樹' in page.js("$('wikiWorkersNote').innerText")
    touch(page,pos)
    assert page.js("$('wikiWorkersNote').hidden&&$('wikiSettings').open")
    touch(page,pos)
    key(page,'Escape',27)
    assert page.js("$('wikiWorkersNote').hidden&&$('wikiSettings').open")
    key(page,'Escape',27)
    page.wait("!$('wikiSettings').open")
    page.check('Help interactions cause no model requests or script errors',
               "!wikiPosts.length&&!errors.length&&!languageErrors.length")
    print(json.dumps({'hover_ms':duration,'launcher_rgba':colors}),flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix='workbench-help-') as tmp:
        folder=Path(tmp)
        html=folder/'fixture.html'
        generate(html)
        markup=html.read_text()
        html.write_text(markup[:markup.rindex('<script>\n(async()=>{try{')]+'</body></html>')
        browser=Browser(folder/'browser')
        try:
            run(browser.page(html.as_uri()))
        finally:
            browser.close()


if __name__=='__main__':
    main()
