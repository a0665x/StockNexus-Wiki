/* Read the installed Codex model/list catalog; never start an inference turn. */
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
export const WIKI_DEFAULT_MODEL='gpt-6.1-sol';
export function readModels(command,env,{spawnProcess=spawn,timeout=15000}={}){
 return new Promise((resolve,reject)=>{
  const child=spawnProcess(command,['app-server','--stdio'],{env,stdio:['pipe','pipe','ignore']});
  let settled=false,id=1,rows=[],pages=0;
  const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);lines.close();child.stdin.end();child.kill();error?reject(error):resolve(value);};
  const timer=setTimeout(()=>finish(Error('Codex model/list timed out')),timeout);
  const lines=createInterface({input:child.stdout});
  const send=(method,params)=>child.stdin.write(JSON.stringify({id:id++,method,params})+'\n');
  child.on('error',()=>finish(Error('Cannot start Codex model catalog')));
  child.stdin.on('error',()=>finish(Error('Codex model catalog disconnected')));
  child.on('exit',()=>{if(!settled)finish(Error('Codex model catalog exited'));});
  lines.on('line',line=>{try{
   const msg=JSON.parse(line);if(msg.id===undefined)return;
   if(msg.error)return finish(Error('Codex model/list unavailable'));
   if(msg.id===1){child.stdin.write(JSON.stringify({method:'initialized',params:{}})+'\n');send('model/list',{includeHidden:false,limit:100});return;}
   if(!Array.isArray(msg.result?.data))return finish(Error('Invalid model catalog response'));
   rows.push(...msg.result.data.filter(m=>!m.hidden&&typeof m.model==='string').map(m=>({id:m.model,name:m.displayName||m.model,description:m.description||'',reasoning:m.supportedReasoningEfforts||[]})));
   if(msg.result.nextCursor&&++pages<10){send('model/list',{cursor:msg.result.nextCursor,includeHidden:false,limit:100});return;}
   if(msg.result.nextCursor)return finish(Error('Model catalog pagination exceeded limit'));
   finish(null,{models:[...new Map(rows.map(m=>[m.id,m])).values()],default_model:WIKI_DEFAULT_MODEL,source:'codex model/list'});
  }catch{finish(Error('Invalid model catalog response'));}});
  send('initialize',{clientInfo:{name:'stocknexus_wiki',title:'StockNexus Wiki',version:'1.0'},capabilities:null});
 });
}
export function modelCatalog(command,env){let cache=null,pending=null,expires=0;return async()=>{
 if(cache&&Date.now()<expires)return cache;
 if(!pending)pending=readModels(command,env).then(value=>{cache=value;expires=Date.now()+300000;return value;}).finally(()=>{pending=null;});
 return pending;
};}
