/* Shared calendar axis for the size curve, news focus and historical OHLC evidence. */
(function(root){
 const DAY=86400000,stamp=d=>Date.parse(d+'T00:00:00Z'),clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 function model(bars,date,horizon,baseline){
  const first=baseline||date,index=bars.findIndex(b=>b.date>=first);
  if(index<0)return {index:-1,window:[],means:[],complete:false};
  const base=bars[index],window=bars.slice(index,index+horizon+1),means=[];let total=0;
  window.slice(1).forEach((bar,i)=>{total+=bar.close;means.push({date:bar.date,close:total/(i+1),return:total/(i+1)/base.close-1});});
  return {index,base,window,means,complete:means.length===horizon,end:window.at(-1)?.date};
 }
 function colors(convention){return convention==='tw'?{up:'#ff687a',down:'#58d6a2'}:{up:'#58d6a2',down:'#ff687a'};}
 function zoom(bounds,full,anchor,factor){const span=Math.min(full.end-full.start,Math.max(7*DAY,(bounds.end-bounds.start)*factor));let start=Math.round((anchor-span*.5)/DAY)*DAY;start=clamp(start,full.start,Math.max(full.start,full.end-span));const end=Math.min(full.end,start+Math.round(span/DAY)*DAY);return {start,end,days:Math.round((end-start)/DAY),startDate:new Date(start).toISOString().slice(0,10),endDate:new Date(end).toISOString().slice(0,10)};}
 function init($,{getState,onDate,onZoom=()=>{}}){
  const svg=$('priceChart'),summary=$('priceChartSummary'),axis=$('priceAlignment'),stack=$('timeChartStack');
  if(!svg)return {paint(){}};
  let drag=null;
  const t=s=>root.AtlasI18n.t(s),NS='http://www.w3.org/2000/svg';
  const add=(name,attrs,text)=>{const n=document.createElementNS(NS,name);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text)n.textContent=text;svg.append(n);return n;};
  function align(){
   const {bounds,date}=getState();if(!bounds)return;
   const r=stack.getBoundingClientRect(),bell=$('timeBell').getBoundingClientRect(),chart=svg.getBoundingClientRect();
   const fraction=clamp((stamp(date)-bounds.start)/Math.max(DAY,bounds.end-bounds.start),0,1);
   axis.style.left=(1.2+97.6*fraction)+'%';axis.style.top=Math.max(0,(bell.height?bell.top:chart.top)-r.top+8)+'px';
   const ticks=[...$('timeFocusTicks').children],step=Math.max(1,Math.ceil(ticks.length*55/Math.max(1,r.width)));ticks.forEach((n,i)=>n.hidden=i%step!==0);
   axis.style.height=Math.max(0,chart.bottom-r.top-20-parseFloat(axis.style.top))+'px';
  }
  function paint(){
   const {bars=[],date,horizon,bounds,ticker,selected,as_of,market='US',currency='USD',loading,error}=getState();if(!bounds)return;
   svg.replaceChildren();const c=colors(market==='TW'?'tw':'us'),m=model(bars,date,horizon,selected?.baseline_date);
   const result=m.complete?m.means.at(-1).return:null,legend=$('priceLegend');legend.replaceChildren();
   for(const [sign,label,color] of [[1,'上漲',c.up],[-1,'下跌',c.down]]){const n=document.createElement('span'),active=result!==null&&result*sign>0;n.textContent=t(label)+(sign>0?' ↑':' ↓');n.dataset.direction=String(sign);n.dataset.active=String(active);n.style.cssText=`color:${color};opacity:${active?1:.4};font-weight:${active?800:400};${active?'text-shadow:0 0 8px '+color+';':''}`;legend.append(n,document.createTextNode(' '));}
   legend.append(document.createTextNode('· '+t('K 線：收盤對開盤；平均線：相對基準收盤')));
   $('priceLegend').style.color='';
   const empty=$('priceChartEmpty');empty.hidden=!!bars.length;empty.textContent=loading?t('讀取股價中…'):error?t(error):!ticker?t('請填入股票代碼以顯示股價'):t('沒有可用的歷史股價');
   const x=d=>12+976*clamp((stamp(d)-bounds.start)/Math.max(DAY,bounds.end-bounds.start),0,1);
   const visible=bars.filter(b=>b.date>=bounds.startDate&&b.date<=bounds.endDate&&(!m.end||b.date<=m.end));
   const values=visible.flatMap(b=>[b.low??b.close,b.high??b.close]);
   const min=values.length?Math.min(...values):0,max=values.length?Math.max(...values):1,pad=Math.max((max-min)*.08,max*.002,.01);
   const y=v=>145-120*(v-min+pad)/(max-min+2*pad);
   // Hidden SVGs report zero width. Keep candle geometry bounded until measured.
   const pixels=svg.getBoundingClientRect().width||1000;
   const width=clamp(Math.max(650/Math.max(1,bounds.days),1200/pixels),.5,18);
   for(const v of [min,max])add('line',{x1:12,x2:988,y1:y(v),y2:y(v),stroke:'#375061','stroke-width':1});
   if(m.base){
    add('rect',{x:x(m.base.date),y:8,width:Math.max(2,x(m.end)-x(m.base.date)),height:140,fill:'#77e8c3',opacity:.08});
    add('line',{x1:x(m.base.date),x2:988,y1:y(m.base.close),y2:y(m.base.close),stroke:'#b8cad5','stroke-dasharray':'5 5',opacity:.55});
   }
   for(const b of visible){
    const full=['open','high','low'].every(k=>Number.isFinite(b[k])),color=full?(b.close>=b.open?c.up:c.down):'#a6bac8';
    const group=document.createElementNS(NS,'g');group.setAttribute('data-date',b.date);svg.append(group);
    const title=document.createElementNS(NS,'title');title.textContent=`${b.date} · O ${b.open??'—'} H ${b.high??'—'} L ${b.low??'—'} C ${b.close}`;group.append(title);
    function part(tag,attrs){const n=add(tag,attrs);group.append(n);}
    if(full){part('line',{x1:x(b.date),x2:x(b.date),y1:y(b.high),y2:y(b.low),stroke:color,'stroke-width':1});part('rect',{x:x(b.date)-width/2,y:Math.min(y(b.open),y(b.close)),width,height:Math.max(1,Math.abs(y(b.open)-y(b.close))),fill:color});}
    else part('circle',{cx:x(b.date),cy:y(b.close),r:1.6,fill:color});
   }
   if(visible.length)add('path',{d:visible.map((b,i)=>(i?'L':'M')+x(b.date)+' '+y(b.close)).join(' '),fill:'none',stroke:'#9fb6f5','stroke-width':1.25,'vector-effect':'non-scaling-stroke','data-close-line':'true'});
   let previous=m.base;
   for(const point of m.means){add('line',{x1:x(previous.date),y1:y(previous.close),x2:x(point.date),y2:y(point.close),stroke:point.return>=0?c.up:c.down,'stroke-width':3,'vector-effect':'non-scaling-stroke','data-mean':point.date});previous=point;}
   if(m.end&&x(m.end)<988)add('rect',{x:x(m.end)+width,y:8,width:Math.max(0,988-x(m.end)-width),height:140,fill:'#09131f',opacity:.85,'data-mask':'after-window'});
   $('priceAxisHigh').textContent=values.length?max.toFixed(2):'';$('priceAxisLow').textContent=values.length?min.toFixed(2):'';

   summary.textContent=m.base?`${ticker} ${currency} · ${t('焦點')} ${date} · ${t('基準收盤')} ${m.base.date} ${m.base.close.toFixed(2)} · ${horizon}${t('交易日平均報酬')} ${result===null?t('資料不足'):(result>=0?'↑ +':'↓ ')+(result*100).toFixed(2)+'%'} · ${t('截至')} ${as_of||'—'}`:t('載入股價後顯示 K 線；點選新聞或拖曳時間軸定位。');
   svg.dataset.start=bounds.startDate;svg.dataset.end=bounds.endDate;
   svg.setAttribute('aria-label',summary.textContent);svg.setAttribute('aria-valuenow',String(Math.round(100*clamp((stamp(date)-bounds.start)/Math.max(DAY,bounds.end-bounds.start),0,1))));svg.setAttribute('aria-valuetext',date);align();
  }
  svg.addEventListener('wheel',e=>{e.preventDefault();e.stopPropagation();const {bounds,fullBounds=bounds,date}=getState();if(!bounds||!e.deltaY)return;onZoom(zoom(bounds,fullBounds,stamp(date),e.deltaY<0?.8:1.25));},{passive:false});
  svg.addEventListener('dblclick',e=>{e.preventDefault();e.stopPropagation();onZoom(null);});
  svg.addEventListener('pointerleave',()=>{svg.querySelectorAll('[data-crosshair]').forEach(n=>n.remove());$('priceHover').textContent='';});
  svg.addEventListener('pointermove',e=>{const rect=svg.getBoundingClientRect(),x=clamp((e.clientX-rect.left)/rect.width*1000,12,988),y=clamp((e.clientY-rect.top)/rect.height*165,8,145);svg.querySelectorAll('[data-crosshair]').forEach(n=>n.remove());for(const attrs of [{x1:x,x2:x,y1:8,y2:145},{x1:12,x2:988,y1:y,y2:y}])add('line',{...attrs,stroke:'#d9e7ef','stroke-dasharray':'4 4','pointer-events':'none','data-crosshair':'true'});if(drag!==null)return;const {bars=[],bounds}=getState();if(!bars.length||!bounds)return;const r=svg.getBoundingClientRect(),at=bounds.start+clamp(((e.clientX-r.left)/r.width-.012)/.976,0,1)*(bounds.end-bounds.start);const b=bars.reduce((a,b)=>Math.abs(stamp(b.date)-at)<Math.abs(stamp(a.date)-at)?b:a);$('priceHover').textContent=`${b.date} · O ${b.open??'—'} · H ${b.high??'—'} · L ${b.low??'—'} · C ${b.close}`;});
  const seek=e=>{const r=svg.getBoundingClientRect(),{bounds}=getState();if(!bounds)return;const fraction=clamp(((e.clientX-r.left)/r.width-.012)/.976,0,1);onDate(new Date(bounds.start+Math.round(fraction*bounds.days)*DAY).toISOString().slice(0,10));};
  svg.addEventListener('pointerdown',e=>{if(e.button!==0)return;drag=e.pointerId;svg.setPointerCapture(e.pointerId);seek(e);e.preventDefault();e.stopPropagation();});
  svg.addEventListener('pointermove',e=>{if(drag===e.pointerId)seek(e);});
  for(const kind of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(kind,e=>{if(drag!==e.pointerId)return;drag=null;if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);});
  svg.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const {bounds,date}=getState();const value=e.key==='Home'?bounds.start:e.key==='End'?bounds.end:clamp(stamp(date)+(e.key==='ArrowLeft'?-DAY:DAY),bounds.start,bounds.end);onDate(new Date(value).toISOString().slice(0,10));});
  if(typeof ResizeObserver!=='undefined'){let queued=false;const observer=new ResizeObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;paint();});});observer.observe(stack);observer.observe(svg);}
  $('timeBellEditor').addEventListener('toggle',align);root.addEventListener('atlas-language',paint);
  return {paint,align};
 }
 const api={model,colors,zoom,init};root.AtlasPriceChart=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
