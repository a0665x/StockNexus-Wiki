const assert=require('node:assert/strict');
const memory=new Map();global.localStorage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)};
global.AtlasUI=require('../dist/explorer-ui.js');global.AtlasView=require('../dist/graph-view.js');
const rules=require('../dist/relation-settings.js');
const elements=new Map(),$=id=>{if(!elements.has(id))elements.set(id,{value:'',handlers:{},children:[],checked:false,setAttribute(){},removeAttribute(){},classList:{add(){},remove(){}},replaceChildren(){this.children=[]},append(v){this.children.push(v)},addEventListener(k,f){this.handlers[k]=f},reportValidity:()=>true,showModal(){},close(){}});return elements.get(id)};
global.document={createElement:()=>({})};
const a={id:'a',title:'A',source:{provider:'google'}},b={id:'b',title:'B',source:{provider:'google'}},isolate={id:'alone',title:'Unconnected',source:{provider:'google'}};
const group={articles:[a,b,isolate],relations:[{id:'ab',source:'a',target:'b',type:'shared_entity',weight:.79}]};
let base={source_graphs:{google:group},relation_settings:rules.defaults},writes=0,request,resolve;
global.fetch=(url,options)=>{request={url,options};return new Promise(r=>resolve=r)};
AtlasUI.write('relationSettings',rules.defaults);
const ui=rules.init($,{get:()=>base,put:value=>{base=value;writes++},view:p=>AtlasView.select(p,['google'],false)});
assert.deepEqual(ui.preferred(),rules.defaults,'Reload must retain explicitly saved original settings');
const submit=()=>$('relationForm').handlers.submit({preventDefault(){}});
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 for(const k of ['entity','topic','title'])$('relation-'+k).checked=false;
 submit();assert.equal($('relationSpinner').hidden,false);assert.equal($('relationProgress').hidden,false);assert.equal(request.url,'/api/graph/build');const body=JSON.parse(request.options.body);
 assert.equal(body.source_graphs.google.articles.length,3);
 resolve({ok:true,json:async()=>({relation_settings:body.relation_settings,source_graphs:{google:{relations:[]}},relations:[],cross_relations:[]})});await tick();
 assert.equal(writes,1);assert.strictEqual(base.source_graphs.google.articles,group.articles,'Keep identical news objects, order and isolated node');assert.equal(base.source_graphs.google.relations.length,0);
 assert.equal($('relationStatus').textContent,'');assert($('relationStatus').hidden);assert($('relationSpinner').hidden);assert.equal($('relationProgress').value,1);
 // Failed requests never replace the existing graph or falsely update applied rules.
 $('relation-entity').checked=true;const previous=base;submit();resolve({ok:false,json:async()=>({error:'test failure'})});await tick();assert.strictEqual(base,previous);assert.equal(ui.applied().entity,false);assert.match($('relationStatus').textContent,/未套用/);
 // A response from an older dataset cannot overwrite a newly loaded graph.
 submit();const late=resolve;base={source_graphs:{google:{articles:[isolate],relations:[]}},relation_settings:ui.applied()};ui.onPayload(base);
 late({ok:true,json:async()=>({relation_settings:body.relation_settings,source_graphs:{google:{relations:[]}},relations:[],cross_relations:[]})});await tick();assert.equal(writes,1);
 assert.equal(base.source_graphs.google.articles.length,1);
 assert(rules.explain({...rules.defaults,entity:false,topic:false,title:false})[0].includes('所有新聞節點仍保留'));
 console.log('PASS: definition rebuild, isolated node identity, errors and stale responses');
})().catch(e=>{console.error(e);process.exitCode=1});
