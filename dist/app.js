'use strict';
const $ = id => document.getElementById(id);
const defaultColors={google:'#0072b2',yahoo:'#e69f00',massive:'#cc79a7'};
const savedColors=AtlasUI.read('sourceColors',{});
const colors=Object.fromEntries(Object.entries(defaultColors).map(([p,value])=>[p,/^#[0-9a-f]{6}$/i.test(savedColors?.[p])?savedColors[p]:value]));
const sourceNames = { google: 'Google', yahoo: 'Yahoo', massive: 'Massive' };
const relationNames = { shared_entity: '共同實體', shared_topic: '共同主題', similar_title: '相似標題' };
let articles = [], relations = [], hovered = null, selected = null, controller = null, exportMeta = {}, currentSearch = 0;
let graph = null, fitTimer = null, sourceArticles = new Map(), lastNetworkRender=null;
let viewRelationJob=null,viewRelationState={phase:"idle",pairs_checked:0},viewRevision=0,viewRequestedSettings=null,restoredRelationSeed=null,restoredRelationViews=[],restoringRelations=false;
const completedRelationViews=new Map();
let renderBudget=800,renderedCount=0,renderedEdges=0,articleListPage=0;
const focusTraceCache=AtlasView.createTraceCache(),previewTraceCache=AtlasView.createTraceCache();
let graphFailure=null,webglCreationReason='',graphRetryBusy=false;
let relationActivity={busy:false},searchPhase='',searchStarted=0,operationNotice='',pendingSearchMeta=null,searchClock=null;
let highlightMode='root',graphChannel='',categoryTrace={nodes:new Map(),edges:new Set(),roots:[]};
let basePayload = {articles:[],relations:[]}, currentView = {articles:[],relations:[]}, sourceStates = {}, saving = false, restoredPositions = new Map();
const providers = ['google','yahoo','massive'];
const viewSources = () => providers.filter(p => $('view-'+p).checked !== false);
const isSeparate = () => $('separateSources').checked === true;
let viewMode='network', channelDefinitions=[], channelCatalog=[], channelFilter='all', timelineCutoff=null, editingChannel=null;
let classifying=false, classificationEpoch=0, timelineBounds=null, timelineFocusRequested=true;
const networkPositions=new Map(), internalLengths=new Map();
const edgeKey=l=>l.scope+':'+[(l.raw_relation||l).source,(l.raw_relation||l).target].sort().join(':');
// Apply the requested exploration preset once per browser; later user edits persist.
const explorationPresetVersion='20261104-galaxy';
if(AtlasUI.read('explorationPresetVersion')!==explorationPresetVersion){
  const savedDraft=AtlasUI.read('searchDraft',{});
  const writes=[AtlasUI.write('exploration',AtlasView.settings()),AtlasUI.write('glow',AtlasGlow.settings()),AtlasUI.write('searchDraft',{...(savedDraft&&typeof savedDraft==='object'?savedDraft:{}),sources:[...providers]})];
  if(writes.every(Boolean))AtlasUI.write('explorationPresetVersion',explorationPresetVersion);
}
let exploration=AtlasView.settings(AtlasUI.read('exploration',{})), activeTrace=AtlasView.trace([],null), candidateTrace=AtlasView.trace([],null);
let glowConfig=AtlasGlow.settings(AtlasUI.read('glow',{})), glowLayer=null, pinnedRoot=null, interaction=null, idleFocus=null, stickyGuideUntil=0;
let lockedRoots=[], keywordLocked=false, rootSearchState=null, rootSearchTicket=0, rootSearchBusy=false;
let focusView={articles:[],relations:[]};
let timeLens=null,timeSizer=null,timePanel=null,relationUI=null,priceLens=null;
const timeLensAvailable=typeof globalThis.AtlasTimeLens?.init==='function'&&typeof globalThis.AtlasTimeLens?.attach==='function';
let timeFocus=AtlasTimeline.timeSettings(AtlasUI.read('timeFocus',{}));
const focusRoot=()=>lockedRoots[0]??null;
const timelineStyle='density';
const reducedMotion = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
function el(tag, text, cls) { const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; }
function date(value) { if (!value) return '日期未知'; const d = new Date(value); return Number.isNaN(d.getTime()) ? '日期未知' : d.toLocaleString(AtlasI18n.language()==='en'?'en-US':'zh-TW'); }
function updateActivity(){
  const messages=[];
  if(graphFailure)messages.push(AtlasI18n.t('3D 無法啟動；請查看錯誤原因後重試。')+' '+graphFailure.message);
  if(graphRetryBusy)messages.push(AtlasI18n.t('正在重建 3D…'));
  if(controller)messages.push(AtlasI18n.t(searchPhase==='relations'?'新聞已載入，正在計算關聯；可切換視圖。':pendingSearchMeta&&focusView.articles.length?'搜尋中，暫時保留上一張圖。':'正在讀取新聞；可切換視圖。')+' '+Math.floor((Date.now()-searchStarted)/1000)+'s');
  if(controller&&basePayload.relations_pending&&relations.length)messages.push(AtlasI18n.t('已保留既有關聯；新資料的關聯仍在更新。'));
  if(relationActivity.busy)messages.push(AtlasI18n.t('套用關聯中；目前圖譜保留，可繼續操作。')+' '+Math.floor((Date.now()-relationActivity.started)/1000)+'s');
  if(!controller&&!relationActivity.busy){if(relationActivity.error)messages.push(relationActivity.error);else if(operationNotice)messages.push(operationNotice);else if(basePayload.relation_scope==='view')messages.push(AtlasI18n.language()==='en'?'View-scoped relations; hidden news is retained.':'依目前視圖計算關聯；未顯示新聞仍保留。');else if(basePayload.relations_pending)messages.push(AtlasI18n.t('新聞已保留，關聯尚未完成；可在設定中重新套用。'));else if(!focusView.articles.length)messages.push(AtlasI18n.t(!viewSources().length?'所有來源已隱藏；請勾選顯示來源。':pendingSearchMeta?'正在等待搜尋結果。':exportMeta.query||exportMeta.ticker?'此搜尋目前沒有可顯示結果；請檢查來源狀態。':'此頁尚未載入搜尋結果；可搜尋或開啟已儲存圖譜。'));else messages.push(AtlasI18n.t(graphFailure?'新聞與關聯已載入':'圖譜已就緒'));}

  $('activityText').textContent=messages.join(' · ');
  updateViewCounters();
  $('activitySpinner').hidden=!(controller||relationActivity.busy||graphRetryBusy||['queued','calculating','render-wait'].includes(viewRelationState.phase));
  $('cancelOperation').hidden=!(controller||relationActivity.busy);
  $('retryGraph').hidden=!graphFailure;$('retryGraph').disabled=graphRetryBusy;
  $('modeNetwork').disabled=graphRetryBusy;
  $('modeNetwork').textContent=AtlasI18n.t('3D 關聯');
  $('modeNetwork').title=graphFailure?AtlasI18n.t('重試建立 3D；目前新聞會保留。'):'';
}
function updateGraphMessage(){
  $('graphFallback').hidden=!graphFailure;
  updateActivity();
  if(graphFailure){
    $('graphFallbackSummary').textContent=AtlasI18n.t('3D 無法使用，已切換時間軸；新聞與關聯搜尋仍可使用。');
    $('graphFailureReason').textContent=graphFailure.message;
  }
  const failure=viewMode==='network'&&graphFailure;
  $('empty').hidden=!failure&&articles.length>0&&(viewMode==='timeline'||!!graph);
  if(failure){
    const title=failure.kind==='context-lost'?'3D 渲染中斷（WebGL context lost）。':'3D 初始化失敗（WebGL）。';
    $('empty').replaceChildren(el('p',AtlasI18n.t(title)),el('p',failure.message,'raw'),el('p',AtlasI18n.t('新聞仍可使用，或切換時間軸查看。Chrome 請檢查設定 → 系統 → 圖形加速及 chrome://gpu，完成後重新載入頁面。')));
  }else $('empty').textContent=controller?AtlasI18n.t('正在讀取新聞；可切換視圖。'):viewSources().length?'目前來源沒有可顯示新聞。':'請勾選至少一個顯示來源。';
}
function reportGraphFailure(kind,message){
  graphFailure={kind,message:String(message)};
  renderBudget=[100,200,400,800,1200,1600,2000,2400].filter(value=>value<=Math.max(100,renderBudget/2)).pop();$('renderBudget').value=String(renderBudget);
  console.error('[GraphNews 3D]',kind,graphFailure.message);
  if(kind==='context-lost'&&graph)switchMode('timeline');else updateGraphMessage();
}
// Capture before construction: a failed renderer never returns a canvas handle.
$('graph').addEventListener('webglcontextcreationerror',event=>{webglCreationReason=event.statusMessage||'';},true);
$('graph').addEventListener('webglcontextlost',event=>{event.preventDefault();reportGraphFailure('context-lost',event.statusMessage||'WebGL context lost');},true);
$('graph').addEventListener('webglcontextrestored',()=>{if(graphFailure?.kind==='context-lost'){graphFailure=null;updateGraphMessage();}},true);
function initializeGraph(){
try {
  graph = ForceGraph3D()($('graph')).backgroundColor('#090f1b').nodeId('id')
    .nodeColor(nodeColor).nodeVal(3).nodeResolution(6).nodeOpacity(.95)
    .linkColor(linkColor).linkWidth(.6).linkOpacity(1)
    .onNodeHover(n => {if(interaction&&interaction.supported!==false)return;setHovered(n);})
    .onNodeClick(n => showArticle(n)).onBackgroundClick(()=>{if(!interaction)clearGraphSelection();}).onNodeDragEnd(n => { n.fx = undefined; n.fy = undefined; n.fz = undefined; rememberNetwork(); graph.d3ReheatSimulation(); });
  graph.d3Force('charge').strength(-45); graph.d3Force('link').distance(l => AtlasView.linkStyle(l,internalLengths.get(edgeKey(l))).distance).strength(l=>AtlasView.linkStyle(l).strength); graph.cooldownTime(reducedMotion ? 800 : 8000);
  graph.d3Force('source-cluster', alpha => {
    if (!isSeparate()) return;
    const active = viewSources();
    for (const n of graph.graphData().nodes) { const center = (active.indexOf(n.display_provider) - (active.length - 1) / 2) * 240; n.vx = (n.vx || 0) + (center - (n.x || 0)) * .035 * alpha; n.vy = (n.vy || 0) - (n.y || 0) * .012 * alpha; n.vz = (n.vz || 0) - (n.z || 0) * .012 * alpha; }
  });
  graph.d3Force('preserve-position', alpha=>{if(isSeparate())return;for(const n of graph.graphData().nodes){if(!n.anchor)continue;for(const k of ['x','y','z'])n['v'+k]=(n['v'+k]||0)+(n.anchor[k]-(n[k]||0))*.012*alpha;}});
  graph.renderer?.()?.setPixelRatio?.(Math.min(globalThis.devicePixelRatio||1,renderBudget<800?1:1.5));
  const size=$('stage').getBoundingClientRect();graph.width(size.width).height(size.height);
  graphFailure=null;
} catch (error) { graph = null; reportGraphFailure('initialization',[error.message||String(error),webglCreationReason].filter(Boolean).join(' · ')); }
}
initializeGraph();
new ResizeObserver(()=>{const r=$('stage').getBoundingClientRect();graph?.width(r.width).height(r.height);if(viewMode==='timeline')renderTimeline();}).observe($('stage'));
function disposeGraph(){
    // A damaged renderer must not prevent construction of its replacement.
    for(const dispose of [()=>rememberNetwork(),()=>interaction?.dispose(),()=>timeSizer?.dispose(),()=>glowLayer?.dispose(),()=>graph?.pauseAnimation(),()=>graph?._destructor?.()]){try{dispose();}catch(error){console.warn('[GraphNews cleanup]',error.message);}}
    graph=null;lastNetworkRender=null;interaction=null;timeSizer=null;glowLayer=null;$('graph').replaceChildren();webglCreationReason='';
}
async function retryGraph(){
  if(graphRetryBusy)return;graphRetryBusy=true;updateActivity();
  await new Promise(resolve=>setTimeout(resolve,30));
  try{
    disposeGraph();
    initializeGraph();attachGraphBehaviors();
    if(!graphFailure&&graph){viewMode='network';applyMode();rebuild();}
    else{viewMode='timeline';applyMode();renderTimeline();}
  }catch(error){reportGraphFailure('initialization',error.message||String(error));viewMode='timeline';applyMode();renderTimeline();}
  finally{graphRetryBusy=false;updateGraphMessage();}
}
$('retryGraph').onclick=retryGraph;
$('renderBudget').value=String(renderBudget);
$('renderBudget').onchange=()=>{renderBudget=AtlasView.renderLimit($('renderBudget').value);renderNetwork();updateActivity();};
$('cancelOperation').onclick=()=>{if(controller)$('cancel').onclick();else relationUI?.cancel();};
function graphTrace(){return highlightMode==='category'&&viewMode==='network'?categoryTrace:activeTrace;}
function graphHasHighlight(){return highlightMode==='category'&&viewMode==='network'?categoryTrace.nodes.size>0:focusRoot()!==null;}
function refreshCategory(){
  const nodes=new Map(focusView.articles.filter(a=>graphChannel&&(a.channels||[]).some(c=>c.id===graphChannel)).map(a=>[a.id,{depth:0,parents:[],strength:1}]));
  categoryTrace={nodes,edges:new Set(focusView.relations.filter(e=>nodes.has(AtlasView.endpoint(e.source))&&nodes.has(AtlasView.endpoint(e.target))).map(AtlasView.identity)),roots:[]};
}
function syncHighlightUI(){
  const category=highlightMode==='category';
  $('highlightModeSwitch').checked=category;
  $('graphChannelLabel').hidden=!category;
  for(const id of ['rootQuery','rootLimit','rootSearchSubmit'])$(id).disabled=category&&viewMode==='network'||rootSearchBusy;
  $('highlightStatus').textContent=AtlasI18n.t(category?(viewMode!=='network'?'分類亮光僅套用 3D；root 選取保留。':!graphChannel?'選擇分類；點擊新聞只查看詳情。':categoryTrace.nodes.size?'分類模式：點擊只查看新聞，不改 root。':'此分類在目前來源沒有新聞。'):'點擊新聞或搜尋 roots');
  if(category&&viewMode==='network'&&graphChannel)$('highlightStatus').textContent+=' '+categoryTrace.nodes.size;
}
function setHighlightMode(mode){highlightMode=mode;hovered=null;interaction?.clear();idleFocus?.stop();refreshCategory();syncHighlightUI();renderNetwork();refreshFocus();if(mode==='root')touchFocus();}
function clearGraphSelection(){if(highlightMode==='category'&&viewMode==='network'){graphChannel='';$('graphChannel').value='';refreshCategory();syncHighlightUI();refreshFocus();}else clearFocus();}
$('highlightModeSwitch').onchange=()=>setHighlightMode($('highlightModeSwitch').checked?'category':'root');
$('graphChannel').onchange=()=>{graphChannel=$('graphChannel').value;refreshCategory();syncHighlightUI();renderNetwork();refreshFocus();};
function nodeColor(n){const base=colors[n.display_provider||n.source.provider]||'#b9d8df';if(!graphHasHighlight())return base;const hit=graphTrace().nodes.get(n.id);if(!hit)return AtlasGlow.tint(base,glowConfig.background);return AtlasGlow.tint(base,Math.max(.12,Math.pow(glowConfig.decay,hit.depth)));}
function edgeLight(l){const id=typeof l.target==='object'?l.target.id:l.target,other=typeof l.source==='object'?l.source.id:l.source;return Math.pow(glowConfig.decay,Math.max(graphTrace().nodes.get(id)?.depth||0,graphTrace().nodes.get(other)?.depth||0));}
function linkColor(l){if(!graphHasHighlight())return l.scope==='cross'?'rgba(244,205,132,.45)':'rgba(130,200,210,.4)';return graphTrace().edges.has(AtlasView.identity(l))?`rgba(140,255,220,${Math.max(.05,edgeLight(l))})`:`rgba(120,155,180,${glowConfig.background*.25})`;}
function edgeStyle(l){if(!graphHasHighlight())return {color:l.scope==='cross'?'#f4cd84':'#82c8d2',opacity:l.scope==='cross'?.45:.4};return graphTrace().edges.has(AtlasView.identity(l))?{color:'#8cffdc',opacity:Math.max(.05,edgeLight(l))}:{color:'#789bb4',opacity:glowConfig.background*.25};}
function acquireRoot(n){if(!n||lockedRoots.length||highlightMode==='category'&&viewMode==='network')return;lockedRoots=[n.id];pinnedRoot=n.id;keywordLocked=false;rootSearchState=null;$('rootResults').replaceChildren();refreshFocus();}
function setHovered(n){const id=n?.id||null;if(hovered!==id){hovered=id;refreshFocus();}touchFocus();showPreview(n);}
function clearFocus(){rootSearchTicket++;idleFocus?.stop();interaction?.clear();lockedRoots=[];keywordLocked=false;rootSearchState=null;pinnedRoot=null;hovered=null;$('rootResults').replaceChildren();refreshFocus();showPreview(null);if(viewMode==='timeline')renderTimeline();}
function touchFocus(){if(highlightMode!=='category'&&focusRoot()!==null&&!keywordLocked&&!rootSearchBusy)idleFocus?.touch();}
function refreshFocus(){pinnedRoot=focusRoot();activeTrace=focusTraceCache(focusView.relations,lockedRoots,exploration);candidateTrace=previewTraceCache(relations,!pinnedRoot&&hovered?[hovered]:[],exploration);showTrace(pinnedRoot,activeTrace);if(highlightMode==='category'&&viewMode==='network')$('traceStatus').textContent='';else if(!pinnedRoot&&hovered)$('traceStatus').textContent=AtlasI18n.t('候選 tree 預覽 · 點一下確認 root')+' · '+candidateTrace.nodes.size;glowLayer?.refresh();}
function showTrace(id,trace){$('traceStatus').textContent=id?`延伸 ${trace.nodes.size-(trace.roots?.length||1)} 個節點 · 最多 ${exploration.depth} 層 · 每節點 ${exploration.branchLimit} 分支`+(trace.truncated?' · 已達顯示上限':''):'';}
function showPreview(n) { const box = $('preview'); box.replaceChildren(); box.hidden = !n; if (!n) return;if(!focusRoot())box.append(el('div',AtlasI18n.t('預覽中 · 點一下進入星系'),'meta')); box.append(el('div', (n.source.publisher || n.source.provider) + ' · ' + (n.display_sources || [n.source.provider]).map(p=>sourceNames[p]).join('／'), 'meta'), el('strong', n.title,'raw'), el('div', date(n.published_at), 'muted')); }
$('graph').addEventListener('pointermove', e => { const box = $('preview'), r = $('stage').getBoundingClientRect(); if (!box.hidden) { box.style.left = Math.max(8, Math.min(r.width - box.offsetWidth - 8, e.clientX - r.left + 18)) + 'px'; box.style.top = Math.max(8, Math.min(r.height - box.offsetHeight - 8, e.clientY - r.top + 18)) + 'px'; } });
function evidenceText(edge) {
  if(globalThis.AtlasRelations)return AtlasRelations.evidence(edge);
  return (edge.evidence || []).map(e => e.entity ? `${e.entity}：${e.source.method === 'provider_ticker' ? AtlasI18n.t('來源標註') : AtlasI18n.t('文章文字')}「${e.source.evidence}」↔ ${e.target.method === 'provider_ticker' ? AtlasI18n.t('來源標註') : AtlasI18n.t('文章文字')}「${e.target.evidence}」` : `共同詞：${(e.title_terms || []).join('、')}；標題相似度 ${e.title_similarity}`).join('；');
}
function showArticle(n,pin=true) {
  if(pin)globalThis.AtlasRuntime?.record('article',n.id);
  selected = n.id;if(pin){priceLens?.select(n);if(AtlasTimeline.day(n.published_at)!==null){timeFocus.date=new Date(AtlasTimeline.day(n.published_at)).toISOString().slice(0,10);syncTimeFocus();AtlasUI.write('timeFocus',timeFocus);}acquireRoot(n);touchFocus();if(graph&&viewMode==='network'&&!graph.graphData().nodes.some(a=>a.id===n.id))renderNetwork();}
  const root = $('article'); root.replaceChildren(); const card = el('div', null, 'card selected-news');card.append(el('div',AtlasI18n.t('目前選取新聞'),'selected-news-label'));
  card.append(el('div', `${n.source.publisher || n.source.provider} · ${date(n.published_at)}`, 'meta raw'), el('h3', n.title,'raw'), el('p', n.summary || '來源未提供摘要。', n.summary?'muted raw':'muted'));
  for (const entity of n.entities || []) card.append(el('span', `${entity.id} · ${entity.method === 'provider_ticker' ? '來源標註' : '文字辨識'}`, 'tag'));
  const link = el('a', '閱讀原文 ↗'); link.href = n.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(el('p'), link);
  if(n.source.country)card.append(el('p',AtlasI18n.t('RSS 搜尋版本')+': '+n.source.country+' · '+(n.source.language||''),'muted raw'));
  if (n.source.via) card.append(el('p', '取得途徑：' + n.source.via, 'muted'));
  const priceNote=priceLens?.describe(n);if(priceNote)card.append(el('p',priceNote,'raw price-detail'));
  root.append(card, el('h3', 'Channel 分類依據'));
  if(pin){const page=$('newsPage');if(page)page.scrollTop=0;else $('detail').scrollTop=0;}
  for(const c of n.channels||[]){const block=el('div',null,'channel-evidence');block.append(el('strong',c.name+(c.id===n.primary_channel?' · 主要分類':''),c.id.startsWith('custom-')?'raw':''),el('p',c.evidence.length?c.evidence.map(e=>`${e.field==='title'?AtlasI18n.t('標題'):AtlasI18n.t('摘要')}：${e.match}`).join('；'):'未命中目前分類規則',c.evidence.length?'raw':''));root.append(block);}
  root.append(el('h3', '與這篇新聞的關聯'));
  const related = relations.filter(r => r.source === n.id || r.target === n.id);
  for (const edge of related) {
    const target = articles.find(a => a.id === (edge.source === n.id ? edge.target : edge.source)); if (!target) continue;
    const item = el('div', null, 'card'), button = el('button', target.title,'raw');
    button.addEventListener('click', () => showArticle(target));
    item.append(el('div', `${edge.scope==='cross'?'跨來源 · ':''}${relationNames[edge.type] || edge.type} · 相隔 ${edge.days_apart ?? '—'} 天`, 'meta'), button, el('p', evidenceText(edge), 'muted raw'));
    root.append(item);
  }
  if (!related.length) root.append(el('p',basePayload.relation_scope==='view'?'目前視圖尚無此新聞的連線；未完成計算或不在視圖內，不代表沒有關聯。':'目前沒有足夠文字依據建立關聯，保留為獨立節點。','muted'));
  renderNodeJson(n);
  $('detail').classList.add('open');if(pin&&viewMode==='timeline')renderTimeline();
}
function rebuild(payload,relationUpdate=false) {
  rootSearchTicket++;
  interaction?.clear();
  const previousCount = articles.length;
  if (payload) {basePayload = payload;classificationEpoch++;if(!relationUpdate){viewRevision++;viewRequestedSettings=null;completedRelationViews.clear();if(!restoringRelations){restoredRelationSeed=null;restoredRelationViews=[];}}}
  if(basePayload.channel_definitions)channelDefinitions=basePayload.channel_definitions;
  renderChannelFilter();
  currentView = AtlasView.select(basePayload, viewSources(), isSeparate());
  currentView.relations=AtlasView.filterEdges(currentView.relations,exploration);
  focusView=currentView;refreshCategory();syncHighlightUI();
  syncTimelineRange(currentView.articles);
  syncTimeFocus();
  if(viewMode==='timeline') currentView=AtlasTimeline.filter(currentView,channelFilter,timelineCutoff);
  articles = currentView.articles; relations = currentView.relations;lockedRoots=lockedRoots.filter(id=>focusView.articles.some(a=>a.id===id));pinnedRoot=focusRoot();if(!lockedRoots.length)keywordLocked=false;if(rootSearchState)renderRootResults();
  exportMeta.total_articles = basePayload.total_articles ?? articles.length;
  hovered = null;activeTrace=AtlasView.trace([],null);showTrace(null,activeTrace); showPreview(null);
  $('count').textContent = articles.length; $('edges').textContent = relations.length;
  updateGraphMessage(); $('export').disabled = !focusView.articles.length;
  $('saveDB').disabled = !focusView.articles.length || !!controller || saving;
  const groups = AtlasView.groups(basePayload);
  for (const p of providers) $('view-count-'+p).textContent = groups[p]?.articles.length || 0;
  const total = viewSources().reduce((n,p)=>n+(groups[p]?.total_articles ?? groups[p]?.articles.length ?? 0),0);
  $('viewLimit').textContent = `${AtlasI18n.t('所選來源')} ${total} · ${AtlasI18n.t('完整資料保留')}`;
  renderArticleList();
  if (selected) { const n = articles.find(a => a.id === selected); if (n) showArticle(n,false); else { selected = null; $('nodeJson').replaceChildren(); $('article').replaceChildren(el('p', '點擊新聞查看來源與關聯依據。', 'muted')); } }
  renderNetwork();
  refreshFocus();if(viewMode==='timeline')renderTimeline();
  if(payload&&!relationUpdate)relationUI?.onPayload(payload);
}
function renderArticleList(page=articleListPage){
  AtlasUI.pagedRows($('list'),articles,a=>{const b=el('button');b.setAttribute('data-article-id',a.id);b.append(el('div',(a.display_sources||[]).map(p=>sourceNames[p]).join('／')+' · '+date(a.published_at),'meta'),el('div',a.title,'raw'));b.addEventListener('click',()=>showArticle(a));return b;},{page,onPage:value=>{articleListPage=value;}});
}
function renderNetwork(){
  scheduleViewRelations();
  if (graph && viewMode==='network') {
   try {
    const priority=viewPriority();
    const slice=AtlasView.renderSlice(currentView,renderBudget,priority);
    renderedCount=slice.articles.length;renderedEdges=slice.relations.length;
    $('viewLimit').textContent=`3D ${renderedCount}/${currentView.articles.length} · ${AtlasI18n.t('連線')} ${renderedEdges}/${currentView.relations.length}`;
    const same=(a,b)=>a.length===b.length&&a.every((item,i)=>item===b[i]);
    if(lastNetworkRender?.graph===graph&&!restoredPositions.size&&same(slice.articles,lastNetworkRender.slice.articles)&&same(slice.relations,lastNetworkRender.slice.relations)){updateActivity();return;}
    rememberNetwork();
    const old=new Map(graph.graphData().nodes.map(n=>[n.id,n]));
    const nodes = slice.articles.map(a => {
      const pos=restoredPositions.get(a.id)||networkPositions.get(a.id)||networkPositions.get(a.display_provider+'::'+a.article_id)||networkPositions.get(a.article_id);
      const n=Object.assign(old.get(a.id)||{},a,pos||{});
      if(pos)n.anchor={x:pos.x,y:pos.y,z:pos.z};
      return n;
    });
    restoredPositions.clear();
    graph.graphData({ nodes, links: slice.relations.map(r => ({ ...r, from: r.source, to: r.target })) });
    lastNetworkRender={graph,slice};
    if (articles.length && !old.size) { clearTimeout(fitTimer); fitTimer = setTimeout(() => graph?.zoomToFit(reducedMotion ? 0 : 500, 65), 1000); }
   } catch(error) {reportGraphFailure('context-lost',error.message||String(error));}
  }
  updateActivity();
}
function rememberNetwork(distances=false){
  if(!graph)return;
  const data=graph.graphData();
  for(const n of data.nodes||[])if(['x','y','z'].every(k=>Number.isFinite(n[k])))networkPositions.set(n.id,{x:n.x,y:n.y,z:n.z});
  if(distances){const nodes=new Map(data.nodes.map(n=>[n.id,n]));for(const l of data.links||[]){if(l.scope==='cross')continue;const a=typeof l.source==='object'?l.source:nodes.get(l.source),b=typeof l.target==='object'?l.target:nodes.get(l.target);if(a&&b){const length=Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);if(Number.isFinite(length)&&length>0)internalLengths.set(edgeKey(l),length);}}}
}
function renderChannelFilter(){
  const select=$('channelFilter');select.replaceChildren();const all=el('option','全部分類');all.value='all';select.append(all);
  for(const c of channelDefinitions){const option=el('option',c.name,c.id.startsWith('custom-')?'raw':'');option.value=c.id;select.append(option);}
  if(channelFilter!=='all'&&!channelDefinitions.some(c=>c.id===channelFilter))channelFilter='all';
  select.value=channelFilter;
  const graphSelect=$('graphChannel');graphSelect.replaceChildren();const placeholder=el('option','選擇分類');placeholder.value='';graphSelect.append(placeholder);
  for(const c of channelDefinitions){const option=el('option',c.name,c.id.startsWith('custom-')?'raw':'');option.value=c.id;graphSelect.append(option);}
  if(!channelDefinitions.some(c=>c.id===graphChannel))graphChannel='';graphSelect.value=graphChannel;
}
function syncTimelineRange(rows){
  const range=AtlasTimeline.range(rows,{start:exportMeta.start,end:exportMeta.end});timelineBounds=range;
  const slider=$('timelineCutoff');slider.min=0;slider.max=range.days;
  if(!timelineCutoff||timelineCutoff<range.startDate||timelineCutoff>range.endDate)timelineCutoff=range.endDate;
  slider.value=Math.round((AtlasTimeline.day(timelineCutoff)-range.start)/86400000);slider.disabled=!rows.length;
  $('cutoffLabel').textContent=timelineCutoff+' UTC';
}
function sizeBounds(){const base=timelineBounds||AtlasTimeline.range([],{start:$('start').value,end:$('end').value});return priceLens?.bounds(base)||base;}
function displaySizeBounds(){return priceLens?.displayBounds(sizeBounds())||sizeBounds();}
function syncTimeFocus(){
  const bounds=displaySizeBounds(),full=sizeBounds();
  const stamp=AtlasTimeline.day(timeFocus.date);
  timeFocus.date=new Date(stamp===null?full.end:Math.min(full.end,Math.max(full.start,stamp))).toISOString().slice(0,10);
  $('timeSizeEnabled').checked=timeFocus.enabled;$('timeSizeEnabled').disabled=!timeLensAvailable;
  const slider=$('timeFocusSlider');slider.min=0;slider.max=bounds.days;slider.value=Math.round((AtlasTimeline.day(timeFocus.date)-bounds.start)/86400000);
  slider.disabled=!timeLensAvailable||!timeFocus.enabled||!focusView.articles.length||!bounds.days;
  slider.setAttribute('aria-valuetext',timeFocus.date+' UTC');
  $('timeFocusDate').textContent=timeFocus.date+' UTC';
  $('timeFocusStart').textContent=bounds.startDate;$('timeFocusEnd').textContent=bounds.endDate;
  const ticks=$('timeFocusTicks');ticks.replaceChildren();
  for(const tick of AtlasTimeline.timeTicks(bounds)){const span=el('span',tick.label);span.style.left=tick.position+'%';ticks.append(span);}
  $('timeFocusBar').classList.toggle('disabled',!timeFocus.enabled||!timeLensAvailable);
  timeLens?.paint();timeSizer?.refresh();priceLens?.paint();
  layoutTimeBar();
}
function layoutTimeBar(){
  const panel=timePanel?.state(),floating=panel&&(globalThis.AtlasDock?.docked($('timeFocusBar'))||panel.collapsed||panel.x!==0||panel.y!==0);
  const bottom=floating?54:($('timeFocusBar').offsetHeight||104)+64;
  $('timeline').style.bottom=(bottom+30)+'px';$('traceStatus').style.bottom=bottom+'px';
}
function updateTimeCurve(values){
  timeFocus=AtlasTimeline.timeSettings({...timeFocus,...values});
  syncTimeFocus();AtlasUI.write('timeFocus',timeFocus);touchFocus();
  if(viewMode==='timeline')renderTimeline();
}
function updateTimeFocus(){
  timeFocus.enabled=$('timeSizeEnabled').checked;
  priceLens?.clearSelection();if(timelineBounds)timeFocus.date=new Date(displaySizeBounds().start+Number($('timeFocusSlider').value)*86400000).toISOString().slice(0,10);
  syncTimeFocus();AtlasUI.write('timeFocus',timeFocus);touchFocus();glowLayer?.refresh();
  if(viewMode==='timeline')renderTimeline();
}
function positionPreview(event){
  if(!event)return;const box=$('preview'),r=$('stage').getBoundingClientRect();const bounds=event.currentTarget?.getBoundingClientRect?.();
  const x=Number.isFinite(event.clientX)?event.clientX:bounds?.left||r.left+30,y=Number.isFinite(event.clientY)?event.clientY:bounds?.top||r.top+30;
  box.style.left=Math.max(8,Math.min(r.width-box.offsetWidth-8,x-r.left+16))+'px';box.style.top=Math.max(8,Math.min(r.height-box.offsetHeight-8,y-r.top+16))+'px';
}
function renderTimeline(){
  if(viewMode!=='timeline')return;
  showPreview(null);
  $('timeline').style.top=(($('graphTools').offsetHeight||220)+25)+'px';
  const width=Math.max(900,$('stage').getBoundingClientRect().width)*(Number($('timelineZoom').value)||1);
  $('timelineZoomValue').textContent=(Number($('timelineZoom').value)||1)+'×';
  $('timelineZoomValue').setAttribute('data-zoom',Number($('timelineZoom').value)||1);
  const renderer=AtlasTimeline.renderDensity;
  const model=renderer($('timeline'),currentView,channelDefinitions,{width,start:timelineBounds?.startDate,end:timelineBounds?.endDate,channel:channelFilter,zoom:Number($('timelineZoom').value)||1,colors,exploration,glow:glowConfig,rootId:pinnedRoot,getRoots:()=>lockedRoots,getTrace:()=>activeTrace,nodeScale:n=>priceLens?.scale(n,AtlasTimeline.timeScale(n,timeFocus,sizeBounds()),timeFocus.enabled)??AtlasTimeline.timeScale(n,timeFocus,sizeBounds()),getPreviewRoot:()=>hovered,onTrace:showTrace,onBucketSelect:showBucket,onBucketHover:previewBucket,onSelect:showArticle,onHover:(n,e)=>{setHovered(n);positionPreview(e);}});
  if(timelineFocusRequested&&model.nodes.length){const focused=model.nodes.filter(n=>(n.articles||[n.article]).some(a=>lockedRoots.includes(a.id)));const related=model.nodes.filter(n=>(n.articles||[n.article]).some(a=>activeTrace.nodes.has(a.id)));const candidates=focused.length?focused:related.length?related:model.nodes;const anchor=candidates.reduce((a,b)=>a.x<b.x?a:b);$('timeline').scrollLeft=Math.max(0,anchor.x-210);$('timeline').scrollTop=Math.max(0,anchor.y-Math.max(56,(($('timeline').clientHeight||156)+48)/2));timelineFocusRequested=false;}
}
function applyMode(){
  if(graphFailure)viewMode='timeline';
  const timeline=viewMode==='timeline';$('timeBellEditor').open=!timeline&&AtlasUI.read('timeCurveOpen',true);layoutTimeBar();$('graph').hidden=timeline;$('glowCanvas').hidden=timeline;glowLayer?.refresh();$('timeline').hidden=!timeline;$('timelineControls').hidden=!timeline;
  $('modeNetwork').classList.toggle('active',!timeline);$('modeTimeline').classList.toggle('active',timeline);
  $('modeNetwork').setAttribute('aria-pressed',String(!timeline));$('modeTimeline').setAttribute('aria-pressed',String(timeline));
  $('stageHint').textContent=timeline?'橫向捲動／縮放 · 發布日期（UTC）× 主要分類 · 連線非因果':'拖曳節點牽動關聯 · 空白旋轉 · Ctrl＋左鍵拖拉平移 · 金色線跨來源';
  if(graph){if(timeline)graph.pauseAnimation();else graph.resumeAnimation();}
  syncHighlightUI();updateGraphMessage();
}
function switchMode(mode){if(mode==='network'&&(graphFailure||!graph)){retryGraph();return;}interaction?.clear();rememberNetwork(true);timelineFocusRequested=true;viewMode=mode;applyMode();rebuild();}

function updateDB(stats) { if (stats) $('dbStatus').textContent = `DB ${stats.articles} 筆 · 圖譜快照 ${stats.snapshots || 0} 份`; }
function paintProgress() {
  const root = $('status'); root.replaceChildren();
  const composition = $('composition'); composition.replaceChildren();
  const values = Object.entries(sourceStates), total = values.reduce((n,[,v])=>n+(v.total || 0),0);
  const finished = values.filter(([,v])=>v.done).length;
  $('progress').max = Math.max(1,values.length); $('progress').value = finished;
  $('progressLabel').textContent = `${finished} / ${values.length} 個來源完成`;
  for (const [source,v] of values) {
    const row = el('div',null,'source-progress'), title = el('div',null,'source-title'), dot = el('i'); dot.style.background=colors[source];
    title.append(dot,el('strong',sourceNames[source]),el('small',v.phase || '等待中',v.error?'error':''));
    const counts = el('div',null,'source-counts');
    for (const [label,num] of [['DB',v.cached||0],['新增',v.new||0],['合計',v.total||0]]) { const part=el('span',label+' ');part.append(el('b',num));counts.append(part); }
    row.append(title,counts);
    if (v.error || v.details?.length) { const details=el('details'), summary=el('summary',v.error?'查看錯誤':'覆蓋／來源說明');details.append(summary); if(v.error)details.append(el('p',v.error,'error'));for(const line of v.details||[])details.append(el('p',line));row.append(details); }
    root.append(row);
    for(const [kind,value] of [['cached',v.cached||0],['new',v.new||0]]) { if(!value)continue;const seg=el('div',null,'segment '+kind);seg.style.width=(value/Math.max(1,total)*100)+'%';seg.style.backgroundColor=colors[source];seg.title=`${sourceNames[source]} · ${kind==='cached'?'DB 既有':'本次新增'} ${value} 筆`;composition.append(seg); }
  }
  composition.setAttribute('aria-label',values.map(([s,v])=>`${sourceNames[s]}：DB ${v.cached||0}，新增 ${v.new||0}`).join('；') || '尚無資料');
}
function acceptSearchGraph(payload,final=false){
  const count=payload.total_articles??Object.values(AtlasView.groups(payload)).reduce((n,g)=>n+g.articles.length,0);
  if(pendingSearchMeta){
    if(!count&&!final&&focusView.articles.length)return;
    exportMeta=pendingSearchMeta;pendingSearchMeta=null;articleListPage=0;clearFocus();timelineCutoff=null;
    networkPositions.clear();internalLengths.clear();selected=null;$('nodeJson').replaceChildren();$('article').replaceChildren();
  }
  if(globalThis.AtlasViewRelations)payload={...payload,relation_scope:'view'};
  rebuild(payload);
}
function handleEvent(msg) {
  if(msg.type==='phase'||msg.type==='heartbeat'){
    if(msg.phase)searchPhase=msg.phase;
    $('elapsed').textContent=AtlasI18n.t(searchPhase==='relations'?'新聞已載入，正在計算關聯':'正在讀取新聞')+' · '+(msg.elapsed||0)+'s';updateActivity();return;
  }
  if(msg.type==='graph'){acceptSearchGraph(msg.graph,true);updateActivity();return;}
  if(msg.type==='graph_error'){operationNotice=AtlasI18n.t(msg.message);updateActivity();return;}
  if (msg.type === 'status') {
    const v=sourceStates[msg.source] ||= {cached:0,new:0,total:0};
    v.phase=msg.phase==='fetching' ? `讀取中 · ${msg.requests || 0} 次請求` : '檢查／補抓中';
    if(Number.isFinite(msg.cached)) Object.assign(v,{cached:msg.cached,new:msg.new,total:msg.total});
    paintProgress(); return;
  }
  if (msg.type === 'cache') {
    for(const [s,count] of Object.entries(msg.counts || {})) sourceStates[s]={cached:count,new:0,total:count,phase:'檢查快取'};
    acceptSearchGraph(msg.graph);paintProgress(); return;
  }
  if (msg.type === 'source') {
    sourceArticles.set(msg.source, msg.articles);
    acceptSearchGraph(msg.graph || { articles: [...sourceArticles.values()].flat(), relations: [] });
    const c=msg.cache, v=sourceStates[msg.source] ||= {};
    const cached=c?.existing_articles ?? v.cached ?? 0;
    Object.assign(v,{cached,new:c?.new_articles ?? Math.max(0,msg.articles.length-cached),total:msg.articles.length,done:true,error:msg.error,
      phase:msg.error ? (msg.error_code==='missing_ticker'?'已略過':'部分／失敗') : c?.reused?'快取完成':'完成',
      details:[...(c?[`API 完整 ${c.complete_days}/${c.requested_days} 天 · RSS 快照 ${c.snapshot_days} 天`,...(c.missing_ranges?.length?['仍有未覆蓋日期，可稍後補抓']:[])]:[]),...(msg.warnings||[])]});
    paintProgress();
    const meta=pendingSearchMeta||exportMeta;meta.sources ||= {}; meta.sources[msg.source] = { cache:c,error:msg.error,warnings:msg.warnings };
  }
  if (msg.type === 'done') { updateDB(msg.db); $('elapsed').textContent = `新聞載入完成 · ${msg.elapsed ?? 0} 秒`; }
}
const today = new Date(); $('end').value = today.toISOString().slice(0, 10); $('end').max = $('end').value;
$('start').value = new Date(today.getTime() - 6 * 86400000).toISOString().slice(0, 10); $('start').max = $('end').value;
const dateRange=AtlasDates.init($);
const persistSearchDraft=AtlasUI.initSearch($,dateRange);
dateRange.onChange(()=>{persistSearchDraft();if(!focusView.articles.length){timelineBounds=AtlasTimeline.range([],{start:$('start').value,end:$('end').value});syncTimeFocus();}});
if(timeLensAvailable)timeLens=AtlasTimeLens.init($,{getState:()=>({config:timeFocus,dates:sizeBounds(),viewport:displaySizeBounds(),components:priceLens?.components}),onChange:updateTimeCurve,onBusy:busy=>{if(!busy)touchFocus();}});
$('timeBellEditor').hidden=!timeLensAvailable;$('timeLensStatus').hidden=timeLensAvailable;
$('timeBellEditor').open=AtlasUI.read('timeCurveOpen',true);$('timeBellEditor').addEventListener('toggle',()=>{if(viewMode==='network')AtlasUI.write('timeCurveOpen',$('timeBellEditor').open);layoutTimeBar();});
$('timeSizeEnabled').onchange=updateTimeFocus;$('timeFocusSlider').oninput=updateTimeFocus;syncTimeFocus();
$('form').addEventListener('submit', async e => {
  if(e.target&&e.target!==$('form'))return;
  e.preventDefault(); if (controller) return;dateRange.refresh();persistSearchDraft();
  const sources = [...document.querySelectorAll('.sources input:checked')].map(x => x.value);
  const query = $('query').value.trim(), ticker = $('ticker').value.trim(), key = $('key').value.trim()||($('rememberKey').checked?AtlasUI.read('massiveKey',''):'');
  persistKey();
  const status = $('status'); status.replaceChildren(); sourceStates = {};
  if (!sources.length || (!query && !ticker)) { status.append(el('p', '請選擇來源並填寫關鍵字或股票代碼。', 'error')); return; }
  const request = ++currentSearch;controller = new AbortController();const searchController=controller;sourceArticles=new Map();
  const preferred=relationUI?.preferred();relationUI?.setSearchBusy(true);
  pendingSearchMeta={query,ticker,rss_region:$('rssRegion').value||'TW',start:$('start').value,end:$('end').value,sources:{}};
  const searchBody={...pendingSearchMeta,defer_relations:!!globalThis.AtlasViewRelations,sources,massive_key:key,force_refresh:$('forceRefresh').checked,relation_settings:preferred};
  searchPhase='sources';searchStarted=Date.now();operationNotice='';timelineFocusRequested=true;
  clearInterval(searchClock);searchClock=setInterval(updateActivity,1000);updateGraphMessage();
  $('submit').disabled = true; $('cancel').hidden = false; $('progress').hidden = false; $('progress').max = sources.length; $('progress').value = 0;
  $('elapsed').textContent = '正在檢查本地日期覆蓋…';
  for (const s of sources) sourceStates[s]={cached:0,new:0,total:0,phase:'等待中'};
  paintProgress();
  const abortTimer = setTimeout(() => searchController.abort(), 600000);
  try {
    const response = await fetch('/api/search', { method: 'POST', signal: searchController.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(searchBody) });
    if (!response.ok || !response.body) { let detail = `搜尋服務回應異常（${response.status}）`; try { detail = (await response.json()).error || detail; } catch {} throw new Error(detail); }
    const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', finished = false;
    while (true) {
      const { value, done } = await reader.read();if(request!==currentSearch||searchController.signal.aborted){await reader.cancel();return;} buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let idx;
      while ((idx = buffer.indexOf('\n')) >= 0) { const line = buffer.slice(0, idx); buffer = buffer.slice(idx + 1); if (!line) continue; const msg = JSON.parse(line); if (msg.type === 'done') finished = true; handleEvent(msg); }
      if (done) break;
    }
    if (!finished) throw new Error('搜尋連線提早中斷；已載入資料仍保留');
    if(pendingSearchMeta)acceptSearchGraph({articles:[],relations:[],relation_settings:preferred},true);
  } catch(err){if(request===currentSearch){operationNotice=AtlasI18n.t(err.name==='AbortError'?'已停止等待；已載入資料保留，伺服器可能繼續處理。':'搜尋失敗；目前圖譜保留。')+(err.name==='AbortError'?'':' '+err.message);status.append(el('p',operationNotice,'error'));}}
  finally{clearTimeout(abortTimer);if(request===currentSearch){controller=null;pendingSearchMeta=null;clearInterval(searchClock);relationUI?.setSearchBusy(false);$('submit').disabled=false;$('cancel').hidden=true;$('saveDB').disabled=!focusView.articles.length||saving;updateGraphMessage();}}
});
$('cancel').onclick=()=>{
  if(!controller)return;const previous=controller;controller=null;currentSearch++;previous.abort();pendingSearchMeta=null;clearInterval(searchClock);
  relationUI?.setSearchBusy(false);$('submit').disabled=false;$('cancel').hidden=true;$('saveDB').disabled=!focusView.articles.length||saving;
  operationNotice=AtlasI18n.t('已停止等待；已載入資料保留，伺服器可能繼續處理。');updateGraphMessage();
};
$('export').onclick = () => { const data = { schema_version: '2.0', search: exportMeta, articles:focusView.articles, relations:focusView.relations, view: {sources:viewSources(),separate:isSeparate(),mode:viewMode,channel_filter:channelFilter,cutoff:timelineCutoff,timeline_style:timelineStyle,exploration,glow:glowConfig,time_focus:timeFocus,price_focus:priceLens?.snapshot(),relation_settings:basePayload.relation_settings||relationUI?.applied(),focus:{mode:lockedRoots.length?(keywordLocked?'keyword':'single'):'overview',root_ids:lockedRoots,query:keywordLocked?rootSearchState?.query||'':'',limit:rootSearchState?.limit||3},channel_definitions:channelDefinitions}, relation_scope:basePayload.relation_scope||'complete',relation_scope_ids:basePayload.relation_scope_ids||null,relations_pending:basePayload.relation_scope==='view'?viewRelationState.phase!=='ready':!!basePayload.relations_pending, relation_note: '關聯來自明確代碼、文字實體、主題與標題相似規則；分數不是機率，連線不是因果。' }; const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })); const a = el('a'); a.href = url; a.download = 'news-atlas.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000); };
$('fit').onclick = () => {if(viewMode==='timeline'){$('timelineZoom').value=1;$('timeline').scrollLeft=0;renderTimeline();}else graph?.zoomToFit(reducedMotion ? 0 : 600, 60);};
$('openSearch').onclick = () => $('searchPanel').classList.add('open'); $('closeSearch').onclick = () => $('searchPanel').classList.remove('open'); $('closeDetail').onclick = () => $('detail').classList.remove('open'); $('openResults').onclick = () => $('detail').classList.add('open');
fetch('/api/status').then(r => r.json()).then(info => { updateDB(info.db); if (info.massive_configured){$('key').placeholder = '伺服器已設定 key，可留白';if(!$('key').value)$('keyStatus').textContent='主機已有金鑰，搜尋會自動沿用。';} }).catch(() => {});

