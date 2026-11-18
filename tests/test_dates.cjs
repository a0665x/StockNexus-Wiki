const assert=require('node:assert/strict');
const {quickRange,init}=require('../dist/date-range.js');
assert.deepEqual(quickRange(3,new Date('2026-10-28T12:00:00Z')),{start:'2026-07-29',end:'2026-10-28',days:92});
assert.deepEqual(quickRange(12,new Date('2024-02-29T01:00:00Z')),{start:'2023-03-01',end:'2024-02-29',days:366});
assert.equal(quickRange(3,new Date('2026-05-31T00:00:00Z')).start,'2026-03-01','Clamp to last valid calendar day before moving to inclusive start');
assert.equal(quickRange(3,new Date('2026-10-28T01:00:00+08:00')).end,'2026-10-27','UTC date, not local date');
for(let year=2020;year<=2030;year++)for(let month=0;month<12;month++)for(const count of [3,6,9,12]){
 const result=quickRange(count,new Date(Date.UTC(year,month+1,0)));assert(result.days>0&&result.days<=366);
}
assert.throws(()=>quickRange(24));
const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,{value:'',classList:{toggle(){}},setAttribute(k,v){this[k]=v},addEventListener(k,f){this[k]=f}});return elements.get(id)};
$('start').value='2026-01-01';$('end').value='2026-01-07';let now=new Date('2026-10-28T00:00:00Z');const ui=init($,()=>now);
$('dateQuick').onclick();$('months-12').onclick();assert.equal($('end').value,'2026-10-28');assert($('start').readOnly);
now=new Date('2026-10-29T00:00:00Z');$('dateQuick').onclick();assert.equal($('end').value,'2026-10-29','Quick search refreshes across midnight');
$('dateCustom').onclick();assert.equal($('start').value,'2026-01-01','Custom draft survives mode switches');assert.equal($('end').value,'2026-01-07');assert(!$('start').readOnly);
$('dateQuick').onclick();$('start').value='2025-09-01';$('end').value='2025-09-30';ui.setCustom();ui.refresh();assert.equal(ui.mode(),'custom');assert.equal($('end').value,'2025-09-30','Snapshot dates remain fixed');
console.log('PASS: calendar months, leap years, 366-day bound, UTC, mode switching, midnight refresh and snapshot dates');

$('start').value='2024-02-29';$('end').value='2025-02-28';ui.setCustom();
assert.equal($('start').min,'2024-02-29');assert.equal($('end').max,'2025-02-28');
$('end').value='2026-10-29';ui.refresh();assert.equal($('start').min,'2025-10-30');
