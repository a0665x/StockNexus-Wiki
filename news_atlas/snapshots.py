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
    search = body.get('search', {})
    if not isinstance(search,dict):
        raise ValueError('搜尋資訊格式錯誤')
    rss_region=validate_region(search.get('rss_region'))
    # Never persist credentials, request headers or arbitrary form fields.
    search = {k: str(search[k])[:200] for k in ('query','ticker','start','end') if k in search}
    if rss_region is not None:search['rss_region']=rss_region
    return {'name': str(body.get('name') or search.get('query') or search.get('ticker') or '新聞圖譜')[:120],
            'search': search, 'view': {'sources': sources, 'separate': view['separate'], 'positions': positions, 'mode':mode, 'channel_filter':channel_filter, 'cutoff':cutoff, 'timeline_zoom':zoom, 'channel_definitions':frozen_defs, 'timeline_style':timeline_style, 'exploration':exploration, 'glow':normalized_glow, 'focus':focus, 'time_focus':time_focus, 'relation_settings':relation_settings(view.get('relation_settings'))},
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
