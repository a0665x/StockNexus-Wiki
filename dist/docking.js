/* Binary pane layout: an edge dwell arms a split; release commits it. */
(function(root){
 const ids=['timeFocusBar','sourcePanel'],EDGE=12,DWELL=650,homes=new Map();
 let area,detail,previewBox,candidate=null,timer=null,armed=false,ready=false,serial=0;
 const docked=p=>p?.classList.contains('docked-tool');
 const clamp=x=>Math.max(.2,Math.min(.8,x));
 function shape(n){if(n.classList.contains('pane-leaf'))return {id:n.dataset.pane};return {axis:n.dataset.axis,ratio:Number(n.dataset.ratio)||.5,a:shape(n.children[0]),b:shape(n.children[2])};}
 function save(){if(ready)root.AtlasUI.write('toolDock',{version:2,tree:shape(area.firstElementChild)});}
 function normalize(n=area?.firstElementChild){if(!n)return;if(n.parentElement===area)n.style.flex='1 1 0';if(n.classList.contains('pane-split')){const ratio=Number(n.dataset.ratio)||.5;n.children[0].style.flex=`${ratio} 1 0`;n.children[2].style.flex=`${1-ratio} 1 0`;normalize(n.children[0]);normalize(n.children[2]);for(const slot of [n.children[0],n.children[2]])if(n.dataset.axis==='column'&&slot.classList.contains('pane-leaf')&&slot.querySelector('.docked-tool.collapsed')){slot.style.flex='0 0 88px';(n.children[0]===slot?n.children[2]:n.children[0]).style.flex='1 1 0';}}}
 function changed(){normalize();root.dispatchEvent(new Event('resize'));root.dispatchEvent(new Event('atlas-dock'));}
 function clear(){clearTimeout(timer);timer=null;candidate=null;armed=false;if(previewBox)previewBox.hidden=true;}
 function leaf(id,content){const n=document.createElement('section');n.className='pane-leaf';n.dataset.pane=id;n.append(content);return n;}
 function setRatio(node,value,notify=true){node.dataset.ratio=clamp(value);node.children[0].style.flex=`${clamp(value)} 1 0`;node.children[2].style.flex=`${1-clamp(value)} 1 0`;node.children[1].setAttribute('aria-valuenow',Math.round(clamp(value)*100));if(notify)changed();}
 function branch(a,b,axis,ratio=.5){
  const n=document.createElement('div'),handle=document.createElement('div');n.className='pane-split';n.dataset.axis=axis;handle.className='pane-divider';handle.id='paneDivider'+(++serial);handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-label',root.AtlasI18n.t('調整視窗大小'));handle.setAttribute('aria-orientation',axis==='row'?'vertical':'horizontal');handle.setAttribute('aria-valuemin','20');handle.setAttribute('aria-valuemax','80');n.append(a,handle,b);setRatio(n,ratio,false);
  let drag=null;
  handle.addEventListener('pointerdown',e=>{if(e.button!==0)return;drag={id:e.pointerId,start:axis==='row'?e.clientX:e.clientY,ratio:Number(n.dataset.ratio)};handle.setPointerCapture(e.pointerId);e.preventDefault();});
  handle.addEventListener('pointermove',e=>{if(!drag||drag.id!==e.pointerId)return;const r=n.getBoundingClientRect();setRatio(n,drag.ratio+((axis==='row'?e.clientX:e.clientY)-drag.start)/Math.max(1,axis==='row'?r.width:r.height));});
  const end=e=>{if(!drag||drag.id!==e.pointerId)return;drag=null;if(handle.hasPointerCapture(e.pointerId))handle.releasePointerCapture(e.pointerId);save();};
  for(const kind of ['pointerup','pointercancel','lostpointercapture'])handle.addEventListener(kind,end);
  handle.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(e.key))return;e.preventDefault();setRatio(n,e.key==='Home'?.5:Number(n.dataset.ratio)+(['ArrowLeft','ArrowUp'].includes(e.key)?-.05:.05));save();});return n;
 }
 function insert(panel,target,edge){
  if(!target?.isConnected||!ready)return;
  panel.classList.add('docked-tool');panel.style.transform='none';panel.style.flex='';if(panel.id==='timeFocusBar')document.getElementById('priceSettings').open=false;
  const slot=leaf(panel.id,panel),marker=document.createComment('split');target.before(marker);
  const before=edge==='top'||edge==='left',node=branch(before?slot:target,before?target:slot,['left','right'].includes(edge)?'row':'column');marker.replaceWith(node);detail.classList.add('open');save();changed();
 }
 function undock(panel){if(!docked(panel))return;clear();const slot=panel.closest('.pane-leaf'),parent=slot.parentElement;panel.classList.remove('docked-tool');panel.style.transform='';panel.style.flex='';const home=homes.get(panel.id);home.marker.after(panel);if(parent.classList.contains('pane-split')){const sibling=parent.children[0]===slot?parent.children[2]:parent.children[0];parent.replaceWith(sibling);}else slot.remove();save();changed();}
 function hit(e){
  if(!ready)return null;
  const hits=[];for(const pane of area.querySelectorAll('.pane-leaf')){const r=pane.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)continue;
   for(const [edge,distance] of [['left',e.clientX-r.left],['right',r.right-e.clientX],['top',e.clientY-r.top],['bottom',r.bottom-e.clientY]])if(distance<=EDGE)hits.push({pane,edge,distance});}
  return hits.sort((a,b)=>a.distance-b.distance)[0]||null;
 }
 function show(c){const r=c.pane.getBoundingClientRect(),horizontal=['left','right'].includes(c.edge);Object.assign(previewBox.style,{left:(r.left+(c.edge==='right'?r.width/2:0))+'px',top:(r.top+(c.edge==='bottom'?r.height/2:0))+'px',width:(horizontal?r.width/2:r.width)+'px',height:(horizontal?r.height:r.height/2)+'px'});previewBox.hidden=false;previewBox.classList.toggle('split-armed',armed);}
 function preview(e){const next=hit(e);if(!next){clear();return;}if(candidate?.pane===next.pane&&candidate.edge===next.edge&&Math.hypot(e.clientX-candidate.x,e.clientY-candidate.y)<=10){show(candidate);return;}clear();candidate={...next,x:e.clientX,y:e.clientY};show(candidate);timer=setTimeout(()=>{if(candidate){armed=true;show(candidate);}},DWELL);}
 function finish(panel,e,cancel=false){const h=hit(e),target=candidate;const commit=!cancel&&armed&&target&&h?.pane===target.pane&&h.edge===target.edge;clear();if(commit)insert(panel,target.pane,target.edge);}
 function init(){
  detail=document.getElementById('detail');const deck=detail?.querySelector('.detail-deck');if(!deck)return;
  area=document.createElement('div');area.id='paneWorkspace';area.className='pane-workspace';deck.before(area);area.append(leaf('news',deck));
  previewBox=document.createElement('div');previewBox.id='splitPreview';previewBox.className='split-preview';previewBox.hidden=true;previewBox.setAttribute('aria-hidden','true');document.body.append(previewBox);
  for(const id of ids){const panel=document.getElementById(id),marker=document.createComment('tool-home');panel.before(marker);homes.set(id,{marker});}
  const saved=root.AtlasUI.read('toolDock',{});ready=true;
  if(saved.version===2&&saved.tree){
   const seen=new Set();function restore(tree,depth=0){if(depth>3||!tree||typeof tree!=='object')throw Error();if(tree.id){if(!['news',...ids].includes(tree.id)||seen.has(tree.id))throw Error();seen.add(tree.id);return {id:tree.id};}if(!['row','column'].includes(tree.axis))throw Error();return {axis:tree.axis,ratio:clamp(Number(tree.ratio)||.5),a:restore(tree.a,depth+1),b:restore(tree.b,depth+1)};}
   try{const tree=restore(saved.tree);if(!seen.has('news'))throw Error();const build=t=>{if(t.id==='news')return leaf('news',deck);if(t.id){const p=document.getElementById(t.id);p.classList.add('docked-tool');if(t.id==='timeFocusBar')document.getElementById('priceSettings').open=false;return leaf(t.id,p);}return branch(build(t.a),build(t.b),t.axis,t.ratio);};area.replaceChildren(build(tree));}catch{for(const id of ids)undock(document.getElementById(id));}
  }else for(const id of saved.ids||[])if(ids.includes(id))insert(document.getElementById(id),area.querySelector('.pane-leaf'),'bottom');
  changed();root.addEventListener('blur',clear);
 }
 root.AtlasDock={init,docked,undock,preview,finish,reflow:p=>{if(docked(p)){const slot=p.closest('.pane-leaf'),parent=slot.parentElement;if(parent.classList.contains('pane-split')){setRatio(parent,Number(parent.dataset.ratio));if(parent.dataset.axis==='column'&&p.classList.contains('collapsed')){slot.style.flex='0 0 88px';const sibling=parent.children[0]===slot?parent.children[2]:parent.children[0];sibling.style.flex='1 1 0';}}changed();}},state:()=>ready?{tree:shape(area.firstElementChild),edge_pixels:EDGE,dwell_ms:DWELL}:null};
})(globalThis);
