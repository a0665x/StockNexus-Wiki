import test from 'node:test';
import assert from 'node:assert/strict';
import {researchEvidence,createService} from '../chat/service.mjs';
import {once} from 'node:events';
const clock=Date.parse('2026-11-10T12:00:00Z');
const run={run_id:'r',bundle:{lens:{instrument:'NASDAQ:TSLA',time_spec:{start:'2026-08-01',end:'2026-11-01'}},manifest:{epochs:{corpus:'old',taxonomy:'t'},candidate_count:40,selected_count:3,truncated:true},opinions:[{claim_id:'a',evidence:[{revision_id:'recent',published_at:'2026-11-09',available_at:'2026-11-09'},{revision_id:'old',published_at:'2026-08-01',available_at:'2026-08-01'},{revision_id:'future',published_at:'2026-11-11',available_at:'2026-11-09'},{revision_id:'late',published_at:'2026-11-09',available_at:'2026-11-11'},{revision_id:'unknown',published_at:null,available_at:null}]},{claim_id:'b',evidence:[{revision_id:'recent',published_at:'2026-11-09',available_at:'2026-11-09'}]}]},current_epochs:{corpus:'new',taxonomy:'t',pending:4}};
test('Given mixed source times, when reading research, then recent counts deduplicate and future/unknown dates never masquerade as recent',()=>{
 const r=researchEvidence(run,7,clock);assert.equal(r.temporal.recent_count,1);assert.equal(r.temporal.evidence.filter(x=>x.status==='future_or_not_yet_known').length,2);assert.equal(r.temporal.evidence.find(x=>x.revision_id==='unknown').status,'unknown_time');assert.deepEqual(r.temporal.evidence.find(x=>x.revision_id==='recent').claim_ids,['a','b']);assert.equal(r.temporal.snapshot_stale,true);assert.equal(r.temporal.pending_l1,4);assert.equal(r.coverage.truncated,true);assert.equal(r.forecast.status,'unavailable');assert.equal(r.temporal.latest_publication,'2026-11-09');assert.equal(researchEvidence(run,1,clock).temporal.recent_count,0);
});
test('Given a research read in flight, when stock/run changes, then reject stale response and prevent cross-session reads',async()=>{
 let token;const server=createService({makeThread:t=>{token=t;return {async runStreamed(_, {signal}){return {events:(async function*(){while(!signal.aborted)await new Promise(r=>setTimeout(r,5));})()};}};}});server.listen(0,'127.0.0.1');await once(server,'listening');const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,b={},key)=>{const r=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:'Bearer '+key}:{})},body:JSON.stringify(b)});return {status:r.status,data:await r.json()};};
 try{const key=(await post('/session')).data.token;const context={revision:1,surface:'wiki',instrument:'NASDAQ:TSLA',research_run:'r'};await post('/sync',{context},key);
 const stream=await fetch(base+'/turn',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+key},body:JSON.stringify({message:'L2 recent risk?'})});
 assert.equal((await post('/tool',{name:'read_research'},key)).status,401);
 assert.equal((await post('/tool',{name:'read_research',args:{lookback_days:0}},token)).status,400);
 const request=post('/tool',{name:'read_research',args:{}},token);let cmd;
 for(let i=0;i<40&&!cmd;i++){await new Promise(r=>setTimeout(r,5));cmd=(await post('/sync',{context},key)).data.commands[0];}assert.equal(cmd.kind,'read_research');
 await post('/sync',{context:{revision:2,surface:'wiki',instrument:'NASDAQ:AMD',research_run:'different'},ack:{id:cmd.commandId,result:run}},key);assert.equal((await request).status,409);
 await post('/sync',{context:{revision:3,surface:'wiki',instrument:'NASDAQ:AMD',research_run:null}},key);assert.equal((await post('/tool',{name:'read_research'},token)).status,400);
 await post('/cancel',{},key);await stream.text();
 }finally{server.shutdown();server.closeAllConnections();}
});
