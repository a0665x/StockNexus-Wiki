"""Stateless, bounded graph inspection for the UI and future MCP tools."""
import datetime as dt
import math
import re
import unicodedata
from .model import mention

LIMITS = {'articles':None,'relations':None,'roots':10,'nodes_per_tree':150}
DEFAULTS = {'internalMin':0,'crossMin':0,'depth':2,'branchLimit':4,'pathMin':.25,'maxNodes':150}

def settings(value=None):
    value={} if value is None else value
    if not isinstance(value,dict): raise ValueError('exploration 必須是 object')
    result={}
    for key,default in DEFAULTS.items():
        val=value.get(key,default)
        maximum={'depth':6,'branchLimit':12,'maxNodes':150}.get(key,1)
        minimum=1 if key in ('depth','branchLimit','maxNodes') else 0
        if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val) or not minimum<=val<=maximum or (key in ('depth','branchLimit','maxNodes') and int(val)!=val):
            raise ValueError('無效 exploration.'+key)
        result[key]=val
    return result

def graph_input(value):
    if not isinstance(value,dict): raise ValueError('graph 必須是 object')
    articles,edges=value.get('articles'),value.get('relations',[])
    if not isinstance(articles,list) or not isinstance(edges,list): raise ValueError('articles 與 relations 必須是陣列')
    ids=set()
    for row in articles:
        if not isinstance(row,dict) or not isinstance(row.get('id'),str) or not 1<=len(row['id'])<=100 or row['id'] in ids or not isinstance(row.get('title'),str) or len(row['title'])>2000 or not isinstance(row.get('summary',''),str) or len(row.get('summary',''))>12000: raise ValueError('無效或重複的文章')
        if not isinstance(row.get('source'),dict) or row['source'].get('provider') not in ('google','yahoo','massive'): raise ValueError('文章來源不正確')
        if row.get('published_at') is not None and not isinstance(row['published_at'],str): raise ValueError('無效 published_at')
        if row.get('primary_channel') is not None and not isinstance(row['primary_channel'],str): raise ValueError('無效 primary_channel')
        if 'display_sources' in row and (not isinstance(row['display_sources'],list) or any(p not in ('google','yahoo','massive') for p in row['display_sources'])): raise ValueError('無效 display_sources')
        if 'origins' in row and (not isinstance(row['origins'],list) or any(not isinstance(p,dict) or p.get('provider') not in ('google','yahoo','massive') for p in row['origins'])): raise ValueError('無效 origins')
        for key in ('entities','topics','channels'):
            values=row.get(key,[])
            if not isinstance(values,list) or len(values)>100 or any(not isinstance(v,dict) for v in values): raise ValueError('無效文章 '+key)
        if not isinstance(row.get('symbols',[]),list) or any(not isinstance(v,str) for v in row.get('symbols',[])): raise ValueError('無效 symbols')
        ids.add(row['id'])
    edge_ids=set()
    for edge in edges:
        if not isinstance(edge,dict) or not isinstance(edge.get('id'),str) or not 1<=len(edge['id'])<=200 or edge['id'] in edge_ids or not isinstance(edge.get('source'),str) or not isinstance(edge.get('target'),str) or edge['source'] not in ids or edge['target'] not in ids or edge['source']==edge['target']: raise ValueError('無效或懸空的關聯')
        weight=edge.get('weight')
        if isinstance(weight,bool) or not isinstance(weight,(int,float)) or not math.isfinite(weight) or not 0<=weight<=1: raise ValueError('關聯 weight 必須介於 0 與 1')
        edge_ids.add(edge['id'])
    return {'articles':articles,'relations':edges}

def filter_graph(graph,options=None):
    options=options or {}
    if not isinstance(options,dict): raise ValueError('filters 必須是 object')
    cfg=settings(options.get('exploration'))
    sources=options.get('sources',['google','yahoo','massive'])
    if not isinstance(sources,list) or any(p not in ('google','yahoo','massive') for p in sources): raise ValueError('無效 sources')
    channel=options.get('channel','all')
    if not isinstance(channel,str): raise ValueError('無效 channel')
    start,end=options.get('start'),options.get('end')
    for value in (start,end):
        if value is not None and (not isinstance(value,str) or dt.date.fromisoformat(value).isoformat()!=value): raise ValueError('無效日期')
    if start and end and start>end: raise ValueError('起始日期不得晚於結束日期')
    rows=[]
    for a in graph['articles']:
        origins=a.get('display_sources') or [a['source']['provider']]
        if not set(origins)&set(sources): continue
        if channel!='all' and not any(c.get('id')==channel for c in a.get('channels',[])): continue
        date=(a.get('published_at') or '')[:10]
        if (start and (not date or date<start)) or (end and (not date or date>end)): continue
        rows.append(a)
    ids={a['id'] for a in rows}
    edges=[e for e in graph['relations'] if e['source'] in ids and e['target'] in ids and e['weight'] >= cfg['crossMin' if e.get('scope')=='cross' or e.get('cross_sources') else 'internalMin']]
    return {'articles':rows,'relations':edges}

