/* UTC timeline layout and accessible SVG renderer. Edges are existing relations, not inferred causality. */
(function(root){
  const DAY=86400000;
  function day(value){const t=Date.parse(value || '');return Number.isFinite(t)?Math.floor(t/DAY)*DAY:null;}
  function range(rows,options={}){
    const times=rows.map(a=>day(a.published_at)).filter(t=>t!==null);
    let start=day(options.start),end=day(options.end);
    if(start===null)start=times.length?Math.min(...times):day(new Date().toISOString());
    if(end===null)end=times.length?Math.max(...times):start;
    end=Math.max(start,end);
    return {start,end,days:Math.round((end-start)/DAY),startDate:new Date(start).toISOString().slice(0,10),endDate:new Date(end).toISOString().slice(0,10)};
  }
  // Calendar-day focus is a display lens, independent of the publication cutoff.
  function timeSettings(value={}) {
    const stamp=day(value?.date);
    const numeric=(key,fallback,lo,hi)=>typeof value?.[key]==='number'&&Number.isFinite(value[key])?Math.max(lo,Math.min(hi,value[key])):fallback;
    const config={enabled:value?.enabled!==false,date:stamp===null?null:new Date(stamp).toISOString().slice(0,10),peak:numeric('peak',2,1,12),width:numeric('width',.12,.01,.5)};
    // A fixed, bounded profile keeps saved lenses portable and inexpensive to evaluate.
    if(Array.isArray(value?.profile)&&value.profile.length===129&&value.profile.every(v=>typeof v==='number'&&Number.isFinite(v)&&v>=1&&v<=12))config.profile=[...value.profile];
    return config;
  }
  function profileGain(config,offset,dates){
    if(config.profile){
      if(offset < -1 || offset > 1)return 1;
      const position=(offset+1)*64,index=Math.min(127,Math.floor(position)),mix=position-index;
      return Math.exp(Math.log(config.profile[index])*(1-mix)+Math.log(config.profile[index+1])*mix);
    }
    const sigma=Math.max(1/Math.max(1,dates?.days||1),config.width);
    return 1+(config.peak-1)*Math.exp(-.5*Math.pow(offset/sigma,2));
  }
  function timeEvaluator(focus,dates){
    const cfg=timeSettings(focus),target=day(cfg.date),span=Math.max(DAY,(dates?.end||0)-(dates?.start||0));
    return article=>{
      const stamp=day(article.published_at);
      return !cfg.enabled||stamp===null||target===null||!dates?1:profileGain(cfg,(stamp-target)/span,dates);
    };
  }
  function timeScale(article,focus,dates){return timeEvaluator(focus,dates)(article);}
  function timeTicks(dates){
    const times=[];
    if(dates.days>=60){
      const start=new Date(dates.start),cursor=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+1,1));
      while(cursor.getTime()<dates.end){times.push(cursor.getTime());cursor.setUTCMonth(cursor.getUTCMonth()+1);}
    }else{
      const step=Math.max(1,Math.ceil(dates.days/6));
      for(let d=step;d<dates.days;d+=step)times.push(dates.start+d*DAY);
    }
    return times.map(time=>({value:Math.round((time-dates.start)/DAY),position:100*(time-dates.start)/Math.max(DAY,dates.end-dates.start),label:new Date(time).toISOString().slice(dates.days>=60?0:5,dates.days>=60?7:10)}));
  }
  function selectionSummary(rows,trace){
    const hits=rows.map(a=>trace.nodes.get(a.id)).filter(Boolean);
    return {matched:hits.length,total:rows.length,roots:hits.filter(h=>h.depth===0).length,depth:hits.length?Math.min(...hits.map(h=>h.depth)):null};
  }
  function selectionTrace(view,options,previewRoots=[]){
    const roots=options.getRoots?.()||[options.rootId].filter(Boolean);
    return roots.length?(options.getTrace?.()||root.AtlasView.traceMany(view.relations,roots,options.exploration)):root.AtlasView.traceMany(view.relations,previewRoots,options.exploration);
  }
  function selectionCount(rows,trace){
    const info=selectionSummary(rows,trace);
    return rows.length+' 篇'+(trace.roots?.length?' · '+info.matched+' 關聯 · '+info.roots+' roots':'');
  }
  function filter(view,channel='all',cutoff=null){
    const end=day(cutoff);
    const articles=view.articles.filter(a=>(channel==='all'||(a.channels||[]).some(c=>c.id===channel))&&(end===null||day(a.published_at)===null||day(a.published_at)<=end));
    const ids=new Set(articles.map(a=>a.id));
    return {...view,articles,relations:view.relations.filter(e=>ids.has(e.source)&&ids.has(e.target))};
  }
  function layout(view,definitions,options={}){
    const dates=range(view.articles,options),width=Math.max(800,options.width||1000),left=210,right=40;
    const scale=(width-left-right)/Math.max(DAY,dates.end+DAY-dates.start);
    const definitionsById=new Map(definitions.map(c=>[c.id,c]));
    const visibleDefs=options.channel&&options.channel!=='all'?definitions.filter(c=>c.id===options.channel):definitions;
    const lanes=visibleDefs.map(c=>({...c,rows:[],tracks:[]}));
    const laneById=new Map(lanes.map(l=>[l.id,l]));
    if(!laneById.has('other')&&(!options.channel||options.channel==='all'||!lanes.length)){const other={id:'other',name:'其他／未分類',color:'#98a9ba',rows:[],tracks:[]};lanes.push(other);laneById.set(other.id,other);}
    const nodes=[];
    for(const a of [...view.articles].sort((a,b)=>(a.published_at||'').localeCompare(b.published_at||'')||a.id.localeCompare(b.id))){
      const primary=options.channel&&options.channel!=='all'?options.channel:a.primary_channel;
      const lane=laneById.get(primary)||laneById.get('other');
      const time=Date.parse(a.published_at||'');
      const x=Number.isFinite(time)?left+(Math.min(dates.end+DAY,Math.max(dates.start,time))-dates.start)*scale:185;
      let track=lane.tracks.findIndex(last=>x-last>=18);
      if(track===-1){track=lane.tracks.length;lane.tracks.push(x);}else lane.tracks[track]=x;
      const node={article:a,id:a.id,x,track,lane:lane.id};lane.rows.push(node);nodes.push(node);
    }
    let y=48;
    for(const lane of lanes){lane.top=y;lane.height=Math.max(110,lane.tracks.length*22+42);for(const n of lane.rows)n.y=y+34+n.track*22;y+=lane.height;}
    const ticks=[];const step=Math.max(1,Math.ceil((dates.days+1)/7));
    for(let d=0;d<=dates.days;d+=step){const time=dates.start+d*DAY;ticks.push({x:left+(time-dates.start)*scale,label:new Date(time).toISOString().slice(0,10)});}
    const byId=new Map(nodes.map(n=>[n.id,n]));
    const edges=view.relations.filter(e=>byId.has(e.source)&&byId.has(e.target)).map(e=>({...e,a:byId.get(e.source),b:byId.get(e.target)}));
    return {width,height:y+20,nodes,edges,lanes,ticks,dates};
  }
  function render(container,view,definitions,options={}){
    const doc=container.ownerDocument||document,ns='http://www.w3.org/2000/svg';
    const svgEl=(name,attrs={})=>{const e=doc.createElementNS(ns,name);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
    const model=layout(view,definitions,options),sheet=doc.createElement('div');sheet.className='timeline-sheet';sheet.style.width=model.width+'px';
    const ruler=doc.createElement('div');ruler.className='timeline-ruler';const rulerBody=doc.createElement('div');rulerBody.className='timeline-ruler-body';rulerBody.style.width=model.width+'px';
    for(const tick of model.ticks){const label=doc.createElement('span');label.textContent=tick.label;label.style.left=tick.x+'px';rulerBody.append(label);}ruler.append(rulerBody);
    const labels=doc.createElement('div');labels.className='timeline-labels';const laneCounts=[];
    for(const lane of model.lanes){const label=doc.createElement('div');label.className='timeline-lane-label';label.style.top=lane.top+'px';label.style.height=lane.height+'px';label.style.borderLeftColor=lane.color;const name=doc.createElement('strong');name.textContent=lane.name;if(lane.id.startsWith('custom-'))name.className='raw';const count=doc.createElement('small');count.textContent=lane.rows.length+' 篇';label.append(name,count);labels.append(label);laneCounts.push({lane,count});}
    const svg=svgEl('svg',{width:model.width,height:model.height,role:'group','aria-label':'新聞發布日期與分類泳道'});
    for(const lane of model.lanes)svg.append(svgEl('rect',{x:170,y:lane.top,width:model.width-170,height:lane.height,fill:model.lanes.indexOf(lane)%2?'#0d1928':'#101f30',stroke:'#263a4d','stroke-width':.5}));
    for(const tick of model.ticks)svg.append(svgEl('line',{x1:tick.x,x2:tick.x,y1:48,y2:model.height,stroke:'#395169','stroke-opacity':.35}));
    const paths=[], nodeElements=[];
    const glow= root.AtlasGlow?.settings(options.glow)||{enabled:false};
    const defs=svgEl('defs');svg.append(defs);

    for(const edge of model.edges){const {a,b}=edge;const bend=Math.max(20,Math.min(90,Math.abs(a.x-b.x)*.16));const path=svgEl('path',{d:`M ${a.x} ${a.y} C ${a.x} ${a.y-bend}, ${b.x} ${b.y-bend}, ${b.x} ${b.y}`,fill:'none',stroke:edge.scope==='cross'?'#f4cd84':'#79bcb3','stroke-width':1,'stroke-opacity':.28,'pointer-events':'none'});if(edge.scope==='cross')path.setAttribute('stroke-dasharray','5 4');svg.append(path);paths.push({edge,path});}
    function highlight(id){const confirmed=options.getRoots?.()||[id].filter(Boolean),roots=confirmed.length?confirmed:[options.getPreviewRoot?.()].filter(Boolean);id=confirmed[0]||null;const trace=selectionTrace(view,options,roots);for(const {lane,count} of laneCounts)count.textContent=selectionCount(lane.rows.map(n=>n.article),trace);for(const {edge,path} of paths){const near=trace.edges.has(root.AtlasView.identity(edge));const depth=Math.max(trace.nodes.get(edge.source)?.depth||0,trace.nodes.get(edge.target)?.depth||0);path.setAttribute('stroke-opacity',id?(near?Math.pow(glow.decay||.64,depth):.045):.28);path.setAttribute('stroke-width',near?2:1);}for(const {node,group,halo} of nodeElements){const hit=trace.nodes.get(node.id);group.setAttribute('opacity',id?(hit?Math.max(.15,Math.pow(glow.decay||.64,hit.depth)):(glow.background||.18)):1);group.setAttribute('data-focus-depth',hit?.depth??'');halo.setAttribute('opacity',hit&&glow.enabled?(1-Math.exp(-root.AtlasGlow.level(hit.depth,glow)*1.6))*(id?1:.3):0);halo.setAttribute('r',hit?glow.radius*(hit.depth===0?1.45:Math.pow(.9,hit.depth)):0);}if(id||!roots.length)options.onTrace?.(id,trace);}

    for(const node of model.nodes){const group=svgEl('g',{tabindex:0,role:'button','aria-label':`${node.article.title}，${node.article.published_at||'日期未知'}`,'data-node-id':node.id});group.style.cursor='pointer';const gradId='news-glow-'+nodeElements.length;const gradient=svgEl('radialGradient',{id:gradId});for(const [offset,color,opacity] of [['0%','#fff',1],['12%',options.colors?.[node.article.display_provider||node.article.source.provider]||'#80e6cc',.8],['40%','#80e6cc',.2],['100%','#80e6cc',0]])gradient.append(svgEl('stop',{offset,'stop-color':color,'stop-opacity':opacity}));defs.append(gradient);const halo=svgEl('circle',{cx:node.x,cy:node.y,r:0,fill:`url(#${gradId})`,opacity:0,'pointer-events':'none','data-glow-node':node.id});group.append(halo);group.append(svgEl('circle',{cx:node.x,cy:node.y,r:11,fill:'transparent'}),svgEl('circle',{cx:node.x,cy:node.y,r:5.5*Math.min(2,options.nodeScale?.(node.article)||1),fill:options.colors?.[node.article.display_provider||node.article.source.provider]||'#c9d8e5',stroke:'#d7e9f4','stroke-width':.7}));const title=svgEl('title');title.textContent=node.article.title;group.append(title);
      const show=e=>{options.onHover?.(node.article,e);highlight(node.id);};const hide=()=>{options.onHover?.(null);highlight(options.rootId||null);};
      group.addEventListener('pointerenter',show);group.addEventListener('pointerleave',hide);group.addEventListener('focus',show);group.addEventListener('blur',hide);group.addEventListener('click',()=>{options.onSelect?.(node.article);highlight(node.id);});group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();options.onSelect?.(node.article);highlight(node.id);}});svg.append(group);nodeElements.push({node,group,halo});}
    sheet.append(ruler,labels,svg);container.replaceChildren(sheet);highlight(options.rootId||null);return model;
  }
  // Fixed-height channel/day cells replace unbounded vertical stacks for dense results.
  function density(view,definitions,options={}){
    const dates=range(view.articles,options),left=170,cell=76*Math.max(1,Math.min(4,Number(options.zoom)||1));
    const used=new Set(view.articles.map(a=>options.channel&&options.channel!=='all'?options.channel:a.primary_channel||'other'));
    const defs=definitions.filter(d=>used.has(d.id));if(used.has('other')&&!defs.some(d=>d.id==='other'))defs.push({id:'other',name:'其他／未分類',color:'#98a9ba'});
    const lanes=defs.map((d,i)=>({...d,top:48+i*82,height:82,rows:[]})),laneMap=new Map(lanes.map(d=>[d.id,d]));
    const bucketMap=new Map();
    for(const a of view.articles){const laneId=options.channel&&options.channel!=='all'?options.channel:a.primary_channel||'other';const lane=laneMap.get(laneId);if(!lane)continue;const stamp=day(a.published_at),offset=stamp===null?dates.days+1:Math.max(0,Math.min(dates.days,Math.round((stamp-dates.start)/DAY)));const key=laneId+':'+offset;
      if(!bucketMap.has(key))bucketMap.set(key,{id:key,lane:laneId,date:stamp===null?'日期未知':new Date(stamp).toISOString().slice(0,10),x:left+offset*cell+cell/2,y:lane.top+40,articles:[],counts:{}});
      const bucket=bucketMap.get(key);bucket.articles.push(a);const provider=a.display_provider||a.source.provider;bucket.counts[provider]=(bucket.counts[provider]||0)+1;lane.rows.push(a);
    }
    const buckets=[...bucketMap.values()],byArticle=new Map();for(const b of buckets)for(const a of b.articles)byArticle.set(a.id,b);
    const edgeMap=new Map();for(const e of view.relations){const a=byArticle.get(e.source),b=byArticle.get(e.target);if(!a||!b||a===b)continue;const key=[a.id,b.id].sort().join('|');if(!edgeMap.has(key))edgeMap.set(key,{id:key,a,b,relations:[]});edgeMap.get(key).relations.push(e);}
    const extra=buckets.some(b=>b.date==='日期未知')?1:0;
    return {dates,lanes,buckets,nodes:buckets,edges:[...edgeMap.values()],width:Math.max(options.width||800,left+(dates.days+1+extra)*cell+30),height:Math.max(160,48+lanes.length*82+20),cell,left};
  }
  function renderDensity(container,view,definitions,options={}){
    const doc=container.ownerDocument||document,ns='http://www.w3.org/2000/svg',model=density(view,definitions,options);
    const make=(tag,attrs={})=>{const e=doc.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))e.setAttribute(k,String(v));return e;};
    const sheet=doc.createElement('div');sheet.className='timeline-sheet';sheet.style.width=model.width+'px';
    const ruler=doc.createElement('div');ruler.className='timeline-ruler';const body=doc.createElement('div');body.className='timeline-ruler-body';body.style.width=model.width+'px';
    for(let i=0;i<=model.dates.days;i++){const span=doc.createElement('span');span.style.left=model.left+i*model.cell+14+'px';span.textContent=new Date(model.dates.start+i*DAY).toISOString().slice(0,10);body.append(span);}ruler.append(body);
    const labels=doc.createElement('div');labels.className='timeline-labels';const laneCounts=[];for(const lane of model.lanes){const label=doc.createElement('div');label.className='timeline-lane-label';label.style.top=lane.top+'px';label.style.height=lane.height+'px';label.style.borderLeftColor=lane.color;const name=doc.createElement('strong');name.textContent=lane.name;if(lane.id.startsWith('custom-'))name.className='raw';const count=doc.createElement('small');count.textContent=lane.rows.length+' 篇';label.append(name,count);labels.append(label);laneCounts.push({lane,count});}
    const svg=make('svg',{width:model.width,height:model.height,role:'group','aria-label':'日期與分類新聞密度格'});
    for(const lane of model.lanes)svg.append(make('rect',{x:model.left,y:lane.top,width:model.width-model.left,height:lane.height,fill:'#101f30',stroke:'#263a4d'}));
    const lines=[];for(const edge of model.edges){const path=make('path',{d:`M${edge.a.x} ${edge.a.y} Q${(edge.a.x+edge.b.x)/2} ${Math.min(edge.a.y,edge.b.y)-45} ${edge.b.x} ${edge.b.y}`,fill:'none',stroke:'#f4cd84','stroke-opacity':0,'pointer-events':'none'});svg.append(path);lines.push({edge,path});}
    const elements=[];
    const glow=root.AtlasGlow?.settings(options.glow)||{enabled:false,decay:.64,background:.18};
    function highlight(bucket){
      const confirmed=(options.getRoots?.()||[options.rootId].filter(Boolean)).length>0;
      const trace=selectionTrace(view,options,bucket?bucket.articles.map(a=>a.id).slice(0,10):[]);
      for(const {lane,count} of laneCounts)count.textContent=selectionCount(lane.rows,trace);
      for(const {edge,path} of lines){
        const matches=edge.relations.filter(e=>trace.edges.has(root.AtlasView.identity(e)));
        const depth=matches.length?Math.min(...matches.map(e=>Math.max(trace.nodes.get(e.source)?.depth||0,trace.nodes.get(e.target)?.depth||0))):0;
        path.setAttribute('stroke-opacity',matches.length?Math.pow(glow.decay,depth):0);
        path.setAttribute('stroke-width',confirmed?2:1);
      }
      for(const {bucket:b,group,outline,badge} of elements){
        const hit=selectionSummary(b.articles,trace),level=hit.matched?Math.pow(glow.decay,hit.depth):0;
        group.setAttribute('opacity',confirmed?(hit.matched?Math.max(.15,level):glow.background):1);
        group.setAttribute('data-focus-depth',hit.depth??'');
        outline.setAttribute('stroke',hit.roots?'#fff':'#8cffdc');
        outline.setAttribute('stroke-opacity',hit.matched?(confirmed?1:.35):0);
        outline.setAttribute('stroke-width',hit.roots?3:1.5);
        outline.style.filter=glow.enabled&&hit.matched?`drop-shadow(0 0 ${Math.round(glow.radius/4)}px rgba(128,230,204,${Math.min(1,glow.brightness*level)*(confirmed?1:.3)}))`:'none';
        badge.textContent=hit.matched?(hit.roots?'★ '+hit.roots+' · ':'')+hit.matched+'/'+hit.total+' · d'+hit.depth:'';
        group.setAttribute('aria-label',b.date+' · '+selectionCount(b.articles,trace));
      }
    }
    const max=Math.max(1,...model.buckets.map(b=>b.articles.length));
    for(const bucket of model.buckets){const group=make('g',{class:'density-bucket',tabindex:0,role:'button','aria-label':bucket.date+' · '+bucket.articles.length+' 篇','data-bucket-id':bucket.id});
      group.append(make('rect',{x:bucket.x-31,y:bucket.y-25,width:62,height:50,rx:7,fill:'#234c60','fill-opacity':.35+.65*Math.sqrt(bucket.articles.length/max),stroke:'#4a7b8e'}));
      const outline=make('rect',{x:bucket.x-31,y:bucket.y-25,width:62,height:50,rx:7,fill:'none','pointer-events':'none'});group.append(outline);
      const badge=make('text',{x:bucket.x,y:bucket.y-30,'text-anchor':'middle',fill:'#b7ffe4','font-size':10,'pointer-events':'none'});group.append(badge);
      const count=make('text',{x:bucket.x,y:bucket.y+2,'text-anchor':'middle',fill:'#edf7ff','font-size':16});count.textContent=bucket.articles.length;group.append(count);let offset=0;
      for(const [provider,num]of Object.entries(bucket.counts)){const width=54*num/bucket.articles.length;group.append(make('rect',{x:bucket.x-27+offset,y:bucket.y+13,width,height:4,fill:options.colors?.[provider]||'#aaa'}));offset+=width;}
      const title=make('title');title.textContent=bucket.date+' · '+bucket.articles.length+' 篇';group.append(title);
      const show=e=>{highlight(bucket);options.onBucketHover?.(bucket,e);},hide=()=>{highlight(null);options.onBucketHover?.(null);};
      group.addEventListener('pointerenter',show);group.addEventListener('pointerleave',hide);group.addEventListener('focus',show);group.addEventListener('blur',hide);group.addEventListener('click',()=>options.onBucketSelect?.(bucket));group.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();options.onBucketSelect?.(bucket);}});svg.append(group);elements.push({bucket,group,outline,badge});
    }
    sheet.append(ruler,labels,svg);container.replaceChildren(sheet);highlight(null);return model;
  }

  const api={timeSettings,profileGain,timeEvaluator,timeScale,timeTicks,selectionSummary,selectionTrace,range,filter,layout,render,day,density,renderDensity};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.AtlasTimeline=api;
})(globalThis);
