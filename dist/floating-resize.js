/* Floating geometry only: resize never changes the graph or control values. */
(function(root){
 function attach({panel,bounds,collapsed,initial,onStart,onMove,onFinish}){
  const dimension=(value,fallback)=>Number.isFinite(Number(value))&&Number(value)>0?Number(value):fallback;
  let width=dimension(initial.width,panel.id==='timeFocusBar'?480:430),height=dimension(initial.height,panel.id==='timeFocusBar'?380:320),drag=null;
  const clamp=(n,a,b)=>Math.max(Math.min(a,b),Math.min(b,n)),enabled=()=>!collapsed()&&!root.AtlasDock?.docked(panel);
  panel.classList.add('floating-resizable');
  function constrain(){if(!enabled())return;const b=bounds();panel.style.setProperty('--floating-width',clamp(width,280,b.width-16)+'px');panel.style.setProperty('--floating-height',clamp(height,180,b.height-8)+'px');}
  function end(e,cancel=false){if(!drag||e?.pointerId!==undefined&&e.pointerId!==drag.id)return;const d=drag;drag=null;
   if(cancel){width=d.width;height=d.height;constrain();onMove(d.rect.left-panel.getBoundingClientRect().left,d.rect.top-panel.getBoundingClientRect().top);}
   if(d.handle.hasPointerCapture(d.id))d.handle.releasePointerCapture(d.id);panel.classList.remove('floating-sizing');constrain();onFinish();
  }
  for(const edge of ['n','e','s','w','ne','se','sw','nw']){
   const h=document.createElement('div');h.className='floating-size-handle';h.dataset.resizeEdge=edge;h.tabIndex=['n','e','s','w','se'].includes(edge)?0:-1;h.setAttribute('role','separator');h.setAttribute('aria-label','Resize panel: '+edge);h.title='拖曳調整大小 / Drag to resize';h.setAttribute('aria-orientation',['e','w'].includes(edge)?'vertical':'horizontal');panel.append(h);
   h.addEventListener('pointerdown',e=>{if(e.button!==0||!enabled())return;e.preventDefault();e.stopPropagation();onStart();const r=panel.getBoundingClientRect();drag={id:e.pointerId,edge,handle:h,x:e.clientX,y:e.clientY,rect:r,width,height};h.setPointerCapture(e.pointerId);panel.classList.add('floating-sizing');});
   h.addEventListener('pointermove',e=>{if(drag?.id!==e.pointerId)return;e.preventDefault();e.stopPropagation();const d=drag,r=d.rect,b=bounds(),dx=e.clientX-d.x,dy=e.clientY-d.y;
    const left=edge.includes('w')?clamp(r.left+dx,b.left,r.right-Math.min(280,b.width-16)):r.left,right=edge.includes('e')?clamp(r.right+dx,r.left+Math.min(280,b.width-16),b.right):r.right;
    const top=edge.includes('n')?clamp(r.top+dy,b.top,r.bottom-Math.min(180,b.height-8)):r.top,bottom=edge.includes('s')?clamp(r.bottom+dy,r.top+Math.min(180,b.height-8),b.bottom):r.bottom;
    width=right-left;height=bottom-top;constrain();const placed=panel.getBoundingClientRect();onMove(left-placed.left,top-placed.top);
   });
   h.addEventListener('pointerup',e=>{e.stopPropagation();end(e);});h.addEventListener('pointercancel',e=>end(e,true));h.addEventListener('lostpointercapture',e=>end(e,true));h.addEventListener('click',e=>e.stopPropagation());
   h.addEventListener('keydown',e=>{if(!enabled()||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(e.key))return;e.preventDefault();e.stopPropagation();onStart();const r=panel.getBoundingClientRect();width=r.width;height=r.height;if(e.key==='Home'){width=panel.id==='timeFocusBar'?480:430;height=panel.id==='timeFocusBar'?380:320;}else if(e.key==='ArrowLeft'||e.key==='ArrowRight')width+=e.key==='ArrowRight'?20:-20;else height+=e.key==='ArrowDown'?20:-20;const b=bounds();width=clamp(width,280,b.width-16);height=clamp(height,180,b.height-8);constrain();onMove(0,0);onFinish();});
  }
  root.addEventListener('blur',()=>end(null,true));constrain();return {constrain,state:()=>({width,height})};
 }
 root.AtlasFloatingResize={attach};
})(globalThis);
