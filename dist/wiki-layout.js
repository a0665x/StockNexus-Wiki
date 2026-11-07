/* Wiki pane geometry is independent from graph data and model work. */
(function(root){
 const defaults={left:280,right:280,bottom:260,live:150},clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function init(panel,onChange){
  const $=id=>document.getElementById(id),header=document.querySelector('body>header'),main=panel.querySelector('.wiki-canvas-area');
  let values={...defaults},drag=null,queued=false;
  try{const saved=JSON.parse(localStorage.getItem('stocknexus.wikiLayout')||'null');values={...values,...saved};values.left=Number(saved?.left)||Number(localStorage.getItem('stocknexus.wikiLeftWidth'))||280;}catch{}
  for(const key of Object.keys(defaults))values[key]=Number.isFinite(values[key])?clamp(values[key],key==='live'?64:key==='bottom'?140:220,key==='live'?340:key==='bottom'?700:620):defaults[key];
  const bars={left:$('wikiResizeLeft'),right:$('wikiResizeRight'),bottom:$('wikiResizeTimeline'),live:$('wikiResizeLive')};
  function limits(){
   const available=Math.max(440,panel.clientWidth-280),fixed=[...main.children].filter(n=>!n.classList.contains('wiki-graph-stage')&&n.id!=='wikiLower'&&n.id!=='wikiResizeTimeline').reduce((s,n)=>s+n.getBoundingClientRect().height,0);
   return {available,bottom:Math.max(140,Math.min(700,main.clientHeight-fixed-150))};
  }
  function refresh(){
   panel.style.setProperty('--wiki-top',Math.max(0,header.getBoundingClientRect().bottom)+'px');
   if(panel.hidden||innerWidth<=800)return;
   const {available,bottom}=limits(),left=clamp(values.left,220,Math.min(620,available-220)),right=clamp(values.right,220,Math.min(620,available-left));
   const actual={left,right,bottom:clamp(values.bottom,140,bottom),live:clamp(values.live,64,Math.max(64,Math.min(340,main.clientHeight-300)))};
   for(const [key,value] of Object.entries(actual)){panel.style.setProperty('--wiki-'+key,value+'px');const bar=bars[key];bar.setAttribute('aria-valuenow',Math.round(value));bar.setAttribute('aria-valuemin',key==='live'?64:key==='bottom'?140:220);bar.setAttribute('aria-valuemax',Math.round(key==='live'?340:key==='bottom'?bottom:Math.min(620,available-actual[key==='left'?'right':'left'])));}
  }
  function schedule(){if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;refresh();});}
  function persist(){try{localStorage.setItem('stocknexus.wikiLayout',JSON.stringify(values));localStorage.setItem('stocknexus.wikiLeftWidth',values.left);}catch{}onChange?.();}
  function set(key,value){
   if(innerWidth<=800)return;
   const {available,bottom}=limits();
   values.left=parseFloat(panel.style.getPropertyValue('--wiki-left'))||280;values.right=parseFloat(panel.style.getPropertyValue('--wiki-right'))||280;
   values[key]=clamp(value,key==='live'?64:key==='bottom'?140:220,key==='live'?340:key==='bottom'?bottom:Math.min(620,available-values[key==='left'?'right':'left']));refresh();
  }
  function finish(e,cancel=false){if(!drag||e&&e.pointerId!==undefined&&e.pointerId!==drag.id)return;const old=drag;drag=null;if(cancel)values=old.before;if(old.bar.hasPointerCapture(old.id))old.bar.releasePointerCapture(old.id);document.body.classList.remove('wiki-sizing');refresh();persist();}
  for(const [key,bar] of Object.entries(bars)){
   bar.onpointerdown=e=>{if(e.button!==0||drag||innerWidth<=800)return;refresh();drag={key,bar,id:e.pointerId,start:['bottom','live'].includes(key)?e.clientY:e.clientX,value:Number(bar.getAttribute('aria-valuenow')),before:{...values}};bar.setPointerCapture(e.pointerId);document.body.classList.add('wiki-sizing');e.preventDefault();};
   bar.onpointermove=e=>{if(drag?.id!==e.pointerId)return;const delta=(['bottom','live'].includes(key)?e.clientY:e.clientX)-drag.start;set(key,drag.value+(['left','live'].includes(key)?delta:-delta));e.preventDefault();};
   bar.onpointerup=e=>finish(e);bar.onpointercancel=e=>finish(e,true);bar.onlostpointercapture=e=>finish(e,true);
   bar.onkeydown=e=>{const arrows=key==='live'?['ArrowUp','ArrowDown']:key==='bottom'?['ArrowDown','ArrowUp']:['ArrowLeft','ArrowRight'];if(![...arrows,'Home'].includes(e.key))return;e.preventDefault();const amount=e.key===arrows[0]?-20:20;set(key,e.key==='Home'?defaults[key]:Number(bar.getAttribute('aria-valuenow'))+(key==='right'?-amount:amount));persist();};
  }
  const observer=new ResizeObserver(schedule);for(const n of [header,panel,main,$('wikiLive'),$('wikiCounts'),$('wikiVersionInfo'),main.querySelector('.wiki-toolbar')])observer.observe(n);
  root.addEventListener('resize',schedule);root.addEventListener('blur',()=>finish(null,true));refresh();
  return {refresh,state:()=>({...values}),restore(saved){if(!saved)return;for(const key of Object.keys(defaults))if(Number.isFinite(saved[key]))values[key]=clamp(saved[key],key==='live'?64:key==='bottom'?140:220,key==='live'?340:key==='bottom'?700:620);refresh();}};
 }
 root.AtlasWikiLayout={init};
})(globalThis);
