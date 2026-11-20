import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Readable} from 'node:stream';
import {EventEmitter} from 'node:events';
import {mkdtempSync,rmSync,statSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {createService} from '../chat/service.mjs';
function request(service,url,body={},token=''){
 const req=Readable.from([Buffer.from(JSON.stringify(body))]);Object.assign(req,{url,method:'POST',headers:{authorization:'Bearer '+token}});
 return new Promise(resolve=>{let status,text='';const res=Object.assign(new EventEmitter(),{writeHead(code){status=code;this.headersSent=true;},write(s){text+=s;},end(s=''){this.writableEnded=true;resolve({status,text:text+s,data:()=>JSON.parse(text+s)});}});service.emit('request',req,res);});
}
test('history survives service restart, resumes the SDK thread and isolates browser owners',async()=>{
 const folder=mkdtempSync(join(tmpdir(),'chat-history-')),historyPath=join(folder,'history.json'),starts=[];
 const make=()=>createService({historyPath,makeThread:(token,model,previous)=>{starts.push(previous);return {id:previous||'sdk-thread',runStreamed:async()=>({events:[{type:'item.completed',item:{type:'agent_message',text:'Cited answer'}},{type:'turn.completed'}]})};}});
 let service=make();try{
  const first=(await request(service,'/session',{surface:'wiki'})).data(),key=first.token;
  await request(service,'/sync',{context:{revision:1,instrument:'NASDAQ:NVDA'}},key);
  assert.equal((await request(service,'/turn',{message:'Explain this evidence'},key)).status,200);
  const list=(await request(service,'/history',{},key)).data().conversations;assert.equal(list.length,1);assert.equal(list[0].title,'Explain this evidence');assert.equal(list[0].message_count,2);assert.equal(list[0].threadId,undefined);
  service.shutdown();service=make();
  const second=(await request(service,'/session',{surface:'wiki',owner:first.owner})).data();
  const restored=(await request(service,'/conversation',{action:'open',id:list[0].id},second.token)).data().conversation;
  assert.deepEqual(restored.messages.map(m=>m.text),['Explain this evidence','Cited answer']);assert.equal(restored.threadId,undefined);
  await request(service,'/sync',{context:{revision:2,instrument:'NASDAQ:NVDA'}},second.token);
  await request(service,'/turn',{message:'What contradicts it?'},second.token);assert.deepEqual(starts,[undefined,'sdk-thread']);
  const other=(await request(service,'/session',{surface:'wiki'})).data();assert.equal((await request(service,'/conversation',{action:'open',id:list[0].id},other.token)).status,404);
  const news=(await request(service,'/session',{owner:first.owner,surface:'news'})).data();assert.equal((await request(service,'/conversation',{action:'open',id:list[0].id},news.token)).status,409);
  assert.equal((await request(service,'/session',{owner:'../../secret'})).status,401);
  assert.equal(statSync(historyPath).mode&0o777,0o600);
  await request(service,'/reset',{},second.token);assert.equal((await request(service,'/history',{},second.token)).data().conversations.length,1);
  await request(service,'/conversation',{action:'delete',id:list[0].id},second.token);assert.equal((await request(service,'/history',{},second.token)).data().conversations.length,0);
  service.shutdown();service=make();const third=(await request(service,'/session',{owner:first.owner,surface:'wiki'})).data();assert.equal((await request(service,'/conversation',{action:'open',id:list[0].id},third.token)).status,404);
 }finally{service.shutdown();rmSync(folder,{recursive:true,force:true});}
});

test('another tab cannot resume, delete or submit to a conversation during a turn',async()=>{
 let finish,hold=false;const service=createService({makeThread:()=>({id:'thread',runStreamed:async()=>({events:(async function*(){yield {type:'item.completed',item:{type:'agent_message',text:'Answer'}};if(hold)await new Promise(r=>finish=r);yield {type:'turn.completed'};})()})})});
 try{
  const a=(await request(service,'/session',{})).data();await request(service,'/sync',{context:{revision:1}},a.token);await request(service,'/turn',{message:'First'},a.token);
  const id=(await request(service,'/history',{},a.token)).data().conversations[0].id;
  const b=(await request(service,'/session',{owner:a.owner})).data();await request(service,'/conversation',{action:'open',id},b.token);await request(service,'/sync',{context:{revision:1}},b.token);
  hold=true;const turn=request(service,'/turn',{message:'Continue'},a.token);while(!finish)await new Promise(r=>setTimeout(r,1));
  assert.equal((await request(service,'/turn',{message:'Race'},b.token)).status,409);
  for(const action of ['open','delete'])assert.equal((await request(service,'/conversation',{action,id},b.token)).status,409);
  finish();await turn;
 }finally{finish?.();service.shutdown();}
});
