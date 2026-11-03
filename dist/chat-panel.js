'use strict';
(() => {
 const runtime=globalThis.AtlasRuntime;if(!runtime)return;
 const detail=document.getElementById('detail');if(!detail)return;
 const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
 const tabs=make('div',null,'detail-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','右側內容');
 const newsTab=make('button','新聞詳情'),chatTab=make('button','Chat Agent');
 for(const [b,id] of [[newsTab,'news'],[chatTab,'chat']]){b.type='button';b.id=id+'Tab';b.setAttribute('role','tab');b.setAttribute('aria-controls',id+'Page');tabs.append(b);}
 const deck=make('div',null,'detail-deck'),news=make('section',null,'detail-page'),chat=make('section',null,'detail-page');news.id='newsPage';chat.id='chatPage';
 for(const [p,id] of [[news,'news'],[chat,'chat']]){p.setAttribute('role','tabpanel');p.setAttribute('aria-labelledby',id+'Tab');}
 while(detail.firstChild)news.append(detail.firstChild);deck.append(news,chat);detail.append(tabs,deck);detail.classList.add('chat-ready');
 const toolbar=make('div',null,'chat-toolbar'),fresh=make('button','新對話'),stop=make('button','停止'),context=make('div',null,'chat-context'),messages=make('div',null,'chat-messages'),status=make('div','開啟 Chat 後連線。','chat-status'),form=make('form',null,'chat-compose'),input=make('textarea'),send=make('button','傳送');
 input.placeholder='整理我選取的新聞，或幫我調整畫面…';input.setAttribute('aria-label','向新聞助理提問');input.maxLength=24000;send.type='submit';fresh.type=stop.type='button';stop.disabled=true;toolbar.append(fresh,stop);form.append(input,send);status.setAttribute('role','status');status.setAttribute('aria-live','polite');chat.append(toolbar,context,messages,status,form);
 let visible=false,busy=false,session=null,connecting=null,lastData=null,syncing=false,timer=null,stopping=false;
 globalThis.AtlasChat={active:()=>visible||busy};
 function setTab(show){visible=show;deck.classList.toggle('chat-visible',show);news.inert=show;chat.inert=!show;news.setAttribute('aria-hidden',String(show));chat.setAttribute('aria-hidden',String(!show));newsTab.setAttribute('aria-selected',String(!show));chatTab.setAttribute('aria-selected',String(show));newsTab.tabIndex=show?-1:0;chatTab.tabIndex=show?0:-1;if(show){detail.classList.add('open');connect().then(()=>sync()).catch(e=>status.textContent=e.message);}}
 newsTab.onclick=()=>setTab(false);chatTab.onclick=()=>setTab(true);tabs.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setTab(!visible);(visible?chatTab:newsTab).focus();}};setTab(false);
 async function request(path,payload){const r=await fetch('/api/chat/'+path,{method:'POST',headers:{'Content-Type':'application/json',...(session?{Authorization:'Bearer '+session}:{})},body:JSON.stringify(payload)});if(!r.ok){let b={};try{b=await r.json();}catch{}if(r.status===401){session=null;lastData=null;}throw Error(b.error||'Chat 連線失敗 ('+r.status+')');}return r;}
 async function connect(){if(session)return;if(connecting)return connecting;connecting=(async()=>{session=(await(await request('session',{})).json()).token;status.textContent='已連線 · 使用本機登入';lastData=null;})();try{await connecting;}finally{connecting=null;}}
 function payload(ack){const state=runtime.state();context.textContent=`目前範圍：${state.scope_kind==='category'?'分類':state.scope_kind==='roots_and_relations'?'Roots 與關聯':state.scope_kind==='article'?'選定新聞':'目前結果'} · ${state.counts.scope} 篇 · ${state.view_mode==='network'?'3D':'時間軸'}\n每次提問跟隨目前選取；回答期間可繼續操作。`;const p={context:state};if(lastData!==state.dataset){p.graph=runtime.data();}if(ack)p.ack=ack;return p;}
 async function sync(){if(!session||syncing)return;syncing=true;try{
  let p=payload(),result=await(await request('sync',p)).json();if(p.graph)lastData=p.context.dataset;
  let commands=result.commands;
  while(commands?.length){const next=[];for(const cmd of commands){let ack={id:cmd.commandId};try{if(stopping)throw Error('已停止操作');await runtime.act(cmd);}catch(e){ack.error=e.message;}p=payload(ack);result=await(await request('sync',p)).json();if(p.graph)lastData=p.context.dataset;next.push(...result.commands);}commands=next;}
 }catch(e){status.textContent=e.message;}finally{syncing=false;}}
 timer=setInterval(()=>{if(visible||busy)sync();},700);
 function message(text,role){const node=make('div',null,'chat-message raw '+role),content=make('div');const pattern=/\[([^\]\n]+)\]\((https?:\/\/[^\s<>]+?)\)|https?:\/\/[^\s<>\])]+/g;let last=0;for(const match of text.matchAll(pattern)){content.append(document.createTextNode(text.slice(last,match.index)));const href=match[2]||match[0];const a=make('a',match[1]||(href.length>80?'來源原文 ↗':href));a.href=href;a.target='_blank';a.rel='noopener noreferrer';content.append(a);last=match.index+match[0].length;}content.append(document.createTextNode(text.slice(last)));node.append(content);if(role==='assistant'){const copy=make('button',AtlasI18n.t('複製'));copy.dataset.copyLabel='複製';copy.onclick=async()=>{try{await navigator.clipboard.writeText(text);copy.dataset.copyLabel='已複製';copy.textContent=AtlasI18n.t('已複製');}catch{copy.dataset.copyLabel='複製失敗，請選取文字';copy.textContent=AtlasI18n.t('複製失敗，請選取文字');}};node.append(copy);}messages.append(node);messages.scrollTop=messages.scrollHeight;return node;}
 form.onsubmit=async e=>{e.preventDefault();if(busy||!input.value.trim())return;const text=input.value.trim();busy=true;stopping=false;send.disabled=true;stop.disabled=false;fresh.disabled=true;input.value='';message(text,'user');status.textContent='正在連線…';
  try{await connect();while(syncing)await new Promise(r=>setTimeout(r,30));await sync();if(stopping)throw Error('已停止回覆。');const response=await request('turn',{message:text}),reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',ended=false;
   while(true){const {done,value}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});let i;while((i=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);if(!line.trim())continue;const event=JSON.parse(line);if(event.type==='message')message(event.text,'assistant');if(event.type==='status')status.textContent=event.message;if(event.type==='error'){ended=true;throw Error(event.message);}if(event.type==='done'){ended=true;status.textContent=event.cancelled?'已停止回覆':'回覆完成';}}if(done)break;}
   if(!ended)throw Error('連線中斷，回覆可能未完成。');
  }catch(e){status.textContent=e.message;}finally{busy=false;send.disabled=false;stop.disabled=true;fresh.disabled=false;}
 };
 input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();form.requestSubmit();}e.stopPropagation();};
 stop.onclick=async()=>{stopping=true;stop.disabled=true;try{if(session)await request('cancel',{});status.textContent='正在停止…';}catch(e){status.textContent=e.message;}};
 fresh.onclick=async()=>{try{await connect();await request('reset',{});messages.replaceChildren();status.textContent='已開始新對話';}catch(e){status.textContent=e.message;}};
 function refreshLanguage(){input.placeholder=AtlasI18n.t('整理我選取的新聞，或幫我調整畫面…');input.setAttribute('aria-label',AtlasI18n.t('向新聞助理提問'));for(const b of messages.querySelectorAll('button'))b.textContent=AtlasI18n.t(b.dataset.copyLabel||'複製');}
 globalThis.addEventListener('atlas-language',refreshLanguage);refreshLanguage();
globalThis.AtlasDock?.init();
})();
