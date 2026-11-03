const assert=require('node:assert/strict');const memory=new Map();global.localStorage={getItem:k=>memory.get(k)||null,setItem:(k,v)=>memory.set(k,v)};
const ui=require('../dist/explorer-ui.js');
function build(){const e=new Map();const $=id=>{if(!e.has(id))e.set(id,{style:{},handlers:{},classList:{toggle(){}},setAttribute(k,v){this[k]=v},addEventListener(k,fn){this.handlers[k]=fn},setPointerCapture(){},hasPointerCapture(){return false}});return e.get(id)};
 $('stage').getBoundingClientRect=()=>({left:0,top:0,right:1000,bottom:700,width:1000,height:700});
 $('sourcePanel').getBoundingClientRect=()=>{const numbers=($('sourcePanel').style.transform||'').match(/-?\d+(?:\.\d+)?/g)||[0,0],left=100+Number(numbers[0]),top=50+Number(numbers[1]);return {left,top,width:500,height:$('sourcePanelBody').hidden?40:300}};
 ui.initSourcePanel($);return $;}
let $=build();$('rootQuery').value='IPO';$('sourcePanelToggle').onclick();assert($('sourcePanelBody').hidden);assert.equal($('sourcePanelToggle')['aria-expanded'],'false');assert.equal($('rootQuery').value,'IPO');
$('sourcePanelDrag').handlers.pointerdown({button:0,pointerId:1,clientX:0,clientY:0,preventDefault(){},stopPropagation(){}});$('sourcePanelDrag').handlers.pointermove({pointerId:1,clientX:2000,clientY:2000});$('sourcePanelDrag').handlers.pointerup({pointerId:1});let rect=$('sourcePanel').getBoundingClientRect();assert(rect.left+rect.width<=1000);assert(rect.top+rect.height<=700);
$=build();assert($('sourcePanelBody').hidden,'Collapse survives reload');assert.equal($('sourcePanel').getBoundingClientRect().left,500,'Position restored');$('sourcePanelToggle').onclick();rect=$('sourcePanel').getBoundingClientRect();assert(rect.top+rect.height<=700,'Expanded panel stays reachable');
$('sourcePanelReset').onclick();assert.equal($('sourcePanel').getBoundingClientRect().left,100);assert.equal($('sourcePanel').getBoundingClientRect().top,114,'Reset respects the reserved navigation area');
console.log('PASS: collapse/expand, unchanged query, pointer drag, bounds, remembered position and reset');
