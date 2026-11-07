"""Snapshot research over the existing Wiki. SQLite is authoritative, model output is a proposal.

No research object is an ingestion source. Legacy L1 nodes are wrapped without rewriting
history. Local deployment has one trusted owner; clients cannot supply an owner.
"""
import datetime as dt
import json
import os
import re
import uuid
from .store import digest, encode, now

OWNER = 'local'
SCHEMA = 'research-v1'
TABLES = {'research_objects', 'research_lenses', 'research_jobs'}
SEEDS = [
 ('topic.data_center','topic','資料中心',['data center','datacenter','資料中心']),
 ('topic.ai_hardware','topic','AI 硬體',['hardware','gpu','晶片','半導體','硬體']),
 ('topic.cloud','topic','雲端',['cloud','雲端']),
 ('topic.energy','topic','能源',['energy','能源']),
 ('driver.demand','driver','需求',['demand','需求']),
 ('driver.capex','driver','資本支出',['capex','capital expenditure','資本支出']),
 ('driver.earnings','driver','財報',['earnings','revenue','財報','營收']),
 ('driver.supply','driver','供應',['supply','供應','產能']),
 ('driver.regulation','driver','政策',['regulation','policy','政策','監管']),
 ('driver.valuation','driver','估值',['valuation','估值']),
 ('analysis.narrative_momentum','analysis_dimension','敘事動能',['narrative','敘事']),
 ('analysis.price_momentum','analysis_dimension','價格動能',['price momentum','價格動能','股價動能']),
 ('analysis.fundamentals','analysis_dimension','基本面',['fundamentals','基本面']),
 ('analysis.risk','analysis_dimension','風險',['risk','風險']),
]

def enabled():
    return os.environ.get('NEWS_ATLAS_RESEARCH','1') != '0'

def instant(value):
    try:
        x=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if x.tzinfo is None: raise ValueError()
        return x.astimezone(dt.timezone.utc)
    except (ValueError,TypeError,AttributeError): raise ValueError('時間需包含日期、時間及時區')

def matches(text, term):
    term=term.casefold();text=text.casefold()
    return bool(re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])',text)) if re.fullmatch(r'[a-z0-9 _-]+',term) else term in text

def migrate(db):
    # Additive tables; no changes to the v1 L1 contract or IDs.
    db.executescript('''
    CREATE TABLE IF NOT EXISTS research_objects(id TEXT PRIMARY KEY,kind TEXT NOT NULL,owner TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS research_lenses(id TEXT PRIMARY KEY,owner TEXT NOT NULL,revision TEXT NOT NULL,updated_at TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS research_jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload TEXT NOT NULL,error TEXT);
    CREATE INDEX IF NOT EXISTS research_kind ON research_objects(kind,owner,created_at);
    ''')

def put(db,kind,payload,owner=OWNER,ident=None):
    ident=ident or kind+'-'+digest(payload)
    db.execute('INSERT OR IGNORE INTO research_objects VALUES (?,?,?,?,?)',(ident,kind,owner,now(),encode(payload)))
    return ident

def obj(db,ident,kind=None,owner=OWNER):
    r=db.execute('SELECT kind,payload FROM research_objects WHERE id=? AND owner=?',(ident,owner)).fetchone()
    if not r or kind and r['kind']!=kind: raise ValueError('找不到此研究版本或無權讀取')
    return json.loads(r['payload'])

def taxonomy(db,cutoff=None):
    rows=db.execute("SELECT payload FROM research_objects WHERE kind='taxonomy' AND owner='' ORDER BY created_at DESC,id DESC").fetchall()
    if not rows:
        tax={'revision_id':uuid.uuid4().hex,'available_at':now(),'terms':[{'id':i,'facet':f,'label':l,'aliases':a,'definition':l+'相關的原子主張','include':a,'exclude':[], 'related_terms':[],'status':'active'} for i,f,l,a in SEEDS]}
        put(db,'taxonomy',tax,'',tax['revision_id']);return tax
    for row in rows:
        tax=json.loads(row[0])
        if cutoff is None or instant(tax['available_at'])<=cutoff:return tax
    return {'revision_id':None,'terms':[],'available_at':None}

def classify(db):
    """Persist classifications separately, once per exact input and taxonomy revision.
    Legacy backfill is known NOW; it cannot fabricate historical assignments.
    """
    tax=taxonomy(db)
    for row in db.execute("SELECT id,payload FROM nodes WHERE kind IN ('Claim','Event','Thesis')").fetchall():
        key='classification-'+digest([row['id'],tax['revision_id'],'lexical-v1'])
        if db.execute('SELECT 1 FROM research_objects WHERE id=?',(key,)).fetchone():continue
        n=json.loads(row['payload']);text=n.get('title','')+' '+n.get('summary','');items=[]
        for term in tax['terms']:
            hits=[a for a in [term['label'],*term['aliases']] if matches(text,a)]
            if term['status']=='active' and hits and not any(matches(text,x) for x in term['exclude']):
                items.append({'opinion_revision':row['id'],'taxonomy_revision':tax['revision_id'],'term_id':term['id'],'claim_ids':[row['id']+':claim'],'rationale':'文字命中：'+', '.join(hits),'confidence_band':'low','classifier_version':'lexical-v1'})
        put(db,'classification',{'opinion_revision':row['id'],'taxonomy_revision':tax['revision_id'],'available_at':now(),'assignments':items,'candidate_terms':[],'status':'classified' if items else 'unclassified','unclassified_reasons':[] if items else ['沒有可靠的詞彙匹配，保留全文召回']},'',key)


