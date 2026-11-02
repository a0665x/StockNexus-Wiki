const assert=require('node:assert/strict');
global.localStorage={getItem:()=>null,setItem(){}};
const ui=require('../dist/explorer-ui.js');
const elements=new Map();
const $=id=>{if(!elements.has(id))elements.set(id,{id,style:{},handlers:{},classList:{toggle(){}},setAttribute(){},addEventListener(k,f){this.handlers[k]=f},setPointerCapture(){},hasPointerCapture(){return false}});return elements.get(id)};
$('stage').getBoundingClientRect=()=>({left:0,top:0,right:1000,bottom:700,width:1000,height:700});
for(const [id,body,left,top] of [['sourcePanel','sourcePanelBody',20,20],['timeFocusBar','timeFocusBody',20,450]]){
 $(id).getBoundingClientRect=()=>{const [x,y]=($(id).style.transform||'').match(/-?\d+(?:\.\d+)?/g)||[0,0];return {left:left+Number(x),top:top+Number(y),width:$(body).hidden?36:500,height:$(body).hidden?36:200}};
}
ui.initSourcePanel($);ui.initTimePanel($);
const event=(target,x,y)=>({target,button:0,pointerId:1,clientX:x,clientY:y,preventDefault(){},stopPropagation(){}});
function drag(id,dx,dy,target=$(id)){
 const p=$(id);assert(p.handlers.pointerdown,'Panel whitespace must listen for dragging');
 p.handlers.pointerdown(event(target,0,0));p.handlers.pointermove(event(target,dx,dy));p.handlers.pointerup(event(target,dx,dy));
}
function separate(){const a=$('sourcePanel').getBoundingClientRect(),b=$('timeFocusBar').getBoundingClientRect();assert(a.left+a.width+8<=b.left||b.left+b.width+8<=a.left||a.top+a.height+8<=b.top||b.top+b.height+8<=a.top,'Floating tools must not overlap');}
drag('sourcePanel',100,40);assert.equal($('sourcePanel').getBoundingClientRect().left,120);
const before=$('sourcePanel').style.transform;
drag('sourcePanel',100,50,{closest:()=>({})});assert.equal($('sourcePanel').style.transform,before,'Inputs, buttons and curve must retain their own gestures');
drag('sourcePanel',-100,430);separate();
$('sourcePanelToggle').onclick();$('timePanelToggle').onclick();
drag('sourcePanel',0,430);separate();
$('sourcePanelToggle').onclick();separate();$('timePanelToggle').onclick();separate();
$('sourcePanelReset').onclick();$('timePanelReset').onclick();separate();
console.log('PASS: panel whitespace, control exclusion, expanded/collapsed collisions and reset');
