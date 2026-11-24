/* Independent Wiki surface. Display controls never start model work. */
(function(root){
 'use strict';
 const hooks=root.AtlasWikiContext;if(!hooks)return;
 const $=id=>document.getElementById(id),language=()=>root.AtlasI18n?.language()||'zh-Hant',t=(zh,en)=>language()==='en'?en:zh;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const termLabel=term=>root.AtlasI18n.termLabel(term);
 const palette={direct:'#7de3bd',indirect:'#7db6f2',low:'#e7b779',uncertain:'#bb9fe4'};
 const kindNames=()=>({ArticleRevision:t('新聞版本','News revision'),Claim:t('陳述','Claim'),Event:t('事件','Event'),Thesis:t('通用觀點 L1','General opinion L1'),CustomerOpinion:t('研究觀點 L2','Research opinion L2'),ArgumentBranch:t('論證分支 L2','Argument branch L2')});
 const categoryNames=()=>({direct:t('直接營運／財務','Direct operating / financial'),indirect:t('間接影響','Indirect influence'),low:t('低關聯／噪聲','Low relevance / noise'),uncertain:t('營運影響待釐清','Operating impact unclear')});
 const panel=el('section',undefined,'wiki-panel');panel.id='wikiPanel';panel.hidden=true;panel.dataset.ownI18n='true';
 panel.innerHTML=`<header class="wiki-header"><a href="#news" id="wikiBack"></a><h2>LLM Wiki</h2><button id="wikiExport"></button></header>
 <div class="wiki-layout"><aside id="wikiControls" class="wiki-controls">
 <label><span data-ui="saved"></span><select id="wikiSaved"></select></label>
 <label><span data-ui="instrument"></span><select id="wikiInstrument"></select></label>
 <div class="help-heading"><label id="wikiScopeHelpName" for="wikiScope" data-ui="scope"></label><button type="button" class="help-trigger" aria-labelledby="wikiScopeHelpName workbenchHelpWord" aria-describedby="wikiScopeHelp"></button></div><select id="wikiScope"><option value="global"></option><option value="loaded"></option><option value="focus"></option></select>
 <span id="wikiScopeHelp" class="help-tip" role="tooltip" hidden></span><p id="wikiSelection" class="wiki-note"></p><section id="wikiCoverage" class="wiki-coverage"></section><p id="wikiStatus" class="wiki-status" role="status"></p>
 <label><span data-ui="dates"></span><select id="wikiRange"><option value="month"></option><option value="quarter"></option><option value="all"></option><option value="custom"></option></select></label>
 <div id="wikiDates"><div class="wiki-pair"><label><span data-ui="start"></span><input id="wikiStartDate" type="date"></label><label><span data-ui="end"></span><input id="wikiEndDate" type="date"></label></div>
 <div class="wiki-dual"><div class="wiki-track"></div><input id="wikiRangeStart" type="range"><input id="wikiRangeEnd" type="range"></div><output id="wikiInterval"></output></div>
 <small id="wikiDateLock" class="wiki-note" hidden></small><section id="wikiSelectedCoverage" aria-live="polite" aria-atomic="true"></section>
 <label><span data-ui="operation"></span><select id="wikiOperation"><option value="update"></option><option value="review"></option></select></label>
 <div class="wiki-actions"><button id="wikiStart" class="wiki-primary" disabled></button><button id="wikiPause" hidden></button></div>
 <button type="button" id="wikiBrowse"></button><button type="button" id="wikiCompare"></button><div class="help-heading"><label id="wikiModelNoteName" for="wikiModel" data-ui="model"></label><button type="button" class="help-trigger" aria-labelledby="wikiModelNoteName workbenchHelpWord" aria-describedby="wikiModelNote"></button></div><select id="wikiModel"></select><span id="wikiModelNote" class="help-tip" role="tooltip" hidden></span>
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
 <div id="wikiResizeLive" class="wiki-resize wiki-resize-row" role="separator" tabindex="0" aria-orientation="horizontal" aria-label="調整進度區高度" aria-controls="wikiLive"></div><div id="wikiResizeChanges" class="wiki-resize wiki-resize-row" role="separator" tabindex="0" aria-orientation="horizontal" aria-label="調整版本變更高度" aria-controls="wikiVersionInfo" hidden></div><details id="wikiVersionInfo" class="wiki-insights"></details><div id="wikiCounts" class="wiki-counts"><span id="wikiTotals"></span>
  <span id="wikiGroups" class="help-heading" hidden><span id="wikiGroupLabel"></span><button type="button" class="help-trigger" aria-labelledby="wikiGroupLabel workbenchHelpWord" aria-describedby="wikiGroupHelp"></button></span>
  <span id="wikiGroupHelp" class="help-tip" role="tooltip" hidden></span><div id="wikiCountDetails"></div></div>
 <div class="wiki-graph-stage"><div id="wikiCanvas" class="wiki-canvas"></div><div id="wikiEmpty" class="wiki-empty"></div><button type="button" id="wikiTimelineLauncher" class="tool-launcher" aria-controls="wikiTimelineTool" hidden></button></div>
 <div id="wikiResizeTimeline" class="wiki-resize wiki-resize-row" role="separator" tabindex="0" aria-orientation="horizontal" aria-controls="wikiLower wikiCanvas"></div><div id="wikiLower" class="wiki-lower"><section id="wikiTimelineTool" aria-labelledby="wikiTimelineTitle"><div class="wiki-timeline-heading">
 <button type="button" id="wikiTimelineGrip"><span id="wikiTimelineTitle"></span></button><button type="button" id="wikiTimelineReset"></button><button type="button" id="wikiTimelineFloat"></button><button type="button" id="wikiTimelineFold"></button></div>
 <div id="wikiTimeline" class="wiki-timeline"></div></section><details id="wikiInsights" class="wiki-insights"></details></div></main>
 <div id="wikiResizeRight" class="wiki-resize" role="separator" tabindex="0" aria-orientation="vertical" aria-controls="wikiSide"></div><aside id="wikiSide" class="wiki-detail"><section id="wikiDetail"></section></aside></div>`;
 document.body.append(panel);
 const dialog=el('dialog',undefined,'wiki-settings');dialog.id='wikiSettings';dialog.dataset.ownI18n='true';dialog.innerHTML=`<form method="dialog"><button id="wikiSettingsClose">×</button></form><h2 id="wikiSettingsTitle"></h2><label><span id="wikiLanguageLabel"></span><select id="wikiLanguages"><option value="both"></option><option value="zh-Hant">繁體中文</option><option value="en">English</option></select></label><div class="help-heading"><label for="wikiStrategy" id="wikiStrategyLabel"></label><button type="button" class="help-trigger" aria-labelledby="wikiStrategyLabel workbenchHelpWord" aria-describedby="wikiStrategyNote"></button></div><select id="wikiStrategy"><option value="lexical"></option><option value="chronological"></option><option value="root"></option><option value="fusion"></option></select><span id="wikiStrategyNote" class="help-tip" role="tooltip" hidden></span><p id="wikiStrategyState" class="wiki-note"></p><div class="help-heading"><label for="wikiEvidenceSize" id="wikiEvidenceLabel"></label><button type="button" class="help-trigger" aria-labelledby="wikiEvidenceLabel workbenchHelpWord" aria-describedby="wikiEvidenceNote"></button></div><select id="wikiEvidenceSize"><option>5</option><option>10</option><option>15</option><option>20</option></select><span id="wikiEvidenceNote" class="help-tip" role="tooltip" hidden></span><label><input type="checkbox" id="wikiVix"><span id="wikiVixLabel"></span></label><div class="help-heading"><label for="wikiWorkers" id="wikiWorkersLabel"></label><button type="button" class="help-trigger" aria-labelledby="wikiWorkersLabel workbenchHelpWord" aria-describedby="wikiWorkersNote"></button></div><select id="wikiWorkers"><option>1</option><option>3</option><option>5</option><option>10</option></select><span id="wikiWorkersNote" class="help-tip" role="tooltip" hidden></span><div class="wiki-settings-actions"><span id="wikiApplyStatus" role="status"></span><button id="wikiApply" class="wiki-primary" hidden>Apply</button></div>`;document.body.append(dialog);
 const open=el('button','LLM Wiki');open.id='modeWiki';$('modeTimeline').after(open);
 let data=null,info=null,graph=null,plan=null,busy=false,models=[],pollTimer=null,previewTimer=null,generation=0,request=0,previewSerial=0;
 let catalogAt=0,catalogPending=null,polling=false,showPending=null,loading=0,pollError=null;const cache=root.AtlasWikiCache.create(api);
 let displayedEpoch=null,displayedKey=null,openEpoch=0,warmTimer=null,warmKey=null,warmAt=0;
 const savedViews=new Map();
 let renderedWiki=null;
 let fitPending=false,fitKey='';
 let baseData=null,researchRun=null,reveal=Infinity,revealTimer=null,hoverNode=null,glow=null,classStamp='';
 let workerExpanded=false;
 let lastJobs=[],lastConfig={},lastCoverage=null,selectedDetail=null,selectedEdge=false;
 let latestPublishedVersion=0,graphLoadError=null;
 let appliedSettings=null,rootSelection=null,graphUniverse=null,graphSettings=null,detailRequest=0;
 const treeOpen=new Set();let initialized=false,restoringUI=false,viewReload=null,focusRoot=null,focusIds=null;
 const runtimeKeys=['wikiLayer','wikiScope','wikiModel','wikiOperation','wikiRange','wikiStartDate','wikiEndDate','wikiRangeStart','wikiRangeEnd','wikiVersion','wikiKind','wikiRelation','wikiBudget','wikiAssessment','wikiLanguages','wikiEvidenceSize','wikiStrategy','wikiWorkers','wikiContinuous'];
 const topicNames=()=>({revenue:t('營收與獲利','Revenue and earnings'),operations:t('生產與營運','Production and operations'),costs:t('成本與投資','Costs and investment'),market:t('市場與股價','Market and price'),trading:t('交易觀點','Trading views'),other:t('其他／待分類','Other / unclassified')});
 const copy=(node)=>{const fields=node.translations?.[language()];return fields?{...node,title:fields.title||node.title,summary:fields.summary||node.summary,rationale:fields.rationale||node.rationale,assessment:{...node.assessment,rationale:fields.rationale}}:node;};
 const status=(text,error=false,working=false)=>{$('wikiStatus').textContent=text;$('wikiStatus').classList.toggle('error',error);$('wikiStatus').classList.toggle('wiki-working',working);$('wikiStatus').setAttribute('aria-busy',String(working));};
 const current=()=>($('wikiSaved').value||$('wikiInstrument').value).trim().toUpperCase();
 const day=d=>d.toISOString().slice(0,10),stamp=d=>Date.parse(d+'T00:00:00Z')/86400000;
 const option=(name,value)=>new Option(name,value);
 function choices(id,items){const node=$(id),old=node.value;node.replaceChildren(...items.map(([v,n])=>option(n,v)));if([...node.options].some(o=>o.value===old))node.value=old;}
 const ui={layer:['觀點層','Opinion layer'],saved:['已建立的 Wiki','Saved Wikis'],instrument:['股票識別','Instrument'],scope:['來源範圍','Evidence scope'],dates:['整理日期（UTC）','News dates (UTC)'],start:['自定義時間起始','Custom start date'],end:['自定義時間結束','Custom end date'],operation:['維護方式','Operation'],model:['L1／L2 輕量模型與思考深度','L1/L2 lightweight model and reasoning depth'],continuous:['持續檢查這個日期範圍的新證據','Watch new evidence in this fixed date range'],version:['版本','Version'],viewStart:['版本內新聞起日（UTC）','News from (UTC)'],viewEnd:['版本內新聞迄日（UTC）','News through (UTC)'],kind:['節點','Nodes'],relation:['關係','Relations'],budget:['渲染上限','Render budget'],category:['觀點分類','Classification']};
 const relationLabels={
  SUPPORTS:['支持','Supports'],CONTRADICTS:['反證','Contradicts'],UPDATES:['修訂','Updates'],EXTENDS:['延伸','Extends'],
  DEPENDS_ON:['依賴','Depends on'],RELATED_TO:['相關','Related to'],TEMPORALLY_PRECEDES:['時間先於','Precedes'],
  DERIVED_FROM:['衍生自 L1','Derived from L1'],ARGUMENT_MEMBER:['論證分組','Argument membership']
 };
 const relationName=type=>relationLabels[type]?t(...relationLabels[type]):type;
 function translate(){
  timelineWindow.labels();
  panel.querySelectorAll('[data-ui]').forEach(n=>n.textContent=t(...ui[n.dataset.ui]));
  const labels={wikiVixLabel:['L1 對照 VIX（同股新聞庫，回看 7 天）','Compare VIX in L1 (this stock’s news, 7-day lookback)'],wikiWorkersLabel:['並行 worker 上限','Concurrent worker limit'],wikiWorkersNote:['每個 worker 分領新聞樹。更多 worker 提高同時用量，實際速度受模型限流及樹大小影響。','Each worker owns a news tree. More workers increase concurrent usage; speed depends on model limits and tree size.'],wikiCompare:['觀點比對','Compare viewpoints'],wikiBrowse:['檢視完整 L1 圖譜','Browse full L1 graph'],wikiBack:['← 新聞圖譜','← News graph'],wikiExport:['匯出 Markdown','Export Markdown'],wikiStart:['開始整理','Start maintenance'],wikiSettingsTitle:['Wiki 設定','Wiki settings'],wikiLanguageLabel:['生成與保存語系','Generate and store languages'],wikiEvidenceLabel:['每次推論的新聞篇數','Articles per reasoning call'],wikiStrategyLabel:['整理時如何選取證據','How to group evidence'],wikiEvidenceNote:['每組 5／10／15／20 篇；Graph 自動覆蓋模式依整棵樹的篇數。沒有每日上限，可隨時停止。','5 / 10 / 15 / 20 per group; Graph coverage uses each complete tree size. No daily limit; stop any time.']};
  for(const [id,text] of Object.entries(labels))$(id).textContent=t(...text);
  choices('wikiLayer',[['L1',t('L1 通用觀點','L1 general viewpoints')],['L2',t('L2 客製化觀點','L2 custom viewpoints')],['both','L1 + L2']]);
  choices('wikiScope',[['global',t('全局：目前查詢與 DB','Global: current queries and DB')],['loaded',t('目前已載入新聞','Loaded news')],['focus',t('目前焦點與關聯節點','Focused roots and related nodes')]]);
  choices('wikiRange',[['month',t('最近一個月','Past month')],['quarter',t('最近三個月','Past three months')],['all',t('全部日期','All dates')],['custom',t('自訂範圍','Custom range')]]);
  choices('wikiOperation',[['update',t('補新證據並檢視相依觀點','Add missing evidence and revisit dependents')],['review',t('重新檢視既有觀點','Re-evaluate existing viewpoints')]]);
  choices('wikiKind',[['',t('全部類型','All types')],...Object.entries(kindNames())]);
  choices('wikiRelation',[['',t('全部關係','All relations')],...Object.keys(relationLabels).map(v=>[v,relationName(v)])]);
  classificationChoices();
  choices('wikiStrategy',[['lexical',t('詞彙相關','Lexical relevance')],['chronological',t('時間順序','Chronological')],['root',t('Graph 強關聯 root','Graph root neighborhood')],['fusion',t('多來源融合','Multi-source fusion')]]);
  $('wikiLanguages').options[0].textContent=t('繁體中文 ＋ English（預設）','Traditional Chinese + English (default)');
  $('wikiStartTip').textContent=t('顯示篩選不會重算 Wiki。按下開始後，選取新聞的標題、摘要及相關舊觀點會交給登入模型處理；引用保留原文，修訂保留原版。你可以隨時停止。已消耗的用量不會退回。','Display filters never recompute the Wiki. Starting sends selected titles, summaries and related prior viewpoints to your signed-in model. Original quotes and previous versions are retained. Stop any time; consumed usage cannot be refunded.');
  $('wikiRangeStart').setAttribute('aria-label',t('選取起點','Selected start'));$('wikiRangeEnd').setAttribute('aria-label',t('選取終點','Selected end'));
  $('wikiResizeLeft').setAttribute('aria-label',t('調整左側寬度','Resize left panel'));$('wikiResizeRight').setAttribute('aria-label',t('調整右側寬度','Resize right panel'));$('wikiResizeTimeline').setAttribute('aria-label',t('調整圖表高度','Resize chart height'));$('wikiResizeChanges').setAttribute('aria-label',t('調整版本變更高度','Resize version changes'));root.AtlasUI.labelIcon($('wikiSettingsClose'),'close',t('關閉設定','Close settings'));
  $('wikiGroupHelp').textContent=t('目前顯示的節點依已驗證的連線分群。變更篩選或渲染上限可能改變群數。','Groups follow validated edges between the visible nodes. Filters and the render limit can change the count.');
  $('wikiScopeHelp').textContent=t('全局範圍會查詢此股票的新聞資料庫。新聞樹大小不同，完成比例依棵數計算。','Global scope also reads the news database for this stock. Progress counts completed trees, which can contain different numbers of articles.');
  $('wikiModelNote').textContent=t('思考深度取自目前登入的模型目錄；更換模型不重抽已完成新聞。','Reasoning choices come from your model catalog. Changing model reuses completed evidence.');
  strategyNote();modelChoices();savedChoices();versionChoices();selection();sliderLabel();if(rangeCounts)paintCounts();activity();render();if(selectedDetail)details(selectedDetail,selectedEdge);
  if(!panel.hidden)$('relationOpen').textContent=t('Wiki 設定','Wiki settings');
 }
 function syncGraphUniverse(news=hooks.selection('global')){if((!news.search?.instrument||news.search.instrument===current())&&news.graph_universe?.articles?.length&&news.graph_universe.ticker===current().split(':')[1]){graphUniverse=news.graph_universe;graphSettings=news.graph_settings;}}
 function strategyNote(){const notes={lexical:['先依詞彙重疊組合新聞，再找相關舊觀點。','Group by word overlap, then retrieve related existing viewpoints.'],chronological:['依新聞日期由早至晚，逐組建立脈絡。','Process news oldest first in adjacent date groups.'],root:['從完整新聞圖譜自動採樣 root，直到涵蓋此日期範圍全部新聞；跳過重複覆蓋，包含未渲染與孤立節點。整棵樹送入模型，區間外成員僅作脈絡；超出輸入容量才分段。','Automatically sample roots over the complete News graph until every article in the Wiki date range is covered, including unrendered and isolated nodes. Skip redundant coverage. Send the whole tree; outside-range members are context. Split only for input capacity.'],fusion:['優先相關但不同來源的新聞，保留分歧及各自的證據邊界。','Prefer related news from different sources; preserve disagreements and their evidence boundaries.']};$('wikiStrategyNote').textContent=t(...notes[$('wikiStrategy').value])+' '+t('所有方式共用同一觀點庫；切換不會清空已整理內容。','All methods share one opinion store; switching keeps completed work.');$('wikiEvidenceSize').disabled=$('wikiStrategy').value==='root';$('wikiWorkers').disabled=$('wikiStrategy').value!=='root'||$('wikiOperation').value==='review';$('wikiStrategyState').textContent=$('wikiStrategy').value==='root'?(graphUniverse?.articles?.length?t(`新聞圖譜完整範圍：${graphUniverse.articles.length} 篇。無需手動點選。`,`Full News universe: ${graphUniverse.articles.length} articles. No manual selection needed.`):t('請先載入此股票的新聞圖譜。','Load the News graph for this stock first.')):'';dirtySettings();}

 async function api(path,body){
  const ident=body&&(body.instrument||current());
  const r=await fetch('/api/wiki/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const value=await r.json();if(!r.ok)throw Error(value.error||t('Wiki 請求失敗','Wiki request failed'));
  if(ident&&['jobs','apply','resume','stop','cancel','configure'].includes(path))cache.invalidateState(ident);
  return value;
 }
 const pendingActions=new Set();let jobStateEpoch=0;
 async function buttonAction(button,label,work,success=''){
  const ident=current(),key=button.id?ident+':'+button.id:button,mine=generation;
  if(button.disabled||pendingActions.has(key))return;
  pendingActions.add(key);const original=button.textContent;
  button.disabled=true;button.textContent=label;button.classList.add('wiki-working');button.setAttribute('aria-busy','true');status(label,false,true);
  try{await work();if(success&&ident===current()&&mine===generation)status(success);}
  catch(e){if(ident===current()&&mine===generation)status(e.message,true);}
  finally{if(ident===current()&&$('wikiStatus').textContent===label)status('');pendingActions.delete(key);button.disabled=false;button.textContent=original;button.classList.remove('wiki-working');button.setAttribute('aria-busy','false');}
 }
 function modelChoices(){const old=$('wikiModel').value;choices('wikiModel',models.flatMap(m=>(m.reasoning?.length?m.reasoning:[{reasoningEffort:'low'}]).map(r=>{const effort=r.reasoningEffort||r.effort||r;return [m.id+'|'+effort,m.name+' · '+effort];})));if([...$('wikiModel').options].some(o=>o.value===old))$('wikiModel').value=old;}
 function instrumentChoices(preferred=current()){
  const saved=$('wikiSaved').value;
  choices('wikiInstrument',saved?[[saved,saved]]:[['',t('選擇已有新聞的股票 DB','Select a news database')],...(info?.news_databases||[]).map(s=>[s.instrument,`${s.instrument} · ${s.articles}`])]);
  $('wikiInstrument').value=saved||preferred;$('wikiInstrument').disabled=!!saved;
 }
 function savedChoices(preserveChoice=false){const old=$('wikiSaved').value,ident=current();choices('wikiSaved',[['',t('建立新的股票 Wiki','Create a stock Wiki')],...(info?.instruments||[]).map(s=>[s.instrument,s.instrument+' · v'+s.version])]);if(data&&!Array.from($('wikiSaved').options).some(o=>o.value===data.instrument))$('wikiSaved').add(option(data.instrument,data.instrument));$('wikiSaved').value=preserveChoice?old:old||data?.instrument||'';instrumentChoices(ident);}

 function versionChoices(){choices('wikiVersion',[['',t('最新版本','Latest version')],...(data?.versions||[]).slice(0,10).map(v=>[String(v.version),'v'+v.version+' · '+new Date(v.created_at).toLocaleString(language())])]);}
 function range(){if($('wikiRange').value==='all')return null;return {start:$('wikiStartDate').value,end:$('wikiEndDate').value};}
 function sliderLabel(){if(!$('wikiRangeStart').value)return;const r=range();$('wikiInterval').textContent=r?r.start+' → '+r.end:t('全部日期','All dates');const a=Number($('wikiRangeStart').min),b=Number($('wikiRangeStart').max),den=b-a||1;document.querySelector('.wiki-dual').style.setProperty('--from',100*(Number($('wikiRangeStart').value)-a)/den+'%');document.querySelector('.wiki-dual').style.setProperty('--to',100*(Number($('wikiRangeEnd').value)-a)/den+'%');}
 function lastYear(end){const start=new Date(end);start.setUTCFullYear(start.getUTCFullYear()-1);return start;}
 function sliders(){
  const custom=$('wikiRange').value==='custom';
  $('wikiDates').hidden=!custom;
  const start=$('wikiStartDate').value,end=$('wikiEndDate').value;
  const a=stamp(start),b=stamp(end),today=new Date();
  if(!Number.isFinite(a)||!Number.isFinite(b)||a>b)return;
  for(const id of ['wikiRangeStart','wikiRangeEnd']){
   const input=$(id);input.min=Math.min(a,stamp(day(lastYear(today))));input.max=Math.max(b,stamp(day(today)));
   input.step=1;input.value=id==='wikiRangeStart'?a:b;
  }
  sliderLabel();
 }
 function datesFromHandles(){
  for(const [date,handle] of [['wikiStartDate','wikiRangeStart'],['wikiEndDate','wikiRangeEnd']])
   $(date).value=day(new Date(Number($(handle).value)*86400000));
  sliderLabel();
 }
 function preset(){
  const mode=$('wikiRange').value,end=new Date(),start=mode==='custom'?lastYear(end):new Date(end);
  if(mode!=='custom')start.setUTCMonth(start.getUTCMonth()-(mode==='quarter'?3:1));
  $('wikiStartDate').value=day(start);$('wikiEndDate').value=day(end);sliders();
 }
 function validDates(){
  return $('wikiRange').value!=='custom'||($('wikiStartDate').value&&$('wikiEndDate').value&&$('wikiStartDate').value<=$('wikiEndDate').value);
 }
 function selection(selected=hooks.selection($('wikiScope').value)){if((selected.search?.instrument&&selected.search.instrument!==current())||selected.search?.ticker!==current().split(':')[1]||!$('wikiSaved').value)selected={articles:[],sources:[],search:{ticker:current().split(':')[1]}};selected.graph_selection=rootSelection||lastConfig.graph_selection||selected.graph_selection;if(![1,3,5,7].includes(selected.price_horizon))selected.price_horizon=lastConfig.price_horizon||3;$('wikiSelection').textContent=t(`已載入 ${selected.articles.length} 篇`,`Loaded ${selected.articles.length} articles`);return selected;}
 function meter(parent,label,value,total){if(!total){parent.append(el('small',t('此範圍沒有新聞','No articles in this range')));return;}const box=el('div',undefined,'wiki-meter');box.append(el('span',`${label} · ${value}/${total} · ${(100*value/total).toFixed(2)}%`));const bar=el('progress');bar.max=total;bar.value=value;bar.setAttribute('aria-label',label);box.append(bar);parent.append(box);}
 function tokenText(usage){return `${usage?.input_tokens||0} ${t('輸入','in')} / ${usage?.output_tokens||0} ${t('輸出','out')}`;}
 function miningIcon(){const span=el('span',undefined,'wiki-worker');span.setAttribute('aria-hidden','true');span.innerHTML=`<svg viewBox="0 0 96 86" focusable="false"><use href="/knowledge-mining.svg#base"/><use class="wiki-scan" href="/knowledge-mining.svg#scan"/><use class="wiki-signal" href="/knowledge-mining.svg#signal"/></svg>`;return span;}
 const dateControls=['wikiRange','wikiStartDate','wikiEndDate','wikiRangeStart','wikiRangeEnd'];
 const stoppingStocks=new Set();
 const isActive=j=>j.status==='queued'||j.status==='running';
 function lockDates(locked,confirmed){
  if(confirmed&&Object.hasOwn(lastConfig,'date_range')){
   const saved=lastConfig.date_range;
   if(!saved){$('wikiRange').value='all';sliders();}
   else if($('wikiRange').value==='all'||range()?.start!==saved.start||range()?.end!==saved.end){
    $('wikiRange').value='custom';$('wikiStartDate').value=saved.start;$('wikiEndDate').value=saved.end;sliders();
   }
   sliderLabel();
  }
  for(const id of dateControls)$(id).disabled=locked;
  $('wikiDateLock').hidden=!locked;
  $('wikiDateLock').textContent=t('本次整理範圍已固定。停止維護後可更改日期。','Maintenance dates are fixed. Stop maintenance to change them.');
 }
 function workUnits(job){
  const p=job.payload;
  return {total:p.total??p.revisions?.length,done:job.done??p.done??0};
 }
 function remainingMs(job){
  const {done,total}=workUnits(job);
  if(!Number.isFinite(total))return null;
  if(done>=total)return 0;
  const elapsed=Date.now()-Date.parse(job.created_at);
  return done>0&&elapsed>0?elapsed*(total-done)/done:null;
 }
 function jobProgress(content,job){
  const {done,total}=workUnits(job);
  if(!total)return;
  meter(content,job.payload.operation==='classify_l1'?t('本次分類觀點','Opinions classified this job'):t('本次已整理新聞','Articles processed this job'),done,total);
  const estimates=lastJobs.filter(isActive).map(remainingMs);
  if(estimates.every(value=>value!==null)){
   const minutes=Math.ceil(estimates.reduce((sum,ms)=>sum+ms,0)/60000);
   if(minutes>0)content.append(el('small',t(`目前已排定的整理約剩 ${minutes} 分鐘（依平均速度估算）`,`About ${minutes} min left for scheduled maintenance at the observed average rate`)));
  }else{
   const ms=remainingMs(job);
   if(ms>0){
    const minutes=Math.ceil(ms/60000);
    content.append(el('small',t(`目前工作約剩 ${minutes} 分鐘，其餘排定工作仍在估算`,`About ${minutes} min for this job. Estimating the rest of the queue`)));
   }else content.append(el('small',job.status==='queued'?t('排隊中，等待可用的處理速度估算','Queued, waiting for a rate estimate'):t('首批完成後估算剩餘時間','Estimating remaining time after the first batch')));
  }
 }
 async function stopMaintenance(){
  const ident=current();if(!ident||stoppingStocks.has(ident))return;
  stoppingStocks.add(ident);activity();status(t('正在停止維護…','Stopping maintenance…'),false,true);
  try{
   const result=await api('stop',{instrument:ident});
   if(ident!==current())return;
   jobStateEpoch++;request++;
   lastJobs=lastJobs.map(j=>result.cancelled_jobs.includes(j.id)?{...j,status:'cancelled'}:j);
   lastConfig={...lastConfig,enabled:false,catch_up:false};$('wikiContinuous').checked=false;
   schedulePreview();await poll();
   if(ident===current())status(t('整理與持續監看已停止，已發布版本可繼續檢視。','Maintenance and watching stopped. Published versions are available.'));
  }catch(error){if(ident===current())status(error.message,true);}
  finally{stoppingStocks.delete(ident);activity();}
 }
 function scopeProgress(parent){
  if(!lastCoverage||lastCoverage.unavailable)return;
  const docs=lastCoverage.documents;
  if(docs?.total)meter(parent,t('文件原文已審視','Document passages reviewed'),docs.done,docs.total);
  const trees=lastCoverage.trees;
  if(trees?.total){meter(parent,t('已完成新聞樹','News trees completed'),trees.done,trees.total);parent.append(el('small',t(`文章覆蓋 ${lastCoverage.scope_done}/${lastCoverage.scope_total} 篇`,`Article coverage ${lastCoverage.scope_done}/${lastCoverage.scope_total}`)));}
  else if(lastCoverage.scope_total)meter(parent,t('已整理新聞','Articles processed'),lastCoverage.scope_done,lastCoverage.scope_total);
 }
 function sdkStage(stage){
  const labels={
   catalog:t('檢查模型設定','Checking model selection'),sdk_starting:t('正在啟動 SDK','Starting SDK'),
   thread_started:t('已建立SDK 工作階段，等候回合開始','SDK thread created, waiting for turn'),
   awaiting_model:t('模型回合已開始，等候首次輸出事件','Turn started, waiting for first output event'),
   reasoning_event:t('已收到推理階段事件','Reasoning activity received'),answer_event:t('已收到回答事件','Answer activity received'),
   turn_completed:t('模型已交回結果','Model turn completed'),sdk_reconnecting:t('SDK 正在重新連線','SDK reconnecting'),
   sdk_notice:t('SDK 回報連線或服務訊息','SDK reported a service notice')
  };
  return labels[stage];
 }
 function treeFailureText(failure){
  const timeout=failure.error?.includes('hard limit')?t('已達單次 20 分鐘上限','20-minute call deadline reached'):
   failure.error?.includes('without new model output')?t('10 分鐘沒有新的模型輸出事件','No new model output event for 10 minutes'):t('模型呼叫逾時','Model call timed out');
  const reasons={timeout,transport_timeout:t('本機橋接未及時回應','Local bridge response timed out'),
   transport_error:t('本機橋接連線中斷','Local bridge connection interrupted'),rate_limit:t('模型服務限制請求頻率','Model service rate limited this request'),invalid_response:t('模型回傳格式無效','Invalid model response'),
   validation:t('提案未通過驗證','Proposal failed validation'),revision_conflict:t('另一棵樹已先修訂同一觀點','Another tree already revised this opinion'),
   tool_use:t('模型嘗試使用未允許的工具','Model attempted an unexpected tool')};
  return [failure.root_id?.startsWith('doc-')?t('文件原文','Document passage'):t(`樹 #${failure.tree} · 第 ${failure.part} 段`,`Tree #${failure.tree} · segment ${failure.part}`),
   reasons[failure.code]||failure.error,sdkStage(failure.sdk_stage)].filter(Boolean).join(' · ');
 }
 function workerDetails(job){
  const details=el('details',undefined,'wiki-workers');details.id='wikiWorkerProgress';details.dataset.job=job.id;details.open=workerExpanded;
  const p=job.payload,states=p.workers_state||{},count=p.workers||1;
  details.append(el('summary',t(`查看 ${count} 個 worker 的進度`,`Inspect ${count} workers`)));
  details.addEventListener('toggle',()=>{if(details.isConnected)workerExpanded=details.open;});
  const names={context:t('讀取新聞與觀點','Reading evidence and viewpoints'),compiling:t('分析中','Analyzing'),repairing:t('修正提案','Repairing proposal'),publishing:t('保存中','Saving'),published:t('已保存分段','Segment saved'),reused:t('沿用已存分段','Reused saved segment'),waiting_context:t('等待共用觀點更新','Waiting for a shared opinion'),completed:t('本樹完成','Tree completed'),idle:t('等待分派','Waiting for a tree')};
  for(let slot=1;slot<=count;slot++){
   const w=states[slot]||{},row=el('div',undefined,'wiki-worker-row');row.dataset.worker=String(slot);
   const label=el('strong',`Worker ${slot} · `+(w.status==='failed'?t('處理失敗','Failed'):w.status==='completed'?t('已完成','Completed'):['failed','interrupted','cancelled'].includes(job.status)?t('已停止','Stopped'):names[w.stage]||t('等待分派','Waiting for a tree')));
   row.append(label,el('small',w.model||p.model));
   if(w.root_id?.startsWith('doc-')){
    row.append(el('small',t('文件原文','Document passage')+' · '+w.title));
    meter(row,t('已保存分段','Segments saved'),w.completed_parts||0,w.parts||1);
   }else if(w.root_id){const tree=p.graph_selection?.trees?.find(x=>x.root_id===w.root_id),button=el('button',t(`查看新聞樹 #${w.tree}`,`View news tree #${w.tree}`),'wiki-root-link');button.type='button';button.dataset.root=w.root_id;button.disabled=!tree||!hooks.showRoot;button.onclick=()=>{try{hooks.showRoot({instrument:current(),tree,group:w.tree,groups:w.total_trees});hide();}catch(error){status(error.message,true);}};row.append(button,el('small',tree?.title||w.title));
    meter(row,t('本樹已保存分段','Tree segments saved'),w.completed_parts||0,w.parts||1);
    row.append(el('small',t(`${w.targets} 篇目標 · 含脈絡 ${w.context_articles} 篇`,`${w.targets} targets · ${w.context_articles} articles with context`)));
   }else if(p.group_info&&slot===1){row.append(el('small',t('舊工作仍由單一 worker 執行；下次開始使用新設定。','Legacy work uses one worker; new settings apply on the next start.')));}
   if(w.sdk_stage&&w.status==='running'&&job.status==='running'){
    const quiet=w.sdk_quiet_minutes;
    row.append(el('small',[sdkStage(w.sdk_stage),quiet>0?t(`距上次事件 ${quiet} 分鐘`,`${quiet} min since last event`):null].filter(Boolean).join(' · ')));
   }
   if(w.error)row.append(el('small',w.error_code?treeFailureText({...w,code:w.error_code}):w.error,'error'));
   details.append(row);
  }
  return details;
 }
 let liveStamp='',coverageStamp='';
 function activity(){
  const active=lastJobs.find(j=>j.status==='running')||lastJobs.find(isActive),running=active?.status==='running',waiting=!!active||!!(lastConfig.catch_up&&(lastCoverage?.scope_pending||lastCoverage?.documents?.pending)>0),box=$('wikiLive');const offline=box.dataset.state==='offline';box.dataset.state=running?'running':waiting?'queued':['failed','interrupted'].includes(lastJobs[0]?.status)?'failed':(lastCoverage?.scope_pending||lastCoverage?.documents?.pending)?'idle':'complete';
  box.classList.toggle('wiki-parallel',!!active?.payload.workers_state);
  const stamp=JSON.stringify([current(),language(),waiting,latestPublishedVersion,data?.nodes.length,graphLoadError,
   lastCoverage,plan?.usage,lastJobs.map(j=>[j.id,j.status,j.updated_at,j.done,j.error,j.payload.stage,j.payload.done,j.payload.workers_state]),
   active?Math.floor(Date.now()/60000):0]);
  if(offline||stamp!==liveStamp||!box.querySelector('#wikiPublishedResult')){
   paintLivePanel(box,active,running,waiting);
   liveStamp=stamp;
  }
  $('wikiStart').classList.toggle('wiki-working',busy||waiting);$('wikiStart').setAttribute('aria-busy',String(busy||waiting));
  $('wikiStart').textContent=busy?t('準備整理…','Preparing…'):waiting?t('整理中…','Processing…'):lastCoverage?t('繼續整理','Continue processing'):t('開始整理','Start processing');
  $('wikiStart').disabled=!validDates()||busy||waiting||loading>0||!info?.writable||!$('wikiModel').value||!current();const maintained=!!active||!!lastConfig.enabled||!!lastConfig.catch_up;
  const stopping=stoppingStocks.has(current());
  $('wikiPause').hidden=!maintained;
  for(const button of [$('wikiPause'),box.querySelector('#wikiStop')].filter(Boolean)){
   const label=stopping?t('正在停止…','Stopping…'):t('停止維護','Stop maintenance');if(button.textContent!==label)button.textContent=label;
   button.disabled=stopping||busy;button.classList.toggle('wiki-working',stopping);button.setAttribute('aria-busy',String(stopping));button.onclick=stopMaintenance;
  }
  lockDates(busy||maintained||stopping,maintained);
  $('wikiContinuous').disabled=busy||maintained||stopping||$('wikiOperation').value==='review';
  if(maintained)$('wikiContinuous').checked=!!lastConfig.enabled;
  const canRetryWhileWatching=lastConfig.strategy==='root'&&lastConfig.enabled&&!active&&!lastConfig.catch_up&&(lastCoverage?.scope_pending||lastCoverage?.documents?.pending)>0;
  if((maintained&&!canRetryWhileWatching)||stopping)$('wikiStart').disabled=true;
  const scopeStamp=JSON.stringify([language(),lastCoverage]);
  if(scopeStamp===coverageStamp)return;
  coverageStamp=scopeStamp;
  const coverage=$('wikiCoverage');coverage.replaceChildren();
  if(lastCoverage){if(lastCoverage.unavailable)coverage.append(el('p',lastCoverage.error));else{const savedDates=lastCoverage.date_range;coverage.append(el('small',t('已套用範圍 · ','Applied range · ')+(savedDates?savedDates.start+' → '+savedDates.end:t('全部日期','All dates'))));scopeProgress(coverage);const store=el('details');store.append(el('summary',t('資料庫','Database')),el('p',lastCoverage.storage,'wiki-storage'));coverage.append(store);}}
 }
 function paintLivePanel(box,active,running,waiting){
  const labels={compiling:t('LLM 正在梳理證據與相依觀點','LLM is analyzing evidence and dependent viewpoints'),repairing:t('正在修正未通過驗證的提案','Repairing a proposal that failed validation'),publishing:t('正在核對引用並保存版本','Checking citations and saving a version')};
  const latestFailure=!waiting&&['failed','interrupted'].includes(lastJobs[0]?.status)?lastJobs[0]:null;
  const title=latestFailure?t('前次整理已停止','Previous maintenance stopped'):active?.payload.operation==='classify_l1'?t('LLM 正在補足通用觀點分類','LLM is classifying existing L1 opinions'):running?labels[active.payload.stage]||labels.compiling:waiting?t('等待背景整理開始','Waiting for background work'):(lastCoverage?.scope_pending||lastCoverage?.documents?.pending)?t('尚有來源待整理，模型目前沒有運行','Evidence pending; model is idle'):t('目前沒有進行中的整理','No active work');
  const worker=box.querySelector('.wiki-worker')||miningIcon(),existingStop=box.querySelector('#wikiStop');const retainedStop=existingStop?.dataset.jobId===active?.id?existingStop:null;if(!worker.isConnected)box.append(worker);if(existingStop&&!retainedStop)existingStop.remove();const content=el('div',undefined,'wiki-live-content');content.append(el('strong',title));
  scopeProgress(content);
  if(active){const p=active.payload;if(p.operation==='classify_l1'||!lastCoverage?.trees)jobProgress(content,active);else content.append(workerDetails(active));if(!p.workers_state&&p.operation!=='classify_l1'){content.append(el('small',t('目前方法：','Current method: ')+({lexical:t('詞彙相關','Word overlap'),chronological:t('時間順序','Chronological'),root:t('Graph 全範圍 root 覆蓋','Graph root coverage'),fusion:t('多來源融合','Source fusion')})[p.strategy||'lexical']));content.append(el('small',p.model),el('small',(p.operation==='review'?t('↻ 重新檢視觀點','↻ Re-evaluating viewpoints'):t('✧ 新證據與觀點更新','✧ New evidence and viewpoint updates'))+' · '+(p.current_date?.slice(0,10)||'—')),el('p',p.current_title||t('準備證據…','Preparing evidence…'),'wiki-current-title'));if(!p.workers_state&&p.group_info?.groups){const info=p.group_info,tree=p.graph_selection?.trees?.find(x=>x.root_id===info.root_id),line=el('div',undefined,'wiki-root-progress');const link=el('button',t(`查看新聞樹 #${info.group} ↗`,`View news tree #${info.group} ↗`),'wiki-root-link');link.type='button';link.id='wikiCurrentRoot';link.dataset.root=info.root_id;link.dataset.job=active.id;link.disabled=!tree||!hooks.showRoot;link.onclick=()=>{try{hooks.showRoot({instrument:current(),tree,group:info.group,groups:info.groups});hide();}catch(error){status(error.message,true);}};line.append(link,el('small',t(`本樹待涵蓋 ${info.targets} 篇目標；整樹含脈絡 ${info.context_articles??tree?.articles.length??'—'} 篇`,`This tree covers ${info.targets} pending targets; ${info.context_articles??tree?.articles.length??'—'} articles including context`)));content.append(line);} if(p.current_size)content.append(el('small',p.current_size+t(' 篇送入本段',' articles in this segment')+(p.group_info?.parts>1?' · '+p.group_info.part+'/'+p.group_info.parts+t(' 段',' parts'):'')));
   content.append(el('small',t('本組 token：等待模型回報','Current batch tokens: awaiting model report')+(p.last_usage?' · '+t('上一組 ','Previous batch ')+tokenText(p.last_usage):'')),el('small',t('本次工作累計 ','Current job total ')+tokenText(active.usage||p.usage)));}
   const stop=retainedStop||el('button');stop.id='wikiStop';stop.dataset.jobId=active.id;if(!retainedStop)box.insertBefore(stop,box.querySelector('.wiki-live-content'));

  }
  const treeJob=active?.payload.failed_tree_count?active:latestFailure?.payload.failed_tree_count?latestFailure:null;
  if(treeJob){
   const p=treeJob.payload;
   content.append(el('small',isActive(treeJob)
    ?t(`${p.failed_tree_count} 棵樹待重試，其餘樹繼續整理。`,`${p.failed_tree_count} trees need another attempt. Other trees continue.`)
    :t(`${p.failed_tree_count} 棵樹待重試。點「繼續整理」可從已保存的分段接續。`,`${p.failed_tree_count} trees need another attempt. Continue processing to resume from saved segments.`)));
   if(p.last_tree_failure)content.append(el('small',treeFailureText(p.last_tree_failure)));
  }
  const lastExtraction=lastJobs.find(j=>j.payload.last_decisions);
  if(lastExtraction){
   const d=lastExtraction.payload.last_decisions;
   if(d.same_publication)content.append(el('small',t('最近分段沿用同一篇原始報導，已連結兩筆來源，未呼叫模型。','Last segment reused an identical original report. Both records are linked; no model call was made.')));
   else if(d.new_topics!==undefined)content.append(el('small',t(`最近分段比對 ${d.candidates} 個既有節點 · 補引文 ${d.reinforced} · 修訂 ${d.updated} · 延伸 ${d.extended} · 新主題 ${d.new_topics}`,
    `Last segment compared ${d.candidates} prior nodes · ${d.reinforced} corroborated · ${d.updated} revised · ${d.extended} extended · ${d.new_topics} new topics`)));
   else content.append(el('small',t(`最近保存的 L1 分段：比對 ${d.candidates} 個舊觀點 · 新增 ${d.created} · 修訂 ${d.updated} · 補引文 ${d.reinforced}`,
    `Last saved L1 segment: ${d.candidates} prior candidates · ${d.created} created · ${d.updated} revised · ${d.reinforced} corroborated`)));
  }
  const classifier=lastJobs.find(job=>job.payload.operation==='classify_l1');
  if(classifier){
   const p=classifier.payload,count=p.failed_count??p.failed_ids?.length??0;
   if(active!==classifier&&isActive(classifier))jobProgress(content,classifier);
   if(isActive(classifier)&&p.recovering)content.append(el('small',t('正在分批重試觀點分類','Retrying classification in smaller batches')));
   if(count)content.append(el('small',t(`分類已保存 ${p.done}/${p.total} 個觀點，${count} 個待補。可在本次工作結束後繼續整理。`,`Classification saved for ${p.done}/${p.total} opinions. ${count} need another attempt after this job.`)));
   if(classifier.status==='failed'&&classifier!==lastJobs[0]&&!count)content.append(el('small',classifier.error||t('觀點分類已停止','Opinion classification stopped')));
  }
  if(!active&&lastJobs[0]?.payload.last_usage)content.append(el('small',t('最近一組已回報 token ','Latest reported batch tokens ')+tokenText(lastJobs[0].payload.last_usage)));
  const usage=plan?.usage||lastCoverage?.usage;if(usage){content.append(el('small',t('所選新聞時段累計 ','Selected news interval total ')+tokenText(usage.reported)));if(usage.legacy_jobs_without_attribution)content.append(el('small',t('較早版本沒有逐批用量資料，未納入此區間統計。','Older jobs lack per-batch usage and are excluded from interval totals.')));}
  if(latestFailure){
   box.dataset.state='failed';
   const error=latestFailure.error==='Wiki compiler is busy; retry the job later'&&latestFailure.payload.workers>1
    ?t('主機模型橋接只接受一個請求。請從專案目錄執行 ./run.sh up 更新橋接。','The host bridge accepted only one request. Run ./run.sh up from the repository to update it.')
    :latestFailure.error||latestFailure.status;
   if(latestFailure.error!==latestFailure.payload.last_tree_failure?.error)content.append(el('small',error));
   if(latestFailure.payload.workers_state)content.append(workerDetails(latestFailure));
  }
  const result=el('div',undefined,'wiki-published-result');result.id='wikiPublishedResult';
  result.append(el('small',graphLoadError?t('讀取已發布圖譜失敗，正在重試；已保存成果不受影響。','Published graph could not be loaded; retrying. Saved results are retained.'):latestPublishedVersion?t(`已發布 v${latestPublishedVersion} · 目前載入 ${data?.nodes.length||0} 節點`,`Published v${latestPublishedVersion} · ${data?.nodes.length||0} nodes loaded`):active?t('尚無已發布版本；第一段通過驗證並保存後會自動顯示。','No published version yet; the first validated, saved segment will appear automatically.'):t('尚無已發布版本。','No published version yet.')));
  const view=el('button',t('查看最新已發布成果','View latest published results'));view.id='wikiShowPublished';view.type='button';view.onclick=showPublished;result.append(view);content.append(result);
  const mounted=box.querySelector('.wiki-live-content');
  if(!mounted){box.replaceChildren(worker,...(active?[box.querySelector('#wikiStop')]:[]),content);return;}
  reconcileProgress(mounted,content);
 }
 // Worker trees are frozen for each job. Keep matching rows and their focused buttons.
 function reconcileProgress(mounted,next){
  const children=[...next.children];
  children.forEach((node,index)=>{
   const old=mounted.children[index];
   if(!old){mounted.append(node);return;}
   if(old.id==='wikiWorkerProgress'&&node.id===old.id&&old.dataset.job===node.dataset.job){
    reconcileProgress(old,node);return;
   }
   if(!old.isEqualNode(node))old.replaceWith(node);
  });
  while(mounted.children.length>children.length)mounted.lastElementChild.remove();
 }
 function invalidate(){rangeCounts=null;generation++;previewSerial++;plan=null;$('wikiStart').disabled=true;$('wikiSelectedCoverage').replaceChildren();}
 let pipelineOpen=false;
 let rangeCounts=null,previewInFlight=false,nextPreview=null;
 function intervalBar(box,title,total,done,pending,labels){
  const row=el('div',undefined,'wiki-range-row'),heading=el('strong',title);
  const bar=el('div',undefined,'wiki-interval-meter');
  bar.setAttribute('aria-hidden','true');
  if(total){
   const filled=el('span');filled.style.width=(100*done/total)+'%';bar.append(filled);
  }else bar.classList.add('is-empty');
  const legend=el('small',undefined,'wiki-count-legend');
  for(const [i,count] of [done,pending].entries()){
   const share=total?' · '+(100*count/total).toLocaleString(language(),{maximumFractionDigits:1})+'%':'';
   legend.append(el('span',labels[i]+' '+count.toLocaleString(language())+share));
  }
  row.append(heading,bar,legend);box.append(row);
 }
 function paintCounts(){
  if(!rangeCounts)return;
  const box=$('wikiSelectedCoverage'),{selected,pending,reused,trees}=rangeCounts;
  const dates=range();
  const review=$('wikiOperation').value==='review';
  box.replaceChildren(el('strong',t('所選區間的 Wiki 工作量','Wiki workload for this range')));
  box.append(el('small',dates?dates.start+' → '+dates.end+' UTC':t('全部日期','All dates')));
  intervalBar(box,t(`新聞 DB · ${selected.toLocaleString(language())} 篇`,`News DB · ${selected.toLocaleString(language())} articles`),
   selected,reused,selected-reused,[t('Wiki 已整理','In Wiki'),t('尚未整理','Unprocessed')]);
  if(trees&&!review){
   intervalBar(box,t(`新聞樹 · ${trees.total.toLocaleString(language())} 棵`,`News trees · ${trees.total.toLocaleString(language())}`),
    trees.total,trees.done,trees.pending,[t('已完成','Complete'),t('待整理','Pending')]);
  }
  const docs=rangeCounts.documents;
  if(docs){
   intervalBar(box,t('綁定的文件原文 · 全部日期','Bound document passages · all dates'),docs.total,docs.done,docs.pending,
    [t('L1 已審視','Reviewed by L1'),t('待審視','Pending review')]);
   for(const binding of docs.sources||[]){
    box.append(el('small',binding.collection+' / '+binding.source+' · '+t('DB 已匯入 '+binding.records+' 個節點',binding.records+' imported records')));
   }
   if(!docs.total)box.append(el('small',t('請確認綁定來源含段落原文。目錄及匯入觀點本身不列入審視。','Bound sources need original passage text. Folder entries and imported claims are excluded.')));
   const receipt=el('details');receipt.append(el('summary',t('查看各段原文與審視結果','View passages and review outcomes')));
   const names={created:t('新增觀點','Created'),updated:t('修訂','Revised'),extended:t('延伸','Extended'),
    contradicted:t('記錄相反依據','Contradicted'),linked:t('新增關聯','Linked'),reinforced:t('補強引用','Corroborated'),reused:t('沿用','Reused'),unchanged:t('已審視，無變更','Reviewed, no change')};
   receipt.ontoggle=()=>{
    if(!receipt.open||receipt.childElementCount>1)return;
    for(const item of docs.passages){
     const line=el('p'), link=el('a',item.collection+' / '+item.source+' · '+item.title+' · v'+item.revision);
     link.href=item.url;link.target='_blank';link.rel='noopener';
     const results=item.outcomes.map(k=>names[k]||k);
     if(!item.done)results.unshift(t('待審視','Pending review'));
     line.append(link,document.createTextNode(' · '+results.join(' / ')+(item.versions.length?' · Wiki v'+item.versions.join(', v'):'')));receipt.append(line);
     for(const [index,id] of (item.opinions||[]).entries()){
      const button=el('button',t('查看觀點 ','View opinion ')+(index+1));
      button.disabled=!data?.version||Math.min(...item.versions)>data.version;
      button.onclick=()=>openViewpoint({id},true);line.append(' ',button);
     }
    }
   };
   box.append(receipt);
  }
  let note;
  if(!selected)note=t('這個區間沒有符合範圍的新聞。','No articles match this range.');
  else if(review)note=t(`本次可重新檢視 ${pending} 篇已有觀點的新聞。`,`${pending} articles with existing viewpoints are eligible for review.`);
  else if(!pending)note=t('此區間的新聞皆已整理。','All articles in this range have been processed.');
  else if(trees)note=t('開始後會用待整理樹中的新聞補建或更新 L1 觀點。','Start uses evidence from pending trees to build or update L1 viewpoints.');
  else note=t('開始後會將尚未整理的新聞按目前設定分批，補建或更新 L1 觀點。','Start groups unprocessed articles into batches to build or update L1 viewpoints.');
  if(docs?.pending)note+=t(' 本次也會審視待辦文件原文。',' Pending document passages will also be reviewed.');
  box.append(el('small',note,'wiki-range-note'));
  const flow=el('details');flow.id='wikiL1Pipeline';flow.open=pipelineOpen;
  flow.ontoggle=()=>{if(flow.isConnected)pipelineOpen=flow.open;};
  flow.append(el('summary',t('查看 L1 生成與去重流程','Inspect the L1 generation pipeline')));
  const steps=el('ol');
  const labels=review?[t('選取已有觀點的新聞重新檢視','Select previously processed news for review')]:
   [t(`比對新聞版本：已整理 ${reused} 篇，待處理 ${pending} 篇`,`Check news revisions: ${reused} processed, ${pending} pending`)];
  if(docs)labels.push(t('核對文件修訂版本，優先比對引用過同一段落的觀點','Check document revisions and prioritize opinions citing this passage'));
  if(!review&&trees)labels.push(t('逐棵樹重用已保存分段','Reuse saved segments in each tree'));
  if(!review)labels.push(t('檢查單篇轉載：原文網址、日期與內容完全相同即可沿用','Check single-article reprints for identical original URL, date and content'));
  labels.push(t('搜尋同股票的既有命題，比對主體、期間與條件','Retrieve existing propositions and compare subject, period and conditions'),
   t('重述可略過；新佐證補引文，判斷改變就修訂，也可從原觀點延伸出子觀點','Skip restatements, attach supporting quotes, revise changed conclusions, or branch from an existing thesis'),
   review?t('重新檢視會把新觀點接回既有觀點鏈','In review, connect new interpretations to existing viewpoints'):t('無法接到既有觀點時，記下差異並建立新主題','Start a new topic only after recording why the previous theses do not fit'),
   t('核對原文引用與修訂版本，保存結果','Check source quotes and the revision base, then save'));
  for(const label of labels)steps.append(el('li',label));
  flow.append(steps);box.append(flow);
 }
 function schedulePreview(refresh=false){
  if(!refresh){invalidate();activity();}
  clearTimeout(previewTimer);nextPreview=null;
  if(panel.hidden||!current())return;
  const box=$('wikiSelectedCoverage'),serial=previewSerial,ident=current();
  if(!validDates()){box.textContent=t('請輸入有效的起訖日期。','Enter a valid start and end date.');return;}
  if(!rangeCounts)box.textContent=t('正在計算所選區間的工作量…','Counting work in the selected range…');
  const valid=()=>serial===previewSerial&&ident===current()&&!panel.hidden;
  async function read(){
   if(!valid())return;
   if(previewInFlight){nextPreview=read;return;}
   previewInFlight=true;
   try{
    const result=await api('range-counts',requestBody());
    if(valid()){rangeCounts=result;paintCounts();}
   }catch(error){if(valid()){rangeCounts=null;box.textContent=t('區間統計讀取失敗：','Range counts unavailable: ')+error.message;}}
   finally{previewInFlight=false;const next=nextPreview;nextPreview=null;if(next)next();}
  }
  previewTimer=setTimeout(read,300);
 }
 function draftSettings(){return {include_vix:$('wikiVix').checked,workers:$('wikiStrategy').value==='root'&&$('wikiOperation').value!=='review'?Number($('wikiWorkers').value):1,languages:$('wikiLanguages').value==='both'?['zh-Hant','en']:[$('wikiLanguages').value],evidence_size:Number($('wikiEvidenceSize').value)||5,strategy:$('wikiStrategy').value,...($('wikiStrategy').value==='root'?{graph_universe:graphUniverse,graph_settings:graphSettings||lastConfig.graph_settings||{}}:{} )};}
 function dirtySettings(){const changed=!!appliedSettings&&JSON.stringify(draftSettings())!==JSON.stringify(appliedSettings),missing=!!$('wikiSaved').value&&$('wikiStrategy').value==='root'&&(!graphUniverse?.articles?.length||graphUniverse.ticker!==current().split(':')[1]);$('wikiApply').hidden=!changed;$('wikiApply').disabled=!validDates()||busy||missing;$('wikiApplyStatus').textContent=changed&&missing?t('請先載入同一股票的新聞圖譜；不需要點選 root。','Load this stock’s News graph first; no root click is required.'):changed?t('套用後，進行中的工作會停止並依新設定接續。','Apply stops active work and continues with these settings.'):'';}

 function requestBody(settings=appliedSettings||draftSettings()){const [model,reasoning_effort]=$('wikiModel').value.split('|');const body={...selection(),news_db:!$('wikiSaved').value,instrument:current(),model,reasoning_effort,scope:$('wikiSaved').value?$('wikiScope').value:'global',date_range:range(),operation:$('wikiOperation').value,...settings};if(body.strategy==='root'&&body.graph_universe?.articles?.length){delete body.graph_selection;delete body.articles;delete body.graph_edges;}if(body.operation==='review')body.workers=1;return body;}
 function query(){const p=new URLSearchParams({instrument:current()});if($('wikiVersion').value)p.set('version',$('wikiVersion').value);const dates=range();if(dates){p.set('start',dates.start);p.set('end',dates.end);}return p;}
 function clearStock(){renderedWiki=null;for(const id of ['wikiKind','wikiRelation','wikiAssessment'])$(id).value='';$('wikiLayer').value='L1';displayedKey=null;displayedEpoch=null;classStamp='';appliedSettings=null;rootSelection=null;graphUniverse=null;graphSettings=null;latestPublishedVersion=0;graphLoadError=null;researchRun=null;baseData=null;clearTimeout(revealTimer);root.dispatchEvent(new CustomEvent('atlas-wiki-stock'));invalidate();request++;data=null;lastCoverage=null;lastJobs=[];lastConfig={};selectedDetail=null;detailRequest++;chart.resetRange();focusRoot=null;focusIds=null;fitKey='';treeOpen.clear();versionChoices();$('wikiViewStart').value='';$('wikiViewEnd').value='';$('wikiDetail').replaceChildren();$('wikiTotals').textContent=t('尚未載入此股票 Wiki','This stock Wiki is not loaded');$('wikiGroups').hidden=true;$('wikiCountDetails').replaceChildren();$('wikiVersionInfo').replaceChildren();chart.update({rows:[],terms:[],bounds:null,selected:''});$('wikiInsights').replaceChildren();graph?.graphData({nodes:[],links:[]});activity();}
 function restore(cfg){if(!cfg)return;$('wikiVix').checked=!!cfg.include_vix;if(cfg.model){const value=cfg.model+'|'+(cfg.reasoning_effort||'low');if([...$('wikiModel').options].some(o=>o.value===value))$('wikiModel').value=value;}$('wikiWorkers').value=String(cfg.workers||1);$('wikiLanguages').value=cfg.languages?.length===1?cfg.languages[0]:'both';$('wikiEvidenceSize').value=String([5,10,15,20].includes(cfg.evidence_size)?cfg.evidence_size:5);$('wikiStrategy').value=cfg.strategy||'lexical';$('wikiRange').value=cfg.date_range?'custom':'all';if(cfg.date_range){$('wikiStartDate').value=cfg.date_range.start;$('wikiEndDate').value=cfg.date_range.end;}sliders();if(!rootSelection?.ticker&&cfg.graph_selection?.mode!=='coverage')rootSelection=cfg.graph_selection;if(cfg.graph_universe){graphUniverse=cfg.graph_universe;graphSettings=cfg.graph_settings;}appliedSettings={...draftSettings(),...(cfg.strategy==='root'?{graph_universe:cfg.graph_universe||null,graph_settings:cfg.graph_settings||{}}: {})};strategyNote();}
 function applyState(value){
  lastJobs=[...(value.jobs||[]),...(value.classification_jobs||[])];
  lastConfig=value.config||{};lastCoverage=value.coverage;latestPublishedVersion=Number(value.version)||0;
 }
 function classificationStamp(state){return JSON.stringify((state.classification_jobs||[]).map(j=>[j.status,j.updated_at]));}
 function paintSnapshot(entry,key,meta){
  const value=entry.value,changed=!entry.token||baseData!==value||displayedKey!==key;
  if(data&&data.version!==value.version){selectedDetail=null;detailRequest++;$('wikiDetail').replaceChildren(el('p',t('點選此版本的節點查看引用。','Select a node in this version to view its citations.')));}
  if(meta)applyState(meta);
  if(!entry.token&&value.jobs)applyState({...meta,...value}); // Older servers also return live activity here.
  graphLoadError=null;displayedEpoch=entry.epoch;displayedKey=key;
  latestPublishedVersion=Math.max(latestPublishedVersion,Number(value.version)||0);
  classStamp=classificationStamp(meta||value);
  if(changed){
   baseData=value;combine();savedChoices();versionChoices();classificationChoices();
   render();if(focusRoot&&data.nodes.some(n=>n.id===focusRoot))focusGalaxy(focusRoot,false);
  }
  activity();
 }
 async function load(restoreSettings=false,saved=null,verifiedState=null){
  const mine=++request,ident=current();if(!ident)return false;
  const valid=()=>mine===request&&!panel.hidden&&current()===ident;
  loading++;let prepared=false,restoredFilters=false;
  function prepare(meta){
   if(restoreSettings&&!prepared&&meta){
    applyState(meta);restore(meta.config);
    if(saved?.instrument===ident){
     const pin=saved.controls?.wikiVersion;
     if(pin&&![...$('wikiVersion').options].some(o=>o.value===pin))$('wikiVersion').add(option('v'+pin,pin));
     restoreRuntime(saved);
    }
    activity();prepared=true;
   }
  }
  function showEntry(entry,key,meta){
   paintSnapshot(entry,key,meta);
   if(saved?.controls?.wikiAssessment&&!restoredFilters){
    const choice=$('wikiAssessment'),term=saved.controls.wikiAssessment;
    if([...choice.options].some(o=>o.value===term)){choice.value=term;render();}
    restoredFilters=true;
   }
  }
  try{
   const cached=cache.peekState(ident);
   prepare(cached);
   const earlyKey=String(query()),early=cache.peekGraph(earlyKey);
   if(early&&(!restoreSettings||prepared))showEntry(early,earlyKey,cached);
   else if(!baseData||displayedKey!==earlyKey)status(t('正在讀取已保存的 Wiki 圖譜…','Loading saved Wiki graph…'),false,true);
   activity();
   const meta=verifiedState||await cache.state(ident);
   if(!valid())return false;
   if(prepared&&!saved&&cached?.config_token!==meta.config_token)restore(meta.config);
   prepare(meta);applyState(meta);activity();
   const key=String(query()),hit=cache.peekGraph(key);
   if(hit&&baseData!==hit.value)showEntry(hit,key,meta);
   const shared=cache.hasPendingGraph(key);
   let entry=await cache.graph(key);
   if(shared&&valid()&&key===String(query())&&meta.epoch&&entry.epoch!==meta.epoch)entry=await cache.graph(key);
   if(!valid()||key!==String(query()))return false;
   showEntry(entry,key,meta);
   if(String(query())!==key)return load();
   if(restoreSettings){
    schedulePreview();
    if(saved&&$('wikiLayer').value!=='L1'&&!researchRun)root.dispatchEvent(new CustomEvent('atlas-wiki-layer',{detail:{runId:saved.research_run}}));
   }
   if(!busy)status('');return true;
  }catch(e){
   if(valid()&&$('wikiVersion').value&&e.message.includes('只保留最近 10 個可切換版本')){
    $('wikiVersion').value='';const ok=await load();if(ok)status(t('先前固定的版本已超出保留範圍，已開啟最新版。','The pinned version expired. Showing the latest version.'));return ok;
   }
   if(valid()){graphLoadError=e.message;status(e.message,true);}return false;
  }
  finally{loading--;if(!loading&&!busy){$('wikiStatus').classList.remove('wiki-working');$('wikiStatus').setAttribute('aria-busy','false');}if(!panel.hidden)activity();}
 }
 async function refreshCatalog(force=false){
  if(panel.hidden)return;if(catalogPending)return catalogPending;if(!force&&Date.now()-catalogAt<5000)return;
  catalogAt=Date.now();catalogPending=(async()=>{try{const value=await cache.catalog('status',force?0:5000);if(panel.hidden)return;const changed=JSON.stringify([value.instruments,value.news_databases])!==JSON.stringify([info?.instruments,info?.news_databases]);info=value;if(changed)savedChoices(true);}catch{}finally{catalogPending=null;}})();return catalogPending;
 }
 async function poll(){
  if(panel.hidden||polling||loading)return;polling=true;
  try{
   await refreshCatalog();
   if(panel.hidden||!current()||!$('wikiSaved').value)return;
   const ident=current(),mine=request,epoch=jobStateEpoch;
   const valid=()=>!panel.hidden&&current()===ident&&mine===request&&epoch===jobStateEpoch;
   try{
    const value=await cache.state(ident);if(!valid())return;
    if(pollError&&$('wikiStatus').textContent===pollError&&!busy)status('');pollError=null;
    const was=lastJobs.some(isActive),oldVersion=latestPublishedVersion;applyState(value);activity();
    if(!data||graphLoadError||displayedKey!==String(query())||
      (value.epoch?displayedEpoch!==value.epoch:!$('wikiVersion').value&&(data.version!==value.version||classStamp!==classificationStamp(value))))await load(false,null,value);
    if(oldVersion!==latestPublishedVersion||(was&&!lastJobs.some(isActive)))schedulePreview(true);
   }catch(e){if(valid()){pollError=e.message;$('wikiLive').dataset.state='offline';$('wikiLive').replaceChildren(el('strong',t('連線中斷，無法確認模型狀態','Connection lost. Model status unknown.')));status(e.message,true);}}
  }finally{polling=false;}
 }
 const termColor=n=>data?.taxonomy?.terms.find(t=>(n.classification_terms||[]).includes(t.id))?.color;
 const roleName=role=>role==='support'?t('支持論證','Supporting arguments'):t('反對論證','Counterarguments');
 const roleColor=role=>role==='support'?'#73ddca':'#efa88c';
 const nodeColor=n=>n.wikiDim?'#1a293a':n.argument_role?roleColor(n.argument_role):termColor(n)||(n.id===focusRoot?'#ffe0a0':n.wikiContext?'#687b8e':({ArticleRevision:'#78b7e7',Claim:'#83dfbf',Event:'#e6bc76',Thesis:'#c3a2ee',CustomerOpinion:'#f1b4df'})[n.kind]);
 function nodeHeading(n){
  const box=el('div',undefined,'wiki-node-heading'),term=data?.taxonomy?.terms.find(t=>(n.classification_terms||[]).includes(t.id));
  box.append(el('strong',(n.layer||'L1')+' · '+(kindNames()[n.kind]||n.kind)));
  const line=el('div'),swatch=el('span',undefined,'wiki-node-swatch');swatch.style.backgroundColor=nodeColor(n);line.append(swatch,document.createTextNode(n.wikiDim?t('暗色：非目前選取分支','Dimmed: outside selected branch'):n.argument_role?roleName(n.argument_role):term?t('分類：','Category: ')+termLabel(term):n.wikiContext?t('灰色：引用／相依背景','Gray: evidence/dependency context'):t('類型色：','Type color: ')+(kindNames()[n.kind]||n.kind)));box.append(line);
  if(n.research_question)box.append(el('small',t('研究問題：','Research question: ')+n.research_question));
  if(n.argument_roles?.length)box.append(el('small',n.argument_roles.map(roleName).join(' / ')));
  const labels=(data?.taxonomy?.terms||[]).filter(t=>(n.classification_terms||[]).includes(t.id));if(labels.length>1)box.append(el('small',t('所有分類：','All categories: ')+labels.map(termLabel).join(' · ')));
  return box;
 }
 function nodeTooltip(n){const box=el('div',undefined,'wiki-node-tooltip');box.append(nodeHeading(n),el('div',copy(n).title));return box.outerHTML;}
 // Reuse the renderer's own Three constructors; keep picking/dragging on the real mesh.
 function shapeArguments(){for(const n of graph.graphData().nodes){const mesh=n.__threeObj;if(!n.argument_role||!mesh?.geometry||mesh.geometry.userData.argumentRole===n.argument_role)continue;
  const cube=n.argument_role==='counter',v=cube?[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]:[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]],faces=cube?[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[3,7,6],[3,6,2],[1,2,6],[1,6,5],[0,4,7],[0,7,3]]:[[0,2,4],[2,1,4],[1,3,4],[3,0,4],[2,0,5],[1,2,5],[3,1,5],[0,3,5]];
  const geometry=mesh.geometry.clone(),Attribute=mesh.geometry.attributes.position.constructor;geometry.setIndex(null);for(const key of Object.keys(geometry.attributes))geometry.deleteAttribute(key);geometry.setAttribute('position',new Attribute(new Float32Array(faces.flatMap(f=>f.flatMap(i=>v[i].map(x=>x*(cube?4:7))))),3));geometry.computeVertexNormals();geometry.computeBoundingSphere();geometry.computeBoundingBox();geometry.userData.argumentRole=n.argument_role;mesh.geometry=geometry;
 }paintShapeLegend();}
 let legendRenderer=null;
 function paintShapeLegend(){
  const box=$('wikiShapeLegend');if(!box||!graph)return;const nodes=graph.graphData().nodes,groups=new Map();
  for(const n of nodes){const term=data?.taxonomy?.terms.find(t=>(n.classification_terms||[]).includes(t.id));const key=n.argument_role||term?.id||n.kind;if(!groups.has(key))groups.set(key,{n,label:n.argument_role?roleName(n.argument_role):term?termLabel(term):kindNames()[n.kind]});}
  const key=language()+JSON.stringify([...groups].map(([id,{n,label}])=>[id,label,n.kind,n.argument_role,!!n.wikiContext,nodeColor({...n,wikiDim:false})]));
  if(box.dataset.key!==key){
   box.dataset.key=key;delete box.dataset.painted;
   box.replaceChildren(...[...groups.values()].map(({label})=>{
    const entry=el('span',undefined,'wiki-shape-entry');entry.title=label;
    entry.append(el('span',undefined,'wiki-shape-slot'),el('span',label));return entry;
   }));
  }
  if(box.dataset.painted||[...groups.values()].some(({n})=>!n.__threeObj?.geometry))return;
  try{
   legendRenderer ||= new (graph.renderer().constructor)({alpha:true,antialias:true});legendRenderer.setSize(48,48);legendRenderer.setPixelRatio(Math.min(devicePixelRatio,2));legendRenderer.setClearColor(0x000000,0);
   const scene=new (graph.scene().constructor)(),camera=graph.camera().clone();camera.aspect=1;camera.position.set(18,14,24);camera.lookAt(0,0,0);camera.updateProjectionMatrix();for(const light of graph.lights())scene.add(light.clone());
   const slots=box.querySelectorAll('.wiki-shape-slot');let i=0;
   for(const {n,label} of groups.values()){
    const mesh=n.__threeObj.clone();mesh.material=n.__threeObj.material.clone();mesh.material.color.set(nodeColor({...n,wikiDim:false}));mesh.position.set(0,0,0);scene.add(mesh);
    try{
     legendRenderer.render(scene,camera);const icon=el('img');icon.src=legendRenderer.domElement.toDataURL();icon.alt=label;icon.width=32;icon.height=32;slots[i++].replaceChildren(icon);
    }finally{scene.remove(mesh);mesh.material.dispose();}
   }
   box.dataset.painted='true';
  }catch{/* The labels and their reserved space remain readable without WebGL thumbnails. */}
 }
 const nodeSize=n=>n.wikiContext?2:n.kind==='ArticleRevision'?3:6;
 const linkColor=l=>l.wikiDim?'#152333':l.edge.argument_role?roleColor(l.edge.argument_role):l.edge.relation_type==='CONTRADICTS'?roleColor('counter'):l.edge.relation_type==='SUPPORTS'?roleColor('support'):'#91b4c5',linkWidth=l=>l.wikiDim?.25:1;
 function styleFocus(){if(!graph)return;const id=v=>typeof v==='object'?v.id:v;for(const n of graph.graphData().nodes)n.wikiDim=!!focusIds&&!focusIds.has(n.id);for(const l of graph.graphData().links)l.wikiDim=!!focusIds&&(!focusIds.has(id(l.source))||!focusIds.has(id(l.target)));graph.nodeColor(nodeColor).linkColor(linkColor).linkWidth(linkWidth);}
 function clearGalaxy(){if(!focusRoot)return;focusRoot=null;focusIds=null;selectedDetail=null;detailRequest++;$('wikiDetail').replaceChildren(el('p',t('點選此版本的節點查看引用。','Select a node in this version to view its citations.')));styleFocus();saveRuntime();}
 function focusGalaxy(id,remember=true){focusRoot=id;focusIds=new Set([id]);let layer=[id];const branch=data.nodes.find(n=>n.id===id&&n.argument_role);if(branch){focusIds=new Set([id,...branch.branch_members]);layer=[];}for(let depth=0;depth<3&&layer.length&&focusIds.size<150;depth++){const next=[];for(const e of data.edges){const a=e.source.stable_id,b=e.target.stable_id;for(const [from,to] of [[a,b],[b,a]])if(layer.includes(from)&&!focusIds.has(to)&&focusIds.size<150){focusIds.add(to);next.push(to);}}layer=next;}fitPending=false;styleFocus();if(remember)saveRuntime();}
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
  const readingLineage=followedViewpoint?.id===selectedDetail?.id&&followedViewpoint?.instrument===data.instrument&&followedViewpoint?.version===data.version;
  if((focusRoot&&!ids.has(focusRoot))||(selectedDetail&&(!selectedEdge?!ids.has(selectedDetail.id)&&!readingLineage:!edges.some(e=>e.id===selectedDetail.id)))){focusRoot=null;focusIds=null;selectedDetail=null;selectedEdge=false;detailRequest++;$('wikiDetail').replaceChildren();}
  if(focusIds)focusIds=new Set([...focusIds].filter(id=>ids.has(id)));
  const parents=new Map(subset.map(n=>[n.id,n.id])),find=id=>{let p=id;while(parents.get(p)!==p)p=parents.get(p);while(id!==p){const next=parents.get(id);parents.set(id,p);id=next;}return p;};
  for(const e of edges)parents.set(find(e.source.stable_id),find(e.target.stable_id));
  const clusters=new Set(subset.map(n=>find(n.id))).size;
  const legend=$('wikiShapeLegend')||el('div',undefined,'wiki-shape-legend');
  $('wikiTotals').textContent=t(`版本 ${data.version} · 節點 ${subset.length} / ${data.total_nodes} · 連線 ${edges.length}`,`Version ${data.version} · Nodes ${subset.length} / ${data.total_nodes} · Edges ${edges.length}`)+(data.truncated?t(' · 已限制載入範圍',' · Load limit applied'):'');
  $('wikiGroups').hidden=clusters<2;
  $('wikiGroupLabel').textContent=t(`${clusters} 個獨立群`,`${clusters} separate groups`);
  const countDetails=$('wikiCountDetails');countDetails.replaceChildren();
  if(category&&!kind&&layer!=='L2')countDetails.append(el('small',t(`符合分類 ${matches.length} · 引用／相依背景 ${context.length}（灰色）`,`Category matches ${matches.length} · Citation/dependency context ${context.length} (gray)`)));
  if(researchRun&&layer!=='L1')countDetails.append(el('strong',t('研究問題：','Research question: ')+researchRun.bundle.lens.query,'wiki-research-question'));
  if(researchRun&&layer!=='L1')countDetails.append(el('small',t('L2 與引用背景使用建立研究時的固定快照。','L2 and cited context use the fixed research snapshot.')));
  legend.id='wikiShapeLegend';countDetails.append(legend);
  const empty=$('wikiEmpty');empty.hidden=subset.length>0;empty.replaceChildren();
  if(!subset.length){const active=lastJobs.some(j=>['queued','running'].includes(j.status));let message;
   if(layer==='L2')message=t('目前顯示 L2；請從「研究問題 · L2」建立或讀取研究。L1 整理成果位於 L1 圖層。','Viewing L2; open Research question · L2 to create or read research. L1 processing results are in the L1 layer.');
   else if(data.nodes.length)message=t('此版本已有成果，但目前節點／分類篩選沒有符合項目。','This version has results, but none match the current node/classification filters.');
   else if($('wikiVersion').value)message=t('目前固定的歷史版本在此日期範圍沒有節點。','The pinned historical version has no nodes in this date range.');
   else if(active&&!data.version)message=t('正在整理第一段；通過驗證並保存後，節點會自動出現。','Processing the first segment; nodes appear automatically after validation and saving.');
   else message=t('此日期範圍尚無已發布節點；停止會保留已保存結果，未完成的輸出不會顯示為正式觀點。','No published nodes in this date range. Stopping retains saved results; unfinished output is not shown as published opinions.');
   empty.append(el('p',message));if(data.nodes.length||layer==='L2'||$('wikiVersion').value){const reset=el('button',t('查看最新已發布成果','View latest published results'));reset.id='wikiEmptyShowPublished';reset.onclick=showPublished;empty.append(reset);}
  }
  versionInfo();timeline();overview();
  if(!subset.length){if(graph&&graph.graphData().nodes.length)graph.graphData({nodes:[],links:[]});renderedWiki=null;legend.replaceChildren();delete legend.dataset.key;return;}
  try{
   if(!graph){
    graph=root.ForceGraph3D()($('wikiCanvas')).backgroundColor('#141617').showNavInfo(false).nodeId('id')
     .nodeColor(nodeColor)
     .nodeVal(nodeSize).nodeLabel(nodeTooltip).onEngineTick(shapeArguments)
     .linkLabel(l=>el('span',relationName(l.edge.relation_type)).outerHTML).linkColor(linkColor).linkOpacity(.65).linkDirectionalArrowLength(3).linkDirectionalArrowRelPos(1).linkWidth(linkWidth)
     .onNodeHover(n=>{hoverNode=n;glow?.refresh();}).cooldownTicks(70).onNodeClick(n=>{focusGalaxy(n.id);detailRequest++;details(n);if(n.kind!=='ArticleRevision'&&n.layer!=='L2')openViewpoint(n);}).onLinkClick(l=>{detailRequest++;details(l.edge,true);})
     .onBackgroundClick(()=>{if(backgroundClickAllowed)clearGalaxy();})
     .onEngineStop(()=>{shapeArguments();if(fitPending){fitPending=false;graph.zoomToFit(0,35);}});
    if(Array.isArray(graph.controls()?.keys)){graph.controls().keys=[];graph.controls().keyState=-1;}
    graph.controls()?.addEventListener?.('start',()=>{fitPending=false;});
    installGlow();
    graph.d3Force('charge').strength(-18).distanceMax(150);graph.d3Force('link').distance(30);
    graph.d3Force('compact',alpha=>{for(const n of graph.graphData().nodes){n.vx-=n.x*.025*alpha;n.vy-=n.y*.025*alpha;n.vz-=n.z*.025*alpha;}});
    new ResizeObserver(()=>{const r=$('wikiCanvas').getBoundingClientRect();if(r.width&&r.height)graph.width(r.width).height(r.height);}).observe($('wikiCanvas'));
   }
   const nextKey=[data.instrument,$('wikiLayer').value,kind,category,relation,budget,$('wikiVersion').value,JSON.stringify(range())].join('|');
   if(fitKey!==nextKey){fitPending=true;fitKey=nextKey;}
   const previous=renderedWiki;
   if(!previous||previous.base!==baseData||previous.run!==researchRun||previous.reveal!==reveal||previous.key!==nextKey||previous.lang!==language()){
    const old=new Map(graph.graphData().nodes.map(n=>[n.id,n]));graph.graphData({nodes:subset.map(n=>Object.assign(old.get(n.id)||{},n)),links:edges.map(e=>({source:e.source.stable_id,target:e.target.stable_id,edge:e}))});
    renderedWiki={base:baseData,run:researchRun,reveal,key:nextKey,lang:language()};
   }
   if(focusRoot&&!ids.has(focusRoot)){focusRoot=null;focusIds=null;}styleFocus();paintShapeLegend();
  }catch(e){$('wikiEmpty').hidden=false;$('wikiEmpty').textContent=t('3D 無法啟動；請從下方觀點列表閱讀。','3D unavailable; read the viewpoint list below.');}
 }
 function classificationTerms(){return [...(data?.taxonomy?.terms||[]),{id:'__pending',label:t('待分類','Pending classification'),color:'#adc4d5'},{id:'__unclassified',label:t('未歸類','Unclassified'),color:'#bba7d6'}];}
 function classificationTags(n){const valid=new Set((data?.taxonomy?.terms||[]).map(x=>x.id)),tags=(n.classification_terms||[]).filter(id=>valid.has(id));return tags.length?tags:[n.classification_status==='unclassified'?'__unclassified':'__pending'];}
 function classificationChoices(){
  const select=$('wikiAssessment');if(document.activeElement===select)return;
  const rows=viewpoints(),terms=classificationTerms();
  choices('wikiAssessment',[['',t('全部分類','All classifications')],...terms.map(x=>[x.id,termLabel(x)+' · '+rows.filter(n=>classificationTags(n).includes(x.id)).length])]);
  for(const o of select.options){const term=terms.find(x=>x.id===o.value);if(term){o.style.color=term.color;o.title=language()==='en'?termLabel(term):term.definition||term.label;}}
 }
 $('wikiAssessment').onblur=classificationChoices;
 function filterTerm(id,resetKind=true){$('wikiAssessment').value=id;if(resetKind)$('wikiKind').value='';render();saveRuntime();}
 function combine(){
  if(!baseData){data=null;return;}
  data={...baseData,nodes:baseData.nodes.map(n=>({...n})),edges:[...baseData.edges]};
  if(!researchRun||$('wikiLayer').value==='L1'||researchRun.bundle.lens.instrument!==baseData.instrument)return;
  const b=researchRun.bundle,ids=new Set(data.nodes.map(n=>n.id)),endpoint=id=>({stable_id:id,revision_id:id});
  const add=n=>{if(!ids.has(n.id)){ids.add(n.id);data.nodes.push(n);}};
  data.edges.push(...(b.relations||[]));
  for(const o of b.opinions){
   add({id:o.revision_id,kind:o.kind||'Claim',layer:'L1',source_snapshot:researchRun.snapshot,available_at:o.available_at,title:o.title,summary:o.statement,scope:o.scope,citations:o.evidence,classification_terms:o.labels});
   const byArticle=new Map();
   for(const e of o.evidence){
    add({id:e.revision_id,kind:'ArticleRevision',layer:'L1',published_at:e.published_at,available_at:e.available_at,title:e.quote,summary:e.quote,url:e.url,citations:[],classification_terms:o.labels});
    if(!byArticle.has(e.revision_id))byArticle.set(e.revision_id,[]);
    byArticle.get(e.revision_id).push(e);
   }
   for(const [article,refs] of byArticle)data.edges.push({source:endpoint(article),target:endpoint(o.revision_id),relation_type:'SUPPORTS',rationale:t('固定研究快照中的逐字引用','Source quotation in the research snapshot'),evidence_refs:refs});
  }
  researchRun.result.claims.forEach((c,index)=>{const id=researchRun.id+':'+c.id,opinions=b.opinions.filter(o=>c.derived_from.includes(o.claim_id));add({id,kind:'CustomerOpinion',layer:'L2',title:c.statement,summary:c.statement,scope:b.lens.instrument,research_question:b.lens.query,snapshot:researchRun.snapshot,run_id:researchRun.id,derived_from:c.derived_from,argument_roles:['support','counter'].filter(role=>(researchRun.result[role]||[]).includes(c.id)),assumptions:c.assumptions,invalidating_conditions:c.invalidating_conditions,classification_terms:[...new Set(opinions.flatMap(o=>o.labels))],citations:opinions.flatMap(o=>o.evidence),reveal_index:index});for(const o of opinions)data.edges.push({source:endpoint(id),target:endpoint(o.revision_id),relation_type:'DERIVED_FROM',rationale:'L2 使用的精確 L1 claim / revision',evidence_refs:o.evidence});});
  // Saved role membership is relative to the question, never a fabricated L1 truth edge.
  for(const role of ['support','counter']){
   const claims=researchRun.result.claims.filter(c=>(researchRun.result[role]||[]).includes(c.id)&&b.opinions.some(o=>c.derived_from.includes(o.claim_id)));if(!claims.length)continue;
   const id=researchRun.id+':argument:'+role,opinions=b.opinions.filter(o=>claims.some(c=>c.derived_from.includes(o.claim_id)));
   add({id,kind:'ArgumentBranch',layer:'L2',argument_role:role,title:roleName(role),summary:t('模型對研究問題的論證分組；引用不等於已證實。','Model argument grouping relative to the research question; citation is not proof.'),research_question:b.lens.query,snapshot:researchRun.snapshot,run_id:researchRun.id,classification_terms:[...new Set(opinions.flatMap(o=>o.labels))],branch_members:[...claims.map(c=>researchRun.id+':'+c.id),...opinions.flatMap(o=>[o.revision_id,...o.evidence.map(e=>e.revision_id)])],reveal_index:Math.min(...claims.map(c=>researchRun.result.claims.indexOf(c)))});
   for(const c of claims)data.edges.push({source:endpoint(id),target:endpoint(researchRun.id+':'+c.id),relation_type:'ARGUMENT_MEMBER',argument_role:role,rationale:t('模型對研究問題的分組：','Model grouping relative to the question: ')+roleName(role),evidence_refs:[]});
  }
  const seenEdges=new Set(),seenEndpoints=new Set();
  data.edges=data.edges.filter(e=>{
   const key=[e.source.stable_id,e.target.stable_id,e.relation_type].join('|');
   if(e.revision_id){
    if(seenEdges.has(e.revision_id))return false;
    seenEdges.add(e.revision_id);
   }else if(seenEndpoints.has(key))return false;
   seenEndpoints.add(key);return true;
  });data.total_nodes=data.nodes.length;
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
 function selectedBounds(){const dates=range();if(!dates)return null;const a=stamp(dates.start),b=stamp(dates.end);return Number.isFinite(a)&&Number.isFinite(b)&&a>10000&&a<=b?{start:a,end:b}:null;}
 function viewpoints(){const bounds=selectedBounds();return (data?.opinion_index||[]).flatMap(n=>{const dates=(n.dates||[]).filter(d=>!bounds||(stamp(d)>=bounds.start&&stamp(d)<=bounds.end));return bounds&&!dates.length?[]:[{...n,date:dates.at(-1)||'unknown'}];});}
 function chartTerms(){const rows=viewpoints(),chosen=$('wikiAssessment').value;return classificationTerms().filter(c=>(!chosen||chosen===c.id)&&rows.some(n=>classificationTags(n).includes(c.id)));}

 let followedViewpoint=null;
 async function openViewpoint(item,follow=false){const mine=++detailRequest,ident=current(),version=data.version;try{const n=await api('node?'+new URLSearchParams({instrument:ident,id:item.id,version,price_horizon:selection().price_horizon||3}));if(mine===detailRequest&&!panel.hidden&&ident===current()&&data?.version===version){followedViewpoint=follow?{id:n.id,instrument:ident,version}:null;details(n);}}catch(e){if(mine===detailRequest&&!panel.hidden&&ident===current())status(e.message,true);}}
 function viewpointButtons(box,items){let shown=0;const more=el('button',t('顯示更多','Show more'));function append(){const chunk=items.slice(shown,shown+20);shown+=chunk.length;for(const n of chunk){const button=el('button',copy(n).title,'wiki-viewpoint');button.onclick=()=>buttonAction(button,t('正在讀取觀點…','Loading opinion…'),()=>openViewpoint(n));box.insertBefore(button,more);}more.hidden=shown>=items.length;}more.onclick=append;box.append(more);append();}
 function categoryDetail(key,start,end){
  filterTerm(key,false);detailRequest++;selectedDetail=null;
  const box=$('wikiDetail'),items=viewpoints().filter(n=>classificationTags(n).includes(key)&&stamp(n.date)>=start&&stamp(n.date)<=end);
  const term=classificationTerms().find(x=>x.id===key),title=el('h3',termLabel(term)||key);
  box.replaceChildren(title,el('p',day(new Date(start*86400000))+' → '+day(new Date(end*86400000))),el('strong',items.length+t(' 個觀點群',' opinion groups')));
  viewpointButtons(box,items);$('wikinewsTab')?.click();
  if(innerWidth<=800&&$('wikiTimelineTool').dataset.mode==='floating')$('wikiTimelineFold').click();
  title.tabIndex=-1;title.focus({preventScroll:true});
  if(innerWidth<=800)box.scrollIntoView({block:'nearest'});
 }
 function overview(){const box=$('wikiInsights'),rows=viewpoints();box.replaceChildren(el('summary',t('觀點群與分類','Opinion groups and classifications')));for(const term of chartTerms()){const items=rows.filter(n=>classificationTags(n).includes(term.id)),branch=el('details',undefined,'wiki-category');branch.dataset.category=term.id;branch.open=treeOpen.has(term.id);branch.append(el('summary',termLabel(term)+' · '+items.length));const populate=()=>{if(branch.dataset.loaded)return;branch.dataset.loaded='true';viewpointButtons(branch,items);};branch.ontoggle=()=>{branch.open?treeOpen.add(term.id):treeOpen.delete(term.id);if(branch.open)populate();};if(branch.open)populate();box.append(branch);}}
 function timeline(){
  const rows=viewpoints().map(n=>({date:stamp(n.date),tags:[...new Set(classificationTags(n))]}));
  const present=new Set(rows.flatMap(n=>n.tags));
  const terms=classificationTerms().filter(term=>present.has(term.id)).map(term=>({...term,name:termLabel(term)}));
  let bounds=selectedBounds();
  if(!bounds){
   for(const {date} of rows)if(Number.isFinite(date)){
    if(!bounds)bounds={start:date,end:date};
    else{bounds.start=Math.min(bounds.start,date);bounds.end=Math.max(bounds.end,date);}
   }
  }
  chart.update({rows,terms,bounds,selected:$('wikiAssessment').value});
 }
 let dateFrame=0;
 function dateSelectionChanged(){
  clearTimeout(viewReload);if(dialog.open)dirtySettings();schedulePreview();
  if(!validDates())return;
  viewReload=setTimeout(()=>{if(data&&!panel.hidden)load();},250);
  detailRequest++;selectedDetail=null;
  if(data&&!dateFrame)dateFrame=requestAnimationFrame(()=>{
   dateFrame=0;if(panel.hidden||!data||!validDates())return;
   chart.resetRange();$('wikiDetail').replaceChildren();timeline();overview();
  });
 }
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
 function details(item,edge=false){selectedDetail=item;selectedEdge=edge;const n=copy(item.argument_role?data?.nodes.find(x=>x.id===item.id)||item:item),box=$('wikiDetail');box.replaceChildren(el('small',edge?t('模型關係提案','Model-proposed relation'):kindNames()[n.kind]),el('h3',edge?relationName(n.relation_type):n.title),el('p',edge?n.rationale:n.summary===n.title?'':n.summary||''));if(!edge){box.firstChild.replaceWith(nodeHeading(n));}if(!edge&&n.layer==='L2'){box.append(el('p',t('研究問題：','Research question: ')+n.research_question),(()=>{const d=el('details');d.append(el('summary',t('研究版本','Research snapshot')),el('small',n.snapshot));return d;})(),...(n.argument_role?[]:[el('p',t('假設：','Assumptions: ')+(n.assumptions||[]).join('；')),el('p',t('失效條件：','Invalidating conditions: ')+(n.invalidating_conditions||[]).join('；'))]));}
  if(!edge&&n.kind!=='ArticleRevision'&&n.layer!=='L2'){if(!n.translations?.[language()])box.append(el('small',t('此舊節點尚無此語系版本，顯示原始內容。','This older node has no selected-language variant; showing its original content.')));box.append(el('h4',t('財務影響屬性：','Financial impact: ')+categoryNames()[n.assessment?.category||'uncertain']),el('p',n.assessment?.rationale||t('尚未分類','Not yet classified')),el('p',t('模型質性觀點；尚未驗證與未來股價的關聯。','Qualitative model interpretation; not validated against future stock returns.'),'wiki-note'));}
  if(!edge&&n.unassessed_term_ids?.length)box.append(el('small',t('沿用既有分類；新增術語尚未評估。','Existing labels retained; additional terms have not been evaluated.')));
  if(!edge&&n.kind!=='ArticleRevision'&&n.layer!=='L2'){const labels={supported:t('引文支持此說法','Quotes support this statement'),mixed:t('引文對此說法有分歧','Sources differ on this statement'),insufficient:t('引文不足以支撐此說法','Quotes give limited support for this statement')};box.append(el('p',(topicNames()[n.assessment?.topic]||t('主題待重審','Topic pending review'))+' · '+(labels[n.assessment?.evidence]||t('引文支持程度尚未標記','Quote support not yet labeled'))));marketDetails(box,n);}

  if(!edge&&n.kind==='Thesis'&&(n.lineage||n.lineage_links?.length)){
   const section=el('section');section.append(el('h4',t('觀點鏈','Viewpoint lineage')));
   const actions={new_topic:t('開啟新主題','New topic'),extend:t('延伸既有觀點','Branch from a prior viewpoint'),update:t('修訂原判斷','Revise the previous conclusion')};
   if(n.lineage){
    section.append(el('strong',actions[n.lineage.action]),el('p',n.translations?.[language()]?.change_reason||n.opinion_metadata?.change_reason||''));
    if(n.lineage.action==='new_topic'&&n.lineage.compared_id){
     const button=el('button',t('查看曾比對的既有觀點','View the prior thesis considered'));button.onclick=()=>openViewpoint({id:n.lineage.compared_id},true);section.append(button);
    }
   }
   for(const link of n.lineage_links||[]){
    const label=link.relation==='EXTENDS'?(link.parent?t('延伸自','Parent viewpoint'):t('衍生子觀點','Child viewpoint')):(link.parent?t('上一版','Previous revision'):t('下一版','Next revision'));
    const button=el('button',label+' · '+(link.titles[language()]||link.title));button.onclick=()=>openViewpoint(link,true);section.append(button);
   }
   box.append(section);
  }

  if(!edge&&item.url){const a=el('a',t('開啟新聞來源 ↗','Open source ↗'));a.href=item.url;a.target='_blank';a.rel='noopener noreferrer';box.append(a);}
  const history=data.histories?.[item.id];if(history){const section=el('section');section.append(el('h4',t('觀點演變：原始＋最新三批','Evolution: original + latest three batches')));const entry=(node,label)=>{const value=copy(node);section.append(el('small',label+' · v'+node.version),el('h4',value.title),el('p',value.summary));};entry(history.original,t('原始觀點','Original'));history.recent_batches.forEach(group=>{for(const node of group)entry(node,t('修訂觀點','Revision'));});box.append(section);}
  if(!edge){
   const incident=data.edges.filter(e=>e.source.stable_id===item.id||e.target.stable_id===item.id);
   const incoming=incident.filter(e=>e.target.stable_id===item.id&&['SUPPORTS','CONTRADICTS'].includes(e.relation_type));
   const relationButton=e=>{
    const inbound=e.target.stable_id===item.id;
    const other=inbound?e.source:e.target;
    const node=data.nodes.find(n=>n.id===other.stable_id);
    const label=e.relation_type==='SUPPORTS'&&inbound&&node?.kind==='ArticleRevision'?t('原文引用','Source citation'):relationName(e.relation_type);
    const button=el('button',label+' · '+(node?copy(node).title:other.stable_id));
    button.title=copy(e).rationale;button.onclick=()=>details(e,true);return button;
   };
   if(item.kind!=='ArticleRevision'&&item.layer!=='L2'){
    for(const type of ['SUPPORTS','CONTRADICTS']){
     const edges=incoming.filter(e=>e.relation_type===type),group=el('details');
     group.append(el('summary',relationName(type)+t('此觀點',' this viewpoint')+' · '+edges.length));
     group.ontoggle=()=>{if(group.open&&group.childElementCount===1)for(const e of edges)group.append(relationButton(e));};
     box.append(group);
    }
    const archiveLink=el('button',t('檢視此 L1 版本的全部關係','Inspect all relations in this L1 version'));
    archiveLink.onclick=()=>browse('edges',0,data.version,item.id);box.append(archiveLink);
   }
   const rest=item.kind==='ArticleRevision'||item.layer==='L2'?incident:incident.filter(e=>!incoming.includes(e));
   for(const e of rest.slice(0,20))box.append(relationButton(e));
  }
  const ident=data.instrument;const extra=item.corroborating_citations||data.nodes?.find(n=>n.id===item.id)?.corroborating_citations||[];
  for(const c of [...(item.evidence_refs||item.citations||[]),...extra]){if(c===extra[0])box.append(el('strong',t('後續新聞補充的引用','Corroborating quotes from later reports')));box.append(el('blockquote',c.quote));const b=el('button',t('查看引用來源','View cited source'));b.onclick=()=>buttonAction(b,t('正在讀取來源…','Loading source…'),async()=>{const a=await api('article?'+new URLSearchParams({instrument:ident,id:c.article_revision_id}));const link=el('a',a.title+(a.document?' · '+a.document.source+' · v'+a.document.revision:''));
  if(a.document){
   const url=new URL(a.url,location.origin);url.searchParams.set('start',a.document.offset+c.start);url.searchParams.set('end',a.document.offset+c.end);link.href=url.href;
  }else link.href=a.url;link.target='_blank';link.rel='noopener noreferrer';b.replaceWith(link);});box.append(b);}
 }
 let storedUniverse,storedInstrument;
 function saveRuntime(){if(!initialized||restoringUI)return;const controls=Object.fromEntries(runtimeKeys.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).value]));const c=graph?.cameraPosition();const value={instrument:current(),research_run:researchRun?.id||null,controls,layout:layout.state(),root_selection:rootSelection,graph_universe:graphUniverse,graph_settings:graphSettings,root:focusRoot,selected:selectedDetail?.id||null,...(c?{camera:{x:c.x,y:c.y,z:c.z}}:{})};if(value.instrument){savedViews.delete(value.instrument);savedViews.set(value.instrument,value);if(savedViews.size>4)savedViews.delete(savedViews.keys().next().value);}const {graph_universe,...compact}=value;
  const changed=storedUniverse!==graph_universe||storedInstrument!==value.instrument;
  try{
   if(changed)localStorage.setItem('stocknexus.wikiUniverse',JSON.stringify({instrument:value.instrument,graph_universe}));
   localStorage.setItem('stocknexus.wikiRuntime',JSON.stringify(compact));
   storedUniverse=graph_universe;storedInstrument=value.instrument;
  }catch{}
  root.AtlasWorkspace?.save('wiki',changed?value:compact);
 }

 function restoreRuntime(saved){if(!saved)return;restoringUI=true;try{layout.restore(saved.layout);if(saved.instrument)instrumentChoices(saved.instrument);for(const [id,value] of Object.entries(saved.controls||{}))if(runtimeKeys.includes(id)&&id!=='wikiRangeStart'&&id!=='wikiRangeEnd'){$(id).type==='checkbox'?$(id).checked=!!value:$(id).value=value;}sliders();for(const id of ['wikiRangeStart','wikiRangeEnd'])if(saved.controls?.[id]!==undefined)$(id).value=saved.controls[id];if(saved.controls?.wikiRange==='custom')datesFromHandles();if(lastJobs.some(isActive)||lastConfig.enabled||lastConfig.catch_up)lockDates(true,true);rootSelection=saved.root_selection||rootSelection;graphUniverse=saved.graph_universe||graphUniverse;graphSettings=saved.graph_settings||graphSettings;focusRoot=saved.root||null;sliderLabel();strategyNote();}finally{restoringUI=false;}}
 const archive=el('dialog',undefined,'wiki-settings wiki-archive');
 archive.setAttribute('aria-labelledby','wikiArchiveTitle');
 document.body.append(archive);
 let archiveRequest=0;
 async function browse(collection='nodes',offset=0,version=data?.version,id=''){
  const ident=current(),ticket=++archiveRequest;
  archive.replaceChildren();
  const close=root.AtlasUI.labelIcon(el('button'),'close',t('關閉 L1 瀏覽器','Close L1 reader'));close.onclick=()=>archive.close();
  const heading=el('div',undefined,'wiki-reader-heading'),title=el('h2',ident+' · L1');title.id='wikiArchiveTitle';
  heading.append(title,close);archive.append(heading,el('p',t('讀取中…','Loading…')));
  if(!archive.open)archive.showModal();
  try{
   const params=new URLSearchParams({instrument:ident,collection,offset,limit:20});
   if(version!=null)params.set('version',version);
   if(id)params.set('id',id);
   const response=await fetch('/api/context/graph?'+params);
   const page=await response.json();
   if(ticket!==archiveRequest || !archive.open)return;
   if(!response.ok)throw Error(page.error);
   const button=(title,fn)=>{const b=el('button',title);b.onclick=fn;return b;};
   archive.lastChild.remove();
   const go=(kind,start=0,filter='')=>browse(kind,start,page.version,filter);
   archive.append(button(t('全部節點','All nodes'),()=>go('nodes')),button(t('全部關係','All edges'),()=>go('edges')),
    el('p',`v${page.version} · ${page.total?offset+1:0}–${offset+page.items.length} / ${page.total}`));
   for(const item of page.items){
    const line=el('details'),edge=collection==='edges';
    line.append(el('summary',edge?relationName(item.relation_type)+' · '+copy(item).rationale:item.title||item.id));
    if(edge){
     for(const end of [item.source,item.target])line.append(button(end.revision_id,()=>go('nodes',0,end.revision_id)));
    }else line.append(el('p',item.summary||''),button(t('支持、反證與相關修訂','Evidence and related revisions'),()=>go('edges',0,item.id)));
    for(const citation of item.citations||item.evidence_refs||[])line.append(el('blockquote',citation.quote||citation.article_revision_id));
    archive.append(line);
   }
   if(offset)archive.append(root.AtlasUI.labelIcon(button('',()=>go(collection,Math.max(0,offset-20),id)),'previous',t('上一頁','Previous page')));
   if(page.next_offset!==null)archive.append(root.AtlasUI.labelIcon(button('',()=>go(collection,page.next_offset,id)),'next',t('下一頁','Next page')));
  }catch(error){if(ticket===archiveRequest)archive.lastChild.textContent=error.message;}
 }
 $('wikiBrowse').onclick=()=>browse();
 $('wikiCompare').onclick=()=>{
  const [model,effort]=$('wikiModel').value.split('|');
  if(current())root.openWikiComparison({instrument:current(),model,effort,t});
 };
 function rememberedView(ident){
  if(ident&&savedViews.has(ident))return savedViews.get(ident);
  let saved=root.AtlasWorkspace?.state.wiki;
  if(!saved){try{saved=JSON.parse(localStorage.getItem('stocknexus.wikiRuntime')||'null');
   if(saved&&!Object.hasOwn(saved,'graph_universe')){
    const stored=JSON.parse(localStorage.getItem('stocknexus.wikiUniverse')||'null');
    if(stored?.instrument===saved.instrument)saved.graph_universe=stored.graph_universe;
   }
  }catch{}}
  return !ident||saved?.instrument===ident?saved:null;
 }
 function alignedInstrument(news,catalog){
  const stocks=[...(catalog.instruments||[]),...(catalog.news_databases||[])];
  if(news.instrument)return stocks.some(row=>row.instrument===news.instrument)?news.instrument:null;
  const matches=[...new Set(stocks.filter(row=>news.ticker&&row.instrument.split(':')[1]===news.ticker).map(row=>row.instrument))];
  return matches.length===1?matches[0]:null;
 }
 function warmQuery(ident,meta){
  const controls=rememberedView(ident)?.controls,p=new URLSearchParams({instrument:ident});
  if(controls?.wikiVersion)p.set('version',controls.wikiVersion);
  const locked=[...(meta.jobs||[]),...(meta.classification_jobs||[])].some(isActive)||meta.config.enabled||meta.config.catch_up;
  let dates=meta.config.date_range;
  if(controls&&!locked){
   if(controls.wikiRange==='all')dates=null;
   else if(controls.wikiRangeStart&&controls.wikiRangeEnd)dates={start:day(new Date(Number(controls.wikiRangeStart)*86400000)),end:day(new Date(Number(controls.wikiRangeEnd)*86400000))};
  }
  if(dates){p.set('start',dates.start);p.set('end',dates.end);}
  return String(p);
 }
 function preload(news){
  if(!panel.hidden||!(news?.ticker||news?.instrument))return;
  const requested=news.instrument||news.ticker;
  if(warmKey===requested&&Date.now()-warmAt<5000)return;
  clearTimeout(warmTimer);warmKey=requested;warmAt=Date.now();
  warmTimer=setTimeout(async()=>{
   try{
    const catalog=await cache.catalog('status',5000);
    if(warmKey!==requested||!panel.hidden)return;
    const ident=alignedInstrument(news,catalog);
    if(!ident||!catalog.instruments.some(stock=>stock.instrument===ident))return;
    const meta=await cache.state(ident);
    if(warmKey===requested&&panel.hidden)await cache.graph(warmQuery(ident,meta));
   }catch{if(warmKey===requested)warmAt=0;} // The foreground read retries a failed prefetch.
  },80);
 }
 function show(){
  if(showPending)return showPending;
  const ticket=++openEpoch;
  showPending=openWiki(ticket).finally(()=>{if(ticket===openEpoch)showPending=null;});
  return showPending;
 }
 async function openWiki(ticket){
  const valid=()=>ticket===openEpoch&&!panel.hidden;
  const confirmed=()=>hooks.confirmedSearch?.()||hooks.selection('global').search||{};
  const news=confirmed();
  if(news.instrument&&data&&data.instrument!==news.instrument)clearStock();
  panel.hidden=false;layout.refresh();hooks.visible(true);
  if(!data)status(t('正在載入 Wiki 狀態…','Loading Wiki status…'),false,true);
  try{
   await root.AtlasWorkspace?.ready;if(!valid())return;
   const search=confirmed();if(data&&((search.instrument&&search.instrument!==data.instrument)||(search.ticker&&search.ticker!==data.instrument.split(':')[1])))clearStock();
   graph?.resumeAnimation();$('relationOpen').textContent=t('Wiki 設定','Wiki settings');
   const modelCatalog=cache.catalog('models',30000).then(catalog=>{
    if(valid()){models=catalog.models;modelChoices();if(!models.length)activity();}
    return catalog;
   }).catch(()=>null);
   const known=cache.peekCatalog('status');
   const warm=known&&alignedInstrument(search,known);
   info=warm?known:await cache.catalog('status',known?0:5000);
   if(!valid())return;
   catalogAt=warm?0:Date.now();
   const aligned=alignedInstrument(search,info),previous=current(),saved=rememberedView(aligned||previous);
   const unmatched=!!(search.instrument||search.ticker)&&!aligned;
   let target=aligned||(!unmatched&&(previous||saved?.instrument));
   if(!target&&!unmatched)target=(info.instruments||[]).filter(row=>row.version>0).sort((a,b)=>b.version-a.version)[0]?.instrument;
   const changed=previous!==target||!data;
   if(changed&&data)clearStock();
   savedChoices(true);
   const exists=info.instruments.some(row=>row.instrument===target);
   $('wikiSaved').value=exists?target:'';instrumentChoices(target||'');
   const openingStock=current();
   let restored=null;
   if(exists){
    if(changed)restored=saved?.instrument===target?saved:null;
    const mounted=cache.peekGraph(String(query()));
    if(!changed&&!graphLoadError&&mounted&&!mounted.token)await poll();
    else await load(changed,restored);
    if(!valid()||current()!==openingStock)return;
    if(restored?.selected){const n=data?.nodes.find(n=>n.id===restored.selected);if(n){details(n);if(n.kind!=='ArticleRevision'&&n.layer!=='L2')await openViewpoint(n);}}
    if(restored?.camera){fitPending=false;graph?.cameraPosition(restored.camera);}
   }
   if(!valid()||current()!==openingStock)return;
   const newsView=hooks.selection('global'),selected=newsView.graph_selection;
   if(selected?.ticker===openingStock.split(':')[1]&&selected.trees?.length)rootSelection=selected;
   syncGraphUniverse(newsView);selection($('wikiScope').value==='global'?newsView:undefined);strategyNote();schedulePreview();
   clearInterval(pollTimer);pollTimer=setInterval(poll,2000);
   const modelInfo=await modelCatalog;if(!valid()||current()!==openingStock)return;
   if(!initialized||changed){
    const preferred=restored?.controls?.wikiModel||(lastConfig.model?lastConfig.model+'|'+(lastConfig.reasoning_effort||'low'):modelInfo?.default_model+'|medium');
    if([...$('wikiModel').options].some(o=>o.value===preferred))$('wikiModel').value=preferred;
   }
   initialized=true;saveRuntime();activity();
   if(info.bridge_ready&&!graphLoadError)status(unmatched?t('目前新聞股票尚無可讀取的 Wiki。','No saved Wiki matches the current News stock.'):'');
   if(!info.bridge_ready||!models.length)status(t('模型橋接或目錄尚未就緒，仍可檢視已保存的 Wiki。','Model bridge or catalog unavailable. Saved Wikis remain available.'),true);
  }catch(e){if(valid())status(e.message,true);}
  if(valid())$('wikiBack').focus();
 }
 function hide(e){e?.preventDefault();saveRuntime();panel.hidden=true;openEpoch++;showPending=null;dialog.close();clearInterval(pollTimer);clearTimeout(previewTimer);invalidate();request++;graph?.pauseAnimation();hooks.visible(false);$('relationOpen').textContent=root.AtlasI18n?.t('關聯設定')||'Edge settings';open.focus();}
 $('wikiSaved').addEventListener('focus',()=>refreshCatalog(true));root.addEventListener('focus',()=>refreshCatalog(true));
 open.onclick=show;$('wikiBack').onclick=hide;
 $('relationOpen').addEventListener('click',e=>{if(panel.hidden)return;e.preventDefault();e.stopImmediatePropagation();appliedSettings=appliedSettings||draftSettings();syncGraphUniverse();strategyNote();dialog.showModal();},true);
 $('wikiSaved').onchange=async()=>{clearStock();instrumentChoices('');if($('wikiSaved').value)await load(true,rememberedView(current()));else{status(t('選擇新聞 DB 後即可建立 Wiki。','Choose a news database to create a Wiki.'));schedulePreview();}saveRuntime();};
 for(const id of ['wikiInstrument','wikiScope','wikiModel','wikiOperation'])$(id).addEventListener('input',()=>{if(id==='wikiInstrument'){if($('wikiSaved').value){instrumentChoices();return;}clearStock();$('wikiScope').value='global';if(info?.instruments.some(x=>x.instrument===current())){$('wikiSaved').value=current();instrumentChoices();load(true,rememberedView(current()));return;}saveRuntime();}if(id==='wikiOperation'){$('wikiContinuous').disabled=$('wikiOperation').value==='review';if($('wikiContinuous').disabled)$('wikiContinuous').checked=false;}strategyNote();selection();schedulePreview();});
 for(const id of ['wikiLanguages','wikiEvidenceSize','wikiStrategy','wikiWorkers','wikiVix'])$(id).oninput=()=>{strategyNote();dirtySettings();};
 $('wikiApply').onclick=async()=>{if(busy)return;busy=true;let applyError='';dirtySettings();$('wikiApply').classList.add('wiki-working');$('wikiApply').setAttribute('aria-busy','true');$('wikiApplyStatus').textContent=t('正在套用設定…','Applying settings…');try{const result=await api('apply',{...requestBody(draftSettings()),continuous:$('wikiContinuous').checked});appliedSettings=draftSettings();invalidate();dialog.close();await load();status(result.status==='noop'?t('設定已套用；選取範圍皆已處理，模型保持停止。','Settings applied; selected evidence is complete. Model remains idle.'):result.resumed?t('已停止舊工作，依新設定接續。','Old work stopped; continuing with new settings.'):t('設定已套用。','Settings applied.'));schedulePreview();}catch(e){applyError=e.message;status(e.message,true);$('wikiApplyStatus').textContent=e.message;}finally{busy=false;$('wikiApply').classList.remove('wiki-working');$('wikiApply').setAttribute('aria-busy','false');dirtySettings();if(applyError)$('wikiApplyStatus').textContent=applyError;activity();}};
 $('wikiRange').onchange=()=>{preset();dateSelectionChanged();};for(const id of ['wikiStartDate','wikiEndDate'])$(id).oninput=()=>{$('wikiRange').value='custom';sliders();dateSelectionChanged();};
 for(const id of ['wikiRangeStart','wikiRangeEnd'])$(id).oninput=()=>{$('wikiRange').value='custom';if(Number($('wikiRangeStart').value)>Number($('wikiRangeEnd').value))$(id==='wikiRangeStart'?'wikiRangeEnd':'wikiRangeStart').value=$(id).value;datesFromHandles();dateSelectionChanged();};
 for(const id of ['wikiKind','wikiRelation','wikiBudget','wikiAssessment'])$(id).onchange=render;
 async function showPublished(){researchRun=null;clearTimeout(revealTimer);$('wikiLayer').value='L1';$('wikiVersion').value='';for(const id of ['wikiKind','wikiRelation','wikiAssessment'])$(id).value='';focusRoot=null;focusIds=null;root.dispatchEvent(new CustomEvent('atlas-wiki-research-clear'));await load();saveRuntime();}
 function selectVersion(){researchRun=null;clearTimeout(revealTimer);$('wikiLayer').value='L1';render();root.dispatchEvent(new CustomEvent('atlas-wiki-research-clear'));return load();}
 for(const id of ['wikiVersion','wikiViewStart','wikiViewEnd'])$(id).onchange=()=>id==='wikiVersion'?selectVersion():load();
 $('wikiStart').onclick=async()=>{
  if(busy||$('wikiStart').disabled)return;busy=true;const mine=generation,ident=current(),started=Date.now();activity();
  let phase=t('核對新聞與建立分組','Checking news and grouping');
  const preparing=setInterval(()=>{if(mine===generation)status(phase+' · '+Math.floor((Date.now()-started)/1000)+t(' 秒',' s'),false,true);},1000);
  status(t('正在核對快取中的新聞範圍與已完成證據…','Checking cached news and completed evidence…'),false,true);
  try{
   const value=await api('plan',requestBody());if(mine!==generation||ident!==current()||panel.hidden)return;plan=value;
   phase=t('排入尚未完成的工作','Queuing remaining work');status(phase,false,true);
   const job=await api('jobs',{plan_id:value.plan_id,continuous:$('wikiContinuous').checked,classify_missing:true});if(mine!==generation||ident!==current()||panel.hidden)return;
   schedulePreview();phase=t('載入已保存成果','Loading saved results');$('wikiVersion').value='';await load();status(job.status==='noop'?job.message:t('工作已排入佇列，可隨時停止。','Work queued. Stop at any time.'));
  }catch(e){if(mine===generation)status(e.message,true);}finally{clearInterval(preparing);busy=false;$('wikiStatus').classList.remove('wiki-working');$('wikiStatus').setAttribute('aria-busy','false');activity();}
 };

 $('wikiExport').onclick=()=>{if(!data)return;return buttonAction($('wikiExport'),t('正在匯出…','Exporting…'),async()=>{const result=await api('markdown?'+new URLSearchParams({instrument:data.instrument,version:data.version,lang:language()}));const url=URL.createObjectURL(new Blob([result.markdown],{type:'text/markdown;charset=utf-8'})),a=el('a');a.href=url;a.download=data.instrument.replace(':','-')+'-wiki.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);},t('已產生 Markdown，下載已交給瀏覽器。','Markdown generated; download handed to the browser.'));};
 let tipTimer;const hideTip=()=>{clearTimeout(tipTimer);$('wikiStartTip').hidden=true;$('wikiStart').removeAttribute('aria-describedby');};for(const event of ['mouseenter','focus'])$('wikiStart').addEventListener(event,()=>{clearTimeout(tipTimer);tipTimer=setTimeout(()=>{$('wikiStartTip').hidden=false;$('wikiStart').setAttribute('aria-describedby','wikiStartTip');},550);});for(const event of ['mouseleave','blur'])$('wikiStart').addEventListener(event,hideTip);$('wikiStart').addEventListener('keydown',e=>{if(e.key==='Escape')hideTip();});
 $('wikiVersionInfo').addEventListener('toggle',()=>{$('wikiResizeChanges').hidden=!$('wikiVersionInfo').open;layout.refresh();});
 const timelineWindow=root.AtlasWikiTimeline.initWindow(t);
 const chart=root.AtlasWikiTimeline.create(t,id=>{
  if($('wikiDetail').querySelector('.wiki-viewpoint')&&!selectedDetail){detailRequest++;$('wikiDetail').replaceChildren();}
  filterTerm(id,false);
 },categoryDetail);
 const layout=root.AtlasWikiLayout.init(panel,saveRuntime);
 for(const event of ['input','change'])for(const surface of [panel,dialog])surface.addEventListener(event,e=>{if(event==='input'&&dateControls.includes(e.target.id))return;if(initialized)saveRuntime();});
 root.addEventListener('storage',event=>{
  if(event.key==='stocknexus.documentImport'&&!panel.hidden&&$('wikiScope').value==='global')schedulePreview(true);
 });
 root.addEventListener('pagehide',saveRuntime);root.addEventListener('atlas-language',translate);preset();translate();appliedSettings=draftSettings();root.AtlasWiki={show,preload,refresh:load,setResearch,filterTerm,selectNode:id=>{const node=data?.nodes.find(n=>n.id===id);if(!node)return;focusGalaxy(id);details(node);if(node.kind!=='ArticleRevision'&&node.layer!=='L2')return openViewpoint(node);},graph:()=>graph,l1Busy:()=>lastJobs.some(j=>['queued','running'].includes(j.status)),classification:()=>data?.taxonomy};
 let chatRevision=0,chatFingerprint='';
 const wikiRuntime={
  state(){const scope=focusIds?[...focusIds]:selectedDetail?.id?[selectedDetail.id]:(graph?.graphData().nodes||[]).map(n=>n.id);const controls=['wikiLayer','wikiKind','wikiRelation','wikiAssessment','wikiVersion'].map(id=>({id,kind:'set',value:$(id).value,options:[...$(id).options].map(o=>({value:o.value,label:o.textContent})),disabled:$(id).disabled}));const state={surface:'wiki',layer:$('wikiLayer').value,research_run:researchRun?.id||null,research_question:researchRun?.bundle.lens.query||null,language:language(),instrument:current(),version:data?.version||0,dataset:JSON.stringify([current(),data?.version,range(),$('wikiLayer').value,researchRun?.id,data?.taxonomy?.revision_id,classStamp]),date_range:range(),scope_ids:scope,scope_kind:focusIds?'galaxy':selectedDetail?'node':'wiki',selected_node:selectedDetail,root_ids:focusRoot?[focusRoot]:[],counts:{loaded:data?.nodes.length||0,visible:graph?.graphData().nodes.length||0,scope:scope.length,edges:data?.edges.length||0},controls,busy:{wiki:lastJobs.some(j=>['queued','running'].includes(j.status))}};const fingerprint=JSON.stringify(state);if(fingerprint!==chatFingerprint){chatFingerprint=fingerprint;chatRevision++;}return {...state,revision:chatRevision};},
  data(){return {articles:(data?.nodes||[]).filter(n=>n.kind==='ArticleRevision'),nodes:data?.nodes||[],edges:(data?.edges||[]).map(e=>({...e,source:e.source.stable_id,target:e.target.stable_id})),histories:data?.histories||{}};},
  async act(action){if(action.kind==='read')return wikiRuntime.state();if(action.kind==='read_research'){
   const ident=current(),id=researchRun?.id;if(!id||action.run_id!==id||action.instrument!==ident)throw Error('Research selection changed; refresh state');
   const r=await api('research/run?'+new URLSearchParams({instrument:ident,id}));
   if(current()!==ident||researchRun?.id!==id||r.bundle?.lens.instrument!==ident)throw Error('Research selection changed during read');
   return {run_id:id,...r};
  }if(action.revision!==wikiRuntime.state().revision)throw Error('Wiki 已更新，請重新讀取狀態');if(action.kind==='select_article'){const n=data.nodes.find(n=>n.id===action.id);if(!n)throw Error('Unknown Wiki node');focusGalaxy(n.id);details(n);if(n.kind!=='ArticleRevision'&&n.layer!=='L2')await openViewpoint(n);}else if(action.kind==='set'&&wikiRuntime.state().controls.some(c=>c.id===action.id&&c.options.some(o=>o.value===String(action.value)))){const control=$(action.id);control.value=action.value;if(action.id==='wikiVersion')await selectVersion();else if(action.id==='wikiLayer')$(action.id).dispatchEvent(new Event('change'));else render();saveRuntime();}else throw Error('此 Wiki 操作不在允許清單');return wikiRuntime.state();}
 };
 root.AtlasWiki.runtime=wikiRuntime;
 root.AtlasWorkspace?.ready.then(()=>preload(hooks.confirmedSearch?.()));
 root.AtlasWiki.chat=root.AtlasChatPanel?.mount({runtime:wikiRuntime,detail:$('wikiSide'),prefix:'wiki',title:'觀點詳情'});

})(globalThis);
