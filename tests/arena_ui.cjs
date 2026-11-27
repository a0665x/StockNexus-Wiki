const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const {randomUUID}=require('node:crypto');
const tick=()=>new Promise(r=>setTimeout(r,5));
test('empty court, audition, drag to seat, cancel move, remove, keyboard setup and gavel',async t=>{
  const dom=new JSDOM(fs.readFileSync('dist/arena.html','utf8'),{url:'http://localhost/arena?instrument=NASDAQ:NVDA',runScripts:'outside-only'});
  t.after(()=>dom.window.close());const w=dom.window,d=w.document,$=id=>d.getElementById(id);
  w.HTMLDialogElement.prototype.show=w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.HTMLElement.prototype.scrollIntoView=()=>{};Object.defineProperty(w,"crypto",{value:{randomUUID}});
  const catalog={adapters:[{id:'codex',models:['test-model'],available:true,name:'Codex',connection:'host'}]};
  const posts=[];let result=null;
  w.fetch=async(path,opts={})=>{
    let body={};
    if(path.endsWith('/arena/catalog'))body=catalog;
    if(path.endsWith('/context/catalog'))body={instruments:[]};
    if(path.endsWith('/runs'))body={runs:result?[result]:[]};
    if(path.endsWith('/start')){
      const req=JSON.parse(opts.body);posts.push(req);
      result={...req,status:'completed',packet:{as_of:'test',sources:[],context:[]},turns:[],verdicts:[]};body=result;
    }
    if(path.includes('/run?'))body=result;
    return {ok:true,json:async()=>body};
  };
  // jsdom v16 lacks DragEvent/DataTransfer. Drive the installed drop handler directly.
  const drops=new WeakMap(),listen=w.HTMLElement.prototype.addEventListener;
  w.HTMLElement.prototype.addEventListener=function(type,fn,...args){
    if(type==='drop')drops.set(this,fn);
    return listen.call(this,type,fn,...args);
  };
  w.eval(fs.readFileSync('dist/arena-live.js','utf8'));
  w.eval(fs.readFileSync('dist/arena.js','utf8'));await tick();
  const seat=id=>d.querySelector('[data-seat="'+id+'"]');
  const submit=()=>$('binding').dispatchEvent(new w.Event('submit',{cancelable:true}));
  function drop(node,p){
    drops.get(node)({preventDefault(){},dataTransfer:{getData:()=>JSON.stringify(p)}});
  }
  assert.equal(d.querySelectorAll('.seat').length,11);assert.equal(d.querySelectorAll('.occupant').length,0);
  assert.equal($('gavel').disabled,true);assert.equal(posts.length,0);
  drop(seat('pro-scout'),{avatar:'planner'});assert.equal($('soul').open,true);$('agentName').value='Aria';submit();
  assert.match(seat('pro-scout').textContent,/Aria/);assert.match($('saved').textContent,/Aria/);
  drop(seat('con-scout'),{avatar:'planner',from:'pro-scout',name:'Aria',runtime:'codex',model:'test-model'});
  $('dismiss').click();assert.match(seat('pro-scout').textContent,/Aria/);assert.match(seat('con-scout').textContent,/空席/);
  drop($('library'),{avatar:'planner',from:'pro-scout'});assert.match(seat('pro-scout').textContent,/空席/);
  $('saved').querySelector('button').click();seat('con-lead').click();submit();assert.match(seat('con-lead').textContent,/Aria/);
  for(const s of [...d.querySelectorAll('.seat')].map(n=>n.dataset.seat).filter(s=>!['con-lead','judge-2','judge-3'].includes(s))){seat(s).click();submit();}
  $('topic').value='Does the filing support the claim?';$('topic').dispatchEvent(new w.Event('input'));
  assert.equal($('gavel').disabled,false);$('gavel').click();await tick();
  assert.equal(posts.length,1);assert.equal(posts[0].instrument,'NASDAQ:NVDA');assert.equal(Object.keys(posts[0].seats).length,9);
  assert.match($('record').textContent,/已結束/);
});

