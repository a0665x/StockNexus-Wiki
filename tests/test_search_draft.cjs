const assert=require('node:assert/strict');
const memory=new Map();global.localStorage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)};
const ui=require('../dist/explorer-ui.js'),dates=require('../dist/date-range.js');
function session(now='2026-10-28T00:00:00Z'){
 const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,{value:'',checked:false,textContent:'',listeners:{},classList:{toggle(){}},setAttribute(){},addEventListener(event,fn){(this.listeners[event]??=[]).push(fn)},emit(event){for(const fn of this.listeners[event]||[])fn()}});return elements.get(id)};
 $('start').value='2026-10-22';$('end').value='2026-10-28';$('source-google').checked=true;
 const range=dates.init($,()=>new Date(now));ui.initSearch($,range);return {$,range};
}
let {$,range}=session();$('query').value='NVDA semiconductor';$('query').emit('input');$('ticker').value='NVDA';$('ticker').emit('input');
for(const p of ['yahoo','massive']){$('source-'+p).checked=true;$('source-'+p).emit('change')}
$('forceRefresh').checked=true;$('forceRefresh').emit('change');$('start').value='2026-01-03';$('start').emit('input');
let reloaded=session();assert.equal(reloaded.$('query').value,'NVDA semiconductor');assert.equal(reloaded.$('ticker').value,'NVDA');assert.equal(reloaded.$('start').value,'2026-01-03');assert(reloaded.$('source-yahoo').checked&&reloaded.$('source-massive').checked&&!reloaded.$('forceRefresh').checked);
$('dateQuick').onclick();$('months-12').onclick();reloaded=session('2026-10-29T00:00:00Z');assert.equal(reloaded.range.mode(),'quick');assert.equal(reloaded.$('end').value,'2026-10-29','Quick dates advance with today');reloaded.$('dateCustom').onclick();assert.equal(reloaded.$('start').value,'2026-01-03','Custom draft survives quick mode and reload');
reloaded.$('query').value='';reloaded.$('query').emit('input');assert.equal(session().$('query').value,'','Intentionally clearing is persisted');
const draft=JSON.parse(memory.get('graphnews.searchDraft'));assert.deepEqual(Object.keys(draft).sort(),['dates','query','rss_region','sources','ticker']);assert(!JSON.stringify(draft).includes('massiveKey'));
for(const p of ['google','yahoo','massive']){reloaded.$('source-'+p).checked=false;reloaded.$('source-'+p).emit('change')}assert.equal(session().$('source-google').checked,false,'Do not restore default source when all unchecked');
memory.set('graphnews.searchDraft','invalid JSON');assert.doesNotThrow(()=>session());
global.localStorage.setItem=()=>{throw Error('blocked')};assert(session().$('searchDraftStatus').textContent.includes('不可用'));
console.log('PASS: refresh persistence, unfinished inputs, all source choices, dates/custom/quick modes, deliberate clearing, credential isolation and unavailable storage feedback');
