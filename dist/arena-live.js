'use strict';
window.ArenaLive = (() => {
  const phases={prepare:'資料準備',opening:'立論',rebuttal:'攻防',regroup:'隊內重整',deepen:'深化',closing:'總答辯',judge:'裁決'};
  const winners={pro:'支持方優勝',con:'反對方優勝',tie:'雙方平手',undecided:'未決出優勝方'};
  const NS='http://www.w3.org/2000/svg';
  const $=id=>document.getElementById(id);
  const el=(tag,text)=>{const node=document.createElement(tag);if(text!=null)node.textContent=text;return node;};
  const svg=(tag,attrs)=>{const n=document.createElementNS(NS,tag);for(const [key,v] of Object.entries(attrs))n.setAttribute(key,v);return n;};
  function figure(role){
    const person=el('span');person.className='figure '+role;person.setAttribute('aria-hidden','true');
    const body=el('img');body.src='/arena-characters/'+role+'.png';body.alt='';
    const accessory=el('i');accessory.className='costume';accessory.append(el('b'),el('i'));
    person.append(body,accessory);return person;
  }
  // Nodes and links are drawn only when the sealed hearing records them.
  function graph(packet,book){
    const nodes=new Map(),links=[];
    function add(id,label,text,keys,kind){if(!nodes.has(id))nodes.set(id,{id,label,text,keys:new Set(),kind});for(const k of keys)nodes.get(id).keys.add(k);}
    function link(a,b){if(a!==b && nodes.has(a)&&nodes.has(b)&&!links.some(l=>l[0]===a&&l[1]===b))links.push([a,b]);}
    const docs=new Map(packet.sources.map(s=>[s.id,s]));
    function addSource(s){const id=s.revision||s.id;add(id,s.title||s.id,s.text,[s.id],s.layer);return id;}
    if(book==='news')for(const s of docs.values())addSource(s);
    packet.context.forEach((c,i)=>{
      const key='K'+(i+1);
      const refs=(c.sources||[]).map(id=>docs.get(id)).filter(Boolean);
      if(c.layer==='News Graph'&&book==='news'&&refs.length===2){
        for(const s of refs)nodes.get(s.revision||s.id).keys.add(key);
        link(refs[0].revision||refs[0].id,refs[1].revision||refs[1].id);
      }else if(book==='wiki'&&['L1','L2'].includes(c.layer)){
        add(c.id,c.title||c.statement,c.statement,[key],c.layer);
        if(c.layer==='L1')for(const source of refs)link(c.id,addSource(source));
      }
    });
    if(book==='wiki'){
      for(const edge of packet.wiki_edges||[])link(edge.source,edge.target);
      for(const c of packet.context.filter(c=>c.layer==='L2')){
        for(const id of c.parents||(c.derived_from||[]).map(k=>k.replace(/:claim$/,'')))link(c.id,id);
      }
    }
    return {nodes:[...nodes.values()],links};
  }
  function layout(nodes,links){
    // Deterministic force layout holds positions when another read arrives.
    const point=new Map(nodes.map((n,i)=>[n.id,{x:230+Math.cos(i*2.4)*Math.sqrt(i+1)*19,y:120+Math.sin(i*2.4)*Math.sqrt(i+1)*12}]));
    for(let step=0;step<85;step++){
      const forces=new Map(nodes.map(n=>[n.id,{x:0,y:0}]));
      function force(a,b,k){const p=point.get(a),q=point.get(b),x=p.x-q.x,y=p.y-q.y,d=Math.max(1,Math.hypot(x,y));
        const f=k(d);forces.get(a).x+=x/d*f;forces.get(a).y+=y/d*f;forces.get(b).x-=x/d*f;forces.get(b).y-=y/d*f;}
      for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++)force(nodes[i].id,nodes[j].id,d=>330/(d*d+1));
      for(const [a,b] of links)force(a,b,d=>(57-d)*.045);
      for(const [id,p] of point){const f=forces.get(id);p.x=Math.max(15,Math.min(445,p.x+f.x+(230-p.x)*.002));p.y=Math.max(15,Math.min(225,p.y+f.y+(120-p.y)*.004));}
    }
    return point;
  }
  function mount({api,seatName}){
    let run=null,currentBook='news',pinned=null,chosen=null,seen=0,lastRun='';
    const phaseName=key=>phases[key]||({scout:'立論',challenger:'駁論',planner:'深化',lead:'總答辯'})[key]||key;
    const chat=new Map(),asking=new Set(),timers=new Map();
    const events=()=>run?.events||[];
    const readEvents=book=>events().filter(e=>e.book===book);
    const eventText=e=>{
      const who=e.seat?seatName(e.seat)+' · ':'';
      if(e.kind==='read'||e.kind==='verify')return who+(e.kind==='read'?'調閱':'核對引文')+' '+(e.book==='wiki'?'LLM Wiki':'新聞節點')+' '+e.ids.join('、');
      if(e.kind==='brief')return who+'交付簡報給'+(e.recipient?seatName(e.recipient):'隊友');
      if(e.kind==='speech')return who+e.claim+(e.target?' 回應 '+e.target:' 立論');
      if(e.kind==='stage')return '進入'+phaseName(e.phase);
      if(e.kind==='decision')return winners[e.winner];
      if(e.kind==='turn_end')return who+({done:'完成',failed:'失敗',cancelled:'停止',interrupted:'中斷'}[e.status]||e.status);
      return who+'開始'+phaseName(e.phase);
    };
    function switchTab(which){
      for(const key of ['source','observer']){
        $(key+'Tab').setAttribute('aria-selected',String(which===key));$(key+'Pane').hidden=which!==key;
      }
    }
    function openBook(book,event=null,node=null){
      currentBook=book;pinned=event;chosen=node;
      if(!$('galaxy').open)$('galaxy').show();
      drawGalaxy();
    }
    function drawGalaxy(){
      const packet=run?.packet||{sources:[],context:[]};
      const {nodes,links}=graph(packet,currentBook);
      const recent=pinned||readEvents(currentBook).at(-1),keys=new Set(recent?.ids||[]);
      const matches=n=>[...n.keys].some(k=>keys.has(k));
      $('galaxyTitle').textContent=currentBook==='wiki'?'LLM Wiki 星圖':'新聞節點星圖';
      $('galaxyScope').textContent=(currentBook==='wiki'?'L1 v'+(packet.wiki_version??'—'):'圖譜快照 '+(packet.graph_snapshot?.slice(0,8)||'—'))+' · 本庭 '+nodes.length+' 節點 / '+links.length+' 關聯'+(recent?' · '+eventText(recent):'');
      const plot=$('constellation');plot.replaceChildren();
      if(!nodes.length){plot.textContent='本庭尚無此類索引節點。';$('nodeDetail').replaceChildren();return;}
      if(!nodes.some(n=>n.id===chosen))chosen=(nodes.find(matches)||nodes[0]).id;
      const canvas=svg('svg',{viewBox:'0 0 460 240','aria-label':$('galaxyTitle').textContent});
      const positions=layout(nodes,links);
      for(const [a,b] of links){const p=positions.get(a),q=positions.get(b);canvas.append(svg('line',{x1:p.x,y1:p.y,x2:q.x,y2:q.y}));}
      for(const n of nodes){
        const p=positions.get(n.id),g=svg('g',{transform:'translate('+p.x+' '+p.y+')',tabindex:0,role:'button','aria-label':[...n.keys].join(', ')+' '+n.label,class:(matches(n)?'hit ':'')+(n.id===chosen?'selected':'')});
        const key=[...n.keys][0],title=svg('title',{});title.textContent=key+' '+n.label;
        const label=svg('text',{x:8,y:-5});label.textContent=key;g.append(title,svg('circle',{r:matches(n)?6:4}),label);
        const focus=()=>{chosen=n.id;drawGalaxy();};
        g.onclick=focus;g.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();focus();}};canvas.append(g);
      }
      plot.append(canvas);const n=nodes.find(n=>n.id===chosen);
      const related=packet.sources.filter(s=>(s.revision||s.id)===n.id);
      const excerpts=related.filter(s=>keys.has(s.id));
      const displayed=excerpts.length?excerpts:related;
      const source=displayed[0];
      $('nodeDetail').replaceChildren(el('strong',[...n.keys].join('、')+' · '+n.label));
      if(displayed.length){
        for(const s of displayed)$('nodeDetail').append(el('p',s.id+' · '+s.text));
      }else $('nodeDetail').append(el('p',n.text));
      $('nodeDetail').append(el('small',n.id));
      if(source?.url && (/^https?:\/\//i.test(source.url)||source.url.startsWith('/documents?'))){
        const a=el('a','開啟來源原文 ↗');a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';$('nodeDetail').append(a);
      }
    }
    function flash(node,kind){
      if(!node)return;
      clearTimeout(timers.get(node));node.dataset.action=kind;
      timers.set(node,setTimeout(()=>{delete node.dataset.action;timers.delete(node);},1800));
    }
    function visit(evt){
      const from=document.querySelector('[data-seat="'+evt.seat+'"]');
      const to=evt.book?$(evt.book+'Book'):document.querySelector('[data-seat="'+evt.recipient+'"]');
      if(!from||!to)return;
      flash(from,evt.kind);flash(to,evt.kind);
      if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || !from.animate)return;
      const court=document.querySelector('.court'),origin=court.getBoundingClientRect();
      const a=from.getBoundingClientRect(),b=to.getBoundingClientRect();
      const mini=figure(run.seats[evt.seat].avatar);mini.classList.add('visitor');
      const x=a.left+a.width/2-origin.left-16,y=a.top+a.height/2-origin.top-16;
      mini.style.left=x+'px';mini.style.top=y+'px';
      const dx=b.left+b.width/2-a.left-a.width/2,dy=b.top+b.height/2-a.top-a.height/2;
      court.append(mini);
      const walk=mini.animate([{opacity:0,transform:'translate(0,0)'},{opacity:1,offset:.14},
        {opacity:1,transform:'translate('+dx+'px,'+(dy-7)+'px) rotate(-8deg)',offset:.55},
        {opacity:1,transform:'translate('+dx+'px,'+dy+'px)',offset:.72},
        {opacity:0,transform:'translate(0,0)'}],{duration:1300,easing:'ease-in-out'});
      walk.onfinish=walk.oncancel=()=>mini.remove();
    }
    let chatKey=null;
    function drawChat(){
      const key=[run?.id,(chat.get(run?.id)||[]).length,asking.has(run?.id)].join('|');
      if(key===chatKey)return;
      chatKey=key;
      $('observerMessages').replaceChildren(...(chat.get(run?.id)||[]).map(m=>{
        const p=el('p',m.text);p.className='utterance '+m.role;return p;
      }));
      $('observerInfo').textContent=run?'讀取本庭事件與公開發言 · '+run.seats['pro-lead'].runtime+' / '+run.seats['pro-lead'].model:'選取庭次後可詢問法庭進度。';
      $('observerSend').disabled=!run||asking.has(run.id);
      $('observerSend').textContent=asking.has(run?.id)?'觀察員查閱中…':'送出';
    }
    $('observerForm').onsubmit=async e=>{
      e.preventDefault();
      const id=run?.id,question=$('observerQuestion').value.trim();if(!id||!question||asking.has(id))return;
      const messages=chat.get(id)||[],history=messages.slice(-6).map(m=>({...m,text:m.text.slice(0,2400)}));
      chat.set(id,messages);asking.add(id);messages.push({role:'user',text:question});$('observerQuestion').value='';drawChat();
      try{const r=await api('/api/arena/observe',{id,question,history});messages.push({role:'assistant',text:r.answer});}
      catch(e){messages.push({role:'assistant',text:'觀察員無法作答：'+e.message});}
      finally{asking.delete(id);if(run?.id===id)drawChat();}
    };
    $('sourceTab').onclick=()=>switchTab('source');$('observerTab').onclick=()=>switchTab('observer');
    $('newsBook').onclick=()=>openBook('news');$('wikiBook').onclick=()=>openBook('wiki');
    $('closeGalaxy').onclick=()=>$('galaxy').close();
    $('galaxy').addEventListener('keydown',e=>{if(e.key==='Escape')$('galaxy').close();});
    function render(r){
      const changed=(r?.id||'')!==lastRun;
      if(changed){pinned=null;chosen=null;seen=0;lastRun=r?.id||'';}
      run=r;
      const list=events(),log=$('eventLog'),now=r?.phase;
      $('phaseTrack').replaceChildren(...Object.entries(phases).map(([k,label])=>{
        const n=el('span',label);if(r?.status==='running'&&now===k)n.setAttribute('aria-current','step');
        else if(list.some(ev=>ev.kind==='stage'&&ev.phase===k))n.classList.add('visited');return n;
      }));
      const start=r?.status==='running';
      for(const seat of document.querySelectorAll('.seat')){
        const turn=start&&r.turns.findLast(t=>t.seat===seat.dataset.seat&&t.status==='running');
        seat.dataset.state=turn?(turn.task==='brief'?'discuss':turn.task==='research'?'search':'speak'):'idle';
        const note=seat.querySelector('.action-state');if(note)note.textContent=turn?phaseName(turn.phase):'';
      }
      for(const book of ['news','wiki']){
        const recent=readEvents(book).at(-1),button=$(book+'Book');
        button.title=recent?eventText(recent):'開啟本庭封存的來源星圖';

      }
      if(!changed || start){
        const fresh=list.filter(e=>e.seq>seen && (e.book||e.recipient) && (!changed || Date.now()-Date.parse(e.at)<2500));
        for(const evt of fresh)visit(evt);
      }
      if(changed||seen!==list.length||!r||!log.childElementCount){
        log.replaceChildren(...list.slice().reverse().map(evt=>{
          const li=el('li'),time=el('time',new Date(evt.at).toLocaleTimeString('zh-TW',{hour12:false}));
          li.append(time);
          if(evt.book){const b=el('button',eventText(evt));b.onclick=()=>openBook(evt.book,evt);li.append(b);}
          else li.append(el('span',eventText(evt)));return li;
        }));
        $('sourceIndex').replaceChildren();
        if(!r)$('sourceIndex').textContent='開庭後顯示封存來源與查閱紀錄。';
        else {
          for(const book of ['news','wiki']){
            const nodes=graph(r.packet,book).nodes,b=el('button',(book==='news'?'新聞節點':'LLM Wiki')+' · '+nodes.length+' 節點');
            b.onclick=()=>openBook(book);$('sourceIndex').append(b);
          }
          if(!list.length)log.append(el('li','這個庭次沒有逐事件紀錄。'));
        }
        if($('galaxy').open){if(!pinned && readEvents(currentBook).at(-1)?.seq>seen)chosen=null;drawGalaxy();}
      }
      seen=list.length;
      $('resultBanner').hidden=!r?.decision;
      if(r?.decision)$('resultBanner').textContent=winners[r.decision.winner]+' · 加權票　支持 '+r.decision.weights.pro+' ／ 反對 '+r.decision.weights.con+' ／ 平手 '+r.decision.weights.tie+' ／ 棄權 '+r.decision.weights.abstain;
      drawChat();
    }
    function pane(key){document.body.dataset.mobilePane=document.body.dataset.mobilePane===key?'':key;}
    $('showLibrary').onclick=()=>pane('library');$('showInspector').onclick=()=>pane('sources');
    window.addEventListener('message',e=>{
      if(e.origin!==location.origin||e.source!==parent||!['library','sources'].includes(e.data?.arenaPane))return;
      pane(e.data.arenaPane);
    });
    return {render,phaseName};
  }
  return {figure,graph,mount};
})();
