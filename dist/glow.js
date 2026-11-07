/* Additive screen-space light, projected from the existing 3D camera. No physics changes. */
(function(root){
  const defaults={enabled:true,brightness:1.55,radius:25,decay:.9,background:.18};
  function settings(value={}){const out={enabled:value.enabled!==false};for(const [key,min,max]of [['brightness',0,2],['radius',12,90],['decay',.2,.9],['background',.03,.6]]){const n=Number(value[key]);out[key]=value[key]!==undefined&&Number.isFinite(n)?Math.max(min,Math.min(max,n)):defaults[key];}return out;}
  function level(depth,options={}){const cfg=settings(options);return cfg.enabled?cfg.brightness*Math.pow(cfg.decay,Math.max(0,depth)):0;}
  function tint(hex,amount){const rgb=(hex.match(/[a-f\d]{2}/gi)||['b9','d8','df']).map(v=>parseInt(v,16));return `rgb(${rgb.map(v=>Math.round(v*Math.max(0,Math.min(1,amount)))).join(',')})`;}
  const ease=(current,target,dt,reduced=false,tau=85)=>reduced?target:current+(target-current)*(1-Math.exp(-Math.max(0,Math.min(64,dt))/tau));
  // Adapter for the pinned 3d-force-graph bundle's node/link mesh bindings.
  // Clone per-object materials: the library can share one material among many nodes.
  function appearance(){
    const cache=new WeakMap();
    function paint(object,target,amount){
      const apply=mesh=>{if(!mesh.material?.color||Array.isArray(mesh.material)||!mesh.material.clone)return;
        let state=cache.get(mesh);if(!state||state.material!==mesh.material){if(state)state.material.dispose?.();const original=mesh.material,material=original.clone();mesh.material=material;state={original,material,goal:material.color.clone(),target:null};cache.set(mesh,state);}
        if(state.target!==target.color){state.goal.set(target.color);state.target=target.color;}
        state.material.color.lerp(state.goal,amount);
        if(target.opacity!==undefined){state.material.opacity+=(target.opacity-state.material.opacity)*amount;state.material.transparent=true;}
      };
      if(object?.traverse)object.traverse(apply);else if(object)apply(object);
    }
    return {dispose(graph){const data=graph?.graphData?.();for(const obj of [...(data?.nodes||[]).map(n=>n.__threeObj),...(data?.links||[]).map(e=>e.__lineObj)]){const restore=mesh=>{const state=cache.get(mesh);if(!state)return;if(mesh.material===state.material)mesh.material=state.original;state.material.dispose?.();cache.delete(mesh);};if(obj?.traverse)obj.traverse(restore);else if(obj)restore(obj);}},step(graph,nodeStyle,edgeStyle,dt,active,reduced){const data=graph.graphData?.();if(!data)return;const amount=ease(0,1,dt,reduced,active?85:260);
      if(nodeStyle)for(const n of data.nodes||[])paint(n.__threeObj,{color:nodeStyle(n)},amount);
      if(edgeStyle)for(const e of data.links||[])paint(e.__lineObj,edgeStyle(e),amount);
    }};
  }
  function attach(canvas,getState){
    const ctx=canvas?.getContext?.('2d'),initial=getState(),renderer=initial.graph?.renderer?.();
    if(!ctx||!renderer?.render)return {refresh(){},dispose(){}};
    const originalRender=renderer.render,lights=new Map(),links=new Map(),materials=appearance();let disposed=false,lastTime=null;
    function draw(dt){
      if(disposed)return;const {graph,trace,config,colors,active,visible=true,reducedMotion=false,hitGuide=null}=getState();
      const rect=canvas.getBoundingClientRect(),dpr=Math.min(root.devicePixelRatio||1,2),w=Math.round(rect.width*dpr),h=Math.round(rect.height*dpr);
      if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
      ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,rect.width,rect.height);
      if(!graph||!visible||document.hidden||!config.enabled||config.brightness===0){lights.clear();links.clear();return;}
      if(!active&&!lights.size)return;
      const camera=graph.camera(),projected=new Map(),wantedLinks=new Map();
      const data=graph.graphData().nodes,ids=new Set(data.map(n=>n.id));
      for(const id of lights.keys())if(!ids.has(id))lights.delete(id);
      for(const node of data){
        const info=active?trace.nodes.get(node.id):null,previous=lights.get(node.id)||{light:0,radius:config.radius};
        const target=info?level(info.depth,config):0;
        const light=ease(previous.light,target,dt,reducedMotion,active?85:260);
        const radius=ease(previous.radius,config.radius*(info?.depth===0?1.45:Math.max(.45,Math.pow(.9,info?.depth||1))),dt,reducedMotion);
        if(light<.001&&!info){lights.delete(node.id);continue;}
        lights.set(node.id,{light,radius});
        for(const parent of info?.parents||(info?.parent!=null?[info.parent]:[]))wantedLinks.set(JSON.stringify([parent,node.id]),{from:parent,to:node.id,target});
        if(!['x','y','z'].every(k=>Number.isFinite(node[k])))continue;
        const v=camera.position.clone().set(node.x,node.y,node.z).project(camera);if(v.z< -1||v.z>1)continue;
        const x=(v.x+1)*rect.width/2,y=(1-v.y)*rect.height/2;if(x< -140||y< -140||x>rect.width+140||y>rect.height+140)continue;
        projected.set(node.id,{x,y,radius,color:(typeof colors==='function'?colors(node):colors[node.display_provider||node.source?.provider])||'#b9d8df',light});
      }
      for(const [id,edge] of wantedLinks)if(!links.has(id))links.set(id,{...edge,light:0});
      ctx.globalCompositeOperation='lighter';
      for(const [id,edge]of links){edge.light=ease(edge.light,wantedLinks.get(id)?.target||0,dt,reducedMotion,active?85:260);if(edge.light<.001&&!wantedLinks.has(id)){links.delete(id);continue;}
        const parent=projected.get(edge.from),node=projected.get(edge.to);if(!parent||!node)continue;
        const gradient=ctx.createLinearGradient(parent.x,parent.y,node.x,node.y);gradient.addColorStop(0,`rgba(135,235,220,${Math.min(.7,edge.light*.5)})`);gradient.addColorStop(1,`rgba(135,200,255,${Math.min(.7,edge.light*.3)})`);
        ctx.strokeStyle=gradient;ctx.lineWidth=2+edge.light*2;ctx.shadowBlur=10;ctx.shadowColor=node.color;ctx.beginPath();ctx.moveTo(parent.x,parent.y);ctx.lineTo(node.x,node.y);ctx.stroke();
      }
      ctx.shadowBlur=0;
      // Keep dense category halos colored; additive blending clips hundreds of overlaps to white.
      ctx.globalCompositeOperation='source-over';
      for(const node of [...projected.values()].sort((a,b)=>a.light-b.light)){
        const {radius}=node,alpha=1-Math.exp(-node.light*1.6),rgb=node.color.match(/[a-f\d]{2}/gi).map(v=>parseInt(v,16)).join(',');
        const gradient=ctx.createRadialGradient(node.x,node.y,0,node.x,node.y,radius);
        gradient.addColorStop(0,`rgba(255,255,255,${alpha})`);gradient.addColorStop(.09,`rgba(${rgb},${alpha*.9})`);gradient.addColorStop(.32,`rgba(${rgb},${alpha*.36})`);gradient.addColorStop(.65,`rgba(${rgb},${alpha*.1})`);gradient.addColorStop(1,`rgba(${rgb},0)`);
        ctx.fillStyle=gradient;ctx.fillRect(node.x-radius,node.y-radius,radius*2,radius*2);
      }
      ctx.globalCompositeOperation='source-over';
      if(active&&trace.roots?.length>1&&typeof ctx.fillText==='function'){ctx.save();ctx.font='600 12px system-ui';ctx.fillStyle='#f2ffff';for(const [i,id]of trace.roots.entries()){const p=projected.get(id);if(p){ctx.globalAlpha=1-Math.exp(-p.light*1.6);ctx.fillText('#'+(i+1),p.x+12,p.y-12);}}ctx.restore();}
      if(hitGuide){const point=projected.get(hitGuide.id);if(point){ctx.save();ctx.setLineDash([4,5]);ctx.strokeStyle='rgba(205,245,236,.8)';ctx.lineWidth=1;ctx.beginPath();ctx.arc(point.x,point.y,hitGuide.radius,0,Math.PI*2);ctx.stroke();ctx.restore();}}
    }
    // The exact camera/physics state used for WebGL is projected immediately after its render.
    function renderWithGlow(scene,camera){const state=getState(),graph=state.graph,main=graph&&scene===graph.scene()&&camera===graph.camera();let dt=16;
      if(main){const now=performance.now();dt=lastTime===null?16:now-lastTime;lastTime=now;materials.step(graph,state.nodeStyle,state.edgeStyle,dt,state.active,state.reducedMotion);}
      const result=originalRender.apply(this,arguments);if(main)draw(dt);return result;}
    renderer.render=renderWithGlow;
    return {refresh(){/* The next graph frame draws the new target without restarting a RAF loop. */},dispose(){disposed=true;if(renderer.render===renderWithGlow)renderer.render=originalRender;materials.dispose(getState().graph);lights.clear();links.clear();ctx.clearRect(0,0,canvas.width,canvas.height);}};
  }
  const api={settings,level,tint,attach,ease,appearance};root.AtlasGlow=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
