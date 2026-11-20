// Private application history. Browser capabilities never expose SDK thread IDs.
import {existsSync,readFileSync,mkdirSync,writeFileSync,renameSync} from 'node:fs';
import {dirname} from 'node:path';
import {randomBytes,randomUUID} from 'node:crypto';
const fail=(message,status=400)=>Object.assign(new Error(message),{status});
export function createHistory(path){
 const data=path&&existsSync(path)?JSON.parse(readFileSync(path,'utf8')):{owners:{}};
 const save=()=>{if(!path)return;mkdirSync(dirname(path),{recursive:true,mode:0o700});const tmp=path+'.'+randomUUID()+'.tmp';writeFileSync(tmp,JSON.stringify(data),{mode:0o600});renameSync(tmp,path);};
 const owner=key=>{if(!/^[a-f0-9]{64}$/.test(key||'')||!Object.hasOwn(data.owners,key))throw fail('Chat history unavailable for this browser',401);return data.owners[key];};
 const get=(key,id)=>{const item=owner(key).find(x=>x.id===id);if(!item)throw fail('Conversation not found',404);return item;};
 const publicRecord=item=>{const {threadId,...safe}=item;return structuredClone(safe);};
 return {
  owner(key){if(key){owner(key);return key;}key=randomBytes(32).toString('hex');data.owners[key]=[];save();return key;},
  get,
  list(key,surface){return owner(key).filter(x=>x.surface===surface).map(({messages,threadId,...rest})=>({...rest,message_count:messages.length})).sort((a,b)=>b.updated_at.localeCompare(a.updated_at));},
  publicRecord,
  create(key,surface){const rows=owner(key);if(rows.length>=200)throw fail('Conversation limit reached; delete an old conversation first',409);const now=new Date().toISOString();const item={id:randomUUID(),surface,title:'',instrument:null,created_at:now,updated_at:now,messages:[],threadId:null,model:null};rows.push(item);save();return item;},
  append(key,id,role,text){const item=get(key,id);if(item.messages.length>=2000)throw fail('Conversation is full; start a new chat',409);item.messages.push({role,text,created_at:new Date().toISOString()});if(role==='user'&&!item.title)item.title=text.slice(0,100);item.updated_at=new Date().toISOString();save();},
  update(key,id,values){Object.assign(get(key,id),values);save();},
  remove(key,id){get(key,id);data.owners[key]=owner(key).filter(x=>x.id!==id);save();}
 };
}
