// Geometry and preference fixture. Native hit testing, touch and dock placement run in Chromium.
const ui=require('../dist/explorer-ui.js');
function build(memory=new Map()){
  global.localStorage={getItem:k=>memory.get(k)??null,setItem:(k,v)=>memory.set(k,v)};
  Object.assign(global,{innerWidth:1200,innerHeight:900,addEventListener(){},removeEventListener(){},
    ResizeObserver:class {observe(){}},AtlasI18n:{t:s=>s},
    AtlasFloatingResize:{attach:({panel})=>({constrain(){},state:()=>({width:panel.w,height:panel.h})})}});
  function element(id){
    const classes=new Set(),attributes=new Map(),listeners=new Map();
    return {id,style:{},classList:{add:v=>classes.add(v),contains:v=>classes.has(v),
      toggle(v,enabled){if(enabled)classes.add(v);else classes.delete(v);}},
      getAttribute:k=>attributes.get(k),setAttribute:(k,v)=>attributes.set(k,v),
      addEventListener(k,f){listeners.set(k,f);},removeEventListener(k){listeners.delete(k);},
      emit(k,e){listeners.get(k)?.({...e,type:k,preventDefault(){}});},
      focus(){},append(){},replaceChildren(){},querySelector(){return element();},
      setPointerCapture(){},hasPointerCapture(){return false;},closest(){return null;}};
  }
  const doc=element(),nodes=new Map(),$=id=>{
    if(!nodes.has(id))nodes.set(id,Object.assign(element(id),{ownerDocument:doc}));
    return nodes.get(id);
  };
  const rect=(left,top,width,height)=>({left,top,width,height,right:left+width,bottom:top+height});
  global.document=doc;doc.createElementNS=()=>element();doc.documentElement=element();
  doc.querySelector=()=>$('header');
  $('header').getBoundingClientRect=()=>rect(0,0,1200,68);
  $('stage').getBoundingClientRect=()=>rect(240,68,640,832);
  $('graphTools').getBoundingClientRect=()=>rect(256,84,608,128);
  $('newsFloatingTools').getClientRects=()=>[rect(0,0,1200,900)];
  for(const [id,w,h] of [['sourcePanel',430,320],['timeFocusBar',480,380]]){
    const p=$(id);p.w=w;p.h=h;
    p.getBoundingClientRect=()=>{const folded=p.classList.contains('collapsed');
      return rect(parseFloat(p.style.left)||0,parseFloat(p.style.top)||0,folded?40:w,folded?40:h);};
  }
  function drag(id,dx,dy,target=$(id)){
    const p=$(id),r=p.getBoundingClientRect(),x=r.left+20,y=r.top+20;
    const event={target,pointerId:1,button:0,clientX:x,clientY:y};
    p.emit('pointerdown',event);
    doc.emit('pointermove',{...event,clientX:x+dx,clientY:y+dy});
    doc.emit('pointerup',{...event,clientX:x+dx,clientY:y+dy});
  }
  return {ui,$,drag};
}
module.exports={build};
