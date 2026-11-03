const assert=require('node:assert/strict'),p=require('../dist/price-lens.js');
assert.equal(p.priceScale(.05,.05),4);assert.equal(p.priceScale(-.05,.05),.25);assert.equal(p.priceScale(null,.05),null);
assert.equal(p.priceScale(1,.05),4);assert.equal(p.priceScale(-1,.05),.25);assert.equal(p.priceScale(0,0),1);
assert.ok(Math.abs(p.blend(3,.05,.7,.05)-3.7)<1e-12);assert.equal(p.blend(3,null,.7,.05),3);
const part=p.parts(3,.05,.7,.05);assert.ok(Math.abs(part.priceShare-2.8/3.7)<1e-12);assert.equal(part.normalized,1);assert.equal(p.parts(3,null,1,.05).priceShare,0);
const data={bars:Array.from({length:22},(_,i)=>({close:100*1.01**i}))};assert.ok(Math.abs(p.reference(data,1)-.01)<1e-12);assert.ok(p.reference(data,3)>p.reference(data,1));
const outlier={bars:[100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,10000].map(close=>({close}))};assert.ok(p.reference(outlier,1)<.02);
assert.deepEqual(p.settings(),{mix:0,horizon:3});assert.equal(p.settings({horizon:2}).horizon,3);
console.log('PASS: signed P95 normalization, outlier cap, horizon scale, contribution shares, missing evidence');
