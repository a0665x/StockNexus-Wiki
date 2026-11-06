"""Version summaries, viewpoint lineage, evidence grouping and reported usage.
All knowledge stays in the existing append-only nodes/edges and JSON payloads.
"""
import datetime as dt
import json
import re
from collections import defaultdict, deque


def news_day(value):
    if not value:return ''
    return dt.datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(dt.timezone.utc).date().isoformat()


def settings(body):
    effort=body.get('reasoning_effort','low')
    if effort not in ('minimal','low','medium','high','xhigh','max','ultra','persistent'):raise ValueError('無效思考深度')
    languages=body.get('languages',['zh-Hant','en'])
    if not isinstance(languages,list) or not languages or len(languages)>2 or len(set(languages))!=len(languages) or any(x not in ('zh-Hant','en') for x in languages):raise ValueError('無效生成語系')
    size=body.get('evidence_size',1)
    if type(size) is not int or not 1<=size<=20:raise ValueError('每次證據篇數需為1–20')
    strategy=body.get('strategy','lexical')
    if strategy not in ('lexical','chronological','root','fusion'):raise ValueError('無效分組方式')
    edges=body.get('graph_edges',[])
    if not isinstance(edges,list) or len(edges)>30000:raise ValueError('圖譜關係過多')
    clean=[]
    for e in edges:
        if not isinstance(e,dict) or not all(isinstance(e.get(k),str) and len(e[k])<=100 for k in ('source','target')):raise ValueError('無效圖譜端點')
        weight=e.get('weight',1)
        if not isinstance(weight,(float,int)) or not 0<=weight<=100:raise ValueError('無效關係強度')
        clean.append({'source':e['source'],'target':e['target'],'weight':weight})
    from .evidence import graph_options
    horizon=body.get('price_horizon',3)
    if type(horizon) is not int or horizon not in (1,3,5,7):raise ValueError('無效股價交易日範圍')
    return dict(reasoning_effort=effort,languages=languages,evidence_size=size,strategy=strategy,graph_edges=clean,graph_settings=graph_options(body.get('graph_settings')),price_horizon=horizon)


def batches(rows,config):
    """Bounded group selection; explicit News edges are hints, never evidence."""
    if config.get('strategy')=='root':
        from .evidence import root_groups
        yield from root_groups(rows,config)
        return
    remaining=sorted(rows,key=lambda a:(a['published_at'] or '',a['revision_id']))
    size=config.get('evidence_size',1);method=config.get('strategy','lexical')
    adjacency=defaultdict(dict)
    for e in config.get('graph_edges',[]):
        a=e['source'].split('::')[-1];b=e['target'].split('::')[-1]
        adjacency[a][b]=max(adjacency[a].get(b,0),e['weight']);adjacency[b][a]=adjacency[a][b]
    terms=lambda a:set(re.findall(r'[a-z0-9_]+|[\u4e00-\u9fff]',(a['title']+' '+a['summary'][:1500]).lower()))
    while remaining:
        if method=='root':
            ids={a['id'] for a in remaining}
            seed=max(remaining,key=lambda a:sum(w for b,w in adjacency[a['id']].items() if b in ids));remaining.remove(seed)
        else:seed=remaining.pop(0)
        group=[seed];words=terms(seed)
        while remaining and len(group)<size:
            if method=='chronological':candidate=remaining[0]
            else:
                def score(a):
                    overlap=len(words&terms(a));link=max((adjacency[n['id']].get(a['id'],0) for n in group),default=0)
                    diversity=int(a['provider'] not in {n['provider'] for n in group})
                    return (link,overlap) if method=='root' else (int(overlap>0),diversity,link,overlap) if method=='fusion' else (overlap,)
                candidate=max(remaining,key=score)
                if method=='root' and score(candidate)[0]==0:break
            remaining.remove(candidate);group.append(candidate)
        yield group


