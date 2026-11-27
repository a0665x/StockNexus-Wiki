'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const roles = {
    scout: ['立論員', '蒐集原始證據，提出可以查核的命題。'],
    challenger: ['駁論員', '檢驗對方假設，提出反例並核對引用。'],
    planner: ['推論規劃員', '盤點分歧，深化推論並提出驗證路徑。'],
    lead: ['總答辯員', '梳理己方論證，回應最強反例並選定結辯主張。'],
    judge: ['評審', '獨立檢查每一條命題及其引文，記錄分數、理由與保留意見。']
  };
  const sides = { pro: '支持方', con: '反對方', judge: '評審席' };
  const findings = { supported:'有證據支持', contradicted:'有證據反駁', insufficient:'目前材料不足', abstain:'棄權', unresolved:'未取得多數' };
  const statuses = { running:'進行中', done:'完成', completed:'已結束', partial:'部分完成', interrupted:'服務中斷', cancelled:'已停止', failed:'失敗' };
  const fallback = [
    ['codex','Codex','在橋接主機執行 codex login。'],
    ['claude','Claude Code','在橋接主機執行 claude auth login。'],
    ['ollama','Ollama','在橋接主機執行 ollama serve，再下載模型。'],
    ['gemini','Gemini CLI','在橋接主機配置 GEMINI_API_KEY 與 Gemini CLI。']
  ].map(([id,name,connection])=>({id,name,connection,available:false,models:[]}));
  const slots = ['pro','con'].flatMap(side=>Object.keys(roles).slice(0,4).map(role=>side+'-'+role))
    .concat(['judge-1','judge-2','judge-3']);
  const roleOf = seat => seat.startsWith('judge-') ? 'judge' : seat.split('-')[1];
  const seatName = seat => seat.startsWith('judge-') ? '評審 '+seat.slice(-1) : sides[seat.split('-')[0]]+'・'+roles[roleOf(seat)][0];
  const el = (tag,text) => { const n=document.createElement(tag); if(text!=null)n.textContent=text; return n; };
  const option = (value,label) => { const n=el('option',label); n.value=value; return n; };
  const portrait = window.ArenaLive.figure;
  const live = window.ArenaLive.mount({api,seatName});
  const read = (key,def) => { try {return JSON.parse(localStorage.getItem(key)) ?? def;} catch {return def;} };
  const write = (key,data) => { try {localStorage.setItem(key,JSON.stringify(data));} catch { $('notice').textContent='瀏覽器無法儲存本機草稿。';} };
  const prefix='stocknexus.arena.v1.';
  let stock=new URLSearchParams(location.search).get('instrument')||'';
  let profiles=read(prefix+'profiles',[]), draft, selected=null, editing=null, adapters=fallback;
  let bridge=false, busy=false, observed=null, poll=null, selectedRun='', generation=0;
  async function api(path,body) {
    const res=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await res.json().catch(()=>({}));
    if(!res.ok) throw Error(data.error || 'HTTP '+res.status);
    return data;
  }
  function restore() {
    draft=read(prefix+stock,{seats:{},topic:''});
    $('topic').value=draft.topic;
    selected=null;
    drawPalette(); drawSeats();
  }
  function remember() {write(prefix+stock,draft);}
  function markChanged() {delete draft.requestId; remember();}
  function able(profile) {
    const adapter=adapters.find(a=>a.id===profile.runtime);
    return adapter?.available && (adapter.manualModel || adapter.models.includes(profile.model));
  }
  function readiness() {
    const seats=Object.entries(observed?.seats||draft.seats), team=seats.filter(([key])=>!key.startsWith('judge')).length;
    const jury=seats.length-team;
    $('count').textContent='辯方 '+team+'/8　評審 '+jury+'/3';
    const message=observed?'正在檢視庭次，可返回排席配置下一庭':busy?'正在送出開庭請求':
      !draft.topic.trim()?'請先填寫辯論主題':team<8||!jury?'雙方各需四席，並至少配置一位評審':
      !bridge?'請啟動主機橋接並檢查連線':seats.some(([,p])=>!able(p))?'部分席位的執行環境或模型無法使用':'';
    $('gavel').disabled=Boolean(message);
    $('ready').textContent=message||'本庭含準備、攻防與評審，最多 '+(22+jury)+' 次席位呼叫。封存材料將送至所選模型。';
  }
  function drag(node,payload) {
    node.draggable=true;
    node.addEventListener('dragstart',event=>{event.dataTransfer.setData('application/x-arena-profile',JSON.stringify(payload));event.dataTransfer.effectAllowed=payload.from?'move':'copy';});
  }
  function drop(node,accept) {
    node.addEventListener('dragover',e=>{if(e.dataTransfer.types.includes('application/x-arena-profile')){e.preventDefault();node.classList.add('drop-on');}});
    node.addEventListener('dragleave',()=>node.classList.remove('drop-on'));
    node.addEventListener('drop',e=>{
      e.preventDefault();node.classList.remove('drop-on');
      let payload;
      try {payload=JSON.parse(e.dataTransfer.getData('application/x-arena-profile'));}catch {return;}
      if(payload && Object.hasOwn(roles,payload.avatar))accept(payload);
    });
  }
  function card(profile,caption,detail) {
    const button=el('button'), label=el('span');
    button.className='avatar-card';button.type='button';button.dataset.avatar=profile.avatar;
    button.setAttribute('aria-pressed',String(selected?.avatar===profile.avatar && selected?.name===profile.name));
    label.append(el('strong',caption),el('small',detail));button.append(portrait(profile.avatar),label);
    button.onclick=()=>{selected=profile;drawPalette();$('notice').textContent='已選 '+caption+'，請點選空席。';};
    drag(button,profile);return button;
  }
  function drawPalette() {
    $('palette').replaceChildren(...Object.entries(roles).map(([avatar,[name]],i)=>card({avatar},name,['立論與蒐證','驗證與反駁','盤點與深化','統整與答辯','逐項裁決'][i])));
    $('savedSection').hidden=!profiles.length;
    $('saved').replaceChildren(...profiles.map(p=>card(p,p.name,p.runtime+' · '+p.model)));
  }
  function drawSeats() {
    for(const key of ['pro','con','jury']) $(key).replaceChildren();
    for(const seat of slots) {
      const p=(observed?.seats||draft.seats)[seat], button=el('button'),label=el('span'),role=roleOf(seat);
      button.type='button';button.className='seat';button.dataset.seat=seat;
      button.setAttribute('aria-label',seatName(seat)+' · '+(p?.name||'空席'));
      label.append(el('strong',p?.name||(role==='judge'?seatName(seat):roles[role][0])),
        el('small',p?roles[role][0]+' · '+p.model:'空席'));
      const icon=p?portrait(p.avatar):el('span','＋');icon.classList.add(p?'occupant':'vacant');const action=el('small');action.className='action-state';label.append(action);button.append(icon,label);
      button.onclick=()=>openSeat(seat,p||selected||{avatar:role});
      button.disabled=!!observed;
      if(p&&!observed)drag(button,{...p,from:seat});
      drop(button,payload=>{
        if(observed||payload.from===seat)return;
        if(draft.seats[seat]){ $('notice').textContent='請先將原席位的代理人移出，再放入另一位。';return; }
        openSeat(seat,payload);
      });
      $(role==='judge'?'jury':seat.split('-')[0]).append(button);
    }
    readiness();
  }
  function removeSeat(seat) {
    delete draft.seats[seat];markChanged();drawSeats();$('notice').textContent=seatName(seat)+' 已空出。';
  }
  function adapterMenu() {
    const adapter=adapters.find(a=>a.id===$('runtime').value)||fallback[0];
    $('models').replaceChildren(...adapter.models.map(m=>option(m,m)));
    $('model').placeholder=adapter.models[0]||({claude:'sonnet',gemini:'模型 ID',ollama:'模型名稱:標籤',codex:'模型 ID'})[adapter.id];
    $('connection').textContent=(adapter.planned?'規劃中':adapter.available?'已偵測執行環境':bridge?'尚未偵測到':'橋接離線')+' · '+adapter.connection;
  }
  function openSeat(seat,p) {
    editing={seat,from:p.from,avatar:p.avatar};
    $('sideName').textContent=sides[seat.split('-')[0]];
    $('soulTitle').textContent='配置'+roles[roleOf(seat)][0];$('portrait').replaceChildren(portrait(p.avatar));
    $('duty').textContent=roles[roleOf(seat)][1];$('agentName').value=p.name||seatName(seat);
    $('runtime').replaceChildren(...adapters.map(a=>option(a.id,a.name)));
    $('runtime').value=p.runtime||'codex';adapterMenu();$('model').value=p.model||adapters.find(a=>a.id===$('runtime').value)?.models[0]||'';
    $('persona').value=p.persona||'';$('weight').value=String(p.weight||1);$('weightRow').hidden=roleOf(seat)!=='judge';
    $('remove').hidden=!draft.seats[seat];$('soul').showModal();
  }
  async function checkAdapters() {
    try{adapters=(await api('/api/arena/catalog')).adapters;bridge=true;}
    catch{adapters=fallback;bridge=false;}
    if($('soul').open)adapterMenu();readiness();
  }
  async function history() {
    const response=await api('/api/arena/runs');
    $('history').replaceChildren(option('','選擇庭次'),...response.runs.map(r=>option(r.id,(r.instrument?r.instrument+' · ':'')+r.topic+' · '+statuses[r.status])));
    $('history').value=selectedRun;return response.runs;
  }
  function safeLink(url) {
    if(!url)return null;
    try{const u=new URL(url,location.origin);return ['http:','https:'].includes(u.protocol)?u.href:null;}catch{return null;}
  }
  function citations(parent,refs,run) {
    for(const ref of refs||[]) {
      const source=run.packet.sources.find(s=>s.id===ref.id);if(!source)continue;
      const line=el('blockquote'),href=safeLink(source.url),label=source.id+' · '+source.title;
      if(href){const a=el('a',label);a.href=href;a.target='_blank';a.rel='noopener noreferrer';line.append(a);}else line.append(el('strong',label));
      line.append(el('p',ref.quote));parent.append(line);
    }
  }
  function showRun(r) {
    const box=$('record');
    const expanded=new Set(observed?.id===r.id ? [...box.querySelectorAll('details[open]')].map(d=>d.dataset.key) : []);
    const section=key=>{const details=el('details');details.dataset.key=key;details.open=expanded.has(key);return details;};
    const switched=observed?.id!==r.id;
    observed=r;
    $('draftMode').hidden=false;$('topic').readOnly=true;$('topic').value=r.topic;$('instrument').disabled=true;
    if(r.instrument && ![...$('instrument').options].some(o=>o.value===r.instrument))$('instrument').append(option(r.instrument,r.instrument));
    $('instrument').value=r.instrument||'';
    if(switched)drawSeats();live.render(r);
    box.replaceChildren(el('h3',r.topic),el('p',(r.instrument||'無指定標的')+' · '+statuses[r.status]+(r.status==='running'?' · '+live.phaseName(r.phase):'')+' · '+r.turns.filter(t=>t.status==='done').length+' 回合完成'));
    if(r.status==='running'){
      const stop=el('button','停止本庭');stop.onclick=async()=>{try{await api('/api/arena/cancel',{id:r.id});await view(r.id);}catch(e){$('notice').textContent=e.message;}};box.append(stop);
    }
    const packet=section('packet');packet.append(el('summary','本庭封存材料 · '+r.packet.sources.length+' 份原文 · L1 v'+(r.packet.wiki_version??'—')));
    packet.append(el('p','截點 '+r.packet.as_of));
    for(const s of r.packet.sources)citations(packet,[{id:s.id,quote:s.text}],r);
    for(const c of r.packet.context||[])packet.append(el('p',c.layer+' · '+c.statement+' '+(c.sources||[]).join(', ')));
    box.append(packet);
    const jury=Object.entries(r.seats).filter(([k])=>k.startsWith('judge'));
    if(new Set(jury.map(([,p])=>p.runtime+'/'+p.model)).size<jury.length)box.append(el('p','有評審使用相同模型，票數可能反映共同偏誤。'));
    for(const turn of r.turns) {
      const details=section((turn.phase||'')+turn.seat+turn.task);details.append(el('summary',(turn.phase?live.phaseName(turn.phase)+' · ':'')+seatName(turn.seat)+' · '+statuses[turn.status]+(turn.claim?' · '+turn.claim.statement:'')));
      details.append(el('p',r.seats[turn.seat].name+' · '+r.seats[turn.seat].runtime+' / '+r.seats[turn.seat].model));
      if(turn.note)details.append(el('p','隊內簡報 · '+turn.note));
      if(turn.claim?.responds_to)details.append(el('small','回應 '+turn.claim.responds_to));
      if(turn.error)details.append(el('p',turn.error));
      if(turn.claim){details.append(el('p',turn.claim.reason));citations(details,turn.claim.citations,r);}
      if(turn.reviews)details.append(el('p','已提交 '+turn.reviews.length+' 項獨立評核'));
      if(turn.usage?.input_tokens!=null||turn.usage?.output_tokens!=null)details.append(el('small','Token 輸入 '+(turn.usage.input_tokens??'—')+' / 輸出 '+(turn.usage.output_tokens??'—')));
      box.append(details);
    }
    if(r.decision){
      const result=section('award');result.append(el('summary','優勝裁決 · 各評審票與依據'));
      for(const b of r.decision.ballots){
        result.append(el('p',seatName(b.seat)+'（權重 '+r.seats[b.seat].weight+'） · '+
          ({pro:'支持方',con:'反對方',tie:'平手',abstain:'棄權'}[b.choice])+' · 平均論證分　支持 '+b.points.pro.toFixed(2)+' ／ 反對 '+b.points.con.toFixed(2)));
      }
      box.append(result);
    }
    if(r.verdicts?.length){
      box.append(el('h3','逐項裁決'));
      const represented=new Set(r.turns.filter(turn=>turn.claim).map(turn=>turn.seat.split('-')[0]));
      if(represented.size===2 && r.verdicts.every(v=>v.finding==='insufficient')){
        box.append(el('p','雙方本庭提出的命題，依目前材料均不足以成立。'));
      }
    }
    for(const v of r.verdicts||[]){
      const claim=r.turns.find(t=>t.claim?.id===v.claim)?.claim,detail=section(v.claim);
      detail.append(el('summary',v.claim+' · '+findings[v.finding]+' · '+(claim?.statement||'')),el('p','加權票數　'+Object.entries(v.votes).map(([k,n])=>findings[k]+' '+n).join('　')));
      for(const j of v.reviews){
        const review=el('div');review.className='review';
        review.append(el('strong',seatName(j.seat)+' · '+findings[j.finding]),el('p',j.reason),
          el('small','可信度 '+j.scores.credibility+'　邏輯 '+j.scores.logic+'　反駁 '+j.scores.rebuttal+'　完整性 '+j.scores.completeness+'（各 0–4）'));
        citations(review,j.citations,r);detail.append(review);
      }
      box.append(detail);
    }
    readiness();
  }
  async function view(id) {
    const epoch=++generation;clearTimeout(poll);selectedRun=id;write(prefix+'lastRun',id);
    if(!id){observed=null;$('record').textContent='尚未選取庭次。';$('draftMode').hidden=true;
      $('instrument').disabled=false;$('instrument').value=stock;$('topic').readOnly=false;restore();live.render(null);return;}
    try{
      const run=await api('/api/arena/run?id='+encodeURIComponent(id));if(epoch!==generation)return;
      showRun(run);if(run.status==='running')poll=setTimeout(()=>view(id),950);else await history();
    }catch(e){if(epoch!==generation)return;$('record').textContent='讀取庭次失敗：'+e.message;poll=setTimeout(()=>view(id),6000);}
  }
  $('binding').onsubmit=e=>{
    e.preventDefault();
    const {seat,avatar,from}=editing;
    const p={avatar,runtime:$('runtime').value,model:$('model').value.trim(),name:$('agentName').value.trim(),persona:$('persona').value.trim(),weight:roleOf(seat)==='judge'?Number($('weight').value):1};
    if(!p.name||!(/^[a-zA-Z0-9][a-zA-Z0-9_./:-]{0,127}$/).test(p.model)){ $('connection').textContent='請填寫代理人名稱及有效的模型 ID。';return;}
    if(from&&from!==seat)delete draft.seats[from];draft.seats[seat]=p;
    profiles=[p,...profiles.filter(other=>other.name!==p.name)].slice(0,32);write(prefix+'profiles',profiles);
    selected=null;markChanged();drawPalette();drawSeats();$('soul').close();$('notice').textContent=p.name+' 已入席。';
  };
  $('dismiss').onclick=()=>$('soul').close();
  $('remove').onclick=()=>{removeSeat(editing.seat);$('soul').close();};
  $('runtime').onchange=()=>{adapterMenu();$('model').value=adapters.find(a=>a.id===$('runtime').value)?.models[0]||'';};
  $('refresh').onclick=checkAdapters;
  drop($('library'),p=>{if(slots.includes(p.from))removeSeat(p.from);});
  $('topic').oninput=()=>{draft.topic=$('topic').value;markChanged();readiness();};
  $('instrument').onchange=()=>{stock=$('instrument').value;if(parent!==window)parent.postMessage({arenaStock:stock},location.origin);restore();};
  $('draftMode').onclick=()=>{ $('history').value='';view(''); };
  $('history').onchange=()=>view($('history').value);
  $('gavel').onclick=async()=>{
    if($('gavel').disabled)return;
    busy=true;readiness();
    try{
      const requestId=draft.requestId||crypto.randomUUID();draft.requestId=requestId;remember();
      const r=await api('/api/arena/start',{id:requestId,instrument:stock,seats:draft.seats,topic:draft.topic});
      delete draft.requestId;remember();showRun(r);
      await view(r.id);
      history().catch(()=>{});

    }catch(e){$('notice').textContent='開庭請求：'+e.message;}
    finally{busy=false;readiness();}
  };
  if(stock)$('instrument').append(option(stock,stock));
  $('instrument').value=stock;restore();live.render(null);checkAdapters();
  api('/api/context/catalog').then(data=>{
    for(const item of data.instruments||[])if(item.instrument!==stock)$('instrument').append(option(item.instrument,item.instrument));
  }).catch(()=>{});
  history().then(runs=>{const id=runs.find(r=>r.status==='running')?.id||read(prefix+'lastRun','');if(runs.some(r=>r.id===id)){ $('history').value=id;view(id); }}).catch(()=>{$('record').textContent='連上主機橋接後即可讀取庭次紀錄。';});
})();
