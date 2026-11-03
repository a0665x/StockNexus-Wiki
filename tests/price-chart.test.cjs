const assert=require('node:assert/strict'),c=require('../dist/price-chart.js');
const bars=[['2026-10-30',100],['2026-11-02',110],['2026-11-03',90],['2026-11-04',130]].map(([date,close])=>({date,close}));
let m=c.model(bars,'2026-10-30',3);assert.equal(m.means.length,3);assert.equal(m.means.at(-1).close,110);assert.ok(Math.abs(m.means.at(-1).return-.1)<1e-9);assert.equal(m.complete,true);
m=c.model(bars,'2026-10-31',3);assert.equal(m.base.date,'2026-11-02');assert.equal(m.complete,false);
assert.equal(c.model(bars,'2026-10-30',1,'2026-11-02').base.close,110);
assert.equal(c.colors('tw').up,c.colors('us').down);assert.equal(c.model([], '2026-10-30',3).index,-1);
console.log('PASS: forward cumulative mean, weekends, incomplete window and color convention');

const day=86400000,full={start:Date.parse('2026-01-01'),end:Date.parse('2026-05-01')};
const z=c.zoom(full,full,full.start+60*day,.8);assert.ok(z.end-z.start<full.end-full.start);assert.ok(z.start<=full.start+60*day&&z.end>=full.start+60*day);
const lo=c.zoom(z,full,full.start,.01);assert.equal(lo.start,full.start);assert.equal(lo.days,7);
const reset=c.zoom(z,full,full.end,100);assert.equal(reset.start,full.start);assert.equal(reset.end,full.end);
console.log('PASS: zoom boundaries, minimum window and full-range restoration');
