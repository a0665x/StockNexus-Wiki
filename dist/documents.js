/* Document sources are read from SQLite independently of market feeds. */
(() => {
  const byId = id => document.getElementById(id);
  const picker = byId('documentCollection');
  if (!picker) return;
  const launcher = byId('documentLauncher');
  const choices = byId('documentChoices');
  const params = new URLSearchParams(location.search);
  const nodeKey = (source,id) => source + '/' + id;
  const key = node => nodeKey(node.source,node.id);
  const make = (tag,text) => {
    const elem = document.createElement(tag);
    if (text !== undefined) elem.textContent = text;
    return elem;
  };
  async function read(parameters) {
    const response = await fetch('/api/documents?' + new URLSearchParams(parameters));
    const payload = await response.json();
    if (!response.ok) throw Error(payload.error || String(response.status));
    return payload;
  }
  let collections = [], nodes = [], graph, selected, reading = 0, loadTicket = 0;
  let catalogTicket = 0, catalogSignature;
  function fail(error) {
    (byId('counts') || choices).textContent = error.message;
  }
  function listChoices(enabled) {
    choices.replaceChildren();
    const collection = collections.find(item => item.id === picker.value);
    for (const [source,count] of Object.entries(collection?.sources || {})) {
      const box = make('input'), label = make('label');
      box.type = 'checkbox'; box.value = source; box.checked = enabled.has(source);
      box.onchange = () => {
        if (launcher) {
          if (box.checked) {
            box.checked = false;
            location.assign('/documents?' + new URLSearchParams({collection:picker.value,source}));
          }
        } else render();
      };
      label.append(box,document.createTextNode(' '+source+' ('+count+')'));
      choices.append(label);
    }
  }
  function clearDetails() {
    selected = null; ++reading;
    byId('details').replaceChildren(make('h2','節點詳情'),make('p','點選目錄或圖上的節點。'));
  }
  function show(node) {
    selected = key(node);
    const ticket = ++reading, panel = byId('details');
    let current = node;
    const index = new Map(nodes.map(n => [key(n),n]));
    while (!current.path && current.parent_id && index.has(nodeKey(current.source,current.parent_id))) {
      current = index.get(nodeKey(current.source,current.parent_id));
    }
    panel.replaceChildren(make('h2',node.title), make('p',[node.source,node.kind,node.layer,'v'+node.revision].filter(Boolean).join(' · ')));
    panel.append(make('p', [current.path,node.locator?.heading,node.locator?.page && 'p. '+node.locator.page,
      node.locator?.line && 'L'+node.locator.line].filter(Boolean).join(' · ')),
      make('p',node.published_at || '日期未知'));
    if (node.question) panel.append(make('p',node.question));
    if (node.text) panel.append(make('pre',node.text));
    for (const link of node.links || []) {
      const source = link.source || node.source;
      const target = index.get(nodeKey(source,link.id));
      const button = make('button', link.type+' → '+(target?.title || link.id)+(link.revision?' · v'+link.revision:''));
      button.onclick = async () => {
        if (!link.revision) { if (target) show(target); return; }
        try {
          const result = await read({collection:picker.value,source,id:link.id,revision:link.revision});
          if (ticket===reading) show({...result.record,source,revision:result.revision});
        } catch(error) { if(ticket===reading) fail(error); }
      };
      panel.append(button);
      if (link.rationale) panel.append(make('p', '關聯依據：' + link.rationale));
    }
  }
  function render() {
    const enabled = new Set([...choices.querySelectorAll('input:checked')].map(el => el.value));
    const layer = byId('layers').value;
    const visible = nodes.filter(n => enabled.has(n.source) && (!layer || (layer==='documents'?!n.layer:n.layer===layer)));
    const ids = new Set(visible.map(key)), children = new Map(), edges = [];
    if (!ids.has(selected)) clearDetails();
    for (const n of visible) {
      const parent = nodeKey(n.source,n.parent_id);
      const group = n.parent_id && ids.has(parent) ? parent : '';
      if (!children.has(group)) children.set(group,[]);
      children.get(group).push(n);
      if (group) edges.push({source:group,target:key(n),type:'contains'});
      for (const l of n.links || []) {
        const target = nodeKey(l.source || n.source,l.id);
        if (ids.has(target)) edges.push({source:key(n),target,type:l.type});
      }
    }
    const outline = byId('outline');
    outline.replaceChildren();
    function entries(parent,container) {
      for (const n of children.get(parent) || []) {
        const button = make('button',n.title); button.type='button'; button.className='entry';
        button.onclick=() => show(n);
        if (!children.has(key(n))) { container.append(button); continue; }
        const branch=make('details'), summary=make('summary'), content=make('div');
        summary.append(button); branch.append(summary,content); container.append(branch);
        // Build a subtree on first expansion so large manuals can open immediately.
        branch.ontoggle=() => { if(branch.open&&!content.childElementCount) entries(key(n),content); };
        button.onclick=e => { e.preventDefault(); show(n); branch.open=!branch.open; };
      }
    }
    entries('',outline);
    byId('counts').textContent=visible.length+' 節點 · '+edges.length+' 關係'+(graph?'':' · 3D 無法使用，可從目錄瀏覽');
    if (graph) graph.graphData({nodes:visible.map(n=>({id:key(n),record:n})),links:edges});
  }
  async function load(requested) {
    const ticket=++loadTicket;
    const sources=Object.keys(collections.find(c=>c.id===picker.value)?.sources || {});
    listChoices(new Set(launcher ? [] : requested ?? sources));
    if (launcher) return;
    clearDetails(); nodes=[]; render();
    if (!picker.value) return;
    const result = await read({collection:picker.value});
    if(ticket!==loadTicket) return;
    nodes=result.nodes; render();
  }
  async function refresh(force=false, imported=null) {
    const ticket=++catalogTicket;
    const result=await read({});
    if(ticket!==catalogTicket) return;
    const next=JSON.stringify(result.collections);
    if(next===catalogSignature && !force) return;
    const old=picker.value;
    const previous=[...choices.querySelectorAll('input:checked')].map(box=>box.value);
    catalogSignature=next; collections=result.collections;
    picker.replaceChildren(...collections.map(c=>new Option(c.id,c.id)));
    const desired = imported?.collection || old || params.get('collection');
    if (collections.some(c=>c.id===desired)) picker.value=desired;
    if (launcher) launcher.hidden=!collections.length;
    await load(imported ? [imported.source] : old===picker.value && old ? previous : params.has('source')?[params.get('source')]:undefined);
  }
  picker.onchange=()=>load().catch(fail);
  if (!launcher) {
    const form = byId('importDocuments');
    const status = byId('importStatus');
    form.onsubmit = async event => {
      event.preventDefault();
      if (form.ariaBusy === 'true') return;
      const file = form.elements.records.files[0];
      if (!file) return;
      const mode = event.submitter?.value || 'apply';
      const collection = form.elements.collection.value;
      const source = form.elements.source.value;
      const buttons = form.querySelectorAll('button');
      form.ariaBusy = 'true';
      buttons.forEach(button => { button.disabled = true; });
      status.textContent = mode === 'preview' ? '預覽中…' : '匯入中…';
      try {
        const query = new URLSearchParams({collection, source, mode});
        const response = await fetch('/api/documents/import?' + query, {
          method:'POST', headers:{'Content-Type':'application/x-ndjson'}, body:file
        });
        const result = await response.json();
        if (!response.ok) throw Error(result.error || String(response.status));
        const action = result.dry_run ? '預覽（未寫入）' : '已匯入';
        status.textContent = action + ' · 新增 ' + result.added + ' · 更新 ' + result.updated +
          ' · 未變更 ' + result.unchanged + ' · 重複列 ' + result.duplicate_lines;
        if (!result.dry_run) {
          try {
            await refresh(true, {collection, source});
            history.replaceState(null, '', '/documents?' + new URLSearchParams({collection,source}));
          } catch (error) {
            status.textContent += '。讀取圖譜失敗，請重新讀取 DB。' + error.message;
          }
        }
      } catch (error) {
        status.textContent = error.message;
      } finally {
        form.ariaBusy = 'false';
        buttons.forEach(button => { button.disabled = false; });
      }
    };
    byId('layers').onchange=render;
    byId('refreshDocuments').onclick=()=>refresh(true).catch(fail);
    const canvas=byId('docGraph');
    try {
      graph=ForceGraph3D()(canvas).backgroundColor('#0b1420').nodeLabel(n=>n.record.title.replace(/[&<>"']/g,c=>'&#'+c.charCodeAt(0)+';'))
        .nodeAutoColorBy(n=>n.record.layer || n.record.source).linkDirectionalArrowLength(3)
        .linkColor(l=>l.type==='contains'?'#5d8498':l.type==='contradicts'?'#fa8292':'#6ddbc2')
        .linkLabel('type').onNodeClick(n=>show(n.record));
      const resize=()=>graph.width(canvas.clientWidth).height(canvas.clientHeight);
      new ResizeObserver(resize).observe(canvas); resize();
    } catch { graph=null; }
  }
  refresh().catch(fail);
  if (launcher) {
    window.addEventListener('pageshow',()=>refresh().catch(fail));
    document.addEventListener('visibilitychange',()=>{if(!document.hidden) refresh().catch(fail);});
    window.setInterval(()=>{if(!document.hidden) refresh().catch(fail);},10000);
  }
})();