def canonical_ast(value,terms,depth=0):
    if value is None:return {'op':'all'}
    if not isinstance(value,dict) or depth>8:raise ValueError('篩選條件格式錯誤或過深')
    op=value.get('op')
    if op=='all' and set(value)=={'op'}:return value
    if op in ('and','or') and set(value)=={'op','args'}:
        args=value['args']
        if not isinstance(args,list) or not 1<=len(args)<=20:raise ValueError('布林條件需有 1–20 項')
        return {'op':op,'args':sorted([canonical_ast(a,terms,depth+1) for a in args],key=encode)}
    if op=='not' and set(value)=={'op','arg'}:return {'op':op,'arg':canonical_ast(value['arg'],terms,depth+1)}
    if op in ('term','text') and set(value)=={'op','value'}:
        v=value['value']
        if not isinstance(v,str) or not 1<=len(v)<=120:raise ValueError('篩選值長度錯誤')
        if op=='term' and v not in terms:raise ValueError('未知分類；可用文字條件查詢')
        return {'op':op,'value':v}
    raise ValueError('不支援的篩選條件')

def allowed(ast,text,labels):
    op=ast['op']
    if op=='all':return True
    if op=='term':return ast['value'] in labels
    if op=='text':return matches(text,ast['value'])
    if op=='not':return not allowed(ast['arg'],text,labels)
    return (all if op=='and' else any)(allowed(a,text,labels) for a in ast['args'])

def parse_lens(body,stock,tax,clock=None):
    if 'owner' in body or 'owner_id' in body:raise ValueError('owner 由服務端決定')
    q=body.get('query','').strip()
    if not 1<=len(q)<=2000:raise ValueError('請輸入 1–2000 字的研究問題')
    named=re.findall(r'\b[A-Z][A-Z0-9_-]{1,15}:[A-Z0-9][A-Z0-9.-]{0,19}\b',q)
    if named and any(x!=stock for x in named):raise ValueError('問題指定其他股票；請先切換股票')
    clock=clock or instant(now());cutoff=instant(body['as_of']) if body.get('as_of') else clock
    if cutoff>clock:raise ValueError('不能查詢未來截止時間')
    days=body.get('lookback_days',30)
    if type(days)!=int or not 1<=days<=3660:raise ValueError('觀察窗需為 1–3660 日')
    if body.get('required_terms') or body.get('excluded_terms'):raise ValueError('請只使用 filter_ast 表達硬條件')
    terms={t['id'] for t in tax['terms']}
    ast=canonical_ast(body.get('filter_ast'),terms)
    # Explicit exclusion controls and common quoted free-text exclusions are hard.
    exclusions=re.findall(r'(?:排除|不含|excluding|exclude)\s*[「"\']([^」"\']+)[」"\']',q,re.I)
    unparsed=re.sub(r'(?:排除|不含|excluding|exclude)\s*[「"\'][^」"\']+[」"\']','',q,flags=re.I)
    if re.search(r'排除|不含|不包括|僅限|只要|必須|\b(?:exclude|excluding|only|AND|OR|NOT)\b',unparsed,re.I):
        raise ValueError('硬條件尚不明確：請在問題中以 排除「關鍵字」 指定排除文字；其他複雜硬條件目前無法解析')
    if exclusions:ast={'op':'and','args':[ast,*[{'op':'not','arg':{'op':'text','value':x}} for x in exclusions]]}
    soft=[t['id'] for t in tax['terms'] if any(matches(q,a) for a in [t['label'],*t['aliases']])]
    momentum=bool(re.search(r'動能|momentum',q,re.I))
    return {'schema':SCHEMA,'instrument':stock,'query':q,'normalized_question':q,'filter_ast':ast,'soft_terms':soft,
            'dimensions':['analysis.narrative_momentum','analysis.price_momentum'] if momentum else ['analysis.fundamentals'],
            'time_policy':{'lookback_days':days,'cutoff_mode':'fixed' if body.get('as_of') else 'rolling_now','fixed_as_of':body.get('as_of'),'window_basis':'published_at','horizon_sessions':20},
            'time_spec':{'start':(cutoff-dt.timedelta(days=days)).isoformat(),'end':cutoff.isoformat(),'as_of':cutoff.isoformat(),'temporal_mode':'as_known','timezone':'UTC'},
            'interpretation_notes':['股票沿用目前 root','以來源發布時間篩選；只用截止前已取得的版本','未指定展望時採 20 個交易日；觀察窗與展望分開','分類＋全文檢索；無向量索引；分類信心不是上漲機率']}

