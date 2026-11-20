import test from 'node:test';
import assert from 'node:assert/strict';
import {createService} from '../chat/service.mjs';
import {once} from 'node:events';
test('Given a DB read without loaded graph, return results and reject changed stocks or browser session tokens',async()=>{
 let token;const server=createService({makeThread:t=>{token=t;return {async runStreamed(_, {signal}){return {events:(async function*(){while(!signal.aborted)await new Promise(r=>setTimeout(r,5));})()};}};}});server.listen(0,'127.0.0.1');await once(server,'listening');const base='http://127.0.0.1:'+server.address().port;
 const post=async(path,b={},key)=>{const r=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json',...(key?{Authorization:'Bearer '+key}:{})},body:JSON.stringify(b)});return {status:r.status,data:await r.json()};};
 try{const key=(await post('/session')).data.token;const context={revision:1,surface:'wiki',instrument:'NASDAQ:TSLA',research_run:'r'};await post('/sync',{context},key);
 const stream=await fetch(base+'/turn',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+key},body:JSON.stringify({message:'L2 recent risk?'})});
 assert.equal((await post('/tool',{name:'read_database'},key)).status,401);
 assert.equal((await post('/tool',{name:'read_database',args:{resource:'invalid'}},token)).status,400);
 const request=post('/tool',{name:'read_database',args:{resource:'news',instrument:'NASDAQ:TSLA'}},token);let cmd;
 for(let i=0;i<40&&!cmd;i++){await new Promise(r=>setTimeout(r,5));cmd=(await post('/sync',{context},key)).data.commands[0];}assert.equal(cmd.kind,'read_database');
 await post('/sync',{context,ack:{id:cmd.commandId,result:{instrument:'NASDAQ:TSLA',items:[{id:'a'}]}}},key);
 const success=await request;assert.equal(success.status,200);assert.equal(success.data.items[0].id,'a');
 const late=post('/tool',{name:'read_database',args:{resource:'news',instrument:'NASDAQ:TSLA'}},token);cmd=null;
 for(let i=0;i<40&&!cmd;i++){await new Promise(r=>setTimeout(r,5));cmd=(await post('/sync',{context},key)).data.commands[0];}

 await post('/sync',{context:{revision:2,surface:'wiki',instrument:'NASDAQ:AMD',research_run:'different'},ack:{id:cmd.commandId,result:{instrument:'NASDAQ:TSLA',items:[]}}},key);assert.equal((await late).status,409);
 await post('/sync',{context:{revision:3,surface:'wiki',instrument:'NASDAQ:AMD',research_run:null}},key);assert.equal((await post('/tool',{name:'read_database'},token)).status,400);
 await post('/cancel',{},key);await stream.text();
 }finally{server.shutdown();server.closeAllConnections();}
});
