/* Browser preferences and lazy, text-only JSON inspection. No credentials enter graph data. */
(function(root){
  const read=(key,fallback=null)=>{try{return JSON.parse(localStorage.getItem('graphnews.'+key))??fallback;}catch{return fallback;}};
  const write=(key,value)=>{try{if(value===null)localStorage.removeItem('graphnews.'+key);else localStorage.setItem('graphnews.'+key,JSON.stringify(value));return true;}catch{return false;}};
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
      const ok=write('searchDraft',draft);$('searchDraftStatus').textContent=ok?'搜尋設定已自動保存在此瀏覽器。':'瀏覽器儲存不可用；重新整理後無法保留搜尋設定。';return ok;
    }
    for(const id of ['query','ticker','rssRegion','forceRefresh',...providers.map(p=>'source-'+p)])for(const event of ['input','change'])$(id).addEventListener(event,save);
    dates.onChange(save);save();return save;
  }
  // Each stage coordinates its tools, including restored and resized geometry.
  const floatingStages=new WeakMap();
  function initFloatingPanel($,{key,panelId,bodyId,handleId,toggleId,resetId,onChange=()=>{}}){
    const panel=$(panelId),body=$(bodyId),handle=$(handleId),toggle=$(toggleId),stage=$('stage');
    let group=floatingStages.get(stage);if(!group){group={panels:[],busy:false};floatingStages.set(stage,group);}
    const saved=read(key,{});let x=Number(saved?.x)||0,y=Number(saved?.y)||0,collapsed=saved?.collapsed===true,drag=null,suppressClick=false,resizer=null;
    const persist=()=>write(key,{x,y,collapsed,...resizer?.state()});
    const rectOf=()=>panel.getBoundingClientRect();
    const areaOf=()=>{const r=stage.getBoundingClientRect(),counter=$('activityCounters')?.getBoundingClientRect?.(),reserved=counter?.height?counter.bottom-r.top+12:114,gap=Math.min(Math.max(114,reserved),Math.max(r.height*.25,r.height-80));return {left:r.left,right:r.right,top:r.top+gap,bottom:r.bottom,width:r.width,height:r.height-gap};};
    const overlaps=(a,b)=>a.left<b.left+b.width+8&&a.left+a.width+8>b.left&&a.top<b.top+b.height+8&&a.top+a.height+8>b.top;
    function avoid(){
      if(group.busy)return;
      // Resize observers of inactive tools must yield to the tool the user opened.
      const active=group.panels.find(p=>p.panel===group.active);
      if(active&&active.panel!==panel&&!root.AtlasDock?.docked(active.panel)){active.constrain();return;}
      group.busy=true;
      try{
        for(const other of group.panels){
          if(other.panel===panel||root.AtlasDock?.docked(other.panel))continue;
          let a=rectOf(),b=other.rect();if(!overlaps(a,b))continue;
          const area=areaOf();
          const place=()=>{
            a=rectOf();b=other.rect();
            const clampX=v=>Math.max(area.left,Math.min(area.right-a.width,v));
            const clampY=v=>Math.max(area.top,Math.min(area.bottom-a.height,v));
            const candidates=[[b.left-a.width-8,clampY(a.top)],[b.left+b.width+8,clampY(a.top)],[clampX(a.left),b.top-a.height-8],[clampX(a.left),b.top+b.height+8]];
            const valid=candidates.filter(([left,top])=>left>=area.left&&top>=area.top&&left+a.width<=area.right&&top+a.height<=area.bottom&&!overlaps({left,top,width:a.width,height:a.height},b));
            valid.sort((u,v)=>Math.hypot(u[0]-a.left,u[1]-a.top)-Math.hypot(v[0]-a.left,v[1]-a.top));
            if(!valid.length)return false;
            x+=valid[0][0]-a.left;y+=valid[0][1]-a.top;panel.style.transform=`translate(${x}px,${y}px)`;persist();return true;
          };
          if(!place()){
            other.compact();
            if(!place()){
              // A compact sibling in the middle must yield to the tool being opened.
              const small=other.rect();let placed=false;
              for(const [left,top] of [[area.left,area.top],[area.right-small.width,area.top],[area.left,area.bottom-small.height],[area.right-small.width,area.bottom-small.height]]){
                other.moveTo(left,top);if(place()){placed=true;break;}
              }
              if(!placed){
                // Keep the requested tool open; scroll its body in the remaining space.
                panel.style.maxHeight=Math.max(72,area.height-small.height-8)+'px';
                other.moveTo(area.left,area.top);place();persist();
              }
            }
          }
        }
      }finally{group.busy=false;}
    }
    function constrain(){
      if(root.AtlasDock?.docked(panel)){panel.style.maxHeight='';onChange();return;}
      resizer?.constrain();
      const area=areaOf();
      const sibling=group.panels.some(p=>p.panel!==panel&&!root.AtlasDock?.docked(p.panel));
      const reserve=!collapsed&&sibling&&rectOf().width+80>area.width?80:0;
      panel.style.maxHeight=Math.max(72,area.height-reserve)+'px';
      const rect=panel.getBoundingClientRect(),baseX=rect.left-x,baseY=rect.top-y;
      x=Math.max(area.left-baseX,Math.min(area.right-baseX-rect.width,x));
      y=Math.max(area.top-baseY,Math.min(area.bottom-baseY-Math.min(rect.height,area.height),y));
      panel.style.transform=`translate(${x}px,${y}px)`;avoid();onChange();
    }
    function paint(){body.hidden=collapsed;panel.classList.toggle('collapsed',collapsed);toggle.setAttribute('aria-expanded',String(!collapsed));handle.setAttribute('aria-expanded',String(!collapsed));panel.style.transform=`translate(${x}px,${y}px)`;constrain();root.AtlasDock?.reflow(panel);}
    function fold(){const before=panel.getBoundingClientRect();collapsed=!collapsed;if(!collapsed)group.active=panel;paint();const after=panel.getBoundingClientRect();x+=before.left-after.left;y+=before.top-after.top;panel.style.transform=`translate(${x}px,${y}px)`;constrain();persist();}
    toggle.onclick=fold;
    $(resetId).onclick=()=>{x=0;y=0;panel.style.transform='';constrain();if(x===0&&y===0)panel.style.transform='';persist();};
    panel.addEventListener('click',e=>{if(e.target===panel&&collapsed&&!suppressClick)fold();});
    handle.onclick=e=>{if(suppressClick&&e?.detail!==0){suppressClick=false;return;}if(collapsed)fold();};
    const start=e=>{
      if(e.button!==0||e.target?.closest?.('[data-resize-edge]'))return;
      const control=e.target?.closest?.('button,input,select,textarea,a,label,summary,svg,[role="slider"],[contenteditable="true"]');
      if(control&&control!==handle)return;
      group.active=panel;drag={id:e.pointerId,cx:e.clientX,cy:e.clientY,x,y,moved:false,docked:root.AtlasDock?.docked(panel),grabX:e.clientX-rectOf().left,grabY:e.clientY-rectOf().top};panel.setPointerCapture(e.pointerId);e.preventDefault();e.stopPropagation();
    };
    const move=e=>{if(!drag||drag.id!==e.pointerId)return;drag.moved ||= Math.hypot(e.clientX-drag.cx,e.clientY-drag.cy)>4;if(!drag.moved)return;if(drag.docked){root.AtlasDock.undock(panel);x=0;y=0;panel.style.transform='';const r=rectOf();drag.x=e.clientX-r.left-Math.min(drag.grabX,r.width-20);drag.y=e.clientY-r.top-Math.min(drag.grabY,24);drag.cx=e.clientX;drag.cy=e.clientY;drag.docked=false;}root.AtlasDock?.preview(e);x=drag.x+e.clientX-drag.cx;y=drag.y+e.clientY-drag.cy;panel.style.transform=`translate(${x}px,${y}px)`;constrain();};
    const end=e=>{if(!drag||drag.id!==e.pointerId)return;suppressClick=drag.moved;if(drag.moved)root.AtlasDock?.finish(panel,e,e.type!=='pointerup');if(suppressClick)setTimeout(()=>{suppressClick=false;},0);drag=null;if(panel.hasPointerCapture?.(e.pointerId))panel.releasePointerCapture(e.pointerId);persist();};
    // Keep handle listeners for keyboard/legacy integrations; stop bubbling on start.
    for(const surface of [panel,handle]){
      surface.addEventListener('pointerdown',start);surface.addEventListener('pointermove',move);
      for(const event of ['pointerup','pointercancel','lostpointercapture'])surface.addEventListener(event,end);
    }
    handle.addEventListener('keydown',e=>{const delta={ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]}[e.key];if(!delta)return;e.preventDefault();x+=delta[0];y+=delta[1];panel.style.transform=`translate(${x}px,${y}px)`;constrain();persist();});
    if(typeof ResizeObserver!=='undefined'){let queued=false;const observer=new ResizeObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;constrain();});});observer.observe(stage);observer.observe(panel);const counters=$('activityCounters');if(counters?.nodeType===1)observer.observe(counters);}
    group.panels.push({panel,rect:rectOf,constrain,moveTo(left,top){const rect=rectOf();x+=left-rect.left;y+=top-rect.top;panel.style.transform=`translate(${x}px,${y}px)`;constrain();persist();},compact(){if(collapsed)return;const before=rectOf();collapsed=true;paint();const after=rectOf();x+=before.left-after.left;y+=before.top-after.top;panel.style.transform=`translate(${x}px,${y}px)`;constrain();persist();}});
    resizer=root.AtlasFloatingResize?.attach({panel,bounds:areaOf,collapsed:()=>collapsed,initial:saved,onStart(){group.active=panel;},onMove(dx,dy){x+=dx;y+=dy;panel.style.transform=`translate(${x}px,${y}px)`;constrain();},onFinish(){constrain();persist();}});
    paint();return {constrain,state:()=>({x,y,collapsed,...resizer?.state()})};
  }
  const initSourcePanel=$=>initFloatingPanel($,{key:'sourcePanel',panelId:'sourcePanel',bodyId:'sourcePanelBody',handleId:'sourcePanelDrag',toggleId:'sourcePanelToggle',resetId:'sourcePanelReset'});
  const initTimePanel=($,onChange)=>initFloatingPanel($,{key:'timePanel',panelId:'timeFocusBar',bodyId:'timeFocusBody',handleId:'timePanelDrag',toggleId:'timePanelToggle',resetId:'timePanelReset',onChange});
  function initResize($,onResize){
    if(!document.documentElement?.style)return;
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
  const api={read,write,jsonTree,pagedRows,initKey,initSearch,initFloatingPanel,initSourcePanel,initTimePanel,initResize};root.AtlasUI=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
