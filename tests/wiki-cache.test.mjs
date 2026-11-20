import test from 'node:test';
import assert from 'node:assert/strict';
import '../dist/wiki-cache.js';

const instrument='NASDAQ:TSLA',key=new URLSearchParams({instrument}).toString();
const full={kind:'full',instrument,token:'a',epoch:'1',graph:{instrument,version:1,
 nodes:[{id:'old'},{id:'keep',title:'v1'}],histories:{old:1,keep:1}}};

test('a delta removes, reorders, inserts and revises rows without mutating the old snapshot',async()=>{
 const replies=[full,{kind:'delta',instrument,base:'a',token:'b',epoch:'2',set:{version:2},
  rows:{nodes:{key:'id',upsert:[{id:'keep',title:'v2'},{id:'new'}],order:['new','keep']}},
  maps:{histories:{set:{keep:2},remove:['old']}}}];
 const cache=AtlasWikiCache.create(async()=>replies.shift());
 const original=await cache.graph(key),updated=await cache.graph(key);
 assert.deepEqual(updated.value,{instrument,version:2,nodes:[{id:'new'},{id:'keep',title:'v2'}],histories:{keep:2}});
 assert.deepEqual(original.value,full.graph);
});

test('an unrecognized base or incomplete order triggers one full fetch without since',async()=>{
 for(const change of [{base:'expired',rows:{}},{base:'a',rows:{nodes:{key:'id',upsert:[],order:['missing']}}}]){
  const replies=[full,{kind:'delta',instrument,token:'b',maps:{},set:{},...change},{...full,token:'current'}],paths=[];
  const cache=AtlasWikiCache.create(async path=>{paths.push(path);return replies.shift();});
  await cache.graph(key);assert.equal((await cache.graph(key)).token,'current');
  assert.match(paths[1],/since=a/);assert.doesNotMatch(paths[2],/since=/);assert.equal(paths.length,3);
 }
});

test('coalesced reads stay scoped to the exact query and a wrong-stock response cannot poison the cache',async()=>{
 let finish,calls=0;const cache=AtlasWikiCache.create(()=>{calls++;return new Promise(resolve=>{finish=resolve;});});
 const first=cache.graph(key),same=cache.graph(key);
 assert.equal(calls,1);finish(full);assert.equal(await first,await same);
 const next=cache.graph(key+'&version=1');finish({...full,instrument:'NASDAQ:AAPL'});
 await assert.rejects(next,/mismatch/);assert.equal(cache.peekGraph(key+'&version=1'),undefined);
 assert.equal(cache.peekGraph(key).value,full.graph);
});

test('a delayed progress read cannot restore pre-stop state after a successful mutation',async()=>{
 const replies=[];const cache=AtlasWikiCache.create(()=>new Promise(resolve=>replies.push(resolve)));
 const before=cache.state(instrument);
 cache.invalidateState(instrument);
 const after=cache.state(instrument);
 replies[1]({instrument,config_token:'new',config:{enabled:false}});
 await after;
 replies[0]({instrument,config_token:'old',config:{enabled:true}});
 await before;
 assert.equal(cache.peekState(instrument).config.enabled,false);
});
