"""Per-instrument append-only knowledge versions and durable compilation jobs."""
import contextlib
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid

PROMPT_VERSION = 'wiki-extract-v1'
KINDS = ('Claim', 'Event', 'Thesis')
RELATIONS = ('SUPPORTS', 'CONTRADICTS', 'UPDATES', 'DEPENDS_ON', 'RELATED_TO', 'TEMPORALLY_PRECEDES')

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()

def instrument(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Z][A-Z0-9_-]{1,15}:[A-Z0-9][A-Z0-9.-]{0,19}',value):
        raise ValueError('請填入交易所與股票，例如 NASDAQ:TSLA')
    return value

def capture(row):
    if not isinstance(row,dict): raise ValueError('無效新聞')
    provider=row.get('source',{}).get('provider') if isinstance(row.get('source'),dict) else None
    if provider not in ('google','yahoo','massive') or not re.fullmatch(r'[a-f0-9]{24}',str(row.get('id',''))): raise ValueError('無效新聞來源／ID')
    out={k:row.get(k) for k in ('id','title','summary','url','published_at')}
    out['summary']=out['summary'] or ''
    if not isinstance(out['title'],str) or not 1<=len(out['title'])<=2000 or not isinstance(out['summary'],str) or len(out['summary'])>12000: raise ValueError('新聞標題／摘要長度錯誤')
    if not isinstance(out['url'],str) or not re.match(r'^https?://[^\s]+$',out['url']): raise ValueError('新聞網址錯誤')
    if out['published_at'] is not None:
        if not isinstance(out['published_at'],str): raise ValueError('新聞日期錯誤')
        stamp=dt.datetime.fromisoformat(out['published_at'].replace('Z','+00:00'))
        if stamp.tzinfo is None: raise ValueError('新聞日期必須含時區')
    out['provider']=provider
    out['content_hash']=digest(out)
    out['revision_id']='article-'+out['content_hash']
    return out

