/* Review two exact viewpoints; the research worker stores a separate comparison. */
(function(root){
 'use strict';
 root.openWikiComparison=function({instrument,model,effort,t}){
  const el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
  const button=(text,action)=>{const b=el('button',text);b.type='button';b.onclick=action;return b;};
  const iconButton=(name,label,action)=>root.AtlasUI.labelIcon(button('',action),name,label);
  const opener=document.activeElement;
  const dialog=el('dialog');dialog.className='wiki-settings wiki-comparison';document.body.append(dialog);
  dialog.setAttribute('aria-labelledby','wikiComparisonHeading');dialog.dataset.ownI18n='true';
  const chosen=[],select=el('select'),search=el('input'),selection=el('div'),history=el('section'),detail=el('section'),notice=el('p');
  let submittedJob=null,page=0,historyOffset=0,serial=0,historySerial=0,detailSerial=0,timer=null,submitting=false;
  notice.setAttribute('role','status');
  const closed=new AbortController();
  async function api(name,params={},body){
   const url='/api/wiki/research/'+name;
   const r=await fetch(body?url:url+'?'+new URLSearchParams({instrument,...params}),body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument,...body}),signal:closed.signal}:{signal:closed.signal});
   const value=await r.json();if(!r.ok)throw Error(value.error||r.statusText);return value;
  }
  function error(e){if(dialog.open)notice.textContent=e.message;}
  const previous=iconButton('previous',t('上一頁候選觀點','Previous candidates'),()=>load(page-50));
  const next=iconButton('next',t('下一頁候選觀點','Next candidates'),()=>load(page+50));
  async function load(offset){
   const ticket=++serial;previous.disabled=next.disabled=true;
   try{
    const result=await api('comparison-candidates',{q:search.value,offset});
    if(ticket!==serial)return;page=offset;
    select.replaceChildren(...result.items.map(r=>new Option(r.origin+' · '+r.title,r.ref)));
    previous.disabled=page===0;next.disabled=result.next_offset===null;
    paint();
    if(!result.items.length)notice.textContent=t('找不到符合的已保存觀點','No matching saved viewpoints');
    else notice.textContent='';
   }catch(e){error(e);}
  }
  const submit=button(t('使用模型比對並另存摘要','Compare with model and save summary'),async()=>{
   if(submitting||chosen.length!==2)return;submitting=true;paint();notice.textContent=t('正在送出比對…','Submitting…');
   try{
    const job=await api('compare',{}, {refs:chosen.map(x=>x.ref),model,reasoning_effort:effort});
    submittedJob=job.job_id;notice.textContent=t('比對工作','Comparison job')+' · '+job.status;
    historyOffset=0;await refreshHistory();
   }catch(e){error(e);}finally{submitting=false;paint();}
  });
  function paint(){
   selection.replaceChildren(...chosen.map((c,i)=>{
    const p=el('p');p.append(el('span',c.label),iconButton('close',t('移除觀點','Remove viewpoint')+' · '+c.label,()=>{
     chosen.splice(i,1);paint();select.focus();
    }));return p;
   }));
   add.disabled=chosen.length===2||!select.value||chosen.some(c=>c.ref===select.value);
   submit.disabled=submitting||chosen.length!==2||!model;
  }
  const add=button(t('選入比對','Add to comparison'),()=>{
   if(!select.value||chosen.some(c=>c.ref===select.value)||chosen.length>=2)return;
   chosen.push({ref:select.value,label:select.selectedOptions[0].textContent});paint();
  });
  add.dataset.action='add';select.onchange=paint;
  const verdicts={similar:['可合併摘要','Similar viewpoints'],conflicting:['同命題有分歧','Conflicting positions'],different_scope:['適用範圍不同','Different scopes'],insufficient:['證據不足','Insufficient evidence']};
  async function showReport(id){
   const ticket=++detailSerial;
   try{
    const value=await api('comparison',{id});if(ticket!==detailSerial)return;
    const r=value.result;
    detail.replaceChildren(el('h3',t(...verdicts[r.verdict])),el('p',r.summary),el('p',r.reason),el('small',value.model+' · '+value.reasoning_effort));
    for(const source of value.inputs){
     const d=el('details');d.append(el('summary',source.statement),el('small',source.ref));
     if(source.question){
      d.append(el('p',source.question),el('small',[source.window?.start,source.window?.as_of].filter(Boolean).join(' → ')));
      for(const premise of source.premises)d.append(el('p',premise.statement),el('small',premise.revision_id));
     }
     if(source.scope)d.append(el('p',source.scope+' · '+(source.available_at||'')));
     for(const c of source.evidence.filter(c=>r.citations.includes(c.id))){
      d.append(el('blockquote',c.quote),el('small',[c.published_at,c.article_revision_id].filter(Boolean).join(' · ')));
      if(/^https?:\/\//i.test(c.url||'')){const a=el('a',t('新聞原文','News source'));a.href=c.url;a.target='_blank';a.rel='noopener noreferrer';d.append(a);}
     }
     detail.append(d);
    }
   }catch(e){error(e);}
  }
  async function refreshHistory(){
   const ticket=++historySerial;clearTimeout(timer);
   try{
    const value=await api('comparisons',{offset:historyOffset});if(ticket!==historySerial)return;
    history.replaceChildren(el('h3',t('比對紀錄','Comparison history')));
    for(const j of value.jobs){
     if(j.id===submittedJob)notice.textContent=t('比對工作','Comparison job')+' · '+(j.error||j.status);
     const p=el('p');p.append(el('span',j.first_statement+' / '+j.second_statement));
     if(j.comparison_id)p.append(button(t('檢視結果','View result'),()=>showReport(j.comparison_id)));
     else p.append(el('span',j.error||j.status));history.append(p);
    }
    if(historyOffset)history.append(iconButton('previous',t('上一頁比對紀錄','Previous comparisons'),()=>{historyOffset-=50;refreshHistory();}));
    if(value.jobs.length===50)history.append(iconButton('next',t('下一頁比對紀錄','Next comparisons'),()=>{historyOffset+=50;refreshHistory();}));
    if(value.jobs.some(j=>['queued','running'].includes(j.status)))timer=setTimeout(refreshHistory,2500);
   }catch(e){error(e);if(dialog.open)history.append(button(t('重試','Retry'),refreshHistory));}
  }
  const form=el('form');search.type='search';search.maxLength=200;search.placeholder=t('搜尋已保存的觀點','Search saved viewpoints');search.setAttribute('aria-label',search.placeholder);
  const find=root.AtlasUI.labelIcon(el('button'),'search',t('搜尋','Search'));find.type='submit';form.append(search,find);form.onsubmit=e=>{e.preventDefault();load(0);};
  select.setAttribute('aria-label',t('觀點候選','Saved viewpoint candidates'));
  const heading=el('div'),title=el('h2',t('觀點比對','Compare viewpoints')+' · '+instrument);
  heading.className='wiki-reader-heading';title.id='wikiComparisonHeading';
  heading.append(title,iconButton('close',t('關閉比對','Close comparison'),()=>dialog.close()));
  const candidates=el('div'),actions=el('div');candidates.className='comparison-candidates';actions.className='comparison-submit';
  selection.className='comparison-selected';history.className='comparison-history';
  candidates.append(select,previous,next,add);actions.append(el('small',model+' · '+effort),submit);
  dialog.append(heading,el('p',t('選取兩筆 L1 或 L2 觀點','Choose two L1 or L2 viewpoints')),
   form,candidates,selection,actions,notice,history,detail);
  dialog.onclose=()=>{clearTimeout(timer);closed.abort();dialog.remove();if(opener?.isConnected)opener.focus({preventScroll:true});};
  dialog.showModal();paint();load(0);refreshHistory();
 };
})(globalThis);