for (const p of providers) $('view-'+p).addEventListener('change',()=>{rememberNetwork(true);rebuild();});
$('separateSources').addEventListener('change',()=>{rememberNetwork(true);selected=null;rebuild();});
function savedPayload() {
  rememberNetwork();for(const [id,pos] of restoredPositions)networkPositions.set(id,pos);const ids=new Set(focusView.articles.map(a=>a.id));
  const positions=[...networkPositions].filter(([id])=>ids.has(id)).map(([id,p])=>({id,...p}));
  const payload=AtlasView.snapshot(basePayload,AtlasView.select(basePayload,viewSources(),isSeparate()),viewSources(),isSeparate(),exportMeta,positions);
  Object.assign(payload.view,{selected_id:ids.has(selected)?selected:null,highlight_mode:highlightMode,graph_channel:graphChannel,render_budget:renderBudget,relation_cache_version:basePayload.relation_cache_version||0,relation_scope_sources:basePayload.relation_scope_sources||[],relation_scope:basePayload.relation_scope||'complete',relation_scope_ids:(basePayload.relation_scope_ids||[]).filter(id=>ids.has(id)),relations_pending:basePayload.relation_scope==='view'?viewRelationState.phase!=='ready':!!basePayload.relations_pending,mode:viewMode,channel_filter:channelFilter,cutoff:timelineCutoff,timeline_zoom:Number($('timelineZoom').value)||1,timeline_style:timelineStyle,exploration,glow:glowConfig,time_focus:timeFocus,price_focus:priceLens?.snapshot(),relation_settings:basePayload.relation_settings||relationUI?.applied(),focus:{mode:lockedRoots.length?(keywordLocked?'keyword':'single'):'overview',root_ids:lockedRoots,query:keywordLocked?rootSearchState?.query||'':'',limit:rootSearchState?.limit||3},channel_definitions:channelDefinitions});
  const sources=new Set(viewSources());
  payload.view.relation_views=[...restoredRelationViews,...completedRelationViews.values()].filter(v=>v.sources.every(p=>sources.has(p))).slice(-12);
  return payload;
}
$('saveDB').onclick = async () => {
  if (saving || controller || !focusView.articles.length) return;
  const payload=savedPayload(); saving=true; $('saveDB').disabled=true; $('saveStatus').textContent='儲存中…';
  try {const response=await fetch('/api/snapshots',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const saved=await response.json();if(!response.ok)throw new Error(saved.error || '儲存失敗');$('saveStatus').textContent=`已儲存「${saved.name}」· ${payload.view.sources.map(p=>sourceNames[p]).join('／')} 分開保存`;updateDB(saved.db);await loadSnapshots();}
  catch(error){$('saveStatus').textContent='儲存失敗：'+error.message;}
  finally{saving=false;$('saveDB').disabled=!focusView.articles.length || !!controller;}
};
async function loadSnapshots() {
  try {const response=await fetch('/api/snapshots');if(!response.ok)return;const data=await response.json();const root=$('snapshots');root.replaceChildren();for(const saved of data.snapshots || []){const button=el('button',`${saved.name} · ${date(saved.created_at)}`,'raw');button.addEventListener('click',()=>restoreSnapshot(saved.id));root.append(button);}if(!data.snapshots?.length)root.append(el('p','尚無已儲存圖譜','muted'));} catch {}
}
async function restoreSnapshot(id) {
  if(controller || saving){$('saveStatus').textContent='請等待目前搜尋／儲存完成。';return;}
  try {
    const response=await fetch('/api/snapshots/'+encodeURIComponent(id));const saved=await response.json();if(!response.ok)throw new Error(saved.error);
    restoringRelations=true;viewRelationJob?.cancel();
    networkPositions.clear();internalLengths.clear();
    for(const p of providers)$('view-'+p).checked=saved.view.sources.includes(p);
    $('separateSources').checked=saved.view.separate;exportMeta={...saved.search,sources:{}};
    // Restoring a graph must not overwrite the user's editable search draft.
    restoredPositions=new Map(saved.view.positions.map(p=>[p.id,p]));for(const [id,p] of restoredPositions)networkPositions.set(id,p);
    timelineFocusRequested=true;viewMode=saved.view.mode||'network';channelFilter=saved.view.channel_filter||'all';timelineCutoff=saved.view.cutoff||null;$('timelineZoom').value=saved.view.timeline_zoom||1;
    clearFocus();timeFocus=AtlasTimeline.timeSettings(saved.view.time_focus||{enabled:false});AtlasUI.write('timeFocus',timeFocus);glowConfig=AtlasGlow.settings(saved.view.glow||{});syncGlowControls();exploration=AtlasView.settings(saved.view.exploration||{});syncRelationControls();
    highlightMode=saved.view.highlight_mode||'root';graphChannel=saved.view.graph_channel||'';
    renderBudget=AtlasView.renderLimit(saved.view.render_budget||800);$('renderBudget').value=String(renderBudget);
    restoredRelationViews=saved.view.relation_views||[];
    restoredRelationSeed=saved.view.relation_cache_version===1&&!saved.view.relations_pending? saved : null;
    relationUI?.restore(saved.view.relation_settings);selected=null;$('article').replaceChildren(el('p','點擊新聞查看來源與關聯依據。','muted'));$('nodeJson').replaceChildren();applyMode();rebuild({relation_cache_version:saved.view.relation_cache_version,relation_scope_sources:saved.view.relation_scope_sources,relation_scope:saved.view.relation_scope,relation_scope_ids:saved.view.relation_scope_ids,relations_pending:saved.view.relations_pending,relation_settings:saved.view.relation_settings,source_graphs:saved.source_graphs,cross_relations:saved.cross_relations,channel_definitions:saved.view.channel_definitions?.length?saved.view.channel_definitions:channelCatalog});
    priceLens?.restore(saved.view.price_focus,saved.search?.ticker||'');
    const focus=saved.view.focus;if(focus?.root_ids?.length){lockedRoots=focus.root_ids.filter(id=>focusView.articles.some(a=>a.id===id));keywordLocked=focus.mode==='keyword'&&lockedRoots.length>0;$('rootQuery').value=focus.query||'';$('rootLimit').value=focus.limit||3;if(keywordLocked){rootSearchState={query:focus.query,limit:focus.limit,matches:lockedRoots.map(id=>({id,title:focusView.articles.find(a=>a.id===id).title,evidence:[]}))};renderRootResults();}refreshFocus();if(viewMode==='timeline')renderTimeline();touchFocus();}
    const savedSelection=focusView.articles.find(a=>a.id===saved.view.selected_id);if(savedSelection)showArticle(savedSelection,false);
    restoringRelations=false;if(viewMode==='network')renderNetwork();else scheduleViewRelations();
    $('saveStatus').textContent=`已載入「${saved.name}」· ${date(saved.created_at)}`;sourceStates={};
    for(const [s,g] of Object.entries(saved.source_graphs))sourceStates[s]={cached:g.articles.length,new:0,total:g.articles.length,done:true,phase:'已存圖譜'};
    paintProgress();$('elapsed').textContent='歷史圖譜快照 · 未重新搜尋';
    if(!saved.view.channel_definitions?.length)await reclassifyCurrent();
  }catch(error){$('saveStatus').textContent='載入失敗：'+error.message;}
  finally{restoringRelations=false;}
}
$('modeNetwork').onclick=()=>switchMode('network');$('modeTimeline').onclick=()=>switchMode('timeline');
$('channelFilter').onchange=()=>{channelFilter=$('channelFilter').value;timelineFocusRequested=true;rebuild();};
function zoomTimeline(value){
  const scroller=$('timeline'),old=Number($('timelineZoomValue').dataset?.zoom)||1;
  const next=Math.max(1,Math.min(4,Number(value)||1));
  const center=(scroller.scrollLeft+(scroller.clientWidth||0)/2-170)/old;
  $('timelineZoom').value=next;$('timelineZoomValue').textContent=next+'×';
  $('timelineZoomValue').setAttribute('data-zoom',next);renderTimeline();
  scroller.scrollLeft=Math.max(0,170+center*next-(scroller.clientWidth||0)/2);
}
$('timelineZoom').oninput=()=>zoomTimeline($('timelineZoom').value);
$('timelineZoomOut').onclick=()=>zoomTimeline(Number($('timelineZoom').value)-.5);
$('timelineZoomIn').onclick=()=>zoomTimeline(Number($('timelineZoom').value)+.5);
$('timelineCutoff').oninput=()=>{const range=timelineBounds||AtlasTimeline.range([],{start:exportMeta.start,end:exportMeta.end});timelineCutoff=new Date(range.start+Number($('timelineCutoff').value)*86400000).toISOString().slice(0,10);rebuild();};
$('timeline').addEventListener('click',e=>{if(!e.target.closest?.('[data-node-id], [data-bucket-id], button'))clearFocus();});
$('timeline').addEventListener('pointermove',e=>{if(!$('preview').hidden)positionPreview(e);});
function resetChannelForm(){editingChannel=null;$('channelName').value='';$('channelKeywords').value='';$('channelMatch').value='any';$('channelColor').value='#9dd6c4';$('channelSubmit').textContent='新增 Channel';$('channelCancel').hidden=true;}
function renderChannelManager(){
  const root=$('channelList');root.replaceChildren();
  for(const c of channelCatalog){const row=el('div',null,'channel-row');const title=el('strong',c.name+(c.builtin?' · 預設':''),c.builtin?'':'raw');title.style.color=c.color;row.append(title,el('p',c.keywords.join('、')||'未命中其他分類',c.keywords.length?'raw':''));
    if(!c.builtin){const edit=el('button','編輯');edit.type='button';edit.onclick=()=>{editingChannel=c.id;$('channelName').value=c.name;$('channelKeywords').value=c.keywords.join(', ');$('channelMatch').value=c.match;$('channelColor').value=c.color;$('channelSubmit').textContent='更新 Channel';$('channelCancel').hidden=false;};const remove=el('button','移除');remove.type='button';remove.onclick=()=>deleteChannel(c.id);row.append(edit,remove);}root.append(row);
  }
}
async function loadChannels(){try{const response=await fetch('/api/channels');if(!response.ok)throw new Error('無法讀取分類');const data=await response.json();channelCatalog=data.channels;renderChannelManager();if(!channelDefinitions.length){channelDefinitions=channelCatalog;renderChannelFilter();if(viewMode==='timeline')renderTimeline();}}catch(error){$('channelStatus').textContent=error.message;}}
async function reclassifyCurrent(){
  if(classifying)return;classifying=true;const epoch=classificationEpoch;
  const groups=AtlasView.groups(basePayload),rows=[];for(const [provider,g] of Object.entries(groups))for(const a of g.articles)rows.push({id:provider+'::'+a.id,title:a.title,summary:a.summary||''});
  $('reclassify').disabled=true;$('channelStatus').textContent='重新分類中…';
  try{const response=await fetch('/api/classify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({articles:rows})});const data=await response.json();if(!response.ok)throw new Error(data.error);if(epoch!==classificationEpoch){$('channelStatus').textContent='搜尋資料已更新，請再按重新分類。';return;}const annotations=new Map(data.annotations.map(a=>[a.id,a]));for(const [provider,g] of Object.entries(groups))for(const a of g.articles){const hit=annotations.get(provider+'::'+a.id);if(hit){const {id,...classification}=hit;Object.assign(a,classification);}}basePayload.source_graphs=groups;basePayload.channel_definitions=data.channels;basePayload.channel_version=data.version;channelCatalog=data.channels;renderChannelManager();rebuild();$('channelStatus').textContent='已依最新規則分類目前新聞；已存快照不變。';}catch(error){$('channelStatus').textContent='分類失敗：'+error.message;}finally{classifying=false;$('reclassify').disabled=false;}
}
$('channelForm').addEventListener('submit',async e=>{e.preventDefault();const payload={name:$('channelName').value.trim(),keywords:$('channelKeywords').value.split(/[,，、\n]/).map(t=>t.trim()).filter(Boolean),match:$('channelMatch').value,color:$('channelColor').value};if(editingChannel)payload.id=editingChannel;$('channelSubmit').disabled=true;
  try{const response=await fetch('/api/channels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.error);channelCatalog=data.channels;renderChannelManager();resetChannelForm();await reclassifyCurrent();}catch(error){$('channelStatus').textContent=error.message;}finally{$('channelSubmit').disabled=false;}});
async function deleteChannel(id){try{const response=await fetch('/api/channels/'+encodeURIComponent(id),{method:'DELETE'});const data=await response.json();if(!response.ok)throw new Error(data.error);if(editingChannel===id)resetChannelForm();channelCatalog=data.channels;renderChannelManager();await reclassifyCurrent();}catch(error){$('channelStatus').textContent=error.message;}}
$('channelCancel').onclick=resetChannelForm;$('reclassify').onclick=reclassifyCurrent;
loadSnapshots();loadChannels();applyMode();
$('graphFallback').addEventListener('toggle',()=>{if(viewMode==='timeline')renderTimeline();});

$('manageChannels').onclick=()=>{$('searchPanel').classList.add('open');$('channelManager').open=true;$('channelForm').scrollIntoView({block:'start',behavior:reducedMotion?'instant':'smooth'});$('channelName').focus({preventScroll:true});};

function renderNodeJson(n){
  const fields=['id','title','summary','url','published_at','source','symbols','language','fetched_at','entities','topics','analysis_version','origins','channels','primary_channel','channel_version'];
  const article={};for(const k of fields)if(n[k]!==undefined)article[k]=k==='id'?(n.article_id||n.id):n[k];
  const related=relations.filter(e=>e.source===n.id||e.target===n.id).map(e=>e.raw_relation||e);
  const trace=AtlasView.trace(relations,n.id,exploration);
  const paths=[...trace.nodes].filter(([id])=>id!==n.id).map(([id,info])=>({node_id:id,...info}));
  AtlasUI.jsonTree($('nodeJson'),{schema_version:'2.0',article,relations:related,visible_exploration:{root:n.id,settings:exploration,paths}});
}
function showBucket(bucket){
  selected=null;$('nodeJson').replaceChildren();const panel=$('article');panel.replaceChildren(el('h3',bucket.date+' UTC'),el('p',`${bucket.articles.length} 篇新聞 · 點選一篇查看內容`,'bucket-note'));
  const list=el('div',null,'bucket-list');AtlasUI.pagedRows(list,bucket.articles,a=>{const button=el('button');button.append(el('div',(a.display_sources||[a.source.provider]).map(p=>sourceNames[p]).join(' / ')+' · '+date(a.published_at),'meta'),el('div',a.title,'raw'));if(lockedRoots.length){const hit=activeTrace.nodes.get(a.id);button.append(el('div',hit?(hit.depth===0?'★ root':AtlasI18n.t('關聯深度')+' '+hit.depth):AtlasI18n.t('未在選定樹內'),'meta'));}button.onclick=()=>showArticle(a);return button;});panel.append(list);$('detail').classList.add('open');
}
function previewBucket(bucket,event){const box=$('preview');box.replaceChildren();box.hidden=!bucket;if(!bucket)return;box.append(el('strong',bucket.date+' UTC'),el('div',`${bucket.articles.length} 篇新聞 · 點選一篇查看內容`),el('div',Object.entries(bucket.counts).map(([p,n])=>sourceNames[p]+' '+n).join(' / '),'meta'));positionPreview(event);}
function syncRelationControls(){if($('glowLegend'))syncGlowControls();for(const k of ['internalMin','crossMin','depth','branchLimit','pathMin']){$('rel-'+k).value=exploration[k];$('out-'+k).textContent=exploration[k];}}
for(const k of ['internalMin','crossMin','depth','branchLimit','pathMin'])$('rel-'+k).oninput=()=>{rememberNetwork(true);exploration=AtlasView.settings({...exploration,[k]:Number($('rel-'+k).value)});syncRelationControls();AtlasUI.write('exploration',exploration);rebuild();};
$('resetRelations').onclick=()=>{exploration=AtlasView.settings();syncRelationControls();AtlasUI.write('exploration',exploration);rememberNetwork(true);rebuild();};
syncRelationControls();
const persistKey=AtlasUI.initKey($,{
  persist:async key=>{const response=await fetch('/api/settings/massive-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key})});if(!response.ok)throw Error('Key persistence failed');$('keyStatus').textContent='已保存於本機；重啟或換 port 會沿用。';},
  forget:async()=>{const response=await fetch('/api/settings/massive-key',{method:'DELETE'});if(!response.ok)throw Error('Key removal failed');$('keyStatus').textContent='已清除記住的金鑰；環境變數設定仍由主機管理。';$('key').placeholder='也可在伺服器環境設定';}
});
AtlasUI.initResize($,()=>{if(viewMode==='timeline')renderTimeline();});
let schemaLoaded=false;$('jsonInspector').addEventListener('toggle',async()=>{if(!$('jsonInspector').open||schemaLoaded)return;try{const response=await fetch('/schema/news-atlas.schema.json');if(!response.ok)throw new Error();AtlasUI.jsonTree($('schemaJson'),await response.json());schemaLoaded=true;}catch{$('schemaJson').textContent='Schema 載入失敗，請關閉後重試。';}});
$('language').value=AtlasI18n.language();$('language').onchange=()=>{AtlasI18n.setLanguage($('language').value);rebuild();};
AtlasI18n.start();

function syncGlowControls(){
  $('glow-enabled').checked=glowConfig.enabled;for(const key of ['brightness','radius','decay','background']){$('glow-'+key).value=glowConfig[key];$('glow-out-'+key).textContent=key==='decay'||key==='background'?Math.round(glowConfig[key]*100)+'%':glowConfig[key];}
  const legend=$('glowLegend');legend.replaceChildren();for(let depth=0;depth<=exploration.depth;depth++){const entry=el('span',depth===0?'root':String(depth));const dot=el('i');dot.style.opacity=1-Math.exp(-AtlasGlow.level(depth,glowConfig)*1.6);entry.append(dot);legend.append(entry);}
}
function updateGlow(){glowConfig=AtlasGlow.settings({enabled:$('glow-enabled').checked,...Object.fromEntries(['brightness','radius','decay','background'].map(k=>[k,Number($('glow-'+k).value)]))});AtlasUI.write('glow',glowConfig);syncGlowControls();refreshFocus();if(viewMode==='timeline')renderTimeline();}
for(const key of ['brightness','radius','decay','background'])$('glow-'+key).oninput=updateGlow;$('glow-enabled').onchange=updateGlow;
$('resetGlow').onclick=()=>{glowConfig=AtlasGlow.settings();AtlasUI.write('glow',glowConfig);syncGlowControls();refreshFocus();if(viewMode==='timeline')renderTimeline();};
$('clearRoot').onclick=clearFocus;
function glowState(){const category=highlightMode==='category'&&viewMode==='network',preview=!category&&focusRoot()===null&&hovered!==null;return {graph,trace:category?categoryTrace:preview?candidateTrace:activeTrace,config:preview?{...glowConfig,brightness:glowConfig.brightness*.3,radius:glowConfig.radius*.7}:glowConfig,colors,active:viewMode==='network'&&(graphHasHighlight()||preview),visible:viewMode==='network',reducedMotion,nodeStyle:nodeColor,edgeStyle,hitGuide:preview?interaction?.guide(hovered):Date.now()<stickyGuideUntil?interaction?.guide(focusRoot()):null};}
syncGlowControls();
new ResizeObserver(layoutTimeBar).observe($('timeFocusBar'));

idleFocus=AtlasInteraction.idleFocus(clearFocus,{isBusy:()=>globalThis.AtlasChat?.active()===true||highlightMode==='category'||$('relationDialog')?.open===true||interaction?.isDragging()===true||timeLens?.isDragging()===true});
function attachGraphBehaviors(){
  glowLayer=AtlasGlow.attach($('glowCanvas'),glowState);
  if(timeLensAvailable)timeSizer=AtlasTimeLens.attach(graph,()=>({config:timeFocus,dates:sizeBounds(),scale:(n,v)=>priceLens?.scale(n,v,timeFocus.enabled)??v}));
  interaction=AtlasInteraction.attach($('graph'),{getGraph:()=>graph,enabled:()=>viewMode==='network'&&!!graph,onHover:setHovered,onSelect:showArticle,onDragEnd:()=>rememberNetwork(),onBackground:clearGraphSelection,onActivity:touchFocus,strength:()=>Number($('stickyStrength').value)});
}
attachGraphBehaviors();
$('stickyStrength').value=AtlasUI.read('stickyStrength',65);$('stickyStrengthValue').textContent=$('stickyStrength').value+'%';
$('stickyStrength').oninput=()=>{$('stickyStrengthValue').textContent=$('stickyStrength').value+'%';AtlasUI.write('stickyStrength',Number($('stickyStrength').value));stickyGuideUntil=Date.now()+2000;touchFocus();interaction?.refresh();glowLayer?.refresh();};
for(const name of ['pointermove','pointerdown','pointerup','wheel','keydown'])document.addEventListener?.(name,touchFocus,{capture:true,passive:true});

$('massiveHelpButton').onclick=()=>$('massiveHelp').showModal();
$('closeMassiveHelp').onclick=()=>$('massiveHelp').close();
$('massiveHelp').addEventListener('click',event=>{if(event.target!==$('massiveHelp'))return;const r=$('massiveHelp').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)$('massiveHelp').close();});

function rootFeedback(message,state='info'){
  const box=$('rootSearchStatus');box.textContent=message;box.className='root-search-status '+state;
}
async function searchRuntimeRoots(event){
  if(highlightMode==='category'&&viewMode==='network')return;
  event?.preventDefault();event?.stopPropagation?.();if(rootSearchBusy)return;
  const query=$('rootQuery').value.trim(),limit=Number($('rootLimit').value);
  if(!query){rootFeedback(AtlasI18n.t('請輸入圖內搜尋關鍵字。'),'warning');return;}
  if(!articles.length){rootFeedback(AtlasI18n.t('目前圖譜沒有節點，請先搜尋新聞並勾選顯示來源。'),'warning');return;}
  if(!Number.isInteger(limit)||limit<1||limit>10){rootFeedback(AtlasI18n.t('Top N 必須為 1–10 的整數。'),'warning');return;}
  const ticket=++rootSearchTicket,button=$('rootSearchSubmit');rootSearchBusy=true;idleFocus?.stop();
  button.disabled=true;button.setAttribute('aria-busy','true');$('rootSearchSpinner').hidden=false;
  rootFeedback(AtlasI18n.t('搜尋中…')+' '+articles.length+' '+AtlasI18n.t('個節點'));
  try{
    // Yield a paint before local ranking so the busy state is visible.
    await new Promise(resolve=>setTimeout(resolve,80));
    if(ticket!==rootSearchTicket){rootFeedback(AtlasI18n.t('圖譜或選取已變更，請重新搜尋。'),'warning');return;}
    const result=AtlasView.rankRoots(articles,query,limit);
    if(!result.roots.length){rootFeedback(`「${query}」 · ${AtlasI18n.t('已掃描')} ${result.scanned_articles} · ${AtlasI18n.t('命中')} 0 · `+AtlasI18n.t('沒有符合的 roots；保留目前圖譜與星系。'),'warning');return;}
    lockedRoots=result.roots.map(r=>r.id);if(focusView.articles.length>renderBudget)renderNetwork();keywordLocked=true;rootSearchState={query,limit,matches:result.roots,total:result.matched_articles};
    refreshFocus();renderRootResults();if(viewMode==='timeline'){timelineFocusRequested=true;renderTimeline();}
    const warnings=[];
    if(!glowConfig.enabled||glowConfig.brightness===0)warnings.push(AtlasI18n.t('光暈已關閉或亮度為 0，請至光暈設定開啟。'));
    if(!activeTrace.edges.size)warnings.push(AtlasI18n.t('目前門檻下沒有延伸連線，僅標示 roots。'));
    if(viewMode==='network'&&graph){const nodes=graph.graphData().nodes,rect=$('stage').getBoundingClientRect();const inView=lockedRoots.some(id=>{const n=nodes.find(a=>a.id===id);if(!n)return false;const p=graph.graph2ScreenCoords(n.x,n.y,n.z);return p&&p.x>=0&&p.y>=0&&p.x<=rect.width&&p.y<=rect.height;});if(!inView)warnings.push(AtlasI18n.t('Roots 在目前視野外，可按「重設視角」查看全圖。'));}
    if(viewMode==='network'&&!graph)warnings.push(AtlasI18n.t('3D 無法使用，請查看下方 roots 清單。'));
    if(viewMode==='timeline'&&timelineStyle==='density')warnings.push(AtlasI18n.t('密度格以最淺關聯深度高亮；★ 表示 root，比例表示格內命中篇數。'));
    rootFeedback(`「${query}」 · ${AtlasI18n.t('已掃描')} ${result.scanned_articles} · ${AtlasI18n.t('命中')} ${result.matched_articles} · roots ${lockedRoots.length} · ${AtlasI18n.t('高亮節點')} ${activeTrace.nodes.size}`+(warnings.length?' · '+warnings.join(' '):' · '+AtlasI18n.t('已套用星系；視角保持不變。')),warnings.length?'warning':'success');
  }catch(error){rootFeedback(AtlasI18n.t('圖內搜尋失敗；目前圖譜保留。')+' '+String(error?.message||error),'error');}
  finally{rootSearchBusy=false;button.disabled=false;button.setAttribute('aria-busy','false');$('rootSearchSpinner').hidden=true;syncHighlightUI();touchFocus();}
}
$('rootSearchSubmit').onclick=searchRuntimeRoots;
$('rootSearch').addEventListener('keydown',event=>{if(event.key==='Enter'&&(!event.target||['rootQuery','rootLimit'].includes(event.target.id))){event.preventDefault();return searchRuntimeRoots(event);}});

function renderRootResults(){
  const box=$('rootResults');box.replaceChildren();if(!rootSearchState)return;
  box.append(el('div',AtlasI18n.t('已鎖定 roots')+': '+lockedRoots.length+(rootSearchState.total===undefined?'':' / '+rootSearchState.total)));
  for(const [i,id] of lockedRoots.entries()){const root=rootSearchState.matches.find(r=>r.id===id);if(!root)continue;const button=el('button',`${i+1}. ${root.title}`+(root.score==null?'':` · ${root.score}`),'raw');button.type='button';button.title=root.evidence.map(e=>`${e.field}: ${e.match}`).join(' · ');button.onclick=()=>{const n=articles.find(a=>a.id===id);if(n)showArticle(n,false);};box.append(button);}
}

AtlasUI.initSourcePanel($);
timePanel=AtlasUI.initTimePanel($,()=>{timeLens?.paint();layoutTimeBar();});
function syncRSSRegion(){const languages={TW:'zh-TW',US:'en-US',HK:'zh-HK',JP:'ja',GB:'en-GB'},region=$('rssRegion').value||'TW';$('yahooRegion').textContent=region+' · '+languages[region];}
$('rssRegion').addEventListener('change',syncRSSRegion);syncRSSRegion();

document.addEventListener?.('keydown',event=>{if(event.key==='Escape'&&!$('relationDialog')?.open&&!['INPUT','TEXTAREA','SELECT'].includes(event.target?.tagName))clearGraphSelection();});

if(globalThis.AtlasRelations)relationUI=AtlasRelations.init($,{
  status:state=>{relationActivity=state;updateActivity();},
  get:()=>basePayload,
  put:payload=>{rememberNetwork(true);rebuild(payload,true);},
  ...(globalThis.AtlasViewRelations?{applyView:cfg=>{viewRelationJob?.cancel();viewRequestedSettings=cfg;basePayload={...basePayload,relation_scope:'view',relations_pending:true};viewRevision++;scheduleViewRelations();}}:{}),
  view:payload=>{const view=AtlasView.select(payload,viewSources(),isSeparate());return {...view,relations:AtlasView.filterEdges(view.relations,exploration)};}
});

function syncSourceColors(){
  for(const p of providers){$('color-'+p).value=colors[p];$('view-color-'+p).style.backgroundColor=colors[p];}
  graph?.nodeColor(nodeColor);glowLayer?.refresh();paintProgress();if(viewMode==='timeline')renderTimeline();
}
for(const p of providers)$('color-'+p).addEventListener('input',()=>{
  const value=$('color-'+p).value;if(!/^#[0-9a-f]{6}$/i.test(value))return;
  colors[p]=value;AtlasUI.write('sourceColors',colors);syncSourceColors();
});
$('resetSourceColors').onclick=()=>{Object.assign(colors,defaultColors);AtlasUI.write('sourceColors',colors);syncSourceColors();};
syncSourceColors();

// Public, redacted runtime contract shared by Chat and its MCP UI adapter.
(() => {
  if(typeof document.addEventListener!=='function')return;
  const clickIds=['modeNetwork','modeTimeline','fit','clearRoot','resetGlow','resetRelations','rootSearchSubmit','relationOpen','relationClose','relationApply','relationCancel','cancelOperation','retryGraph','priceLoad','sourcePanelToggle','sourcePanelReset','timePanelToggle','timePanelReset','timeBellUndo','timeBellReset','timelineZoomIn','timelineZoomOut','submit','cancel','dateCustom','dateQuick','months-3','months-6','months-9','months-12'];
  const setIds=['language','query','ticker','start','end','rssRegion','source-google','source-yahoo','source-massive','view-google','view-yahoo','view-massive','rootQuery','rootLimit','renderBudget','highlightModeSwitch','graphChannel','separateSources','channelFilter','timelineZoom','timelineCutoff','stickyStrength','timeSizeEnabled','timeFocusSlider','priceMix','priceHorizon','glow-enabled',...['brightness','radius','decay','background'].map(k=>'glow-'+k),...['internalMin','crossMin','depth','branchLimit','pathMin'].map(k=>'rel-'+k),...['adaptive','entity','entity_days','topic','topic_days','topic_similarity','title','title_days','title_similarity','title_terms_min','half_life','internal_neighbors','cross_neighbors','coverage_first'].map(k=>'relation-'+k)];
  let revision=0,previous='',dataset=0,lastArticles=null,lastEdges=null;const recent=[];
  const note=(type,id)=>{recent.push({type,id,at:new Date().toISOString()});if(recent.length>12)recent.shift();};
  document.addEventListener('click',e=>{const node=e.target.closest?.('[id], [data-article-id]');if(clickIds.includes(node?.id))note('click',node.id);});
  document.addEventListener('change',e=>{if(setIds.includes(e.target.id))note('change',e.target.id);});
  const control=(id,kind)=>{const e=$(id);if(!e)return null;return {id,kind,type:e.type,disabled:!!e.disabled,hidden:!!e.closest('[hidden]'),value:e.type==='checkbox'?e.checked:e.value,min:e.min||undefined,max:e.max||undefined,step:e.step||undefined,options:e.tagName==='SELECT'?Array.from(e.options,o=>({value:o.value,label:o.textContent})):undefined};};
  function state(){
    if(lastArticles!==focusView.articles||lastEdges!==focusView.relations){dataset++;lastArticles=focusView.articles;lastEdges=focusView.relations;}
    const scope=highlightMode==='category'&&viewMode==='network'?Array.from(categoryTrace.nodes.keys()):lockedRoots.length?Array.from(new Set([...lockedRoots,...activeTrace.nodes.keys()])):selected?[selected]:currentView.articles.map(a=>a.id);
    const state={dataset,view_mode:viewMode,highlight_mode:highlightMode,selected_article:selected,root_ids:[...lockedRoots],category:graphChannel,channel_filter:channelFilter,scope_ids:scope,scope_kind:highlightMode==='category'&&viewMode==='network'?'category':lockedRoots.length?'roots_and_relations':selected?'article':'visible_results',visible_ids:currentView.articles.map(a=>a.id),counts:{loaded:focusView.articles.length,visible:currentView.articles.length,scope:scope.length,edges:focusView.relations.length,rendered:renderedCount},sources:viewSources(),search:{query:exportMeta.query||'',ticker:exportMeta.ticker||'',start:exportMeta.start||'',end:exportMeta.end||''},cutoff:timelineCutoff,render_budget:renderBudget,exploration:{...exploration},glow:{...glowConfig},time_focus:{...timeFocus},price_focus:priceLens?.state(),tool_dock:globalThis.AtlasDock?.state(),relation_settings:basePayload.relation_settings||{},busy:{search:!!controller,relations:!!relationActivity.busy,root_search:rootSearchBusy},graph_error:graphFailure?.message||null,controls:[...clickIds.map(id=>control(id,'click')),...setIds.map(id=>control(id,'set'))].filter(Boolean),recent_actions:recent.slice()};
    const fingerprint=JSON.stringify(state);if(fingerprint!==previous){previous=fingerprint;revision++;}return {...state,revision};
  }
  function data(){return {articles:focusView.articles.map(a=>({id:a.id,title:a.title,summary:a.summary||'',url:a.url,published_at:a.published_at,source:{provider:a.source?.provider,publisher:a.source?.publisher},channels:a.channels,entities:a.entities})),edges:focusView.relations.map(e=>({id:AtlasView.identity(e),source:AtlasView.endpoint(e.source),target:AtlasView.endpoint(e.target),type:e.type,score:e.score,evidence:e.evidence}))};}
  async function act(action){
    if(action.kind==='read')return state();
    const before=state();if(action.revision!==before.revision)throw Error('畫面已更新，請重新讀取狀態再操作。');
    let target;
    if(action.kind==='select_article'){
      const index=articles.findIndex(a=>a.id===action.id);
      if(index<0)throw Error('這篇新聞不在目前可選清單中。');
      if(Math.floor(index/100)!==articleListPage)renderArticleList(Math.floor(index/100));
      target=Array.from($('list').querySelectorAll('[data-article-id]')).find(e=>e.dataset.articleId===action.id);
      if(!target)throw Error('這篇新聞不在目前可選清單中。');
      target.click();
    }else{
      const allowed=action.kind==='click'?clickIds:action.kind==='set'?setIds:[];
      if(!allowed.includes(action.id))throw Error('此控制項未開放操作。');
      target=$(action.id);if(!target||target.disabled)throw Error('控制項目前不可用。');
      if(action.kind==='click')target.click();
      else {
        if(target.type==='checkbox'){
          if(typeof action.value!=='boolean')throw Error('此設定需要 true／false。');
          if(target.checked!==action.value)target.click();
        }else{
          const value=String(action.value);
          if(target.tagName==='SELECT'&&!Array.from(target.options).some(o=>o.value===value))throw Error('無效選項。');
          if(['range','number'].includes(target.type)){
            const n=Number(value),min=target.min===''?-Infinity:Number(target.min),max=target.max===''?Infinity:Number(target.max),step=Number(target.step)||1;
            if(!Number.isFinite(n)||n<min||n>max||Math.abs((n-(Number.isFinite(min)?min:0))/step-Math.round((n-(Number.isFinite(min)?min:0))/step))>1e-6)throw Error('數值超出範圍或步進。');
          }
          if(value.length>200)throw Error('輸入過長。');
          const old=target.value;target.value=value;if(!target.checkValidity()){target.value=old;throw Error('輸入格式無效。');}
          target.dispatchEvent(new Event('input',{bubbles:true}));target.dispatchEvent(new Event('change',{bubbles:true}));
        }
      }
    }
    target.classList.add('agent-operated');setTimeout(()=>target.classList.remove('agent-operated'),1600);
    note('agent',action.id);
    await new Promise(r=>setTimeout(r,120));
    if(action.id==='relationApply'||action.id==='rootSearchSubmit'){
      const until=Date.now()+12000;while((relationActivity.busy||rootSearchBusy)&&Date.now()<until)await new Promise(r=>setTimeout(r,100));
      if(relationActivity.busy||rootSearchBusy)throw Error('操作仍在處理，尚未確認完成。');
      if(relationActivity.error)throw Error(relationActivity.error);
    }
    return state();
  }
  globalThis.AtlasRuntime={state,data,act,record:note};
})();

if(globalThis.AtlasPrice)priceLens=AtlasPrice.init($,{articles:()=>focusView.articles,ticker:()=>$('ticker').value,focus:()=>({bounds:sizeBounds(),date:timeFocus.date}),onDate:date=>updateTimeCurve({date}),onChange:()=>{syncTimeFocus();if(viewMode==='timeline')renderTimeline();const n=articles.find(a=>a.id===selected);if(n)showArticle(n,false);}});

globalThis.addEventListener?.('atlas-dock',layoutTimeBar);

function viewPriority(){
  return [selected,...lockedRoots,...(highlightMode==='category'?categoryTrace.nodes.keys():basePayload.relation_scope==='view'?[]:focusTraceCache(focusView.relations,lockedRoots,exploration).nodes.keys())].filter(Boolean);
}
function scheduleViewRelations(){
  if(!viewRelationJob||restoringRelations)return;
  if(basePayload.relation_scope!=='view'||!currentView.articles.length){viewRelationJob.schedule(null);return;}
  const slice=AtlasView.renderSlice(currentView,renderBudget,viewPriority());
  const byProvider=new Map();
  for(const row of slice.articles)for(const p of row.display_sources||[row.source.provider]){
    if(!byProvider.has(p))byProvider.set(p,new Set());byProvider.get(p).add(row.article_id||row.id);
  }
  const groups={};for(const [p,g] of Object.entries(AtlasView.groups(basePayload))){const ids=byProvider.get(p);if(ids)groups[p]={articles:g.articles.filter(a=>ids.has(a.id))};}
  const cfg=viewRequestedSettings||basePayload.relation_settings||AtlasRelations.defaults;
  const ids=slice.articles.map(a=>a.id).sort();
  const sources=Object.keys(groups).sort(),separate=isSeparate();
  const scope={key:JSON.stringify([viewRevision,ids,cfg,separate,sources]),groups,cfg,ids,separate};
  const remembered=restoredRelationViews.find(v=>JSON.stringify([ids,sources,cfg,separate])===JSON.stringify([v.ids,v.sources,v.relation_settings,v.separate]));
  if(remembered)viewRelationJob.seed(scope.key,{...remembered,stage:'complete',pairs_checked:0});
  const saved=restoredRelationSeed;
  if(saved&&JSON.stringify([ids,sources,cfg,separate])===JSON.stringify([saved.view.relation_scope_ids.slice().sort(),saved.view.relation_scope_sources.slice().sort(),saved.view.relation_settings,saved.view.separate])){
    viewRelationJob.seed(scope.key,{stage:'complete',source_graphs:saved.source_graphs,cross_relations:saved.cross_relations,relation_settings:cfg,pairs_checked:0});
    restoredRelationSeed=null;
  }
  viewRelationJob.schedule(scope);
}
function updateViewCounters(){
  if(!globalThis.AtlasViewRelations||!$('activityNodesValue'))return;
  const say=AtlasViewRelations.say,s=viewRelationState,scoped=basePayload.relation_scope==='view';
  $('activityNodesValue').textContent=`${viewMode==='network'?renderedCount:currentView.articles.length} / ${focusView.articles.length}`;
  $('activityCalculationValue').textContent=scoped&&s.cache_hit?say('已重用完整視圖','Reused complete view'):scoped&&Number.isFinite(s.pairs_computed)?`${say('新算','New')} ${s.pairs_computed} · ${say('重用','Reused')} ${s.pairs_reused||0}`:scoped?`${s.pairs_checked||0} ${say('組已檢查','pairs checked')}${s.group&&s.phase==='calculating'?` · ${s.group} ${s.nodes_checked}/${s.nodes_total}`:''}`:say('既有圖譜','Existing graph');
  const visibleIds=new Set((lastNetworkRender?.slice.articles||[]).map(a=>a.id));
  const eligible=viewMode==='network'?currentView.relations.filter(e=>visibleIds.has(e.source)&&visibleIds.has(e.target)).length:currentView.relations.length;
  $('activityEdgesValue').textContent=`${viewMode==='network'?renderedEdges:eligible} / ${eligible}`;
  const phases={idle:say('等待資料','Waiting for news'),queued:say('準備目前視圖','Preparing view'),calculating:s.stage==='strict'?say('計算嚴格關聯','Computing strict relations'):say('背景補算關聯','Computing relations'), 'idle-fill':say('可互動，等待閒置補算','Interactive; waiting for idle'), 'render-wait':say('結果已備妥，等待閒置顯示','Results ready; waiting for idle'),ready:s.cache_hit?say('已重用完成結果，可互動','Completed view reused; interactive'):say('目前視圖完成，範圍外未計算','View complete; outside scope deferred'),error:s.error,stopped:say('已停止，可重試','Stopped; retry available')};
  $('activityStateValue').textContent=scoped?phases[s.phase]||s.phase:say('既有圖譜','Existing graph');
  for(const [id,zh,english] of [['Nodes','節點','Nodes'],['Calculation','關聯計算','Relation checks'],['Edges','連線渲染','Drawn edges'],['State','狀態','Status']])$('activity'+id+'Label').textContent=say(zh,english);
  $('viewRelationsRetry').textContent=say('重試關聯','Retry relations');$('viewRelationsStop').textContent=say('暫停補算','Pause completion');
  $('viewRelationsRetry').hidden=!scoped||!['error','stopped'].includes(s.phase);
  $('viewRelationsStop').hidden=!scoped||['idle','ready','error','stopped'].includes(s.phase);
}
if(globalThis.AtlasViewRelations){
viewRelationJob=AtlasViewRelations.create({
  status:state=>{viewRelationState=state;updateActivity();},retry:scheduleViewRelations,
  put:(result,scope)=>{
    if(result.stage==='complete'){
      const entry={ids:scope.ids,sources:Object.keys(scope.groups).sort(),separate:scope.separate,relation_settings:result.relation_settings,source_graphs:Object.fromEntries(Object.entries(result.source_graphs).map(([p,g])=>[p,{relations:g.relations}])),cross_relations:result.cross_relations};
      completedRelationViews.delete(scope.key);completedRelationViews.set(scope.key,entry);
      while(completedRelationViews.size>12)completedRelationViews.delete(completedRelationViews.keys().next().value);
    }
    const groups=AtlasView.groups(basePayload),source_graphs={};
    for(const [p,g] of Object.entries(groups))source_graphs[p]={...g,relations:result.source_graphs[p]?.relations||[]};
    const scoped={...basePayload,source_graphs,cross_relations:result.cross_relations,
      relations:[...Object.values(result.source_graphs).flatMap(g=>g.relations),...result.cross_relations],
      relation_cache_version:1,relation_scope_sources:Object.keys(scope.groups),relations_pending:result.stage==='strict',relation_scope:'view',relation_scope_ids:scope.ids,relation_settings:result.relation_settings};
    rememberNetwork();rebuild(scoped,true);if(result.stage==='complete')relationUI?.onViewResult(result.relation_settings);
  }
});
$('viewRelationsRetry').onclick=()=>viewRelationJob.retry();$('viewRelationsStop').onclick=()=>viewRelationJob.cancel();
AtlasViewRelations.tooltip($('activityCounters'));updateViewCounters();
}

// Wiki uses an independent renderer/store; opening it never rebuilds News Graph.
globalThis.AtlasWikiContext={
  selection(mode){
    const visibleSources=viewSources(),groups=AtlasView.groups(basePayload);
    const focus=new Set([selected,...lockedRoots,...graphTrace().nodes.keys()].filter(Boolean));
    const rows=visibleSources.flatMap(p=>(groups[p]?.articles||[]).filter(a=>mode!=='focus'||focus.has(a.id)||focus.has(p+'::'+a.id)));
    return {articles:rows.map(a=>({id:a.id,title:a.title,summary:a.summary||'',url:a.url,published_at:a.published_at,source:{provider:a.source.provider}})),sources:visibleSources,search:{query:exportMeta.query||'',ticker:exportMeta.ticker||'',rss_region:exportMeta.rss_region||'TW'}};
  },
  visible(open){if(open){clearTimeout(fitTimer);graph?.pauseAnimation();}else if(viewMode==='network')graph?.resumeAnimation();}
};
