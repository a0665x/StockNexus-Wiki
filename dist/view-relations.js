/* View-scoped server work; rendering and background admission stay on the browser. */
(function(root){
  const en=()=>root.AtlasI18n?.language()==='en';
  const say=(zh,english)=>en()?english:zh;
  function create(hooks){
    let key=null,ticket=0,abort=null,lastInput=0,held=false;
    const completed=new Map();
    function remember(key,result){completed.delete(key);completed.set(key,result);while(completed.size>12)completed.delete(completed.keys().next().value);}
    let state={phase:'idle',pairs_checked:0};
    const publish=patch=>{state={...state,...patch};hooks.status(state);};
    const input=()=>{lastInput=Date.now();};
    for(const type of ['pointermove','wheel','keydown'])document.addEventListener(type,input,{passive:true,capture:true});
    document.addEventListener('pointerdown',()=>{held=true;input();},{passive:true,capture:true});
    for(const type of ['pointerup','pointercancel','lostpointercapture'])document.addEventListener(type,()=>{held=false;input();},{passive:true,capture:true});
    root.addEventListener('blur',()=>{held=false;input();});
    const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    async function idle(mine){
      while(mine===ticket){
        while(mine===ticket&&(held||document.hidden||Date.now()-lastInput<650))await wait(100);
        if(mine!==ticket)return false;
        await new Promise(resolve=>(root.requestIdleCallback||((fn)=>setTimeout(fn,0)))(resolve,{timeout:500}));
        if(mine===ticket&&!held&&!document.hidden&&Date.now()-lastInput>=650)return true;
      }
      return false;
    }
    async function run(scope,mine){
      try{
        // First pass starts promptly, independently of the source-fetch stream.
        await wait(40);if(mine!==ticket)return;
        const stages=scope.cfg.adaptive?['strict','complete']:['complete'];
        for(const stage of stages){
          if(stage==='complete'&&stages.length>1){publish({phase:'idle-fill'});if(!await idle(mine))return;}
          publish({phase:'calculating',stage,pairs_checked:0,pairs_computed:0,pairs_reused:0,cache_hit:false,group:null});
          const request=new AbortController();abort=request;
          const timeout=setTimeout(()=>request.abort(),300000);
          let result=null,finished=false;
          try{
            const response=await fetch('/api/graph/preview',{method:'POST',headers:{'Content-Type':'application/json'},signal:request.signal,
              body:JSON.stringify({ticker:scope.ticker||'',source_graphs:scope.groups,relation_settings:scope.cfg,include_cross:!scope.separate,stage})});
            if(!response.ok||!response.body)throw Error(`HTTP ${response.status}`);
            const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
            while(true){
              const {value,done}=await reader.read();
              if(mine!==ticket){await reader.cancel();return;}
              buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});
              let at;while((at=buffer.indexOf('\n'))>=0){
                const line=buffer.slice(0,at);buffer=buffer.slice(at+1);if(!line)continue;
                const event=JSON.parse(line);
                if(event.type==='progress')publish(event);
                if(event.type==='result')result=event;
                if(event.type==='error')throw Error(event.message);
                if(event.type==='done')finished=true;
              }
              if(done)break;
            }
          }finally{clearTimeout(timeout);if(abort===request)abort=null;}
          if(!finished||!result)throw Error(say('關聯串流中斷','Relation stream interrupted'));
          publish({phase:'render-wait',pairs_checked:result.pairs_checked,pairs_computed:result.pairs_computed,pairs_reused:result.pairs_reused});
          if(!await idle(mine))return;
          if(stage==='complete')remember(scope.key,result);
          hooks.put(result,scope);
          if(mine!==ticket)return;
        }
        publish({phase:'ready'});
      }catch(error){if(mine===ticket)publish({phase:'error',error:error.name==='AbortError'?say('計算逾時，請重試','Calculation timed out; retry'):error.message});}
    }
    return {
      seed(key,result){remember(key,result);},
      schedule(scope){
        if(!scope){if(key!==null){ticket++;abort?.abort();key=null;publish({phase:'idle',pairs_checked:0});}return;}
        if(scope.key===key)return;
        key=scope.key;const mine=++ticket;abort?.abort();
        const cached=completed.get(key);
        if(cached){remember(key,cached);publish({phase:'ready',pairs_checked:0,pairs_computed:0,pairs_reused:0,cache_hit:true,error:null});hooks.put(cached,scope);return;}
        publish({phase:'queued',pairs_checked:0,pairs_computed:0,pairs_reused:0,cache_hit:false,error:null});run(scope,mine);
      },
      cancel(){ticket++;abort?.abort();publish({phase:'stopped'});},
      retry(){key=null;hooks.retry();},
      state:()=>state
    };
  }
  const help={
    nodes:()=>say('目前顯示的新聞節點／符合篩選的新聞總數。優先選取項目與分類，再依發布時間由新到舊；3D 最多 2,400 個，時間軸保留全部篩選結果。未顯示的新聞仍可搜尋。','Displayed news / filtered news. Selected items and categories first, then newest publication time; at most 2,400 in 3D; the timeline retains all filtered news. Hidden news remains searchable.'),
    calculation:()=>say('候選配對是待檢查關聯的兩則新聞。先依發布時間找出啟用規則日期窗口內的配對，再比對公司／代碼、主題與標題。計數是本階段已檢查的組數，不是連線數；快取命中會重用已檢查的結果（包括無關聯），新計算只處理缺少或內容／規則已改變的配對。連線排名仍依目前視圖重新選擇。','A candidate pair is two news items awaiting a relation check. Publication-time windows select pairs, then company/ticker, topic and title rules test them. Counts are checks in this pass, not edges; source tasks or adaptive stages may revisit a pair. Only the current view is computed.'),
    edges:()=>say('已繪製連線／目前視圖已找到且通過顯示門檻的關聯。兩端都必須在可見節點內；連線預算為節點預算的 3 倍。這不是全部新聞的關聯總數。','Drawn edges / discovered relations passing display thresholds in this view. Both endpoints must be visible; edge budget is 3× the node budget. This is not a whole-dataset relation count.'),
    status:()=>say('先建立目前視圖的嚴格關聯，讓你操作；閒置時再補算自適應關聯。操作期間延後套用新結果；切換範圍會取消舊請求，已完成的配對保留，近期相同視圖直接重用。預算外新聞暫不計算，不代表沒有關聯。','Strict relations arrive first. Adaptive completion starts when idle; new results wait during interaction. Scope changes cancel stale requests but retain completed pair work; recent identical views are reused. News outside the budget is deferred, not deemed unrelated.')
  };
  function tooltip(container){
    const box=document.createElement('div');box.id='activityHelp';box.className='activity-help raw';box.setAttribute('role','tooltip');box.hidden=true;document.body.append(box);
    let timer=null,target=null,point=null;
    const hide=()=>{clearTimeout(timer);box.hidden=true;target?.removeAttribute('aria-describedby');};
    function show(){
      if(!target?.isConnected)return;
      box.textContent=help[target.dataset.activityHelp]?.()||'';box.hidden=false;target.setAttribute('aria-describedby',box.id);
      const rect=target.getBoundingClientRect(),bounds=box.getBoundingClientRect();
      box.style.left=Math.max(8,Math.min(innerWidth-bounds.width-8,rect.left))+'px';
      box.style.top=Math.max(8,Math.min(innerHeight-bounds.height-8,rect.bottom+8))+'px';
    }
    container.addEventListener('pointermove',event=>{
      const next=event.target.closest('[data-activity-help]');
      if(next===target&&point?.x===event.clientX&&point?.y===event.clientY)return;
      hide();target=next;point={x:event.clientX,y:event.clientY};if(target)timer=setTimeout(show,650);
    });
    container.addEventListener('pointerleave',()=>{hide();target=null;point=null;});
    container.addEventListener('focusin',event=>{hide();target=event.target.closest('[data-activity-help]');point=null;if(target)show();});
    container.addEventListener('focusout',hide);
    document.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});
    root.addEventListener('scroll',hide,true);root.addEventListener('resize',hide);root.addEventListener('blur',hide);
  }
  root.AtlasViewRelations={create,tooltip,say};
})(globalThis);
