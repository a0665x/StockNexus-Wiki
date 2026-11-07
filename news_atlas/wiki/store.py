"""Per-instrument append-only knowledge versions and durable compilation jobs."""
import contextlib
import datetime as dt
import hashlib
import heapq
import json
from pathlib import Path
import re
import sqlite3
import uuid

PROMPT_VERSION = 'wiki-extract-v8'
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

def folder_name(ident):
    return instrument(ident).split(':',1)[1]


def migrate_legacy(data):
    """Called at service startup, after the previous server has stopped."""
    data=Path(data)
    legacy=data/'research'
    for path in sorted(legacy.glob('*/wiki.sqlite3')):
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            row=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
        if not row:raise ValueError('舊 Wiki 缺少股票識別')
        ident=instrument(json.loads(row[0]))
        if path.parent.name!=digest(ident)[:24]:raise ValueError('舊 Wiki 路徑與股票不符')
        dest=data/'llm_wiki'/folder_name(ident)
        if dest.exists():raise ValueError('新舊 Wiki 同時存在，請先以 merge_data.sh 合併，勿覆蓋：'+str(dest))
        dest.parent.mkdir(parents=True,exist_ok=True)
        # Rename the whole folder, including WAL/SHM, on the same filesystem.
        path.parent.rename(dest)


