"""Stock-scoped graph evidence and cached, observed market response. No network calls."""
import json
import sqlite3
from pathlib import Path
from ..graph_storage import select
from ..exploration import settings as exploration_settings
from ..relation_settings import settings as relation_settings
from ..price_lens import measurements

OPTION_KEYS=('reasoning_effort','languages','evidence_size','strategy','graph_edges','graph_settings','price_horizon','settings_version','graph_selection','graph_universe','graph_context_revisions')
TOPICS=('revenue','operations','costs','market','trading','other')

def graph_options(value=None):
    value={} if value is None else value
    if not isinstance(value,dict) or set(value)-{'relation_settings','exploration'}:raise ValueError('無效 Graph 設定')
    return {'relation_settings':relation_settings(value.get('relation_settings')),'exploration':exploration_settings(value.get('exploration'))}

def selected_graph_rows(news,ident,selection,dates=None):
    if not isinstance(selection,dict) or not isinstance(selection.get('ticker'),str) or selection.get('ticker','').upper()!=ident.split(':',1)[1]:raise ValueError('請在新聞圖譜選取同一股票的 root 星河')
    trees=selection.get('trees',[])
    if not isinstance(trees,list) or not 1<=len(trees)<=10:raise ValueError('請先點選新聞圖譜的 node，展開 root 星河後再使用此方式')
    wanted=set()
    for tree in trees:
        if not isinstance(tree,dict) or not isinstance(tree.get('root_id'),str) or len(tree['root_id'])>150 or not isinstance(tree.get('title',''),str) or len(tree.get('title',''))>1000:raise ValueError('無效 root')
        articles=tree.get('articles',[])
        if not isinstance(articles,list) or not 1<=len(articles)<=150:raise ValueError('無效 root 文章範圍')
        for a in articles:
            if not isinstance(a,dict) or a.get('provider') not in ('google','yahoo','massive') or not isinstance(a.get('id'),str) or len(a['id'])>100:raise ValueError('無效 root 新聞識別')
            wanted.add((a['provider'],a['id']))
    store=select(news,ident.split(':',1)[1])
    rows=[]
    with store.connection() as db:
        for provider,ident in sorted(wanted):
            row=db.execute('SELECT payload FROM articles WHERE provider=? AND id=?',(provider,ident)).fetchone()
            if not row:raise ValueError('此 root 有新聞不在指定股票 DB；請重新搜尋並選取星河')
            a=json.loads(row[0]);date=(a.get('published_at') or '')[:10]
            if dates and not dates['start']<=date<=dates['end']:continue
            rows.append(a)
    return rows

def root_groups(rows,config):
    selection=config.get('graph_selection')
    if selection:
        remaining={(a['provider'],a['id']):a for a in rows}
        for tree in selection['trees']:
            group=[]
            for key in tree['articles']:
                a=remaining.pop((key['provider'],key['id']),None)
                if a:group.append(a)
            if group:yield group
        if remaining:raise ValueError('工作證據超出已選取星河')
        return
    raise ValueError('請重新選取新聞圖譜的 root 星河；不再自動建立其他樹')

def bounded_groups(groups):
    # A whole root is the unit of selection. Split only for the model input budget,
    # not the fixed count dropdown. Preserve all articles; never silently truncate.
    for tree_index,group in enumerate(groups):
        chunks=[];part=[];size=0
        for a in group:
            length=len(json.dumps(a,ensure_ascii=False))
            if part and size+length>65000:chunks.append(part);part=[];size=0
            part.append(a);size+=length
        if part:chunks.append(part)
        for i,chunk in enumerate(chunks):yield chunk,{'group':tree_index+1,'articles':len(group),'part':i+1,'parts':len(chunks)}

def cached_market(news,ident,rows,horizon=3):
    store=select(news,ident.split(':',1)[1]);path=Path(str(store.path)+'.prices.sqlite3')
    result={a['revision_id']:{'ticker':ident.split(':',1)[1],'horizon':horizon,'mean_return':None,'status':'unavailable','available_sessions':0,'required_sessions':horizon,'method':'mean_forward_close_return_v1'} for a in rows}
    if not path.exists():return result
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        try:series=db.execute('SELECT payload FROM series ORDER BY fetched ASC').fetchall()
        except sqlite3.OperationalError:return result
    for record in series:
        value=json.loads(record[0]);bars=value.get('bars',[])
        # Never reuse another symbol or an unidentifiable old cache payload.
        if value.get('ticker')!=ident.split(':',1)[1] or not bars:continue
        import datetime as dt,math
        if any(not isinstance(b.get('close'),(int,float)) or not math.isfinite(b['close']) or b['close']<=0 for b in bars):continue
        bars=sorted(bars,key=lambda b:b['date'])
        # Separate incomplete cache segments; do not count a gap as one trading day.
        segments=[];segment=[]
        for b in bars:
            if segment and (dt.date.fromisoformat(b['date'])-dt.date.fromisoformat(segment[-1]['date'])).days>5:segments.append(segment);segment=[]
            segment.append(b)
        if segment:segments.append(segment)
        for segment in segments:
            first=dt.date.fromisoformat(segment[0]['date'])
            eligible=[a for a in rows if a.get('published_at') and first<=dt.date.fromisoformat(a['published_at'][:10])<=dt.date.fromisoformat(segment[-1]['date'])]
            obs=measurements([dict(id=a['revision_id'],published_at=a['published_at']) for a in eligible],segment)
            for revision,o in obs.items():
                measured=o['returns'][str(horizon)]
                if measured is None and result[revision]['mean_return'] is not None:continue
                available=sum(b['date']>o['baseline_date'] for b in segment) if o['baseline_date'] else 0
                result[revision].update(mean_return=measured,status='observed' if measured is not None else 'pending',baseline_date=o['baseline_date'],baseline_close=o['baseline_close'],as_of=segment[-1]['date'],fetched_at=value.get('fetched_at'),available_sessions=min(horizon,available))
    return result

def topic(node):
    explicit=node.get('assessment',{}).get('topic')
    if explicit in TOPICS:return explicit
    text=(node.get('title','')+' '+node.get('summary','')).lower()
    import re
    for key,pattern in [('revenue',r'revenue|earnings|營收|業績|財報|獲利'),('costs',r'cost|expense|成本|支出|資本支出'),('operations',r'production|supply|cloud|product|生產|供應|營運|產品|雲端'),('trading',r'trading|buy|sell|交易|買進|賣出'),('market',r'stock|share price|股價|市場')]:
        if re.search(pattern,text):return key
    return 'other'
