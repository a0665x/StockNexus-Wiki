'use strict';
(() => {
 function mount({runtime,detail,prefix='',title='新聞詳情'}){if(!runtime||!detail)return null;
 const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
 const tr=text=>AtlasI18n.t(text),format=(text,values)=>AtlasI18n.format(text,values);
 const tabs=make('div',null,'detail-tabs');tabs.dataset.ownI18n='';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','右側內容');
 const newsTab=make('button',title),chatTab=make('button','Chat Agent');
 for(const [b,id] of [[newsTab,'news'],[chatTab,'chat']]){b.type='button';b.id=prefix+id+'Tab';b.setAttribute('role','tab');b.setAttribute('aria-controls',prefix+id+'Page');tabs.append(b);}
 const deck=make('div',null,'detail-deck'),news=make('section',null,'detail-page'),chat=make('section',null,'detail-page');news.id=prefix+'newsPage';chat.id=prefix+'chatPage';chat.dataset.ownI18n='';
 for(const [p,id] of [[news,'news'],[chat,'chat']]){p.setAttribute('role','tabpanel');p.setAttribute('aria-labelledby',prefix+id+'Tab');}
 while(detail.firstChild)news.append(detail.firstChild);deck.append(news,chat);detail.append(tabs,deck);detail.classList.add('chat-ready');
 const toolbar=make('div',null,'chat-toolbar'),fresh=make('button','新對話'),stop=make('button','停止'),context=make('div',null,'chat-context'),messages=make('div',null,'chat-messages'),status=make('div','開啟 Chat 後連線。','chat-status'),form=make('form',null,'chat-compose'),input=make('textarea'),send=make('button',null,'chat-send');
 input.placeholder='整理我選取的新聞，或幫我調整畫面…';input.setAttribute('aria-label','向新聞助理提問');input.maxLength=24000;send.type='submit';send.disabled=true;send.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m21 3-6.5 18-4-7.5L3 9.5 21 3Z M10.5 13.5 21 3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';fresh.type=stop.type='button';stop.disabled=true;toolbar.append(fresh,stop);form.append(input,send);status.setAttribute('role','status');status.setAttribute('aria-live','polite');chat.append(toolbar,context,messages,status,form);
 let statusState={source:'開啟 Chat 後連線。',values:{}},sourceLinks=[];
 function renderStatus(){status.textContent=format(statusState.source,statusState.values);}
 function setStatus(source,values={}){statusState={source,values};renderStatus();}
 function showError(error){const source=String(error.message||error);if(source==='Session expired; start a new chat.')setStatus('對話連線已失效，請重新開啟 Chat。');else if(source.startsWith('回覆失敗：'))setStatus('回覆失敗：{detail}',{detail:source.slice(5)});else if(/^Chat 連線失敗 \(\d+\)$/.test(source))setStatus('Chat 連線失敗 ({code})',{code:source.match(/\d+/)[0]});else setStatus(source==='已停止回覆。'?'已停止回覆':source);}
 function renderContext(state=runtime.state()){context.textContent=state.surface==='wiki'?format('Wiki {instrument} · v{version} · {count} 個節點\n依目前選取與日期討論觀點；論述與引用可由工具讀取。',{instrument:state.instrument+' · '+(state.layer||'L1'),version:state.version,count:state.counts.scope})+(state.selected_node?'\n'+(state.selected_node.layer||'L1')+' · '+state.selected_node.title:'')+(state.research_question?'\n'+state.research_question:''):format('目前範圍：{scope} · {count} 篇 · {view}\n每次提問跟隨目前選取；回答期間可繼續操作。',{scope:tr(state.scope_kind==='category'?'分類':state.scope_kind==='roots_and_relations'?'Roots 與關聯':state.scope_kind==='article'?'選定新聞':'目前結果'),count:state.counts.scope,view:tr(state.view_mode==='network'?'3D':'時間軸')});}
 let visible=false,busy=false,session=null,connecting=null,lastData=null,syncing=false,timer=null,stopping=false;
 const api={active:()=>visible||busy};
 function setTab(show){visible=show;deck.classList.toggle('chat-visible',show);news.inert=show;chat.inert=!show;news.setAttribute('aria-hidden',String(show));chat.setAttribute('aria-hidden',String(!show));newsTab.setAttribute('aria-selected',String(!show));chatTab.setAttribute('aria-selected',String(show));newsTab.tabIndex=show?-1:0;chatTab.tabIndex=show?0:-1;if(show){detail.classList.add('open');connect().then(()=>sync()).catch(showError);}}
 newsTab.onclick=()=>setTab(false);chatTab.onclick=()=>setTab(true);tabs.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setTab(!visible);(visible?chatTab:newsTab).focus();}};setTab(false);
 async function request(path,payload){const r=await fetch('/api/chat/'+path,{method:'POST',headers:{'Content-Type':'application/json',...(session?{Authorization:'Bearer '+session}:{})},body:JSON.stringify(payload)});if(!r.ok){let b={};try{b=await r.json();}catch{}if(r.status===401){session=null;lastData=null;}throw Error(b.error||'Chat 連線失敗 ('+r.status+')');}return r;}
 async function connect(){if(session)return;if(connecting)return connecting;connecting=(async()=>{session=(await(await request('session',{})).json()).token;setStatus('已連線 · 使用本機登入');lastData=null;})();try{await connecting;}finally{connecting=null;}}
 function payload(ack){const state=runtime.state();renderContext(state);const p={context:state};if(lastData!==state.dataset){p.graph=runtime.data();}if(ack)p.ack=ack;return p;}
 async function sync(){if(!session||syncing)return;syncing=true;try{
  let p=payload(),result=await(await request('sync',p)).json();if(p.graph)lastData=p.context.dataset;
  let commands=result.commands;
  while(commands?.length){const next=[];for(const cmd of commands){let ack={id:cmd.commandId};try{if(stopping)throw Error('已停止操作');await runtime.act(cmd);}catch(e){ack.error=e.message;}p=payload(ack);result=await(await request('sync',p)).json();if(p.graph)lastData=p.context.dataset;next.push(...result.commands);}commands=next;}
 }catch(e){showError(e);}finally{syncing=false;}}
 timer=setInterval(()=>{if(visible||busy)sync();},700);
 function message(text,role){const node=make('div',null,'chat-message raw '+role),content=make('div');const pattern=/\[([^\]\n]+)\]\((https?:\/\/[^\s<>]+?)\)|https?:\/\/[^\s<>\])]+/g;let last=0;for(const match of text.matchAll(pattern)){content.append(document.createTextNode(text.slice(last,match.index)));const href=match[2]||match[0];const a=make('a',match[1]||(href.length>80?tr('來源原文 ↗'):href));a.href=href;a.target='_blank';a.rel='noopener noreferrer';if(!match[1]&&href.length>80)sourceLinks.push(a);content.append(a);last=match.index+match[0].length;}content.append(document.createTextNode(text.slice(last)));node.append(content);messages.append(node);messages.scrollTop=messages.scrollHeight;return node;}
 form.onsubmit=async e=>{e.preventDefault();if(busy||!input.value.trim())return;const text=input.value.trim();busy=true;stopping=false;send.disabled=true;stop.disabled=false;fresh.disabled=true;input.value='';message(text,'user');setStatus('正在連線…');
  try{await connect();while(syncing)await new Promise(r=>setTimeout(r,30));await sync();if(stopping)throw Error('已停止回覆。');const response=await request('turn',{message:text}),reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',ended=false;
   while(true){const {done,value}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});let i;while((i=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);if(!line.trim())continue;const event=JSON.parse(line);if(event.type==='message')message(event.text,'assistant');if(event.type==='status')setStatus(event.message);if(event.type==='error'){ended=true;throw Error(event.message);}if(event.type==='done'){ended=true;setStatus(event.cancelled?'已停止回覆':'回覆完成');}}if(done)break;}
   if(!ended)throw Error('連線中斷，回覆可能未完成。');
  }catch(e){showError(e);}finally{busy=false;send.disabled=!input.value.trim();stop.disabled=true;fresh.disabled=false;}
 };
 input.oninput=()=>{send.disabled=busy||!input.value.trim();};
 input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();form.requestSubmit();}e.stopPropagation();};
 stop.onclick=async()=>{stopping=true;stop.disabled=true;setStatus('正在停止…');try{if(session)await request('cancel',{});}catch(e){if(busy&&stopping)showError(e);}};
 fresh.onclick=async()=>{try{await connect();await request('reset',{});messages.replaceChildren();sourceLinks=[];setStatus('已開始新對話');}catch(e){showError(e);}};
 function refreshLanguage(){newsTab.textContent=tr(title);tabs.setAttribute('aria-label',tr('右側內容'));renderStatus();renderContext();for(const link of sourceLinks)link.textContent=tr('來源原文 ↗');fresh.textContent=AtlasI18n.t('新對話');stop.textContent=AtlasI18n.t('停止');send.setAttribute('aria-label',AtlasI18n.t('傳送'));send.title=AtlasI18n.t('傳送');input.placeholder=AtlasI18n.t(prefix?'分析目前觀點、引用與關聯…':'整理我選取的新聞，或幫我調整畫面…');input.setAttribute('aria-label',AtlasI18n.t(prefix?'向 Wiki 助理提問':'向新聞助理提問'));}
 globalThis.addEventListener('atlas-language',refreshLanguage);refreshLanguage();
return api;
 }
 globalThis.AtlasChatPanel={mount};
 globalThis.AtlasChat=mount({runtime:globalThis.AtlasRuntime,detail:document.getElementById('detail')});
 globalThis.AtlasDock?.init();
})();