def enrich_graph(store,version,start=None,end=None):
    for value in (start,end):
        if value:dt.date.fromisoformat(value)
    if start and end and start>end:raise ValueError('開始日期不得晚於結束日期')
    with store.connection() as db:
        nodes={r['id']:json.loads(r['payload']) for r in db.execute('SELECT * FROM nodes WHERE created_version<=?',(version,))}
        edges=[json.loads(r[0]) for r in db.execute('SELECT e.payload FROM edges e JOIN nodes a ON a.id=e.source JOIN nodes b ON b.id=e.target WHERE e.created_version<=?',(version,))]
        articles={r['id']:json.loads(r['payload']) for r in db.execute('SELECT id,payload FROM articles')}
        changes=[]
        for v in db.execute('SELECT * FROM versions WHERE version<=? ORDER BY version DESC LIMIT 10',(version,)):
            fresh=[n for n in nodes.values() if n.get('version')==v['version']]
            links=[json.loads(r[0]) for r in db.execute('SELECT e.payload FROM edges e JOIN nodes a ON a.id=e.source JOIN nodes b ON b.id=e.target WHERE e.created_version=?',(v['version'],))]
            changes.append({**dict(v),'added':len(fresh),'relations':len(links),'updates':sum(e['relation_type']=='UPDATES' for e in links),'titles':[n['title'] for n in fresh if n['kind']!='ArticleRevision'][:8], 'node_ids':[n['id'] for n in fresh], 'edge_ids':[e['stable_id'] for e in links]})
    def dates(n):
        if n['kind']=='ArticleRevision':return [news_day(n.get('published_at'))]
        return [news_day(articles.get(c['article_revision_id'],{}).get('published_at')) for c in n.get('citations',[])]
    def visible(n):
        return not(start or end) or any(d and (not start or d[:10]>=start) and (not end or d[:10]<=end) for d in dates(n))
    visible_ids={k for k,n in nodes.items() if visible(n)}
    # UPDATES is directional new -> previous; preserve branches and group latest by actual publish batch.
    parent=defaultdict(set);children=defaultdict(set)
    for e in edges:
        if e['relation_type']=='UPDATES':
            a=e['source']['stable_id'];b=e['target']['stable_id'];parent[a].add(b);children[b].add(a)
    histories={}
    for ident,n in nodes.items():
        if n['kind']!='Thesis':continue
        seen=set();queue=deque([ident])
        while queue:
            key=queue.popleft()
            if key in seen:continue
            seen.add(key);queue.extend(parent[key]|children[key])
        chain=sorted((nodes[k] for k in seen if k in nodes and nodes[k]['kind']=='Thesis'),key=lambda n:(n.get('version',0),n['id']))
        if not chain:continue
        original=chain[0];groups=defaultdict(list)
        for item in chain[1:]:groups[item.get('batch_id',str(item.get('version',0)))].append(item)
        latest=list(groups.values())[-3:]
        histories[ident]={'original':original,'recent_batches':latest,'revision_count':len(chain)}
    counts=defaultdict(lambda:defaultdict(int))
    for k,n in nodes.items():
        if k not in visible_ids or n['kind']!='Thesis':continue
        dated=[d[:10] for d in dates(n) if d]
        day=max(dated) if dated else 'unknown'
        counts[day][n.get('assessment',{}).get('category','uncertain')]+=1
    selected=[n for k,n in nodes.items() if k in visible_ids]
    categories=defaultdict(int)
    for n in selected:
        if n['kind']!='ArticleRevision':categories[n.get('assessment',{}).get('category','uncertain')]+=1
    theses=sorted((n for n in selected if n['kind']=='Thesis'),key=lambda n:n.get('version',0),reverse=True)
    from .evidence import topic
    index=[{'id':n['id'],'title':n['title'],'translations':{k:{'title':v['title']} for k,v in n.get('translations',{}).items()},'category':n.get('assessment',{}).get('category','uncertain'),'topic':topic(n),'topic_basis':'model' if n.get('assessment',{}).get('topic') else 'legacy_title_rule','date':max((d for d in dates(n) if d),default='unknown'),'version':n.get('version',0)} for n in theses]
    categories={k:sum(n['category']==k for n in index) for k in ('direct','indirect','low','uncertain')}
    perspectives={'index':index,'categories':dict(categories),'theses':theses[:40],'total_theses':len(theses),'note':'Stored model interpretations; not a whole-graph re-analysis.'}
    return {'filtered_perspectives':perspectives,'changes':changes,'histories':histories,'timeline':[{'date':d,'categories':dict(v)} for d,v in sorted(counts.items())], 'visible_ids':list(visible_ids),'display_range':{'start':start,'end':end}}


def usage_summary(store,start=None,end=None):
    """Sum complete reported calls touching interval; overlapping calls counted once."""
    total=defaultdict(int);calls=0;legacy=0
    with store.connection() as db:
        for r in db.execute('SELECT payload,usage FROM jobs'):
            p=json.loads(r['payload'])
            if 'receipts' not in p:
                if any(json.loads(r['usage']).values()):legacy+=1
                continue
            for receipt in p['receipts']:
                if (start or end) and not any(a.get('date') and (not start or news_day(a['date'])>=start) and (not end or news_day(a['date'])<=end) for a in receipt['articles']):continue
                calls+=1
                for k,v in receipt['usage'].items():
                    if type(v) is int and v>=0:total[k]+=v
    return {'reported':dict(total),'calls':calls,'legacy_jobs_without_attribution':legacy,'basis':'complete calls touching selected news dates; overlapping batches counted once'}
