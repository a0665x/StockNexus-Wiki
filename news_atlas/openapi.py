"""OpenAPI 3.1 contract; data schemas are sourced from the canonical JSON Schema."""
import copy
import json
from .api import SCHEMA_PATH
from .regions import REGIONS

def obj(properties,required=()): return {'type':'object','properties':properties,**({'required':list(required)} if required else {})}
def arr(items,maximum=None): return {'type':'array','items':items,**({'maxItems':maximum} if maximum else {})}
def ref(name): return {'$ref':'#/components/schemas/'+name}
def string(maximum=None): return {'type':'string',**({'maxLength':maximum} if maximum else {})}

def specification():
    raw=json.loads(SCHEMA_PATH.read_text())
    def convert(value):
        if isinstance(value,list): return [convert(v) for v in value]
        if isinstance(value,dict):
            return {k:('#/components/schemas/'+v.split('/')[-1] if k=='$ref' and v.startswith('#/$defs/') else '#/components/schemas/ChannelDefinitions' if k=='$ref' and v=='#/properties/channel_definitions' else convert(v)) for k,v in value.items()}
        return value
    schemas={k:convert(v) for k,v in raw['$defs'].items()}
    schemas['ChannelDefinitions']=convert(raw['properties']['channel_definitions'])
    provider={'type':'string','enum':['google','yahoo','massive']}
    date={'type':'string','format':'date'}
    region={'type':['string','null'],'enum':[None,*REGIONS],'description':'Shared Google/Yahoo RSS edition. UI defaults TW. Omission preserves legacy Google TW / Yahoo US Finance semantics; explicit editions have separate coverage. Does not affect Massive.'}
    graph_node=copy.deepcopy(schemas['article']);graph_node['required']=['id','title','source']
    graph_node['properties']['id']={'type':'string','minLength':1,'maxLength':100}
    graph_node['properties'].update(display_sources=arr(provider,3),article_id=string(100))
    schemas['GraphNode']=graph_node
    edge=copy.deepcopy(schemas['relation']);edge['required']=['id','source','target','weight']
    edge['properties'].update(id=string(200),source=string(100),target=string(100),scope=string(20),cross_sources=arr(provider,3))
    schemas['GraphEdge']=edge
    schemas['Graph']=obj({'articles':arr(ref('GraphNode')),'relations':arr(ref('GraphEdge'))},['articles','relations'])
    schemas['GraphPayload']=obj({'relations_pending':{'type':'boolean'},'relation_settings':ref('relation_settings'),'schema_version':{'const':'2.0'},'articles':arr(ref('article')),'relations':arr(ref('GraphEdge')),'source_graphs':{'type':'object','additionalProperties':ref('Graph')},'cross_relations':arr(ref('GraphEdge')),'channel_definitions':ref('ChannelDefinitions'),'channel_version':string(),'total_articles':{'type':'integer'},'display_limit':{'type':'null'}})
    schemas['Error']=obj({'error':string()},['error'])
    schemas['SearchRequest']=obj({'relation_settings':ref('relation_settings'),'rss_region':region,'query':string(200),'ticker':string(20),'sources':{**arr(provider,3),'minItems':1,'uniqueItems':True},'start':date,'end':date,'force_refresh':{'type':'boolean','default':False},'massive_key':{'type':'string','format':'password','maxLength':512,'writeOnly':True,'description':'Optional request override; otherwise uses a separately remembered host key, then MASSIVE_API_KEY. Never returned or stored in the news DB.'}},['sources'])
    schemas['SearchRequest']['description']='Inclusive UTC dates, maximum 366 days. Massive requires explicit ticker; Google/Yahoo require query or ticker. Missing dates default to the last 7 days.'
    schemas['SearchResult']=obj({'graph':ref('GraphPayload'),'sources':arr({'type':'object'}),'db':{'type':'object'},'elapsed':{'type':'number'},'partial':{'type':'boolean'}})
    schemas['StreamEvent']=obj({'type':{'enum':['cache','status','source','heartbeat','phase','graph','graph_error','done']},'graph':ref('GraphPayload'),'source':provider,'articles':arr(ref('article')),'error':{'type':['string','null']},'cache':{'type':'object'},'counts':{'type':'object'},'message':string(),'phase':string(),'elapsed':{'type':'number'},'db':{'type':'object'}},['type'])
    schemas['ChannelInput']=obj({'id':string(60),'name':{**string(40),'minLength':1},'keywords':{**arr({**string(60),'minLength':1},30),'minItems':1},'match':{'enum':['any','all'],'default':'any'},'color':{'type':'string','pattern':'^#[a-fA-F0-9]{6}$'}},['name','keywords'])
    schemas['ClassifyRequest']=obj({'articles':arr(obj({'id':string(100),'title':string(2000),'summary':string(12000)},['id','title']))},['articles'])
    schemas['RawArticle']=obj({'provider':provider,'title':string(2000),'url':{'type':'string','format':'uri'},'published_at':string(),'summary':string(12000),'publisher':string(),'symbols':arr(string(20))},['provider','title','url','published_at'])
    schemas['NormalizeRequest']=obj({'articles':arr(ref('RawArticle'))},['articles'])
    schemas['Filters']=obj({'sources':arr(provider,3),'channel':string(60),'start':date,'end':date,'exploration':ref('exploration')})
    schemas['FilterRequest']=obj({'graph':ref('Graph'),'filters':ref('Filters')},['graph'])
    schemas['ExploreRequest']=obj({'graph':ref('Graph'),'query':string(200),'limit':{'type':'integer','minimum':1,'maximum':10,'default':3},'root_ids':{**arr(string(100),10),'minItems':1,'uniqueItems':True},'exploration':ref('exploration')},['graph'])
    schemas['ExploreRequest']['description']='Provide a nonblank query OR explicit root_ids. Literal title/symbol/entity/topic/channel/summary scoring; no embeddings. Traversal cannot pass through a different selected root. Trees can share other nodes.'
    schemas['TreeNode']=obj({'id':string(),'parent':{'type':['string','null']},'edge':string(),'depth':{'type':'integer'},'strength':{'type':'number'}},['id','parent','depth','strength'])
    schemas['Tree']=obj({'root_id':string(),'nodes':arr(ref('TreeNode'),150),'edge_ids':arr(string()),'truncated':{'type':'boolean'}},['root_id','nodes','edge_ids','truncated'])
    schemas['RootMatch']=obj({'id':string(),'title':string(),'score':{'type':['number','null']},'evidence':arr(obj({'field':string(),'term':string(),'match':string(),'score':{'type':'number'}}))},['id','title','score','evidence'])
    schemas['ExploreResult']=obj({'query':string(),'roots':arr(ref('RootMatch'),10),'trees':arr(ref('Tree'),10),'shared_nodes':arr(obj({'id':string(),'root_ids':arr(string())})),'matched_articles':{'type':'integer'},'scanned_articles':{'type':'integer'},'exploration':ref('exploration'),'method':{'const':'weighted_prefix_v2'},'scope':{'const':'submitted_graph'},'note':string()},['roots','trees','method','scope'])
    view=convert(raw['properties']['view']);view['properties'].update(positions=arr(obj({'id':string(),'x':{'type':'number'},'y':{'type':'number'},'z':{'type':'number'}},['id','x','y','z'])),timeline_zoom={'type':'number','minimum':1,'maximum':4})
    schemas['View']=view
    schemas['SnapshotRequest']=obj({'name':string(120),'search':obj({'rss_region':region,'query':string(200),'ticker':string(20),'start':date,'end':date}),'view':ref('View'),'source_graphs':{'type':'object','additionalProperties':ref('Graph')},'cross_relations':arr(ref('GraphEdge'))},['view','source_graphs'])
    schemas['SnapshotRequest']['description']='view.sources and view.separate are required. Source graph article IDs are canonical 24-char IDs; positions/focus IDs use provider::id in separate mode. Sanitized fields only; no credentials.'
    schemas['Snapshot']=obj({'id':string(),'name':string(),'created_at':{'type':'string','format':'date-time'},'search':{'type':'object'},'view':ref('View'),'source_graphs':{'type':'object','additionalProperties':ref('Graph')},'cross_relations':arr(ref('GraphEdge'))})
    schemas['DatabaseStats']=obj({k:{'type':'integer','minimum':0} for k in ('articles','coverage','attempts','snapshots')})
    schemas['NormalizeResult']=obj({'schema_version':{'const':'2.0'},'articles':arr(ref('article')),'rejected':arr(obj({'index':{'type':'integer'},'reason':string()},['index','reason'])),'persisted':{'const':False}},['articles','rejected','persisted'])
    schemas['TimelineResult']=obj({'timezone':{'const':'UTC'},'buckets':arr(obj({'channel':string(),'date':{'type':['string','null'],'format':'date'},'article_ids':arr(string()),'count':{'type':'integer'},'sources':{'type':'object','additionalProperties':{'type':'integer'}}},['channel','date','article_ids','count','sources'])),'relations':arr(ref('GraphEdge'))},['timezone','buckets','relations'])
    schemas['CacheResult']=obj({'graph':ref('GraphPayload'),'network_requests':{'const':0},'coverage':{'type':'object','additionalProperties':obj({'fresh_days':arr(obj({'day':date,'kind':string(),'checked_at':{'type':'number'}})),'missing_ranges':arr({'type':'array','prefixItems':[date,date],'minItems':2,'maxItems':2}),'end_exclusive':date})}},['graph','network_requests','coverage'])
    schemas['ChannelResult']=obj({'channels':ref('ChannelDefinitions'),'version':string()})
    schemas['SnapshotSummary']=obj({'id':string(),'name':string(),'created_at':{'type':'string','format':'date-time'},'sources':arr(provider)})
    view['required']=['sources','separate']
    paths={}
    def operation(path,method,name,summary,tag,request=None,response=None,description='',writes=False,network=False,parameters=None,code='200',media='application/json'):
        content={'description':'Success','content':{media:{'schema':response or {'type':'object'}}}}
        op={'operationId':name,'summary':summary,'tags':[tag],'description':description,'responses':{code:content,'400':{'description':'Invalid input','content':{'application/json':{'schema':ref('Error')}}},'404':{'description':'Not found','content':{'application/json':{'schema':ref('Error')}}}},'x-mcp':{'readOnlyHint':not writes,'destructiveHint':method=='delete','idempotentHint':not writes,'openWorldHint':network}}
        if request: op['requestBody']={'required':True,'content':{'application/json':{'schema':request}}};op['responses']['415']={'description':'Content-Type must be application/json'}
        if parameters:op['parameters']=parameters
        paths.setdefault(path,{})[method]=op
    def param(name):return [{'name':name,'in':'path','required':True,'schema':string()}]
    operation('/api/status','get','get_status','服務與 DB 狀態','System',response=obj({'schema_version':string(),'db':ref('DatabaseStats'),'massive_configured':{'type':'boolean'}}))
    operation('/api/settings/massive-key','post','remember_massive_key','保存本機 Massive 金鑰','System',obj({'key':{'type':'string','minLength':1,'maxLength':512,'format':'password','writeOnly':True}},['key']),obj({'configured':{'type':'boolean'}}),description='Explicit opt-in: save the last key in a private host file (0600), outside SQLite and exports. Never returns the key. Reused across server restarts and ports on this host.',writes=True)
    operation('/api/settings/massive-key','delete','forget_massive_key','清除本機 Massive 金鑰','System',response=obj({'configured':{'type':'boolean'}}),description='Deletes only the remembered host file. MASSIVE_API_KEY environment configuration is unchanged.',writes=True)
    operation('/api/capabilities','get','get_capabilities','功能、來源語系與限制','System')
    operation('/api/schema','get','get_data_schema','取得統一 JSON Schema','System',description='Canonical Draft 2020-12 data schema. The static /schema/news-atlas.schema.json URL is equivalent.')
    operation('/api/search','post','search_news_stream','串流搜尋真實新聞','News',ref('SearchRequest'),ref('StreamEvent'),description='NDJSON: one JSON event per line, not one JSON document. Updates cache. Source failures are events; HTTP 200 does not guarantee complete coverage. Use search_news_result for clients without streaming.',writes=True,network=True,media='application/x-ndjson')
    operation('/api/search/result','post','search_news_result','搜尋新聞並回傳單一 JSON','News',ref('SearchRequest'),ref('SearchResult'),description='Same bounded acquisition as streaming search; waits for sources. Inspect partial and each source cache/error. May take up to the source request budget.',writes=True,network=True)
    operation('/api/cache/graph','post','read_cached_graph','只讀本地快取與日期缺口','News',ref('SearchRequest'),ref('CacheResult'),description='No provider requests; force_refresh and massive_key are ignored. Coverage ranges use exclusive end dates; request end is inclusive.')
    operation('/api/articles/{id}','get','get_article_observations','依標準 ID 讀取各來源觀測','News',response=obj({'articles':arr(ref('article'))}),parameters=param('id'))
    operation('/api/normalize','post','normalize_articles','標準化文章／去重／分類','Graph',ref('NormalizeRequest'),ref('NormalizeResult'),description='Pure transformation of supplied records. Does not fetch URLs or save to DB. Invalid title/URL/date records are listed in rejected; malformed request objects return 400.')
    operation('/api/graph/build','post','build_graph','從標準文章產生有依據關聯','Graph',obj({'articles':arr(ref('article')),'source_graphs':{'type':'object','maxProperties':3,'additionalProperties':obj({'articles':arr(ref('GraphNode'))},['articles'])},'relation_settings':ref('relation_settings')}),ref('GraphPayload'),description='Provide articles OR source_graphs (google/yahoo/massive, all supplied articles). Rebuilds only supplied data, retains isolated and unknown-date nodes. Configurable rule switches, time windows, Jaccard thresholds, degree budgets and optional time half-life. No fetching or persistence; defaults preserve rules-v1.')
    operation('/api/graph/filter','post','filter_graph','來源／分類／日期／edge 門檻篩選','Graph',ref('FilterRequest'),ref('Graph'))
    operation('/api/graph/explore','post','explore_graph','關鍵字 Top-N roots 或指定 roots 的多棵探索樹','Graph',ref('ExploreRequest'),ref('ExploreResult'),description='Searches only the submitted graph. No new relations are inferred. Scores are heuristic, not probability or causality.')
    operation('/api/timeline','post','aggregate_timeline','UTC 日期 × Channel 分桶','Graph',ref('FilterRequest'),ref('TimelineResult'),description='Returns bucket article IDs, counts, source counts and unchanged filtered relations. No layout coordinates or causal inference.')
    operation('/api/channels','get','list_channels','列出預設／自訂分類','Channels',response=ref('ChannelResult'))
    operation('/api/channels','post','save_channel','新增或更新自訂分類','Channels',ref('ChannelInput'),obj({'channel':schemas['ChannelDefinitions']['items'],'channels':ref('ChannelDefinitions')}),description='Include a custom id to update. Built-ins are read-only. Up to 25 custom channels.',writes=True)
    operation('/api/channels/{id}','delete','delete_channel','刪除自訂分類','Channels',response=ref('ChannelResult'),parameters=param('id'),description='Only custom-* IDs. Existing snapshots retain frozen definitions.',writes=True)
    operation('/api/classify','post','classify_articles','以目前 Channel 規則分類文字','Channels',ref('ClassifyRequest'),description='Pure classification; no fetching or persistence.')
    operation('/api/view/validate','post','validate_view','驗證與清理完整視圖／快照內容','Snapshots',ref('SnapshotRequest'),ref('SnapshotRequest'),description='Uses the same validation as saving snapshots, without writing to DB. Useful before a future MCP write tool.')
    operation('/api/snapshots','get','list_snapshots','列出最近 50 份圖譜快照','Snapshots',response=obj({'snapshots':arr(ref('SnapshotSummary'),50)}))
    operation('/api/snapshots','post','save_snapshot','按來源保存圖譜與視圖設定','Snapshots',ref('SnapshotRequest'),obj({'id':string(),'name':string(),'created_at':{'type':'string','format':'date-time'},'db':ref('DatabaseStats')}),description='Creates a new snapshot; never marks acquisition coverage complete. Freezes channel and root-selection state.',writes=True,code='201')
    operation('/api/snapshots/{id}','get','get_snapshot','載回文章、關聯與視圖設定','Snapshots',response=ref('Snapshot'),parameters=param('id'))
    return {'openapi':'3.1.0','info':{'title':'GraphNews API','version':'1.0.0','description':'Local/trusted-network GraphNews service. No browser state is controlled by REST. All graph transformations are bounded. No MCP transport is implemented yet; stable operationIds and x-mcp hints support a future wrapper.'},'servers':[{'url':'/'}],'paths':paths,'components':{'schemas':schemas}}
