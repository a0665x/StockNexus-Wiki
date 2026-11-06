// Structural work bounds, not wall-clock thresholds tied to one GPU/CPU.
const assert=require('node:assert/strict'),view=require('../dist/graph-view.js');
const rows=Array.from({length:10000},(_,i)=>({id:String(i),published_at:'2026-01-01'}));
let edgeReads=0;
const edges=rows.slice(1).map((row,i)=>({id:'e'+i,get source(){edgeReads++;return String(i)},target:row.id,weight:.9}));
const before=JSON.stringify(rows);
const roots=['0','100','200','300','400','500','600','700','800','900'];
view.traceMany(edges,roots);assert(edgeReads<=edges.length*2,'A ten-root forest must index its edges once, not ten times');
const cache=view.createTraceCache();
const first=cache(edges,roots,{depth:2});edgeReads=0;
assert.equal(cache(edges,roots,{depth:2}),first,'Unchanged roots reuse the same read-only result');
assert.equal(edgeReads,0,'A cache hit cannot rescan edges');
assert.notEqual(cache(edges,roots,{depth:3}),first,'Settings invalidate results');
assert.notEqual(cache([...edges],roots,{depth:3}),first,'A new edge revision invalidates the index');
const sameRevision=cache(edges,['0']);
for(let i=1;i<=20;i++)cache(edges,[String(i)]);
assert.notEqual(cache(edges,['0']),sameRevision,'Root-result cache is bounded; old roots are evicted');
const capped=view.renderSlice({articles:rows,relations:[]},100,['9999',...rows.map(r=>r.id)]);
assert.equal(capped.articles[0].id,'9999','First priority wins even if duplicated by a category');
let inspected=0;
const dense=Array.from({length:10000},()=>({get source(){inspected++;return '0'},target:'1'}));
const slice=view.renderSlice({articles:rows.slice(0,100),relations:dense},100);
assert.equal(slice.relations.length,300);assert.equal(inspected,300,'Stop scanning edges as soon as the render cap is filled');
for(const budget of [-10,0,100,800,2400,9999,NaN,Infinity,'bad',800.9]){
  const result=view.renderSlice({articles:rows,relations:[]},budget);
  assert(result.articles.length>=100&&result.articles.length<=2400);
}
assert.equal(JSON.stringify(rows),before,'Rendering and tracing never mutate complete news');
console.log('PASS: shared adjacency, bounded/invalidation-aware trace cache, stable priorities and bounded edge allocation');
const vm=require('node:vm'),fs=require('node:fs');let compiled=0;
const context={RegExp:function(pattern,flags){compiled++;return new RegExp(pattern,flags)}};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/graph-view.js','utf8'),context);
const ranked=context.AtlasView.rankRoots(rows.map(row=>({...row,title:'NVIDIA AI robot',summary:'Robotics update',symbols:['NVDA']})),'NVDA robot',10);
assert.equal(ranked.matched_articles,10000);assert.equal(ranked.roots.length,10);
assert.deepEqual(Array.from(ranked.roots,r=>r.id),rows.map(r=>r.id).sort().slice(0,10),'Bounded Top N preserves deterministic ID tie-breaking');
assert(compiled<=4,'Compile keyword regexes per query, not per article/field');
console.log('PASS: keyword search scans full data with bounded query matchers');