def epochs(db):
    # Hash all immutable revision identities, not merely the most recently completed job.
    sources=[tuple(r) for r in db.execute('SELECT id,captured_at FROM articles ORDER BY captured_at,id')]
    done={r[0] for r in db.execute('SELECT DISTINCT revision FROM extractions')}
    nodes=[tuple(r) for r in db.execute('SELECT id,created_version FROM nodes ORDER BY id')]
    edges=[tuple(r) for r in db.execute('SELECT id FROM edges ORDER BY id')]
    tax=taxonomy(db)
    status_events=[tuple(r) for r in db.execute("SELECT id FROM research_objects WHERE kind IN ('source_status','classification') ORDER BY id")]
    consumed_prefix=0
    for source in sources:
        if source[0] not in done:break
        consumed_prefix+=1
    return {'ingest_epoch_consumed':consumed_prefix,'corpus':digest([sources,nodes,edges,status_events]),'taxonomy':tax['revision_id'],'ingest':len(sources),'consumed':sum(1 for x in sources if x[0] in done),'pending':sum(1 for x in sources if x[0] not in done)}

def bundle(db,lens):
    cutoff=instant(lens['time_spec']['as_of']);start=instant(lens['time_spec']['start']);tax=taxonomy(db,cutoff)
    articles={r['id']:{**json.loads(r['payload']),'available_at':r['captured_at']} for r in db.execute('SELECT * FROM articles') if instant(r['captured_at'])<=cutoff}
    latest={}
    for a in articles.values():
        key=(a['provider'],a['id'])
        if key not in latest or a['available_at']>latest[key]['available_at']:latest[key]=a
    current={a['revision_id'] for a in latest.values()}
    statuses={}
    for r in db.execute("SELECT payload FROM research_objects WHERE kind='source_status' AND owner='' ORDER BY created_at,id"):
        e=json.loads(r[0])
        if instant(e['known_at'])<=cutoff:statuses[e['revision_id']]=e['status']
    current={r for r in current if statuses.get(r,'active')=='active'}
    nodes={}
    for r in db.execute("SELECT n.*,v.created_at FROM nodes n JOIN versions v ON v.version=n.created_version WHERE n.kind IN ('Claim','Event','Thesis') ORDER BY n.created_version,n.id"):
        n=json.loads(r['payload']);available=n.get('available_at') or r['created_at']
        if instant(available)<=cutoff:nodes[n['id']]={**n,'available_at':available}
    edges=[json.loads(r['payload']) for r in db.execute('SELECT payload FROM edges')]
    edges=[e for e in edges if e.get('available_at') and instant(e['available_at'])<=cutoff]
    updates={e['source']['stable_id']:e['target']['stable_id'] for e in edges if e['relation_type']=='UPDATES'}
    superseded=set(updates.values())
    def logical(key):
        seen=set()
        while key in updates and key not in seen:seen.add(key);key=updates[key]
        return key
    classified={}
    for r in db.execute("SELECT payload FROM research_objects WHERE kind='classification' AND owner=''"):
        a=json.loads(r[0])
        if a.get('classifier_version')=='llm-v1' and a['taxonomy_revision']==tax['revision_id'] and instant(a['available_at'])<=cutoff:classified[a['opinion_revision']]=a
    from .classifier import groups
    membership=groups({'nodes':list(nodes.values()),'edges':edges})
    inherited={i:[] for i in nodes}
    for root,members in membership.items():
        for member in members:
            if member!=root:inherited[member].extend(classified.get(root,{}).get('assignments',[]))
    candidates=[];excluded={'outdated_source':0,'outside_window':0,'hard_filter':0,'unresolved_source':0};assignments=[]
    for n in nodes.values():
        if n['id'] in superseded:continue
        cites=n.get('citations',[])
        if not cites or any(c.get('article_revision_id') not in articles for c in cites):excluded['unresolved_source']+=1;continue
        if any(c['article_revision_id'] not in current for c in cites):excluded['outdated_source']+=1;continue
        sources=[articles[c['article_revision_id']] for c in cites]
        if not any(a.get('published_at') and start<=instant(a['published_at'])<cutoff for a in sources):excluded['outside_window']+=1;continue
        text=n.get('title','')+' '+n.get('summary','')
        classification=classified.get(n['id'],{})
        items=[*classification.get('assignments',[]),*inherited.get(n['id'],[])]
        labels=[a['term_id'] for a in items];assignments.extend(items)
        if not allowed(lens['filter_ast'],text,labels):excluded['hard_filter']+=1;continue
        terms=re.findall(r'[a-z0-9]{2,}|[\u3400-\u9fff]{2,}',lens['query'].lower())
        soft_hits=sum(any(matches(text,a) for a in [t['label'],*t['aliases']]) for t in tax['terms'] if t['id'] in lens['soft_terms'])
        score=sum(1 for x in terms if matches(text,x))+soft_hits+2*len(set(labels)&set(lens['soft_terms']))
        evid=[]
        for c in cites:
            a=articles[c['article_revision_id']]
            if a.get(c['field'],'')[c['start']:c['end']]!=c['quote']:raise ValueError('L1 引用內容與來源不符')
            evid.append({**c,'revision_id':a['revision_id'],'url':a['url'],'provider':a['provider'],'published_at':a['published_at'],'available_at':a['available_at'],'content_completeness':'summary_only','syndication_group':digest(re.sub(r'\W','',a['title'].casefold()))})
        candidates.append({'opinion_id':logical(n['id']),'revision_id':n['id'],'kind':n['kind'],'claim_id':n['id']+':claim','claim_type':n.get('opinion_metadata',{}).get('claim_type','inference' if n['kind']=='Thesis' else 'reported_claim'),'statement':n['summary'],'title':n['title'],'scope':n['scope'],'available_at':n['available_at'],'conditions':n.get('opinion_metadata',{}).get('conditions',[]),'horizon':n.get('opinion_metadata',{}).get('horizon'),'change_reason':n.get('opinion_metadata',{}).get('change_reason','legacy wrapper'),'legacy':'opinion_metadata' not in n,'evidence':evid,'labels':labels,'score':score,'selection_reason':'分類／全文相關' if score else '同股票時間窗內背景觀點'})
    # Keep contrary connected opinions only when they passed the same filters and time checks.
    candidates.sort(key=lambda n:(-n['score'],n['revision_id']))
    pool={n['revision_id']:n for n in candidates}
    broad=lens['query'].strip().lower() in ('動能','股票動能','momentum','風險','risk','總覽','overview')
    selected=[];narratives=set()
    for n in candidates:
        key=re.sub(r'\W','',n['statement'].casefold())
        if (broad or n['score']>0) and key not in narratives and len(selected)<20:
            selected.append(n);narratives.add(key)
    selected_ids={n['revision_id'] for n in selected}
    for e in edges:
        if e['relation_type']=='CONTRADICTS':
            a=e['source']['stable_id'];b=e['target']['stable_id']
            if a in selected_ids and b in pool and b not in selected_ids and len(selected)<24:selected.append(pool[b]);selected_ids.add(b)
            if b in selected_ids and a in pool and a not in selected_ids and len(selected)<24:selected.append(pool[a]);selected_ids.add(a)
    size=0;bounded=[]
    for n in selected:
        size+=len(encode(n))
        if size>65000:break
        bounded.append(n)
    selected=bounded;selected_ids={n['revision_id'] for n in selected}
    relations=[e for e in edges if e['source']['stable_id'] in selected_ids and e['target']['stable_id'] in selected_ids][:100]
    state=epochs(db)
    manifest={'schema':SCHEMA,'instrument':lens['instrument'],'cutoff':lens['time_spec']['as_of'],'epochs':state,'taxonomy_revision':tax['revision_id'],'source_revisions':sorted({e['revision_id'] for n in selected for e in n['evidence']}),'opinion_revisions':sorted(selected_ids),'enabled_retrieval_channels':['classification','full_text'],'classification_state':'partial','market_state':'unavailable','index_state':'transactional_scan','candidate_count':len(candidates),'selected_count':len(selected),'truncated':len(candidates)>len(selected),'excluded':excluded,'baseline':'unavailable','graph_expansion':{'hops':1,'max_nodes':24,'max_edges':100}}
    result={'lens':lens,'manifest':manifest,'opinions':selected,'relations':relations,'assignments':[a for a in assignments if a['opinion_revision'] in selected_ids],'features':[],'outcomes':[], 'computed_at':now(), 'gaps':['價格資料缺少可驗證的歷史可知性，價格動能 unavailable','沒有可比歷史敘事基線，不推斷敘事轉強','僅引用已取得的標題與摘要；新聞來源取得可能不完整','既有觀點採相容包裝，成立條件及展望未知','分類採可解釋詞彙規則，未分類仍可由全文召回']}
    manifest['snapshot_id']='snapshot-'+digest(result)
    # Exclude clock/observation timestamp from content fingerprint. Time eligibility itself is included.
    effective={'opinions':selected,'relations':relations,'taxonomy':tax,'query':lens['query'],'filter':lens['filter_ast'],'dimensions':lens['dimensions'],'time_policy':lens['time_policy'],'gaps':result['gaps']}
    result['input_hash']=digest(effective)
    return result

