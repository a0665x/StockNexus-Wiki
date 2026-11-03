/* Direct curve sculpting and per-frame mesh sizing. No graph-data or physics mutation. */
(function(root){
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  const maximum=cfg=>cfg.profile?Math.max(...cfg.profile):cfg.peak;
  const compensation=cfg=>cfg.enabled?clamp((maximum(cfg)-2)/6,0,1):0;
  function depthScale(depth,reference,strength){
    if(!(depth>0&&reference>0)||!strength)return 1;
    return Math.pow(depth/reference,strength);
  }
  function attach(graph,getState){
    const renderer=graph?.renderer?.();if(!renderer?.render)return {refresh(){},dispose(){}};
    const original=renderer.render;
    function refresh(){
      const {config,dates,scale}=getState(),sizeAt=root.AtlasTimeline.timeEvaluator(config,dates),camera=graph.camera();camera.updateMatrixWorld?.();
      const matrix=camera.matrixWorldInverse?.elements;
      const depth=p=>matrix?-(matrix[2]*(p.x||0)+matrix[6]*(p.y||0)+matrix[10]*(p.z||0)+matrix[14]):0;
      const reference=depth(graph.controls?.()?.target||{x:0,y:0,z:0}),amount=compensation(config);
      for(const node of graph.graphData().nodes||[]){
        const object=node.__threeObj;if(!object?.scale?.setScalar)continue;
        const size=(scale?scale(node,sizeAt(node)):sizeAt(node))*depthScale(depth(node),reference,amount);
        object.scale.setScalar(Number.isFinite(size)&&size>0?size:1);
      }
    }
    function render(scene,camera){if(scene===graph.scene()&&camera===graph.camera())refresh();return original.apply(this,arguments);}
    renderer.render=render;
    return {refresh,dispose(){if(renderer.render===render)renderer.render=original;for(const n of graph.graphData().nodes||[])n.__threeObj?.scale?.setScalar?.(1);}};
  }
  const count=129,brushRadius=.12;
  const shape=cfg=>({peak:cfg.peak,width:cfg.width,profile:cfg.profile??null});
  // One stroke is evaluated from its initial profile, not accumulated pointer events.
  // The compact cosine brush changes only nearby dates and has zero slope at its edge.
  function sculpt(config,dates,offset,logDelta){
    return Array.from({length:count},(_,i)=>{
      const position=i/64-1,distance=Math.abs(position-offset)/brushRadius;
      const weight=distance<1?(1+Math.cos(Math.PI*distance))/2:0;
      return clamp(Math.exp(Math.log(root.AtlasTimeline.profileGain(config,position,dates))+logDelta*weight),1,12);
    });
  }
  function stretch(config,dates,offset,dx){
    const both=Math.abs(offset)<.025,side=offset<0?-1:1;
    const factor=clamp(both?Math.exp(dx*5):1+dx*side/Math.abs(offset),.2,5);
    const profile=Array.from({length:count},(_,i)=>{
      const point=i/64-1,applies=both||point*side>=0;
      return root.AtlasTimeline.profileGain(config,applies?point/factor:point,dates);
    });
    return {config:{...config,profile},offset:offset*factor};
  }
  function curve(config,dates){
    const span=Math.max(1,dates.days),center=clamp((root.AtlasTimeline.day(config.date)-dates.start)/86400000/span,0,1);
    const gain=x=>root.AtlasTimeline.profileGain(config,x-center,dates);
    const y=x=>88-72*Math.log(gain(x))/Math.log(12);
    const points=Array.from({length:257},(_,i)=>[i/256,y(i/256)]);
    points.push([center,y(center)]);points.sort((a,b)=>a[0]-b[0]);
    return {center,peakY:y(center),points,gain,y};
  }
  function init($,{getState,onChange,onBusy=()=>{}}){
    const svg=$('timeBell'),handle=$('timeBellHandle'),t=text=>root.AtlasI18n?.t(text)||text;
    let drag=null,selected=null,undo=null;
    function paint(){
      const {config,dates,viewport=dates,components}=getState();if(!dates)return;const model=curve(config,dates),at=selected??model.center;
      const x=v=>12+((dates.start+v*dates.days*86400000-viewport.start)/Math.max(86400000,viewport.end-viewport.start))*976,path=model.points.map(([a,b],i)=>(i?'L':'M')+x(a).toFixed(2)+' '+b.toFixed(2)).join(' ');
      if(components){
        const fractions=model.points.map(([a,b])=>{const date=new Date(dates.start+Math.round(a*dates.days)*86400000).toISOString().slice(0,10),part=components(date,model.gain(a));return [x(a),88-(88-b)*part.priceShare];});
        const boundary=fractions.map(([a,b],i)=>(i?'L':'M')+a.toFixed(2)+' '+b.toFixed(2)).join(' ');
        for(const [id,color,d] of [['timeContribution','#65aaf5',path+' '+fractions.slice().reverse().map(([a,b])=>'L'+a.toFixed(2)+' '+b.toFixed(2)).join(' ')+' Z'],['priceContribution','#f1ba59',boundary+' L'+x(1)+' 88 L'+x(0)+' 88 Z']]){let n=$(id);if(!n){n=document.createElementNS('http://www.w3.org/2000/svg','path');n.id=id;n.setAttribute('fill',color);n.setAttribute('opacity','.65');n.style.pointerEvents='none';$('timeBellLine').before(n);}n.setAttribute('d',d);}
        $('timeBellFill').style.opacity='0';
      }
      $('timeBellLine').setAttribute('d',path);$('timeBellHit').setAttribute('d',path);$('timeBellFill').setAttribute('d',path+' L'+x(1)+' 88 L'+x(0)+' 88 Z');
      $('timeBellCenter').setAttribute('x1',x(model.center));$('timeBellCenter').setAttribute('x2',x(model.center));
      const rect=svg.getBoundingClientRect();handle.setAttribute('rx',8000/Math.max(1,rect.width));handle.setAttribute('ry',800/Math.max(1,rect.height));
      handle.setAttribute('cx',x(at));handle.setAttribute('cy',model.y(at));handle.setAttribute('aria-disabled',String(!config.enabled));handle.setAttribute('tabindex',config.enabled?'0':'-1');
      const date=new Date(dates.start+Math.round(at*dates.days)*86400000).toISOString().slice(0,10),value=model.gain(at).toFixed(1)+'×';
      handle.setAttribute('aria-valuenow',model.gain(at).toFixed(1));handle.setAttribute('aria-valuetext',date+' · '+value);
      $('timeCurvePoint').textContent=date+' · '+value;
      if(components){const part=components(date,model.gain(at));$('timeCurvePoint').textContent+=` · ${t('時間')} ${((1-part.priceShare)*100).toFixed(0)}% / ${t('股價')} ${(part.priceShare*100).toFixed(0)}% · ${t('混合倍率')} ${part.total.toFixed(2)}× · Δ ${part.delta===null?'—':(part.delta*100).toFixed(2)+'%'} · z ${part.normalized===null?'—':part.normalized.toFixed(2)}`;}

      $('timePeakValue').textContent=maximum(config).toFixed(1)+'×';
      $('timePerspective').textContent=t('遠近補償')+' '+Math.round(compensation(config)*100)+'%';
      $('timeBellUndo').disabled=!config.enabled||!undo||!!drag;$('timeBellReset').disabled=!config.enabled||!!drag;
      svg.classList.toggle('inactive',!config.enabled);
    }
    function change(values){onChange(values);paint();}
    const position=(event,rect)=>{const {dates,viewport=dates}=getState(),fraction=clamp(((event.clientX-rect.left)/Math.max(1,rect.width)*1000-12)/976,0,1);return clamp((viewport.start+fraction*(viewport.end-viewport.start)-dates.start)/Math.max(86400000,dates.end-dates.start),0,1);};
    function begin(event){
      if(event.button!==0||!getState().config.enabled||drag)return;
      event.preventDefault();event.stopPropagation();
      const {config,dates}=getState(),rect=svg.getBoundingClientRect(),model=curve(config,dates);
      selected=event.currentTarget===handle?(selected??model.center):position(event,rect);
      drag={id:event.pointerId,x:event.clientX,y:event.clientY,config,dates,rect,offset:selected-model.center,center:model.center,changed:false};
      svg.setPointerCapture?.(event.pointerId);svg.classList.add('dragging');onBusy(true);paint();
    }
    for(const element of [handle,$('timeBellLine'),$('timeBellHit')])element.addEventListener('pointerdown',begin);
    svg.addEventListener('pointermove',event=>{
      if(!drag){if(getState().config.enabled){selected=position(event,svg.getBoundingClientRect());paint();}return;}
      if(event.pointerId!==drag.id)return;event.preventDefault();event.stopPropagation();
      const delta=(drag.y-event.clientY)/Math.max(1,drag.rect.height)*100/72*Math.log(12);
      const state=getState(),view=state.viewport||drag.dates;const dx=(event.clientX-drag.x)/Math.max(1,drag.rect.width)*1000/976*(view.end-view.start)/Math.max(86400000,drag.dates.end-drag.dates.start);
      if(!delta&&!dx&&!drag.changed)return;
      if(!drag.changed){undo=drag.config;drag.changed=true;}
      // Returning to the grab height restores the exact pre-stroke curve.
      const widened=dx?stretch(drag.config,drag.dates,drag.offset,dx):{config:drag.config,offset:drag.offset};
      selected=clamp(drag.center+widened.offset,0,1);
      change(delta||dx?{profile:sculpt(widened.config,drag.dates,widened.offset,delta)}:shape(drag.config));
    });
    function finish(event){if(!drag||event.pointerId!==drag.id)return;const id=drag.id;drag=null;svg.classList.remove('dragging');if(svg.hasPointerCapture?.(id))svg.releasePointerCapture(id);onBusy(false);paint();}
    for(const name of ['pointerup','pointercancel','lostpointercapture'])svg.addEventListener(name,finish);
    handle.addEventListener('keydown',event=>{
      const {config,dates}=getState();if(!config.enabled||drag)return;
      if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();event.stopPropagation();const model=curve(config,dates);selected=selected??model.center;
      if(event.shiftKey&&(event.key==='ArrowLeft'||event.key==='ArrowRight')){undo=config;const widened=stretch(config,dates,selected-model.center,event.key==='ArrowRight'?.015:-.015);selected=clamp(model.center+widened.offset,0,1);change({profile:widened.config.profile});return;}
      if(event.key==='ArrowLeft'||event.key==='ArrowRight'){selected=clamp(selected+(event.key==='ArrowRight'?1:-1)/Math.max(1,dates.days),0,1);paint();return;}
      undo=config;const gain=model.gain(selected),target=event.key==='Home'?1:event.key==='End'?12:clamp(gain+(event.key==='ArrowUp'?.2:-.2),1,12);
      change({profile:sculpt(config,dates,selected-model.center,Math.log(target/gain))});
    });
    $('timeBellUndo').onclick=()=>{if(!undo||drag||!getState().config.enabled)return;const previous=undo;undo=null;change(shape(previous));};
    $('timeBellReset').onclick=()=>{if(drag||!getState().config.enabled)return;undo=getState().config;selected=null;change({peak:2,width:.12,profile:null});};
    if(typeof ResizeObserver!=='undefined')new ResizeObserver(paint).observe(svg);
    return {paint,isDragging:()=>!!drag};
  }
  const api={maximum,compensation,depthScale,curve,sculpt,stretch,attach,init};root.AtlasTimeLens=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(globalThis);
