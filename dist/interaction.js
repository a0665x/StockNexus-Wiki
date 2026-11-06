/* Screen-space proximity with hysteresis; camera-plane dragging uses the existing force nodes. */
(function(root){
  function adaptiveRadius(bodyRadius,strength=65){const body=Math.max(2,Number(bodyRadius)||2),amount=Math.max(0,Math.min(100,Number(strength)||0))/100;return body+Math.min(80,(6+body*.9)*2*amount);}
  function idleFocus(onIdle,{delay=5500,isBusy=()=>false,schedule=setTimeout,cancel=clearTimeout}={}){let timer=null,disposed=false;const api={touch(){if(disposed)return;if(timer!==null)cancel(timer);timer=schedule(()=>{timer=null;if(isBusy())api.touch();else onIdle();},delay);},stop(){if(timer!==null)cancel(timer);timer=null;},dispose(){api.stop();disposed=true;}};return api;}
  function nearest(points,pointer,current=null,radius=26){
    const ranked=points.map(p=>({...p,distance:Math.hypot(p.x-pointer.x,p.y-pointer.y)})).sort((a,b)=>a.distance-b.distance||a.z-b.z);
    const best=ranked.find(p=>p.distance<=(p.radius??radius)),previous=ranked.find(p=>p.id===current);const hold=previous?.radius??radius,margin=Math.min(14,hold*.27);
    if(previous&&previous.distance<=hold*1.38&&(!best||best.id===current||best.distance+margin>=previous.distance))return previous;
    return best||null;
  }
  function stableFocus(onChange,{delay=80,leaveDelay=140,retainOnLeave=true,schedule=setTimeout,cancel=clearTimeout}={}){
    let current=null,pending=null,timer=null,locked=false;
    function clear(){if(timer!==null)cancel(timer);timer=null;pending=null;}
    function commit(id){clear();if(current===id)return;current=id;onChange(id);}
    return {get:()=>current,offer(id){if(locked)return;if(id===null){if(retainOnLeave){clear();return;}if(current===null||pending===null&&timer!==null)return;clear();timer=schedule(()=>commit(null),leaveDelay);return;}if(id===current){clear();return;}if(id===pending&&timer!==null)return;clear();if(current===null&&id!==null){commit(id);return;}pending=id;timer=schedule(()=>{timer=null;commit(id);},id===null?leaveDelay:delay);},lock(id){locked=true;commit(id);},unlock(){locked=false;},clear(){locked=false;commit(null);},dispose:clear};
  }
  function attach(element,{getGraph,enabled=()=>true,onHover,onSelect,onDragEnd,onBackground=()=>{},onActivity=()=>{},strength=()=>65}){
    if(!element?.setPointerCapture)return {supported:false,hasPointer:()=>false,isDragging:()=>false,refresh(){},guide(){return null;},clear(){},dispose(){}};
    let pointer=null,gesture=null,background=null,suppressClick=false;
    const focus=stableFocus(id=>{const node=getGraph()?.graphData().nodes.find(n=>n.id===id);onHover(node||null);},{retainOnLeave:false});
    function project(onlyId=null){const graph=getGraph();if(!graph||!enabled())return [];const camera=graph.camera(),rect=element.getBoundingClientRect();
      const matrix=camera.matrixWorld?.elements,right=matrix?{x:matrix[0],y:matrix[1],z:matrix[2]}:{x:1,y:0,z:0};const size=Number(graph.nodeRelSize?.())||4,value=graph.nodeVal?.();
      const nodes=graph.graphData().nodes,selected=onlyId===null?null:nodes.find(n=>n.id===onlyId);
      return (onlyId===null?nodes:selected?[selected]:[]).flatMap(node=>{if(!['x','y','z'].every(k=>Number.isFinite(node[k])))return [];const v=camera.position.clone().set(node.x,node.y,node.z).project(camera);if(v.z< -1||v.z>1)return [];
        const amount=typeof value==='function'?value(node):typeof value==='string'?node[value]:value;
        const worldRadius=(Number(node.__threeObj?.scale?.x)||1)*size*Math.cbrt(Number.isFinite(Number(amount))?Math.max(0,Number(amount)):3);
        const edge=camera.position.clone().set(node.x+right.x*worldRadius,node.y+right.y*worldRadius,node.z+right.z*worldRadius).project(camera);
        const body=Math.hypot((edge.x-v.x)*rect.width/2,(edge.y-v.y)*rect.height/2);
        return [{id:node.id,node,x:(v.x+1)*rect.width/2,y:(1-v.y)*rect.height/2,z:v.z,bodyRadius:body,radius:adaptiveRadius(body,strength())}];});}

    function location(event){const r=element.getBoundingClientRect();return {x:event.clientX-r.left,y:event.clientY-r.top};}
    function pick(event,sticky=true){return nearest(project(),location(event),sticky?focus.get():null,0);}
    function world(event,z){const graph=getGraph(),r=element.getBoundingClientRect();return graph.camera().position.clone().set((event.clientX-r.left)/r.width*2-1,1-(event.clientY-r.top)/r.height*2,z).unproject(graph.camera());}
    function move(event){if(!enabled())return;onActivity();if(background&&event.pointerId===background.id&&Math.hypot(event.clientX-background.x,event.clientY-background.y)>4)background.moved=true;if(gesture){if(event.pointerId!==gesture.pointerId)return;event.preventDefault();event.stopImmediatePropagation();const g=gesture;
        if(Math.hypot(event.clientX-g.clientX,event.clientY-g.clientY)>3)g.moved=true;
        if(g.kind==='pan'){const pos=world(event,g.z),camera=getGraph().camera();for(const k of ['x','y','z']){const delta=g.world[k]-pos[k];camera.position[k]+=delta;g.controls.target[k]+=delta;}camera.updateMatrixWorld?.();return;}
        if(g.moved){const pos=world(event,g.z);for(const k of ['x','y','z']){g.node[k]=g.start[k]+pos[k]-g.world[k];g.node['f'+k]=g.node[k];g.node['v'+k]=0;}getGraph().d3ReheatSimulation();}return;
      }
      if(event.buttons||event.ctrlKey)return;pointer={clientX:event.clientX,clientY:event.clientY};focus.offer(pick(event)?.id||null);
    }
    function down(event){if(!enabled()||event.button!==0||event.isPrimary===false||gesture)return;suppressClick=false;onActivity();
      if(event.ctrlKey){const graph=getGraph(),controls=graph.controls(),camera=graph.camera();if(!controls.target)return;
        const target=controls.target.clone().project(camera);gesture={kind:'pan',z:target.z,world:world(event,target.z),pointerId:event.pointerId,clientX:event.clientX,clientY:event.clientY,moved:false,controls,controlsEnabled:controls.enabled};
        background=null;pointer=null;focus.lock(focus.get());controls.enabled=false;suppressClick=true;element.setPointerCapture(event.pointerId);event.preventDefault();event.stopImmediatePropagation();return;
      }
      const hit=pick(event,true);if(!hit){background={id:event.pointerId,x:event.clientX,y:event.clientY,moved:false};return;}background=null;
      const graph=getGraph(),controls=graph.controls();gesture={node:hit.node,z:hit.z,world:world(event,hit.z),start:{x:hit.node.x,y:hit.node.y,z:hit.node.z},fixed:{fx:hit.node.fx,fy:hit.node.fy,fz:hit.node.fz},pointerId:event.pointerId,clientX:event.clientX,clientY:event.clientY,moved:false,controls,controlsEnabled:controls.enabled};
      pointer={clientX:event.clientX,clientY:event.clientY};focus.lock(hit.id);controls.enabled=false;suppressClick=true;element.setPointerCapture(event.pointerId);event.preventDefault();event.stopImmediatePropagation();
    }
    function end(event,cancelled=false){onActivity();if(background&&event.pointerId===background.id){const old=background;background=null;if(!cancelled&&!old.moved)onBackground();}if(!gesture||event.pointerId!==gesture.pointerId)return;const g=gesture;gesture=null;g.controls.enabled=g.controlsEnabled;
      if(g.kind==='pan'){focus.unlock();pointer=null;if(element.hasPointerCapture?.(event.pointerId))element.releasePointerCapture(event.pointerId);event.preventDefault();event.stopImmediatePropagation();return;}
      for(const key of ['fx','fy','fz']){if(g.fixed[key]===undefined)delete g.node[key];else g.node[key]=g.moved?g.node[key.slice(1)]:g.fixed[key];}
      focus.unlock();if(element.hasPointerCapture?.(event.pointerId))element.releasePointerCapture(event.pointerId);event.preventDefault();event.stopImmediatePropagation();
      if(g.moved){g.node.anchor={x:g.node.x,y:g.node.y,z:g.node.z};getGraph().d3ReheatSimulation();onDragEnd?.(g.node);}else if(!cancelled)onSelect(g.node);
      if(event.pointerType==='touch'||cancelled){pointer=null;focus.offer(null);}else focus.offer(pick(event)?.id||null);
    }
    const refresh=()=>{if(pointer&&!gesture&&enabled())focus.offer(pick(pointer)?.id||null);};
    const controls=getGraph()?.controls?.();
    // Trackball's global A/S/D shortcuts also observe typing and can outlive focus.
    if(Array.isArray(controls?.keys)){controls.keys=[];controls.keyState=-1;}
    const resetCamera=()=>{if(gesture)end({pointerId:gesture.pointerId,preventDefault(){},stopImmediatePropagation(){}},true);background=null;pointer=null;focus.clear();if(controls&&'keyState' in controls){controls.keyState=-1;controls.state=-1;}};
    root.addEventListener?.('blur',resetCamera);
    controls?.addEventListener?.('change',refresh);
    const up=e=>end(e),cancel=e=>end(e,true),leave=()=>{if(gesture)return;pointer=null;focus.offer(null);},click=e=>{if(suppressClick){suppressClick=false;e.preventDefault();e.stopImmediatePropagation();}};
    const listeners=[['wheel',onActivity],['pointermove',move],['pointerdown',down],['pointerup',up],['pointercancel',cancel],['lostpointercapture',cancel],['pointerleave',leave],['click',click]];
    for(const [name,fn]of listeners)element.addEventListener(name,fn,true);
    return {supported:true,hasPointer:()=>pointer!==null||focus.get()!==null,isDragging:()=>gesture!==null,refresh,guide(id=focus.get()){if(id==null)return null;const point=project(id)[0];return point?{id:point.id,radius:point.radius}:null;},clear(){background=null;if(gesture){const g=gesture;gesture=null;g.controls.enabled=g.controlsEnabled;if(g.node)Object.assign(g.node,g.fixed);if(element.hasPointerCapture?.(g.pointerId))element.releasePointerCapture(g.pointerId);}pointer=null;focus.clear();},dispose(){this.clear();root.removeEventListener?.('blur',resetCamera);focus.dispose();controls?.removeEventListener?.('change',refresh);for(const [name,fn]of listeners)element.removeEventListener(name,fn,true);}};
  }
  const api={nearest,stableFocus,attach,adaptiveRadius,idleFocus};root.AtlasInteraction=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
