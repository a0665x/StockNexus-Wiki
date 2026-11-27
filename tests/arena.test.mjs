import assert from 'node:assert/strict';
import test from 'node:test';
import { randomUUID } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';
import { createArena } from '../chat/arena.mjs';

const duties=['scout','challenger','planner','lead'];
const catalog=async()=>[{id:'codex',available:true,models:['test-model']}];
function hearing(n=2) {
  const seats={};
  for(const side of ['pro','con'])for(const role of duties)seats[side+'-'+role]={avatar:role,name:side+'-'+role};
  for(let j=1;j<=n;j++)seats['judge-'+j]={avatar:'judge',name:'judge-'+j,weight:1};
  for(const p of Object.values(seats))Object.assign(p,{runtime:'codex',model:'test-model'});
  return {id:randomUUID(),instrument:'NASDAQ:NVDA',topic:'Did orders increase?',seats,
    packet:{instrument:'NASDAQ:NVDA',sources:[{id:'E1',text:'Orders grew in the quarter.'}],context:[]}};
}
const citation={id:'E1',quote:'Orders grew'};
function response(seat,prompt) {
  const {prior_claims,task,reply_target,index}=JSON.parse(prompt.split('\n').at(-1));
  if(task==='research')return {text:JSON.stringify({ids:index.map(i=>i.id).slice(0,4),note:'Investigate filings.'})};
  if(task==='brief')return {text:JSON.stringify({note:'Check the competing demand hypothesis.'})};
  const data=seat.avatar==='judge'?{reviews:prior_claims.map(c=>({claim:c.id,finding:'insufficient',citations:[],
    reason:'The sample covers only one quarter.',scores:{credibility:2,logic:3,rebuttal:1,completeness:2}}))}
    :{statement:'Claim of '+seat.name,reason:'A quarterly observation',responds_to:reply_target,citations:[citation]};
  return {text:JSON.stringify(data),usage:{input_tokens:12,output_tokens:5}};
}
async function finish(run) {
  for(let n=0;run.status==='running'&&n<300;n++)await delay(5);
  assert.notEqual(run.status,'running');return run;
}
test('team preparation precedes alternating exchanges, the second speaker targets the first and jurors vote independently',async()=>{
  const seen=[], req=hearing(3);
  const arena=createArena({chooseFirst:()=>'con',adapters:{catalog,async turn(p,prompt){
    seen.push(JSON.parse(prompt.split('\n').at(-1)));
    const res=response(p,prompt),c=seen.at(-1);
    if(c.phase==='rebuttal'&&c.seat==='pro-challenger'){
      res.text=JSON.stringify({...JSON.parse(res.text),regroup:true});
    }
    return res;
  }}});
  const r=await arena.start(req);assert.equal(await arena.start(req),r);
  await finish(r);assert.equal(r.status,'completed');assert.equal(r.turns.length,16);
  const speech=seen.filter(c=>c.task==='speech');
  assert.equal(speech.length,8);
  speech.forEach((c,i)=>{
    assert.equal(c.prior_claims.length,i);assert.equal(c.reply_target,i?'C'+i:null);
    assert.equal(c.seat.split('-')[0],i%2?'pro':'con');
    assert.ok(c.team_notes.length>=2);
  });
  const jurors=seen.filter(c=>c.task==='ballot');
  assert.equal(jurors.length,3);assert.deepEqual(jurors[0].prior_claims,jurors[2].prior_claims);
  assert.equal(jurors[0].prior_claims.length,8);
  assert.deepEqual(r.events.filter(e=>e.kind==='stage').map(e=>e.phase),['prepare','opening','rebuttal','regroup','deepen','closing','judge']);
  assert.equal(r.verdicts.every(v=>v.finding==='insufficient'),true);assert.equal(r.decision.winner,'undecided');
  await assert.rejects(arena.start({...req,topic:'Different'}),/識別碼/);
});
test('a stuck opening seat expires independently and the other side and later rounds finish',async()=>{
  const arena=createArena({timeout:35,adapters:{catalog,turn(p,prompt){
    if(p.name==='pro-scout')return new Promise(()=>{});
    return response(p,prompt);
  }}});
  const r=await arena.start(hearing(1));await finish(r);
  assert.equal(r.status,'partial');assert.equal(r.turns.find(t=>t.seat==='con-scout').status,'done');
  assert.match(r.turns.find(t=>t.seat==='pro-scout').error,/超過/);assert.ok(r.verdicts.length>=4 && r.verdicts.length<8);
});
test('a fabricated quote invalidates that ballot, missing votes retain their denominator',async()=>{
  const req=hearing();req.seats['judge-2'].weight=3;
  const arena=createArena({adapters:{catalog,turn(p,prompt){
    const out=response(p,prompt);
    if(p.name==='judge-2'){
      const data=JSON.parse(out.text);data.reviews[0].finding='supported';
      data.reviews[0].citations=[{id:'E1',quote:'Orders collapsed'}];out.text=JSON.stringify(data);
    }
    return out;
  }}});
  const r=await finish(await arena.start(req));assert.equal(r.status,'partial');
  assert.deepEqual(r.verdicts[0].votes,{supported:0,contradicted:0,insufficient:1,abstain:3});
  assert.equal(r.verdicts[0].finding,'unresolved');
});
test('admission requires complete seats and a discoverable model, only one hearing may run',async()=>{
  const arena=createArena({adapters:{catalog,turn:()=>new Promise(()=>{})}});
  const incomplete=hearing();delete incomplete.seats['con-lead'];
  await assert.rejects(arena.start(incomplete),/席位/);
  const invalid=hearing();invalid.seats['pro-lead'].model='missing';
  await assert.rejects(arena.start(invalid),/連線與模型/);
  const r=await arena.start(hearing());await assert.rejects(arena.start(hearing()),/進行中/);
  arena.cancel(r.id);await delay(5);assert.equal(r.status,'cancelled');assert.equal(r.turns.length,2);
  assert.ok(r.turns.every(t=>t.status==='cancelled'));
});
test('persisted hearing is replayable and a process interruption never relaunches agents',async t=>{
  const directory=await mkdtemp(join(tmpdir(),'debate-history-'));t.after(()=>rm(directory,{recursive:true,force:true}));
  const adapters={catalog,turn:response},arena=createArena({adapters,directory});
  const req=hearing(1),r=await finish(await arena.start(req)),file=join(directory,r.id+'.json');
  let saved=JSON.parse(await readFile(file));assert.equal(saved.verdicts.length,8);
  assert.equal(createArena({adapters,directory}).get(r.id).turns.length,13);
  saved.status='running';saved.turns.at(-1).status='running';await writeFile(file,JSON.stringify(saved));
  const recovered=createArena({adapters,directory});assert.equal(recovered.get(r.id).status,'interrupted');
  assert.equal((await recovered.start(req)).turns.at(-1).status,'interrupted');
});

