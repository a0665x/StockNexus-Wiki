// Mount the court below the live workbench header. Keep the actual mode buttons and the
// background graphs mounted so returning to a view restores its viewport and selection.
(() => {
  const $=id=>document.getElementById(id);
  const trigger=$('modeArena'), modes=trigger?.parentElement;
  if(!modes)return;
  const shell=document.createElement('section');
  shell.id='arenaPanel';shell.hidden=true;shell.setAttribute('aria-label','Debate Arena');
  const frame=document.createElement('iframe');
  frame.title='Debate Arena 辯論法庭';
  shell.append(frame);document.body.append(shell);
  const anchor=document.createComment('workbench modes');
  modes.before(anchor);
  let active=false,fromWiki=false,sourceUrl='/',loadedStock=null;
  function returnFocus(){(fromWiki?$('wikiArena'):trigger).focus();}
  function fit(){
    if(!active)return;
    const root=document.documentElement;
    const wiki=$('wikiPanel');
    const style=getComputedStyle(fromWiki?wiki:root);
    const left=style.getPropertyValue(fromWiki?'--wiki-left':'--left-width').trim()||'280px';
    const right=style.getPropertyValue(fromWiki?'--wiki-right':'--right-width').trim()||'280px';
    const head=$('workbenchHeader').getBoundingClientRect();
    shell.style.top=head.bottom+'px';
    for(const [name,v] of [['left',left],['right',right]]){
      shell.style.setProperty('--arena-'+name,v);
      frame.contentDocument?.documentElement?.style.setProperty('--arena-'+name,v);
    }
    const tools=$('graphTools').getBoundingClientRect(),compact=innerWidth<=800;
    const stage=$('stage').getBoundingClientRect();
    const margin=Math.max(0,tools.left-stage.left);
    const top=Math.max(4,tools.top-stage.top);
    shell.style.setProperty('--mode-left',compact?'10px':fromWiki?'calc('+left+' + 10px + '+margin+'px)':tools.left+'px');
    shell.style.setProperty('--mode-top',top+'px');
    const row=modes.getBoundingClientRect();
    frame.contentDocument?.documentElement?.style.setProperty('--mode-height',Math.ceil(row.height+top+6)+'px');
  }
  function activate(push=true){
    if(active)return;
    fromWiki=!$('wikiPanel').hidden;
    sourceUrl=location.pathname==='/arena'?(fromWiki?'/#wiki':'/'):location.pathname+location.search+location.hash;
    const ident=new URLSearchParams(location.search).get('instrument')||(fromWiki?($('wikiSaved')?.value||$('wikiInstrument')?.value):'')||window.AtlasWikiContext?.confirmedSearch?.()?.instrument||'';
    if(push){
      if(fromWiki && location.hash!=='#wiki'){sourceUrl='/#wiki';history.replaceState(history.state,'',sourceUrl);}
      history.pushState({arena:true},'', '/arena'+(ident?'?'+new URLSearchParams({instrument:ident}):''));
    }
    active=true;shell.hidden=false;document.body.classList.add('arena-open');
    shell.prepend(modes);
    if(!fromWiki)window.AtlasWikiContext?.visible(true);
    trigger.classList.add('active');trigger.setAttribute('aria-pressed','true');
    for(const b of modes.querySelectorAll('button'))if(b!==trigger){b.dataset.arenaActive=b.classList.contains('active')?'1':'0';b.classList.remove('active');b.setAttribute('aria-pressed','false');}
    if(loadedStock!==ident){loadedStock=ident;frame.src='/arena/court'+(ident?'?'+new URLSearchParams({instrument:ident}):'');}
    fit();
  }
  function leave(dest){
    if(!active)return;
    active=false;shell.hidden=true;document.body.classList.remove('arena-open');
    anchor.after(modes);trigger.classList.remove('active');trigger.setAttribute('aria-pressed','false');
    for(const b of modes.querySelectorAll('[data-arena-active]')){
      const on=b.dataset.arenaActive==='1';b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));delete b.dataset.arenaActive;
    }
    if(!fromWiki)window.AtlasWikiContext?.visible(false);
    if(dest)history.pushState({},'',dest);
  }
  trigger.onclick=()=>activate();
  $('wikiArena').onclick=()=>activate();
  for(const [id,url] of [['modeNetwork','/'],['modeTimeline','/'],['modeWiki','/#wiki']]){
    $(id).addEventListener('click',()=>{
      if(!active)return;leave(url);
      if(id!=='modeWiki'&&!$('wikiPanel').hidden)$('wikiBack').click();
    },true);
  }
  for(const [id,pane] of [['openSearch','library'],['openResults','sources']]){
    $(id).addEventListener('click',e=>{
      if(!active)return;e.stopImmediatePropagation();frame.contentWindow?.postMessage({arenaPane:pane},location.origin);
    },true);
  }
  $('relationOpen').addEventListener('click',()=>{if(active)leave(sourceUrl);},true);
  window.addEventListener('message',e=>{
    if(!active||e.origin!==location.origin||e.source!==frame.contentWindow||typeof e.data?.arenaStock!=='string')return;
    loadedStock=e.data.arenaStock;
    history.replaceState({arena:true},'', '/arena'+(loadedStock?'?'+new URLSearchParams({instrument:loadedStock}):''));
  });
  frame.addEventListener('load',fit);
  if(window.ResizeObserver){const observer=new ResizeObserver(fit);observer.observe($('workbenchHeader'));observer.observe(modes);}
  shell.addEventListener('keydown',e=>{if(e.key==='Escape' && e.target!==frame){leave(sourceUrl);returnFocus();}});
  window.addEventListener('resize',fit);
  window.addEventListener('popstate',()=>{
    if(location.pathname==='/arena')activate(false);
    else if(active){
      leave();
      if(location.hash==='#wiki')$('modeWiki').click();
      else if(!$('wikiPanel').hidden)$('wikiBack').click();
    }
  });
  if(location.pathname==='/arena')activate(false);
})();
