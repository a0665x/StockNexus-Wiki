"""Exercise the shared header through the served News and Wiki interfaces."""
import json
import tempfile
from pathlib import Path

from browser_chat_language import Browser
from browser_relations import generate
from browser_wiki_timeline import SETUP, click, drag, key, mouse, point, rect, touch, viewport


EDGE = '#headerResize'


def measured_logo(page):
    # Measure the visible pixels independently of the workbench's crop variables.
    return page.js("""(()=>{
      const image=document.querySelector('.workbench-brand'),r=image.getBoundingClientRect();
      const canvas=document.createElement('canvas');canvas.width=Math.min(image.naturalWidth,1024);
      canvas.height=Math.max(1,Math.round(canvas.width*image.naturalHeight/image.naturalWidth));
      const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,canvas.width,canvas.height);
      const data=ctx.getImageData(0,0,canvas.width,canvas.height).data;
      let x0=canvas.width,x1=-1,y0=canvas.height,y1=-1;
      for(let i=3;i<data.length;i+=4)if(data[i]>=32){
        const x=((i-3)/4)%canvas.width,y=Math.floor((i-3)/4/canvas.width);
        x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);
      }
      return {left:r.left+r.width*x0/canvas.width,right:r.left+r.width*(x1+1)/canvas.width,
        top:r.top+r.height*y0/canvas.height,bottom:r.top+r.height*(y1+1)/canvas.height,
        height:r.height*(y1+1-y0)/canvas.height};
    })()""")


def ready(page):
    page.wait("typeof AtlasWiki!=='undefined'&&document.querySelector('#workbenchHeader h1').style.getPropertyValue('--brand-aspect')!==''")


def check_geometry(page, wiki=False):
    header=rect(page,'#workbenchHeader')
    frame=rect(page,'.brand-artwork')
    art=measured_logo(page)
    assert frame['left']-2<=art['left']<=20 and art['right']<=frame['right']+2,(art,frame)
    assert frame['top']-2<=art['top']<art['bottom']<=frame['bottom']+2,(art,frame)
    layout=rect(page,'.layout')
    assert abs(layout['top']-header['bottom'])<1 and abs(layout['bottom']-page.js('innerHeight'))<1,layout
    if wiki:
        page.wait("Math.abs($('wikiPanel').getBoundingClientRect().top-$('workbenchHeader').getBoundingClientRect().bottom)<1")
    obscured=page.js("""[...$('workbenchHeader').querySelectorAll('button,select')].filter(n=>n.offsetWidth).flatMap(n=>{
        const r=n.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
        return r.left>=0&&r.right<=innerWidth&&n.contains(hit)?[]:[{id:n.id,x:r.x,y:r.y,
          right:r.right,topElement:hit?.id||hit?.tagName}]})""")
    assert not obscured,obscured
    assert int(page.js("$('headerResize').getAttribute('aria-valuenow')"))==header['height']
    return header['height'],round(art['height'],1)


def run(page):
    viewport(page,1223,914)
    ready(page)
    default,small=check_geometry(page)
    assert default==68 and small>=default*.75,(default,small)
    page.js(SETUP)
    page.wait("AtlasWiki.runtime.state().version===124")
    drag(page,point(page,EDGE,.16),0,52)
    enlarged,big=check_geometry(page,wiki=True)
    assert enlarged==default+52 and big>small+15,(default,small,enlarged,big)
    page.check('Wiki drag saves the height locally',f"AtlasUI.read('headerHeight')==={enlarged}&&!wikiPosts.length")
    drag(page,point(page,EDGE,.16),0,300)
    ceiling,largest=check_geometry(page,wiki=True)
    assert ceiling==180 and largest>=big
    drag(page,point(page,EDGE,.16),0,enlarged-ceiling)
    page.call('Page.reload')
    ready(page)
    assert check_geometry(page)[0]==enlarged
    click(page,EDGE)
    key(page,'ArrowUp',38)
    assert check_geometry(page)[0]==enlarged-8
    key(page,'ArrowDown',40)
    assert check_geometry(page)[0]==enlarged

    # A shorter viewport clamps only the rendered height.
    viewport(page,1000,400)
    page.wait("$('headerResize').getAttribute('aria-valuenow')==='100'")
    assert check_geometry(page)[0]==100 and page.js("AtlasUI.read('headerHeight')")==enlarged
    viewport(page,1223,914)
    page.wait(f"$('headerResize').getAttribute('aria-valuenow')==='{enlarged}'")
    key(page,'Home',36)
    assert check_geometry(page)[0]==default and page.js("AtlasUI.read('headerHeight')") is None

    viewport(page,690,914)
    page.wait("$('headerResize').getAttribute('aria-valuenow')==='60'")
    narrow,narrow_art=check_geometry(page)
    touch_pos=point(page,EDGE,.8)
    touch(page,touch_pos,{'x':touch_pos['x'],'y':touch_pos['y']+66},cancel=True)
    assert check_geometry(page)[0]==narrow and page.js("AtlasUI.read('headerHeight')") is None
    touch(page,touch_pos,{'x':touch_pos['x'],'y':touch_pos['y']+66})
    taller,tall_art=check_geometry(page)
    assert taller==narrow+66 and tall_art>narrow_art+10,(taller,tall_art,narrow_art)
    page.language('en')
    page.wait("$('headerResize').getAttribute('aria-label')==='Resize header height'")
    click(page,'#openSearch')
    assert abs(rect(page,'.left')['top']-taller)<1
    pos=point(page,EDGE,.85)
    for count in (1,2):
        mouse(page,'mousePressed',pos,button='left',buttons=1,clickCount=count)
        mouse(page,'mouseReleased',pos,button='left',clickCount=count)
    assert check_geometry(page)[0]==narrow and page.js("AtlasUI.read('headerHeight')") is None

    viewport(page,390,844)
    page.wait("$('headerResize').getAttribute('aria-valuenow')==='94'")
    phone,phone_art=check_geometry(page)
    pos=point(page,EDGE,.7)
    touch(page,pos,{'x':pos['x'],'y':pos['y']+20},cancel=False)
    larger_phone,larger_art=check_geometry(page)
    assert larger_phone==phone+20 and larger_art>=phone_art
    assert larger_art>phone_art+4 or rect(page,'.brand-artwork')['width']>=372
    page.language('zh-Hant')
    assert page.js("document.documentElement.scrollWidth<=innerWidth")
    check_geometry(page)
    viewport(page,320,740)
    page.language('en')
    check_geometry(page)

    # Substitute an opaque, differently shaped PNG in this browser profile only.
    page.js("""(()=>{const c=document.createElement('canvas');c.width=120;c.height=60;
      const ctx=c.getContext('2d');ctx.fillRect(0,0,120,60);
      document.querySelector('.workbench-brand').src=c.toDataURL('image/png');})()""")
    page.wait("document.querySelector('#workbenchHeader h1').style.getPropertyValue('--brand-aspect')==='2'")
    image,frame=rect(page,'.workbench-brand'),rect(page,'.brand-artwork')
    assert all(abs(image[k]-frame[k])<1 for k in ('width','height','top','left')),(image,frame)
    page.check('replacement PNG and gestures produced no script errors',"!errors.length")
    print(json.dumps({'desktop':[default,small,enlarged,big],'narrow':[narrow,narrow_art,taller,tall_art],
                      'phone':[phone,phone_art,larger_phone,larger_art]}),flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix='workbench-header-') as tmp:
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
