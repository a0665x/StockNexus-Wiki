/* Shared host persistence; restoring UI never starts inference. */
(function(root){
 const state={},pending=new Map(),timers=new Map(),chains=new Map();
 const ready=fetch('/api/workspace').then(r=>{if(!r.ok)throw Error('Workspace unavailable');return r.json();}).then(value=>Object.assign(state,value)).catch(e=>console.warn(e.message));
 function send(section){const value=pending.get(section);if(!value)return chains.get(section)||Promise.resolve();pending.delete(section);const chain=(chains.get(section)||Promise.resolve()).then(async()=>{try{const res=await fetch('/api/workspace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({section,value})});if(!res.ok)throw Error('Workspace save failed');}catch(e){pending.set(section,{...value,...pending.get(section)});console.warn(e.message);}});chains.set(section,chain);return chain;}
 root.AtlasWorkspace={state,ready,save(section,value){state[section]={...state[section],...value};pending.set(section,{...pending.get(section),...value});clearTimeout(timers.get(section));timers.set(section,setTimeout(()=>send(section),450));},flush:()=>Promise.all([...new Set([...pending.keys(),...chains.keys()])].map(send))};
 root.addEventListener('pagehide',()=>queueMicrotask(()=>{for(const [section,value] of pending){const compact={...value};delete compact.snapshot;fetch('/api/workspace',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({section,value:compact}),keepalive:true}).catch(()=>{});}}));
})(globalThis);
