import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,readdirSync,statSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createWikiCompiler} from '../chat/wiki.mjs';
import {createWikiTrace} from '../chat/wiki-trace.mjs';
const input={job_id:'a'.repeat(32),parent_job_id:'b'.repeat(32),trace_id:'c'.repeat(32),instrument:'NASDAQ:TSLA',model:'fixture',article:{title:'private-evidence'},context:[]};
test('bridge trace separates catalog SDK parse and correlates usage without content',async()=>{
 const rows=[];const c=createWikiCompiler(()=>({run:async()=>{await new Promise(r=>setTimeout(r,20));return {finalResponse:'{"nodes":[]}',items:[],usage:{input_tokens:10,output_tokens:2}};}}),{trace:r=>rows.push(r),validateModel:async()=>{}});
 await c.run(input);
 const model=rows.find(r=>r.stage==='sdk_run'&&r.event==='end');
 assert.ok(model.elapsed_ms>=15);assert.equal(model.job_id,input.parent_job_id);assert.equal(model.call_id,input.trace_id);assert.equal(model.usage.output_tokens,2);
 assert.deepEqual(rows.filter(r=>r.event==='end').map(r=>r.stage),['catalog','sdk_run','parse_response','bridge_call']);
 assert.ok(!JSON.stringify(rows).includes('private-evidence'));
});
test('failed SDK call records safe failure and releases slot even if sink fails',async()=>{
 const rows=[];const c=createWikiCompiler(()=>({run:async()=>{throw Error('secret-token');}}),{trace:r=>rows.push(r)});
 await assert.rejects(c.run(input));await assert.rejects(c.run(input));
 assert.equal(rows.filter(r=>r.stage==='sdk_run'&&r.event==='error').length,2);assert.ok(!JSON.stringify(rows).includes('secret-token'));
 const good=createWikiCompiler(()=>({run:async()=>({finalResponse:'{}',items:[]})}),{trace:()=>{throw Error('disk');}});await good.run(input);
});
test('private trace rotates to bounded valid JSONL files',()=>{
 const dir=mkdtempSync(join(tmpdir(),'wiki-trace-'));try{
 const log=createWikiTrace(join(dir,'bridge.jsonl'),{maxBytes:300,backups:2});for(let i=0;i<20;i++)log({event:'state',stage:'test',i});
 assert.equal(readdirSync(dir).length,3);for(const name of readdirSync(dir)){const path=join(dir,name);assert.equal(statSync(path).mode&0o777,0o600);for(const line of readFileSync(path,'utf8').trim().split('\n'))JSON.parse(line);}
 }finally{rmSync(dir,{recursive:true,force:true});}
});
test('in-flight model heartbeat stops after completion',async t=>{
 t.mock.timers.enable({apis:['setInterval']});
 let release;const rows=[];const c=createWikiCompiler(()=>({run:()=>new Promise(r=>{release=r;})}),{trace:r=>rows.push(r)});
 const pending=c.run(input);t.mock.timers.tick(15000);
 assert.equal(rows.filter(r=>r.event==='heartbeat'&&r.stage==='sdk_run').length,1);
 release({finalResponse:'{}',items:[]});await pending;t.mock.timers.tick(30000);
 assert.equal(rows.filter(r=>r.event==='heartbeat').length,1);t.mock.timers.reset();
});
