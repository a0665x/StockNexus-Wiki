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
 await post('/sync',{context:{revision:1,surface:'wiki',instrument:'NASDAQ:GOOGL',version:8,scope_ids:['n']},graph:{articles:[{id:'a',title:'Source'}],nodes:[{id:'n',kind:'Thesis',title:'Interpretation',citations:[{article_revision_id:'a'}]},{id:'hidden',kind:'Claim'}],edges:[],histories:{n:{original:{id:'old'}}}}},key);
 const wikiRead=(await post('/tool',{name:'read_wiki',args:{}},toolToken)).data;assert.equal(wikiRead.total,1);assert.equal(wikiRead.instrument,'NASDAQ:GOOGL');assert.equal(wikiRead.nodes[0].kind,'Thesis');assert.equal(wikiRead.histories.n.original.id,'old');
 // The selected L2 claim and exact source chain travel through the real tool route.
 await post('/sync',{context:{revision:2,surface:'wiki',instrument:'NASDAQ:GOOGL',version:8,layer:'both',research_run:'run-one',research_question:'Cloud demand?',scope_ids:['l2','n'],selected_node:{id:'l2',layer:'L2'}},graph:{articles:[{id:'a',title:'Source'}],nodes:[{id:'l2',kind:'CustomerOpinion',layer:'L2',run_id:'run-one',derived_from:['n:claim'],title:'Conditional interpretation'},{id:'n',kind:'Thesis',layer:'L1',citations:[{article_revision_id:'a'}]},{id:'other',kind:'Thesis'}],edges:[{source:'l2',target:'n',relation_type:'DERIVED_FROM'}],histories:{}}},key);
 const l2Read=(await post('/tool',{name:'read_wiki',args:{}},toolToken)).data;assert.equal(l2Read.total,2);assert.equal(l2Read.layer,'both');assert.equal(l2Read.research_run,'run-one');assert.equal(l2Read.research_question,'Cloud demand?');assert.deepEqual(l2Read.nodes[0].derived_from,['n:claim']);
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
