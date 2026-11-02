/* Edge definitions are rebuilt by the same backend used by search and API clients. */
(function(root){
  const defaults={entity:true,topic:true,title:true,entity_days:30,topic_days:7,title_days:3,topic_similarity:.18,title_similarity:.5,internal_neighbors:6,cross_neighbors:2,half_life:0,title_terms_min:4,coverage_first:false,adaptive:false};
  const general={...defaults,entity_days:180,topic_days:60,title_days:30,topic_similarity:.10,title_similarity:.25,title_terms_min:3,coverage_first:true};
  const unified={...general,adaptive:true};
  const presets={original:defaults,general,entity:{...defaults,topic:false,title:false,entity_days:7},topic:{...defaults,entity:false,title:false},title:{...defaults,entity:false,topic:false}};
  const same=(a,b)=>Object.keys(defaults).every(k=>a[k]===b[k]);
  const normalize=value=>Object.fromEntries(Object.entries(defaults).map(([k,v])=>[k,value?.[k]??v]));
  const en=()=>root.AtlasI18n?.language()==='en';
  const say=(zh,english)=>en()?english:zh;
  function explain(cfg){
    const rows=[];
    if(cfg.entity)rows.push(say(`共同實體：至少一個共同公司／代碼，相隔 ≤ ${cfg.entity_days} 天。分數 = 0.72 + min(0.20, 0.07 × 共同實體數)。`,`Shared entity: ≥1 shared company/ticker within ${cfg.entity_days} days. Score = 0.72 + min(0.20, 0.07 × shared entities).`));
    if(cfg.topic)rows.push(say(`共同主題：相隔 ≤ ${cfg.topic_days} 天、共同主題、至少 2 個共同標題詞，Jaccard ≥ ${cfg.topic_similarity}。分數 = 0.40 + min(0.25, Jaccard)。`,`Shared topic: within ${cfg.topic_days} days, a shared topic, ≥2 shared title terms, Jaccard ≥ ${cfg.topic_similarity}. Score = 0.40 + min(0.25, Jaccard).`));
    if(cfg.title)rows.push(say(`相似標題：相隔 ≤ ${cfg.title_days} 天、至少 ${cfg.title_terms_min} 個共同標題詞，Jaccard ≥ ${cfg.title_similarity}。分數 = 0.45 + min(0.30, Jaccard ÷ 2)。`,`Similar title: within ${cfg.title_days} days, ≥${cfg.title_terms_min} shared title terms, Jaccard ≥ ${cfg.title_similarity}. Score = 0.45 + min(0.30, Jaccard ÷ 2).`));
    if(!rows.length)rows.push(say('所有規則關閉：不產生 edge，所有新聞節點仍保留。','All rules off: no edges; every news node remains.'));
    rows.push(say('判斷順序：共同實體 → 共同主題 → 相似標題；採第一個符合的已開啟規則，不累加。','Priority: shared entity → shared topic → similar title. First enabled matching rule wins; scores are not added.'));
    rows.push(cfg.half_life?say(`時間衰減：最終分數 = 規則分數 × 2^(−相隔天數 ÷ ${cfg.half_life})。`,`Time decay: final score = rule score × 2^(−days apart ÷ ${cfg.half_life}).`):say('時間衰減關閉：時間只限制能否連線，不降低分數。','Time decay off: time gates eligibility without reducing scores.'));
    rows.push(say(`依分數高、日期近排序；每篇來源內最多 ${cfg.internal_neighbors} 條，每個跨來源配對最多 ${cfg.cross_neighbors} 條。`,`Rank by score, then date proximity. Up to ${cfg.internal_neighbors} internal edges per article; ${cfg.cross_neighbors} per cross-source pair.`));
    if(cfg.coverage_first)rows.push(say('覆蓋優先：先以合格證據連接尚無連線的節點，再依分數補線；不憑空製造關聯。','Coverage first: connect uncovered nodes with qualifying evidence before filling by score; never invent a relationship.'));
    return rows;
  }
  function evidence(edge){
    const rule=(edge.evidence||[]).find(e=>e.rule_settings);
    const lines=(edge.evidence||[]).filter(e=>e.entity||e.title_terms).map(e=>e.entity?`${e.entity}: ${e.source?.evidence||''} ↔ ${e.target?.evidence||''}`:say(`主題：${(e.topics||[]).join('、')||'—'}；共同標題詞：${(e.title_terms||[]).join('、')}；Jaccard = ${e.title_similarity}`,`Topics: ${(e.topics||[]).join(', ')||'—'}; shared title terms: ${(e.title_terms||[]).join(', ')}; Jaccard = ${e.title_similarity}`));
    if(rule)lines.push(say(`計分：${rule.base_score} × 時間係數 ${rule.time_factor} = ${edge.weight}`,`Score: ${rule.base_score} × time factor ${rule.time_factor} = ${edge.weight}`));
    else lines.push(say(`規則分數：${edge.weight}；無時間衰減。`,`Rule score: ${edge.weight}; no time decay.`));
    const cfg=rule?.rule_settings||defaults;
    const key={shared_entity:'entity',shared_topic:'topic',similar_title:'title'}[edge.type];
    if(key)lines.push(...explain({...cfg,entity:key==='entity',topic:key==='topic',title:key==='title'}).slice(0,1));
    return lines.join('\n');
  }
  function tooltip($,read){
    const box=$('relationTooltip'),form=$('relationForm');let timer=null,active=null,last=null;
    function hide(){clearTimeout(timer);box.classList.remove('visible');box.setAttribute('aria-hidden','true');}
    function content(key){const cfg=read();
      const texts={
        adaptive:say('先保留嚴格規則的連線，再以欄位設定的較寬範圍替孤立節點補線；不新增無證據的關聯。','Keep strict-rule edges, then use these broader limits to connect isolated nodes with qualifying evidence.'),
        entity:explain({...cfg,entity:true,topic:false,title:false})[0],
        topic:explain({...cfg,entity:false,topic:true,title:false})[0],
        title:explain({...cfg,entity:false,topic:false,title:true})[0],
        entity_days:say('共同實體可連線的最大日期差；自適應先用最多 30 天，再對孤立點放寬至此值。','Maximum days apart for a shared entity. Adaptive starts at up to 30 days, then expands to this limit for isolated nodes.'),
        topic_days:say('共同主題可連線的最大日期差；自適應先用最多 7 天。','Maximum days apart for shared topics. Adaptive starts at up to 7 days.'),
        title_days:say('相似標題可連線的最大日期差；自適應先用最多 3 天。','Maximum days apart for similar titles. Adaptive starts at up to 3 days.'),
        topic_similarity:say('Jaccard＝共同標題詞數 ÷ 聯集詞數；仍需共同主題和至少 2 個共同詞。','Jaccard = shared title terms / their union. Requires a shared topic and at least 2 shared terms.'),
        title_similarity:say('Jaccard＝共同標題詞數 ÷ 聯集詞數。降低門檻可增加連線，但不是 embedding 語意距離。','Jaccard = shared title terms / their union. Lower thresholds admit more edges; this is not embedding distance.'),
        title_terms_min:say('標題規則至少需要的共同詞數；英文以詞、中文以雙字比對。','Minimum shared title terms: English words and Chinese character pairs.'),
        half_life:say('0：不衰減。其他值：分數 × 2^(−相隔天數 ÷ 半衰期)。','0: no decay. Otherwise: score × 2^(−days apart / half-life).'),
        internal_neighbors:say('每篇在同來源內的連線上限；0 不建立來源內連線。','Maximum within-source edges per article. 0 disables these edges.'),
        cross_neighbors:say('每篇在每個來源配對中的跨來源連線上限；0 關閉。','Maximum cross-source edges per article per source pair. 0 disables them.'),
        coverage_first:say('非自適應模式時，先連接孤立節點再補線；自適應模式固定優先補孤立點。','Without adaptation, prioritize isolated nodes before filling other edges. Adaptive mode always prioritizes isolated nodes.')
      };return texts[key]||'';
    }
    function show(target,event,keyboard=false){
      const key=target?.dataset?.ruleHelp;if(!key)return;
      if(!keyboard&&active===target&&last?.x===event.clientX&&last?.y===event.clientY)return;
      active=target;last=keyboard?null:{x:event.clientX,y:event.clientY};clearTimeout(timer);
      box.textContent=content(key);box.classList.add('visible');box.setAttribute('aria-hidden','false');
      const rect=target.getBoundingClientRect(),width=box.getBoundingClientRect().width;
      box.style.left=Math.max(12,Math.min(innerWidth-width-12,keyboard?rect.left:event.clientX+12))+'px';
      box.style.top=Math.max(12,Math.min(innerHeight-box.getBoundingClientRect().height-12,keyboard?rect.bottom+8:event.clientY+18))+'px';
      if(!keyboard)timer=setTimeout(hide,2000);
    }
    form.addEventListener('pointermove',e=>{const target=e.target.closest?.('[data-rule-help]');if(target)show(target,e);else{active=null;last=null;hide();}});
    form.addEventListener('pointerleave',()=>{active=null;last=null;hide();});
    form.addEventListener('focusin',e=>{const target=e.target.closest?.('[data-rule-help]');if(target)show(target,e,true);});
    form.addEventListener('focusout',hide);
    $('relationDialog').addEventListener('close',hide);
    return {hide};
  }
  function init($,hooks){
    const dialog=$('relationDialog'),form=$('relationForm');
    const saved=root.AtlasUI.read('relationSettings',null);
    let desired=saved?normalize(saved):{...unified};
    let applied={...defaults},ticket=0,abort=null,timer=null,doneTimer=null,error='',externalBusy=false,applying=false,started=0,clock=null;
    function fields(cfg){for(const [k,v] of Object.entries(defaults)){const input=$('relation-'+k);if(typeof v==='boolean')input.checked=cfg[k];else input.value=cfg[k];}}
    function read(){return Object.fromEntries(Object.entries(defaults).map(([k,v])=>[k,typeof v==='boolean'?$('relation-'+k).checked:Number($('relation-'+k).value)]));}
    function paint(){
      $('relationOpen').textContent=say('⚙ 關聯設定','⚙ Edge settings');
      hooks.status?.({busy:applying,waiting:externalBusy,error,started});
      $('relationStatus').hidden=!error;$('relationStatus').textContent=error;
    }
    function busy(value,complete=false){
      clearTimeout(doneTimer);clearInterval(clock);applying=value;if(value){started=Date.now();clock=setInterval(paint,1000);}
      form.setAttribute('aria-busy',String(value));
      $('relationSpinner').hidden=!value;$('relationApply').disabled=value||externalBusy;$('relationCancel').hidden=!value;
      $('relationApplyText').textContent=externalBusy?say('搜尋完成後可套用','Available after search'):value?say('套用中…','Applying…'):complete?say('已套用','Applied'):say('套用','Apply');
      $('relationProgress').hidden=!value&&!complete;
      if(value)$('relationProgress').removeAttribute('value');else $('relationProgress').value=1;
      hooks.status?.({busy:applying,waiting:externalBusy,error,started});
      if(complete)doneTimer=setTimeout(()=>{busy(false);},900);
    }
    async function apply(cfg=read()){
      if(externalBusy)return;
      clearTimeout(timer);abort?.abort();const mine=++ticket,base=hooks.get();
      const groups=root.AtlasView.groups(base),source_graphs=Object.fromEntries(Object.entries(groups).map(([p,g])=>[p,{articles:g.articles}]));
      error='';paint();busy(true);
      if(!Object.values(groups).some(g=>g.articles.length)){
        applied=desired={...cfg};root.AtlasUI.write('relationSettings',desired);busy(false,true);return;
      }
      const request=new AbortController();abort=request;const timeout=setTimeout(()=>request.abort(),300000);let complete=false;
      try{
        const response=await fetch('/api/graph/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_graphs,relation_settings:cfg}),signal:request.signal});
        const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);
        if(mine!==ticket||hooks.get()!==base)return;
        if(!result.relation_settings||!same(result.relation_settings,cfg))throw Error(say('請重啟服務後重試。','Restart the server and retry.'));
        const updated={...base,relation_settings:result.relation_settings,relations_pending:false,relations:result.relations,cross_relations:result.cross_relations,source_graphs:Object.fromEntries(Object.entries(groups).map(([p,g])=>[p,{...g,relations:result.source_graphs[p]?.relations||[]}]))};
        applied=desired={...result.relation_settings};root.AtlasUI.write('relationSettings',desired);hooks.put(updated);complete=true;
      }catch(e){if(mine===ticket)error=say('未套用：','Not applied: ')+(e.name==='AbortError'?say('請求逾時，請重試。','Request timed out. Retry.'):e.message);}
      finally{clearTimeout(timeout);if(mine===ticket){busy(false,complete);paint();}}
    }
    function cancel(){ticket++;abort?.abort();clearTimeout(timer);error=say('已停止等待；目前圖譜保留。','Stopped waiting; current graph retained.');busy(false);paint();}
    $('relationCancel').onclick=cancel;
    $('relationOpen').onclick=()=>{fields(desired);paint();dialog.showModal();};
    $('relationClose').onclick=()=>dialog.close();
    dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
    form.addEventListener('submit',e=>{e.preventDefault();if(form.reportValidity())apply();});
    $('language').addEventListener('change',paint);
    fields(desired);paint();tooltip($,read);
    return {
      applied:()=>({...applied}),
      preferred:()=>({...desired}),
      cancel,
      setSearchBusy(value){externalBusy=value;ticket++;abort?.abort();clearTimeout(timer);error='';busy(false);paint();},
      restore(cfg){desired=normalize(cfg);fields(desired);},
      onPayload(payload){ticket++;abort?.abort();clearTimeout(timer);busy(false);applied=normalize(payload.relation_settings);error='';paint();if(!externalBusy&&!payload.relations_pending&&!same(applied,desired))timer=setTimeout(()=>apply(desired),180);},
    };
  }
  root.AtlasRelations={defaults,general,unified,presets,normalize,same,explain,evidence,tooltip,init};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.AtlasRelations;
})(globalThis);