test('news and Wiki books show the sealed graph, a read highlights its nodes, observer asks about the selected hearing',async t=>{
  const dom=new JSDOM(fs.readFileSync('dist/arena.html','utf8'),{url:'http://localhost/arena/court',runScripts:'outside-only'});
  t.after(()=>dom.window.close());const w=dom.window,$=id=>w.document.getElementById(id);
  w.HTMLDialogElement.prototype.show=w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
  w.eval(fs.readFileSync('dist/arena-live.js','utf8'));
  const packet={sources:[{id:'E1',revision:'original-A',title:'Orders',text:'Orders rose.'},{id:'E2',revision:'original-B',title:'Sales',text:'Sales fell.'}],
    context:[{layer:'News Graph',id:'EDGE-2',statement:'shared entity',sources:['E1','E2']},
      {layer:'L1',id:'L1-op',statement:'Sales outlook',sources:['E2']}],wiki_version:7,graph_snapshot:'snapshot1'};
  const asks=[];
  const live=w.ArenaLive.mount({seatName:id=>id,api:async(path,body)=>{asks.push([path,body]);return {answer:'The opposition checked sales.'};}});
  const r={id:'sample',topic:'Sales?',status:'running',phase:'rebuttal',packet,seats:{'pro-lead':{model:'fixture',runtime:'codex'}},
    events:[{seq:1,kind:'read',phase:'rebuttal',seat:'con-challenger',at:new Date().toISOString(),book:'wiki',ids:['K2']}],turns:[]};
  live.render(r);$('wikiBook').click();
  assert.equal($('galaxy').open,true);assert.equal($('constellation').querySelectorAll('circle').length,2);
  assert.equal($('constellation').querySelectorAll('.hit').length,1);assert.match($('nodeDetail').textContent,/L1-op/);
  $('closeGalaxy').click();$('newsBook').click();assert.equal($('constellation').querySelectorAll('line').length,1);
  $('closeGalaxy').click();$('eventLog').querySelector('button').click();assert.match($('galaxyTitle').textContent,/Wiki/);
  $('closeGalaxy').click();$('observerTab').click();assert.equal($('observerPane').hidden,false);
  $('observerQuestion').value='Which sources?';await $('observerForm').onsubmit({preventDefault(){}});
  assert.equal(asks[0][1].id,'sample');assert.match($('observerMessages').textContent,/checked sales/);
  live.render({...r,id:'another',events:[]});assert.equal($('observerMessages').textContent,'');
});

test('switching into the court preserves header and the original mode controls, including browser back',()=>{
  const dom=new JSDOM('<header id="workbenchHeader"><button id="openSearch"></button><button id="openResults"></button><button id="relationOpen"></button></header><main id="stage"><div id="graphTools"><div class="mode-tabs"><button id="modeNetwork" class="active"></button><button id="modeTimeline"></button><button id="modeWiki"></button><button id="modeArena"></button></div></div></main><section hidden id="wikiPanel"><button id="wikiArena"></button><button id="wikiBack"></button></section>',{url:'http://localhost/',runScripts:'outside-only'});
  try{
    const w=dom.window,$=id=>w.document.getElementById(id),header=$('workbenchHeader'),modes=$('modeArena').parentElement;
    w.getComputedStyle=node=>node.style;const errors=[];w.addEventListener('error',e=>errors.push(e.message));
    w.eval(fs.readFileSync('dist/arena-shell.js','utf8'));$('modeArena').click();
    assert.equal(w.location.pathname,'/arena');assert.equal($('arenaPanel').hidden,false);assert.equal(modes.parentElement,$('arenaPanel'));
    assert.deepEqual(errors,[]);assert.equal($('workbenchHeader'),header);assert.equal($('modeArena').getAttribute('aria-pressed'),'true');
    w.history.replaceState({},'','/');w.dispatchEvent(new w.PopStateEvent('popstate'));
    assert.equal($('arenaPanel').hidden,true);assert.equal(modes.parentElement,$('graphTools'));assert.equal($('modeNetwork').getAttribute('aria-pressed'),'true');
  }finally{dom.window.close();}
});
