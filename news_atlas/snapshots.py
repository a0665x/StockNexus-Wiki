"""Validate explicit saved views, keeping source partitions separate from acquisition cache."""
import math
import datetime as dt
import re
from .model import canonical_url
from .regions import validate_region
from .relation_settings import settings as relation_settings

PROVIDERS = ('google', 'yahoo', 'massive')
ARTICLE_FIELDS = ('id','title','summary','url','published_at','source','symbols','language','fetched_at','entities','topics','analysis_version','origins','channels','primary_channel','channel_version')
EDGE_FIELDS = ('id','source','target','type','weight','method','evidence','days_apart','cross_sources')

def validate_snapshot(body):
    if not isinstance(body, dict):
        raise ValueError('快照必須是 JSON object')
    view = body.get('view', {})
    sources = view.get('sources') if isinstance(view, dict) else None
    if not isinstance(sources, list) or not sources or len(sources)>3 or any(s not in PROVIDERS for s in sources) or len(set(sources)) != len(sources):
        raise ValueError('請選擇要儲存的來源')
    if not isinstance(view.get('separate'), bool):
        raise ValueError('無效圖譜模式')
    groups = body.get('source_graphs', {})
    if not isinstance(groups, dict) or set(groups) != set(sources):
        raise ValueError('快照來源與圖譜來源不一致')
    normalized, all_ids = {}, set()
    for provider in sources:
        group = groups[provider]
        if not isinstance(group, dict) or not isinstance(group.get('articles'), list):
            raise ValueError('來源 articles 必須是陣列')
        articles, ids = [], set()
        for row in group['articles']:
            if not isinstance(row, dict) or not re.fullmatch(r'[a-f0-9]{24}', str(row.get('id',''))) or row['id'] in ids:
                raise ValueError('文章 ID 格式錯誤或重複')
            if not isinstance(row.get('source'), dict) or row['source'].get('provider') != provider:
                raise ValueError('文章來源不符合分組')
            if not isinstance(row.get('title'), str) or not row['title'] or not canonical_url(row.get('url')):
                raise ValueError('文章缺少標題或有效網址')
            ids.add(row['id'])
            articles.append({k: row[k] for k in ARTICLE_FIELDS if k in row})
        relations = validate_edges(group.get('relations', []), ids)
        normalized[provider] = {'articles': articles, 'relations': relations, 'total_articles': len(articles)}
        all_ids.update(ids)
    if not all_ids:
        raise ValueError('目前沒有可儲存的新聞')
    cross = validate_edges(body.get('cross_relations', []), all_ids)
    if view['separate'] and cross:
        raise ValueError('來源分組模式不能包含跨來源連線')
    positions = []
    valid_view_ids = {f'{p}::{a["id"]}' for p, g in normalized.items() for a in g['articles']} if view['separate'] else all_ids
    for pos in view.get('positions', []):
        if not isinstance(pos, dict) or pos.get('id') not in valid_view_ids:
            raise ValueError('節點位置參照無效')
        coords = [pos.get(k) for k in ('x','y','z')]
        if not all(isinstance(v,(int,float)) and math.isfinite(v) and abs(v)<=1e6 for v in coords):
            raise ValueError('節點位置超出範圍')
        positions.append({k: pos[k] for k in ('id','x','y','z')})
    mode=view.get('mode','network')
    if mode not in ('network','timeline'):
        raise ValueError('無效呈現模式')
    channel_defs=view.get('channel_definitions',[])
    if not isinstance(channel_defs,list) or len(channel_defs)>32:
        raise ValueError('Channel 定義數量錯誤')
    from .channels import validate_custom, OTHER
    frozen_defs=[]
    for definition in channel_defs:
        if not isinstance(definition,dict) or not isinstance(definition.get('id'),str) or not re.fullmatch(r'[a-z0-9-]{1,60}',definition['id']):
            raise ValueError('Channel ID 格式錯誤')
        normalized_def=dict(OTHER) if definition['id']=='other' else validate_custom(definition)
        normalized_def.update(id=definition['id'],builtin=bool(definition.get('builtin',False)))
        frozen_defs.append(normalized_def)
    if len({d['id'] for d in frozen_defs}) != len(frozen_defs):
        raise ValueError('Channel ID 重複')
    channel_filter=view.get('channel_filter','all')
    if channel_filter!='all' and channel_filter not in {d['id'] for d in frozen_defs}:
        raise ValueError('分類篩選不在快照定義內')
    cutoff=view.get('cutoff')
    if cutoff is not None:
        if not isinstance(cutoff,str):
            raise ValueError('時間軸截止日格式錯誤')
        cutoff=dt.date.fromisoformat(cutoff).isoformat()
    zoom=view.get('timeline_zoom',1)
    if not isinstance(zoom,(int,float)) or not math.isfinite(zoom) or not 1<=zoom<=4:
        raise ValueError('時間軸縮放值錯誤')
    timeline_style=view.get('timeline_style','density')
    if timeline_style not in ('density','nodes'):
        raise ValueError('無效時間軸呈現方式')
    raw_settings=view.get('exploration',{})
    if not isinstance(raw_settings,dict):
        raise ValueError('無效關聯設定')
    exploration={}
    for key,default,low,high,integer in [('internalMin',0,0,1,False),('crossMin',0,0,1,False),('depth',2,1,6,True),('branchLimit',4,1,12,True),('pathMin',.25,0,1,False),('maxNodes',150,1,150,True)]:
        value=raw_settings.get(key,default)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high or (integer and int(value)!=value):
            raise ValueError('關聯設定超出範圍')
        exploration[key]=value
    glow=view.get('glow',{})
    if not isinstance(glow,dict) or not isinstance(glow.get('enabled',True),bool):
        raise ValueError('無效光暈設定')
    normalized_glow={'enabled':glow.get('enabled',True)}
    for key,default,low,high in [('brightness',1,0,2),('radius',38,12,90),('decay',.64,.2,.9),('background',.18,.03,.6)]:
        value=glow.get(key,default)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('光暈設定超出範圍')
        normalized_glow[key]=value
    time_focus=view.get('time_focus',{'enabled':False,'date':None})
    if not isinstance(time_focus,dict) or not isinstance(time_focus.get('enabled',True),bool):
        raise ValueError('無效時間大小設定')
    focus_date=time_focus.get('date')
    if focus_date is not None:
        if not isinstance(focus_date,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',focus_date):
            raise ValueError('時間大小焦點日期格式錯誤')
        focus_date=dt.date.fromisoformat(focus_date).isoformat()
    curve={}
    for key,default,low,high in [('peak',2,1,12),('width',.12,.01,.5)]:
        value=time_focus.get(key,default)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError('時間鐘形曲線設定超出範圍')
        curve[key]=value
    if 'profile' in time_focus:
        profile=time_focus['profile']
        if not isinstance(profile,list) or len(profile)!=129 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 1<=v<=12 for v in profile):
            raise ValueError('時間塑形曲線必須包含 129 個 1–12 倍的有限數值')
        curve['profile']=profile[:]
    time_focus={'enabled':time_focus.get('enabled',True),'date':focus_date,**curve}
    focus=view.get('focus',{'mode':'overview','root_ids':[],'query':'','limit':3})
    if not isinstance(focus,dict): raise ValueError('無效 focus')
    root_ids=focus.get('root_ids',[]);focus_mode=focus.get('mode','overview');query=focus.get('query','');limit=focus.get('limit',3)
    if focus_mode not in ('overview','single','keyword') or not isinstance(root_ids,list) or len(root_ids)>10 or any(not isinstance(r,str) or r not in valid_view_ids for r in root_ids) or len(set(root_ids))!=len(root_ids) or not isinstance(query,str) or len(query)>200 or isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=10: raise ValueError('無效 focus roots 或設定')
    if (focus_mode=='overview' and root_ids) or (focus_mode=='single' and len(root_ids)!=1) or (focus_mode=='keyword' and (not root_ids or not query.strip())): raise ValueError('focus 模式與 roots 不一致')
    focus={'mode':focus_mode,'root_ids':root_ids,'query':query,'limit':limit}
    relation_scope=view.get('relation_scope','complete')
    scope_ids=view.get('relation_scope_ids',[])
    pending=view.get('relations_pending',False)
    if relation_scope not in ('complete','view') or not isinstance(pending,bool) or not isinstance(scope_ids,list) or len(scope_ids)>2400 or any(not isinstance(i,str) or i not in valid_view_ids for i in scope_ids):
        raise ValueError('無效關聯計算範圍')
    selected_id=view.get('selected_id')
    highlight_mode=view.get('highlight_mode','root')
    graph_channel=view.get('graph_channel','')
    if selected_id is not None and (not isinstance(selected_id,str) or selected_id not in valid_view_ids): raise ValueError('無效選取節點')
    if highlight_mode not in ('root','category') or not isinstance(graph_channel,str) or (graph_channel and graph_channel not in {d['id'] for d in frozen_defs}): raise ValueError('無效圖譜分類焦點')
    render_budget=view.get('render_budget',800)
    cache_version=view.get('relation_cache_version',0)
    scope_sources=view.get('relation_scope_sources',[])
    if isinstance(render_budget,bool) or render_budget not in (100,200,400,800,1200,1600,2000,2400):
        raise ValueError('無效渲染預算')
    if type(cache_version) is not int or cache_version not in (0,1) or not isinstance(scope_sources,list) or len(scope_sources)>3 or any(p not in PROVIDERS for p in scope_sources) or len(set(scope_sources))!=len(scope_sources):
        raise ValueError('無效快照關聯版本')
    relation_views=[]
    raw_views=view.get('relation_views',[])
    if not isinstance(raw_views,list) or len(raw_views)>12:
        raise ValueError('最多保存12組已完成視圖')
    for item in raw_views:
        if not isinstance(item,dict): raise ValueError('無效已完成視圖')
        ps=item.get('sources'); ids=item.get('ids'); separate=item.get('separate')
        gs=item.get('source_graphs')
        if not isinstance(ps,list) or not ps or len(ps)>3 or any(not isinstance(p,str) or p not in normalized for p in ps) or len(set(ps))!=len(ps) or not isinstance(separate,bool) or not isinstance(gs,dict) or set(gs)!=set(ps):
            raise ValueError('無效已完成視圖來源')
        allowed={f'{p}::{a["id"]}' if separate else a['id'] for p in ps for a in normalized[p]['articles']}
        if not isinstance(ids,list) or len(ids)>2400 or any(not isinstance(i,str) or i not in allowed for i in ids) or len(set(ids))!=len(ids):
            raise ValueError('無效已完成視圖節點')
        ids_set=set(ids); clean_groups={}; raw_ids=set()
        for p in ps:
            permitted={a['id'] for a in normalized[p]['articles'] if (f'{p}::{a["id"]}' if separate else a['id']) in ids_set}
            if not isinstance(gs[p],dict): raise ValueError('無效已完成視圖關聯')
            clean_groups[p]={'relations':validate_edges(gs[p].get('relations',[]),permitted)}
            raw_ids.update(permitted)
        cross_edges=validate_edges(item.get('cross_relations',[]),raw_ids)
        if separate and cross_edges: raise ValueError('分組視圖不能包含跨來源連線')
        relation_views.append({'ids':sorted(ids),'sources':sorted(ps),'separate':separate,'relation_settings':relation_settings(item.get('relation_settings')),'source_graphs':clean_groups,'cross_relations':cross_edges})
    search = body.get('search', {})
    if not isinstance(search,dict):
        raise ValueError('搜尋資訊格式錯誤')
    rss_region=validate_region(search.get('rss_region'))
    # Never persist credentials, request headers or arbitrary form fields.
    search = {k: str(search[k])[:200] for k in ('query','ticker','instrument','start','end') if k in search}
    if rss_region is not None:search['rss_region']=rss_region
    return {'name': str(body.get('name') or search.get('query') or search.get('ticker') or '新聞圖譜')[:120],
            'search': search, 'view': {'selected_id':selected_id,'highlight_mode':highlight_mode,'graph_channel':graph_channel,'relation_views':relation_views,'render_budget':render_budget,'relation_cache_version':cache_version,'relation_scope_sources':scope_sources,'relation_scope':relation_scope,'relation_scope_ids':scope_ids,'relations_pending':pending,'sources': sources, 'separate': view['separate'], 'positions': positions, 'mode':mode, 'channel_filter':channel_filter, 'cutoff':cutoff, 'timeline_zoom':zoom, 'channel_definitions':frozen_defs, 'timeline_style':timeline_style, 'exploration':exploration, 'glow':normalized_glow, 'focus':focus, 'time_focus':time_focus, 'price_focus':validate_price_focus(view.get('price_focus'),valid_view_ids), 'relation_settings':relation_settings(view.get('relation_settings'))},
            'source_graphs': normalized, 'cross_relations': cross}

