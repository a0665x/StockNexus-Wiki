import test from 'node:test';
import assert from 'node:assert/strict';
import {createService} from '../chat/service.mjs';
import {once} from 'node:events';

test('session isolation, current selection, browser acknowledgement, cancellation and continued thread',async()=>{
 let toolToken,starts=0,turns=0;
 const server=createService({makeThread:t=>{toolToken=t;starts++;return {async runStreamed(_, {signal}){turns++;return {events:(async function*(){while(!signal.aborted)await new Promise(r=>setTimeout(r,10));})()};}};}});
 server.listen(0,'127.0.0.1');await once(server,'listening');const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,b={},key)=>{const r=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:'Bearer '+key}:{})},body:JSON.stringify(b)});return {status:r.status,data:await r.json()};};
 try{
 const key=(await post('/session')).data.token,other=(await post('/session')).data.token;
 assert.equal((await post('/sync',{},'wrong')).status,401);
 await post('/sync',{context:{revision:1,scope_ids:['a']},graph:{articles:[{id:'a',title:'Selected'},{id:'b',title:'Hidden'}],edges:[]}},key);
 assert.equal((await post('/tool',{name:'get_state'},key)).status,401);
 const start=()=>fetch(base+'/turn',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+key},body:JSON.stringify({message:'test'})});
 let stream=await start();assert.equal(stream.status,200);
 assert.equal((await post('/turn',{message:'second'},key)).status,409);
 assert.equal((await post('/tool',{name:'read_news',args:{}},toolToken)).data.total,1);
 const action=post('/tool',{name:'act',args:{kind:'click',id:'modeTimeline',revision:1}},toolToken);
 await new Promise(r=>setTimeout(r,30));
 assert.equal((await post('/sync',{context:{revision:1}},other)).data.commands.length,0);
 const cmd=(await post('/sync',{context:{revision:1}},key)).data.commands[0];assert.equal(cmd.commandId.length,36);
 await post('/sync',{context:{revision:2,view_mode:'timeline'},ack:{id:cmd.commandId}},key);
 assert.equal((await action).data.state.view_mode,'timeline');
 await post('/cancel',{},key);assert.match(await stream.text(),/"cancelled":true/);
 assert.equal((await post('/tool',{name:'read_news'},toolToken)).status,409);
 stream=await start();await post('/cancel',{},key);await stream.text();assert.equal(starts,1);assert.equal(turns,2);
 await post('/reset',{},key);stream=await start();await post('/cancel',{},key);await stream.text();assert.equal(starts,2);
 }finally{server.shutdown();server.closeAllConnections();}
});
