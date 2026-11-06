// Exercise real app initialization + rebuild after a failed 3D constructor.
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element {
  constructor(){this.value='';this.children=[];this.handlers={};this.style={};this.classList={add(){},remove(){},toggle(){}};}
  set textContent(v){this.children=[];this.text=String(v)} get textContent(){return (this.text||'')+this.children.map(c=>c.textContent||'').join('')}
  setCustomValidity(){} reportValidity(){}
  setAttribute(k,v){this[k]=v} append(...e){this.children.push(...e)} replaceChildren(...e){this.text='';this.children=e}
  addEventListener(k,fn){this.handlers[k]=fn} getBoundingClientRect(){return {width:900,height:600,left:0,top:0}} click(){}
}
const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
const logs=[];
const context={ResizeObserver:class{observe(){}},document:{documentElement:{},getElementById:get,createElement:()=>new Element(),createElementNS:()=>new Element(),querySelectorAll:()=>[],body:new Element()},ForceGraph3D(){throw Error('Error creating WebGL context.');},console:{...console,error:(...args)=>logs.push(args.join(' '))},Date,URL,Blob,TextDecoder,TextEncoder,Uint8Array,AbortController,setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,clearInterval(){},fetch:async()=>({ok:true,json:async()=>({db:{articles:1},channels:[],snapshots:[]})})};
context.addEventListener=()=>{};context.document.addEventListener=()=>{};context.AtlasWorkspace={ready:new Promise(()=>{}),save(){}};
vm.createContext(context);
for(const file of ['i18n','explorer-ui','graph-view','timeline','glow','date-range','interaction','time-lens','app'])vm.runInContext(fs.readFileSync('dist/'+file+'.js','utf8'),context);
vm.runInContext(`rebuild({articles:[{id:'one',title:'Test article',source:{provider:'google'},published_at:'2026-10-28',summary:'',symbols:[]}],relations:[]})`,context);
assert.equal(get('count').textContent,'1');
assert.equal(vm.runInContext('viewMode',context),'timeline','Failed WebGL must select the usable timeline');
assert.equal(get('empty').hidden,true);
assert.equal(get('graphFallback').hidden,false);
assert.equal(get('modeNetwork').disabled,false,'Graph retry must remain available after WebGL failure');
assert.match(get('graphFailureReason').textContent,/Error creating WebGL context/,'Original failure must survive successful news loading');
assert.equal(get('empty').hidden,true,'Do not show an empty-news message for valid articles');
assert(logs.some(s=>s.includes('[GraphNews 3D]')&&s.includes('Error creating WebGL context')));
vm.runInContext("switchMode('timeline')",context);assert.equal(get('empty').hidden,true,'Timeline remains usable');
vm.runInContext("switchMode('network');AtlasI18n.setLanguage('en');rebuild()",context);
assert.equal(vm.runInContext('viewMode',context),'timeline');assert.match(get('graphFallbackSummary').textContent,/3D unavailable/);assert.match(get('graphFailureReason').textContent,/Error creating WebGL context/);
console.log('PASS: WebGL initialization failure remains visible after news load and mode/language changes');