def validate_fusion(proposal,b):
    if not isinstance(proposal,dict) or set(proposal)!={'claims','summary','support','counter','narrative','gaps'}:raise ValueError('L2 輸出 schema 錯誤')
    known={n['claim_id']:n for n in b['opinions']};ids=set()
    if not isinstance(proposal['claims'],list) or len(proposal['claims'])>24:raise ValueError('L2 claims 過多')
    for c in proposal['claims']:
        if not isinstance(c,dict) or set(c)!={'id','statement','derived_from','assumptions','invalidating_conditions','type'}:raise ValueError('L2 claim 格式錯誤')
        if not isinstance(c['id'],str) or not re.fullmatch('c[1-9][0-9]?',c['id']) or c['id'] in ids:raise ValueError('L2 claim ID 錯誤')
        ids.add(c['id'])
        if not isinstance(c['statement'],str) or not 1<=len(c['statement'])<=2000:raise ValueError('L2 statement 長度錯誤')
        refs=c['derived_from']
        if not isinstance(refs,list) or not refs or any(r not in known for r in refs):raise ValueError('L2 引用不在 snapshot 白名單')
        if c['type'] not in ('inference','reported_claim'):raise ValueError('L2 claim type 錯誤')
        for field in ('assumptions','invalidating_conditions'):
            if not isinstance(c[field],list) or any(not isinstance(v,str) or len(v)>1000 for v in c[field]):raise ValueError('L2 條件格式錯誤')
        if c['type']=='inference' and (not c['assumptions'] or not c['invalidating_conditions']):raise ValueError('推論必須列出假設與失效條件')
        if c['type']=='reported_claim' and not any(c['statement'] in known[r]['statement'] for r in refs):raise ValueError('來源報導主張必須保留 L1 原文；新整合請標 inference 並列條件')
        supplied=' '.join(known[r]['statement']+' '+' '.join(e['quote'] for e in known[r]['evidence']) for r in refs)
        for number in re.findall(r'\d+(?:[.,]\d+)*%?',c['statement']):
            if number not in supplied:raise ValueError('L2 數值缺少對應來源')
        if re.search(r'轉強|轉弱|正在增強|正在減弱|strengthening|weakening',c['statement'],re.I):raise ValueError('缺少比較基線，不可宣稱動能變化')
    if proposal['claims'] and any(e['relation_type']=='CONTRADICTS' for e in b['relations']) and not proposal['counter']:raise ValueError('EvidenceBundle 有明確反證，L2 不可省略反證分支')
    for field in ('summary','support','counter','narrative'):
        if not isinstance(proposal[field],list) or any(x not in ids for x in proposal[field]):raise ValueError('摘要只能引用已驗證 claims')
    if not isinstance(proposal['gaps'],list) or any(not isinstance(g,str) or len(g)>1000 for g in proposal['gaps']):raise ValueError('L2 gaps 格式錯誤')
    return {**proposal,'price_momentum':{'status':'unavailable','features':[]},'baseline':'unavailable','content_status':'partial' if ids else 'insufficient_evidence','semantic_validation':'not_independently_verified','gaps':list(dict.fromkeys([*b['gaps'],*proposal['gaps']]))}

