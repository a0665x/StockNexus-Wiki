const assert=require('node:assert/strict');
const glow=require('../dist/glow.js');
const settings=glow.settings();let previous=Infinity;
for(let depth=0;depth<=6;depth++){const light=glow.level(depth,settings);assert(light<previous,'Every deeper hop is dimmer');previous=light;}
assert.equal(glow.level(3,{brightness:1,decay:.5}),.125);
assert.equal(glow.level(0,{enabled:false}),0);
assert.equal(glow.level(0,{brightness:0}),0);
assert.equal(glow.settings({brightness:Infinity}).brightness,1.55);
assert.equal(glow.settings({radius:500}).radius,90);
assert.equal(glow.settings({decay:0}).decay,.2);
assert.equal(glow.tint('#80e6cc',.5),'rgb(64,115,102)');
console.log('PASS: monotonic root-to-depth glow, decay, disable, bounds and source-color dimming');

let light=1;const first=glow.ease(light,0,16);assert(first>0&&first<1,'Root changes fade instead of cutting');
for(let i=0;i<40;i++)light=glow.ease(light,0,16);assert(light<.001);
assert.equal(glow.ease(0,1,16,true),1,'Reduced motion bypasses transition');
