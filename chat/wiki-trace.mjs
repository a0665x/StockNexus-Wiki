/* Metadata-only private trace. Separate file from Python: one writer per process. */
import {mkdirSync,statSync,existsSync,renameSync,appendFileSync} from 'node:fs';
import {dirname} from 'node:path';
export function createWikiTrace(path,{maxBytes=8*1024*1024,backups=5}={}){
 let warned=false;
 return row=>{if(!path)return;try{
  mkdirSync(dirname(path),{recursive:true,mode:0o700});
  const line=JSON.stringify({schema:1,ts:new Date().toISOString(),process:'bridge',pid:process.pid,...row})+'\n';
  if(existsSync(path)&&statSync(path).size+Buffer.byteLength(line)>maxBytes){for(let n=backups;n>=1;n--){const src=n===1?path:path+'.'+(n-1);if(existsSync(src))renameSync(src,path+'.'+n);}}
  appendFileSync(path,line,{mode:0o600});
 }catch{if(!warned){warned=true;process.stderr.write('Wiki bridge trace write failed; check private log storage.\n');}}};
}