class WikiStore:
    def __init__(self, root, ident, fixture=False):
        self.instrument=instrument(ident)
        self.folder=Path(root)/digest(ident)[:24]
        self.folder.mkdir(parents=True,exist_ok=True)
        self.path=self.folder/'wiki.sqlite3'
        self.fixture=fixture
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, captured_at TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions (version INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,job_id TEXT NOT NULL,model TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY,kind TEXT NOT NULL,created_version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS edges (id TEXT PRIMARY KEY,source TEXT NOT NULL,target TEXT NOT NULL,created_version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS extractions (revision TEXT NOT NULL,model TEXT NOT NULL,prompt TEXT NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(revision,model,prompt));
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,done INTEGER NOT NULL DEFAULT 0,error TEXT,usage TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY,day TEXT NOT NULL,job_id TEXT NOT NULL,revision TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS edges_endpoints ON edges(source,target,created_version);
            CREATE INDEX IF NOT EXISTS nodes_version ON nodes(created_version DESC,id);
            PRAGMA user_version=1;
            ''')
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('instrument',encode(ident)))
            actual=json.loads(db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()[0])
            if actual!=ident: raise ValueError('Wiki資料庫股票識別不符')

    @contextlib.contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    def config(self):
        with self.connection() as db:
            row=db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
        return json.loads(row[0]) if row else {'enabled':False,'batch_size':5,'daily_limit':20,'model':'','subscriptions':[]}

    def configure(self,value):
        with self.connection() as db: db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('config',encode(value)))

    def ingest(self, rows):
        with self.connection() as db:
            stamp=now()
            for a in rows:
                db.execute('INSERT OR IGNORE INTO articles VALUES (?,?,?,?)',(a['revision_id'],a['provider']+':'+a['id'],stamp,encode(a)))

    def pending(self,model,limit=20):
        with self.connection() as db:
            rows=db.execute('''SELECT a.payload FROM articles a WHERE NOT EXISTS
                (SELECT 1 FROM extractions e WHERE e.revision=a.id AND e.model=? AND e.prompt=?)
                ORDER BY a.captured_at,a.id LIMIT ?''',(model,PROMPT_VERSION,limit)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def known(self,rows,model):
        with self.connection() as db:
            known={r[0] for r in db.execute('SELECT revision FROM extractions WHERE model=? AND prompt=?',(model,PROMPT_VERSION))}
        return [r for r in rows if r['revision_id'] not in known]

    def enqueue(self,model,limit,daily_limit):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute("SELECT id FROM jobs WHERE status IN ('queued','running') LIMIT 1").fetchone()
            if active: return active[0]
            rows=db.execute('''SELECT a.id FROM articles a WHERE NOT EXISTS
                (SELECT 1 FROM extractions e WHERE e.revision=a.id AND e.model=? AND e.prompt=?)
                ORDER BY a.captured_at,a.id LIMIT ?''',(model,PROMPT_VERSION,limit)).fetchall()
            ident=uuid.uuid4().hex;stamp=now()
            payload={'model':model,'daily_limit':daily_limit,'revisions':[r[0] for r in rows],'prompt_version':PROMPT_VERSION}
            db.execute('INSERT INTO jobs(id,created_at,updated_at,status,payload) VALUES (?,?,?,?,?)',(ident,stamp,stamp,'queued' if rows else 'completed',encode(payload)))
        return ident

    def jobs(self):
        with self.connection() as db:
            return [dict(r, payload=json.loads(r['payload']),usage=json.loads(r['usage'])) for r in db.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 30')]

    def cancel(self,ident):
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM jobs WHERE id=?',(ident,)).fetchone(): raise ValueError('工作不存在')
            db.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE id=? AND status IN ('queued','running')",(now(),ident))

    def reserve_call(self,job,revision):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            state=db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()
            if not state or state[0]!='running': return False
            n=db.execute('SELECT count(*) FROM calls WHERE day=?',(now()[:10],)).fetchone()[0]
            if n>=job['payload']['daily_limit']:
                db.execute("UPDATE jobs SET status='budget_paused',error='已達每日篇數上限',updated_at=? WHERE id=?",(now(),job['id']))
                return False
            db.execute('INSERT INTO calls VALUES (?,?,?,?)',(uuid.uuid4().hex,now()[:10],job['id'],revision))
        return True

    def context(self,article):
        words=set(re.findall(r'\w+|[\u4e00-\u9fff]',article['title'].lower()))
        with self.connection() as db:
            nodes=[json.loads(r[0]) for r in db.execute("SELECT payload FROM nodes WHERE kind!='ArticleRevision' ORDER BY created_version DESC LIMIT 500")]
        nodes.sort(key=lambda n:len(words & set(re.findall(r'\w+|[\u4e00-\u9fff]',(n['title']+' '+n.get('scope','')).lower()))),reverse=True)
        return [{k:n[k] for k in ('id','kind','title','scope')} for n in nodes[:12]]

    def publish(self,job,article,proposal,context,usage):
        nodes,edges=validate_proposal(article,proposal,context)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            state=db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()
            if not state or state[0]!='running': return False
            if db.execute('SELECT 1 FROM extractions WHERE revision=? AND model=? AND prompt=?',(article['revision_id'],job['payload']['model'],PROMPT_VERSION)).fetchone(): return True
            stamp=now();version=db.execute('INSERT INTO versions(created_at,job_id,model) VALUES (?,?,?)',(stamp,job['id'],job['payload']['model'])).lastrowid
            article_node={'id':article['revision_id'],'kind':'ArticleRevision','title':article['title'],'summary':article['summary'],'scope':self.instrument,'url':article['url'],'provider':article['provider'],'published_at':article['published_at'],'content_hash':article['content_hash'],'status':'source','citations':[]}
            all_nodes={n['id']:n for n in [article_node,*nodes]}
            all_nodes.update({n['id']:n for n in context})
            for n in [article_node,*nodes]:
                n={**n,'available_at':stamp,'version':version,'is_fixture':self.fixture}
                db.execute('INSERT OR IGNORE INTO nodes VALUES (?,?,?,?)',(n['id'],n['kind'],version,encode(n)))
            for edge in edges:
                source=all_nodes[edge['source']];target=all_nodes[edge['target']]
                ident='edge-'+digest([edge['source'],edge['target'],edge['type'],edge['citations']])
                endpoint=lambda n:{'stable_id':n['id'],'revision_id':n['id'],'kind':n['kind']}
                record={'schema_version':'0.1','is_fixture':self.fixture,'instrument_id':self.instrument,'ticker':self.instrument.split(':')[1],
                    'stable_id':ident,'revision_id':ident,'run_id':job['id'],'mode':'live_recorded','relation_type':edge['type'],
                    'source':endpoint(source),'target':endpoint(target),'status':'hypothesis' if edge['type']=='RELATED_TO' else 'proposed',
                    'scope':target.get('scope',self.instrument),'rationale':edge['rationale'],'event_time':None,'available_at':stamp,'produced_at':stamp,
                    'decision_as_of':stamp,'simulated_effective_at':None,'evidence_refs':edge['citations'],
                    'scores':{'semantic_similarity':None,'evidence_quality':None,'predictive_association':None},
                    'provenance':{'producer':'llm_proposal','model_revision':job['payload']['model'],'prompt_version':PROMPT_VERSION,'input_hash':article['content_hash'],'patch_id':job['id']+':'+article['revision_id']}}
                db.execute('INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?)',(ident,edge['source'],edge['target'],version,encode(record)))
            db.execute('INSERT INTO extractions VALUES (?,?,?,?)',(article['revision_id'],job['payload']['model'],PROMPT_VERSION,version))
            old=json.loads(db.execute('SELECT usage FROM jobs WHERE id=?',(job['id'],)).fetchone()[0])
            totals=dict(old)
            for k,v in usage.items():
                if isinstance(v,int) and not isinstance(v,bool) and v>=0: totals[k]=old.get(k,0)+v
            db.execute('UPDATE jobs SET done=done+1,updated_at=?,usage=? WHERE id=?',(stamp,encode(totals),job['id']))
        return True

    def graph(self,version=None,as_of=None,limit=2400):
        with self.connection() as db:
            versions=[dict(r) for r in db.execute('SELECT * FROM versions ORDER BY version DESC LIMIT 100')]
            if as_of:
                stamp=dt.datetime.fromisoformat(as_of.replace('Z','+00:00'))
                if stamp.tzinfo is None: raise ValueError('as_of必須含時區')
                stamp=stamp.astimezone(dt.timezone.utc).isoformat()
                chosen=db.execute('SELECT max(version) FROM versions WHERE created_at<=?',(stamp,)).fetchone()[0] or 0
            elif version is not None:
                chosen=int(version)
                if chosen<0 or (chosen and not db.execute('SELECT 1 FROM versions WHERE version=?',(chosen,)).fetchone()): raise ValueError('版本不存在')
            else: chosen=versions[0]['version'] if versions else 0
            nodes=[json.loads(r[0]) for r in db.execute('SELECT payload FROM nodes WHERE created_version<=? ORDER BY created_version DESC,id LIMIT ?',(chosen,limit))]
            edges=[json.loads(r[0]) for r in db.execute('''WITH visible AS (
                SELECT id FROM nodes WHERE created_version<=? ORDER BY created_version DESC,id LIMIT ?)
                SELECT e.payload FROM edges e JOIN visible s ON e.source=s.id
                JOIN visible t ON e.target=t.id WHERE e.created_version<=?''',(chosen,limit,chosen))]
            total=db.execute('SELECT count(*) FROM nodes WHERE created_version<=?',(chosen,)).fetchone()[0]
            count=db.execute('SELECT count(*) FROM articles').fetchone()[0]
        return {'instrument':self.instrument,'mode':'live_recorded','version':chosen,'versions':versions,'nodes':nodes,'edges':edges,'total_nodes':total,'captured_articles':count,'truncated':total>len(nodes),'config':self.config(),'jobs':self.jobs()}

    def markdown(self,version=None):
        graph=self.graph(version=version)
        lines=[f"# {self.instrument} Wiki",f"版本 {graph['version']} · live_recorded",'引用已核對原文；LLM陳述仍為提案，並非已驗證事實。','']
        for n in graph['nodes']:
            lines.extend([f"## {n['kind']}: {n['title']}",n.get('summary','')])
            for c in n.get('citations',[]): lines.append(f"> {c['quote']}\n\n來源版本：{c['article_revision_id']}，{c['field']}[{c['start']}:{c['end']}]")
        if graph['truncated']: lines.append('此匯出受2400節點上限限制。')
        return '\n\n'.join(lines)

def validate_proposal(article,proposal,context):
    if not isinstance(proposal,dict) or set(proposal)!= {'nodes','relations'}: raise ValueError('LLM輸出必須包含nodes及relations')
    ns=proposal['nodes']; rs=proposal['relations']
    if not isinstance(ns,list) or len(ns)>8 or not isinstance(rs,list) or len(rs)>16: raise ValueError('LLM輸出超出單篇上限')
    def citations(values):
        if not isinstance(values,list) or not 1<=len(values)<=5: raise ValueError('每項陳述都必須附1–5段引用')
        result=[]
        for c in values:
            if not isinstance(c,dict) or c.get('revision_id')!=article['revision_id'] or c.get('field') not in ('title','summary'): raise ValueError('引用版本不在本次證據內')
            text=article[c['field']];quote=c.get('quote')
            if not isinstance(quote,str) or not 3<=len(quote)<=2000 or quote not in text: raise ValueError('LLM引用無法在原文逐字核對')
            start=text.index(quote)
            if any(r['field']==c['field'] and r['quote']==quote for r in result): continue
            result.append({'article_revision_id':article['revision_id'],'content_hash':article['content_hash'],'field':c['field'],'start':start,'end':start+len(quote),'quote':quote})
        return result
    nodes=[];mapped={n['id']:n for n in context};edges=[]
    for n in ns:
        if not isinstance(n,dict) or n.get('kind') not in KINDS or not isinstance(n.get('key'),str) or not re.fullmatch(r'n[0-9]{1,2}',n['key']) or n['key'] in mapped: raise ValueError('無效Wiki節點')
        for field,cap in [('title',250),('summary',2000),('scope',250)]:
            if not isinstance(n.get(field),str) or not 1<=len(n[field])<=cap: raise ValueError('無效Wiki文字欄位')
        refs=citations(n.get('citations'));ident='node-'+digest([n['kind'],n['title'],n['summary'],n['scope']])
        node={'id':ident,'kind':n['kind'],'title':n['title'],'summary':n['summary'],'scope':n['scope'],'status':'hypothesis' if n['kind']=='Thesis' else 'proposed','citations':refs}
        mapped[n['key']]=node;nodes.append(node)
        edges.append({'source':article['revision_id'],'target':ident,'type':'SUPPORTS','rationale':'原文支持此LLM提案；只核對引用，不代表陳述已證實。','citations':refs})
    for r in rs:
        if not isinstance(r,dict) or not isinstance(r.get('source'),str) or not isinstance(r.get('target'),str): raise ValueError('無效Wiki關聯')
        a=mapped.get(r['source']);b=mapped.get(r['target']);kind=r.get('type')
        if not a or not b or a['id']==b['id'] or kind not in RELATIONS or r['source'] not in {n['key'] for n in ns}: raise ValueError('關聯只能由本次新節點指向本次或檢索節點')
        if kind=='DEPENDS_ON' and a['kind']!='Thesis': raise ValueError('DEPENDS_ON方向錯誤')
        if kind=='TEMPORALLY_PRECEDES' and (a['kind']!='Event' or b['kind']!='Event'): raise ValueError('時間順序只能連接事件')
        if kind in ('SUPPORTS','CONTRADICTS') and a['kind']=='Thesis': raise ValueError('觀點不能充當已核對證據')
        if kind=='CONTRADICTS' and a['scope']!=b['scope']: raise ValueError('反證必須屬於相同命題範圍')
        if not isinstance(r.get('rationale'),str) or not 1<=len(r['rationale'])<=1000: raise ValueError('關聯必須包含理由')
        edges.append({'source':a['id'],'target':b['id'],'type':kind,'rationale':r['rationale'],'citations':citations(r.get('citations'))})
    return nodes,edges
