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
    schemas['SearchRequest']=obj({'defer_relations':{'type':'boolean','default':False,'description':'Return news without computing a complete graph; UI computes a bounded view via /api/graph/preview.'},'relation_settings':ref('relation_settings'),'rss_region':region,'query':string(200),'ticker':string(40),'instrument':string(40),'sources':{**arr(provider,3),'minItems':1,'uniqueItems':True},'start':date,'end':date,'force_refresh':{'type':'boolean','default':False},'massive_key':{'type':'string','format':'password','maxLength':512,'writeOnly':True,'description':'Optional request override; otherwise uses a separately remembered host key, then MASSIVE_API_KEY. Never returned or stored in the news DB.'}},['sources'])
    schemas['SearchRequest']['description']='Web UI requires EXCHANGE:SYMBOL; instrument accepts this identity and ticker stays the provider symbol. Legacy API bare tickers remain supported. Explicit ticker selects data/graph/<ticker>; missing ticker uses _unassigned. Inclusive UTC dates, up to one inclusive calendar year. Massive requires explicit ticker; Google/Yahoo require query or ticker. Missing dates default to the last 7 days.'
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
    view['properties'].update({'relation_scope':{'type':'string','enum':['complete','view']},'relation_scope_ids':arr(string(),2400),'relations_pending':{'type':'boolean'}})
    schemas['CompletedRelationView']=obj({'ids':arr(string(),2400),'sources':arr(provider,3),'separate':{'type':'boolean'},'relation_settings':ref('relation_settings'),'source_graphs':{'type':'object','additionalProperties':obj({'relations':arr(ref('GraphEdge'))})},'cross_relations':arr(ref('GraphEdge'))},['ids','sources','separate','relation_settings','source_graphs'])
    view['properties'].update({'selected_id':{'type':['string','null']},'highlight_mode':{'enum':['root','category']},'graph_channel':string(),'render_budget':{'type':'integer','enum':[100,200,400,800,1200,1600,2000,2400]},'relation_cache_version':{'type':'integer','enum':[0,1]},'relation_scope_sources':arr(provider,3),'relation_views':arr(ref('CompletedRelationView'),12)})
    schemas['View']=view
    schemas['SnapshotRequest']=obj({'name':string(120),'search':obj({'instrument':string(40),'rss_region':region,'query':string(200),'ticker':string(20),'start':date,'end':date}),'view':ref('View'),'source_graphs':{'type':'object','additionalProperties':ref('Graph')},'cross_relations':arr(ref('GraphEdge'))},['view','source_graphs'])
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
    for resource in ('catalog','news','related','prices','l1','l2'):
        parameters=[{'name':name,'in':'query','required':name=='instrument' and resource!='catalog','schema':schema} for name,schema in {
            'instrument':string(40),'days':{'type':'integer','minimum':1,'maximum':3660,'default':7},
            'end':{'type':'string','format':'date-time'},'query':string(2000),'id':string(200),
            'limit':{'type':'integer','minimum':1,'maximum':100,'default':20},'offset':{'type':'integer','minimum':0,'maximum':100000,'default':0}}.items()]
        names={'catalog':set(),'news':{'instrument','days','end','query','limit','offset'},'related':{'instrument','days','end','query','limit','offset','id'},'prices':{'instrument','days','end'},'l1':{'instrument','days','end','query'},'l2':{'instrument','days','end','query','limit','offset','id'}}[resource]
        parameters=[x for x in parameters if x['name'] in names]
        for parameter in parameters:
            if resource=='related' and parameter['name']=='id': parameter['required']=True
        operation('/api/context/'+resource,'get','read_database_'+resource,'Read cached '+resource,'Research context',parameters=parameters,
            description='Allowed same-origin host required. Read-only, no network/model jobs. Independent of rendered graph. end exclusive; news uses publication time, L1 uses as-known evidence, L2 list uses run creation time; L2 id returns fixed snapshot. Prices use latest cached adjusted close vintage and full completed date buckets. Related uses shared entities/topics, not saved edges. L1 has a bounded 24-opinion retrieval and reports truncation; limit/offset apply to news, related and L2 lists.')
        paths['/api/context/'+resource]['get']['responses']['403']={'description':'Origin is not allowed'}
        paths['/api/context/'+resource]['get']['responses']['503']={'description':'Database temporarily unavailable'}
    arena_id={'type':'string','format':'uuid'}
    seat=obj({'name':string(60),'avatar':{'enum':['scout','challenger','planner','lead','judge']},
              'runtime':{'enum':['codex','claude','ollama','gemini']},'model':string(128),
              'persona':string(800),'weight':{'type':'integer','minimum':1,'maximum':5}},['name','avatar','runtime','model'])
    operation('/api/arena/catalog','get','arena_catalog','Detect host agent runtimes and models','Debate Arena')
    operation('/api/arena/runs','get','arena_runs','List local hearings','Debate Arena')
    operation('/api/arena/run','get','arena_run','Read sealed sources, arguments and independent ballots','Debate Arena',
              parameters=[{'name':'id','in':'query','required':True,'schema':arena_id}])
    operation('/api/arena/start','post','arena_start','Freeze available evidence and start a hearing','Debate Arena',
              obj({'id':arena_id,'topic':string(360),'instrument':string(40),'seats':{'type':'object','additionalProperties':seat}},
                  ['id','topic','seats']),writes=True,network=True,code='202')
    operation('/api/arena/cancel','post','arena_cancel','Stop the hearing and cancel active turns','Debate Arena',
              obj({'id':arena_id},['id']),writes=True)
    operation('/api/arena/observe','post','arena_observe','Ask a read-only observer about a sealed hearing snapshot','Debate Arena',
              obj({'id':arena_id,'question':string(1200),'history':arr(obj({'role':string(12),'text':string(2400)}),6)},
                  ['id','question']),network=True)
    for action in ('catalog','runs','run','start','cancel','observe'):
        operation_spec=next(iter(paths['/api/arena/'+action].values()))
        operation_spec['responses'].update({'403':{'description':'Same-origin local access required'},
                                           '503':{'description':'Host bridge or source database unavailable'}})
    paths['/api/arena/start']['post']['responses']['409']={'description':'A hearing is active or the ID was reused with a different configuration'}
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
    operation('/api/graph/preview','post','preview_graph','只計算目前視圖的關聯','Graph',obj({'ticker':string(20),'source_graphs':{'type':'object'},'relation_settings':ref('relation_settings'),'include_cross':{'type':'boolean','default':True},'stage':{'type':'string','enum':['strict','complete']}},['source_graphs']),{'type':'object'},description='NDJSON progress/result/done. At most 2400 unique article IDs, up to three source copies. pairs_checked counts date-window visits; pairs_computed and pairs_reused distinguish new scoring from persistent cache hits. include_cross=false skips cross-source work. Pair scores (including no match) persist separately; final edge selection remains view-scoped.',media='application/x-ndjson')
    operation('/api/graph/build','post','build_graph','從標準文章產生有依據關聯','Graph',obj({'ticker':string(20),'articles':arr(ref('article')),'source_graphs':{'type':'object','maxProperties':3,'additionalProperties':obj({'articles':arr(ref('GraphNode'))},['articles'])},'relation_settings':ref('relation_settings')}),ref('GraphPayload'),description='Provide articles OR source_graphs (google/yahoo/massive, all supplied articles). Rebuilds only supplied data, retains isolated and unknown-date nodes. Configurable rule switches, time windows, Jaccard thresholds, degree budgets and optional time half-life. No fetching or persistence; defaults preserve rules-v1.')
    operation('/api/graph/filter','post','filter_graph','來源／分類／日期／edge 門檻篩選','Graph',ref('FilterRequest'),ref('Graph'))
    operation('/api/graph/explore','post','explore_graph','關鍵字 Top-N roots 或指定 roots 的多棵探索樹','Graph',ref('ExploreRequest'),ref('ExploreResult'),description='Searches only the submitted graph. No new relations are inferred. Scores are heuristic, not probability or causality.')
    operation('/api/timeline','post','aggregate_timeline','UTC 日期 × Channel 分桶','Graph',ref('FilterRequest'),ref('TimelineResult'),description='Returns bucket article IDs, counts, source counts and unchanged filtered relations. No layout coordinates or causal inference.')
    operation('/api/channels','get','list_channels','列出預設／自訂分類','Channels',response=ref('ChannelResult'))
    operation('/api/channels','post','save_channel','新增或更新自訂分類','Channels',ref('ChannelInput'),obj({'channel':schemas['ChannelDefinitions']['items'],'channels':ref('ChannelDefinitions')}),description='Include a custom id to update. Built-ins are read-only. Up to 25 custom channels.',writes=True)
    operation('/api/channels/{id}','delete','delete_channel','刪除自訂分類','Channels',response=ref('ChannelResult'),parameters=param('id'),description='Only custom-* IDs. Existing snapshots retain frozen definitions.',writes=True)
    operation('/api/classify','post','classify_articles','以目前 Channel 規則分類文字','Channels',ref('ClassifyRequest'),description='Pure classification; no fetching or persistence.')
    operation('/api/view/validate','post','validate_view','驗證與清理完整視圖／快照內容','Snapshots',ref('SnapshotRequest'),ref('SnapshotRequest'),description='Uses the same validation as saving snapshots, without writing to DB. Useful before a future MCP write tool.')
    operation('/api/documents','get','read_document_collection','文件知識庫目錄、節點或指定修訂','Documents',
              response={'type':'object'},parameters=[{'in':'query','name':k,'required':False,'schema':string()} for k in ('collection','source','id','revision')],
              description='No parameters lists collections and source counts. collection returns current nodes, optionally filtered by source. Supply collection, source, id and revision to retrieve an exact historical record.')
    operation('/api/documents/import','post','import_document_collection','預覽或匯入研究文件 JSONL','Documents',
              parameters=[{'in':'query','name':key,'required':True,'schema':schema} for key,schema in
                          [('collection',string(64)),('source',string(64)),('mode',{'enum':['preview','apply']})]],
              description='Send a UTF-8 JSONL file up to 32 MiB from an allowed same-origin client. Preview validates without writing. Apply imports the complete source batch and returns counts. Records require display titles but publication dates may be absent/null. Explicit content links accept an optional non-empty rationale of at most 2000 characters; importing does not infer relationships or semantic distances.',writes=True)
    upload=paths['/api/documents/import']['post']
    upload['parameters'].append({'in':'query','name':'instrument','required':False,'schema':string(),'description':'Associate the source with this stock on apply.'})
    operation('/api/documents/bind','post','bind_document_source','將既有文件來源納入股票 L1','Documents',
              parameters=[{'in':'query','name':k,'required':True,'schema':string()} for k in ('collection','source','instrument')],
              description='Idempotently bind an existing source to global incremental L1 maintenance.',writes=True)
    upload['requestBody']={'required':True,'content':{'application/x-ndjson':{'schema':{'type':'string'}}}}
    upload['responses'].update({str(code):{'description':message} for code,message in
                               [(403,'Origin is not allowed'),(413,'Upload exceeds 32 MiB'),(415,'Expected application/x-ndjson'),(503,'Storage unavailable')]})
    operation('/api/snapshots','get','list_snapshots','列出最近 50 份圖譜快照','Snapshots',response=obj({'snapshots':arr(ref('SnapshotSummary'),50)}))
    operation('/api/snapshots','post','save_snapshot','按來源保存圖譜與視圖設定','Snapshots',ref('SnapshotRequest'),obj({'id':string(),'name':string(),'created_at':{'type':'string','format':'date-time'},'db':ref('DatabaseStats')}),description='Creates a new snapshot; never marks acquisition coverage complete. Freezes channel and root-selection state.',writes=True,code='201')
    operation('/api/snapshots/{id}','get','get_snapshot','載回文章、關聯與視圖設定','Snapshots',response=ref('Snapshot'),parameters=param('id'))
    operation('/api/prices/lens','post','price_lens','Forward trading-day average returns','Prices',obj({'ticker':string(15),'articles':arr(obj({'id':string(100),'published_at':{'type':['string','null'],'format':'date-time'}},['id']),100000),'massive_key':{'type':'string','format':'password','writeOnly':True,'maxLength':512}},['ticker','articles']),description='Explicit Massive ticker only. First complete US trading session close is baseline; mean of following 1/3/5/7 closes relative to baseline. Split-adjusted, excludes dividends and current ET day. Six-hour cache; missing complete horizons are null.',writes=True,network=True)
    schemas['Workspace']=obj({'news':obj({'draft':{'type':'object'},'snapshot':ref('SnapshotRequest'),'camera':{'type':'object'}}),'wiki':obj({'instrument':string(40),'controls':{'type':'object'},'root_selection':{'type':['object','null']},'root':{'type':['string','null']},'selected':{'type':['string','null']},'camera':{'type':'object'}})})
    operation('/api/workspace','get','read_workspace','恢復兩個獨立工作畫面','Workspace',response=ref('Workspace'),description='Trusted same-origin host state. Restores UI only; never starts model inference or provider acquisition.')
    operation('/api/workspace','post','save_workspace','保存新聞或 Wiki 工作畫面','Workspace',obj({'section':{'enum':['news','wiki']},'value':{'type':'object'}},['section','value']),obj({'saved':{'const':True}}),description='Same-origin/local-peer guard. Whitelisted settings and sanitized snapshots only, no credentials. Section updates preserve the other runtime. Stored in data/private/workspace.sqlite3.',writes=True)
    schemas['ChatRuntime']=obj({'revision':{'type':'integer'},'dataset':{'type':['integer','string']},'surface':{'enum':['news','wiki']},'instrument':string(40),'version':{'type':'integer'},'date_range':{'type':['object','null']},'selected_node':{'type':['object','null']},'view_mode':{'enum':['network','timeline']},'root_ids':arr(string()),'scope_ids':arr(string()),'selected_article':{'type':['string','null']},'controls':arr({'type':'object'})},['revision'])
    schemas['ChatEvent']=obj({'type':{'enum':['status','message','heartbeat','done','error']},'message':string(),'text':string(),'cancelled':{'type':'boolean'}},['type'])
    schemas['ChatSync']=obj({'context':ref('ChatRuntime'),'graph':obj({'articles':arr({'type':'object'}),'nodes':arr({'type':'object'}),'histories':{'type':'object'},'edges':arr({'type':'object'})},['articles','edges']),'ack':obj({'id':string(),'error':string()},['id'])},['context'])
    chat_description='Local browser integration only. Requires loopback Host and same-origin Origin on POST; bridge runs on host via private Unix socket. Maximum body 32 MiB. Tokens are ephemeral, not Codex credentials. Not a general remote automation API.'
    for name,method,request,response,media in [
        ('status','get',None,obj({'ready':{'type':'boolean'}}),'application/json'),
        ('models','get',None,{'type':'object'},'application/json'),
        ('session','post',obj({}),obj({'token':string()},['token']),'application/json'),
        ('sync','post',ref('ChatSync'),obj({'commands':arr({'type':'object'})}),'application/json'),
        ('turn','post',obj({'model':string(100),'message':{**string(24000),'minLength':1}},['message']),ref('ChatEvent'),'application/x-ndjson'),
        ('cancel','post',obj({}),obj({'ok':{'type':'boolean'}}),'application/json'),
        ('reset','post',obj({}),obj({'ok':{'type':'boolean'}}),'application/json')]:
        operation('/api/chat/'+name,method,'chat_'+name,'Chat '+name,'Chat',request,response,description=chat_description,writes=method=='post',network=name=='turn',media=media)
        op=paths['/api/chat/'+name][method]
        for status,label in [('401','Expired session'),('403','Not a local same-origin request'),('409','Busy or missing context'),('413','Context too large'),('503','Host chat bridge unavailable')]:op['responses'][status]={'description':label,'content':{'application/json':{'schema':ref('Error')}}}
        if name not in ('session','status','models'):op['security']=[{'ChatSession':[]}]
        if method=='post':op['parameters']=[{'name':'Origin','in':'header','required':True,'schema':{'type':'string','enum':['http://127.0.0.1:8765','http://localhost:8765']}}]
    wiki_description='Separate per-instrument SQLite Wiki. Writes require matching Origin/Host and local peer; remote origin must be explicitly listed in NEWS_ATLAS_WIKI_ORIGINS. Preview is model-free; start consumes a 10-minute plan. Bounded evidence batches, bilingual proposals, retrieved dependent viewpoint reassessment, immutable version history; no forecasts or exhaustive whole-graph reasoning.'
    for name,method in [('status','get'),('models','get'),('graph','get'),('jobs','get'),('article','get'),('node','get'),('markdown','get'),('range-counts','post'),('plan','post'),('apply','post'),('jobs','post'),('configure','post'),('cancel','post'),('stop','post'),('resume','post')]:
        operation('/api/wiki/'+name,method,'wiki_'+method+'_'+name,'Wiki '+name,'Wiki',request={'type':'object'} if method=='post' else None,description=wiki_description,writes=method=='post' and name!='range-counts',network=method=='post' and name in ('jobs','resume','apply'),code='202' if method=='post' and name=='jobs' else '200')
        op=paths['/api/wiki/'+name][method]
        if method=='get' and name not in ('status','models'):
            op['parameters']=[{'name':'instrument','in':'query','required':True,'schema':string()}]
            if name in ('graph','markdown','node'):op['parameters'].append({'name':'version','in':'query','schema':{'type':'integer','minimum':0}})
            if name=='markdown':op['parameters'].append({'name':'lang','in':'query','schema':{'enum':['en','zh-Hant']}})
            if name=='graph':
                op['parameters'].append({'name':'as_of','in':'query','schema':{'type':'string','format':'date-time'}})
                op['parameters'].extend({'name':key,'in':'query','schema':{'type':'string','format':'date'}} for key in ('start','end'))
            if name in ('article','node'):op['parameters'].append({'name':'id','in':'query','required':True,'schema':string()})
        if name=='node':op['parameters'].append({'name':'price_horizon','in':'query','schema':{'type':'integer','enum':[1,3,5,7]}})
        if method=='post':op['parameters']=[{'name':'Origin','in':'header','required':True,'schema':string()}]
        op['responses']['403']={'description':'Origin or peer not authorized'}
        op['responses']['503']={'description':'Wiki or model bridge unavailable'}
    graph_params={'instrument':string(40),'version':{'type':'integer','minimum':0},
                  'collection':{'enum':['nodes','edges']},'id':string(),'offset':{'type':'integer','minimum':0},
                  'limit':{'type':'integer','minimum':1,'maximum':100}}
    operation('/api/context/graph','get','read_versioned_graph','逐頁檢視完整 L1 節點、支持、反證與修訂','Research context',
              parameters=[{'in':'query','name':k,'required':k=='instrument','schema':v} for k,v in graph_params.items()],
              description='Pin the returned version and follow next_offset until null for each collection. id selects a node or incident edges in either direction. Retains historical revisions.')
    maintenance={'instrument':string(40),'model':string(100),'news_db':{'type':'boolean'},
                 'scope':{'enum':['global','loaded','focus']},'operation':{'enum':['update','review']},
                 'date_range':obj({'start':date,'end':date},['start','end']),
                 'include_vix':{'type':'boolean','default':False,'description':'Consider dated VIX news from the same stock archive during L1 extraction.'},'reasoning_effort':string(),'workers':{'type':'integer','enum':[1,3,5,10],'default':1,'description':'Concurrent tree workers for Graph root incremental update; a concurrency cap, not a guaranteed speed multiplier.'},'continuous':{'type':'boolean'}}
    for action in ('plan','apply'):
        payload=paths['/api/wiki/'+action]['post']['requestBody']['content']['application/json']
        payload['schema']=obj(maintenance,['instrument','model'])
        payload['example']={'instrument':'NASDAQ:GOOGL','model':'gpt-6.1-sol','scope':'global','news_db':True,'operation':'update'}
    paths['/api/wiki/jobs']['post']['requestBody']['content']['application/json']['schema']=obj(
        {'plan_id':string(),'continuous':{'type':'boolean'},'classify_missing':{'type':'boolean'}},['plan_id'])
    stop=paths['/api/wiki/stop']['post']
    stop['description']='Stop all queued or running L1 compilation and classification for this instrument and disable automatic catch-up and watching. Idempotent. Published versions and separate L2 research are retained.'
    stop['requestBody']['content']['application/json']['schema']=obj({'instrument':string(40)},['instrument'])
    prefix='/api/wiki/research/'
    operation(prefix+'compare','post','compare_saved_viewpoints','Compare two exact L1/L2 viewpoints','L2 research',
              request=obj({'instrument':string(),'refs':{'type':'array','items':string(),'minItems':2,'maxItems':2,'uniqueItems':True},
                           'model':string(),'reasoning_effort':string()},['instrument','refs','model']),
              writes=True,network=True,code='202',description='Explicit model review. Reuses matching work. Poll research/job, then read comparison using payload.comparison_id. Originals are retained.')
    paths[prefix+'compare']['post']['responses']['200']=paths[prefix+'compare']['post']['responses']['202']
    for name in ('comparison-candidates','comparisons','comparison'):
        params=[{'name':'instrument','in':'query','required':True,'schema':string()}]
        if name=='comparison':params.append({'name':'id','in':'query','required':True,'schema':string()})
        else:params.append({'name':'offset','in':'query','schema':{'type':'integer','minimum':0}})
        if name=='comparison-candidates':params.append({'name':'q','in':'query','schema':string()})
        operation(prefix+name,'get','read_'+name.replace('-','_'),name,'L2 research',parameters=params)
    for name in ('availability','job','runs','run','lenses','taxonomy'):
        keys=['instrument','id'] if name in ('job','run') else ['instrument']
        operation(prefix+name,'get','read_research_'+name,'L2 '+name,'L2 research',
                  parameters=[{'name':key,'in':'query','required':True,'schema':string()} for key in keys])
    fields={'query':string(2000),'model':string(100),'lookback_days':{'type':'integer','minimum':1,'maximum':3660},
            'reasoning_effort':string(),'mode':{'enum':['live','pinned']},'terms':arr({'type':'object'}),
            'status':{'enum':['active','corrected','retracted']}}
    for name,required,optional in [
            ('query',['query'],['model','reasoning_effort','lookback_days']),
            ('refresh',['lens_id','expected_revision'],[]),('save',['run_id','mode'],[]),
            ('source-status',['revision_id','status','reason'],[]),
            ('candidate',['text','facet'],[]),('taxonomy',['expected_revision','terms'],[])]:
        keys=['instrument',*required]
        operation(prefix+name,'post','write_research_'+name,'L2 '+name,'L2 research',
                  request=obj({k:fields.get(k,string()) for k in keys+optional},keys),
                  writes=True,network=name in ('query','refresh'),
                  description='Supply matching Origin and Host. Poll job with the returned job_id. Completed results reference an immutable run.')
        if name in ('query','refresh'):
            responses=paths[prefix+name]['post']['responses']
            responses['202']={'description':'Queued. Poll research/job with instrument and id.'}
    return {'openapi':'3.1.0','info':{'title':'StockNexus-Wiki API','version':'1.1.0','description':'Agent workflow: GET /api/context/catalog for news counts, L1 version and L2 run counts. POST /api/cache/graph with instrument, sources and inclusive dates; inspect coverage per source. For gaps POST the same request to /api/search, consume NDJSON status/heartbeat/source/done, then check coverage again. To maintain L1 choose a model from /api/wiki/models, plan with news_db and global scope, start with plan_id, poll /api/wiki/jobs. For L2 check research/availability, submit research/query, poll research/job, read research/run using payload.run_id. Browse /api/context/graph for all published L1 revisions and relations. Local Chat has a session-scoped stdio MCP bridge for runtime context and acknowledged UI controls.'},'servers':[{'url':'/'}],'paths':paths,'components':{'schemas':schemas,'securitySchemes':{'ChatSession':{'type':'http','scheme':'bearer','description':'Ephemeral browser session token from /api/chat/session; never a model login credential.'}}}}
