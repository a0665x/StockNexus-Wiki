import { execFile, spawn } from 'node:child_process';
import { promisify } from 'node:util';
import { constants } from 'node:fs';
import { access, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { delimiter, join } from 'node:path';
import { tmpdir } from 'node:os';

const exec = promisify(execFile);
const ollama = 'http://127.0.0.1:11434';
async function executable(name) {
  for (const dir of (process.env.PATH || '').split(delimiter).filter(Boolean)) {
    const path = join(dir, name);
    try { await access(path, constants.X_OK); return path; } catch {}
  }
  return null;
}

async function claudeAccess() {
  const path = await executable('claude');
  if (!path) return {available:false, connection:'請在橋接主機安裝 Claude Code'};
  try {
    const {stdout} = await exec(path, ['auth','status','--json'], {timeout:3500, maxBuffer:32768});
    if (JSON.parse(stdout).loggedIn === true) {
      return {available:true, connection:'主機 Claude Code 已登入 · 模型權限於呼叫時確認'};
    }
  } catch {}
  return {available:false, connection:'請在主機執行 claude auth login，再重新檢查連線'};
}

async function cliReply(profile, prompt, signal) {
  const claude = profile.runtime === 'claude';
  const name = claude ? 'Claude Code' : 'Gemini CLI';
  const path = await executable(profile.runtime);
  if (!path) throw Error('找不到主機執行檔 '+name);
  const cwd = await mkdtemp(join(tmpdir(), 'stocknexus-arena-'));
  try {
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
      ['PATH','LANG','USER','HTTPS_PROXY','HTTP_PROXY','NO_PROXY','SSL_CERT_FILE'].includes(key)));
    let args;
    if (claude) {
      for (const key of ['HOME','CLAUDE_CONFIG_DIR','ANTHROPIC_API_KEY','CLAUDE_CODE_OAUTH_TOKEN']) {
        if (process.env[key]) env[key] = process.env[key];
      }
      env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1';
      args=['-p','--model',profile.model,'--output-format','json','--tools','','--strict-mcp-config',
        '--mcp-config','{"mcpServers":{}}','--setting-sources','','--disable-slash-commands','--no-session-persistence'];
    } else {
      if (!process.env.GEMINI_API_KEY) throw Error('橋接程序未設定 GEMINI_API_KEY');
      env.HOME=cwd; env.GEMINI_CLI_HOME=join(cwd,'.gemini'); env.GEMINI_API_KEY=process.env.GEMINI_API_KEY;
      env.GEMINI_CLI_SYSTEM_SETTINGS_PATH=join(cwd,'settings.json');
      await writeFile(env.GEMINI_CLI_SYSTEM_SETTINGS_PATH, JSON.stringify({
        security:{auth:{selectedType:'gemini-api-key'}}, hooksConfig:{enabled:false}, model:{maxSessionTurns:1},
        admin:{mcp:{enabled:false},extensions:{enabled:false}}, telemetry:{enabled:false}
      }));
      const policy=join(cwd,'arena.toml');
      await writeFile(policy,'[[rule]]\ntoolName = "*"\ndecision = "deny"\npriority = 999\n');
      args=['--model',profile.model,'--output-format','json','--admin-policy',policy,'-p','Read stdin and return the requested JSON.'];
    }
    const raw=await new Promise((resolve,reject)=>{
      const child=spawn(path,args,{cwd,env,signal,killSignal:'SIGKILL',stdio:['pipe','pipe','ignore']});
      let output='', size=0;
      child.stdout.setEncoding('utf8');
      child.stdout.on('data',chunk=>{
        size+=Buffer.byteLength(chunk);
        if(size>512000)child.kill('SIGKILL');else output+=chunk;
      });
      child.on('error',reject);
      child.stdin.on('error',()=>{});child.stdin.end(prompt);
      child.on('close',code=>{
        if(code!==0)reject(Error(name+' 回合失敗（exit '+code+'），請檢查主機認證、模型與配額'));
        else resolve(output);
      });
    });
    const reply=JSON.parse(raw);
    if(reply.is_error||reply.error)throw Error(name+' 未完成回合，請檢查主機登入與配額');
    if(claude)return {text:reply.result,usage:reply.usage||{}};
    const models=Object.values(reply.stats?.models||{}),usage={};
    for(const {tokens} of models){
      if(Number.isSafeInteger(tokens?.prompt))usage.input_tokens=(usage.input_tokens||0)+tokens.prompt;
      if(Number.isSafeInteger(tokens?.candidates))usage.output_tokens=(usage.output_tokens||0)+tokens.candidates;
    }
    return {text:reply.response,usage};
  } finally {await rm(cwd,{recursive:true,force:true});}
}

export function createArenaAdapters({makeWikiThread,listModels}){
  async function catalog(){
    const [codex,local,claude,gemini]=await Promise.allSettled([
      (async()=>{if(!makeWikiThread||!listModels)throw Error();return (await listModels()).models.map(m=>m.id);})(),
      (async()=>{const r=await fetch(ollama+'/api/tags',{signal:AbortSignal.timeout(2500),redirect:'error'});
        if(!r.ok)throw Error();return (await r.json()).models.map(m=>m.name);})(),
      claudeAccess(),executable('gemini')
    ]);
    return [
      {id:'codex',name:'Codex',available:codex.status==='fulfilled'&&codex.value.length>0,models:codex.value||[],
        connection:'主機 Codex 登入 · npx --no-install codex login'},
      {id:'ollama',name:'Ollama',available:local.status==='fulfilled'&&local.value.length>0,models:local.value||[],
        connection:'主機本地模型 · ollama serve，再以 ollama pull 下載模型'},
      {id:'claude',name:'Claude Code',models:[],manualModel:true,
        ...(claude.value||{available:false,connection:'請在主機檢查 claude auth status'})},
      {id:'gemini',name:'Gemini CLI',available:!!gemini.value&&!!process.env.GEMINI_API_KEY,models:[],manualModel:true,
        connection:'主機 Gemini CLI · 橋接程序需要 GEMINI_API_KEY，支援 --admin-policy 的版本'}
    ];
  }
  async function turn(profile,prompt,signal){
    if(profile.runtime==='codex'){
      const result=await makeWikiThread(profile.model,'low').run(prompt,{signal});
      return {text:result.finalResponse,usage:result.usage||{}};
    }
    if(['claude','gemini'].includes(profile.runtime))return cliReply(profile,prompt,signal);
    if(profile.runtime!=='ollama')throw Error('未知執行環境');
    const r=await fetch(ollama+'/api/chat',{method:'POST',signal,redirect:'error',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({model:profile.model,stream:false,format:'json',options:{num_predict:6144},
        messages:[{role:'user',content:prompt}]})});
    if(!r.ok)throw Error('Ollama HTTP '+r.status);
    const result=await r.json();
    return {text:result.message.content,usage:{input_tokens:result.prompt_eval_count,output_tokens:result.eval_count}};
  }
  return {catalog,turn};
}
