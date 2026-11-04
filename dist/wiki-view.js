/* Separate Wiki surface; never replaces News Graph state, edges or snapshots. */
(function(root){
 const hooks=root.AtlasWikiContext;if(!hooks)return;
 const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const colors={ArticleRevision:'#78b7e7',Claim:'#83dfbf',Event:'#e6bc76',Thesis:'#c3a2ee'};
 const names={ArticleRevision:'新聞版本',Claim:'陳述',Event:'事件',Thesis:'觀點'};
 const panel=make('section',undefined,'wiki-panel');panel.id='wikiPanel';panel.hidden=true;panel.setAttribute('aria-label','LLM Wiki');
 panel.innerHTML='<header class="wiki-header"><button id="wikiBack" type="button">返回新聞圖譜</button><h2>LLM Wiki</h2><p>從新聞證據整理知識，保留引用與每次更新。</p><button id="wikiExport" type="button">匯出 Markdown</button></header><div class="wiki-layout"><aside class="wiki-controls"><label>已建立的 Wiki<select id="wikiSaved"><option value="">建立新的股票 Wiki</option></select></label><label>股票識別<input id="wikiInstrument" placeholder="例如 NASDAQ:TSLA" autocomplete="off" maxlength="40"></label><label>來源範圍<select id="wikiScope"><option value="global">全局：目前查詢的所有來源與 DB</option><option value="loaded">目前已載入新聞（所選來源）</option><option value="focus">目前焦點與關聯節點</option></select></label><p id="wikiSelection" class="wiki-note"></p><label>整理日期（UTC）<select id="wikiRange"><option value="month">最近一個月</option><option value="quarter">最近三個月</option><option value="all">全部日期</option><option value="custom">自訂範圍</option></select></label><div id="wikiDates"><div class="wiki-pair"><label>起始日期<input id="wikiStartDate" type="date"></label><label>結束日期<input id="wikiEndDate" type="date"></label></div><label>拖曳起點<input id="wikiRangeStart" type="range" aria-label="整理範圍起點"></label><label>拖曳終點<input id="wikiRangeEnd" type="range" aria-label="整理範圍終點"></label><p class="wiki-note">滑桿涵蓋已載入新聞；更早的 DB 資料可直接輸入日期。</p></div><label>維護方式<select id="wikiOperation"><option value="update">只補新增／變更內容（跨模型重用）</option><option value="review">手動局部校正（已校正且無新證據則略過）</option></select></label><label>模型（Codex /model）<select id="wikiModel"><option value="">正在載入實際模型清單…</option></select></label><p id="wikiModelNote" class="wiki-note"></p><div class="wiki-pair"><label>每批篇數<input id="wikiBatch" type="number" min="1" max="20" value="5"></label><label>每日篇數上限<input id="wikiDaily" type="number" min="1" max="100" value="20"></label></div><label class="wiki-check"><input id="wikiContinuous" type="checkbox"><span>持續維護指定查詢<br><small>每分鐘檢查新聞 DB；日期固定，不自動擴大。</small></span></label><button id="wikiPreview" type="button" class="wiki-primary">預覽更新範圍</button><p id="wikiStatus" class="wiki-status" role="status" aria-live="polite"></p><div class="wiki-actions"><button id="wikiStart" type="button" class="wiki-primary" hidden>確認並開始整理</button><button id="wikiPause" type="button" hidden>停止持續維護</button></div><p class="wiki-note">主頁 edge 設定、渲染數與顯示篩選不觸發 Wiki 重算。預設只補缺少的證據；手動校正才重查選定範圍。預覽不呼叫模型。開始後會將選取文章的標題、摘要及少量既有 Wiki 內容交給登入模型處理。篇數上限不是金額或 token 上限。</p><h3>更新紀錄</h3><div id="wikiJobs" aria-live="polite"></div></aside><main class="wiki-canvas-area"><div class="wiki-toolbar"><label>版本<select id="wikiVersion"><option value="">最新版本</option></select></label><label>歷史時點（UTC）<input id="wikiAsOf" type="datetime-local"></label><label>節點<select id="wikiKind"><option value="">全部類型</option><option value="ArticleRevision">新聞版本</option><option value="Claim">陳述</option><option value="Event">事件</option><option value="Thesis">觀點</option></select></label><label>連線<select id="wikiRelation"><option value="">全部關係</option><option>SUPPORTS</option><option>CONTRADICTS</option><option>UPDATES</option><option>DEPENDS_ON</option><option>RELATED_TO</option><option>TEMPORALLY_PRECEDES</option></select></label><label>渲染上限<select id="wikiBudget"><option>800</option><option>1600</option><option>2400</option></select></label></div><div id="wikiCounts" class="wiki-counts">尚未載入 Wiki</div><div id="wikiCanvas" class="wiki-canvas"></div><div id="wikiEmpty" class="wiki-empty"><h3>讓新聞累積成可追溯的知識</h3><p>選擇股票與新聞範圍，先預覽，再讓模型整理第一批內容。已建立的 Wiki 可直接切換查看。</p></div></main><aside id="wikiDetail" class="wiki-detail"><div id="wikiLegend" class="wiki-legend"></div><h3>點選節點或連線</h3><p class="wiki-note">查看原文引用、關係方向與版本。引用核對不代表事實已證實，線條不代表因果。</p></aside></div>';
 document.body.append(panel);const $=id=>document.getElementById(id);
 const open=make('button','LLM Wiki');open.id='modeWiki';open.type='button';$('modeTimeline').after(open);
 let info=null,data=null,graph=null,plan=null,timer=null,busy=false,request=0,generation=0;
 let modelReady=false;
 const status=(text,error=false)=>{$('wikiStatus').textContent=text;$('wikiStatus').classList.toggle('error',error);};
 async function api(path,body){
  const response=await fetch('/api/wiki/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const value=await response.json();if(!response.ok)throw Error(value.error||'Wiki請求失敗');return value;
 }
 const day=date=>date.toISOString().slice(0,10),stamp=value=>Date.parse(value+'T00:00:00Z')/86400000;
 function range(){return $('wikiRange').value==='all'?null:{start:$('wikiStartDate').value,end:$('wikiEndDate').value};}
 function sliders(){
  const values=hooks.selection('global').articles.map(a=>a.published_at?.slice(0,10)).filter(Boolean);
  const ends=[...values,$('wikiStartDate').value,$('wikiEndDate').value,day(new Date())].filter(Boolean).map(stamp).filter(Number.isFinite);
  const min=Math.min(...ends),max=Math.max(...ends);
  for(const id of ['wikiRangeStart','wikiRangeEnd']){$(id).min=min;$(id).max=Math.max(min+1,max);$(id).step=1;}
  $('wikiRangeStart').value=stamp($('wikiStartDate').value);$('wikiRangeEnd').value=stamp($('wikiEndDate').value);
  $('wikiDates').hidden=$('wikiRange').value==='all';
 }
 function preset(){
  if(['month','quarter'].includes($('wikiRange').value)){
   const end=new Date(),start=new Date(Date.UTC(end.getUTCFullYear(),end.getUTCMonth()-($('wikiRange').value==='month'?1:3),1));
   const last=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+1,0)).getUTCDate();start.setUTCDate(Math.min(end.getUTCDate(),last));
   $('wikiStartDate').value=day(start);$('wikiEndDate').value=day(end);
  }
  sliders();
 }
 function selection(){const value=hooks.selection($('wikiScope').value),dates=range();const count=value.articles.filter(a=>!dates||(a.published_at&&a.published_at.slice(0,10)>=dates.start&&a.published_at.slice(0,10)<=dates.end)).length;$('wikiSelection').textContent='已載入範圍內 '+count+' 篇；全局模式另查 DB，不受 3D 預算與主頁來源勾選影響。';return value;}
 preset();
 function invalidate(){generation++;plan=null;$('wikiStart').hidden=true;}
 function clearStock(){invalidate();request++;data=null;$('wikiVersion').replaceChildren(new Option('最新版本',''));$('wikiAsOf').value='';$('wikiJobs').replaceChildren();$('wikiDetail').replaceChildren(make('p','選擇 Wiki 後查看引用。'));$('wikiCounts').textContent='尚未載入此股票 Wiki';$('wikiEmpty').hidden=false;if(graph)graph.graphData({nodes:[],links:[]});}
 function current(){return $('wikiInstrument').value.trim().toUpperCase();}
 function query(){const p=new URLSearchParams({instrument:current()});if($('wikiAsOf').value)p.set('as_of',$('wikiAsOf').value+'Z');else if($('wikiVersion').value)p.set('version',$('wikiVersion').value);return p.toString();}
 function legend(){const box=$('wikiLegend');if(!box)return;for(const [k,c] of Object.entries(colors)){const s=make('span',names[k]);const dot=make('i',undefined,'wiki-dot');dot.style.setProperty('--wiki-color',c);s.prepend(dot);box.append(s);}}
 legend();
 function details(item,edge=false){
  const ident=data.instrument;const box=$('wikiDetail');box.replaceChildren();
  if(edge){box.append(make('small',item.status==='hypothesis'?'假說關係':'LLM 關係提案'),make('h3',item.relation_type),make('p',item.rationale),make('small',item.source.kind+' → '+item.target.kind));}
  else{box.append(make('small',(names[item.kind]||item.kind)+' · '+(item.status==='source'?'凍結來源':'LLM 提案')),make('h3',item.title),make('p',item.summary||''));if(item.url){const a=make('a','開啟新聞來源');a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}}
  box.append(make('p','可用時間：'+(item.available_at||'—'),'wiki-note'));
  for(const cite of item.evidence_refs||item.citations||[]){
   box.append(make('blockquote',cite.quote),make('small',cite.field+' ['+cite.start+':'+cite.end+'] · 引用已逐字核對'));
   const button=make('button','查看引用來源');button.type='button';button.onclick=async()=>{try{const a=await api('article?'+new URLSearchParams({instrument:ident,id:cite.article_revision_id}));const link=make('a',a.title);link.href=a.url;link.target='_blank';link.rel='noopener noreferrer';button.replaceWith(link);}catch(e){status(e.message,true);}};box.append(make('p'),button);
  }
 }
 function render(){
  if(!data)return;
  const subset=data.nodes.filter(n=>!$('wikiKind').value||n.kind===$('wikiKind').value).slice(0,Number($('wikiBudget').value));
  const ids=new Set(subset.map(n=>n.id));
  const edges=data.edges.filter(e=>ids.has(e.source.stable_id)&&ids.has(e.target.stable_id)&&(!$('wikiRelation').value||e.relation_type===$('wikiRelation').value)).slice(0,subset.length*3);
  $('wikiCounts').textContent='版本 '+data.version+' · 節點 '+subset.length+' / '+data.total_nodes+' · 連線 '+edges.length+' · '+(data.truncated?'已限制載入範圍':'引用可追溯，提案待判讀');
  $('wikiEmpty').hidden=subset.length>0;
  if(!subset.length){if(graph)graph.graphData({nodes:[],links:[]});return;}
  try{
   if(!graph){
    graph=root.ForceGraph3D()($('wikiCanvas')).backgroundColor('#080f1a').showNavInfo(false).nodeId('id').nodeColor(n=>colors[n.kind]||'#b9cddd').nodeVal(n=>n.kind==='ArticleRevision'?2:4).nodeLabel(n=>make('span',n.title).outerHTML).linkLabel(l=>make('span',l.edge.relation_type).outerHTML).linkColor(l=>l.edge.status==='hypothesis'?'#b99ce0':'#6c9cab').linkDirectionalArrowLength(4).linkDirectionalArrowRelPos(1).linkWidth(.7).cooldownTicks(70).onNodeClick(n=>details(n)).onLinkClick(l=>details(l.edge,true));
    const ro=new ResizeObserver(()=>{const r=$('wikiCanvas').getBoundingClientRect();if(r.width&&r.height)graph.width(r.width).height(r.height);});ro.observe($('wikiCanvas'));
   }
   const old=new Map(graph.graphData().nodes.map(n=>[n.id,n]));
   graph.graphData({nodes:subset.map(n=>Object.assign(old.get(n.id)||{},n)),links:edges.map(e=>({source:e.source.stable_id,target:e.target.stable_id,edge:e}))});
   const r=$('wikiCanvas').getBoundingClientRect();graph.width(r.width).height(r.height);
  }catch(error){$('wikiEmpty').hidden=false;$('wikiEmpty').replaceChildren(make('h3','3D 暫時無法顯示'),make('p','仍可點選下方節點閱讀證據。'));const list=make('div');for(const n of subset.slice(0,40)){const b=make('button',n.title);b.onclick=()=>details(n);list.append(b);}$('wikiEmpty').style.pointerEvents='auto';$('wikiEmpty').append(list);}
 }
 function jobs(items,cfg,ident){
  const box=$('wikiJobs');box.replaceChildren();$('wikiPause').hidden=!cfg?.enabled;
  const labels={queued:'等待處理',running:'整理中',completed:'已完成',failed:'失敗',cancelled:'已停止',interrupted:'服務中斷，可續跑',budget_paused:'已達每日上限'};
  for(const j of items.slice(0,8)){const row=make('div',undefined,'wiki-job');row.append(make('strong',(labels[j.status]||j.status)+' · '+j.done+'/'+j.payload.revisions.length),make('small',new Date(j.created_at).toLocaleString()+' · '+j.payload.model));if(j.error)row.append(make('p',j.error));if(j.usage?.input_tokens!==undefined)row.append(make('small','輸入 '+j.usage.input_tokens+' / 輸出 '+(j.usage.output_tokens||0)+' tokens'));if(['queued','running'].includes(j.status)){const b=make('button','停止此工作與持續維護');b.onclick=async()=>{try{await api('cancel',{instrument:ident,job_id:j.id});await poll();}catch(e){status(e.message,true);}};row.append(b);}box.append(row);}
  if(cfg?.enabled)box.prepend(make('p','背景範圍：'+(cfg.date_range?cfg.date_range.start+'～'+cfg.date_range.end:'全部日期')+' · 模型 '+cfg.model,'wiki-note'));
  if(!items.length)box.append(make('p','尚無工作紀錄','wiki-note'));
 }
 async function load(){
  const mine=++request;if(!current())return;
  try{
   const value=await api('graph?'+query());if(mine!==request)return;
   if(data&&data.version!==value.version)$('wikiDetail').replaceChildren(make('p','點選此版本的節點或連線查看引用。'));
   data=value;if(!Array.from($('wikiSaved').options).some(o=>o.value===value.instrument))$('wikiSaved').add(new Option(value.instrument,value.instrument));$('wikiSaved').value=value.instrument;const version=$('wikiVersion').value;$('wikiVersion').replaceChildren(new Option('最新版本',''),...value.versions.map(v=>new Option('v'+v.version+' · '+new Date(v.created_at).toLocaleString(),v.version)));$('wikiVersion').value=version;
   jobs(value.jobs,value.config,value.instrument);render();
  }catch(e){if(mine===request)status(e.message,true);}
 }
 async function poll(){
  if(panel.hidden||!current())return;
  const ident=current(),mine=request;try{const state=await api('jobs?'+new URLSearchParams({instrument:ident}));if(panel.hidden||ident!==current()||mine!==request)return;jobs(state.jobs,state.config,ident);if(!$('wikiVersion').value&&!$('wikiAsOf').value&&(!data||data.instrument!==current()||data.version!==state.version))await load();}catch(e){if(data)status(e.message,true);}
 }
 async function show(){
  panel.hidden=false;open.setAttribute('aria-pressed','true');hooks.visible(true);graph?.resumeAnimation();selection();
  try{info=await api('status');$('wikiSaved').replaceChildren(new Option('建立新的股票 Wiki',''),...info.instruments.map(s=>new Option(s.instrument+' · v'+s.version,s.instrument)));if(data)$('wikiSaved').value=data.instrument;$('wikiPreview').disabled=true;modelReady=false;$('wikiModel').disabled=true;const catalog=await api('models'),previous=$('wikiModel').value;$('wikiModel').replaceChildren(...catalog.models.map(m=>new Option(m.name,m.id)));const selected=catalog.models.some(m=>m.id===previous)?previous:catalog.default_model;if(!catalog.models.some(m=>m.id===selected)){$('wikiModel').prepend(new Option('指定預設模型目前不可用，請明確選擇',''));$('wikiModel').value='';}else $('wikiModel').value=selected;modelReady=!!$('wikiModel').value;$('wikiModel').disabled=false;$('wikiModelNote').textContent='來自 '+catalog.source+'；切換模型不重抽已完成的新聞。';$('wikiPreview').disabled=!info.writable||!modelReady;if(!info.writable)status('此頁可查看Wiki；維護需使用已允許的來源。',true);else if(!info.bridge_ready)status('LLM橋接尚未就緒；可預覽，啟動前請檢查Chat服務。',true);if(data)render();}catch(e){status(e.message,true);}
  clearInterval(timer);timer=setInterval(poll,5000);$('wikiBack').focus();
 }
 open.onclick=show;
 $('wikiBack').onclick=()=>{panel.hidden=true;open.setAttribute('aria-pressed','false');clearInterval(timer);request++;invalidate();graph?.pauseAnimation();hooks.visible(false);open.focus();};
 $('wikiSaved').onchange=()=>{if($('wikiSaved').value){$('wikiInstrument').value=$('wikiSaved').value;clearStock();load();}};
 for(const id of ['wikiInstrument','wikiModel','wikiBatch','wikiDaily','wikiScope','wikiStartDate','wikiEndDate','wikiOperation'])$(id).addEventListener('input',()=>{if(id==='wikiInstrument')clearStock();else invalidate();if(id==='wikiModel'){modelReady=!!$('wikiModel').value;$('wikiPreview').disabled=!info?.writable||!modelReady;}if(id==='wikiStartDate'||id==='wikiEndDate'){$('wikiRange').value='custom';sliders();}if(id==='wikiOperation'){$('wikiContinuous').disabled=$('wikiOperation').value==='review';if($('wikiContinuous').disabled)$('wikiContinuous').checked=false;}selection();});
 $('wikiRange').onchange=()=>{invalidate();preset();selection();};
 for(const id of ['wikiRangeStart','wikiRangeEnd'])$(id).oninput=()=>{invalidate();$('wikiRange').value='custom';const start=Number($('wikiRangeStart').value),end=Number($('wikiRangeEnd').value);if(start>end)$(id==='wikiRangeStart'?'wikiRangeEnd':'wikiRangeStart').value=$(id).value;$('wikiStartDate').value=day(new Date(Number($('wikiRangeStart').value)*86400000));$('wikiEndDate').value=day(new Date(Number($('wikiRangeEnd').value)*86400000));selection();};
 $('wikiPreview').onclick=async()=>{
  if(busy||!modelReady)return;busy=true;invalidate();const mine=generation;$('wikiPreview').disabled=true;status('正在核對選取範圍與既有抽取…');
  try{const selected=selection();const value=await api('plan',{...selected,scope:$('wikiScope').value,date_range:range(),operation:$('wikiOperation').value,instrument:current(),model:$('wikiModel').value.trim(),batch_size:Number($('wikiBatch').value),daily_limit:Number($('wikiDaily').value)});if(mine!==generation||panel.hidden)return;plan=value;status(plan.instrument+' · '+(plan.operation==='review'?'手動校正（將再次呼叫模型）':'增量補足')+'\n日期：'+(plan.date_range?plan.date_range.start+'～'+plan.date_range.end:'全部')+'\n選取 '+plan.selected+' 篇 · 已抽取 '+plan.reused+' 篇\n待處理 '+plan.pending+' 篇；本批最多 '+plan.next_batch+' 篇\n模型：'+plan.model+'；每日最多 '+plan.daily_limit+' 篇\n持續維護查詢：'+(plan.watch_sources.map(s=>s.provider+': '+s.term).join('、')||'僅既有待處理文章')+'\n'+plan.note);$('wikiStart').hidden=false;}
  catch(e){status(e.message,true);}finally{busy=false;$('wikiPreview').disabled=!info?.writable||!modelReady;}
 };
 $('wikiStart').onclick=async()=>{
  if(busy||!plan)return;const mine=generation;busy=true;$('wikiStart').disabled=true;
  try{await api('jobs',{plan_id:plan.plan_id,continuous:$('wikiContinuous').checked});if(mine!==generation||panel.hidden)return;invalidate();status('工作已排入佇列。可以切回新聞圖譜，背景會繼續整理。');$('wikiVersion').value='';$('wikiAsOf').value='';await load();}
  catch(e){status(e.message,true);}finally{busy=false;$('wikiStart').disabled=false;}
 };
 $('wikiPause').onclick=async()=>{try{await api('configure',{instrument:current(),enabled:false});status('已停用後續自動維護；進行中的工作可在更新紀錄停止。');await poll();}catch(e){status(e.message,true);}};
 for(const id of ['wikiKind','wikiRelation','wikiBudget'])$(id).onchange=render;
 $('wikiVersion').onchange=()=>{$('wikiAsOf').value='';load();};$('wikiAsOf').onchange=load;
 $('wikiExport').onclick=async()=>{if(!data)return;const ident=data.instrument,version=data.version;try{const value=await api('markdown?'+new URLSearchParams({instrument:ident,version}));const url=URL.createObjectURL(new Blob([value.markdown],{type:'text/markdown;charset=utf-8'}));const a=make('a');a.href=url;a.download=ident.replace(':','-')+'-wiki.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}catch(e){status(e.message,true);}};
 root.AtlasWiki={show,refresh:load};
})(globalThis);