test('runtime contracts route the selected model, sandbox options, credentials, stdin and usage',async t=>{
  const {createArenaAdapters}=await import('../chat/arena-adapters.mjs');
  const dir=await mkdtemp(join(tmpdir(),'debate-cli-fixtures-'));t.after(()=>rm(dir,{recursive:true,force:true}));
  const beforePath=process.env.PATH,oldKey=process.env.GEMINI_API_KEY,oldFetch=globalThis.fetch;
  t.after(()=>{process.env.PATH=beforePath;if(oldKey===undefined)delete process.env.GEMINI_API_KEY;else process.env.GEMINI_API_KEY=oldKey;globalThis.fetch=oldFetch;});
  process.env.PATH=dir+':'+beforePath;process.env.GEMINI_API_KEY='arena-fixture';
  const script=(name)=>`#!${process.execPath}
const fs=require('node:fs'),assert=require('node:assert/strict'),args=process.argv.slice(2);
if(args[0]==='auth'){assert.equal(args[1],'status');console.log(JSON.stringify({loggedIn:true}));process.exit(0);}
assert.equal(args[args.indexOf('--model')+1],'demo');assert.equal(fs.readFileSync(0,'utf8'),'packet');
if('${name}'==='claude'){
  assert.equal(args[args.indexOf('--tools')+1],'');assert.ok(args.includes('--strict-mcp-config'));
  assert.equal(process.env.GEMINI_API_KEY,undefined);console.log(JSON.stringify({result:'reply',usage:{input_tokens:8}}));
}else{
  assert.equal(process.env.GEMINI_API_KEY,'arena-fixture');
  assert.equal(JSON.parse(fs.readFileSync(process.env.GEMINI_CLI_SYSTEM_SETTINGS_PATH)).admin.mcp.enabled,false);
  assert.ok(fs.readFileSync(args[args.indexOf('--admin-policy')+1],'utf8').includes('decision = "deny"'));
  console.log(JSON.stringify({response:'reply',stats:{models:{demo:{tokens:{prompt:8,candidates:4}}}}}));
}`;
  for(const name of ['gemini','claude'])await writeFile(join(dir,name),script(name),{mode:0o700});
  const signal=new AbortController().signal;
  globalThis.fetch=async(url,opts)=>{
    if(url.endsWith('/api/tags'))return {ok:true,json:async()=>({models:[{name:'demo'}]})};
    assert.equal(url,'http://127.0.0.1:11434/api/chat');assert.equal(opts.signal,signal);assert.equal(JSON.parse(opts.body).model,'demo');
    return {ok:true,json:async()=>({message:{content:'reply'},prompt_eval_count:8,eval_count:4})};
  };
  const adapters=createArenaAdapters({listModels:async()=>({models:[{id:'demo'}]}),makeWikiThread(model){
    assert.equal(model,'demo');return {run:async(prompt,opt)=>{assert.equal(opt.signal,signal);assert.equal(prompt,'packet');return {finalResponse:'reply',usage:{input_tokens:8}};}};
  }});
  const runtimes=await adapters.catalog();assert.equal(runtimes.length,4);assert.ok(runtimes.every(a=>a.available));
  for(const runtime of runtimes){
    const result=await adapters.turn({runtime:runtime.id,model:'demo'},'packet',signal);
    assert.equal(result.text,'reply');assert.equal(result.usage.input_tokens,8);
  }
});

