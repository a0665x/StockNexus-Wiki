const assert=require('node:assert/strict'),view=require('../dist/graph-view.js');
const articles=Array.from({length:7106},(_,i)=>({id:String(i),published_at:`2026-01-${String(i%28+1).padStart(2,'0')}`}));
const relations=articles.slice(1).map((a,i)=>({source:String(i),target:a.id}));
const payload={articles,relations};
let slice=view.renderSlice(payload);
assert.equal(slice.articles.length,800);
assert.equal(payload.articles.length,7106);
assert(slice.relations.length<=2400);
const ids=new Set(slice.articles.map(a=>a.id));
assert(slice.relations.every(e=>ids.has(e.source)&&ids.has(e.target)));
assert.equal(view.renderSlice(payload,400,['0']).articles[0].id,'0');
assert.equal(view.renderSlice(payload,100).articles.length,100);
assert.equal(view.renderSlice(payload).articles.map(a=>a.id).join(),slice.articles.map(a=>a.id).join());
console.log('PASS: full data retained, bounded deterministic GPU slice, selected roots prioritized, no dangling edges');

for(const budget of [1200,1600,2000,2400]){const result=view.renderSlice(payload,budget,['0']);assert.equal(result.articles.length,budget);assert.equal(result.articles[0].id,'0');const ids=new Set(result.articles.map(a=>a.id));assert(result.relations.every(e=>ids.has(e.source)&&ids.has(e.target)));assert(result.relations.length<=budget*3);}
assert.equal(view.renderSlice(payload,9999).articles.length,2400);
assert.equal(view.renderSlice(payload).articles.length,800);