class Research:
    def __init__(self,store):self.store=store

    def prepare(self,body,clock=None):
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            tax=taxonomy(db);lens=parse_lens(body,self.store.instrument,tax,clock)
            b=bundle(db,lens);snapshot='snapshot-'+digest(b)
            return lens,b,snapshot

    def query(self,body):
        with self.store.connection() as db:
            if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone() or db.execute("SELECT 1 FROM research_jobs WHERE json_extract(payload,'$.operation')='classify_l1' AND status IN ('queued','running')").fetchone():
                raise ValueError('請先停止 L1 資料補足，再開始進階觀點分析；已保存的研究仍可閱讀。')
        lens,b,snapshot=self.prepare(body)
        model=body.get('model') or 'gpt-6.1-sol';effort=body.get('reasoning_effort') or 'high'
        if not isinstance(model,str) or len(model)>100 or effort not in ('low','medium','high','xhigh','max','ultra'):raise ValueError('模型設定錯誤')
        key=digest([OWNER,self.store.instrument,b['input_hash'],model,effort,SCHEMA,body.get('lens_id'),body.get('expected_revision')])
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for r in db.execute("SELECT * FROM research_jobs WHERE owner=? AND status IN ('queued','running','completed')",(OWNER,)):
                p=json.loads(r['payload'])
                if p.get('operation')!='classify_l1' and p['key']==key:
                    if r['status']=='completed' and not body.get('lens_id'):
                        previous=obj(db,p['run_id'],'run');previous_bundle=obj(db,previous['snapshot'],'snapshot')
                        if previous_bundle['lens']['time_spec']!=lens['time_spec']:
                            put(db,'snapshot',b,ident=snapshot)
                            reused={**previous,'snapshot':snapshot,'created_at':now(),'reused_from':p['run_id'],'usage':{}}
                            run_id=put(db,'run',reused);newid=uuid.uuid4().hex
                            payload={**p,'snapshot':snapshot,'run_id':run_id}
                            db.execute('INSERT INTO research_jobs VALUES (?,?,?,?,?,?,NULL)',(newid,OWNER,'completed',now(),now(),encode(payload)))
                            return {'job_id':newid,'status':'completed','lens':lens}
                    return {'job_id':r['id'],'status':r['status'],'lens':lens}
            if body.get('lens_id'):
                saved=self._lens(db,body['lens_id'])
                if saved['revision']!=body.get('expected_revision'):raise ValueError('研究條件已變更，請重新載入')
                if saved['mode']=='pinned':raise ValueError('固定快照不能刷新；請建立新的研究')
                if saved.get('input_hash')==b['input_hash'] and saved.get('run_id'):
                    saved.update(checked_epochs=b['manifest']['epochs'],checked_at=now(),last_error=None)
                    self._save(db,saved)
                    return {'status':'unchanged','run_id':saved['run_id'],'lens':lens}
            put(db,'snapshot',b,ident=snapshot)
            ident=uuid.uuid4().hex;stamp=now()
            payload={'key':key,'snapshot':snapshot,'model':model,'reasoning_effort':effort,'lens_id':body.get('lens_id'),'expected_revision':body.get('expected_revision'),'input_hash':b['input_hash']}
            db.execute('INSERT INTO research_jobs VALUES (?,?,?,?,?,?,NULL)',(ident,OWNER,'queued',stamp,stamp,encode(payload)))
            return {'job_id':ident,'status':'queued','lens':lens}

    def _lens(self,db,ident):
        r=db.execute('SELECT payload FROM research_lenses WHERE id=? AND owner=?',(ident,OWNER)).fetchone()
        if not r:raise ValueError('找不到此研究 Lens')
        return json.loads(r[0])

    def _save(self,db,saved):
        db.execute('INSERT INTO research_lenses VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at,payload=excluded.payload',(saved['id'],OWNER,saved['revision'],now(),encode(saved)))

    def save(self,body):
        if body.get('mode') not in ('live','pinned'):raise ValueError('請選擇持續追蹤或固定快照')
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE');run=obj(db,body['run_id'],'run');b=obj(db,run['snapshot'],'snapshot')
            ident='lens-'+digest([OWNER,body['run_id'],body['mode']]);revision=uuid.uuid4().hex
            old=db.execute('SELECT payload FROM research_lenses WHERE id=? AND owner=?',(ident,OWNER)).fetchone()
            if old:return json.loads(old[0])
            policy=dict(b['lens']['time_policy'])
            if body['mode']=='live':policy.update(cutoff_mode='rolling_now',fixed_as_of=None)
            saved={'id':ident,'revision':revision,'instrument':self.store.instrument,'mode':body['mode'],'lens':{**b['lens'],'time_policy':policy},'model':run['model'],'reasoning_effort':run['reasoning_effort'],'run_id':body['run_id'],'input_hash':b['input_hash'],'checked_epochs':b['manifest']['epochs'],'checked_at':now(),'history':[body['run_id']],'last_error':None}
            put(db,'lens_revision',saved,ident=revision);self._save(db,saved);return saved

    def refresh(self,body):
        with self.store.connection() as db:s=self._lens(db,body['lens_id'])
        if body.get('expected_revision')!=s['revision']:raise ValueError('研究條件已變更，請重新載入')
        lens=s['lens'];return self.query({'query':lens['query'],'filter_ast':lens['filter_ast'],'lookback_days':lens['time_policy']['lookback_days'],'model':s['model'],'reasoning_effort':s['reasoning_effort'],'lens_id':s['id'],'expected_revision':s['revision']})

    def read(self,kind,ident=None):
        with self.store.connection() as db:
            if kind=='runs':
                return {'runs':[{'id':r['id'],'created_at':r['created_at']} for r in db.execute("SELECT id,created_at FROM research_objects WHERE kind='run' AND owner=? ORDER BY created_at DESC LIMIT 20",(OWNER,))]}
            if kind=='run':
                r=obj(db,ident,'run');b=obj(db,r['snapshot'],'snapshot')
                return {**r,'bundle':b,'current_epochs':epochs(db)}
            if kind=='job':
                r=db.execute('SELECT * FROM research_jobs WHERE id=? AND owner=?',(ident,OWNER)).fetchone()
                if not r:raise ValueError('找不到研究工作')
                return {**dict(r),'payload':json.loads(r['payload'])}
            if kind=='taxonomy':
                from .classifier import enrich
                graph={'nodes':[json.loads(r[0]) for r in db.execute('SELECT payload FROM nodes')],'edges':[json.loads(r[0]) for r in db.execute('SELECT payload FROM edges')]}
                return enrich(db,graph)['taxonomy']
            if kind=='lenses':
                state=epochs(db);out=[]
                for r in db.execute('SELECT payload FROM research_lenses WHERE owner=? ORDER BY updated_at DESC',(OWNER,)):
                    s=json.loads(r[0]);stale=s['checked_epochs']!=state or instant(s['checked_at']).date()!=instant(now()).date() or bool(state['pending'])
                    s['refresh_state']='pinned' if s['mode']=='pinned' else 'failed' if s.get('last_error') else 'stale' if stale else 'fresh';out.append(s)
                return {'lenses':out,'epochs':state}
        raise ValueError('未知研究讀取操作')

    def source_status(self,body):
        if body.get('status') not in ('active','corrected','retracted') or not isinstance(body.get('reason'),str) or not 1<=len(body['reason'])<=500:raise ValueError('來源狀態與理由錯誤')
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM articles WHERE id=?',(body.get('revision_id'),)).fetchone():raise ValueError('來源不屬於此股票')
            event={'revision_id':body['revision_id'],'status':body['status'],'reason':body['reason'],'known_at':now(),'committed_at':now()}
            put(db,'source_status',event,'');return event

    def candidate(self,body):
        text=body.get('text','').strip();facet=body.get('facet')
        if not 1<=len(text)<=120 or facet not in ('topic','driver','analysis_dimension'):raise ValueError('候選詞格式錯誤')
        with self.store.connection() as db:
            tax=taxonomy(db)
            matches_=[t['id'] for t in tax['terms'] if t['facet']==facet and text.casefold() in [x.casefold() for x in [t['label'],*t['aliases']]]]
            if matches_:return {'status':'mapped','term_ids':matches_}
            record={'text':text,'facet':facet,'taxonomy_revision':tax['revision_id'],'status':'candidate','reason':'尚無確定同義詞；待維護者定義，不直接建立正式分類'}
            ident=put(db,'candidate_term',record,'');return {**record,'id':ident}

    def update_taxonomy(self,body):
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE');old=taxonomy(db)
            if body.get('expected_revision')!=old['revision_id']:raise ValueError('分類版本衝突')
            terms=body.get('terms')
            if not isinstance(terms,list) or not 1<=len(terms)<=200:raise ValueError('分類數量錯誤')
            ids=set()
            terms=[{k:v for k,v in t.items() if k not in ('color','opinion_ids','node_ids')} for t in terms]
            for t in terms:
                if set(t)!={'id','facet','label','aliases','definition','include','exclude','related_terms','status'} or t['facet'] not in ('topic','driver','analysis_dimension') or not re.fullmatch(r'(topic|driver|analysis)\.[a-z_]+',t['id']) or t['id'] in ids:raise ValueError('分類格式或 ID 錯誤')
                ids.add(t['id'])
                prefix={'topic':'topic','driver':'driver','analysis_dimension':'analysis'}[t['facet']]
                if not t['id'].startswith(prefix+'.') or any(not isinstance(t[k],str) or not 1<=len(t[k])<=1000 for k in ('label','definition')):raise ValueError('分類定義或 facet 錯誤')
                previous=next((x for x in old['terms'] if x['id']==t['id']),None)
                if previous and previous['facet']!=t['facet']:raise ValueError('穩定 ID 不可變更 facet')
                for k in ('aliases','include','exclude','related_terms'):
                    if not isinstance(t[k],list) or any(not isinstance(x,str) or len(x)>200 for x in t[k]):raise ValueError('分類清單格式錯誤')
                if t['status'] not in ('active','deprecated'):raise ValueError('分類狀態錯誤')
            if not {t['id'] for t in old['terms']}<=ids:raise ValueError('穩定 ID 不可刪除，請標 deprecated')
            new={'revision_id':uuid.uuid4().hex,'available_at':now(),'terms':terms};put(db,'taxonomy',new,'',new['revision_id']);return new

    def observe_news(self,news):
        if not hasattr(news,'for_ticker'):return
        path=news.data_root/'graph'/self.store.instrument.split(':')[1]/'news-atlas.sqlite3'
        if not path.exists():return
        import sqlite3
        from .store import capture
        import contextlib
        with contextlib.closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles')]
        revisions=[]
        for r in rows:
            try:revisions.append(capture(r))
            except ValueError:continue
        self.store.ingest(revisions)

    def refresh_live(self):
        # Saved live is explicit ongoing authorization. Failure blocks automatic paid retry.
        with self.store.connection() as db:
            if db.execute("SELECT 1 FROM research_jobs WHERE status IN ('queued','running')").fetchone():return
        for s in self.read('lenses')['lenses']:
            if s['mode']=='live' and s['refresh_state']=='stale' and not s.get('last_error'):
                self.refresh({'lens_id':s['id'],'expected_revision':s['revision']})
                return  # bounded one candidate per stock/worker round

    def process(self,service):
        with self.store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            r=db.execute("SELECT * FROM research_jobs WHERE status='queued' AND COALESCE(json_extract(payload,'$.operation'),'')!='classify_l1' ORDER BY created_at LIMIT 1").fetchone()
            if not r:return
            job=dict(r);p=json.loads(job['payload']);b=obj(db,p['snapshot'],'snapshot')
            db.execute("UPDATE research_jobs SET status='running',updated_at=? WHERE id=?",(now(),job['id']))
        service.active=(self.store,job['id'])
        try:
            if not b['opinions']:
                response={'proposal':{'claims':[],'summary':[],'support':[],'counter':[],'narrative':[],'gaps':['沒有符合硬條件的 L1；未放寬篩選']},'usage':{}}
            else:
                response=service.runner(self.store,{'id':job['id'],'payload':{**p,'operation':'research_fusion','languages':['zh-Hant']}},{'research_bundle':b},[])
            with self.store.connection() as db:put(db,'model_receipt',{'job_id':job['id'],'phase':'fusion','usage':response.get('usage',{}),'recorded_at':now()},ident=job['id']+':fusion')
            result=validate_fusion(response['proposal'],b)
            if any(c['type']=='inference' for c in result['claims']):
                # One bounded semantic check only for new synthesis. Exact L1 excerpts do
                # not consume another call. A rejection keeps the last successful result.
                checked=service.runner(self.store,{'id':job['id'],'payload':{**p,'operation':'research_review','languages':['zh-Hant']}},{'research_bundle':b,'candidate':result},[])
                with self.store.connection() as db:put(db,'model_receipt',{'job_id':job['id'],'phase':'semantic_review','usage':checked.get('usage',{}),'recorded_at':now()},ident=job['id']+':review')
                audit=checked.get('proposal',{})
                if audit.get('assessment')!='pass' or set(audit.get('checked_claim_ids',[]))!={c['id'] for c in result['claims']} or any(i.get('severity')=='error' for i in audit.get('issues',[])):
                    raise ValueError('語意支持檢查未通過；保留前版，不自動重試')
                result['semantic_validation']='model_checked_not_proven';result['semantic_review']=audit
                totals=dict(response.get('usage',{}))
                for key,value in checked.get('usage',{}).items():
                    if type(value)==int:totals[key]=totals.get(key,0)+value
                response['usage']=totals

            with self.store.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT status FROM research_jobs WHERE id=?',(job['id'],)).fetchone()[0]!='running':return
                run={'snapshot':p['snapshot'],'result':result,'model':p['model'],'reasoning_effort':p['reasoning_effort'],'usage':response.get('usage',{}),'created_at':now(),'schema':SCHEMA,'input_hash':b['input_hash']}
                runid=put(db,'run',run);p['run_id']=runid
                if p.get('lens_id'):
                    s=self._lens(db,p['lens_id'])
                    if s['revision']!=p['expected_revision']:raise ValueError('CAS 衝突，保留既有 Lens 結果')
                    s.update(run_id=runid,input_hash=b['input_hash'],checked_at=now(),checked_epochs=b['manifest']['epochs'],last_error=None,revision=uuid.uuid4().hex,history=[*s['history'],runid])
                    put(db,'lens_revision',s,ident=s['revision']);self._save(db,s)
                db.execute("UPDATE research_jobs SET status='completed',payload=?,updated_at=? WHERE id=?",(encode(p),now(),job['id']))
        except Exception as error:
            with self.store.connection() as db:
                db.execute("UPDATE research_jobs SET status='failed',error=?,updated_at=? WHERE id=?",(str(error)[:600],now(),job['id']))
                if p.get('lens_id'):
                    s=self._lens(db,p['lens_id']);s['last_error']=str(error)[:600];self._save(db,s)
        finally:service.active=None


