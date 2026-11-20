import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Readable} from 'node:stream';
import {EventEmitter} from 'node:events';
import {createService} from '../chat/service.mjs';

// Exercise the bridge request handlers without a listening socket or model credentials.
function request(service, url, body, token) {
  const req=Readable.from(body?[Buffer.from(JSON.stringify(body))]:[]);
  Object.assign(req,{url,method:body?'POST':'GET',headers:{authorization:'Bearer '+token}});
  return new Promise(resolve=>{
    let status,content='';
    const res=Object.assign(new EventEmitter(),{
      writeHead(code){status=code;this.headersSent=true;},
      write(chunk){content+=chunk;},
      end(chunk=''){resolve({status,body:content+chunk});}
    });
    service.emit('request',req,res);
  });
}

test('chat can switch to a full catalog model and resume its conversation independently of Wiki',async()=>{
  const starts=[];
  const service=createService({
    listModels:async()=>({models:[{id:'future-sol'},{id:'future-astra'}]}),
    makeThread:(token,model,previous)=>{
      starts.push({model,previous});
      return {id:'conversation',async runStreamed(){return {events:[{type:'turn.completed'}]};}};
    }
  });
  try {
    const getModels=async path=>JSON.parse((await request(service,path)).body).models.map(m=>m.id);
    assert.deepEqual(await getModels('/models'),['future-sol','future-astra']);
    assert.deepEqual(await getModels('/wiki/models'),['future-sol']);
    const key=JSON.parse((await request(service,'/session',{})).body).token;
    await request(service,'/sync',{context:{revision:1}},key);
    for(const model of ['future-sol','future-astra','future-astra']){
      const result=await request(service,'/turn',{model,message:'test'},key);
      assert.equal(result.status,200);assert.match(result.body,/"type":"done"/);
    }
    assert.deepEqual(starts,[{model:'future-sol',previous:undefined},{model:'future-astra',previous:'conversation'}]);
    assert.equal((await request(service,'/turn',{model:'unknown',message:'test'},key)).status,400);
  } finally {service.shutdown();}
});