def validate_edges(edges, ids):
    if not isinstance(edges,list):
        raise ValueError('relations 必須是陣列')
    out, seen = [], set()
    for edge in edges:
        if not isinstance(edge,dict) or edge.get('source') not in ids or edge.get('target') not in ids or edge['source']==edge['target']:
            raise ValueError('關聯參照不存在的節點')
        if not isinstance(edge.get('id'),str) or len(edge['id'])>150 or edge['id'] in seen:
            raise ValueError('關聯 ID 錯誤或重複')
        if edge.get('type') not in ('shared_entity','shared_topic','similar_title') or not isinstance(edge.get('evidence'),list):
            raise ValueError('關聯類型或依據格式錯誤')
        seen.add(edge['id'])
        out.append({k:edge[k] for k in EDGE_FIELDS if k in edge})
    return out


def validate_price_focus(value, ids):
    if value is None:return {'mix':0,'horizon':3,'ticker':'','as_of':None,'observations':{}}
    if not isinstance(value,dict):raise ValueError('Invalid price focus')
    mix=value.get('mix',0);horizon=value.get('horizon',3);ticker=value.get('ticker','')
    if isinstance(mix,bool) or not isinstance(mix,(int,float)) or not math.isfinite(mix) or not 0<=mix<=1 or isinstance(horizon,bool) or horizon not in (1,3,5,7) or not isinstance(ticker,str) or (ticker and not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',ticker)):raise ValueError('Invalid price settings')
    def date(v):
        if v is None:return None
        if not isinstance(v,str):raise ValueError('Invalid price date')
        return dt.date.fromisoformat(v).isoformat()
    rows=value.get('observations',{});out={}
    if not isinstance(rows,dict) or len(rows)>len(ids):raise ValueError('Invalid price observations')
    from .price_lens import instant
    for key,row in rows.items():
        if key not in ids or not isinstance(row,dict):raise ValueError('Invalid price article')
        stamp=row.get('published_at');close=row.get('baseline_close');returns=row.get('returns',{})
        if stamp is not None and not instant(stamp):raise ValueError('Invalid price timestamp')
        if close is not None and (isinstance(close,bool) or not isinstance(close,(int,float)) or not math.isfinite(close) or close<=0):raise ValueError('Invalid baseline close')
        if not isinstance(returns,dict):raise ValueError('Invalid price returns')
        clean={}
        for n in (1,3,5,7):
            v=returns.get(str(n))
            if v is not None and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v < -1):raise ValueError('Invalid price return')
            clean[str(n)]=v
        out[key]={'published_at':stamp,'baseline_date':date(row.get('baseline_date')),'baseline_close':close,'returns':clean}
    bars=value.get('bars',[]);clean_bars=[]
    if not isinstance(bars,list) or len(bars)>500:raise ValueError('Invalid price bars')
    for bar in bars:
        if not isinstance(bar,dict):raise ValueError('Invalid price bar')
        item={'date':date(bar.get('date'))}
        if not item['date']:raise ValueError('Missing bar date')
        for field in ('open','high','low','close'):
            v=bar.get(field)
            if (field=='close' or v is not None) and (isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0):raise ValueError('Invalid OHLC')
            item[field]=v
        if all(item[k] is not None for k in ('open','high','low')) and not item['low']<=min(item['open'],item['close'])<=max(item['open'],item['close'])<=item['high']:raise ValueError('Invalid OHLC range')
        clean_bars.append(item)
    if any(a['date']>=b['date'] for a,b in zip(clean_bars,clean_bars[1:])):raise ValueError('Unordered price bars')
    return {'mix':mix,'horizon':horizon,'ticker':ticker,'as_of':date(value.get('as_of')),'observations':out,'bars':clean_bars,'market':'US','currency':'USD'}
