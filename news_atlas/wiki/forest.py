"""Deterministic roots covering a date-selected subset of the full News graph.

Rendering budgets/clicked roots are not inputs. Tree members outside the target
interval are frozen context, not completed target evidence.
"""
import json
from ..graph_storage import select
from ..graph_cache import build_cached
from ..graph_payload import graph_payload
from ..exploration import trace,settings,adjacency_index
from .store import capture
from .evidence import bounded_groups

PROVIDERS=('google','yahoo','massive')
def universe_rows(news,ident,universe):
    if not isinstance(universe,dict) or set(universe)-{'ticker','articles','separate'} or str(universe.get('ticker','')).upper()!=ident.split(':')[1]:raise ValueError('請先載入同一股票的新聞圖譜')
    refs=universe.get('articles');separate=universe.get('separate',False)
    if not isinstance(refs,list) or not 1<=len(refs)<=10000 or not isinstance(separate,bool):raise ValueError('完整新聞範圍需包含 1–10000 篇')
    wanted=set()
    for a in refs:
        if not isinstance(a,dict) or set(a)!={'id','provider'} or a['provider'] not in PROVIDERS or not isinstance(a['id'],str) or not 1<=len(a['id'])<=100:raise ValueError('無效新聞圖譜成員')
        wanted.add((a['provider'],a['id']))
    store=select(news,ident.split(':')[1]);rows=[]
    with store.connection() as db:
        for provider,key in sorted(wanted):
            row=db.execute('SELECT payload FROM articles WHERE provider=? AND id=?',(provider,key)).fetchone()
            if not row:raise ValueError('完整圖譜有新聞不在此股票 DB；請重新載入新聞圖譜')
            rows.append(json.loads(row[0]))
    return rows

def in_range(a,dates):
    day=(a.get('published_at') or '')[:10]
    return not dates or bool(day and dates['start']<=day<=dates['end'])

def prepare(news,ident,universe,graph_settings,dates):
    raw=universe_rows(news,ident,universe);store=select(news,ident.split(':')[1])
    graph=build_cached(store,graph_payload,raw,store.list_channels(),graph_settings['relation_settings'])
    cfg=settings(graph_settings['exploration']);separate=universe.get('separate',False)
    key=lambda p,i:p+'::'+i if separate else i
    refs={};titles={};edges={}
    for provider in PROVIDERS:
        for a in graph['source_graphs'][provider]['articles']:
            node=key(provider,a['id']);refs.setdefault(node,[]).append({'provider':provider,'id':a['id']});titles[node]=a['title']
        for e in graph['source_graphs'][provider]['relations']:
            a,b=key(provider,e['source']),key(provider,e['target']);pair=tuple(sorted((a,b)))
            if pair not in edges:edges[pair]={**e,'id':(provider+':' if separate else '')+':'.join(sorted((e['source'],e['target']))),'source':a,'target':b,'scope':provider}
    if not separate:
        for e in graph['cross_relations']:
            pair=tuple(sorted((e['source'],e['target'])))
            if pair not in edges:edges[pair]={**e,'id':':'.join(pair),'scope':'cross'}
    edges=[e for e in edges.values() if e['weight']>=cfg['crossMin' if e['scope']=='cross' else 'internalMin']]
    rows=[capture(a) for a in raw];targets=[a for a in rows if in_range(a,dates)]
    target_keys={(a['provider'],a['id']) for a in targets};uncovered=set(target_keys)
    degree={n:0 for n in refs}
    for e in edges:degree[e['source']]+=e['weight'];degree[e['target']]+=e['weight']
    roots=sorted((n for n,items in refs.items() if any((a['provider'],a['id']) in target_keys for a in items)),key=lambda n:(-degree[n],n))
    trees=[];context_keys=set();adjacency=adjacency_index(edges)
    for root in roots:
        if not any((a['provider'],a['id']) in uncovered for a in refs[root]):continue
        tree=trace(edges,root,cfg,adjacency=adjacency)
        members=[a for n in tree['nodes'] for a in refs[n['id']]]
        covered=[a for a in members if (a['provider'],a['id']) in uncovered]
        if not covered:continue
        trees.append({'root_id':root,'title':titles[root],'articles':members,'targets':covered})
        uncovered.difference_update((a['provider'],a['id']) for a in covered)
        context_keys.update((a['provider'],a['id']) for a in members)
    if uncovered:raise ValueError('完整圖譜覆蓋未完成，請重新預覽')
    context=[a for a in rows if (a['provider'],a['id']) in context_keys]
    forest={'mode':'coverage','ticker':ident.split(':')[1],'trees':trees,'universe_articles':len(rows),'target_articles':len(targets),'context_articles':len(context),'target_revisions':[a['revision_id'] for a in targets]}
    return targets,context,forest

def groups(pending,context,forest):
    remaining={a['revision_id']:a for a in pending};by_key={(a['provider'],a['id']):a for a in context}
    for index,tree in enumerate(forest['trees']):
        targets=[by_key[(a['provider'],a['id'])] for a in tree['targets'] if (a['provider'],a['id']) in by_key]
        targets=[a for a in targets if a['revision_id'] in remaining]
        if not targets:continue
        anchor=targets[0];members=[by_key[(a['provider'],a['id'])] for a in tree['articles']]
        # Keep the entire tree, including already processed/older context. For large
        # trees retain a pending anchor in each segment and credit coverage only when
        # every segment of that tree has published successfully.
        chunks=list(bounded_groups([[anchor,*[a for a in members if a['revision_id']!=anchor['revision_id']]]]))
        for part,(chunk,meta) in enumerate(chunks):
            evidence=[anchor,*[a for a in chunk if a['revision_id']!=anchor['revision_id']]]
            covered=targets if part==len(chunks)-1 else []
            yield evidence,{**meta,'group':index+1,'groups':len(forest['trees']),'targets':len(targets),'context_articles':len(members),'root_id':tree['root_id']},covered
        for a in targets:remaining.pop(a['revision_id'],None)
    if remaining:raise ValueError('有新聞尚未納入 root 覆蓋，請重新套用 Graph 設定')
