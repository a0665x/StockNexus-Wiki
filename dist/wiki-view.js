/* Independent Wiki surface. Display controls never start model work. */
(function(root){
 'use strict';
 const hooks=root.AtlasWikiContext;if(!hooks)return;
 const $=id=>document.getElementById(id),language=()=>root.AtlasI18n?.language()||'zh-Hant',t=(zh,en)=>language()==='en'?en:zh;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const palette={direct:'#7de3bd',indirect:'#7db6f2',low:'#e7b779',uncertain:'#bb9fe4'};
 const kindNames=()=>({ArticleRevision:t('新聞版本','News revision'),Claim:t('陳述','Claim'),Event:t('事件','Event'),Thesis:t('通用觀點 L1','General opinion L1'),CustomerOpinion:t('研究觀點 L2','Research opinion L2')});
 const categoryNames=()=>({direct:t('直接營運／財務','Direct operating / financial'),indirect:t('間接影響','Indirect influence'),low:t('低關聯／噪聲','Low relevance / noise'),uncertain:t('證據不足','Uncertain')});
 const panel=el('section',undefined,'wiki-panel');panel.id='wikiPanel';panel.hidden=true;panel.dataset.ownI18n='true';
 panel.innerHTML=`<header class="wiki-header"><a href="#news" id="wikiBack"></a><h2>LLM Wiki</h2><button id="wikiExport"></button></header>
 <div class="wiki-layout"><aside id="wikiControls" class="wiki-controls">
 <label><span data-ui="saved"></span><select id="wikiSaved"></select></label>
 <label><span data-ui="instrument"></span><input id="wikiInstrument" placeholder="NASDAQ:GOOGL" maxlength="40"></label>
 <label><span data-ui="scope"></span><select id="wikiScope"><option value="global"></option><option value="loaded"></option><option value="focus"></option></select></label>
 <p id="wikiSelection" class="wiki-note"></p><section id="wikiCoverage" class="wiki-coverage"></section><p id="wikiStatus" class="wiki-status" role="status"></p><div class="wiki-actions"><button id="wikiStart" class="wiki-primary" disabled></button><button id="wikiPause" hidden></button></div>
 <label><span data-ui="dates"></span><select id="wikiRange"><option value="month"></option><option value="quarter"></option><option value="all"></option><option value="custom"></option></select></label>
 <div id="wikiDates"><div class="wiki-pair"><label><span data-ui="start"></span><input id="wikiStartDate" type="date"></label><label><span data-ui="end"></span><input id="wikiEndDate" type="date"></label></div>
 <div class="wiki-dual"><div class="wiki-track"></div><input id="wikiRangeStart" type="range"><input id="wikiRangeEnd" type="range"></div><output id="wikiInterval"></output></div>
 <section id="wikiSelectedCoverage"></section>
 <label><span data-ui="operation"></span><select id="wikiOperation"><option value="update"></option><option value="review"></option></select></label>
 <label><span data-ui="model"></span><select id="wikiModel"></select></label><p id="wikiModelNote" class="wiki-note"></p>
 <label class="wiki-check"><input type="checkbox" id="wikiContinuous"><span data-ui="continuous"></span></label>

 <div id="wikiStartTip" class="wiki-tip" role="tooltip" hidden></div></aside>
 <div id="wikiResizeLeft" class="wiki-resize" role="separator" tabindex="0" aria-orientation="vertical" aria-controls="wikiControls"></div>
 <main class="wiki-canvas-area"><div class="wiki-toolbar">
 <label><span data-ui="layer"></span><select id="wikiLayer"><option value="L1">L1</option><option value="L2">L2</option><option value="both">L1 + L2</option></select></label><label><span data-ui="version"></span><select id="wikiVersion"></select></label>
 <input id="wikiViewStart" type="hidden"><input id="wikiViewEnd" type="hidden">
 <label><span data-ui="kind"></span><select id="wikiKind"></select></label><label><span data-ui="relation"></span><select id="wikiRelation"></select></label>
 <label><span data-ui="budget"></span><select id="wikiBudget"><option>800</option><option>1600</option><option>2400</option></select></label>
 <label><span data-ui="category"></span><select id="wikiAssessment"></select></label></div>
 <section id="wikiLive" class="wiki-live" role="status" aria-live="polite"></section>
 <div id="wikiResizeLive" class="wiki-resize wiki-resize-row" role="separator" tabindex="0" aria-orientation="horizontal" aria-label="調整進度區高度" aria-controls="wikiLive"></div><details id="wikiVersionInfo" class="wiki-insights"></details><div id="wikiCounts" class="wiki-counts"></div>
 <div class="wiki-graph-stage"><div id="wikiCanvas" class="wiki-canvas"></div><div id="wikiEmpty" class="wiki-empty"></div></div>
 <div id="wikiResizeTimeline" class="wiki-resize wiki-resize-row" role="separator" tabindex="0" aria-orientation="horizontal" aria-controls="wikiLower wikiCanvas"></div><div id="wikiLower" class="wiki-lower"><section id="wikiTimeline" class="wiki-timeline"></section><details id="wikiInsights" class="wiki-insights"></details></div></main>
 <div id="wikiResizeRight" class="wiki-resize" role="separator" tabindex="0" aria-orientation="vertical" aria-controls="wikiSide"></div><aside id="wikiSide" class="wiki-detail"><section id="wikiDetail"></section></aside></div>`;
 document.body.append(panel);
 const dialog=el('dialog',undefined,'wiki-settings');dialog.id='wikiSettings';dialog.dataset.ownI18n='true';dialog.innerHTML=`<form method="dialog"><button id="wikiSettingsClose">×</button></form><h2 id="wikiSettingsTitle"></h2><label><span id="wikiLanguageLabel"></span><select id="wikiLanguages"><option value="both"></option><option value="zh-Hant">繁體中文</option><option value="en">English</option></select></label><label><span id="wikiStrategyLabel"></span><select id="wikiStrategy"><option value="lexical"></option><option value="chronological"></option><option value="root"></option><option value="fusion"></option></select></label><p id="wikiStrategyNote" class="wiki-note"></p><label><span id="wikiEvidenceLabel"></span><select id="wikiEvidenceSize"><option>5</option><option>10</option><option>15</option><option>20</option></select></label><p id="wikiEvidenceNote" class="wiki-note"></p><div class="wiki-settings-actions"><span id="wikiApplyStatus" role="status"></span><button id="wikiApply" class="wiki-primary" hidden>Apply</button></div>`;document.body.append(dialog);
 const open=el('button','LLM Wiki');open.id='modeWiki';$('modeTimeline').after(open);
 let data=null,info=null,graph=null,plan=null,busy=false,models=[],pollTimer=null,previewTimer=null,generation=0,request=0,previewSerial=0;
 let catalogAt=0,catalogPending=null,polling=false,showPending=null,loading=0,pollError=null;const graphRequests=new Map();
 let fitPending=false,fitKey='';
 let baseData=null,researchRun=null,reveal=Infinity,revealTimer=null,hoverNode=null,glow=null,classStamp='';
 let lastJobs=[],lastConfig={},lastCoverage=null,selectedDetail=null,selectedEdge=false;
 let appliedSettings=null,rootSelection=null,graphUniverse=null,graphSettings=null,chartWindow=null,chartDrag=null,chartMoved=false,chartReload=null,chartResize=null,detailRequest=0;
 const treeOpen=new Set();let initialized=false,restoringUI=false,viewReload=null,focusRoot=null,focusIds=null;
 const runtimeKeys=['wikiLayer','wikiScope','wikiModel','wikiOperation','wikiRange','wikiStartDate','wikiEndDate','wikiRangeStart','wikiRangeEnd','wikiVersion','wikiKind','wikiRelation','wikiBudget','wikiAssessment','wikiLanguages','wikiEvidenceSize','wikiStrategy','wikiContinuous'];
 const topicNames=()=>({revenue:t('營收與獲利','Revenue and earnings'),operations:t('生產與營運','Production and operations'),costs:t('成本與投資','Costs and investment'),market:t('市場與股價','Market and price'),trading:t('交易觀點','Trading views'),other:t('其他／待分類','Other / unclassified')});
 const copy=(node)=>{const fields=node.translations?.[language()];return fields?{...node,title:fields.title||node.title,summary:fields.summary||node.summary,rationale:fields.rationale||node.rationale,assessment:{...node.assessment,rationale:fields.rationale}}:node;};
 const status=(text,error=false,working=false)=>{$('wikiStatus').textContent=text;$('wikiStatus').classList.toggle('error',error);$('wikiStatus').classList.toggle('wiki-working',working);$('wikiStatus').setAttribute('aria-busy',String(working));};
 const current=()=>$('wikiInstrument').value.trim().toUpperCase();
 const day=d=>d.toISOString().slice(0,10),stamp=d=>Date.parse(d+'T00:00:00Z')/86400000;
 const option=(name,value)=>new Option(name,value);
 function choices(id,items){const node=$(id),old=node.value;node.replaceChildren(...items.map(([v,n])=>option(n,v)));if([...node.options].some(o=>o.value===old))node.value=old;}
 const ui={layer:['觀點層','Opinion layer'],saved:['已建立的 Wiki','Saved Wikis'],instrument:['股票識別','Instrument'],scope:['來源範圍','Evidence scope'],dates:['整理日期（UTC）','News dates (UTC)'],start:['全局起始日期','Outer start date'],end:['全局結束日期','Outer end date'],operation:['維護方式','Operation'],model:['模型與思考深度','Model and reasoning depth'],continuous:['持續檢查這個日期範圍的新證據','Watch new evidence in this fixed date range'],version:['版本','Version'],viewStart:['版本內新聞起日（UTC）','News from (UTC)'],viewEnd:['版本內新聞迄日（UTC）','News through (UTC)'],kind:['節點','Nodes'],relation:['關係','Relations'],budget:['渲染上限','Render budget'],category:['觀點分類','Classification']};
 function translate(){
  panel.querySelectorAll('[data-ui]').forEach(n=>n.textContent=t(...ui[n.dataset.ui]));
  const labels={wikiBack:['← 新聞圖譜','← News graph'],wikiExport:['匯出 Markdown','Export Markdown'],wikiStart:['開始整理','Start maintenance'],wikiPause:['停止持續維護','Stop watching'],wikiSettingsTitle:['Wiki 設定','Wiki settings'],wikiLanguageLabel:['生成與保存語系','Generate and store languages'],wikiEvidenceLabel:['每次推論的新聞篇數','Articles per reasoning call'],wikiStrategyLabel:['整理時如何選取證據','How to group evidence'],wikiEvidenceNote:['每組 5／10／15／20 篇；Graph 自動覆蓋模式依整棵樹的篇數。沒有每日上限，可隨時停止。','5 / 10 / 15 / 20 per group; Graph coverage uses each complete tree size. No daily limit; stop any time.']};
  for(const [id,text] of Object.entries(labels))$(id).textContent=t(...text);
  choices('wikiScope',[['global',t('全局：目前查詢與 DB','Global: current queries and DB')],['loaded',t('目前已載入新聞','Loaded news')],['focus',t('目前焦點與關聯節點','Focused roots and related nodes')]]);
  choices('wikiRange',[['month',t('最近一個月','Past month')],['quarter',t('最近三個月','Past three months')],['all',t('全部日期','All dates')],['custom',t('自訂範圍','Custom range')]]);
  choices('wikiOperation',[['update',t('補新證據並檢視相依觀點','Add missing evidence and revisit dependents')],['review',t('重新檢視既有觀點','Re-evaluate existing viewpoints')]]);
  choices('wikiKind',[['',t('全部類型','All types')],...Object.entries(kindNames())]);
  choices('wikiRelation',[['',t('全部關係','All relations')],...['SUPPORTS','CONTRADICTS','UPDATES','DEPENDS_ON','RELATED_TO','TEMPORALLY_PRECEDES'].map(v=>[v,v])]);
  classificationChoices();
  choices('wikiStrategy',[['lexical',t('詞彙相關','Lexical relevance')],['chronological',t('時間順序','Chronological')],['root',t('Graph 強關聯 root','Graph root neighborhood')],['fusion',t('多來源融合','Multi-source fusion')]]);
  $('wikiLanguages').options[0].textContent=t('繁體中文 ＋ English（預設）','Traditional Chinese + English (default)');
  $('wikiStartTip').textContent=t('顯示篩選不會重算 Wiki。按下開始後，選取新聞的標題、摘要及相關舊觀點會交給登入模型處理；引用保留原文，修訂保留原版。你可以隨時停止。已消耗的用量不會退回。','Display filters never recompute the Wiki. Starting sends selected titles, summaries and related prior viewpoints to your signed-in model. Original quotes and previous versions are retained. Stop any time; consumed usage cannot be refunded.');
  $('wikiRangeStart').setAttribute('aria-label',t('選取起點','Selected start'));$('wikiRangeEnd').setAttribute('aria-label',t('選取終點','Selected end'));
  $('wikiResizeLeft').setAttribute('aria-label',t('調整左側寬度','Resize left panel'));$('wikiResizeRight').setAttribute('aria-label',t('調整右側寬度','Resize right panel'));$('wikiResizeTimeline').setAttribute('aria-label',t('調整圖表高度','Resize chart height'));$('wikiSettingsClose').setAttribute('aria-label',t('關閉設定','Close settings'));
  $('wikiModelNote').textContent=t('思考深度取自目前登入的模型目錄；更換模型不重抽已完成新聞。','Reasoning choices come from your model catalog. Changing model reuses completed evidence.');
  strategyNote();modelChoices();savedChoices();versionChoices();selection();sliderLabel();paintPlan();activity();render();if(selectedDetail)details(selectedDetail,selectedEdge);
  if(!panel.hidden)$('relationOpen').textContent=t('⚙ Wiki 設定','⚙ Wiki settings');
 }
 function syncGraphUniverse(){const news=hooks.selection('global');if(news.graph_universe?.articles?.length&&news.graph_universe.ticker===current().split(':')[1]){graphUniverse=news.graph_universe;graphSettings=news.graph_settings;}}
 function strategyNote(){const notes={lexical:['先依詞彙重疊組合新聞，再找相關舊觀點。','Group by word overlap, then retrieve related existing viewpoints.'],chronological:['依新聞日期由早至晚，逐組建立脈絡。','Process news oldest first in adjacent date groups.'],root:['從完整新聞圖譜自動採樣 root，直到涵蓋此日期範圍全部新聞；跳過重複覆蓋，包含未渲染與孤立節點。整棵樹送入模型，區間外成員僅作脈絡；超出輸入容量才分段。','Automatically sample roots over the complete News graph until every article in the Wiki date range is covered, including unrendered and isolated nodes. Skip redundant coverage. Send the whole tree; outside-range members are context. Split only for input capacity.'],fusion:['優先相關但不同來源的新聞，保留分歧及各自的證據邊界。','Prefer related news from different sources; preserve disagreements and their evidence boundaries.']};$('wikiStrategyNote').textContent=t(...notes[$('wikiStrategy').value])+' '+t('所有方式共用同一觀點庫；切換不會清空已整理內容。','All methods share one opinion store; switching keeps completed work.');$('wikiEvidenceSize').disabled=$('wikiStrategy').value==='root';if($('wikiStrategy').value==='root')$('wikiStrategyNote').textContent+=' '+(graphUniverse?.articles?.length?t(`新聞圖譜完整範圍：${graphUniverse.articles.length} 篇。無需手動點選。`,`Full News universe: ${graphUniverse.articles.length} articles. No manual selection needed.`):t('請先載入此股票的新聞圖譜。','Load the News graph for this stock first.'));dirtySettings();}

 async function api(path,body){const r=await fetch('/api/wiki/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await r.json();if(!r.ok)throw Error(value.error||t('Wiki 請求失敗','Wiki request failed'));return value;}
 function modelChoices(){const old=$('wikiModel').value;choices('wikiModel',models.flatMap(m=>(m.reasoning?.length?m.reasoning:[{reasoningEffort:'low'}]).map(r=>{const effort=r.reasoningEffort||r.effort||r;return [m.id+'|'+effort,m.name+' · '+effort];})));if([...$('wikiModel').options].some(o=>o.value===old))$('wikiModel').value=old;}
 function savedChoices(preserveChoice=false){const old=$('wikiSaved').value;choices('wikiSaved',[['',t('建立新的股票 Wiki','Create a stock Wiki')],...(info?.instruments||[]).map(s=>[s.instrument,s.instrument+' · v'+s.version])]);if(data&&!Array.from($('wikiSaved').options).some(o=>o.value===data.instrument))$('wikiSaved').add(option(data.instrument,data.instrument));$('wikiSaved').value=preserveChoice?old:old||data?.instrument||'';}
 function versionChoices(){choices('wikiVersion',[['',t('最新版本','Latest version')],...(data?.versions||[]).slice(0,10).map(v=>[String(v.version),'v'+v.version+' · '+new Date(v.created_at).toLocaleString(language())])]);}
 function range(){if($('wikiRange').value==='all')return null;return {start:day(new Date(Number($('wikiRangeStart').value)*86400000)),end:day(new Date(Number($('wikiRangeEnd').value)*86400000))};}
 function sliderLabel(){if(!$('wikiRangeStart').value)return;const r=range();$('wikiInterval').textContent=r?r.start+' → '+r.end:t('全部日期','All dates');const a=Number($('wikiRangeStart').min),b=Number($('wikiRangeStart').max),den=b-a||1;document.querySelector('.wiki-dual').style.setProperty('--from',100*(Number($('wikiRangeStart').value)-a)/den+'%');document.querySelector('.wiki-dual').style.setProperty('--to',100*(Number($('wikiRangeEnd').value)-a)/den+'%');}
 function sliders(reset=true){const a=stamp($('wikiStartDate').value),b=stamp($('wikiEndDate').value);if(!Number.isFinite(a)||!Number.isFinite(b)||a>b)return;for(const id of ['wikiRangeStart','wikiRangeEnd']){$(id).min=a;$(id).max=b;$(id).step=1;if(reset)$(id).value=id==='wikiRangeStart'?a:b;}$('wikiDates').hidden=false;sliderLabel();}
 function preset(){const end=new Date(),start=new Date(end);start.setUTCMonth(start.getUTCMonth()-($('wikiRange').value==='quarter'?3:1));if(['month','quarter'].includes($('wikiRange').value)){$('wikiStartDate').value=day(start);$('wikiEndDate').value=day(end);}sliders();}
 function selection(){const selected=hooks.selection($('wikiScope').value);selected.graph_selection=rootSelection||lastConfig.graph_selection||selected.graph_selection;if(![1,3,5,7].includes(selected.price_horizon))selected.price_horizon=lastConfig.price_horizon||3;$('wikiSelection').textContent=t(`已載入 ${selected.articles.length} 篇；全局模式另查 DB。`,`Loaded ${selected.articles.length} articles; global scope also reads the DB.`);return selected;}
 function meter(parent,label,value,total){if(!total){parent.append(el('small',t('此範圍沒有新聞','No articles in this range')));return;}const box=el('div',undefined,'wiki-meter');box.append(el('span',`${label} · ${value}/${total} · ${(100*value/total).toFixed(2)}%`));const bar=el('progress');bar.max=total;bar.value=value;bar.setAttribute('aria-label',label);box.append(bar);parent.append(box);}
 function tokenText(usage){return `${usage?.input_tokens||0} ${t('輸入','in')} / ${usage?.output_tokens||0} ${t('輸出','out')}`;}
 function miningIcon(){const span=el('span',undefined,'wiki-worker');span.setAttribute('aria-hidden','true');span.innerHTML=`<svg viewBox="0 0 96 86" focusable="false"><use href="/knowledge-mining.svg#base"/><use class="wiki-scan" href="/knowledge-mining.svg#scan"/><use class="wiki-signal" href="/knowledge-mining.svg#signal"/></svg>`;return span;}
 function activity(){
  const active=lastJobs.find(j=>['queued','running'].includes(j.status)),running=active?.status==='running',waiting=!!active||!!(lastConfig.catch_up&&lastCoverage?.scope_pending>0),box=$('wikiLive');box.dataset.state=running?'running':waiting?'queued':lastCoverage?.scope_pending?'idle':'complete';
  const labels={compiling:t('LLM 正在梳理證據與相依觀點','LLM is analyzing evidence and dependent viewpoints'),repairing:t('正在修正未通過驗證的提案','Repairing a proposal that failed validation'),publishing:t('正在核對引用並保存版本','Checking citations and saving a version')};
  const title=active?.payload.operation==='classify_l1'?t('LLM 正在補足通用觀點分類','LLM is classifying existing L1 opinions'):running?labels[active.payload.stage]||labels.compiling:waiting?t('等待背景整理開始','Waiting for background work'):lastCoverage?.scope_pending?t('尚有新聞待補；模型目前沒有運行','Evidence pending; model is idle'):t('目前沒有進行中的整理','No active work');
  const worker=box.querySelector('.wiki-worker')||miningIcon();if(!worker.isConnected)box.append(worker);for(const child of [...box.children])if(child!==worker)child.remove();const content=el('div');content.append(el('strong',title));
  if(lastCoverage?.scope_total)meter(content,t('已確認範圍覆蓋','Confirmed scope coverage'),lastCoverage.scope_done,lastCoverage.scope_total);
  if(active){const p=active.payload;content.append(el('small',t('目前方法：','Current method: ')+({lexical:t('詞彙相關','Word overlap'),chronological:t('時間順序','Chronological'),root:t('Graph 全範圍 root 覆蓋','Graph root coverage'),fusion:t('多來源融合','Source fusion')})[p.strategy||'lexical']));content.append(el('small',t(`本次工作 ${active.done??p.done}/${p.revisions?.length??p.total} · ${p.model}`,`Current work ${active.done??p.done}/${p.revisions?.length??p.total} · ${p.model}`)),el('small',(p.operation==='review'?t('↻ 重新檢視觀點','↻ Re-evaluating viewpoints'):t('✧ 新證據與觀點更新','✧ New evidence and viewpoint updates'))+' · '+(p.current_date?.slice(0,10)||'—')),el('p',p.current_title||t('準備證據…','Preparing evidence…'),'wiki-current-title'));if(p.group_info?.groups)content.append(el('small',t(`Root ${p.group_info.group}/${p.group_info.groups} · 本樹涵蓋目標 ${p.group_info.targets} 篇`,`Root ${p.group_info.group}/${p.group_info.groups} · ${p.group_info.targets} target articles`)));if(p.current_size)content.append(el('small',p.current_size+t(' 篇／本組',' articles in this group')+(p.group_info?.parts>1?' · '+p.group_info.part+'/'+p.group_info.parts+t(' 段',' parts'):'')));
   content.append(el('small',t('本組 token：等待模型回報','Current batch tokens: awaiting model report')+(p.last_usage?' · '+t('上一組 ','Previous batch ')+tokenText(p.last_usage):'')),el('small',t('本次工作累計 ','Current job total ')+tokenText(active.usage||p.usage)));
   const stop=el('button',t('停止工作','Stop'));stop.onclick=async()=>{try{await api('cancel',{instrument:current(),job_id:active.id});await poll();schedulePreview();}catch(e){status(e.message,true);}};box.append(stop);
  }
  if(!active&&lastJobs[0]?.payload.last_usage)content.append(el('small',t('最近一組已回報 token ','Latest reported batch tokens ')+tokenText(lastJobs[0].payload.last_usage)));
  const usage=plan?.usage||lastCoverage?.usage;if(usage){content.append(el('small',t('所選新聞時段累計 ','Selected news interval total ')+tokenText(usage.reported)));if(usage.legacy_jobs_without_attribution)content.append(el('small',t('較早版本沒有逐批用量資料，未納入此區間統計。','Older jobs lack per-batch usage and are excluded from interval totals.')));}
  if(!waiting){const failed=lastJobs.find(j=>j.status==='failed'||j.status==='interrupted');if(failed&&failed===lastJobs[0]){box.dataset.state='failed';content.append(el('small',t('前次工作停止：','Previous work stopped: ')+(failed.error||failed.status)));}}
  box.append(content);
  $('wikiStart').classList.toggle('wiki-working',busy||waiting);$('wikiStart').setAttribute('aria-busy',String(busy||waiting));
  $('wikiStart').textContent=busy?t('準備整理…','Preparing…'):waiting?t('整理中…','Processing…'):lastCoverage?t('繼續整理','Continue processing'):t('開始整理','Start processing');
  $('wikiStart').disabled=busy||waiting||loading>0||!info?.writable||!$('wikiModel').value||!current();$('wikiPause').hidden=!(lastConfig.enabled||lastConfig.catch_up);
  const coverage=$('wikiCoverage');coverage.replaceChildren();
  if(lastCoverage){if(lastCoverage.unavailable)coverage.append(el('p',lastCoverage.error));else{meter(coverage,t('已確認新聞','Confirmed evidence'),lastCoverage.scope_done,lastCoverage.scope_total);const store=el('details');store.append(el('summary',t('資料庫','Database')),el('p',lastCoverage.storage,'wiki-storage'));coverage.append(store);}}
 }
 function invalidate(){generation++;previewSerial++;plan=null;$('wikiStart').disabled=true;$('wikiSelectedCoverage').replaceChildren();}
 function schedulePreview(){invalidate();clearTimeout(previewTimer);activity();}
 function paintPlan(){if(!plan)return;const box=$('wikiSelectedCoverage');box.replaceChildren();meter(box,t('所選區間已處理','Processed in selected interval'),plan.reused,plan.selected);box.append(el('small',t(`待處理 ${plan.pending} 篇；按開始後持續整理，可隨時停止。`,`${plan.pending} articles pending. Start to process; stop any time.`)));if(plan.graph_selection?.mode==='coverage')box.append(el('small',t(`完整圖譜 ${plan.graph_selection.universe_articles} 篇 → ${plan.graph_selection.trees.length} 棵 root；區間目標 ${plan.graph_selection.target_articles} 篇，整樹含脈絡 ${plan.graph_selection.context_articles} 篇。`,`Full graph ${plan.graph_selection.universe_articles} articles → ${plan.graph_selection.trees.length} roots; ${plan.graph_selection.target_articles} interval targets, ${plan.graph_selection.context_articles} members including context.`)));else if(plan.graph_selection)box.append(el('small',plan.graph_selection.trees.map(x=>x.title+' · '+x.articles.length+t(' 篇',' articles')).join(' / ')));status(plan.pending?plan.instrument:t('此範圍無待辦，未啟動模型。','Nothing pending in this range. Model remains idle.'));}
 function draftSettings(){return {languages:$('wikiLanguages').value==='both'?['zh-Hant','en']:[$('wikiLanguages').value],evidence_size:Number($('wikiEvidenceSize').value)||5,strategy:$('wikiStrategy').value,...($('wikiStrategy').value==='root'?{graph_universe:graphUniverse,graph_settings:graphSettings||lastConfig.graph_settings||{}}:{} )};}
 function dirtySettings(){const changed=!!appliedSettings&&JSON.stringify(draftSettings())!==JSON.stringify(appliedSettings),missing=$('wikiStrategy').value==='root'&&(!graphUniverse?.articles?.length||graphUniverse.ticker!==current().split(':')[1]);$('wikiApply').hidden=!changed;$('wikiApply').disabled=busy||missing;$('wikiApplyStatus').textContent=changed&&missing?t('請先載入同一股票的新聞圖譜；不需要點選 root。','Load this stock’s News graph first; no root click is required.'):changed?t('套用後，進行中的工作會停止並依新設定接續。','Apply stops active work and continues with these settings.'):'';}

 function requestBody(settings=appliedSettings||draftSettings()){const [model,reasoning_effort]=$('wikiModel').value.split('|');const body={...selection(),instrument:current(),model,reasoning_effort,scope:$('wikiScope').value,date_range:range(),operation:$('wikiOperation').value,...settings};if(body.strategy==='root'&&body.graph_universe)delete body.graph_selection;return body;}
 function query(){const p=new URLSearchParams({instrument:current()});if($('wikiVersion').value)p.set('version',$('wikiVersion').value);const dates=range();if(dates){p.set('start',dates.start);p.set('end',dates.end);}return p;}
 function clearStock(){researchRun=null;baseData=null;clearTimeout(revealTimer);root.dispatchEvent(new CustomEvent('atlas-wiki-stock'));invalidate();request++;data=null;lastCoverage=null;lastJobs=[];lastConfig={};selectedDetail=null;detailRequest++;chartWindow=null;focusRoot=null;focusIds=null;fitKey='';treeOpen.clear();versionChoices();$('wikiViewStart').value='';$('wikiViewEnd').value='';$('wikiDetail').replaceChildren();$('wikiCounts').textContent=t('尚未載入此股票 Wiki','This stock Wiki is not loaded');$('wikiVersionInfo').replaceChildren();$('wikiTimeline').replaceChildren();$('wikiInsights').replaceChildren();graph?.graphData({nodes:[],links:[]});activity();}
 function restore(cfg){if(!cfg)return;if(cfg.model){const value=cfg.model+'|'+(cfg.reasoning_effort||'low');if([...$('wikiModel').options].some(o=>o.value===value))$('wikiModel').value=value;}$('wikiLanguages').value=cfg.languages?.length===1?cfg.languages[0]:'both';$('wikiEvidenceSize').value=String([5,10,15,20].includes(cfg.evidence_size)?cfg.evidence_size:5);$('wikiStrategy').value=cfg.strategy||'lexical';$('wikiRange').value=cfg.date_range?'custom':'all';if(cfg.date_range){$('wikiStartDate').value=cfg.date_range.start;$('wikiEndDate').value=cfg.date_range.end;}sliders();if(!rootSelection?.ticker&&cfg.graph_selection?.mode!=='coverage')rootSelection=cfg.graph_selection;if(cfg.graph_universe){graphUniverse=cfg.graph_universe;graphSettings=cfg.graph_settings;}appliedSettings={...draftSettings(),...(cfg.strategy==='root'?{graph_universe:cfg.graph_universe||null,graph_settings:cfg.graph_settings||{}}: {})};strategyNote();}
 async function load(restoreSettings=false){
  const mine=++request;if(!current())return false;loading++;status(t('正在讀取已保存的 Wiki 圖譜…','Loading saved Wiki graph…'),false,true);activity();
  try{
   // Restore the saved range from lightweight state before loading the graph.
   // This avoids building a graph for the default month only to discard it.
   if(restoreSettings){const meta=await api('jobs?'+new URLSearchParams({instrument:current()}));if(mine!==request||panel.hidden)return false;restore(meta.config||{});}
   const key=String(query());
   if(!graphRequests.has(key)){const work=api('graph?'+key).finally(()=>graphRequests.delete(key));graphRequests.set(key,work);}
   const value=await graphRequests.get(key);if(mine!==request||panel.hidden)return false;
   if(data&&data.version!==value.version){selectedDetail=null;$('wikiDetail').replaceChildren(el('p',t('點選此版本的節點查看引用。','Select a node in this version to view its citations.')));}
   baseData=value;combine();lastJobs=[...(value.jobs||[]),...(value.classification_jobs||[])];lastConfig=value.config||{};lastCoverage=value.coverage;
   classStamp=JSON.stringify((value.classification_jobs||[]).map(j=>[j.status,j.updated_at]));
   savedChoices();versionChoices();classificationChoices();activity();
   if(focusRoot&&!data.nodes.some(n=>n.id===focusRoot)){focusRoot=null;focusIds=null;}
   render();if(focusRoot&&data.nodes.some(n=>n.id===focusRoot))focusGalaxy(focusRoot,false);
   if(restoreSettings)schedulePreview();if(!busy)status('');return true;
  }catch(e){if(mine===request)status(e.message,true);return false;}
  finally{loading--;if(!loading&&!busy){$('wikiStatus').classList.remove('wiki-working');$('wikiStatus').setAttribute('aria-busy','false');}activity();}
 }
 async function refreshCatalog(force=false){
  if(panel.hidden)return;if(catalogPending)return catalogPending;if(!force&&Date.now()-catalogAt<5000)return;
  catalogAt=Date.now();catalogPending=(async()=>{try{const value=await api('status');if(panel.hidden)return;const changed=JSON.stringify(value.instruments)!==JSON.stringify(info?.instruments);info=value;if(changed)savedChoices(true);}catch{}finally{catalogPending=null;}})();return catalogPending;
 }
 async function poll(){if(panel.hidden||polling)return;polling=true;try{await refreshCatalog();if(panel.hidden||!current()||!data)return;const ident=current(),mine=request;try{const value=await api('jobs?'+new URLSearchParams({instrument:ident}));if(panel.hidden||current()!==ident||mine!==request)return;if(pollError&&$('wikiStatus').textContent===pollError&&!busy&&!loading)status('');pollError=null;const was=lastJobs.some(j=>['queued','running'].includes(j.status));lastJobs=[...(value.jobs||[]),...(value.classification_jobs||[])];lastConfig=value.config||{};lastCoverage=value.coverage;activity();const nextStamp=JSON.stringify((value.classification_jobs||[]).map(j=>[j.status,j.updated_at]));if(!$('wikiVersion').value&&(data.version!==value.version||classStamp!==nextStamp)){classStamp=nextStamp;await load();}if(was&&!lastJobs.some(j=>['queued','running'].includes(j.status)))schedulePreview();}catch(e){if(panel.hidden||current()!==ident||mine!==request)return;pollError=e.message;$('wikiLive').dataset.state='offline';$('wikiLive').replaceChildren(el('strong',t('連線中斷；無法確認模型狀態','Connection lost; model status unknown')));status(e.message,true);}}finally{polling=false;}}
 const termColor=n=>data?.taxonomy?.terms.find(t=>(n.classification_terms||[]).includes(t.id))?.color;
 const nodeColor=n=>n.wikiDim?'#1a293a':termColor(n)||(n.id===focusRoot?'#ffe0a0':n.wikiContext?'#687b8e':({ArticleRevision:'#78b7e7',Claim:'#83dfbf',Event:'#e6bc76',Thesis:'#c3a2ee',CustomerOpinion:'#f1b4df'})[n.kind]);
 const nodeSize=n=>n.wikiContext?2:n.kind==='ArticleRevision'?3:6;
 const linkColor=l=>l.wikiDim?'#152333':'#91b4c5',linkWidth=l=>l.wikiDim?.25:1;
 function styleFocus(){if(!graph)return;const id=v=>typeof v==='object'?v.id:v;for(const n of graph.graphData().nodes)n.wikiDim=!!focusIds&&!focusIds.has(n.id);for(const l of graph.graphData().links)l.wikiDim=!!focusIds&&(!focusIds.has(id(l.source))||!focusIds.has(id(l.target)));graph.nodeColor(nodeColor).linkColor(linkColor).linkWidth(linkWidth);}
 function clearGalaxy(){if(!focusRoot)return;focusRoot=null;focusIds=null;selectedDetail=null;detailRequest++;$('wikiDetail').replaceChildren(el('p',t('點選此版本的節點查看引用。','Select a node in this version to view its citations.')));styleFocus();saveRuntime();}
 function focusGalaxy(id,remember=true){focusRoot=id;focusIds=new Set([id]);let layer=[id];for(let depth=0;depth<3&&layer.length&&focusIds.size<150;depth++){const next=[];for(const e of data.edges){const a=e.source.stable_id,b=e.target.stable_id;for(const [from,to] of [[a,b],[b,a]])if(layer.includes(from)&&!focusIds.has(to)&&focusIds.size<150){focusIds.add(to);next.push(to);}}layer=next;}fitPending=false;styleFocus();if(remember)saveRuntime();}
 // Track travel for the whole gesture: dragging away and back is still a drag.
 let graphPress=null,backgroundClickAllowed=false;
 const canvas=$('wikiCanvas');
 canvas.addEventListener('pointerdown',e=>{fitPending=false;backgroundClickAllowed=false;graphPress={id:e.pointerId,x:e.clientX,y:e.clientY,moved:false,left:e.button===0&&!e.ctrlKey&&!e.metaKey};},true);
 canvas.addEventListener('pointermove',e=>{if(graphPress?.id===e.pointerId&&Math.hypot(e.clientX-graphPress.x,e.clientY-graphPress.y)>4)graphPress.moved=true;},true);
 canvas.addEventListener('pointerup',e=>{backgroundClickAllowed=!!graphPress&&graphPress.id===e.pointerId&&graphPress.left&&!graphPress.moved;graphPress=null;},true);
 canvas.addEventListener('pointercancel',()=>{graphPress=null;backgroundClickAllowed=false;},true);
 root.addEventListener('blur',()=>{graphPress=null;backgroundClickAllowed=false;});
 function render(){
  combine();if(!data)return;classificationChoices();
  const kind=$('wikiKind').value,category=$('wikiAssessment').value,relation=$('wikiRelation').value,budget=Number($('wikiBudget').value);
  const specialIds=new Set(viewpoints().filter(n=>classificationTags(n).includes(category)).flatMap(n=>data.opinion_groups?.[n.id]||[n.id]));
  const layer=$('wikiLayer').value;const priority=new Set(researchRun?.bundle.opinions.flatMap(o=>[o.revision_id,...o.evidence.map(e=>e.revision_id)])||[]);const matches=data.nodes.filter(n=>(layer==='both'||(n.layer||'L1')===layer)&&(!kind||n.kind===kind)&&(!category||(category.startsWith('__')?specialIds.has(n.id):(n.classification_terms||[]).includes(category)))&&(n.layer!=='L2'||n.reveal_index<reveal)).sort((a,b)=>(b.layer==='L2'?2:priority.has(b.id)?1:0)-(a.layer==='L2'?2:priority.has(a.id)?1:0)).slice(0,budget);
  const primary=new Set(matches.map(n=>n.id)),wanted=new Set(primary),allowed=data.edges.filter(e=>!relation||e.relation_type===relation);
  // A category describes interpretations, not sources. Keep their actual one-hop
  // evidence/dependencies visible as context, within the same rendering budget.
  if(category&&!kind&&layer!=='L2')for(const e of allowed){const a=e.source.stable_id,b=e.target.stable_id;if(primary.has(a))wanted.add(b);if(primary.has(b))wanted.add(a);}
  const context=data.nodes.filter(n=>(layer==='both'||(n.layer||'L1')===layer)&&wanted.has(n.id)&&!primary.has(n.id)).slice(0,Math.max(0,budget-matches.length));
  const subset=[...matches.map(n=>({...n,wikiContext:false})),...context.map(n=>({...n,wikiContext:true}))],ids=new Set(subset.map(n=>n.id));
  const edges=allowed.filter(e=>ids.has(e.source.stable_id)&&ids.has(e.target.stable_id));
  if((focusRoot&&!ids.has(focusRoot))||(selectedDetail&&(!selectedEdge?!ids.has(selectedDetail.id):!edges.some(e=>e.id===selectedDetail.id)))){focusRoot=null;focusIds=null;selectedDetail=null;selectedEdge=false;detailRequest++;$('wikiDetail').replaceChildren();}
  if(focusIds)focusIds=new Set([...focusIds].filter(id=>ids.has(id)));
  const parents=new Map(subset.map(n=>[n.id,n.id])),find=id=>{let p=id;while(parents.get(p)!==p)p=parents.get(p);while(id!==p){const next=parents.get(id);parents.set(id,p);id=next;}return p;};
  for(const e of edges)parents.set(find(e.source.stable_id),find(e.target.stable_id));
  const clusters=new Set(subset.map(n=>find(n.id))).size;
  $('wikiCounts').replaceChildren(document.createTextNode(t(`版本 ${data.version} · 節點 ${subset.length} / ${data.total_nodes} · 連線 ${edges.length}`,`Version ${data.version} · Nodes ${subset.length} / ${data.total_nodes} · Edges ${edges.length}`)+(data.truncated?t(' · 已限制載入範圍',' · Load limit applied'):'')));
  if(category&&!kind&&layer!=='L2')$('wikiCounts').append(el('small',t(`符合分類 ${matches.length} · 引用／相依背景 ${context.length}（灰色）`,`Category matches ${matches.length} · Citation/dependency context ${context.length} (gray)`)));
  if(researchRun&&layer!=='L1')$('wikiCounts').append(el('small',t('L2 與引用背景使用建立研究時的固定快照。','L2 and cited context use the fixed research snapshot.')));
  if(clusters>1)$('wikiCounts').append(el('small',t(`${clusters} 個獨立群；群之間尚無通過驗證的模型關係。`,`${clusters} separate groups; no validated model relation between them yet.`)));
  $('wikiEmpty').hidden=subset.length>0;$('wikiEmpty').textContent=t('此範圍尚無節點。選擇新聞範圍並開始整理。','No nodes in this range. Select evidence and start processing.');
  versionInfo();timeline();overview();
  if(!subset.length){graph?.graphData({nodes:[],links:[]});return;}
  try{
   if(!graph){
    graph=root.ForceGraph3D()($('wikiCanvas')).backgroundColor('#080f1a').showNavInfo(false).nodeId('id')
     .nodeColor(nodeColor)
     .nodeVal(nodeSize).nodeLabel(n=>el('span',(n.layer||'L1')+' · '+copy(n).title+' · '+(data?.taxonomy?.terms||[]).filter(t=>(n.classification_terms||[]).includes(t.id)).map(t=>t.label).join('、')+(n.wikiContext?t(' · 引用／相依背景',' · Evidence/dependency context'):'')).outerHTML)
     .linkLabel(l=>el('span',l.edge.relation_type).outerHTML).linkColor(linkColor).linkOpacity(.65).linkDirectionalArrowLength(3).linkDirectionalArrowRelPos(1).linkWidth(linkWidth)
     .onNodeHover(n=>{hoverNode=n;glow?.refresh();}).cooldownTicks(70).onNodeClick(n=>{focusGalaxy(n.id);detailRequest++;details(n);if(n.kind!=='ArticleRevision'&&n.layer!=='L2')openViewpoint(n);}).onLinkClick(l=>{detailRequest++;details(l.edge,true);})
     .onBackgroundClick(()=>{if(backgroundClickAllowed)clearGalaxy();})
     .onEngineStop(()=>{if(fitPending){fitPending=false;graph.zoomToFit(0,35);}});
    if(Array.isArray(graph.controls()?.keys)){graph.controls().keys=[];graph.controls().keyState=-1;}
    graph.controls()?.addEventListener?.('start',()=>{fitPending=false;});
    installGlow();
    graph.d3Force('charge').strength(-18).distanceMax(150);graph.d3Force('link').distance(30);
    graph.d3Force('compact',alpha=>{for(const n of graph.graphData().nodes){n.vx-=n.x*.025*alpha;n.vy-=n.y*.025*alpha;n.vz-=n.z*.025*alpha;}});
    new ResizeObserver(()=>{const r=$('wikiCanvas').getBoundingClientRect();if(r.width&&r.height)graph.width(r.width).height(r.height);}).observe($('wikiCanvas'));
   }
   const nextKey=[data.instrument,$('wikiLayer').value,kind,category,relation,budget,$('wikiVersion').value,JSON.stringify(range())].join('|');
   if(fitKey!==nextKey){fitPending=true;fitKey=nextKey;}
   const old=new Map(graph.graphData().nodes.map(n=>[n.id,n]));graph.graphData({nodes:subset.map(n=>Object.assign(old.get(n.id)||{},n)),links:edges.map(e=>({source:e.source.stable_id,target:e.target.stable_id,edge:e}))});if(focusRoot&&!ids.has(focusRoot)){focusRoot=null;focusIds=null;}styleFocus();
   const r=$('wikiCanvas').getBoundingClientRect();graph.width(r.width).height(r.height);
  }catch(e){$('wikiEmpty').hidden=false;$('wikiEmpty').textContent=t('3D 無法啟動；請從下方觀點列表閱讀。','3D unavailable; read the viewpoint list below.');}
 }
 function classificationTerms(){return [...(data?.taxonomy?.terms||[]),{id:'__pending',label:t('待分類','Pending classification'),color:'#adc4d5'},{id:'__unclassified',label:t('未歸類','Unclassified'),color:'#bba7d6'}];}
 function classificationTags(n){const valid=new Set((data?.taxonomy?.terms||[]).map(x=>x.id)),tags=(n.classification_terms||[]).filter(id=>valid.has(id));return tags.length?tags:[n.classification_status==='unclassified'?'__unclassified':'__pending'];}
 function classificationChoices(){
  const select=$('wikiAssessment');if(document.activeElement===select)return;
  const rows=viewpoints(),terms=classificationTerms();
  choices('wikiAssessment',[['',t('全部分類','All classifications')],...terms.map(x=>[x.id,x.label+' · '+rows.filter(n=>classificationTags(n).includes(x.id)).length])]);
  for(const o of select.options){const term=terms.find(x=>x.id===o.value);if(term){o.style.color=term.color;o.title=term.definition||term.label;}}
 }
 $('wikiAssessment').onblur=classificationChoices;
 function filterTerm(id){$('wikiAssessment').value=id;$('wikiKind').value='';render();saveRuntime();}
 function combine(){
  if(!baseData){data=null;return;}
  data={...baseData,nodes:baseData.nodes.map(n=>({...n})),edges:[...baseData.edges]};
  if(!researchRun||$('wikiLayer').value==='L1'||researchRun.bundle.lens.instrument!==baseData.instrument)return;
  const b=researchRun.bundle,ids=new Set(data.nodes.map(n=>n.id)),endpoint=id=>({stable_id:id,revision_id:id});
  const add=n=>{if(!ids.has(n.id)){ids.add(n.id);data.nodes.push(n);}};
  for(const o of b.opinions){add({id:o.revision_id,kind:o.kind||'Claim',layer:'L1',source_snapshot:researchRun.snapshot,title:o.title,summary:o.statement,scope:o.scope,citations:o.evidence,classification_terms:o.labels});for(const e of o.evidence){add({id:e.revision_id,kind:'ArticleRevision',layer:'L1',title:e.quote,summary:e.quote,url:e.url,citations:[],classification_terms:o.labels});data.edges.push({source:endpoint(e.revision_id),target:endpoint(o.revision_id),relation_type:'SUPPORTS',rationale:'固定研究快照中的逐字來源',evidence_refs:[e]});}}
  researchRun.result.claims.forEach((c,index)=>{const id=researchRun.id+':'+c.id,opinions=b.opinions.filter(o=>c.derived_from.includes(o.claim_id));add({id,kind:'CustomerOpinion',layer:'L2',title:c.statement,summary:c.statement,scope:b.lens.instrument,research_question:b.lens.query,snapshot:researchRun.snapshot,run_id:researchRun.id,derived_from:c.derived_from,assumptions:c.assumptions,invalidating_conditions:c.invalidating_conditions,classification_terms:[...new Set(opinions.flatMap(o=>o.labels))],citations:opinions.flatMap(o=>o.evidence),reveal_index:index});for(const o of opinions)data.edges.push({source:endpoint(id),target:endpoint(o.revision_id),relation_type:'DERIVED_FROM',rationale:'L2 使用的精確 L1 claim / revision',evidence_refs:o.evidence});});
  data.edges=[...new Map(data.edges.map(e=>[[e.source.stable_id,e.target.stable_id,e.relation_type].join('|'),e])).values()];data.total_nodes=data.nodes.length;
 }
 function setResearch(run,id,animate=false){
  if(run.bundle.lens.instrument!==current())return;clearTimeout(revealTimer);researchRun={...run,id};reveal=animate&&!matchMedia('(prefers-reduced-motion: reduce)').matches?0:Infinity;combine();if(animate||$('wikiLayer').value==='L1')$('wikiLayer').value='both';$('wikiKind').value='';$('wikiRelation').value='';$('wikiAssessment').value='';render();
  const step=()=>{if(!researchRun||researchRun.id!==id)return;reveal++;render();if(reveal<run.result.claims.length)revealTimer=setTimeout(step,100);};if(reveal===0)step();saveRuntime();
 }
 function installGlow(){
  if(!root.AtlasGlow||glow)return;const overlay=el('canvas',undefined,'wiki-focus-glow');$('wikiCanvas').parentNode.append(overlay);
  glow=root.AtlasGlow.attach(overlay,()=>{const selected=new Set(focusIds||[]);if(hoverNode)selected.add(hoverNode.id);return {graph,trace:{nodes:new Map([...selected].map(id=>[id,{depth:id===focusRoot||id===hoverNode?.id?0:1}]))},config:root.AtlasGlow.settings({brightness:1.8,radius:28}),colors:nodeColor,active:!!selected.size,visible:!panel.hidden,reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches};});
 }
 $('wikiLayer').onchange=()=>{clearTimeout(revealTimer);reveal=Infinity;render();saveRuntime();root.dispatchEvent(new CustomEvent('atlas-wiki-layer',{detail:$('wikiLayer').value}));};
 function versionInfo(){const box=$('wikiVersionInfo'),change=data.changes?.find(v=>v.version===data.version);box.replaceChildren(el('summary',t('此版本的變更','Changes in this version')));if(!change){box.append(el('p',t('此版本沒有變更摘要','No change summary for this version')));return;}box.append(el('p',`v${change.version} · ${change.model} · ${new Date(change.created_at).toLocaleString(language())}`),el('p',t(`新增 ${change.added} 節點、${change.relations} 關係；${change.updates} 個觀點更新連結。`,`Added ${change.added} nodes and ${change.relations} relations; ${change.updates} viewpoint update links.`)));for(const title of change.titles)box.append(el('p',title));}
 function selectedBounds(){const a=Number($('wikiRangeStart').value),b=Number($('wikiRangeEnd').value);return Number.isFinite(a)&&Number.isFinite(b)&&a>10000&&a<=b?{start:a,end:b}:null;}
 function viewpoints(){const bounds=selectedBounds();return (data?.opinion_index||[]).flatMap(n=>{const dates=(n.dates||[]).filter(d=>!bounds||(stamp(d)>=bounds.start&&stamp(d)<=bounds.end));return bounds&&!dates.length?[]:[{...n,date:dates.at(-1)||'unknown'}];});}
 function chartTerms(){const rows=viewpoints(),chosen=$('wikiAssessment').value;return classificationTerms().filter(c=>(!chosen||chosen===c.id)&&rows.some(n=>classificationTags(n).includes(c.id)));}

 async function openViewpoint(item){const mine=++detailRequest,ident=current(),version=data.version;try{const n=await api('node?'+new URLSearchParams({instrument:ident,id:item.id,version,price_horizon:selection().price_horizon||3}));if(mine===detailRequest&&ident===current()&&data.version===version)details(n);}catch(e){status(e.message,true);}}
 function viewpointButtons(box,items){let shown=0;const more=el('button',t('顯示更多','Show more'));function append(){const chunk=items.slice(shown,shown+20);shown+=chunk.length;for(const n of chunk){const button=el('button',copy(n).title,'wiki-viewpoint');button.onclick=()=>openViewpoint(n);box.insertBefore(button,more);}more.hidden=shown>=items.length;}more.onclick=append;box.append(more);append();}
 function categoryDetail(key,start,end){filterTerm(key);detailRequest++;selectedDetail=null;const box=$('wikiDetail'),items=viewpoints().filter(n=>classificationTags(n).includes(key)&&stamp(n.date)>=start&&stamp(n.date)<=end),term=classificationTerms().find(x=>x.id===key);box.replaceChildren(el('h3',term?.label||key),el('p',day(new Date(start*86400000))+' → '+day(new Date(end*86400000))),el('strong',items.length+t(' 個觀點群',' opinion groups')));viewpointButtons(box,items);if(innerWidth<=800)box.scrollIntoView({behavior:'smooth'});}
 function overview(){const box=$('wikiInsights'),rows=viewpoints();box.replaceChildren(el('summary',t('觀點群與分類','Opinion groups and classifications')));for(const term of chartTerms()){const items=rows.filter(n=>classificationTags(n).includes(term.id)),branch=el('details',undefined,'wiki-category');branch.dataset.category=term.id;branch.open=treeOpen.has(term.id);branch.append(el('summary',term.label+' · '+items.length));const populate=()=>{if(branch.dataset.loaded)return;branch.dataset.loaded='true';viewpointButtons(branch,items);};branch.ontoggle=()=>{branch.open?treeOpen.add(term.id):treeOpen.delete(term.id);if(branch.open)populate();};if(branch.open)populate();box.append(branch);}}
 function timeline(){chartResize?.disconnect();const box=$('wikiTimeline'),index=viewpoints(),terms=chartTerms(),colors=Object.fromEntries(terms.map(c=>[c.id,c.color])),names=Object.fromEntries(terms.map(c=>[c.id,c.label]));const dated=index.filter(n=>n.date!=='unknown').map(n=>stamp(n.date));const bounds=selectedBounds()||(dated.length?{start:Math.min(...dated),end:Math.max(...dated)}:null);box.replaceChildren(el('strong',t('L1 觀點群 × 引用新聞日期（UTC）','L1 opinion groups × cited news date (UTC)')));const legend=el('div',undefined,'wiki-chart-legend');for(const term of terms){const n=el('button',term.label);n.style.color=term.color;n.dataset.term=term.id;n.onclick=()=>filterTerm(term.id);legend.append(n);}box.append(legend);if(!bounds){box.append(el('small',t('此範圍尚無可統計的觀點群','No dated opinion groups in this range')));return;}
  let first=chartWindow?.start??bounds.start,last=chartWindow?.end??bounds.end;const span=Math.min(last-first,bounds.end-bounds.start);first=Math.max(bounds.start,Math.min(first,bounds.end-span));last=first+span;chartWindow={start:first,end:last};box.dataset.start=String(first);box.dataset.end=String(last);
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 700 140');svg.setAttribute('role','group');svg.setAttribute('tabindex','0');svg.setAttribute('aria-label',t('觀點分類數量；滾輪縮放，拖曳平移，點選長條查看觀點','Viewpoint counts; wheel to zoom, drag to pan, click a bar for viewpoints'));const add=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,String(v));if(text)n.textContent=text;svg.append(n);return n;};
  const days=last-first+1,bins=Math.min(60,days),groups=Array.from({length:bins},()=>({}));const counts=index.map(n=>({date:n.date,categories:Object.fromEntries(classificationTags(n).filter(k=>k in colors).map(k=>[k,1]))}));for(const row of counts){const date=stamp(row.date);if(date<first||date>last||!Number.isFinite(date))continue;const i=Math.min(bins-1,Math.floor((date-first)/days*bins));for(const [k,v] of Object.entries(row.categories))groups[i][k]=(groups[i][k]||0)+v;}const max=Math.max(1,...groups.map(g=>Object.values(g).reduce((a,b)=>a+b,0)));const hover=el('div',undefined,'wiki-chart-tooltip');hover.hidden=true;hover.setAttribute('role','tooltip');
  function drawPlot(){
   const width=Math.max(220,svg.clientWidth),height=Math.max(80,svg.clientHeight),base=height-30,plotHeight=height-44,plotWidth=width-48;
   svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.replaceChildren();
   add('line',{x1:35,y1:base,x2:width-10,y2:base,stroke:'#486176'});add('text',{x:2,y:15,fill:'#b5c9d8','font-size':11},String(max));add('text',{x:10,y:base+1,fill:'#b5c9d8','font-size':11},'0');
  groups.forEach((g,i)=>{let y=base;const a=first+Math.ceil(i*days/bins),b=first+Math.ceil((i+1)*days/bins)-1;for(const k of Object.keys(colors)){const h=(g[k]||0)/max*plotHeight;if(!h)continue;y-=h;const rect=add('rect',{x:36+i*plotWidth/bins,y,width:Math.max(1,plotWidth/bins-2),height:h,fill:colors[k],tabindex:0,role:'button','data-category':k,'data-count':g[k]});const label=day(new Date(a*86400000))+' → '+day(new Date(b*86400000))+' · '+names[k]+': '+g[k];rect.setAttribute('aria-label',label);rect.onpointermove=e=>{if(chartDrag)return;hover.textContent=label;hover.hidden=false;hover.style.left=Math.min(e.clientX+12,innerWidth-300)+'px';hover.style.top=e.clientY-45+'px';};rect.onpointerleave=()=>hover.hidden=true;rect.onclick=()=>{if(!chartMoved)categoryDetail(k,a,b);};rect.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();categoryDetail(k,a,b);}};const title=document.createElementNS(ns,'title');title.textContent=label;rect.append(title);}});add('text',{x:35,y:height-9,fill:'#b5c9d8','font-size':11},day(new Date(first*86400000)));add('text',{x:width-10,y:height-9,fill:'#b5c9d8','text-anchor':'end','font-size':11},day(new Date(last*86400000)));
  }
  box.append(svg,hover);drawPlot();chartResize=new ResizeObserver(drawPlot);chartResize.observe(svg);
  function zoom(factor,anchor=.5){const count=Math.max(1,Math.min(bounds.end-bounds.start+1,Math.round(days*factor)));const start=Math.round(first+days*anchor-count*anchor);chartWindow={start,end:start+count-1};timeline();}
  svg.onwheel=e=>{e.preventDefault();const r=svg.getBoundingClientRect();zoom(e.deltaY>0?1.3:1/1.3,Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)));};svg.onpointerdown=e=>{if(e.button)return;chartMoved=false;chartDrag={id:e.pointerId,x:e.clientX,start:first,end:last,width:svg.getBoundingClientRect().width};};svg.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','+','-','Home'].includes(e.key))return;e.preventDefault();if(e.key==='+'||e.key==='-')zoom(e.key==='+'?1/1.3:1.3);else{chartWindow=e.key==='Home'?null:{start:first+Math.round(days*.2)*(e.key==='ArrowLeft'?-1:1),end:last+Math.round(days*.2)*(e.key==='ArrowLeft'?-1:1)};timeline();}};
  const reset=el('button',t('重設縮放','Reset zoom'));reset.onclick=()=>{chartWindow=null;timeline();};const actions=el('div',undefined,'wiki-chart-actions');actions.append(reset,el('small',t('多標籤觀點可列入多個分類；點選長條查看。','Multi-label opinions may appear in multiple categories; select a bar to inspect.')));box.append(actions);
 }
 root.addEventListener('pointermove',e=>{if(!chartDrag||e.pointerId!==chartDrag.id)return;const delta=e.clientX-chartDrag.x;if(Math.abs(delta)<4&&!chartMoved)return;chartMoved=true;const span=chartDrag.end-chartDrag.start+1,shift=Math.round(-delta/chartDrag.width*span);chartWindow={start:chartDrag.start+shift,end:chartDrag.end+shift};timeline();});for(const name of ['pointerup','pointercancel'])root.addEventListener(name,()=>{chartDrag=null;setTimeout(()=>chartMoved=false,0);});
 function dateSelectionChanged(){clearTimeout(viewReload);viewReload=setTimeout(()=>{if(data)load();},250);saveRuntime();chartWindow=null;detailRequest++;selectedDetail=null;if(data){$('wikiDetail').replaceChildren();timeline();overview();}schedulePreview();}
 function marketDetails(box,n){
  box.append(el('h4',t('觀察到的市場反應','Observed market response')));
  const section=el('section',undefined,'wiki-market-current');box.append(section);
  function observation(o){
   const missing=o.mean_return===null||o.mean_return===undefined;
   let result=missing?t('快取資料尚不足','Cached prices incomplete'):(o.mean_return>=0?'+':'')+(100*o.mean_return).toFixed(2)+'%';
   if(missing&&Number.isFinite(o.available_sessions))result+=t(`（已取得 ${o.available_sessions}/${o.required_sessions||o.horizon} 個後續交易日）`,` (${o.available_sessions}/${o.required_sessions||o.horizon} subsequent sessions available)`);
   return el('p',o.ticker+' · '+o.horizon+t(' 交易日平均報酬：',' trading-day mean return: ')+result+(o.baseline_date?' · '+t('基準 ','Baseline ')+o.baseline_date:'')+(o.as_of?' · '+t('股價截至 ','Prices through ')+o.as_of:''));
  }
  if(n.current_market){
   section.append(el('small',t('目前快取觀察 · 跟隨新聞圖譜的交易日設定','Current cached observation · follows News Graph horizon')));
   if(!n.current_market.length)section.append(el('p',t('此節點沒有可對應的新聞股價資料。','No matching article price observations for this node.')));
   for(const o of n.current_market)section.append(observation(o));
   if(n.current_market.some(o=>o.mean_return==null))section.append(el('small',t('尚未到期或股價快取缺日；以最後股價日期與已取得天數判讀，可回新聞圖譜更新股價。','The window may be unfinished or cached sessions missing. Check the last price date and available sessions; refresh prices in News Graph.')));
   section.append(el('small',t('此為最新股價觀察，不改寫模型當時的論證。','These current observations do not rewrite the model’s original rationale.')));
  }else section.append(el('small',t('正在讀取目前股價快取…','Reading current cached prices…')));
  if(n.market_evidence?.length){const history=el('details',undefined,'wiki-market-history');history.append(el('summary',t('生成時使用的股價資料','Price evidence used at generation')));for(const o of n.market_evidence)history.append(observation(o));box.append(history);}
 }
 function details(item,edge=false){selectedDetail=item;selectedEdge=edge;const n=copy(item),box=$('wikiDetail');box.replaceChildren(el('small',edge?t('模型關係提案','Model-proposed relation'):kindNames()[n.kind]),el('h3',edge?n.relation_type:n.title),el('p',edge?n.rationale:n.summary===n.title?'':n.summary||''));if(!edge&&n.layer==='L2'){box.append(el('p','研究問題：'+n.research_question),(()=>{const d=el('details');d.append(el('summary','研究版本'),el('small',n.snapshot));return d;})(),el('p','假設：'+(n.assumptions||[]).join('；')),el('p','失效條件：'+(n.invalidating_conditions||[]).join('；')));}
  if(!edge&&n.kind!=='ArticleRevision'&&n.layer!=='L2'){if(!n.translations?.[language()])box.append(el('small',t('此舊節點尚無此語系版本，顯示原始內容。','This older node has no selected-language variant; showing its original content.')));box.append(el('h4',t('財務影響屬性：','Financial impact: ')+categoryNames()[n.assessment?.category||'uncertain']),el('p',n.assessment?.rationale||t('尚未分類','Not yet classified')),el('p',t('模型質性觀點；尚未驗證與未來股價的關聯。','Qualitative model interpretation; not validated against future stock returns.'),'wiki-note'));}
  if(!edge&&n.unassessed_term_ids?.length)box.append(el('small',t('沿用既有分類；新增術語尚未評估。','Existing labels retained; additional terms have not been evaluated.')));
  if(!edge&&n.kind!=='ArticleRevision'&&n.layer!=='L2'){const labels={supported:t('引用支持','Supported by quotes'),mixed:t('證據分歧','Mixed evidence'),insufficient:t('證據不足','Insufficient evidence')};box.append(el('p',(topicNames()[n.assessment?.topic]||t('主題待重審','Topic pending review'))+' · '+(labels[n.assessment?.evidence]||t('證據程度尚未標記','Evidence strength not yet labeled'))));marketDetails(box,n);}

  if(!edge&&item.url){const a=el('a',t('開啟新聞來源 ↗','Open source ↗'));a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}
  const history=data.histories?.[item.id];if(history){const section=el('section');section.append(el('h4',t('觀點演變：原始＋最新三批','Evolution: original + latest three batches')));const entry=(node,label)=>{const value=copy(node);section.append(el('small',label+' · v'+node.version),el('h4',value.title),el('p',value.summary));};entry(history.original,t('原始觀點','Original'));history.recent_batches.forEach(group=>{for(const node of group)entry(node,t('修訂觀點','Revision'));});box.append(section);}
  if(!edge){for(const e of data.edges.filter(e=>e.source.stable_id===item.id||e.target.stable_id===item.id).slice(0,20)){const b=el('button',e.relation_type+' · '+copy(e).rationale);b.onclick=()=>details(e,true);box.append(b);}}
  const ident=data.instrument;for(const c of item.evidence_refs||item.citations||[]){box.append(el('blockquote',c.quote));const b=el('button',t('查看引用來源','View cited source'));b.onclick=async()=>{try{const a=await api('article?'+new URLSearchParams({instrument:ident,id:c.article_revision_id}));const link=el('a',a.title);link.href=a.url;link.target='_blank';link.rel='noopener noreferrer';b.replaceWith(link);}catch(e){status(e.message,true);}};box.append(b);}
 }
 function saveRuntime(){if(!initialized||restoringUI)return;const controls=Object.fromEntries(runtimeKeys.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).value]));const c=graph?.cameraPosition();const value={instrument:current(),controls,layout:layout.state(),root_selection:rootSelection,graph_universe:graphUniverse,graph_settings:graphSettings,root:focusRoot,selected:selectedDetail?.id||null,...(c?{camera:{x:c.x,y:c.y,z:c.z}}:{})};try{localStorage.setItem('stocknexus.wikiRuntime',JSON.stringify(value));}catch{}root.AtlasWorkspace?.save('wiki',value);}
 function restoreRuntime(saved){if(!saved)return;restoringUI=true;try{layout.restore(saved.layout);if(saved.instrument)$('wikiInstrument').value=saved.instrument;for(const [id,value] of Object.entries(saved.controls||{}))if(runtimeKeys.includes(id)&&id!=='wikiRangeStart'&&id!=='wikiRangeEnd'){$(id).type==='checkbox'?$(id).checked=!!value:$(id).value=value;}sliders();for(const id of ['wikiRangeStart','wikiRangeEnd'])if(saved.controls?.[id]!==undefined)$(id).value=saved.controls[id];rootSelection=saved.root_selection||rootSelection;graphUniverse=saved.graph_universe||graphUniverse;graphSettings=saved.graph_settings||graphSettings;focusRoot=saved.root||null;sliderLabel();strategyNote();}finally{restoringUI=false;}}
 function show(){if(showPending)return showPending;showPending=openWiki().finally(()=>{showPending=null;});return showPending;}
 async function openWiki(){
  panel.hidden=false;layout.refresh();hooks.visible(true);status(t('正在載入 Wiki 狀態…','Loading Wiki status…'),false,true);
  await root.AtlasWorkspace?.ready;
  const selected=hooks.selection('global').graph_selection;if(selected?.trees?.length)rootSelection=selected;
  panel.hidden=false;layout.refresh();hooks.visible(true);graph?.resumeAnimation();translate();
  try{
   const [nextInfo,catalog]=await Promise.all([api('status'),initialized?Promise.resolve(null):api('models')]);info=nextInfo;catalogAt=Date.now();
   if(!initialized){models=catalog.models;modelChoices();
    const saved=root.AtlasWorkspace?.state.wiki||JSON.parse(localStorage.getItem('stocknexus.wikiRuntime')||'null');
    if(saved?.instrument)$('wikiInstrument').value=saved.instrument;
    else if(!current()){const id=hooks.selection('global').search?.instrument;const existing=info.instruments.find(x=>x.instrument===id)||info.instruments.filter(x=>x.version>0).sort((a,b)=>b.version-a.version)[0];if(existing)$('wikiInstrument').value=existing.instrument;}
    savedChoices();
    if(info.instruments.some(x=>x.instrument===current()))await load(true);
    if(saved&&Object.keys(saved.controls||{}).length){const before=String(query());restoreRuntime(saved);if(String(query())!==before&&info.instruments.some(x=>x.instrument===current()))await load();else render();if(saved.selected){const n=data?.nodes.find(n=>n.id===saved.selected);if(n){details(n);if(n.kind!=='ArticleRevision'&&n.layer!=='L2')await openViewpoint(n);}}if(saved.camera){fitPending=false;graph?.cameraPosition(saved.camera);}}
    else if(!data){const preferred=catalog.default_model+'|low';if([...$('wikiModel').options].some(o=>o.value===preferred))$('wikiModel').value=preferred;}
    initialized=true;
   }else{savedChoices();if(data)poll();else if(info.instruments.some(x=>x.instrument===current()))await load();}
   if(selected?.trees?.length)rootSelection=selected;syncGraphUniverse();strategyNote();schedulePreview();saveRuntime();
   if(info.bridge_ready&&!$('wikiStatus').classList.contains('error'))status('');if(!info.bridge_ready)status(t('模型橋接尚未就緒；啟動前請檢查 Chat 服務。','Model bridge is not ready; check the Chat service before starting.'),true);
  }catch(e){status(e.message,true);}
  clearInterval(pollTimer);pollTimer=setInterval(poll,2000);$('wikiBack').focus();
 }
 function hide(e){e?.preventDefault();saveRuntime();panel.hidden=true;dialog.close();clearInterval(pollTimer);clearTimeout(previewTimer);invalidate();request++;graph?.pauseAnimation();hooks.visible(false);$('relationOpen').textContent=root.AtlasI18n?.t('⚙ 關聯設定')||'⚙ Edge settings';open.focus();}
 $('wikiSaved').addEventListener('focus',()=>refreshCatalog(true));root.addEventListener('focus',()=>refreshCatalog(true));
 open.onclick=show;$('wikiBack').onclick=hide;
 $('relationOpen').addEventListener('click',e=>{if(panel.hidden)return;e.preventDefault();e.stopImmediatePropagation();appliedSettings=appliedSettings||draftSettings();syncGraphUniverse();strategyNote();dialog.showModal();},true);
 $('wikiSaved').onchange=async()=>{if(!$('wikiSaved').value)return;$('wikiInstrument').value=$('wikiSaved').value;clearStock();await load(true);};
 for(const id of ['wikiInstrument','wikiScope','wikiModel','wikiOperation'])$(id).addEventListener('input',()=>{if(id==='wikiInstrument')clearStock();if(id==='wikiOperation'){$('wikiContinuous').disabled=$('wikiOperation').value==='review';if($('wikiContinuous').disabled)$('wikiContinuous').checked=false;}strategyNote();selection();schedulePreview();});
 for(const id of ['wikiLanguages','wikiEvidenceSize','wikiStrategy'])$(id).oninput=()=>{strategyNote();dirtySettings();};
 $('wikiApply').onclick=async()=>{if(busy)return;busy=true;dirtySettings();$('wikiApply').classList.add('wiki-working');try{const result=await api('apply',{...requestBody(draftSettings()),continuous:$('wikiContinuous').checked});appliedSettings=draftSettings();invalidate();dialog.close();await load();status(result.status==='noop'?t('設定已套用；選取範圍皆已處理，模型保持停止。','Settings applied; selected evidence is complete. Model remains idle.'):result.resumed?t('已停止舊工作，依新設定接續。','Old work stopped; continuing with new settings.'):t('設定已套用。','Settings applied.'));schedulePreview();}catch(e){status(e.message,true);$('wikiApplyStatus').textContent=e.message;}finally{busy=false;$('wikiApply').classList.remove('wiki-working');dirtySettings();activity();}};
 $('wikiRange').onchange=()=>{preset();dateSelectionChanged();};for(const id of ['wikiStartDate','wikiEndDate'])$(id).oninput=()=>{$('wikiRange').value='custom';sliders();dateSelectionChanged();};
 for(const id of ['wikiRangeStart','wikiRangeEnd'])$(id).oninput=()=>{$('wikiRange').value='custom';if(Number($('wikiRangeStart').value)>Number($('wikiRangeEnd').value))$(id==='wikiRangeStart'?'wikiRangeEnd':'wikiRangeStart').value=$(id).value;sliderLabel();dateSelectionChanged();};
 for(const id of ['wikiKind','wikiRelation','wikiBudget','wikiAssessment'])$(id).onchange=render;
 function selectVersion(){researchRun=null;clearTimeout(revealTimer);$('wikiLayer').value='L1';render();root.dispatchEvent(new CustomEvent('atlas-wiki-research-clear'));return load();}
 for(const id of ['wikiVersion','wikiViewStart','wikiViewEnd'])$(id).onchange=()=>id==='wikiVersion'?selectVersion():load();
 $('wikiStart').onclick=async()=>{
  if(busy||$('wikiStart').disabled)return;busy=true;const mine=generation,ident=current();activity();
  status(t('正在核對快取中的新聞範圍與已完成證據…','Checking cached news and completed evidence…'),false,true);
  try{
   const value=await api('plan',requestBody());if(mine!==generation||ident!==current()||panel.hidden)return;plan=value;
   status(t('正在排入尚未完成的整理工作…','Queuing remaining work…'),false,true);
   const job=await api('jobs',{plan_id:value.plan_id,continuous:$('wikiContinuous').checked,classify_missing:true});if(mine!==generation||ident!==current()||panel.hidden)return;
   invalidate();$('wikiVersion').value='';await load();status(job.status==='noop'?job.message:t('工作已排入佇列，可隨時停止。','Work queued. Stop at any time.'));
  }catch(e){if(mine===generation)status(e.message,true);}finally{busy=false;$('wikiStatus').classList.remove('wiki-working');$('wikiStatus').setAttribute('aria-busy','false');activity();}
 };
 $('wikiPause').onclick=async()=>{try{await api('configure',{instrument:current(),enabled:false});await poll();}catch(e){status(e.message,true);}};
 $('wikiExport').onclick=async()=>{if(!data)return;try{const result=await api('markdown?'+new URLSearchParams({instrument:data.instrument,version:data.version}));const url=URL.createObjectURL(new Blob([result.markdown],{type:'text/markdown;charset=utf-8'})),a=el('a');a.href=url;a.download=data.instrument.replace(':','-')+'-wiki.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}catch(e){status(e.message,true);}};
 let tipTimer;const hideTip=()=>{clearTimeout(tipTimer);$('wikiStartTip').hidden=true;$('wikiStart').removeAttribute('aria-describedby');};for(const event of ['mouseenter','focus'])$('wikiStart').addEventListener(event,()=>{clearTimeout(tipTimer);tipTimer=setTimeout(()=>{$('wikiStartTip').hidden=false;$('wikiStart').setAttribute('aria-describedby','wikiStartTip');},550);});for(const event of ['mouseleave','blur'])$('wikiStart').addEventListener(event,hideTip);$('wikiStart').addEventListener('keydown',e=>{if(e.key==='Escape')hideTip();});
 const layout=root.AtlasWikiLayout.init(panel,saveRuntime);
 for(const event of ['input','change'])for(const surface of [panel,dialog])surface.addEventListener(event,()=>{if(initialized)saveRuntime();});
 root.addEventListener('pagehide',saveRuntime);root.addEventListener('atlas-language',translate);preset();translate();appliedSettings=draftSettings();root.AtlasWiki={show,refresh:load,setResearch,filterTerm,selectNode:id=>{if(!data?.nodes.some(n=>n.id===id))return;focusGalaxy(id);details(data.nodes.find(n=>n.id===id));},graph:()=>graph,l1Busy:()=>lastJobs.some(j=>['queued','running'].includes(j.status)),classification:()=>data?.taxonomy};
 let chatRevision=0,chatFingerprint='';
 const wikiRuntime={
  state(){const scope=focusIds?[...focusIds]:selectedDetail?.id?[selectedDetail.id]:(graph?.graphData().nodes||[]).map(n=>n.id);const controls=['wikiLayer','wikiKind','wikiRelation','wikiAssessment','wikiVersion'].map(id=>({id,kind:'set',value:$(id).value,options:[...$(id).options].map(o=>({value:o.value,label:o.textContent})),disabled:$(id).disabled}));const state={surface:'wiki',layer:$('wikiLayer').value,research_run:researchRun?.id||null,research_question:researchRun?.bundle.lens.query||null,language:language(),instrument:current(),version:data?.version||0,dataset:JSON.stringify([current(),data?.version,range(),$('wikiLayer').value,researchRun?.id,data?.taxonomy?.revision_id,classStamp]),date_range:range(),scope_ids:scope,scope_kind:focusIds?'galaxy':selectedDetail?'node':'wiki',selected_node:selectedDetail,root_ids:focusRoot?[focusRoot]:[],counts:{loaded:data?.nodes.length||0,visible:graph?.graphData().nodes.length||0,scope:scope.length,edges:data?.edges.length||0},controls,busy:{wiki:lastJobs.some(j=>['queued','running'].includes(j.status))}};const fingerprint=JSON.stringify(state);if(fingerprint!==chatFingerprint){chatFingerprint=fingerprint;chatRevision++;}return {...state,revision:chatRevision};},
  data(){return {articles:(data?.nodes||[]).filter(n=>n.kind==='ArticleRevision'),nodes:data?.nodes||[],edges:(data?.edges||[]).map(e=>({...e,source:e.source.stable_id,target:e.target.stable_id})),histories:data?.histories||{}};},
  async act(action){if(action.kind==='read')return wikiRuntime.state();if(action.revision!==wikiRuntime.state().revision)throw Error('Wiki 已更新，請重新讀取狀態');if(action.kind==='select_article'){const n=data.nodes.find(n=>n.id===action.id);if(!n)throw Error('Unknown Wiki node');focusGalaxy(n.id);details(n);if(n.kind!=='ArticleRevision'&&n.layer!=='L2')await openViewpoint(n);}else if(action.kind==='set'&&wikiRuntime.state().controls.some(c=>c.id===action.id&&c.options.some(o=>o.value===String(action.value)))){const control=$(action.id);control.value=action.value;if(action.id==='wikiVersion')await selectVersion();else if(action.id==='wikiLayer')$(action.id).dispatchEvent(new Event('change'));else render();saveRuntime();}else throw Error('此 Wiki 操作不在允許清單');return wikiRuntime.state();}
 };
 root.AtlasWiki.runtime=wikiRuntime;
 root.AtlasWiki.chat=root.AtlasChatPanel?.mount({runtime:wikiRuntime,detail:$('wikiSide'),prefix:'wiki',title:'觀點詳情'});

})(globalThis);
