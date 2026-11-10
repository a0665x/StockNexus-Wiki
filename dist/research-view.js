/* Research controls share the mounted Wiki graph, selection and chat runtime. */
(function(){
 'use strict';
 const $=id=>document.getElementById(id),wiki=window.AtlasWiki;
 if(!wiki)return;
 const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const button=(text,fn)=>{const b=node('button',text);b.type='button';b.onclick=async()=>{if(b.disabled)return;const token=serial;b.disabled=true;b.setAttribute('aria-busy','true');b.classList.add('research-working');try{await fn();}catch(e){if(token===serial)status(e.message);}finally{b.disabled=false;b.setAttribute('aria-busy','false');b.classList.remove('research-working');}};return b;};
 const field=(label,text)=>{const p=node('p');p.append(node('span',label),node('span',text,'research-source'));return p;};
 const details=(text,children)=>{const d=node('details');d.append(node('summary',text),...children);return d;};
 const open=node('button','研究問題 · L2');open.type='button';open.onclick=()=>show();open.id='researchOpen';$('wikiPanel').querySelector('.wiki-header').append(open);
 const panel=node('section',undefined,'research-panel');panel.id='researchPanel';panel.hidden=true;
 panel.innerHTML=`<button type="button" id="researchBack">← L1 整理設定</button><h2>我的研究</h2><p id="researchStock"></p>
 <form id="researchForm"><label for="researchQuestion">你想研究什麼？</label><input id="researchQuestion" required maxlength="2000" placeholder="例如：資料中心需求對獲利的影響" autocomplete="off"><label for="researchWindow">觀察期間</label><select id="researchWindow"><option value="30">最近 30 日</option><option value="90">最近 90 日</option><option value="365">最近一年</option></select><small id="researchModel"></small><div id="researchAvailability" class="research-meta" role="status" aria-live="polite" hidden><span id="researchAvailabilityText"></span><div id="researchBlockers" hidden></div></div><span id="researchSubmitWrap" tabindex="0"><button id="researchSubmit" class="wiki-primary">建立研究</button></span><div id="researchBusyTip" class="wiki-tip" role="tooltip" hidden></div></form>
 <p id="researchStatus" role="status" aria-live="polite"></p><h3>研究問題目錄</h3><p class="research-meta">依問題文字整理面向；不改變研究依據。</p><div id="researchFacets" class="research-facets"></div><label for="researchSearch">尋找研究問題</label><input id="researchSearch" type="search" placeholder="搜尋問題文字"><div id="researchSaved"></div><details><summary>觀點分類</summary><div id="researchTaxonomy"></div></details>`;
 $('wikiControls').prepend(panel);
 const result=node('section',undefined,'research-result');result.id='researchResult';result.hidden=true;$('wikiLower').prepend(result);
 const layerStatus=node('div',undefined,'wiki-counts');layerStatus.id='wikiResearchStatus';layerStatus.hidden=true;layerStatus.setAttribute('role','status');layerStatus.setAttribute('aria-live','polite');const layerText=node('span');const layerRetry=button('重試讀取',()=>loadLayer());layerRetry.id='wikiResearchRetry';layerStatus.append(layerText,layerRetry);$('wikiCounts').after(layerStatus);
 const layerMessage=(text,working=false,retry=false)=>{layerText.textContent=text;layerStatus.hidden=!text;layerStatus.setAttribute('aria-busy',String(working));layerText.classList.toggle('research-working',working);layerRetry.hidden=!retry;};
 let layerRequest=0,runRequest=0,catalogRequest=0,facetFilter='',catalogRows=[];
 const facetNames={investment:'投資回報',growth:'需求與成長',profitability:'獲利與成本',valuation:'估值與股價',risk:'風險與監管',competition:'競爭優勢',momentum:'動能與趨勢',general:'其他研究'};
 let stock='',serial=0,runId=null,timer=null,availabilityTimer=null,tipTimer=null,busy=false,submitting=false,lastAvailability=null;
 const pending=new Map(),drafts=new Map();let progressText='',watching=null,availabilityError='',checking=false,availabilityRequest=0;
 function rememberDraft(){if(stock)drafts.set(stock,{question:$('researchQuestion').value,window:$('researchWindow').value});}
 let statusSource='';const status=text=>{statusSource=text;$('researchStatus').textContent=text;};
 function progress(text){progressText=text;status(text);layerMessage(text,true);}
 function finishProgress(){progressText='';layerMessage('');}
 async function api(path,body){const r=await fetch('/api/wiki/research/'+path+(body===undefined?(path.includes('?')?'&':'?')+'instrument='+encodeURIComponent(stock):''),body===undefined?{signal:AbortSignal.timeout(45000)}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,instrument:stock})});const v=await r.json();if(!r.ok)throw Error(v.error||'研究請求失敗');return v;}
 function clearTip(){clearTimeout(tipTimer);$('researchBusyTip').hidden=true;}
 function busyReason(){return availabilityError?'無法確認模型狀態，正在重新連線…':checking?'正在確認模型狀態…':busy?'L1 整理中：'+(lastAvailability?.instruments?.join('、')||'其他工作')+'。共用模型目前忙碌；完成或停止後即可建立研究。':'';}
 function explain(){clearTip();if(busy&&!availabilityError&&!checking)tipTimer=setTimeout(()=>{if(!busy)return;$('researchBusyTip').textContent=busyReason()+' 可先停止 L1 資料補足；已保存的 L2 仍可閱讀。';$('researchBusyTip').hidden=false;},550);}
 for(const ev of ['pointerenter','focusin'])$('researchSubmitWrap').addEventListener(ev,explain);
 for(const ev of ['pointerleave','focusout'])$('researchSubmitWrap').addEventListener(ev,clearTip);
 $('researchSubmitWrap').addEventListener('keydown',e=>{if(e.key==='Escape')clearTip();});
 function availabilityMessage(){
  const message=busyReason(),box=$('researchAvailability');box.hidden=!message;$('researchAvailabilityText').textContent=message;box.setAttribute('aria-busy',String(checking));box.classList.toggle('research-working',checking);
  const links=$('researchBlockers'),targets=busy&&!checking&&!availabilityError?(lastAvailability?.instruments||[]):[],stamp=targets.join('|')+(availabilityError?'error':'');
  if(links.dataset.state!==stamp){links.dataset.state=stamp;links.replaceChildren();
   for(const target of targets)links.append(button('查看 '+target,async()=>{rememberDraft();$('wikiInstrument').value=target;$('wikiSaved').value=target;await $('wikiSaved').onchange();}));
   if(availabilityError)links.append(button('重新確認',()=>availabilityOnce()));
  }
  links.hidden=!links.children.length;
 }
 function syncButton(){ $('researchSubmit').setAttribute('aria-busy',String(submitting||checking));$('researchSubmit').disabled=busy||checking||submitting;$('researchSubmit').textContent=submitting?'分析中…':checking?'確認狀態…':'建立研究';$('researchSubmit').classList.toggle('research-working',submitting||checking);$('researchSubmitWrap').setAttribute('aria-describedby','researchAvailability researchBusyTip');availabilityMessage();if(!busy||availabilityError||checking)clearTip();}
 async function availability(){const token=serial;try{await availabilityOnce();if(token!==serial)return;if(pending.has(stock)&&watching!==pending.get(stock))track(pending.get(stock),token);}catch(e){/* Availability owns its visible error; polling will recover. */}finally{if(token===serial&&!panel.hidden){clearTimeout(availabilityTimer);availabilityTimer=setTimeout(availability,2000);}}}
 async function loadRun(id,animate=false,valid=()=>true){const token=serial,request=++runRequest,r=await api('run?id='+encodeURIComponent(id));if(token!==serial||request!==runRequest||!valid()||r.bundle.lens.instrument!==stock)return false;runId=id;layerMessage('');wiki.setResearch(r,id,animate);render(r);renderCatalog();return true;}
 function render(r){
  result.hidden=false;result.replaceChildren();$('wikiLower').classList.add('research-visible');
  result.append(node('h3',r.bundle.lens.normalized_question,'research-source'));
  if(r.current_epochs.corpus!==r.bundle.manifest.epochs.corpus||r.current_epochs.taxonomy!==r.bundle.manifest.epochs.taxonomy)result.append(node('p','來源或觀點已有更新；目前保留原研究快照。','research-meta'));
  const actions=node('div',undefined,'research-actions');
  for(const [label,mode] of [['持續追蹤','live'],['固定快照','pinned']])actions.append(button(label,async()=>{const token=serial;await api('save',{run_id:runId,mode});if(token!==serial)return;status(mode==='live'?'已保存；L1 閒置後依相關新證據增量更新。':'已固定這次條件與結果。');await saved();}));
  result.append(actions);const claims=new Map(r.result.claims.map(c=>[c.id,c]));
  for(const [heading,refs] of [['結論',r.result.summary],['敘事動能',r.result.narrative],['支持',r.result.support],['反證',r.result.counter]]){
   const section=node('section');section.append(node('h4',heading));if(!refs.length)section.append(node('p','本次範圍沒有足夠資料。'));
   for(const id of refs){const c=claims.get(id);if(!c)continue;const article=node('article');article.append(Object.assign(button(c.statement,()=>wiki.selectNode(runId+':'+c.id)),{className:'research-source'}));const chain=[];
    for(const o of r.bundle.opinions.filter(o=>c.derived_from.includes(o.claim_id))){chain.push(Object.assign(button('L1 · '+o.title,()=>wiki.selectNode(o.revision_id)),{className:'research-source'}),node('p',o.selection_reason));for(const e of o.evidence){const a=node('a','新聞原文');a.href=e.url;a.target='_blank';a.rel='noopener noreferrer';chain.push(node('blockquote',e.quote,'research-source'),a);}}
    if(c.assumptions.length)chain.push(field('成立條件：',c.assumptions.join('；')));if(c.invalidating_conditions.length)chain.push(field('失效條件：',c.invalidating_conditions.join('；')));article.append(details('查看依據與條件',chain));section.append(article);
   }result.append(section);
  }
  result.append(details('價格動能 · 無可用資料',[node('p','缺少可驗證的行情版本，未計算報酬或價格動能。')]),details('範圍與缺口',[node('p',r.bundle.lens.time_spec.start+' → '+r.bundle.lens.time_spec.end),...r.result.gaps.map(x=>node('p',x))]));
 }
 async function saved(){
  const token=serial,request=++catalogRequest,[r,recent]=await Promise.all([api('lenses'),api('runs')]);if(token!==serial||request!==catalogRequest)return;
  const known=new Set((r.lenses||[]).flatMap(s=>s.history||[s.run_id]));
  catalogRows=[...(r.lenses||[]),...(recent.runs||[]).filter(s=>s.lens&&!known.has(s.id)).map(s=>({id:s.id,lens:s.lens,run_id:s.id,mode:'result',history:[s.id]}))];
  renderCatalog();
 }
 function renderCatalog(){
  const facets=$('researchFacets');facets.replaceChildren();
  const keys=[...new Set(catalogRows.flatMap(s=>s.lens.research_facets||['general']))];
  if(facetFilter&&!keys.includes(facetFilter))facetFilter='';
  for(const key of ['',...keys]){const count=catalogRows.filter(s=>!key||(s.lens.research_facets||['general']).includes(key)).length;
   const b=button('',()=>{facetFilter=key;renderCatalog();});b.append(node('span',key?(facetNames[key]||key):'全部研究'),node('small',' · '+count));b.dataset.facet=key;b.setAttribute('aria-pressed',String(facetFilter===key));facets.append(b);}
  const query=$('researchSearch').value.trim().toLocaleLowerCase(),r={lenses:catalogRows.filter(s=>(!facetFilter||(s.lens.research_facets||['general']).includes(facetFilter))&&s.lens.query.toLocaleLowerCase().includes(query))};
  const box=$('researchSaved');box.replaceChildren();
  if(!r.lenses.length)box.append(node('p',catalogRows.length?'沒有符合的研究問題。':'尚未建立研究。'));
  for(const s of r.lenses){const section=node('section');section.dataset.run=s.run_id;section.classList.toggle('research-current',s.history.includes(runId));section.append(Object.assign(button(s.lens.query,()=>loadRun(s.run_id)),{className:'research-source'}),node('small',s.mode==='result'?'已完成結果':s.mode==='pinned'?'固定快照':({fresh:'已更新',stale:'有新資料',failed:'更新失敗'})[s.refresh_state]));
   if(s.mode==='live')section.append(button('更新',async()=>{await availabilityOnce();if(busy){status(busyReason());return;}const token=serial,j=await api('refresh',{lens_id:s.id,expected_revision:s.revision});if(token!==serial)return;if(j.status==='unchanged')status('證據未變，已沿用結果，沒有呼叫模型。');else{submitting=true;syncButton();track(j.job_id,token);}}));
   if(s.history.length>1)section.append(details('歷史版本',s.history.slice().reverse().map((id,i)=>button(i?'較早版本 '+(s.history.length-i):'目前版本',()=>loadRun(id)))),button('比較上一版',async()=>{const token=serial,[a,b]=await Promise.all([api('run?id='+s.run_id),api('run?id='+s.history.at(-2))]);if(token!==serial)return;await loadRun(s.run_id);if(token!==serial)return;const before=new Set(b.result.claims.map(c=>c.statement)),after=new Set(a.result.claims.map(c=>c.statement));const diff=details('與上一版比較',[node('p','新增／修訂'),...a.result.claims.filter(c=>!before.has(c.statement)).map(c=>node('p',c.statement)),node('p','不再出現'),...b.result.claims.filter(c=>!after.has(c.statement)).map(c=>node('p',c.statement))]);diff.open=true;result.prepend(diff);}));box.append(section);
  }
 }
 $('researchSearch').addEventListener('input',renderCatalog);
 async function terms(){const token=serial,t=await api('taxonomy');if(token!==serial)return;const box=$('researchTaxonomy');box.replaceChildren();for(const term of t.terms){const b=button(AtlasI18n.termLabel(term)+' · '+(term.opinion_ids?.length||0)+(AtlasI18n.language()==='en'?' groups':' 組'),()=>{$('wikiLayer').value='L1';$('wikiLayer').dispatchEvent(new Event('change'));wiki.filterTerm(term.id);});const dot=node('i',undefined,'wiki-dot');dot.style.background=term.color;b.prepend(dot);box.append(b);}}
 function track(job,token){pending.set(stock,job);watching=job;submitting=true;syncButton();progress('L2 正在讀取研究進度…');watch(job,token);}
 async function watch(job,token){
  clearTimeout(timer);if(token!==serial)return;
  try{
   const j=await api('job?id='+job);if(token!==serial)return;
   if(j.status==='completed'){
    progress('L2 已完成分析，正在載入觀點圖譜…');
    // Retain the job until its result is mounted. A failed GET never resubmits the model job.
    const loaded=await loadRun(j.payload.run_id,true);if(token!==serial)return;
    if(!loaded){timer=setTimeout(()=>watch(job,token),2000);return;}
    pending.delete(stock);watching=null;submitting=false;finishProgress();syncButton();
    status('研究完成；已驗證的 L2 觀點已加入共用圖譜。');
    try{await saved();}catch(e){if(token===serial)status('研究已完成；保存清單暫時無法讀取：'+e.message);}
   }else if(['failed','interrupted','cancelled'].includes(j.status)){
    pending.delete(stock);watching=null;submitting=false;finishProgress();syncButton();
    const message='研究未完成：'+(j.error||j.status)+'。原有結果已保留。';status(message);layerMessage(message);
   }else{
    const since=Date.parse(j.created_at),elapsed=Number.isFinite(since)?' · 已等待 '+Math.max(0,Math.floor((Date.now()-since)/1000))+' 秒':'';
    progress((j.status==='queued'?'L2 等待模型工作槽':'L2 正在整合觀點與反證')+elapsed+'；完成後加入圖譜。');
    timer=setTimeout(()=>watch(job,token),2000);
   }
  }catch(e){if(token===serial){
   progress('L2 進度／結果讀取暫時中斷，正在重新連線：'+e.message);
   // Keep watching even when the research sidebar is closed.
   timer=setTimeout(()=>watch(job,token),2000);
  }}
 }
 async function availabilityOnce(){const token=serial,request=++availabilityRequest;try{const a=await api('availability');if(token!==serial||request!==availabilityRequest)return;lastAvailability=a;busy=a.busy;checking=false;availabilityError='';if(a.active_job&&!pending.has(stock))pending.set(stock,a.active_job.id);syncButton();}catch(e){if(token===serial&&request===availabilityRequest){lastAvailability=null;busy=true;checking=false;availabilityError=e.message;syncButton();}throw e;}}
 async function show(){layerMessage('');const next=$('wikiInstrument').value;if(next!==stock){rememberDraft();runId=null;result.replaceChildren();result.hidden=true;$('researchSaved').replaceChildren();$('researchTaxonomy').replaceChildren();stock=next;facetFilter='';catalogRows=[];$('researchSearch').value='';const draft=drafts.get(stock);$('researchQuestion').value=draft?.question||'';$('researchWindow').value=draft?.window||'30';}serial++;clearTimeout(timer);watching=null;clearTimeout(availabilityTimer);submitting=pending.has(stock);checking=true;availabilityError='';lastAvailability=null;busy=false;syncButton();panel.hidden=false;$('wikiControls').classList.add('research-mode');$('researchStock').textContent=stock;$('researchModel').textContent=$('wikiModel').selectedOptions[0]?.textContent||'gpt-6.1-sol · high';const token=serial;status('正在載入已保存研究與分類…');$('researchStatus').classList.add('research-working');availability();try{await Promise.all([saved(),terms()]);if(token===serial&&statusSource==='正在載入已保存研究與分類…')status('');}catch(e){if(token===serial)status(e.message);}finally{if(token===serial)$('researchStatus').classList.remove('research-working');}if(token===serial)$('researchQuestion').focus();}
 $('researchBack').onclick=()=>{panel.hidden=true;$('wikiControls').classList.remove('research-mode');clearTimeout(availabilityTimer);clearTip();};
 $('researchForm').onsubmit=async e=>{e.preventDefault();if(submitting)return;const token=serial;submitting=true;syncButton();progress('L2 正在確認研究工作狀態…');try{await availabilityOnce();if(token!==serial)return;if(busy){submitting=false;finishProgress();syncButton();status(busyReason());return;}progress('L2 準備研究條件與證據…');const [model,reasoning_effort]=($('wikiModel').value||'gpt-6.1-sol|high').split('|');const j=await api('query',{query:$('researchQuestion').value,lookback_days:Number($('researchWindow').value),model,reasoning_effort});if(token!==serial)return;track(j.job_id,token);}catch(e){if(token===serial){submitting=false;finishProgress();syncButton();status(e.message);}}};
 window.addEventListener('atlas-wiki-stock',()=>{rememberDraft();serial++;layerRequest++;runRequest++;finishProgress();stock='';runId=null;clearTimeout(timer);clearTimeout(availabilityTimer);watching=null;panel.hidden=true;result.hidden=true;result.replaceChildren();$('wikiControls').classList.remove('research-mode');$('wikiLower').classList.remove('research-visible');});
 window.addEventListener('atlas-wiki-research-clear',()=>{layerRequest++;runRequest++;layerMessage('');runId=null;result.hidden=true;$('wikiLower').classList.remove('research-visible');});
 async function loadLayer(){
  const request=++layerRequest;runRequest++;
  if(submitting&&progressText){layerMessage(progressText,true);return;}
  if($('wikiLayer').value==='L1'){layerMessage('');result.hidden=true;$('wikiLower').classList.remove('research-visible');return;}
  if(runId){layerMessage('');result.hidden=false;$('wikiLower').classList.add('research-visible');return;}
  stock=$('wikiInstrument').value;const token=serial,valid=()=>token===serial&&request===layerRequest&&$('wikiLayer').value!=='L1';
  layerMessage('正在讀取 L2 研究…',true);
  try{const r=await api('runs');if(!valid())return;if(r.runs.length)await loadRun(r.runs[0].id,false,valid);else layerMessage('尚未建立 L2；請由「研究問題 · L2」輸入問題。');}
  catch(e){if(valid())layerMessage('無法讀取 L2：'+e.message,false,true);}
 }
 window.addEventListener('atlas-wiki-layer',loadLayer);

 const uiPhrases={
  "研究問題目錄":"Research questions", "依問題文字整理面向；不改變研究依據。":"Grouped by question wording; research evidence is unchanged.",
  "尋找研究問題":"Find a research question", "全部研究":"All research", "已完成結果":"Completed result",
  "沒有符合的研究問題。":"No matching research questions.", "尚未建立研究。":"No research yet.",
  "投資回報":"Investment returns", "需求與成長":"Demand and growth", "獲利與成本":"Profitability and costs", "估值與股價":"Valuation and price", "風險與監管":"Risk and regulation", "競爭優勢":"Competitive advantage", "動能與趨勢":"Momentum and trends", "其他研究":"Other research",
  "研究問題 · L2": "Research question · L2",
  "← L1 整理設定": "← L1 maintenance",
  "我的研究": "My research",
  "你想研究什麼？": "What would you like to research?",
  "例如：資料中心需求對獲利的影響": "Example: Data center demand and earnings",
  "觀察期間": "Lookback window",
  "最近 30 日": "Last 30 days",
  "最近 90 日": "Last 90 days",
  "最近一年": "Last year",
  "建立研究": "Create research",
  "已保存的研究": "Saved research",
  "觀點分類": "Opinion classifications",
  "重試讀取": "Retry reading",
  "持續追蹤": "Track updates",
  "固定快照": "Pinned snapshot",
  "結論": "Conclusions",
  "敘事動能": "Narrative momentum",
  "支持": "Support",
  "反證": "Counterarguments",
  "本次範圍沒有足夠資料。": "Insufficient evidence in this scope.",
  "新聞原文": "Original news",
  "查看依據與條件": "Evidence and conditions",
  "價格動能 · 無可用資料": "Price momentum · unavailable",
  "缺少可驗證的行情版本，未計算報酬或價格動能。": "No verifiable price revision; returns and price momentum were not calculated.",
  "範圍與缺口": "Scope and gaps",
  "尚未保存研究。": "No saved research.",
  "已更新": "Up to date",
  "有新資料": "New evidence",
  "更新失敗": "Update failed",
  "更新": "Update",
  "歷史版本": "History",
  "目前版本": "Current version",
  "比較上一版": "Compare previous version",
  "與上一版比較": "Changes from previous version",
  "新增／修訂": "Added / revised",
  "不再出現": "No longer present",
  "分析中…": "Analyzing…",
  "確認狀態…": "Checking status…",
  "重新確認": "Check again",
  "正在載入已保存研究與分類…": "Loading saved research and classifications…",
  "正在讀取 L2 研究…": "Loading L2 research…",
  "尚未建立 L2；請由「研究問題 · L2」輸入問題。": "No L2 yet. Enter a question in Research question · L2.",
  "研究完成；已驗證的 L2 觀點已加入共用圖譜。": "Research complete; validated L2 opinions are now in the shared graph.",
  "L2 正在確認研究工作狀態…": "L2 checking research availability…",
  "L2 準備研究條件與證據…": "L2 preparing the lens and evidence…",
  "L2 正在讀取研究進度…": "L2 reading research progress…",
  "L2 已完成分析，正在載入觀點圖譜…": "L2 analysis complete; loading the graph…",
  "來源或觀點已有更新；目前保留原研究快照。": "Sources or opinions have changed; this view retains the original research snapshot.",
  "證據未變，已沿用結果，沒有呼叫模型。": "Evidence unchanged; reusing the result without a model call.",
  "已保存；L1 閒置後依相關新證據增量更新。": "Saved; relevant new evidence will be checked when L1 is idle.",
  "已固定這次條件與結果。": "This lens and result are pinned.",
  "無法確認模型狀態，正在重新連線…": "Cannot confirm model availability; reconnecting…",
  "正在確認模型狀態…": "Checking model availability…",
  "其他工作": "Other work",
  "研究請求失敗": "Research request failed",
  "分類／全文相關": "Classification / full-text relevance",
  "同股票時間窗內背景觀點": "Background opinion within this stock’s time window",
  "成立條件：": "Assumptions: ",
  "失效條件：": "Invalidating conditions: ",
  "價格資料缺少可驗證的歷史可知性，價格動能 unavailable": "Historical availability of prices is not verifiable; price momentum is unavailable.",
  "沒有可比歷史敘事基線，不推斷敘事轉強": "No comparable historical narrative baseline; strengthening narrative is not inferred.",
  "僅引用已取得的標題與摘要；新聞來源取得可能不完整": "Only acquired titles and summaries are cited; news coverage may be incomplete.",
  "既有觀點採相容包裝，成立條件及展望未知": "Legacy opinions use compatibility wrappers; conditions and horizons are unknown.",
  "分類採模型標籤；未分類仍可由全文召回，新增術語尚未評估時沿用原版本標籤": "Classification uses model labels; unlabeled opinions remain retrievable by text. Existing labels are retained until new terms are assessed.",
  "沒有符合硬條件的 L1；未放寬篩選": "No L1 matches the hard constraints; filters were not relaxed."
},uiOriginals=new WeakMap();
 // Dynamic strings remain keyed by their original source, so polling, late
 // responses and round trips through another language use the same UI owner.
 const uiPatterns=[
  [/^L1 整理中：(.*?)。共用模型目前忙碌；完成或停止後即可建立研究。( 可先停止 L1 資料補足；已保存的 L2 仍可閱讀。)?$/,(_,stocks,tip)=>'L1 processing: '+(stocks==='其他工作'?'Other work':stocks)+'. The shared model is busy; create research after it finishes or stops.'+(tip?' You can stop L1 maintenance first. Saved L2 results remain readable.':'')],
  [/^查看 (.+)$/,(_,stock)=>'View '+stock],
  [/^較早版本 (\d+)$/,(_,version)=>'Earlier version '+version],
  [/^L2 (等待模型工作槽|正在整合觀點與反證)(?: · 已等待 (\d+) 秒)?；完成後加入圖譜。$/,(_,stage,seconds)=>(stage==='等待模型工作槽'?'L2 waiting for the model slot':'L2 integrating opinions and counterevidence')+(seconds?' · Waiting '+seconds+' s':'')+'; results will appear in the graph when complete.'],
  [/^研究未完成：(.*)。原有結果已保留。$/,(_,error)=>'Research incomplete: '+error+'. Previous results retained.'],
  [/^研究已完成；保存清單暫時無法讀取：(.*)$/,(_,error)=>'Research complete; saved list temporarily unavailable: '+error],
  [/^L2 進度／結果讀取暫時中斷，正在重新連線：(.*)$/,(_,error)=>'L2 progress/result reading interrupted; reconnecting: '+error],
  [/^無法讀取 L2：(.*)$/,(_,error)=>'Unable to read L2: '+error]
 ];
 function uiText(source){if(AtlasI18n.language()!=='en')return source;if(uiPhrases[source])return uiPhrases[source];for(const [pattern,format] of uiPatterns)if(pattern.test(source))return source.replace(pattern,format);return source;}
 function localizeResearch(){
  const english=AtlasI18n.language()==='en';
  const visit=n=>{if(n.nodeType===3){if(n.parentElement?.closest('.research-source'))return;const old=uiOriginals.get(n),current=n.nodeValue,source=old&&old.rendered===current?old.source:current;const rendered=uiText(source);uiOriginals.set(n,{source,rendered});if(current!==rendered)n.nodeValue=rendered;return;}for(const c of n.childNodes)visit(c);};
  for(const target of [open,panel,result,layerStatus])visit(target);
  $('researchSearch').placeholder=english?'Search question text':'搜尋問題文字';
  $('researchQuestion').placeholder=english?uiPhrases['例如：資料中心需求對獲利的影響']:'例如：資料中心需求對獲利的影響';
 }
 const localeObserver=new MutationObserver(localizeResearch);for(const target of [open,panel,result,layerStatus])localeObserver.observe(target,{subtree:true,childList:true,characterData:true});
 window.addEventListener('atlas-language',()=>{localizeResearch();if(!panel.hidden)terms().catch(()=>{});});localizeResearch();

})();
