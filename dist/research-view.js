/* Research controls share the mounted Wiki graph, selection and chat runtime. */
(function(){
 'use strict';
 const $=id=>document.getElementById(id),wiki=window.AtlasWiki;
 if(!wiki)return;
 const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const button=(text,fn)=>{const b=node('button',text);b.type='button';b.onclick=async()=>{if(b.disabled)return;const token=serial;b.disabled=true;b.setAttribute('aria-busy','true');b.classList.add('research-working');try{await fn();}catch(e){if(token===serial)status(e.message);}finally{b.disabled=false;b.setAttribute('aria-busy','false');b.classList.remove('research-working');}};return b;};
 const details=(text,children)=>{const d=node('details');d.append(node('summary',text),...children);return d;};
 const open=node('button','研究問題 · L2');open.type='button';open.onclick=()=>show();open.id='researchOpen';$('wikiPanel').querySelector('.wiki-header').append(open);
 const panel=node('section',undefined,'research-panel');panel.id='researchPanel';panel.hidden=true;
 panel.innerHTML=`<button type="button" id="researchBack">← L1 整理設定</button><h2>我的研究</h2><p id="researchStock"></p>
 <form id="researchForm"><label for="researchQuestion">你想研究什麼？</label><input id="researchQuestion" required maxlength="2000" placeholder="例如：資料中心需求對獲利的影響" autocomplete="off"><label for="researchWindow">觀察期間</label><select id="researchWindow"><option value="30">最近 30 日</option><option value="90">最近 90 日</option><option value="365">最近一年</option></select><small id="researchModel"></small><div id="researchAvailability" class="research-meta" role="status" aria-live="polite" hidden><span id="researchAvailabilityText"></span><div id="researchBlockers" hidden></div></div><span id="researchSubmitWrap" tabindex="0"><button id="researchSubmit" class="wiki-primary">建立研究</button></span><div id="researchBusyTip" class="wiki-tip" role="tooltip" hidden></div></form>
 <p id="researchStatus" role="status" aria-live="polite"></p><h3>已保存的研究</h3><div id="researchSaved"></div><details><summary>觀點分類</summary><div id="researchTaxonomy"></div></details>`;
 $('wikiControls').prepend(panel);
 const result=node('section',undefined,'research-result');result.id='researchResult';result.hidden=true;$('wikiLower').prepend(result);
 const layerStatus=node('div',undefined,'wiki-counts');layerStatus.id='wikiResearchStatus';layerStatus.hidden=true;layerStatus.setAttribute('role','status');layerStatus.setAttribute('aria-live','polite');const layerText=node('span');const layerRetry=button('重試讀取',()=>loadLayer());layerRetry.id='wikiResearchRetry';layerStatus.append(layerText,layerRetry);$('wikiCounts').after(layerStatus);
 const layerMessage=(text,working=false,retry=false)=>{layerText.textContent=text;layerStatus.hidden=!text;layerStatus.setAttribute('aria-busy',String(working));layerText.classList.toggle('research-working',working);layerRetry.hidden=!retry;};
 let layerRequest=0,runRequest=0;
 let stock='',serial=0,runId=null,timer=null,availabilityTimer=null,tipTimer=null,busy=false,submitting=false,lastAvailability=null;
 const pending=new Map(),drafts=new Map();let watching=null,availabilityError='',checking=false,availabilityRequest=0;
 function rememberDraft(){if(stock)drafts.set(stock,{question:$('researchQuestion').value,window:$('researchWindow').value});}
 const status=text=>{$('researchStatus').textContent=text;};
 async function api(path,body){const r=await fetch('/api/wiki/research/'+path+(body===undefined?(path.includes('?')?'&':'?')+'instrument='+encodeURIComponent(stock):''),body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,instrument:stock})});const v=await r.json();if(!r.ok)throw Error(v.error||'研究請求失敗');return v;}
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
 async function loadRun(id,animate=false,valid=()=>true){const token=serial,request=++runRequest,r=await api('run?id='+encodeURIComponent(id));if(token!==serial||request!==runRequest||!valid()||r.bundle.lens.instrument!==stock)return;runId=id;layerMessage('');wiki.setResearch(r,id,animate);render(r);}
 function render(r){
  result.hidden=false;result.replaceChildren();$('wikiLower').classList.add('research-visible');
  result.append(node('h3',r.bundle.lens.normalized_question));
  if(r.current_epochs.corpus!==r.bundle.manifest.epochs.corpus||r.current_epochs.taxonomy!==r.bundle.manifest.epochs.taxonomy)result.append(node('p','來源或觀點已有更新；目前保留原研究快照。','research-meta'));
  const actions=node('div',undefined,'research-actions');
  for(const [label,mode] of [['持續追蹤','live'],['固定快照','pinned']])actions.append(button(label,async()=>{const token=serial;await api('save',{run_id:runId,mode});if(token!==serial)return;status(mode==='live'?'已保存；L1 閒置後依相關新證據增量更新。':'已固定這次條件與結果。');await saved();}));
  result.append(actions);const claims=new Map(r.result.claims.map(c=>[c.id,c]));
  for(const [heading,refs] of [['結論',r.result.summary],['敘事動能',r.result.narrative],['支持',r.result.support],['反證',r.result.counter]]){
   const section=node('section');section.append(node('h4',heading));if(!refs.length)section.append(node('p','本次範圍沒有足夠資料。'));
   for(const id of refs){const c=claims.get(id);if(!c)continue;const article=node('article');article.append(button(c.statement,()=>wiki.selectNode(runId+':'+c.id)));const chain=[];
    for(const o of r.bundle.opinions.filter(o=>c.derived_from.includes(o.claim_id))){chain.push(button('L1 · '+o.title,()=>wiki.selectNode(o.revision_id)),node('p',o.selection_reason));for(const e of o.evidence){const a=node('a','新聞原文');a.href=e.url;a.target='_blank';a.rel='noopener noreferrer';chain.push(node('blockquote',e.quote),a);}}
    if(c.assumptions.length)chain.push(node('p','成立條件：'+c.assumptions.join('；')));if(c.invalidating_conditions.length)chain.push(node('p','失效條件：'+c.invalidating_conditions.join('；')));article.append(details('查看依據與條件',chain));section.append(article);
   }result.append(section);
  }
  result.append(details('價格動能 · 無可用資料',[node('p','缺少可驗證的行情版本，未計算報酬或價格動能。')]),details('範圍與缺口',[node('p',r.bundle.lens.time_spec.start+' → '+r.bundle.lens.time_spec.end),...r.result.gaps.map(x=>node('p',x))]));
 }
 async function saved(){
  const token=serial,r=await api('lenses');if(token!==serial)return;const box=$('researchSaved');box.replaceChildren();
  if(!r.lenses.length)box.append(node('p','尚未保存研究。'));
  for(const s of r.lenses){const section=node('section');section.append(button(s.lens.query,()=>loadRun(s.run_id)),node('small',s.mode==='pinned'?'固定快照':({fresh:'已更新',stale:'有新資料',failed:'更新失敗'})[s.refresh_state]));
   if(s.mode==='live')section.append(button('更新',async()=>{await availabilityOnce();if(busy){status(busyReason());return;}const token=serial,j=await api('refresh',{lens_id:s.id,expected_revision:s.revision});if(token!==serial)return;if(j.status==='unchanged')status('證據未變，已沿用結果，沒有呼叫模型。');else{submitting=true;syncButton();track(j.job_id,token);}}));
   if(s.history.length>1)section.append(details('歷史版本',s.history.slice().reverse().map((id,i)=>button(i?'較早版本 '+(s.history.length-i):'目前版本',()=>loadRun(id)))),button('比較上一版',async()=>{const token=serial,[a,b]=await Promise.all([api('run?id='+s.run_id),api('run?id='+s.history.at(-2))]);if(token!==serial)return;await loadRun(s.run_id);if(token!==serial)return;const before=new Set(b.result.claims.map(c=>c.statement)),after=new Set(a.result.claims.map(c=>c.statement));const diff=details('與上一版比較',[node('p','新增／修訂'),...a.result.claims.filter(c=>!before.has(c.statement)).map(c=>node('p',c.statement)),node('p','不再出現'),...b.result.claims.filter(c=>!after.has(c.statement)).map(c=>node('p',c.statement))]);diff.open=true;result.prepend(diff);}));box.append(section);
  }
 }
 async function terms(){const token=serial,t=await api('taxonomy');if(token!==serial)return;const box=$('researchTaxonomy');box.replaceChildren();for(const term of t.terms){const b=button(term.label+' · '+(term.opinion_ids?.length||0)+' 組',()=>{$('wikiLayer').value='L1';$('wikiLayer').dispatchEvent(new Event('change'));wiki.filterTerm(term.id);});const dot=node('i',undefined,'wiki-dot');dot.style.background=term.color;b.prepend(dot);box.append(b);}}
 function track(job,token){pending.set(stock,job);watching=job;submitting=true;syncButton();watch(job,token);}
 async function watch(job,token){clearTimeout(timer);if(token!==serial)return;try{const j=await api('job?id='+job);if(token!==serial)return;if(j.status==='completed'){pending.delete(stock);watching=null;await loadRun(j.payload.run_id,true);if(token!==serial)return;submitting=false;syncButton();status('研究完成；已驗證的 L2 觀點已加入共用圖譜。');await saved();}else if(['failed','interrupted','cancelled'].includes(j.status)){pending.delete(stock);watching=null;submitting=false;syncButton();status('研究未完成：'+(j.error||j.status)+'。原有結果已保留。');}else{status(j.status==='queued'?'等待模型工作槽…':'正在整合觀點與反證…');timer=setTimeout(()=>watch(job,token),2000);}}catch(e){if(token===serial){watching=null;submitting=pending.has(stock);syncButton();status(e.message);}}}
 async function availabilityOnce(){const token=serial,request=++availabilityRequest;try{const a=await api('availability');if(token!==serial||request!==availabilityRequest)return;lastAvailability=a;busy=a.busy;checking=false;availabilityError='';if(a.active_job&&!pending.has(stock))pending.set(stock,a.active_job.id);syncButton();}catch(e){if(token===serial&&request===availabilityRequest){lastAvailability=null;busy=true;checking=false;availabilityError=e.message;syncButton();}throw e;}}
 async function show(){layerMessage('');const next=$('wikiInstrument').value;if(next!==stock){rememberDraft();runId=null;result.replaceChildren();result.hidden=true;$('researchSaved').replaceChildren();$('researchTaxonomy').replaceChildren();stock=next;const draft=drafts.get(stock);$('researchQuestion').value=draft?.question||'';$('researchWindow').value=draft?.window||'30';}serial++;clearTimeout(timer);watching=null;clearTimeout(availabilityTimer);submitting=pending.has(stock);checking=true;availabilityError='';lastAvailability=null;busy=false;syncButton();panel.hidden=false;$('wikiControls').classList.add('research-mode');$('researchStock').textContent=stock;$('researchModel').textContent=$('wikiModel').selectedOptions[0]?.textContent||'gpt-6.1-sol · high';const token=serial;status('正在載入已保存研究與分類…');$('researchStatus').classList.add('research-working');availability();try{await Promise.all([saved(),terms()]);if(token===serial&&$('researchStatus').textContent==='正在載入已保存研究與分類…')status('');}catch(e){if(token===serial)status(e.message);}finally{if(token===serial)$('researchStatus').classList.remove('research-working');}if(token===serial)$('researchQuestion').focus();}
 $('researchBack').onclick=()=>{panel.hidden=true;$('wikiControls').classList.remove('research-mode');clearTimeout(availabilityTimer);clearTip();};
 $('researchForm').onsubmit=async e=>{e.preventDefault();if(submitting)return;const token=serial;submitting=true;syncButton();status('正在確認研究工作狀態…');try{await availabilityOnce();if(token!==serial)return;if(busy){submitting=false;syncButton();status(busyReason());return;}status('準備研究條件與證據…');const [model,reasoning_effort]=($('wikiModel').value||'gpt-6.1-sol|high').split('|');const j=await api('query',{query:$('researchQuestion').value,lookback_days:Number($('researchWindow').value),model,reasoning_effort});if(token!==serial)return;track(j.job_id,token);}catch(e){if(token===serial){submitting=false;syncButton();status(e.message);}}};
 window.addEventListener('atlas-wiki-stock',()=>{rememberDraft();serial++;layerRequest++;runRequest++;layerMessage('');stock='';runId=null;clearTimeout(timer);clearTimeout(availabilityTimer);watching=null;panel.hidden=true;result.hidden=true;result.replaceChildren();$('wikiControls').classList.remove('research-mode');$('wikiLower').classList.remove('research-visible');});
 window.addEventListener('atlas-wiki-research-clear',()=>{layerRequest++;runRequest++;layerMessage('');runId=null;result.hidden=true;$('wikiLower').classList.remove('research-visible');});
 async function loadLayer(){
  const request=++layerRequest;runRequest++;
  if($('wikiLayer').value==='L1'){layerMessage('');result.hidden=true;$('wikiLower').classList.remove('research-visible');return;}
  if(runId){layerMessage('');result.hidden=false;$('wikiLower').classList.add('research-visible');return;}
  stock=$('wikiInstrument').value;const token=serial,valid=()=>token===serial&&request===layerRequest&&$('wikiLayer').value!=='L1';
  layerMessage('正在讀取 L2 研究…',true);
  try{const r=await api('runs');if(!valid())return;if(r.runs.length)await loadRun(r.runs[0].id,false,valid);else layerMessage('尚未建立 L2；請由「研究問題 · L2」輸入問題。');}
  catch(e){if(valid())layerMessage('無法讀取 L2：'+e.message,false,true);}
 }
 window.addEventListener('atlas-wiki-layer',loadLayer);
})();