def rank_roots(rows,query,limit):
    query=unicodedata.normalize('NFKC',query).strip()
    terms=list(dict.fromkeys(re.findall(r'[\w.^-]+',query.lower(),re.UNICODE)))[:20]
    matches=[]
    for row in rows:
        fields={'title':row['title'],'summary':row.get('summary',''),'symbols':' '.join(row.get('symbols',[])),
                'entities':' '.join(str(x.get('id',''))+' '+str(x.get('label','')) for x in row.get('entities',[])),
                'topics':' '.join(str(x.get('label','')) for x in row.get('topics',[])),
                'channels':' '.join(str(x.get('name','')) for x in row.get('channels',[]))}
        evidence=[];score=0
        for field,text in fields.items():
            for term in terms:
                normalized=unicodedata.normalize('NFKC',text)
                if re.fullmatch(r'[a-z]{4,}',term,re.I) and field not in ('symbols','entities'):
                    found=re.search(r'(?<![A-Za-z0-9_])'+re.escape(term)+r'[A-Za-z]*(?![A-Za-z0-9_])',normalized,re.I)
                    hit=found.group(0) if found else None
                else: hit=mention(normalized,term)
                if hit:
                    weight={'title':8,'summary':2,'symbols':10,'entities':6,'topics':3,'channels':3}[field]
                    score+=weight;evidence.append({'field':field,'term':term,'match':hit,'score':weight})
        if score: matches.append({'id':row['id'],'title':row['title'],'score':score,'evidence':evidence})
    matches.sort(key=lambda r:(-r['score'],r['id']))
    return matches[:limit],len(matches)

def adjacency_index(edges):
    """Build the deterministic traversal index once for a shared graph."""
    adj={}
    for e in edges:
        for a,b in [(e['source'],e['target']),(e['target'],e['source'])]: adj.setdefault(a,[]).append((b,e))
    for values in adj.values(): values.sort(key=lambda pair:(-pair[1]['weight'],pair[1]['id']))
    return adj

def trace(edges,root,cfg,barriers=(),*,adjacency=None):
    adj=adjacency_index(edges) if adjacency is None else adjacency
    nodes={root:{'id':root,'depth':0,'strength':1,'parent':None}};selected=[];frontier=[root];truncated=False
    for depth in range(1,int(cfg['depth'])+1):
        new=[]
        for parent in sorted(frontier,key=lambda k:(-nodes[k]['strength'],k)):
            branches=0
            for target,edge in adj.get(parent,[]):
                strength=nodes[parent]['strength']*edge['weight']
                if target in nodes or target in barriers or strength<cfg['pathMin']: continue
                if branches>=cfg['branchLimit'] or len(nodes)>=cfg['maxNodes']: truncated=True;break
                nodes[target]={'id':target,'depth':depth,'strength':strength,'parent':parent,'edge':edge['id']};selected.append(edge['id']);new.append(target);branches+=1
        frontier=new
        if not frontier: break
    return {'root_id':root,'nodes':list(nodes.values()),'edge_ids':selected,'truncated':truncated}

def explore(body):
    graph=filter_graph(graph_input(body.get('graph')),{'exploration':body.get('exploration')})
    cfg=settings(body.get('exploration'));ids={a['id'] for a in graph['articles']}
    limit=body.get('limit',3)
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=10: raise ValueError('limit 必須為 1–10')
    query=body.get('query','');roots=body.get('root_ids')
    if not isinstance(query,str) or len(query)>200: raise ValueError('query 最多 200 字')
    if roots is not None:
        if query.strip() or not isinstance(roots,list) or not 1<=len(roots)<=10 or any(not isinstance(r,str) or r not in ids for r in roots) or len(set(roots))!=len(roots): raise ValueError('指定有效 root_ids，或提供 query，兩者擇一')
        matches=[{'id':r,'title':next(a['title'] for a in graph['articles'] if a['id']==r),'score':None,'evidence':[]} for r in roots];total=len(roots)
    else:
        if not query.strip(): raise ValueError('請提供 query 或 root_ids')
        matches,total=rank_roots(graph['articles'],query,limit);roots=[m['id'] for m in matches]
    trees=[trace(graph['relations'],r,cfg,set(roots)-{r}) for r in roots]
    membership={}
    for tree in trees:
        for node in tree['nodes']: membership.setdefault(node['id'],[]).append(tree['root_id'])
    return {'query':query,'roots':matches,'trees':trees,'matched_articles':total,'scanned_articles':len(graph['articles']),
            'shared_nodes':[{'id':k,'root_ids':v} for k,v in membership.items() if len(v)>1], 'exploration':cfg,
            'method':'weighted_prefix_v2','scope':'submitted_graph','note':'文字規則排序，不是語意模型或因果；不同樹可以共用節點。'}

def timeline(graph,channel='all'):
    buckets={}
    for a in graph['articles']:
        lane=channel if channel!='all' else a.get('primary_channel','other');date=(a.get('published_at') or '')[:10] or None
        key=(lane,date);bucket=buckets.setdefault(key,{'channel':lane,'date':date,'article_ids':[],'sources':{}})
        bucket['article_ids'].append(a['id']);provider=a['source']['provider'];bucket['sources'][provider]=bucket['sources'].get(provider,0)+1
    return {'timezone':'UTC','buckets':[dict(b,count=len(b['article_ids'])) for _,b in sorted(buckets.items(),key=lambda item:(item[0][1] or '',item[0][0]))],'relations':graph['relations']}
