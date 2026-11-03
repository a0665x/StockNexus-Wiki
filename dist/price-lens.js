/* Price evidence is an optional display lens; never changes graph edges or physics. */
(function(root){
 const horizons=[1,3,5,7],clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 function settings(value={}){return {mix:typeof value.mix==='number'&&Number.isFinite(value.mix)?clamp(value.mix,0,1):0,horizon:horizons.includes(value.horizon)?value.horizon:3};}
 function priceScale(value,reference=.05){return typeof value==='number'&&Number.isFinite(value)?2**(2*clamp(reference>0?value/reference:0,-1,1)):null;}
 function parts(time,value,mix,reference){const price=priceScale(value,reference),w=clamp(mix,0,1),a=price===null?time:(1-w)*time,b=price===null?0:w*price;return {time:a,price:b,total:a+b,priceShare:b/(a+b),delta:value,normalized:price===null?null:clamp(reference>0?value/reference:0,-1,1),reference};}
 function blend(time,value,mix,reference){return parts(time,value,mix,reference).total;}
 const scales=new WeakMap();
 function reference(data,horizon){if(!data)return 0;let cache=scales.get(data);if(!cache){cache={};scales.set(data,cache);}if(horizon in cache)return cache[horizon];const values=[],bars=data.bars||[];
  for(let i=0;i+horizon<bars.length;i++){let sum=0;for(let j=1;j<=horizon;j++)sum+=bars[i+j].close/bars[i].close-1;values.push(Math.abs(sum/horizon));}
  // Old snapshots may only have article observations: deduplicate their baseline sessions.
  if(!values.length){const seen=new Set();for(const row of Object.values(data.observations||{})){const v=row.returns?.[horizon],key=row.baseline_date||row.published_at;if(!seen.has(key)&&typeof v==='number'&&Number.isFinite(v)){seen.add(key);values.push(Math.abs(v));}}}
  values.sort((a,b)=>a-b);return cache[horizon]=values.length?values[Math.ceil(values.length*.95)-1]:0;
 }
 function init($,{articles,ticker,onChange,focus=()=>({}),onDate=()=>{}}){
  let cfg=settings(root.AtlasUI.read('priceFocus',{})),data=null,loading=false,error='',epoch=0,abort=null,selected=null,chart=null,autoTimer=null,attempted='',savedTicker='',viewport=null;
  const t=x=>root.AtlasI18n.t(x),chosen=()=>String(ticker()||savedTicker||'').trim().toUpperCase();
  const metric=a=>{const row=data?.observations?.[a.id];return row&&row.published_at===a.published_at?row.returns?.[cfg.horizon]??null:null;};
  function paint(){
   $('priceMix').value=Math.round(cfg.mix*100);$('priceHorizon').value=horizons.indexOf(cfg.horizon);
   $('priceMixValue').textContent=t('時間')+' '+Math.round((1-cfg.mix)*100)+'% · '+t('股價')+' '+Math.round(cfg.mix*100)+'%';
   $('priceHorizonValue').textContent=cfg.horizon+' '+t('交易日');
   const count=articles().filter(a=>metric(a)!==null).length;
   $('priceStatus').textContent=(data?.ticker||chosen()||t('未指定股票'))+' · '+(loading?t('讀取股價中…'):error?t(error):data?`${count}/${articles().length} ${t('篇有完整股價')} · ${t('截至')} ${data.as_of}`:t('尚未載入股價'));
   $('priceLoad').disabled=loading||!articles().length;
   $('priceMissing').textContent=t('資料不足或尚未滿 N 日：僅使用時間大小；不視為零報酬。');chart?.paint();schedule();
  }
  function fingerprint(){return chosen()+':'+articles().map(a=>a.id+'@'+a.published_at).join('|');}
  function schedule(){
   clearTimeout(autoTimer);if(loading||!articles().length||!chosen())return;
   const signature=fingerprint(),complete=data?.bars?.length&&data.ticker===chosen()&&articles().every(a=>data.observations?.[a.id]?.published_at===a.published_at);
   if(complete||signature===attempted)return;
   autoTimer=setTimeout(()=>{if(signature===fingerprint()&&!loading){attempted=signature;load();}},650);
  }
  function changed(){root.AtlasUI.write('priceFocus',cfg);paint();onChange();}
  async function load(){
   clearTimeout(autoTimer);attempted=fingerprint();const symbol=chosen(),rows=articles().map(a=>({id:a.id,published_at:a.published_at}));
   viewport=null;abort?.abort();const ticket=++epoch;data=null;error='';loading=false;
   if(!/^[A-Z][A-Z0-9.\-]{0,14}$/.test(symbol)){error='請先填入 Massive 股票代碼';changed();return;}
   if(!rows.length){changed();return;}
   abort=new AbortController();loading=true;changed();
   try{
    const res=await fetch('/api/prices/lens',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ticker:symbol,articles:rows,massive_key:$('key')?.value||undefined}),signal:abort.signal});
    const payload=await res.json();if(ticket!==epoch)return;if(!res.ok)throw Error(payload.error||'股價讀取失敗');data=payload;
   }catch(e){if(ticket!==epoch)return;if(e.name!=='AbortError')error=e.message;}
   finally{if(ticket===epoch){loading=false;changed();}}
  }
  $('priceMix').oninput=()=>{cfg.mix=Number($('priceMix').value)/100;changed();};
  $('priceMix').onchange=()=>{if(cfg.mix>0&&!data&&!loading)load();};
  $('priceHorizon').oninput=()=>{cfg.horizon=horizons[Number($('priceHorizon').value)]||3;changed();};
  $('priceLoad').onclick=load;
  $('ticker').addEventListener('input',()=>{savedTicker='';attempted='';abort?.abort();epoch++;data=null;loading=false;error='';changed();});
  $('key')?.addEventListener('change',()=>{attempted='';schedule();});
  const displayBounds=base=>viewport&&base&&viewport.start>=base.start&&viewport.end<=base.end?viewport:base;
  const api={paint,load,displayBounds,select:a=>{selected=a;viewport=null;},clearSelection:()=>{selected=null;},
   bounds:base=>{const endDate=data?.bars?.at(-1)?.date;if(!base||!endDate||endDate<=base.endDate)return base;const end=Date.parse(endDate+'T00:00:00Z');return {...base,end,endDate,days:Math.round((end-base.start)/86400000)};},scale:(article,time,enabled=true)=>enabled?blend(time,metric(article),cfg.mix,reference(data,cfg.horizon)):time,
   components:(date,time)=>{const chosenRow=selected&&selected.published_at?.slice(0,10)===date?data?.observations?.[selected.id]:null,m=root.AtlasPriceChart?.model(data?.bars||[],date,cfg.horizon,chosenRow?.baseline_date);const value=chosenRow?chosenRow.returns?.[cfg.horizon]??null:m?.complete?m.means.at(-1).return:null;return parts(time,value,cfg.mix,reference(data,cfg.horizon));},
   state:()=>({...cfg,viewport:viewport?{start:viewport.startDate,end:viewport.endDate}:null,normalization:{method:"absolute-return-p95",reference:reference(data,cfg.horizon)},market:data?.market||'US',ticker:data?.ticker||chosen(),loading,error,as_of:data?.as_of||null,complete:articles().filter(a=>metric(a)!==null).length}),
   describe:a=>{const value=metric(a);return !cfg.mix?'':`${data?.ticker||chosen()||t('未指定股票')} · ${cfg.horizon} ${t('交易日平均報酬')} · ${value===null?t('資料不足；僅時間大小'):(value>=0?'+':'')+(value*100).toFixed(2)+'%'} · ${t('股價權重')} ${Math.round(cfg.mix*100)}%`;},
   snapshot:()=>({...cfg,ticker:data?.ticker||chosen(),as_of:data?.as_of||null,market:data?.market||'US',currency:data?.currency||'USD',bars:data?.bars||[],observations:Object.fromEntries(articles().filter(a=>data?.observations?.[a.id]).map(a=>[a.id,data.observations[a.id]]))}),
   restore:(value,explicitTicker='')=>{viewport=null;savedTicker=explicitTicker;attempted='';abort?.abort();epoch++;loading=false;error='';cfg=settings(value||{});data=value?.ticker&&value?.observations?{...value}:null;paint();onChange();}
  };
  chart=root.AtlasPriceChart?.init($,{getState:()=>({...focus(),fullBounds:focus().bounds,bounds:displayBounds(focus().bounds),bars:data?.bars||[],horizon:cfg.horizon,market:data?.market||'US',currency:data?.currency||'USD',loading,error,ticker:data?.ticker||chosen(),as_of:data?.as_of,selected:selected&&selected.published_at?.slice(0,10)===focus().date?data?.observations?.[selected.id]:null}),onDate:date=>{selected=null;onDate(date);},onZoom:value=>{viewport=value;onChange();}});
  root.addEventListener?.('atlas-language',()=>{paint();onChange();});paint();return api;
 }
 const api={settings,priceScale,blend,parts,reference,init};root.AtlasPrice=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
