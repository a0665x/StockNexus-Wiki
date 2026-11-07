"""LLM labels are a versioned index of L1, never a new evidence source.

Backfill is explicitly queued by catch-up. Reads do not spend tokens. A classification
batch is atomic; failures require an explicit retry and never overwrite old revisions.
"""
import json
import uuid
from .store import now, digest, encode
from .research import taxonomy, put, instant, OWNER

COLORS=['#7de3bd','#7db6f2','#d3a5ef','#efbc78','#ec9da6','#91cbd3','#c7cb80']

def assignments(db,revision,cutoff=None):
    out={}
    for r in db.execute("SELECT payload FROM research_objects WHERE kind='classification' AND owner='' ORDER BY created_at,id"):
        a=json.loads(r[0])
        if a.get('classifier_version')!='llm-v1' or a['taxonomy_revision']!=revision:continue
        if cutoff and instant(a['available_at'])>cutoff:continue
        out[a['opinion_revision']]=a
    return out

def validate(raw,node,tax):
    if not isinstance(raw,dict) or set(raw)!={'labels','candidates','unclassified_reason'}:raise ValueError('Invalid L1 classification')
    terms={t['id']:t for t in tax['terms']};labels=raw['labels'];candidates=raw['candidates']
    if not isinstance(labels,list) or len(labels)>12 or not isinstance(candidates,list) or len(candidates)>4:raise ValueError('Too many classification labels')
    if not isinstance(raw['unclassified_reason'],str) or len(raw['unclassified_reason'])>500 or (not labels and not raw['unclassified_reason']):raise ValueError('Unclassified needs a reason')
    items=[];seen=set()
    for x in labels:
        if not isinstance(x,dict) or set(x)!={'term_id','rationale','confidence'} or x['term_id'] not in terms or terms[x['term_id']]['status']!='active' or x['confidence'] not in ('low','medium','high') or not isinstance(x['rationale'],str) or not 1<=len(x['rationale'])<=500:raise ValueError('Invalid classification term/rationale')
        if x['term_id'] in seen:continue
        seen.add(x['term_id']);items.append({'opinion_revision':node['id'],'taxonomy_revision':tax['revision_id'],'term_id':x['term_id'],'claim_ids':[node['id']+':claim'],'rationale':x['rationale'],'confidence_band':x['confidence'],'classifier_version':'llm-v1'})
    for c in candidates:
        if not isinstance(c,dict) or set(c)!={'facet','label','definition'} or c['facet'] not in ('topic','driver','analysis_dimension') or any(not isinstance(c[k],str) or not 1<=len(c[k])<=300 for k in ('label','definition')):raise ValueError('Invalid candidate term')
    return {'opinion_revision':node['id'],'taxonomy_revision':tax['revision_id'],'available_at':now(),'assignments':items,'candidate_terms':candidates,'classifier_version':'llm-v1','status':'classified' if items else 'unclassified','unclassified_reasons':[] if items else [raw['unclassified_reason']]}

def save(db,record):
    ident='classification-'+digest([record['opinion_revision'],record['taxonomy_revision'],'llm-v1'])
    put(db,'classification',record,'',ident)
    tax=taxonomy(db)
    for c in record['candidate_terms']:
        # Aliases already known are not promoted to new terms by the model.
        if any(c['label'].casefold() in [t['label'].casefold(),*[a.casefold() for a in t['aliases']]] for t in tax['terms']):continue
        put(db,'candidate_term',{**c,'status':'candidate','opinion_revision':record['opinion_revision']},'')

def groups(graph):
    nodes={n['id']:n for n in graph['nodes']};deps={i:set() for i in nodes}
    for e in graph['edges']:
        a=e['source']['stable_id'];b=e['target']['stable_id'];kind=e['relation_type']
        if a not in nodes or b not in nodes:continue
        if kind=='DEPENDS_ON':deps[a].add(b)
        elif kind in ('SUPPORTS','CONTRADICTS'):deps[b].add(a)
    result={}
    roots=[i for i,n in nodes.items() if n['kind']=='Thesis']
    reached=set()
    for root in roots:
        seen={root};stack=[root]
        while stack and len(seen)<200:
            for dep in sorted(deps[stack.pop()]):
                if dep not in seen and len(seen)<200:seen.add(dep);stack.append(dep)
        result[root]=sorted(seen);reached.update(seen)
    for i,n in nodes.items():
        if i not in reached and n['kind']!='ArticleRevision':result[i]=sorted({i,*deps[i]})
    return result

def enrich(db,graph,cutoff=None):
    tax=taxonomy(db,cutoff);known=assignments(db,tax['revision_id'],cutoff)
    members=groups(graph);labels={n['id']:set() for n in graph['nodes']}
    for root,ids in members.items():
        own={x['term_id'] for x in known.get(root,{}).get('assignments',[])}
        for i in ids:labels[i].update(own)
    for n in graph['nodes']:
        own=known.get(n['id']);labels[n['id']].update(x['term_id'] for x in (own or {}).get('assignments',[]))
        n.update(layer='L1',classification_terms=sorted(labels[n['id']]),classification_status=(own or {}).get('status','pending'),opinion_roots=[r for r,ids in members.items() if n['id'] in ids])
    graph['taxonomy']={**tax,'terms':[{**t,'color':COLORS[int(digest(t['id'])[:8],16)%len(COLORS)],'opinion_ids':[r for r in members if t['id'] in labels[r]],'node_ids':[i for i in labels if t['id'] in labels[i]]} for t in tax['terms']]}
    graph['opinion_groups']=members
    return graph