class WikiStore:
    def __init__(self, root, ident, fixture=False):
        self.instrument=instrument(ident)
        self.folder=Path(root)/folder_name(ident)
        self.folder.mkdir(parents=True,exist_ok=True)
        self.path=self.folder/'wiki.sqlite3'
        self.fixture=fixture
        with self.connection() as db:
            if db.execute('PRAGMA user_version').fetchone()[0]>1:raise ValueError('Newer database format; update application before opening')
            # A normal read must not acquire SQLite's writer lock. Migrate only
            # incomplete schemas; never cache row data or skip stock validation.
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            required={'metadata','articles','versions','nodes','edges','extractions','jobs','review_coverage','reviews','calls','rejected_proposals','research_objects','research_lenses','research_jobs'}
            if required<=tables:
                row=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
                if row:
                    if json.loads(row[0])!=self.instrument:raise ValueError('Wiki資料庫股票識別不符')
                    return
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, captured_at TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions (version INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,job_id TEXT NOT NULL,model TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY,kind TEXT NOT NULL,created_version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS edges (id TEXT PRIMARY KEY,source TEXT NOT NULL,target TEXT NOT NULL,created_version INTEGER NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS extractions (revision TEXT NOT NULL,model TEXT NOT NULL,prompt TEXT NOT NULL,version INTEGER NOT NULL,PRIMARY KEY(revision,model,prompt));
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,done INTEGER NOT NULL DEFAULT 0,error TEXT,usage TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS review_coverage (revision TEXT PRIMARY KEY,evidence_epoch INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews (job_id TEXT NOT NULL,revision TEXT NOT NULL,PRIMARY KEY(job_id,revision));
            CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY,day TEXT NOT NULL,job_id TEXT NOT NULL,revision TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS rejected_proposals (id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,revision TEXT NOT NULL,created_at TEXT NOT NULL,error TEXT NOT NULL,proposal TEXT,usage TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS edges_endpoints ON edges(source,target,created_version);
            CREATE INDEX IF NOT EXISTS nodes_version ON nodes(created_version DESC,id);
            PRAGMA user_version=1;
            ''')
            from .research import migrate
            migrate(db)
            from .research import taxonomy
            taxonomy(db)
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
        return json.loads(row[0]) if row else {'enabled':False,'model':'','subscriptions':[]}

    def configure(self,value):
        with self.connection() as db: db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('config',encode(value)))

    def ingest(self, rows):
        with self.connection() as db:
            stamp=now()
            for a in rows:
                db.execute('INSERT OR IGNORE INTO articles VALUES (?,?,?,?)',(a['revision_id'],a['provider']+':'+a['id'],stamp,encode(a)))

    def pending(self,model=None,limit=20,revision_ids=None,review=False):
        # Coverage is evidence-based, not tied to model/prompt/UI settings.
        with self.connection() as db:
            rows=db.execute("""SELECT a.payload FROM articles a WHERE
                (? OR NOT EXISTS (SELECT 1 FROM extractions e WHERE e.revision=a.id))
                AND (? IS NULL OR a.id IN (SELECT value FROM json_each(?)))
                AND (NOT ? OR (EXISTS (SELECT 1 FROM extractions e WHERE e.revision=a.id)
                AND EXISTS (SELECT 1 FROM edges l JOIN nodes n ON n.id=l.target
                    WHERE l.source=a.id AND n.kind!='ArticleRevision')))
                ORDER BY json_extract(a.payload,'$.published_at') DESC,a.id LIMIT ?""",
                (review,None if revision_ids is None else 1,encode(revision_ids or []),review,limit)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def known(self,rows,model=None):
        with self.connection() as db:
            known={r[0] for r in db.execute('SELECT DISTINCT revision FROM extractions')}
        return [r for r in rows if r['revision_id'] not in known]

    def enqueue(self,model,limit=10000,daily_limit=None,revision_ids=None,operation='update'):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute("SELECT id FROM jobs WHERE status IN ('queued','running') LIMIT 1").fetchone()
            if active: return active[0]
            rows=self.pending(model,limit,revision_ids,review=operation=='review')
            ident=uuid.uuid4().hex;stamp=now()
            payload={**{k:self.config()[k] for k in ('reasoning_effort','languages','evidence_size','strategy','graph_edges','graph_settings','price_horizon','settings_version','graph_selection','graph_universe') if k in self.config()},'context_revisions':self.config().get('graph_context_revisions',self.config().get('revision_ids')) if self.config().get('strategy')=='root' else None,'model':model,'revisions':[r['revision_id'] for r in rows],'prompt_version':PROMPT_VERSION,'operation':operation}
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
            db.execute('INSERT INTO calls VALUES (?,?,?,?)',(uuid.uuid4().hex,now()[:10],job['id'],revision))
        return True

    def context(self,article):
        terms=lambda text:set(re.findall(r'[a-z0-9_]+|[\u4e00-\u9fff]',text.lower()))
        words=terms(article['title']+' '+article['summary'][:2000])
        with self.connection() as db:
            prior={r[0] for r in db.execute("SELECT e.target FROM edges e JOIN articles a ON a.id=e.source WHERE a.source_id=?",(article['provider']+':'+article['id'],))}
            def candidates():
                for row in db.execute("SELECT payload FROM nodes WHERE kind!='ArticleRevision'"):
                    n=json.loads(row[0])
                    if article.get('_context_revisions') is not None and not any(c['article_revision_id'] in article['_context_revisions'] for c in n.get('citations',[])):continue
                    score=len(words & terms(n['title']+' '+n.get('scope','')))
                    if score or n['id'] in prior: yield (n['id'] in prior,score,n['id'],n)
            best=heapq.nlargest(12,candidates(),key=lambda x:x[:3])
        selected=[n for _,_,_,n in best]
        # Include direct dependents so a changed premise can revise an existing thesis.
        with self.connection() as db:
            ids=[n['id'] for n in selected]
            dependent=[json.loads(r[0]) for r in db.execute("SELECT DISTINCT n.payload FROM nodes n JOIN edges e ON e.source=n.id WHERE e.target IN (SELECT value FROM json_each(?)) AND n.kind='Thesis' ORDER BY n.created_version DESC LIMIT 4",(encode(ids),))]
        if article.get('_context_revisions') is not None:dependent=[n for n in dependent if any(c['article_revision_id'] in article['_context_revisions'] for c in n.get('citations',[]))]
        selected=list({n['id']:n for n in [*dependent,*selected]}.values())[:12]
        with self.connection() as db:
            current={a['revision_id'] for a in article.get('_evidence',[article])}
            candidates=[]
            for row in db.execute("SELECT payload FROM nodes WHERE kind='ArticleRevision'"):
                n=json.loads(row[0])
                if article.get('_context_revisions') is not None and n['id'] not in article['_context_revisions']:continue
                score=len(words & terms(n['title']))
                if n['id'] not in current and score:candidates.append((score,n['id'],n))
            related=[n for _,_,n in heapq.nlargest(4,candidates,key=lambda x:x[:2])]
        return [{k:n[k] for k in ('id','kind','title','scope','summary','assessment','content_hash','url','published_at','provider') if k in n} for n in [*selected[:12-len(related)],*related]]

    def publish(self,job,article,proposal,context,usage):
        nodes,edges=validate_proposal(article,proposal,context)
        evidence=article.get('_evidence',[article]);covered=article.get('_covered_articles',evidence)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            state=db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()
            if not state or state[0]!='running': return False
            review=job['payload'].get('operation')=='review'
            if not review and db.execute('SELECT 1 FROM extractions WHERE revision=?',(article['revision_id'],)).fetchone(): return True
            if review and db.execute('SELECT 1 FROM reviews WHERE job_id=? AND revision=?',(job['id'],article['revision_id'])).fetchone(): return True
            for edge in edges:
                if edge['type']=='UPDATES' and db.execute("SELECT 1 FROM edges WHERE target=? AND json_extract(payload,'$.relation_type')='UPDATES'",(edge['target'],)).fetchone():
                    raise ValueError('L1 revision conflict: the base opinion already has a newer revision')
            stamp=now();version=db.execute('INSERT INTO versions(created_at,job_id,model) VALUES (?,?,?)',(stamp,job['id'],job['payload']['model'])).lastrowid
            article_node={'id':article['revision_id'],'kind':'ArticleRevision','title':article['title'],'summary':article['summary'],'scope':self.instrument,'url':article['url'],'provider':article['provider'],'published_at':article['published_at'],'content_hash':article['content_hash'],'status':'source','citations':[]}
            article_nodes=[dict(article_node,id=a['revision_id'],title=a['title'],summary=a['summary'],url=a['url'],provider=a['provider'],published_at=a['published_at'],content_hash=a['content_hash']) for a in evidence]
            all_nodes={n['id']:n for n in [*article_nodes,*nodes]}
            all_nodes.update({n['id']:n for n in context})
            for n in [*article_nodes,*nodes]:
                classification=n.pop('_classification',None)
                if classification:
                    from .classifier import save
                    save(db,classification)
                n={**n,'available_at':stamp,'version':version,'is_fixture':self.fixture,'batch_id':job['id']+':'+article['revision_id']}
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
                if edge.get('translations'):record['translations']=edge['translations']
                db.execute('INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?)',(ident,edge['source'],edge['target'],version,encode(record)))
            for a in covered:
                db.execute('INSERT OR IGNORE INTO extractions VALUES (?,?,?,?)',(a['revision_id'],job['payload']['model'],PROMPT_VERSION,version))
            if review:
                for a in covered:
                    db.execute('INSERT OR IGNORE INTO reviews VALUES (?,?)',(job['id'],a['revision_id']))
                    db.execute('INSERT OR REPLACE INTO review_coverage VALUES (?,(SELECT count(DISTINCT revision) FROM extractions))',(a['revision_id'],))
            old=json.loads(db.execute('SELECT usage FROM jobs WHERE id=?',(job['id'],)).fetchone()[0])
            totals=dict(old)
            for k,v in usage.items():
                if isinstance(v,int) and not isinstance(v,bool) and v>=0: totals[k]=old.get(k,0)+v
            db.execute('UPDATE jobs SET done=done+?,updated_at=?,usage=? WHERE id=?',(len(covered),stamp,encode(totals),job['id']))
            self.receipt(db,job,article,usage,'published')
        return True

    def reject(self,job,article,proposal,error,usage):
        # Rejected responses consume tokens too; keep evidence for diagnosis, never graph publication.
        with self.connection() as db:
            db.execute('INSERT INTO rejected_proposals(job_id,revision,created_at,error,proposal,usage) VALUES (?,?,?,?,?,?)',
                (job['id'],article['revision_id'],now(),str(error)[:600],encode(proposal),encode(usage)))
            old=json.loads(db.execute('SELECT usage FROM jobs WHERE id=?',(job['id'],)).fetchone()[0])
            for k,v in usage.items():
                if type(v) is int and v>=0:old[k]=old.get(k,0)+v
            db.execute('UPDATE jobs SET usage=?,updated_at=? WHERE id=?',(encode(old),now(),job['id']))
            self.receipt(db,job,article,usage,'rejected')

    def receipt(self,db,job,article,usage,status):
        raw=json.loads(db.execute('SELECT payload FROM jobs WHERE id=?',(job['id'],)).fetchone()[0])
        receipt={'at':now(),'articles':[{'id':a['revision_id'],'date':a['published_at']} for a in article.get('_evidence',[article])],'usage':usage,'status':status}
        raw.setdefault('receipts',[]).append(receipt);raw['last_usage']=usage
        db.execute('UPDATE jobs SET payload=? WHERE id=?',(encode(raw),job['id']))

    def stage(self,job,stage,revision):
        with self.connection() as db:
            db.execute("UPDATE jobs SET payload=json_set(payload,'$.stage',?,'$.current_revision',?),updated_at=? WHERE id=? AND status='running'",(stage,revision,now(),job['id']))

    def perspectives(self,version=None):
        with self.connection() as db:
            version=version if version is not None else db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
            counts={r[0]:r[1] for r in db.execute("SELECT COALESCE(json_extract(payload,'$.assessment.category'),'uncertain'),count(*) FROM nodes WHERE kind!='ArticleRevision' AND created_version<=? GROUP BY 1",(version,))}
            theses=[json.loads(r[0]) for r in db.execute("SELECT payload FROM nodes WHERE kind='Thesis' AND created_version<=? ORDER BY created_version DESC,id LIMIT 40",(version,))]
            total=db.execute("SELECT count(*) FROM nodes WHERE kind='Thesis' AND created_version<=?",(version,)).fetchone()[0]
        return {'categories':counts,'theses':theses,'total_theses':total,'note':'既有模型局部觀點彙整，並非全圖重新推論；分類未以未來股價驗證。'}

    def graph(self,version=None,as_of=None,limit=2400,start=None,end=None):
        with self.connection() as db:
            versions=[dict(r) for r in db.execute('SELECT * FROM versions ORDER BY version DESC LIMIT 10')]
            if as_of:
                stamp=dt.datetime.fromisoformat(as_of.replace('Z','+00:00'))
                if stamp.tzinfo is None: raise ValueError('as_of必須含時區')
                stamp=stamp.astimezone(dt.timezone.utc).isoformat()
                chosen=db.execute('SELECT max(version) FROM versions WHERE created_at<=?',(stamp,)).fetchone()[0] or 0
            elif version is not None:
                chosen=int(version)
                if chosen<0 or (chosen and chosen not in {v['version'] for v in versions}): raise ValueError('只保留最近 10 個可切換版本')
            else: chosen=versions[0]['version'] if versions else 0
            from .workbench import enrich_graph
            extra=enrich_graph(self,chosen,start,end)
            allowed=encode(extra.pop('visible_ids')) if start or end else None
            extra.pop('visible_ids',None)
            nodes=[json.loads(r[0]) for r in db.execute('SELECT payload FROM nodes WHERE created_version<=? AND (? IS NULL OR id IN (SELECT value FROM json_each(?))) ORDER BY created_version DESC,id LIMIT ?',(chosen,allowed,allowed,limit))]
            edges=[json.loads(r[0]) for r in db.execute('''WITH visible AS (
                SELECT id FROM nodes WHERE created_version<=? AND (? IS NULL OR id IN (SELECT value FROM json_each(?))) ORDER BY created_version DESC,id LIMIT ?)
                SELECT e.payload FROM edges e JOIN visible s ON e.source=s.id
                JOIN visible t ON e.target=t.id WHERE e.created_version<=?''',(chosen,allowed,allowed,limit,chosen))]
            total=db.execute('SELECT count(*) FROM nodes WHERE created_version<=? AND (? IS NULL OR id IN (SELECT value FROM json_each(?)))',(chosen,allowed,allowed)).fetchone()[0]
            count=db.execute('SELECT count(*) FROM articles').fetchone()[0]
            from .classifier import enrich
            cutoff=dt.datetime.fromisoformat(stamp) if as_of else (dt.datetime.fromisoformat(next(v['created_at'] for v in versions if v['version']==chosen)) if version and chosen else None)
            classification=enrich(db,{'nodes':nodes,'edges':edges},cutoff)
            classification_jobs=[{**dict(r),'payload':json.loads(r['payload'])} for r in db.execute("SELECT * FROM research_jobs WHERE json_extract(payload,'$.operation')='classify_l1' ORDER BY created_at DESC LIMIT 1")]
        perspectives=extra.pop('filtered_perspectives')
        visible_ids={n['id'] for n in nodes}|{n['id'] for n in perspectives['theses']}
        extra['histories']={k:v for k,v in extra['histories'].items() if k in visible_ids}
        return {**extra,'classification_jobs':classification_jobs,'taxonomy':classification['taxonomy'],'opinion_groups':classification['opinion_groups'],'instrument':self.instrument,'mode':'live_recorded','version':chosen,'versions':versions,'nodes':nodes,'edges':edges,'total_nodes':total,'captured_articles':count,'truncated':total>len(nodes),'config':self.config(),'jobs':self.jobs(),'perspectives':perspectives}

    def markdown(self,version=None):
        graph=self.graph(version=version)
        lines=[f"# {self.instrument} Wiki",f"版本 {graph['version']} · live_recorded",'引用已核對原文；LLM陳述仍為提案，並非已驗證事實。','']
        for n in graph['nodes']:
            lines.extend([f"## {n['kind']}: {n['title']}",n.get('summary','')])
            for c in n.get('citations',[]): lines.append(f"> {c['quote']}\n\n來源版本：{c['article_revision_id']}，{c['field']}[{c['start']}:{c['end']}]")
        if graph['truncated']: lines.append('此匯出受2400節點上限限制。')
        for node_id,history in graph['histories'].items():
            lines.append('## Viewpoint history: '+node_id)
            for n in [history['original'],*[n for batch in history['recent_batches'] for n in batch]]:
                lines.extend([f"### v{n.get('version',0)} · {n['title']}",n['summary']])
        for n in graph['nodes']:
            for lang,fields in n.get('translations',{}).items():
                lines.extend([f"## {lang}: {fields['title']}",fields['summary'],fields['rationale']])
        return '\n\n'.join(lines)

def validate_proposal(article,proposal,context):
    if not isinstance(proposal,dict) or set(proposal)!= {'nodes','relations'}: raise ValueError('LLM輸出必須包含nodes及relations')
    ns=proposal['nodes']; rs=proposal['relations']
    cap=min(60,max(8,len(article.get('_evidence',[article]))*3))
    if not isinstance(ns,list) or len(ns)>cap or not isinstance(rs,list) or len(rs)>cap*2: raise ValueError('LLM輸出超出本批上限')
    batch={a['revision_id']:a for a in article.get('_evidence',[article])}
    evidence={a['revision_id']:a for a in [*batch.values(),*article.get('_related_articles',[])]}
    def citations(values):
        if not isinstance(values,list) or not 1<=len(values)<=5: raise ValueError('每項陳述都必須附1–5段引用')
        result=[]
        for c in values:
            if not isinstance(c,dict) or c.get('revision_id') not in evidence or c.get('field') not in ('title','summary'): raise ValueError('引用版本不在本次證據內')
            source=evidence[c['revision_id']];text=source[c['field']];quote=c.get('quote')
            if not isinstance(quote,str) or not 3<=len(quote)<=2000 or quote not in text: raise ValueError('LLM引用無法在原文逐字核對')
            start=text.index(quote)
            if any(r['article_revision_id']==source['revision_id'] and r['field']==c['field'] and r['quote']==quote for r in result): continue
            result.append({'article_revision_id':source['revision_id'],'content_hash':source['content_hash'],'field':c['field'],'start':start,'end':start+len(quote),'quote':quote})
        return result
    nodes=[];mapped={n['id']:n for n in context};edges=[]
    mapped.update({ident:{'id':ident,'kind':'ArticleRevision','scope':'article'} for ident in batch})
    for n in ns:
        if not isinstance(n,dict) or n.get('kind') not in KINDS or not isinstance(n.get('key'),str) or not re.fullmatch(r'n[0-9]{1,2}',n['key']) or n['key'] in mapped: raise ValueError('無效Wiki節點')
        for field,cap in [('title',250),('summary',2000),('scope',250)]:
            if not isinstance(n.get(field),str) or not 1<=len(n[field])<=cap: raise ValueError('無效Wiki文字欄位')
        refs=citations(n.get('citations'));ident='node-'+digest([n['kind'],n['title'],n['summary'],n['scope']])
        node={'id':ident,'kind':n['kind'],'title':n['title'],'summary':n['summary'],'scope':n['scope'],'status':'hypothesis' if n['kind']=='Thesis' else 'proposed','citations':refs}
        assessment=n.get('assessment')
        if assessment is not None:
            if not isinstance(assessment,dict) or assessment.get('category') not in ('direct','indirect','low','uncertain') or not isinstance(assessment.get('rationale'),str) or not 1<=len(assessment['rationale'])<=1500:raise ValueError('無效觀點分類')
            node['assessment']={'category':assessment['category'],'rationale':assessment['rationale'],'status':'unverified','basis':'title_summary_only','predictive_association':None}
            from .evidence import TOPICS
            for key,allowed in [('topic',TOPICS),('evidence',('supported','mixed','insufficient'))]:
                if key in assessment:
                    if assessment[key] not in allowed:raise ValueError('無效觀點證據／主題')
                    node['assessment'][key]=assessment[key]
            observations=[{'revision_id':r,**article['_market'][r]} for r in dict.fromkeys(c['article_revision_id'] for c in refs) if r in article.get('_market',{})]
            if observations:
                node['market_evidence']=observations
                node['assessment']['basis']='title_summary_and_cached_market_observations' if any(o['mean_return'] is not None for o in observations) else 'title_summary_only_market_unavailable'
            node['id']='node-'+digest([n['kind'],n['title'],n['summary'],n['scope'],node['assessment'],observations]);ident=node['id']
        localized=n.get('translations')
        if localized is not None:
            if not isinstance(localized,dict) or set(localized)-{'en','zh-Hant'}:raise ValueError('無效語系')
            for lang,fields in localized.items():
                if not isinstance(fields,dict) or set(fields)!= {'title','summary','rationale'} or any(not isinstance(fields[k],str) or not 1<=len(fields[k])<=cap for k,cap in [('title',250),('summary',2000),('rationale',1500)]):raise ValueError('無效翻譯內容')
            node['translations']=localized
            node['id']='node-'+digest([node['id'],localized]);ident=node['id']
        if 'opinion_metadata' in n:
            meta=n['opinion_metadata']
            if not isinstance(meta,dict) or set(meta)!={'claim_type','conditions','horizon','change_reason'} or meta['claim_type'] not in ('reported_claim','fact_excerpt','inference','hypothesis') or not isinstance(meta['conditions'],list) or len(meta['conditions'])>8 or any(not isinstance(x,str) or len(x)>500 for x in meta['conditions']) or not isinstance(meta['horizon'],str) or len(meta['horizon'])>300 or not isinstance(meta['change_reason'],str) or len(meta['change_reason'])>500:raise ValueError('Invalid opinion metadata')
            node['opinion_metadata']=meta;node['id']='node-'+digest([node['id'],meta]);ident=node['id']
        if 'classification' in n:
            from .classifier import validate
            if not article.get('_taxonomy'):raise ValueError('Classification requires frozen taxonomy')
            node['_classification']=validate(n['classification'],node,article['_taxonomy'])
        mapped[n['key']]=node;nodes.append(node)
        for source_id in dict.fromkeys(c['article_revision_id'] for c in refs):
            edges.append({'source':source_id,'target':ident,'type':'SUPPORTS','rationale':'原文支持此LLM提案；只核對引用，不代表陳述已證實。','citations':[c for c in refs if c['article_revision_id']==source_id]})
    for index,r in enumerate(rs,1):
        if not isinstance(r,dict) or not isinstance(r.get('source'),str) or not isinstance(r.get('target'),str): raise ValueError('無效Wiki關聯')
        a=mapped.get(r['source']);b=mapped.get(r['target']);kind=r.get('type')
        missing=[f"{end}={r[end][:160]!r}" for end in ('source','target') if r[end] not in mapped]
        if missing:
            raise ValueError(f"關聯[{index}] {'; '.join(missing)} 不在本次可用端點內。僅使用本提案的新節點 key、提供的 existing_pages.id 或本批新聞 revision_id；不可猜測 ID。請刪除此無依據關聯，或依原始證據改用確實提供的端點；保留其他有效節點與關聯。")
        article_link=bool(a and b and a['kind']==b['kind']=='ArticleRevision' and kind=='RELATED_TO' and r['source'] in batch)
        if not a or not b or a['id']==b['id'] or kind not in RELATIONS or (r['source'] not in {n['key'] for n in ns} and not article_link):raise ValueError('關聯需由新節點發出；新聞之間僅允許本批新聞發出的 RELATED_TO')
        if ('ArticleRevision' in (a['kind'],b['kind'])) and not article_link:raise ValueError('新聞端點只允許兩篇新聞之間的 RELATED_TO')
        if article_link:
            refs=citations(r.get('citations'))
            if not {a['id'],b['id']} <= {c['article_revision_id'] for c in refs}:raise ValueError('跨新聞關聯必須引用兩端新聞原文')
        if kind=='DEPENDS_ON' and a['kind']!='Thesis': raise ValueError('DEPENDS_ON方向錯誤')
        if kind=='TEMPORALLY_PRECEDES' and (a['kind']!='Event' or b['kind']!='Event'): raise ValueError('時間順序只能連接事件')
        if kind in ('SUPPORTS','CONTRADICTS') and a['kind']=='Thesis': raise ValueError('觀點不能充當已核對證據')
        if kind=='CONTRADICTS' and a['scope']!=b['scope']: raise ValueError('反證必須屬於相同命題範圍')
        if not isinstance(r.get('rationale'),str) or not 1<=len(r['rationale'])<=1000: raise ValueError('關聯必須包含理由')
        translations=r.get('translations',{})
        if not isinstance(translations,dict) or set(translations)-{'en','zh-Hant'} or any(not isinstance(v,dict) or set(v)!={'rationale'} or not isinstance(v['rationale'],str) or not 1<=len(v['rationale'])<=1500 for v in translations.values()):raise ValueError('無效關係翻譯')
        edges.append({'source':a['id'],'target':b['id'],'type':kind,'rationale':r['rationale'],'citations':citations(r.get('citations')),'translations':translations})
    return nodes,edges
