/* Geometry and chart navigation are local to this reader. No network or model work. */
(function(root){
 'use strict';
 const $=id=>document.getElementById(id);
 const clamp=(value,min,max)=>Math.max(min,Math.min(value,Math.max(min,max)));
 const day=n=>new Date(n*86400000).toISOString().slice(0,10);

 function initWindow(t){
  const tool=$('wikiTimelineTool'),lower=$('wikiLower'),grip=$('wikiTimelineGrip');
  const launcher=$('wikiTimelineLauncher'),fold=$('wikiTimelineFold'),expand=$('wikiTimelineFloat');
  const saved=root.AtlasUI.read('wikiTimelineWindow',{})||{};
  let mode=['floating','collapsed'].includes(saved.mode)?saved.mode:'docked';
  let previous=saved.previous==='floating'?'floating':'docked';
  let x=Number.isFinite(saved.x)?saved.x:null,y=Number.isFinite(saved.y)?saved.y:null,drag=null;
  const header=document.querySelector('.wiki-header');
  const bounds=()=>root.AtlasUI.windowBounds(header);
  let iconPosition=Number.isFinite(saved.iconPosition?.x)&&Number.isFinite(saved.iconPosition.y)?saved.iconPosition:null;
  function placeIcon(point=iconPosition){
   if(mode!=='collapsed'||!launcher.getClientRects().length)return;
   const graph=$('wikiCanvas').getBoundingClientRect(),r=launcher.getBoundingClientRect();
   const p=root.AtlasUI.fitPoint(point||{x:graph.left+12,y:graph.bottom-r.height-12},r,bounds());
   launcher.style.left=p.x+'px';launcher.style.top=p.y+'px';return p;
  }
  function place(){
   if(mode==='collapsed'){placeIcon();return;}
   if(mode!=='floating'||!tool.getClientRects().length)return;
   resize.constrain();
   const b=bounds(),r=tool.getBoundingClientRect(),graph=$('wikiCanvas').getBoundingClientRect();
   x=clamp(x??(graph.left+(graph.width-r.width)/2),b.left,b.right-r.width);
   y=clamp(y??(b.top+(b.height-r.height)/2),b.top,b.bottom-r.height);
   tool.style.left=x+'px';tool.style.top=y+'px';
  }
  const resize=root.AtlasFloatingResize.attach({panel:tool,bounds,collapsed:()=>mode!=='floating',
   initial:{width:saved.width||720,height:saved.height||400},onStart:()=>{},
   onMove(dx,dy){x+=dx;y+=dy;place();},onFinish(){place();persist();}});
  function persist(){root.AtlasUI.write('wikiTimelineWindow',{mode,previous,x,y,iconPosition,...resize.state()});}
  function labels(){
   const title=t('L1 觀點群 × 引用新聞日期（UTC）','L1 opinion groups × cited news date (UTC)');
   $('wikiTimelineTitle').textContent=title;
   grip.title=t('拖動時間軸視窗，或用方向鍵移動','Drag the timeline window or move it with arrow keys');
   grip.setAttribute('aria-label',grip.title);
   root.AtlasUI.labelIcon(launcher,'chart',t('開啟觀點時間軸','Open viewpoint timeline'));
   root.AtlasUI.labelIcon(fold,'minimize',t('縮小時間軸','Minimize timeline'));
   root.AtlasUI.labelIcon(expand,mode==='floating'?'dock':'expand',mode==='floating'?t('停駐在圖譜下方','Dock below graph'):t('放大為浮動視窗','Expand into floating window'));
   root.AtlasUI.labelIcon($('wikiTimelineReset'),'reset',t('返回全部分類與完整日期','Reset classifications and date range'));
   const edges={n:['上','top'],s:['下','bottom'],e:['右','right'],w:['左','left'],nw:['左上','top left'],ne:['右上','top right'],sw:['左下','bottom left'],se:['右下','bottom right']};
   for(const handle of tool.querySelectorAll('[data-resize-edge]')){
    const [zh,en]=edges[handle.dataset.resizeEdge];
    handle.title=t('從'+zh+'側調整時間軸大小','Resize timeline from '+en);
    handle.setAttribute('aria-label',handle.title);
   }
  }
  function display(next){
   mode=next;tool.dataset.mode=mode;lower.dataset.timeline=mode;
   tool.hidden=mode==='collapsed';launcher.hidden=mode!=='collapsed';
   launcher.setAttribute('aria-expanded',String(mode!=='collapsed'));labels();place();
  }
  fold.onclick=()=>{
   if(!iconPosition&&mode==='floating'){const r=tool.getBoundingClientRect();iconPosition={x:r.left,y:r.top};}
   previous=mode;display('collapsed');persist();launcher.focus({preventScroll:true});
  };
  root.AtlasUI.bindWindowDrag(launcher,{
   start(e){const r=launcher.getBoundingClientRect();return {dx:e.clientX-r.left,dy:e.clientY-r.top,iconPosition};},
   move(e,d){iconPosition=placeIcon({x:e.clientX-d.dx,y:e.clientY-d.dy});},
   finish(e,d,cancel){if(cancel){iconPosition=d.iconPosition;placeIcon();}persist();}
  });
  launcher.addEventListener('keydown',e=>{
   const step=root.AtlasUI.arrowStep(e.key);if(!step)return;
   e.preventDefault();const r=launcher.getBoundingClientRect();
   iconPosition=placeIcon({x:r.left+step[0],y:r.top+step[1]});persist();
  });
  launcher.onclick=()=>{display(previous);persist();grip.focus({preventScroll:true});};
  expand.onclick=()=>{display(mode==='floating'?'docked':'floating');persist();};
  grip.onpointerdown=e=>{
   if(e.button!==0||drag)return;
   const r=grip.getBoundingClientRect();
   drag={id:e.pointerId,cx:e.clientX,cy:e.clientY,offsetX:e.clientX-r.left,offsetY:e.clientY-r.top,
    initial:{x,y,mode},moved:false};
   grip.setPointerCapture(e.pointerId);
  };
  grip.onpointermove=e=>{
   if(!drag||drag.id!==e.pointerId)return;
   if(!drag.moved&&Math.hypot(e.clientX-drag.cx,e.clientY-drag.cy)<5)return;
   drag.moved=true;
   if(mode!=='floating')display('floating');
   const r=tool.getBoundingClientRect(),g=grip.getBoundingClientRect();
   x=e.clientX-Math.min(drag.offsetX,g.width-8)-(g.left-r.left);
   y=e.clientY-drag.offsetY-(g.top-r.top);place();
  };
  function finish(e,cancel=false){
   if(!drag||e&&drag.id!==e.pointerId)return;
   const d=drag;drag=null;
   if(cancel&&d.moved){x=d.initial.x;y=d.initial.y;display(d.initial.mode);}
   if(grip.hasPointerCapture(d.id))grip.releasePointerCapture(d.id);
   if(d.moved)persist();
  }
  grip.onpointerup=e=>finish(e);grip.onpointercancel=grip.onlostpointercapture=e=>finish(e,true);
  grip.onkeydown=e=>{
   const movement={ArrowLeft:[-20,0],ArrowRight:[20,0],ArrowUp:[0,-20],ArrowDown:[0,20]}[e.key];
   if(!movement)return;
   e.preventDefault();if(mode!=='floating')display('floating');
   x+=movement[0];y+=movement[1];place();persist();
  };
  grip.onclick=e=>{if(e.detail===0)expand.click();};
  root.addEventListener('blur',()=>finish(null,true));root.addEventListener('resize',place);
  const observer=new ResizeObserver(place);observer.observe(header);
  display(mode);return {labels};
 }

 function create(t,selectTerm,inspect){
  const box=$('wikiTimeline'),reset=$('wikiTimelineReset'),legend=document.createElement('div');
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  const empty=document.createElement('small'),hover=document.createElement('div');
  legend.className='wiki-chart-legend';legend.setAttribute('role','group');
  svg.setAttribute('role','group');svg.setAttribute('tabindex','0');
  hover.className='wiki-chart-tooltip';hover.setAttribute('role','tooltip');hover.hidden=true;
  box.append(legend,svg,empty,hover);
  let rows=[],terms=[],selected='',bounds=null,view=null,drag=null,moved=false;
  function interval(){
   const total=bounds.end-bounds.start+1,count=clamp(view?.count??total,1,total);
   const start=clamp(view?.start??bounds.start,bounds.start,bounds.end-count+1);
   return {start,count,end:start+count-1};
  }
  function draw(){
   reset.disabled=!selected&&!view;
   if(!bounds){delete box.dataset.start;delete box.dataset.end;svg.replaceChildren();return;}
   const {start,end,count}=interval();box.dataset.start=start;box.dataset.end=end;
   const width=svg.clientWidth,height=svg.clientHeight;
   if(width<52||height<36)return;
   const left=36,right=12,base=height-24,plotWidth=width-left-right,plotHeight=base-12;
   const bins=Math.min(60,count),groups=Array.from({length:bins},()=>new Map());
   for(const row of rows){
    if(!Number.isFinite(row.date)||row.date<start||row.date>end)continue;
    const group=groups[Math.floor((row.date-start)/count*bins)];
    for(const id of row.tags)if(!selected||id===selected)group.set(id,(group.get(id)||0)+1);
   }
   const max=Math.max(1,...groups.map(g=>Array.from(g.values()).reduce((a,b)=>a+b,0)));
   const fragment=document.createDocumentFragment();
   function add(tag,attrs,text){
    const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);
    if(text!==undefined)n.textContent=text;fragment.append(n);return n;
   }
   svg.setAttribute('viewBox','0 0 '+width+' '+height);
   add('line',{x1:left,y1:base,x2:width-right,y2:base,stroke:'var(--line)'});
   add('text',{x:2,y:14},max);add('text',{x:8,y:base},'0');
   groups.forEach((g,i)=>{
    let y=base;const a=start+Math.ceil(i*count/bins),b=start+Math.ceil((i+1)*count/bins)-1;
    for(const term of terms){
     const n=g.get(term.id);if(!n)continue;
     const h=n/max*plotHeight;y-=h;
     const label=day(a)+' → '+day(b)+' · '+term.name+' · '+n;
     const bar=add('rect',{x:left+i*plotWidth/bins,y,width:Math.max(1,plotWidth/bins-1),height:h,fill:term.color,
      tabindex:0,role:'button','data-category':term.id,'data-count':n,'aria-label':label});
     bar.onclick=e=>{if(!moved||e.detail===0)inspect(term.id,a,b);};
     bar.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspect(term.id,a,b);}};
     bar.onpointermove=e=>{
      if(drag||e.pointerType==='touch')return;
      hover.textContent=label;hover.hidden=false;
      hover.style.left=clamp(e.clientX+10,4,innerWidth-hover.offsetWidth-4)+'px';
      hover.style.top=Math.max(4,e.clientY-hover.offsetHeight-8)+'px';
     };
     bar.onpointerleave=()=>hover.hidden=true;
    }
   });
   add('text',{x:left,y:height-5},day(start));
   if(end!==start)add('text',{x:width-right,y:height-5,'text-anchor':'end'},day(end));
   svg.replaceChildren(fragment);
  }
  function navigate(start,count){
   const total=bounds.end-bounds.start+1;
   count=clamp(count,1,total);start=clamp(start,bounds.start,bounds.end-count+1);
   if(start===Number(box.dataset.start)&&start+count-1===Number(box.dataset.end))return;
   view=count===total?null:{start,count};hover.hidden=true;draw();
  }
  function zoom(inward,anchor=.5){
   const {start,count}=interval(),next=inward?Math.min(count-1,Math.round(count/1.3)):Math.max(count+1,Math.round(count*1.3));
   const size=clamp(next,1,bounds.end-bounds.start+1);navigate(start+Math.round((count-size)*anchor),size);
  }
  svg.addEventListener('wheel',e=>{
   if(!bounds)return;e.preventDefault();
   const r=svg.getBoundingClientRect(),width=Math.max(1,r.width-48);
   if(e.shiftKey||Math.abs(e.deltaX)>Math.abs(e.deltaY)){
    const pixels=(e.deltaX||e.deltaY)*(e.deltaMode===1?16:e.deltaMode===2?width:1);
    const {start,count}=interval();navigate(start+Math.sign(pixels)*Math.max(1,Math.round(Math.abs(pixels)*count/width)),count);
   }else if(e.deltaY)zoom(e.deltaY<0,clamp((e.clientX-r.left-36)/width,0,1));
  },{passive:false});
  svg.onpointerdown=e=>{
   if(e.button!==0||drag||!bounds)return;
   moved=false;drag={id:e.pointerId,x:e.clientX,width:Math.max(1,svg.clientWidth-48),...interval()};
   // Let a stationary bar receive its native click. A drag transfers capture
   // to the persistent plot before its first redraw can replace that bar.
   if(e.isTrusted)e.target.setPointerCapture(e.pointerId);
  };
  svg.onpointermove=e=>{
   if(!drag||drag.id!==e.pointerId)return;
   const dx=e.clientX-drag.x;if(!moved&&Math.abs(dx)<4)return;
   moved=true;hover.hidden=true;
   if(!svg.hasPointerCapture(drag.id))svg.setPointerCapture(drag.id);
   svg.classList.add('panning');navigate(drag.start-Math.round(dx*drag.count/drag.width),drag.count);
  };
  function end(e){
   if(!drag||e&&e.pointerId!==drag.id)return;
   const id=drag.id;drag=null;svg.classList.remove('panning');
   if(svg.hasPointerCapture(id))svg.releasePointerCapture(id);
  }
  root.addEventListener('pointerup',end);root.addEventListener('pointercancel',end);
  svg.onlostpointercapture=e=>{if(e.target===svg)end(e);};
  root.addEventListener('blur',()=>end());
  svg.onkeydown=e=>{
   if(!bounds||!['ArrowLeft','ArrowRight','+','=','-','Home'].includes(e.key))return;
   e.preventDefault();const {start,count}=interval();
   if(e.key==='Home'){view=null;draw();}
   else if(e.key.startsWith('Arrow'))navigate(start+(e.key==='ArrowLeft'?-1:1)*Math.max(1,Math.round(count*.2)),count);
   else zoom(e.key!=='-');
   svg.focus({preventScroll:true});
  };
  reset.onclick=()=>{view=null;if(selected)selectTerm('');else draw();};
  new ResizeObserver(draw).observe(svg);
  function update(next){
   rows=next.rows;terms=next.terms;bounds=next.bounds;selected=next.selected;
   // A background graph refresh may arrive between pointerdown and click.
   // Keep each existing button attached while its term is still available.
   const remaining=new Map(Array.from(legend.children,b=>[b.dataset.term,b]));
   terms.forEach((term,i)=>{
    let b=remaining.get(term.id);
    if(!b){
     b=document.createElement('button');b.type='button';b.dataset.term=term.id;
     b.onclick=()=>selectTerm(term.id===selected?'':term.id);
    }
    if(b.textContent!==term.name)b.textContent=term.name;
    b.style.setProperty('--series',term.color);b.setAttribute('aria-pressed',String(term.id===selected));
    if(legend.children[i]!==b)legend.insertBefore(b,legend.children[i]||null);
    remaining.delete(term.id);
   });
   for(const removed of remaining.values())removed.remove();
   legend.setAttribute('aria-label',t('觀點分類','Viewpoint classifications'));
   svg.setAttribute('aria-label',t('觀點數量。滾輪縮放、拖曳或用方向鍵平移，選取長條查看觀點。多標籤觀點可計入多個分類。','Viewpoint counts. Wheel to zoom, drag or use arrow keys to pan. Select a bar to read its viewpoints. A viewpoint may count in multiple series.'));
   svg.style.display=bounds?'':'none';empty.hidden=!!bounds;
   empty.textContent=t('此範圍尚無可統計的觀點群','No dated opinion groups in this range');
   hover.hidden=true;draw();
  }
  return {update,resetRange(){view=null;end();}};
 }
 root.AtlasWikiTimeline={create,initWindow};
})(globalThis);