def enqueue(store,model,effort):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE');tax=taxonomy(db);done=assignments(db,tax['revision_id'])
        graph={'nodes':[json.loads(r[0]) for r in db.execute('SELECT payload FROM nodes ORDER BY created_version,id')],'edges':[json.loads(r[0]) for r in db.execute('SELECT payload FROM edges')]}
        superseded={e['target']['stable_id'] for e in graph['edges'] if e['relation_type']=='UPDATES'}
        roots=groups(graph)
        pending=[n for n in graph['nodes'] if n['id'] in roots and n['id'] not in done and n['id'] not in superseded]
        active=db.execute("SELECT id FROM research_jobs WHERE json_extract(payload,'$.operation')='classify_l1' AND status IN ('queued','running')").fetchone()
        if active:return {'job_id':active[0],'status':'queued'}
        if not pending:return {'status':'unchanged','pending':0}
        ident=uuid.uuid4().hex;stamp=now();payload={'operation':'classify_l1','key':ident,'model':model,'reasoning_effort':effort,'taxonomy':tax,'opinion_ids':[n['id'] for n in pending],'done':0,'total':len(pending)}
        db.execute('INSERT INTO research_jobs VALUES (?,?,?,?,?,?,NULL)',(ident,OWNER,'queued',stamp,stamp,encode(payload)))
        return {'job_id':ident,'status':'queued','pending':len(pending)}

def process(store,service):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        r=db.execute("SELECT * FROM research_jobs WHERE status='queued' AND json_extract(payload,'$.operation')='classify_l1' ORDER BY created_at LIMIT 1").fetchone()
        if not r:return
        job=dict(r);p=json.loads(job['payload']);known=assignments(db,p['taxonomy']['revision_id'])
        ids=[i for i in p['opinion_ids'] if i not in known][:12]
        graph={'nodes':[json.loads(r[0]) for r in db.execute('SELECT payload FROM nodes')],'edges':[json.loads(r[0]) for r in db.execute('SELECT payload FROM edges')]}
        byid={n['id']:n for n in graph['nodes']};membership=groups(graph);nodes=[];size=0
        for i in ids:
            if i not in byid:continue
            n={**byid[i],'dependencies':[]};budget=0
            for dep in membership.get(i,[]):
                if dep==i:continue
                value=byid[dep];budget+=len(encode(value))
                if budget>18000:break
                n['dependencies'].append(value)
            n['dependency_context_truncated']=len(n['dependencies'])<len(membership.get(i,[]))-1
            length=len(encode(n))
            if nodes and size+length>65000:break
            nodes.append(n);size+=length
        if not nodes:db.execute("UPDATE research_jobs SET status='completed',payload=json_set(payload,'$.done',?),updated_at=? WHERE id=?",(p['total'],now(),job['id']));return
        p['current_title']=nodes[0]['title'];p['current_size']=len(nodes)
        db.execute("UPDATE research_jobs SET status='running',payload=?,updated_at=? WHERE id=?",(encode(p),now(),job['id']))
    service.active=(store,job['id'])
    try:
        response=service.runner(store,{'id':job['id'],'payload':p},{'opinions':nodes,'taxonomy':p['taxonomy']},[])
        p['usage']={k:p.get('usage',{}).get(k,0)+v for k,v in response.get('usage',{}).items() if type(v)==int and v>=0}
        with store.connection() as db:put(db,'model_receipt',{'job_id':job['id'],'phase':'classify_l1','usage':response.get('usage',{}),'recorded_at':now()})
        rows=response.get('proposal',{}).get('opinions',[])
        if len(rows)!=len(nodes) or {x.get('opinion_revision') for x in rows}!={n['id'] for n in nodes}:raise ValueError('Classification must cover each exact L1 revision once')
        byid={n['id']:n for n in nodes};records=[validate({k:v for k,v in x.items() if k!='opinion_revision'},byid[x['opinion_revision']],p['taxonomy']) for x in rows]
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT status FROM research_jobs WHERE id=?',(job['id'],)).fetchone()[0]!='running':return
            for record in records:save(db,record)
            p['done']+=len(nodes)
            db.execute('UPDATE research_jobs SET status=?,payload=?,updated_at=? WHERE id=?',('completed' if p['done']>=p['total'] else 'queued',encode(p),now(),job['id']))
    except Exception as e:
        with store.connection() as db:db.execute("UPDATE research_jobs SET status='failed',error=?,updated_at=? WHERE id=? AND status='running'",(str(e)[:600],now(),job['id']))
    finally:service.active=None
