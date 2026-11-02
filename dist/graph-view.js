/* Pure view selection: no network calls, no relation inference in the browser. */
(function (root) {
  const providers = ['google', 'yahoo', 'massive'];
  const pair = edge => [edge.source, edge.target].sort().join(':');
  function groups(payload) {
    if (payload.source_graphs) return payload.source_graphs;
    const out = {};
    for (const p of providers) {
      const articles = (payload.articles || []).filter(a => a.source.provider === p);
      const ids = new Set(articles.map(a => a.id));
      out[p] = { articles, relations: (payload.relations || []).filter(r => ids.has(r.source) && ids.has(r.target)), total_articles: articles.length };
    }
    return out;
  }
  function select(payload, selected, separate = false) {
    const sourceGraphs = groups(payload), available = selected.filter(p => sourceGraphs[p]);
    const picked = Object.fromEntries(available.map(p => [p,sourceGraphs[p].articles]));
    const nodes = new Map(), edges = new Map();
    for (const p of available) {
      const ids = new Set(picked[p].map(a => a.id));
      for (const a of picked[p]) {
        const id = separate ? `${p}::${a.id}` : a.id;
        if (!nodes.has(id)) nodes.set(id, { ...a, id, article_id: a.id, display_provider: p, display_sources: [p] });
        else {
          const existing=nodes.get(id);existing.display_sources.push(p);
          existing.symbols=[...new Set([...(existing.symbols||[]),...(a.symbols||[])])];
          const entities=new Map((existing.entities||[]).map(e=>[e.id,e]));
          for(const e of a.entities||[])if(!entities.has(e.id)||e.method==='provider_ticker')entities.set(e.id,e);
          existing.entities=[...entities.values()];
          const channels=new Map((existing.channels||[]).map(c=>[c.id,c]));
          for(const c of a.channels||[])if(!channels.has(c.id)||c.score>channels.get(c.id).score)channels.set(c.id,c);
          existing.channels=[...channels.values()].sort((a,b)=>b.score-a.score);
          existing.primary_channel=existing.channels[0]?.id || 'other';
          existing.origins=[...new Map([...(existing.origins||[existing.source]),...(a.origins||[a.source])].map(origin=>[JSON.stringify(origin),origin])).values()];
        }
      }
      for (const r of sourceGraphs[p].relations || []) {
        if (!ids.has(r.source) || !ids.has(r.target)) continue;
        const key = separate ? `${p}:${pair(r)}` : pair(r);
        if (!edges.has(key)) edges.set(key, { ...r, id: key, raw_relation: r, scope: p, source_relations:[{provider:p,relation:r}],
          source: separate ? `${p}::${r.source}` : r.source, target: separate ? `${p}::${r.target}` : r.target });
        else edges.get(key).source_relations.push({provider:p,relation:r});
      }
    }
    if (!separate) {
      for (const r of payload.cross_relations || payload.relations || []) {
        if (r.cross_sources && !r.cross_sources.every(p=>selected.includes(p))) continue;
        if (!nodes.has(r.source) || !nodes.has(r.target) || edges.has(pair(r))) continue;
        edges.set(pair(r), { ...r, id: pair(r), raw_relation: r, scope: 'cross' });
      }
    }
    return { articles: [...nodes.values()], relations: [...edges.values()], counts: Object.fromEntries(available.map(p => [p, picked[p].length])) };
  }
  function snapshot(payload, view, selected, separate, search, positions = []) {
    const sourceGraphs = groups(payload), out = {};
    for (const p of selected) {
      const visible = new Set(view.articles.filter(a => a.display_sources.includes(p)).map(a => a.article_id));
      out[p] = { articles: (sourceGraphs[p]?.articles || []).filter(a => visible.has(a.id)),
        relations: view.relations.flatMap(r => (r.source_relations || (r.scope===p?[{provider:p,relation:r.raw_relation}]:[])).filter(item=>item.provider===p).map(item=>item.relation)) };
    }
    return { search, view: { sources: selected, separate, positions }, source_graphs: out,
      cross_relations: view.relations.filter(r => r.scope === 'cross').map(r => r.raw_relation) };
  }
  function linkStyle(edge, measuredLength) {
    const cross=edge.scope==='cross';
    const fallback=edge.type==='shared_entity'?45:80;
    return {distance:cross?Math.max(120,fallback*2):Number.isFinite(measuredLength)?Math.max(10,Math.min(1000,measuredLength)):fallback,strength:cross?.025:.14};
  }
  const DEFAULT_SETTINGS={internalMin:0,crossMin:0,depth:2,branchLimit:4,pathMin:.25,maxNodes:150};
  function settings(value={}) {
    const out={};for(const [k,min,max,integer] of [['internalMin',0,1],['crossMin',0,1],['depth',1,6,true],['branchLimit',1,12,true],['pathMin',0,1],['maxNodes',1,150,true]]){
      const n=Number(value[k]);out[k]=Number.isFinite(n)&&value[k]!==undefined?Math.max(min,Math.min(max,integer?Math.round(n):n)):DEFAULT_SETTINGS[k];
    }return out;
  }
  const endpoint=value=>typeof value==='object'?value.id:value;
  const identity=e=>e.id||[endpoint(e.source),endpoint(e.target)].sort().join(':');
  function filterEdges(edges,options={}) {const cfg=settings(options);return edges.filter(e=>(Number(e.weight)||0)>=(e.scope==='cross'?cfg.crossMin:cfg.internalMin));}
  // Breadth-first expansion, deterministic strongest branches first. Scores multiply along a path;
  // these are heuristic display scores, not probabilities or causal attribution.
  function trace(edges,rootId,options={},barriers=new Set()) {
    const cfg=settings(options),nodes=new Map(),chosen=new Set(),adj=new Map();
    if(rootId==null)return {nodes,edges:chosen,truncated:false};
    for(const edge of edges){const a=endpoint(edge.source),b=endpoint(edge.target);for(const [from,to] of [[a,b],[b,a]]){if(!adj.has(from))adj.set(from,[]);adj.get(from).push({to,edge});}}
    for(const list of adj.values())list.sort((a,b)=>(b.edge.weight||0)-(a.edge.weight||0)||identity(a.edge).localeCompare(identity(b.edge)));
    nodes.set(rootId,{depth:0,strength:1,parent:null});let frontier=[rootId],truncated=false;
    for(let depth=1;depth<=cfg.depth&&frontier.length;depth++){
      const next=[];
      frontier.sort((a,b)=>nodes.get(b).strength-nodes.get(a).strength||String(a).localeCompare(String(b)));
      for(const id of frontier){let branches=0;for(const {to,edge} of adj.get(id)||[]){
        const strength=nodes.get(id).strength*Math.max(0,Math.min(1,Number(edge.weight)||0));
        if(strength<cfg.pathMin||nodes.has(to)||barriers.has(to))continue;
        if(branches>=cfg.branchLimit){truncated=true;break;}
        if(nodes.size>=cfg.maxNodes){truncated=true;break;}
        nodes.set(to,{depth,strength,parent:id,edge:identity(edge)});chosen.add(identity(edge));next.push(to);branches++;
      }}frontier=next;
    }return {nodes,edges:chosen,truncated};
  }
  function traceMany(edges,roots,options={}) {
    roots=[...new Set(roots)].slice(0,10);const nodes=new Map(),chosen=new Set(),trees=[];
    for(const root of roots){const tree=trace(edges,root,options,new Set(roots.filter(id=>id!==root)));trees.push({root,...tree});
      for(const [id,hit] of tree.nodes){const old=nodes.get(id),memberships=[...(old?.memberships||[]),root],parents=[...(old?.parents||[]),...(hit.parent==null?[]:[hit.parent])];nodes.set(id,{...(!old||hit.depth<old.depth?hit:old),memberships,parents:[...new Set(parents)]});}
      for(const id of tree.edges)chosen.add(id);
    }return {nodes,edges:chosen,roots,trees,truncated:trees.some(t=>t.truncated)};
  }
  // Pure runtime lookup: never fetch, navigate, filter nodes, or mutate the graph.
  function rankRoots(rows,query,limit=3){
    const terms=[...new Set(String(query).normalize('NFKC').toLowerCase().match(/[\p{L}\p{N}_.^-]+/gu)||[])].slice(0,20),matches=[];
    for(const row of rows){
      const fields={title:row.title||'',summary:row.summary||'',symbols:(row.symbols||[]).join(' '),entities:(row.entities||[]).map(x=>(x.id||'')+' '+(x.label||'')).join(' '),topics:(row.topics||[]).map(x=>x.label||'').join(' '),channels:(row.channels||[]).map(x=>x.name||'').join(' ')};
      let score=0;const evidence=[];
      for(const [field,value]of Object.entries(fields))for(const term of terms){
        const escaped=term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),ascii=/^[\x00-\x7f]+$/.test(term),prefix=/^[a-z]{4,}$/i.test(term)&&!['symbols','entities'].includes(field),pattern=ascii?'(?<![A-Za-z0-9_])'+escaped+(prefix?'[A-Za-z]*':'')+'(?![A-Za-z0-9_])':escaped;
        const hit=String(value).normalize('NFKC').match(new RegExp(pattern,'i'));if(!hit)continue;
        const weight={title:8,summary:2,symbols:10,entities:6,topics:3,channels:3}[field];score+=weight;evidence.push({field,term,match:hit[0],score:weight});
      }
      if(score)matches.push({id:row.id,title:row.title,score,evidence});
    }
    matches.sort((a,b)=>b.score-a.score||(a.id<b.id?-1:a.id>b.id?1:0));
    return {roots:matches.slice(0,Math.max(1,Math.min(10,Number(limit)||3))),matched_articles:matches.length,scanned_articles:rows.length};
  }
  // GPU budget only: never mutate the complete search/export payload.
  function renderSlice(view, limit=800, priority=[]) {
    limit=Math.max(100,Math.min(2400,Number(limit)||800));
    const rank=new Map(priority.map((id,i)=>[id,i]));
    const ordered=view.articles.slice().sort((a,b)=>
      (rank.get(a.id)??Infinity)-(rank.get(b.id)??Infinity)||
      String(b.published_at||'').localeCompare(String(a.published_at||''))||String(a.id).localeCompare(String(b.id)));
    const articles=ordered.slice(0,limit),ids=new Set(articles.map(a=>a.id));
    const relations=view.relations.filter(e=>ids.has(endpoint(e.source))&&ids.has(endpoint(e.target))).slice(0,limit*3);
    return {articles,relations};
  }
  const api = { select, snapshot, groups, linkStyle, settings, filterEdges, trace, traceMany, rankRoots, identity, endpoint, renderSlice };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.AtlasView = api;
})(globalThis);
