// Isolated real MCP transport. Deterministic agent by default; optional one live read-only turn.
import {createService} from '../chat/service.mjs';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {appendFileSync,readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {homedir} from 'node:os';
import {Codex} from '@openai/codex-sdk';
import assert from 'node:assert/strict';
const socket=process.argv[2],audit=process.argv[3];
const record=x=>appendFileSync(audit,JSON.stringify(x)+'\n');
const deterministic=token=>({async runStreamed(prompt){
 assert.match(prompt,/Three future trading sessions/);
 return {events:(async function*(){
 const client=new Client({name:'bdd-research-reader',version:'1.0'});
 await client.connect(new StdioClientTransport({command:process.execPath,args:[resolve('chat/mcp.mjs')],env:{...process.env,ATLAS_CHAT_SOCKET:socket,ATLAS_TOOL_TOKEN:token},stderr:'pipe'}));
 try{
  const list=await client.listTools();assert(list.tools.some(t=>t.name==='read_research'&&t.annotations.readOnlyHint));
  const call=async(name,args={})=>{const out=await client.callTool({name,arguments:args});assert(!out.isError,JSON.stringify(out));const result=JSON.parse(out.content[0].text);record({name,args,result});return result;};
  const state=await call('get_state');assert.equal(state.surface,'wiki');
  const r=await call('read_research',{lookback_days:7});
  assert.equal(r.temporal.recent_count,2);assert.equal(r.temporal.evidence.filter(e=>e.status==='older_context').length,1);
  assert(!r.bundle.opinions.some(o=>o.title.includes('FUTURE')));assert(r.bundle.opinions.some(o=>o.title.includes('OLD')));
  assert(r.result.support.length&&r.result.counter.length);assert.equal(r.forecast.status,'unavailable');assert.equal(r.coverage.render_budget_applied,false);assert.equal(r.temporal.snapshot_stale,true);assert.equal(r.temporal.pending_l1,1);
  const refs=r.temporal.evidence.filter(e=>e.status==='recent');
  const table='| 情境 | 近期線索 | 三交易日目標 |\n| --- | --- | --- |\n'+refs.map((e,i)=>`| ${i?'偏空條件':'偏多條件'} | [來源 ${i+1}](${e.url}) · ${e.published_at.slice(0,10)} | 資料不足，無法估計數字目標價 |`).join('\n');
  yield {type:'item.completed',item:{type:'agent_message',text:'近七日兩筆消息；舊聞僅作背景。依 L2 的支持與反證及其 L1 引用，情境仍有分歧。\n\n'+table+'\n\n<img src=x onerror="window.injected=true">\n\n```html\n<table>not markup</table>\n```'}};
  yield {type:'turn.completed'};
 }finally{await client.close();}
 })()};
}});
const live=token=>{
 const home=join(homedir(),'.local/state/stocknexus-wiki/chat'),thread=new Codex({env:{...process.env,CODEX_HOME:home},config:{features:{shell_tool:false},cli_auth_credentials_store:'file',mcp_servers:{stocknexus:{required:true,enabled_tools:['get_state','read_research','read_wiki','read_edges'],tools:Object.fromEntries(['get_state','read_research','read_wiki','read_edges'].map(name=>[name,{approval_mode:'approve'}])),command:process.execPath,args:[resolve('chat/mcp.mjs')],env:{ATLAS_CHAT_SOCKET:socket,ATLAS_TOOL_TOKEN:token}}}}}).startThread({model:'gpt-6.1-sol',modelReasoningEffort:'low',workingDirectory:join(home,'work'),skipGitRepoCheck:true,sandboxMode:'read-only',approvalPolicy:'never',webSearchMode:'disabled'});
 return {async runStreamed(prompt,{signal}){const r=await thread.runStreamed(prompt,{signal:AbortSignal.any([signal,AbortSignal.timeout(150000)])});return {events:(async function*(){for await(const e of r.events){if(e.type==='item.completed')record({live_item:e.item});yield e;}})()};}};
};
const replay=()=>({async runStreamed(){return {events:(async function*(){const rows=readFileSync(process.env.ATLAS_BDD_REPLAY,'utf8').trim().split('\n').map(JSON.parse);for(const r of rows)if(r.live_item){record(r);yield {type:'item.completed',item:r.live_item};}yield {type:'turn.completed'};})()};}});
const service=createService({makeThread:process.env.ATLAS_BDD_REPLAY?replay:process.env.ATLAS_BDD_LIVE==='1'?live:deterministic});
service.listen(socket,()=>record({ready:true}));
process.on('SIGTERM',()=>{service.shutdown();service.closeAllConnections();});
