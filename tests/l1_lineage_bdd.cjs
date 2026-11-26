const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');

test('Given a child outside the canvas slice, a reader can follow it and return to its parent at the same version',async () => {
 const w=new JSDOM('<button id="modeTimeline"></button><button id="relationOpen"></button>',{url:'http://fixture.local/',runScripts:'outside-only'}).window;
 const instrument='NASDAQ:NVDA',version=5;
 const parent={id:'parent',kind:'Thesis',title:'冷卻供應',assessment:{category:'uncertain',evidence:'supported'}};
 const child={...parent,id:'child',title:'供應商認證',lineage:{action:'extend',compared_id:'parent'},opinion_metadata:{change_reason:'認證開啟另一個供應問題。'}};
 const graph={instrument,version,versions:[{version}],nodes:[parent],edges:[],total_nodes:2,truncated:true,changes:[]};
 const stub=new Proxy({},{get:()=>()=>{}});
 let lang='zh-Hant';
 Object.assign(w,{AtlasWikiContext:{visible:()=>{},selection:()=>({articles:[],search:{instrument}})},
  AtlasI18n:{language:()=>lang,termLabel:t=>t.label},AtlasUI:stub,
  AtlasWikiTimeline:{initWindow:()=>stub,create:()=>stub},AtlasWikiLayout:{init:()=>stub}});
 const inspected=[];
 w.fetch=async url=>{
  const path=new URL(url,w.location.href);
  const route=path.pathname.split('/').pop();
  let data;
  if(route==='node'){
   assert.equal(path.searchParams.get('instrument'),instrument);
   assert.equal(path.searchParams.get('version'),String(version));
   const id=path.searchParams.get('id');inspected.push(id);
   const node=id==='parent'?parent:child, other=id==='parent'?child:parent;
   data={...node,lineage_links:[{id:other.id,title:other.title,titles:{},relation:'EXTENDS',parent:id==='child'}]};
  }else{
   data={models:{models:[{id:'fixture',name:'Fixture'}]},status:{instruments:[{instrument,version}],bridge_ready:true},
    jobs:{instrument,version,jobs:[],config:{}},graph,'range-counts':{selected:2,reused:2,pending:0}}[route];
   assert.ok(data,'unexpected endpoint '+route);
  }
  return {ok:true,json:async()=>data};
 };
 try{
  for(const file of ['wiki-cache','wiki-view'])w.eval(fs.readFileSync('dist/'+file+'.js','utf8'));
  await w.AtlasWiki.show();
  await w.AtlasWiki.selectNode(parent.id);
  const detail=w.document.getElementById('wikiDetail');
  const button=prefix=>Array.from(detail.querySelectorAll('button')).find(b=>b.textContent.startsWith(prefix));
  assert.match(detail.textContent,/營運影響待釐清/);
  assert.match(detail.textContent,/引文支持此說法/);
  await button('衍生子觀點').onclick();
  assert.match(detail.textContent,/認證開啟另一個供應問題/);
  lang='en';w.dispatchEvent(new w.Event('atlas-language'));
  assert.ok(button('Parent viewpoint'));
  await button('Parent viewpoint').onclick();
  assert.ok(button('Child viewpoint'));
  assert.deepEqual(inspected,['parent','child','parent']);
 }finally{w.close();}
});
