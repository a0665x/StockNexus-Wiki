/* Browser preferences and lazy, text-only JSON inspection. No credentials enter graph data. */
(function(root){
  const read=(key,fallback=null)=>{try{return JSON.parse(localStorage.getItem('graphnews.'+key))??fallback;}catch{return fallback;}};
  const write=(key,value)=>{try{if(value===null)localStorage.removeItem('graphnews.'+key);else localStorage.setItem('graphnews.'+key,JSON.stringify(value));return true;}catch{return false;}};
  const iconPaths={
    database:'M20 6a8 3 0 1 1-16 0 8 3 0 0 1 16 0Z M4 6v12a8 3 0 0 0 16 0V6 M4 12a8 3 0 0 0 16 0',
    curveLens:'M18.5 10.5a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z M16.2 16.2l5.3 5.3 M5.5 12.5c1.8 0 2.3-4.6 4.1-3.5s1.9 4.1 3.6 2.1l2.2-3',
    chart:'M3 4v16h18 M7 15v-4 M12 15V6 M17 15V9',
    reset:'M9 4 4 9l5 5 M5 9h9a6 6 0 0 1 0 12',
    expand:'M9 4H4v5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5',
    dock:'M3 4h18v16H3z M3 14h18',
    minimize:'M5 16h14', close:'m6 6 12 12 M18 6 6 18',
    previous:'m14 5-7 7 7 7', next:'m10 5 7 7-7 7',
    search:'M16 10a6 6 0 1 1-12 0 6 6 0 0 1 12 0z M15 15l6 6'
  };
  function icon(name){
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
    const path=document.createElementNS(ns,'path');
    svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    svg.setAttribute('class','workbench-icon');path.setAttribute('d',iconPaths[name]);
    svg.append(path);return svg;
  }
  function labelIcon(button,name,label){
    button.replaceChildren(icon(name));button.title=label;button.setAttribute('aria-label',label);
    button.classList.add('icon-control');return button;
  }
  function jsonTree(container,value){
    const doc=container.ownerDocument||document;
    function field(key,val){
      const details=doc.createElement('details'),summary=doc.createElement('summary');
      const object=val!==null&&typeof val==='object';
      summary.textContent=key+' · '+(Array.isArray(val)?'array ['+val.length+']':object?'object {'+Object.keys(val).length+'}':val===null?'null':typeof val);
      details.append(summary);let loaded=false;
      details.addEventListener('toggle',()=>{if(!details.open||loaded)return;loaded=true;if(object){for(const [k,v] of Object.entries(val))details.append(field(k,v));}else{const pre=doc.createElement('pre');pre.textContent=JSON.stringify(val,null,2);details.append(pre);}});
      return details;
    }
    container.replaceChildren();for(const [k,v] of Object.entries(value))container.append(field(k,v));
  }
  function initKey($,{persist=()=>{},forget=()=>{}}={}){
    $('rememberKey').checked=read('rememberKey',true);if($('rememberKey').checked)$('key').value=read('massiveKey','');
    let lastSent='',pending=Promise.resolve();
    const enqueue=fn=>(pending=pending.catch(()=>{}).then(fn));
    function save(remote=true){
      const remember=$('rememberKey').checked,value=$('key').value.trim();write('rememberKey',remember);
      // Empty transient fields never erase a recorded key; only explicit forget/opt-out does.
      const ok=!remember?write('massiveKey',null):value?write('massiveKey',value):true;
      if(!ok)$('keyStatus').textContent='瀏覽器儲存不可用；此 key 僅供本次使用。';else if(remember&&(value||read('massiveKey','')))$('keyStatus').textContent='已記住金鑰；重新整理會沿用。';else if(!remember)$('keyStatus').textContent='';
      if(remote&&remember){const key=value||read('massiveKey','');if(key&&key!==lastSent){lastSent=key;enqueue(()=>persist(key)).catch(()=>{lastSent='';$('keyStatus').textContent='金鑰仍在此瀏覽器；伺服器保存失敗，請重試。';});}}
      return ok;
    }
    $('key').addEventListener('input',()=>save(false));$('key').addEventListener('change',()=>save());
    $('rememberKey').addEventListener('change',()=>{save(false);if(!$('rememberKey').checked){lastSent='';enqueue(forget).catch(()=>{$('keyStatus').textContent='伺服器金鑰清除失敗，請重試。';});}else save();});
    $('forgetKey').onclick=()=>{$('key').value='';lastSent='';const ok=write('massiveKey',null);$('keyStatus').textContent=ok?'已清除瀏覽器保存的 key。':'無法清除本機儲存；請使用瀏覽器網站資料設定清除。';enqueue(forget).catch(()=>{$('keyStatus').textContent='伺服器金鑰清除失敗，請重試。';});};
    save();return save;
  }
  // Editable search draft is separate from acquired graph/snapshot metadata.
  function initSearch($,dates){
    const providers=['google','yahoo','massive'],saved=read('searchDraft',{});
    if(saved&&typeof saved==='object'){
      for(const [id,max]of [['query',200],['ticker',40]])if(typeof saved[id]==='string')$(id).value=saved[id].slice(0,max);
      if(Array.isArray(saved.sources)&&saved.sources.every(p=>providers.includes(p)))for(const p of providers)$('source-'+p).checked=saved.sources.includes(p);
      if(['TW','US','HK','JP','GB'].includes(saved.rss_region))$('rssRegion').value=saved.rss_region;

      dates.restore(saved.dates);
    }
    $('forceRefresh').checked=false;
    function save(){
      const draft={rss_region:$('rssRegion').value||'TW',query:$('query').value,ticker:$('ticker').value,sources:providers.filter(p=>$('source-'+p).checked),dates:dates.state()};
      const ok=write('searchDraft',draft);$('searchDraftStatus').textContent=ok?'':'瀏覽器儲存不可用；重新整理後無法保留搜尋設定。';return ok;
    }
    for(const id of ['query','ticker','rssRegion','forceRefresh',...providers.map(p=>'source-'+p)])for(const event of ['input','change'])$(id).addEventListener(event,save);
    dates.onChange(save);save();return save;
  }
  const limit=(v,lo,hi)=>Math.max(lo,Math.min(Math.max(lo,hi),v));
  const validPoint=p=>Number.isFinite(p?.x)&&Number.isFinite(p?.y);
  function windowBounds(header){
    const left=8,right=root.innerWidth-8,bottom=root.innerHeight-8;
    const top=limit(header.getBoundingClientRect().bottom+8,8,bottom-64);
    return {left,top,right,bottom,width:right-left,height:bottom-top};
  }
  function fitPoint(point,rect,area){
    return {x:limit(point.x,area.left,area.right-rect.width),y:limit(point.y,area.top,area.bottom-rect.height)};
  }
  function arrowStep(key){
    return {ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]}[key];
  }
  // Capture on a stable ancestor once movement starts. Docking may reparent the tool.
  // A tap retains its native button focus/click, including keyboard activation.
  function bindWindowDrag(surface,{accept=()=>true,start,move,finish}){
    const doc=surface.ownerDocument,host=doc.documentElement;
    let drag=null,suppress=false;
    function travel(e){
      if(!drag||drag.id!==e.pointerId)return;
      if(!drag.moved){
        if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<5)return;
        drag.moved=true;
        host.setPointerCapture(e.pointerId);
      }
      move(e,drag.initial);e.preventDefault();
    }
    function end(e){
      if(!drag||(e.pointerId!==undefined&&e.pointerId!==drag.id))return;
      if(e.type==='lostpointercapture'&&e.target!==host)return;
      const d=drag;drag=null;suppress=d.moved;
      doc.removeEventListener('pointermove',travel);
      for(const type of ['pointerup','pointercancel','lostpointercapture'])doc.removeEventListener(type,end);
      root.removeEventListener('blur',end);
      if(host.hasPointerCapture(d.id))host.releasePointerCapture(d.id);
      if(d.moved)finish?.(e,d.initial,e.type!=='pointerup');
    }
    surface.addEventListener('pointerdown',e=>{
      if(drag||e.button!==0||e.isPrimary===false)return;
      suppress=false;
      if(!accept(e))return;
      drag={id:e.pointerId,x:e.clientX,y:e.clientY,initial:start(e),moved:false};
      doc.addEventListener('pointermove',travel);
      for(const type of ['pointerup','pointercancel','lostpointercapture'])doc.addEventListener(type,end);
      root.addEventListener('blur',end);
    });
    surface.addEventListener('click',e=>{
      if(suppress&&e.detail!==0){e.preventDefault();e.stopImmediatePropagation();}
    },true);
  }
  function unobstructed(rect,other,area){
    const fits=p=>p.x+rect.width+8<=other.left||p.x>=other.right+8||
      p.y+rect.height+8<=other.top||p.y>=other.bottom+8;
    const origin={x:rect.left,y:rect.top};
    if(fits(origin))return origin;
    const choices=[
      {x:other.left-rect.width-8,y:rect.top},{x:other.right+8,y:rect.top},
      {x:rect.left,y:other.top-rect.height-8},{x:rect.left,y:other.bottom+8}
    ].map(p=>fitPoint(p,rect,area)).filter(fits);
    choices.sort((a,b)=>Math.hypot(a.x-origin.x,a.y-origin.y)-Math.hypot(b.x-origin.x,b.y-origin.y));
    return choices[0];
  }
  // Both News tools share the workbench. Give the user's active tool first choice.
  const floatingStages=new WeakMap();
  function initFloatingPanel($,{key,panelId,bodyId,handleId,toggleId,resetId,glyph,openLabel,onChange=()=>{}}){
    const panel=$(panelId),body=$(bodyId),handle=$(handleId),toggle=$(toggleId),reset=$(resetId);
    const stage=$('stage'),home=$('newsFloatingTools'),header=panel.ownerDocument.querySelector('body>header');
    const saved=read(key,{})||{};
    let position=validPoint(saved.position)?saved.position:null;
    let iconPosition=validPoint(saved.iconPosition)?saved.iconPosition:null;
    let collapsed=saved.collapsed===true;
    const docked=()=>root.AtlasDock?.docked(panel);
    const bounds=()=>windowBounds(header);
    const rect=()=>panel.getBoundingClientRect();
    function defaultPoint(){
      const stageRect=stage.getBoundingClientRect();
      const tools=$('graphTools').getBoundingClientRect();
      return {x:stageRect.left+16,y:panelId==='sourcePanel'?tools.bottom+8:stageRect.bottom-38-rect().height};
    }
    // Fresh windows start below the graph controls. A deliberate move unlocks the whole viewport.
    function placementBounds(){
      const b=bounds();
      if(collapsed?iconPosition:position)return b;
      const r=stage.getBoundingClientRect();
      const left=Math.max(b.left,r.left+8),right=Math.min(b.right,r.right-8);
      const bottom=Math.min(b.bottom,r.bottom-8);
      const top=limit($('graphTools').getBoundingClientRect().bottom+8,b.top,bottom-80);
      return {left,top,right,bottom,width:right-left,height:bottom-top};
    }
    function place(point,area=bounds()){
      const p=fitPoint(point,rect(),area);
      panel.style.left=p.x+'px';panel.style.top=p.y+'px';
      return p;
    }
    function setPosition(point){
      const p=place(point);
      if(collapsed)iconPosition=p;else position=p;
    }
    const state=()=>({collapsed,position,iconPosition,...resizer?.state()});
    const persist=()=>write(key,state());
    function labels(){
      const t=root.AtlasI18n.t;
      const label=collapsed?t(openLabel):t('拖動視窗或用方向鍵移動');
      handle.title=label;handle.setAttribute('aria-label',label);
      labelIcon(toggle,'minimize',t('縮小視窗'));
      labelIcon(reset,'reset',t('視窗歸位'));
    }
    function renderMode(){
      body.hidden=collapsed;panel.classList.toggle('collapsed',collapsed);
      handle.classList.toggle('tool-launcher',collapsed);
      for(const button of [handle,toggle])button.setAttribute('aria-expanded',String(!collapsed));
      labels();
    }
    function layout(){
      if(docked())return;
      panel.style.maxHeight='';resizer?.constrain();
      place((collapsed?iconPosition:position)||defaultPoint(),placementBounds());
    }
    function minimize(automatic=false){
      if(collapsed)return;
      const r=rect();
      if(!automatic)iconPosition??={x:r.left,y:r.top};
      collapsed=true;renderMode();root.AtlasDock?.reflow(panel);persist();
    }
    let group=floatingStages.get(stage);
    if(!group){group={tools:[],active:null,busy:false};floatingStages.set(stage,group);}
    function constrain(){
      if(group.busy||!home.getClientRects().length)return;
      group.busy=true;
      try{
        const floating=group.tools.filter(tool=>!tool.docked());
        for(const tool of floating)tool.layout();
        // Dock restoration runs after the News UI mounts. A pane about to dock should keep its saved mode.
        if(floating.length===2&&root.AtlasDock?.ready!==false){
          const active=floating.includes(group.active)?group.active:floating[0];
          const other=floating.find(tool=>tool!==active);
          let point=unobstructed(other.rect(),active.rect(),other.placementBounds());
          if(!point&&!other.collapsed()){
            other.minimize(true);other.layout();
            point=unobstructed(other.rect(),active.rect(),other.placementBounds());
          }
          if(!point){
            // A nearly fullscreen reader still leaves room for its sibling's launcher.
            const b=active.placementBounds();
            active.panel.style.maxHeight=Math.max(44,b.height-other.rect().height-8)+'px';
            active.place({x:active.rect().left,y:b.top},b);
            other.place({x:active.rect().left,y:active.rect().bottom+8});
          }else other.place(point);
        }
        for(const tool of group.tools)tool.changed();
      }finally{group.busy=false;}
    }
    function activate(){group.active=tool;}
    function fold(){
      activate();
      if(collapsed){collapsed=false;renderMode();root.AtlasDock?.reflow(panel);}
      else minimize();
      constrain();persist();handle.focus({preventScroll:true});
    }
    const tool={panel,rect,place,docked,minimize,layout,placementBounds,collapsed:()=>collapsed,changed:onChange};
    home.append(panel);
    handle.querySelector('.panel-symbol').replaceChildren(icon(glyph));
    handle.setAttribute('aria-controls',bodyId);
    const resizer=root.AtlasFloatingResize?.attach({panel,bounds:placementBounds,collapsed:()=>collapsed,initial:saved,
      onStart(){activate();const r=rect();position={x:r.left,y:r.top};},onMove(dx,dy){const r=rect();setPosition({x:r.left+dx,y:r.top+dy});constrain();},
      onFinish(){constrain();persist();}});
    renderMode();
    // The previous format stored translations from the News stage's default position.
    if(!('position' in saved)&&(Number.isFinite(saved.x)||Number.isFinite(saved.y))){
      const base=defaultPoint(),legacy={x:base.x+(saved.x||0),y:base.y+(saved.y||0)};
      if(collapsed)iconPosition=legacy;else if(saved.x||saved.y)position=legacy;
    }
    toggle.onclick=fold;
    handle.onclick=()=>{if(collapsed)fold();};
    reset.onclick=()=>{activate();position=null;constrain();persist();};
    bindWindowDrag(panel,{
      accept(e){
        if(e.target.closest('[data-resize-edge]'))return false;
        if(e.pointerType==='touch'&&e.target.closest('#sourcePanelBody,#timeFocusBody'))return false;
        const control=e.target.closest('button,input,select,textarea,a,label,summary,svg,[role="slider"],[contenteditable="true"]');
        return !control||control===handle;
      },
      start(e){
        activate();
        const r=rect();
        return {offsetX:e.clientX-r.left,offsetY:e.clientY-r.top,position,iconPosition};
      },
      move(e,initial){
        if(docked())root.AtlasDock.lift(panel);
        setPosition({x:e.clientX-Math.min(initial.offsetX,rect().width-5),y:e.clientY-initial.offsetY});
        if(!collapsed)root.AtlasDock?.preview(e);
        constrain();
      },
      finish(e,initial,cancel){
        if(cancel){position=initial.position;iconPosition=initial.iconPosition;}
        if(!collapsed)root.AtlasDock?.finish(panel,e,cancel);
        constrain();persist();
      }
    });
    handle.addEventListener('keydown',e=>{
      const step=arrowStep(e.key);if(!step)return;
      e.preventDefault();activate();const r=rect();
      if(docked())root.AtlasDock.undock(panel);
      setPosition({x:r.left+step[0],y:r.top+step[1]});constrain();persist();
    });
    group.tools.push(tool);
    root.addEventListener('atlas-language',labels);
    if(group.tools.length===1){
      root.addEventListener('resize',constrain);
      const observer=new ResizeObserver(constrain);
      for(const el of [stage,$('graphTools'),header,home])observer.observe(el);
    }
    constrain();return {constrain,state};
  }
  const initSourcePanel=$=>initFloatingPanel($,{key:'sourcePanel',panelId:'sourcePanel',bodyId:'sourcePanelBody',handleId:'sourcePanelDrag',toggleId:'sourcePanelToggle',resetId:'sourcePanelReset',glyph:'database',openLabel:'開啟來源篩選'});
  const initTimePanel=($,onChange)=>initFloatingPanel($,{key:'timePanel',panelId:'timeFocusBar',bodyId:'timeFocusBody',handleId:'timePanelDrag',toggleId:'timePanelToggle',resetId:'timePanelReset',glyph:'curveLens',openLabel:'開啟時間大小焦點',onChange});
  // Measure a small alpha mask once per image load so a drop-in PNG can have any border.
  function frameBrand(image,onMeasure){
    const heading=image.closest('h1');
    function measure(){
      const width=image.naturalWidth,height=image.naturalHeight;
      if(!width||!height)return;
      const sample=document.createElement('canvas'),scale=Math.min(1,512/Math.max(width,height));
      sample.width=Math.max(1,Math.round(width*scale));
      sample.height=Math.max(1,Math.round(height*scale));
      let left=0,top=0,right=sample.width,bottom=sample.height;
      try{
        const ctx=sample.getContext('2d');
        ctx.drawImage(image,0,0,sample.width,sample.height);
        const pixels=ctx.getImageData(0,0,sample.width,sample.height).data;
        let xMin=right,yMin=bottom,xMax=-1,yMax=-1;
        for(let y=0;y<sample.height;y++)for(let x=0;x<sample.width;x++){
          if(pixels[(y*sample.width+x)*4+3]<32)continue;
          xMin=Math.min(xMin,x);xMax=Math.max(xMax,x);
          yMin=Math.min(yMin,y);yMax=Math.max(yMax,y);
        }
        if(xMax>=0){
          left=Math.max(0,xMin-1);top=Math.max(0,yMin-1);
          right=Math.min(right,xMax+2);bottom=Math.min(bottom,yMax+2);
        }
      }catch{/* An unreadable mask uses the full intrinsic image. */}
      const w=right-left,h=bottom-top;
      heading.style.setProperty('--brand-aspect',(width*w/sample.width)/(height*h/sample.height));
      heading.style.setProperty('--brand-image-width',100*sample.width/w+'%');
      heading.style.setProperty('--brand-image-left',-100*left/w+'%');
      heading.style.setProperty('--brand-image-top',-100*top/h+'%');
      onMeasure();
    }
    image.addEventListener('load',measure);
    if(image.complete)measure();
  }

  function initHeaderResize(header,handle){
    if(!header||!handle)return;
    const rootNode=document.documentElement;
    const heading=header.querySelector('h1');
    const controls=Array.from(header.querySelectorAll('button,select'));
    const saved=read('headerHeight');
    let preferred=Number.isFinite(saved)?saved:null;
    let height,minimum,maximum,standard,drag=null;
    // Move the controls below a wide wordmark when a second row gives it more room.
    function fitRows(){
      const css=getComputedStyle(header);
      const gap=parseFloat(css.columnGap);
      let room=header.clientWidth-parseFloat(css.paddingLeft)-parseFloat(css.paddingRight);
      for(const control of controls)if(control.offsetWidth)room-=control.offsetWidth+gap;
      const aspect=Number(heading.style.getPropertyValue('--brand-aspect'))||3;
      const secondRowWidth=(height-parseFloat(css.getPropertyValue('--controls-row')))*aspect;
      header.toggleAttribute('data-stacked',root.innerWidth<=520||secondRowWidth>room);
    }
    function render(value){
      height=limit(Math.round(value??standard),minimum,maximum);
      rootNode.style.setProperty('--workbench-header-height',height+'px');
      fitRows();
      handle.setAttribute('aria-valuenow',height);
    }
    function refresh(){
      const css=getComputedStyle(rootNode);
      standard=parseFloat(css.getPropertyValue('--header-default'));
      minimum=parseFloat(css.getPropertyValue('--header-min'));
      maximum=Math.max(minimum,Math.min(180,Math.floor(root.innerHeight/4)));
      handle.setAttribute('aria-valuemin',minimum);handle.setAttribute('aria-valuemax',maximum);
      render(preferred);
    }
    function save(value){
      render(value);preferred=value===null?null:height;write('headerHeight',preferred);
    }
    function finish(commit){
      if(!drag)return;
      const {id,startHeight}=drag;drag=null;
      if(commit&&height!==startHeight)save(height);
      else render(preferred);
      if(handle.hasPointerCapture(id))handle.releasePointerCapture(id);
    }
    handle.addEventListener('pointerdown',event=>{
      if(drag||event.button!==0)return;
      drag={id:event.pointerId,y:event.clientY,startHeight:height};
      handle.focus({preventScroll:true});handle.setPointerCapture(event.pointerId);event.preventDefault();
    });
    handle.addEventListener('pointermove',event=>{
      if(drag?.id===event.pointerId)render(drag.startHeight+event.clientY-drag.y);
    });
    for(const type of ['pointerup','pointercancel','lostpointercapture']){
      handle.addEventListener(type,event=>{if(drag?.id===event.pointerId)finish(type==='pointerup');});
    }
    handle.addEventListener('keydown',event=>{
      if(event.key==='Escape'&&drag){event.preventDefault();finish(false);return;}
      if(drag||!['ArrowUp','ArrowDown','Home'].includes(event.key))return;
      event.preventDefault();save(event.key==='Home'?null:height+(event.key==='ArrowDown'?8:-8));
    });
    handle.addEventListener('dblclick',()=>save(null));
    root.addEventListener('blur',()=>finish(false));
    root.addEventListener('resize',()=>{finish(false);refresh();});
    root.addEventListener('atlas-language',fitRows);
    refresh();
    frameBrand(header.querySelector('.workbench-brand'),fitRows);
  }

  function initResize($,onResize){
    if(!document.documentElement?.style)return;
    initHeaderResize($('workbenchHeader'),$('headerResize'));
    const style=document.documentElement.style;
    const limits=()=>window.innerWidth<=700?{left:Math.min(520,window.innerWidth*.92),right:window.innerWidth}:{left:Math.max(220,Math.min(520,window.innerWidth-620)),right:Math.max(240,Math.min(620,window.innerWidth-620))};
    const widths={left:read('leftWidth',290),right:read('rightWidth',320)};
    function apply(side,value){const other=side==='left'?'right':'left';const available=window.innerWidth<=700?window.innerWidth*.92:window.innerWidth>1050?window.innerWidth-widths[other]-316:side==='left'?window.innerWidth-288:window.innerWidth*.9;const max=Math.min(limits()[side],available),min=side==='left'?(window.innerWidth<=700?260:220):240; widths[side]=Math.max(min,Math.min(max,Number(value)||min));style.setProperty('--'+side+'-width',widths[side]+'px');const handle=$(side==='left'?'resizeLeft':'resizeRight');handle.setAttribute('aria-valuemin',min);handle.setAttribute('aria-valuemax',max);handle.setAttribute('aria-valuenow',widths[side]);onResize?.();}
    for(const side of ['left','right']){const handle=$(side==='left'?'resizeLeft':'resizeRight');apply(side,widths[side]);
      let start=null;
      handle.addEventListener('pointerdown',e=>{if(e.button!==0)return;start={x:e.clientX,width:widths[side]};handle.setPointerCapture(e.pointerId);document.body.classList.add('resizing');e.preventDefault();});
      handle.addEventListener('pointermove',e=>{if(start)apply(side,start.width+(e.clientX-start.x)*(side==='left'?1:-1));});
      const end=()=>{if(!start)return;start=null;document.body.classList.remove('resizing');write(side+'Width',widths[side]);};
      handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end);handle.addEventListener('lostpointercapture',end);
      handle.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home'].includes(e.key))return;e.preventDefault();apply(side,e.key==='Home'?(side==='left'?290:320):widths[side]+(e.key==='ArrowRight'?20:-20)*(side==='left'?1:-1));write(side+'Width',widths[side]);});
    }
    window.addEventListener('resize',()=>{for(const side of ['left','right'])apply(side,widths[side]);});
  }
  // All rows remain addressable, but only one page owns DOM nodes/listeners.
  function pagedRows(container,rows,renderRow,{page=0,onPage=()=>{}}={}){
    const size=100,pages=Math.max(1,Math.ceil(rows.length/size));
    function show(value){
      page=Math.max(0,Math.min(pages-1,Math.floor(Number(value)||0)));onPage(page);
      container.replaceChildren();
      if(pages>1){
        const nav=document.createElement('nav');nav.className='article-pagination';
        const text=document.createElement('span');text.textContent=`${page*size+1}–${Math.min(rows.length,(page+1)*size)} / ${rows.length}`;
        const prev=document.createElement('button'),next=document.createElement('button'),input=document.createElement('input');
        prev.type=next.type='button';prev.textContent=root.AtlasI18n?.t('上一頁')||'Previous';next.textContent=root.AtlasI18n?.t('下一頁')||'Next';
        prev.disabled=page===0;next.disabled=page===pages-1;prev.onclick=()=>show(page-1);next.onclick=()=>show(page+1);
        input.type='number';input.min=1;input.max=pages;input.step=1;input.value=page+1;
        input.setAttribute('aria-label',root.AtlasI18n?.t('頁碼')||'Page');input.onchange=()=>show(Number(input.value)-1);
        nav.append(text,prev,input,next);container.append(nav);
      }
      for(const row of rows.slice(page*size,(page+1)*size))container.append(renderRow(row));
    }
    show(page);return {show};
  }
  const api={read,write,icon,labelIcon,windowBounds,fitPoint,bindWindowDrag,arrowStep,jsonTree,pagedRows,initKey,initSearch,initFloatingPanel,initSourcePanel,initTimePanel,initResize};root.AtlasUI=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
