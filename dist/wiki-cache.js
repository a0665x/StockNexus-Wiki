// One tab owns the graph bodies. The server issues tokens for exact query scopes.
(function(root){
 'use strict';
 function applyDelta(graph, delta){
  const result={...graph,...delta.set};
  for(const [field,patch] of Object.entries(delta.rows)){
   const rows=new Map(graph[field].map(row=>[row[patch.key],row]));
   for(const row of patch.upsert)rows.set(row[patch.key],row);
   result[field]=(patch.order||[...rows.keys()]).map(id=>{
    if(!rows.has(id))throw Error('Incomplete Wiki graph update');
    return rows.get(id);
   });
  }
  for(const [field,patch] of Object.entries(delta.maps)){
   const values={...graph[field],...patch.set};
   for(const key of patch.remove)delete values[key];
   result[field]=values;
  }
  return result;
 }
 function create(api){
  const graphs=new Map(),states=new Map(),pending=new Map();
  const catalogs=new Map();
  function remember(map,key,value){
   map.delete(key);map.set(key,value);
   if(map.size>4)map.delete(map.keys().next().value);
   return value;
  }
  function share(key,work){
   if(!pending.has(key)){
    const job=work();pending.set(key,job);
    const clear=()=>{if(pending.get(key)===job)pending.delete(key);};
    job.then(clear,clear);
   }
   return pending.get(key);
  }
  function catalog(path,ttl){
   const hit=catalogs.get(path);
   if(hit&&Date.now()-hit.at<ttl)return Promise.resolve(hit.value);
   return share(path,async()=>{
    const value=await api(path);catalogs.set(path,{value,at:Date.now()});return value;
   });
  }
  function state(instrument){
   const key='state:'+instrument;
   const flight=share(key,async()=>{
    const previous=states.get(instrument);
    const query=new URLSearchParams({instrument,view:'compact'});
    if(previous?.config_token)query.set('config_token',previous.config_token);
    const fresh=await api('jobs?'+query);
    if(fresh.instrument&&fresh.instrument!==instrument)throw Error('Wiki instrument mismatch');
    if(!fresh.config&&fresh.config_token&&fresh.config_token!==previous?.config_token)throw Error('Missing Wiki configuration');
    const value={...fresh,config:fresh.config||previous?.config||{}};
    if(pending.get(key)===flight)remember(states,instrument,value);
    return value;
   });
   return flight;
  }
  function invalidateState(instrument){
   states.delete(instrument);pending.delete('state:'+instrument);
  }
  function graph(key){
   return share('graph:'+key,async()=>{
    const previous=graphs.get(key),query=new URLSearchParams(key),ident=query.get('instrument');
    query.set('sync','1');
    if(previous?.token)query.set('since',previous.token);
    let response=await api('graph?'+query);
    function snapshot(value,body){
     if(value.instrument!==ident||body.instrument!==ident)throw Error('Wiki instrument mismatch');
     return remember(graphs,key,{value:body,token:value.token,epoch:value.epoch});
    }
    if(response.instrument!==ident)throw Error('Wiki instrument mismatch');
    if(previous&&response.kind==='unchanged'&&response.token===previous.token)
     return snapshot(response,previous.value);
    if(previous&&response.kind==='delta'&&response.base===previous.token){
     let updated;
     try{updated=applyDelta(previous.value,response);}catch{/* Read one authoritative snapshot below. */}
     if(updated)return snapshot(response,updated);
    }
    if(response.kind==='unchanged'||response.kind==='delta'){
     query.delete('since');response=await api('graph?'+query);
    }
    if(!response.kind)return snapshot(response,response); // Login sessions can straddle a server upgrade.
    if(response.kind!=='full')throw Error('Missing Wiki graph snapshot');
    return snapshot(response,response.graph);
   });
  }
  return {catalog,state,graph,invalidateState,peekCatalog:path=>catalogs.get(path)?.value,hasPendingGraph:key=>pending.has('graph:'+key),peekState:key=>states.get(key),peekGraph:key=>graphs.get(key)};
 }
 root.AtlasWikiCache={create};
})(globalThis);