def handle_research(handler,service,path,params,can_write):
    if not enabled():handler.json_response(404,{'error':'Research disabled'});return
    # Single-user local authority, same-origin access on reads as well as writes.
    if not can_write:handler.json_response(403,{'error':'研究僅開放已允許的本機來源'});return
    if handler.command=='GET':
        body={k:v[0] for k,v in params.items()}
    else:
        length=int(handler.headers.get('Content-Length','0'))
        if handler.headers.get('Content-Type','').split(';')[0]!='application/json' or not 0<length<=200000:raise ValueError('研究請求格式或大小錯誤')
        body=json.loads(handler.rfile.read(length))
    if not isinstance(body,dict) or 'owner' in body or 'owner_id' in body:raise ValueError('研究 owner 由服務端決定')
    from .store import instrument, folder_name
    stock=instrument(body.get('instrument',''))
    if not (service.root/folder_name(stock)/'wiki.sqlite3').exists():raise ValueError('請先建立此股票的 L1 Wiki')
    if path in ('query','refresh','availability'):
        active=[s.instrument for s in service.stores() if any(j['status'] in ('queued','running') for j in s.jobs())]
        for s in service.stores():
            with s.connection() as db:
                if db.execute("SELECT 1 FROM research_jobs WHERE json_extract(payload,'$.operation')='classify_l1' AND status IN ('queued','running')").fetchone() and s.instrument not in active:active.append(s.instrument)
        if path=='availability':
            with service.store(stock).connection() as db:
                job=db.execute("SELECT id,status FROM research_jobs WHERE owner=? AND coalesce(json_extract(payload,'$.operation'),'')!='classify_l1' AND status IN ('queued','running') ORDER BY created_at LIMIT 1",(OWNER,)).fetchone()
            handler.json_response(200,{'busy':bool(active),'instruments':active,'active_job':dict(job) if job else None});return
        if active:raise ValueError('請先停止 L1 資料補足，再開始進階觀點分析：'+', '.join(active))
    research=Research(service.store(stock));research.observe_news(service.news)
    if handler.command=='GET':result=research.read(path,body.get('id'))
    elif path=='query':result=research.query(body);service.wake.set()
    elif path=='save':result=research.save(body)
    elif path=='refresh':result=research.refresh(body);service.wake.set()
    elif path=='taxonomy':result=research.update_taxonomy(body)
    elif path=='source-status':result=research.source_status(body)
    elif path=='candidate':result=research.candidate(body)
    else:raise ValueError('未知研究操作')
    handler.json_response(202 if result.get('status')=='queued' else 200,result)
