// Exercise the shipped form and its real event handlers with a pending HTTP response.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const tick=()=>new Promise(resolve=>setTimeout(resolve,10));
async function until(predicate){
 const end=Date.now()+4000;
 while(!predicate()){assert.ok(Date.now()<end,'Timed out waiting for the range preview');await tick();}
}
test('Given a slow date preview, when the slider changes, then only the newest UTC range and counts are shown',async()=>{
 const w=new JSDOM('<button id="modeTimeline"></button><button id="relationOpen"></button>',{url:'http://fixture.local/',runScripts:'outside-only'}).window;
 const $=id=>w.document.getElementById(id);
 const noop=()=>{},stub=new Proxy({},{get:()=>noop});
 Object.assign(w,{AtlasWikiContext:{selection:()=>({articles:[],search:{}})},AtlasWikiCache:{create:()=>stub},
  AtlasI18n:{language:()=>'zh-Hant',termLabel:t=>t.label},AtlasUI:stub,AtlasWikiTimeline:{initWindow:()=>stub,create:()=>stub},AtlasWikiLayout:{init:()=>stub}});
 const requests=[];
 w.fetch=(url,opts)=>new Promise(resolve=>requests.push({url,body:JSON.parse(opts.body),respond:value=>resolve({ok:true,json:async()=>value})}));
 try{
  w.eval(fs.readFileSync('dist/wiki-view.js','utf8'));
  $('wikiPanel').hidden=false;$('wikiInstrument').add(new w.Option('NASDAQ:NVDA','NASDAQ:NVDA'));
  $('wikiInstrument').value='NASDAQ:NVDA';
  $('wikiRange').value='custom';$('wikiRange').dispatchEvent(new w.Event('change'));
  await until(()=>requests.length===1);
  const field=$('wikiStartDate'),bar=$('wikiRangeStart'),box=$('wikiSelectedCoverage');
  bar.value=String(Number(bar.max)-10);bar.dispatchEvent(new w.Event('input',{bubbles:true}));
  const newStart=field.value;
  assert.notEqual(requests[0].body.date_range.start,newStart);
  requests[0].respond({selected:999,reused:999,pending:0});
  await until(()=>requests.length===2);
  assert.doesNotMatch(box.textContent,/999/);
  assert.equal(requests[1].body.date_range.start,newStart);
  requests[1].respond({selected:9,reused:2,pending:7,trees:{total:4,done:1,pending:3}});
  await until(()=>box.textContent.includes('7 篇')||box.textContent.includes('尚未整理 7'));
  assert.ok(box.textContent.includes(newStart));assert.ok(box.textContent.includes('新聞樹 · 4 棵'));
  assert.ok($('wikiL1Pipeline').textContent.includes('待處理 7 篇'));
  const old=bar.value;field.value=$('wikiEndDate').value;field.dispatchEvent(new w.Event('input'));
  assert.notEqual(bar.value,old);await until(()=>requests.length===3);
  assert.equal(requests[2].body.date_range.start,requests[2].body.date_range.end);
  requests[2].respond({selected:0,reused:0,pending:0,documents:{total:1,done:0,pending:1,
   sources:[{collection:'local',source:'interviews',records:3}],passages:[{title:'產能訪談',collection:'local',source:'interviews',
   url:'/documents?collection=local&source=interviews&id=s&revision=2',revision:2,versions:[],opinions:[],outcomes:[],done:false}]}});
  await until(()=>box.textContent.includes('沒有符合範圍'));
  assert.match(box.textContent,/文件原文 · 全部日期/);
  assert.match(box.textContent,/DB 已匯入 3 個節點/);
  assert.match(box.textContent,/待審視 1/);
  const documents=[...box.querySelectorAll('details')].find(d=>d.textContent.includes('各段原文'));
  documents.open=true;await until(()=>documents.querySelector('a'));
  assert.match(documents.querySelector('a').href,/revision=2/);
  assert.ok(requests.every(r=>r.url.endsWith('/range-counts')));
 }finally{w.close();}
});