test('host bridge accepts start and exposes the complete frozen hearing through its HTTP routes',async t=>{
  const {createService}=await import('../chat/service.mjs');
  const req=hearing(1);
  const server=createService({listModels:async()=>({models:[{id:'test-model'}]}),makeWikiThread:()=>({
    async run(prompt){const profile=prompt.includes('獨立評審。逐一')?{avatar:'judge'}:{avatar:'scout',name:'fixture'};
      return {finalResponse:response(profile,prompt).text,usage:{input_tokens:12}};}
  })});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(()=>server.shutdown());
  const url='http://127.0.0.1:'+server.address().port+'/arena/';
  const started=await fetch(url+'start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(req)});
  assert.equal(started.status,202);
  let r=await started.json();
  for(let i=0;i<40&&r.status==='running';i++){await delay(5);r=await (await fetch(url+'run?id='+req.id)).json();}
  assert.equal(r.status,'completed');assert.equal(r.verdicts.length,8);assert.equal(r.packet.sources[0].text,req.packet.sources[0].text);
  assert.equal((await (await fetch(url+'runs')).json()).runs[0].id,req.id);
});

test('agent-requested reads resolve exact packet nodes; checked citations, winner and observer share the same log',async()=>{
  const req=hearing(2);
  req.packet.context=[{layer:'L1',id:'wiki-order',statement:'Orders increased.',sources:['E1']}];
  let asked=false, captured=null;
  const arena=createArena({chooseFirst:()=>'pro',adapters:{catalog,turn(p,prompt){
    const c=JSON.parse(prompt.split('\n').at(-1));
    if(c.question){captured=c;return {text:'C2 responds to C1.'};}
    if(c.seat==='con-challenger'&&!asked){asked=true;return {text:JSON.stringify({lookup:['K1']})};}
    const out=response(p,prompt);
    if(c.task==='ballot'){
      const body=JSON.parse(out.text);
      body.reviews.forEach((review,i)=>{
        review.finding=i%2===0?'supported':'insufficient';
        review.citations=i%2===0?[citation]:[];
      });out.text=JSON.stringify(body);
    }
    return out;
  }}});
  const r=await finish(await arena.start(req));assert.equal(r.status,'completed');
  assert.equal(r.decision.winner,'pro');assert.equal(r.decision.weights.pro,2);
  assert.ok(r.events.some(e=>e.kind==='read'&&e.seat==='con-challenger'&&e.book==='wiki'&&e.ids.includes('K1')));
  assert.ok(r.events.some(e=>e.kind==='verify'&&e.book==='news'&&e.ids.includes('E1')));
  const before=structuredClone(r);
  assert.equal((await arena.observe({id:req.id,question:'Who replied?',history:[]})).answer,'C2 responds to C1.');
  assert.equal(captured.snapshot.turns.filter(t=>t.claim).length,8);assert.equal(captured.snapshot.events.length,r.events.length);
  assert.deepEqual(r,before);
});

test('a speaker cannot attach a made-up reply target or log imaginary source lookups',async()=>{
  const req=hearing(1),arena=createArena({chooseFirst:()=>'pro',adapters:{catalog,turn(p,prompt){
    const c=JSON.parse(prompt.split('\n').at(-1));
    if(c.seat==='con-scout'&&c.task==='speech')return {text:JSON.stringify({lookup:['K404']})};
    if(c.seat==='con-challenger'&&c.task==='speech'){
      const result=JSON.parse(response(p,prompt).text);result.responds_to='C404';return {text:JSON.stringify(result)};
    }
    return response(p,prompt);
  }}});
  const r=await finish(await arena.start(req));
  assert.equal(r.status,'partial');assert.ok(!r.events.some(e=>e.ids?.includes('K404')));
  assert.match(r.turns.find(t=>t.seat==='con-challenger'&&t.task==='speech').error,/對方命題/);
});

test('observer answers while team members are waiting, without taking a seat or advancing the hearing',async()=>{
  let unblock, notify;
  const started=new Promise(resolve=>notify=resolve),blocked=new Promise(resolve=>unblock=resolve);
  const arena=createArena({adapters:{catalog, async turn(p,prompt){
    const context=JSON.parse(prompt.split('\n').at(-1));
    if(context.question){
      assert.equal(context.snapshot.phase,'prepare');
      assert.ok(context.snapshot.turns.some(t=>t.status==='running'));
      return {text:'兩隊正在準備來源。'};
    }
    if(context.task==='research'){notify();await blocked;}
    return response(p,prompt);
  }}});
  const r=await arena.start(hearing(1));await started;
  const previous=r.turns.length, seq=r.events.length;
  const answer=await arena.observe({id:r.id,question:'現在在做什麼？'});
  assert.equal(answer.seq,seq);assert.equal(r.turns.length,previous);assert.equal(r.phase,'prepare');
  unblock();await finish(r);assert.equal(r.status,'completed');
});
