"""Explicit, non-destructive comparisons of two saved viewpoint revisions."""
import json
import uuid
from .store import digest, encode, now
from .research import OWNER, put

OPERATION = 'compare_viewpoints'
VERDICTS = ('similar', 'conflicting', 'different_scope', 'insufficient')

def candidates(db, term='', offset=0):
    if len(term)>200 or offset<0:raise ValueError('Invalid comparison search')
    has_imports=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='merge_records'").fetchone()
    origin="CASE WHEN EXISTS(SELECT 1 FROM merge_records WHERE origin='viewpoint:'||nodes.id AND table_name='imported_viewpoint') THEN 'L1 · imported · v' ELSE 'L1 · v' END" if has_imports else "'L1 · v'"
    rows=db.execute(f"""
      SELECT ref,title,origin FROM (
        SELECT 'L1/'||id ref,json_extract(payload,'$.title') title,{origin}||created_version origin
          FROM nodes WHERE kind!='ArticleRevision'
        UNION ALL
        SELECT 'L2/'||r.id||'/'||json_extract(c.value,'$.id'),json_extract(c.value,'$.statement'),
               CASE WHEN r.owner=? THEN 'L2 · local' ELSE 'L2 · imported' END
          FROM research_objects r,json_each(r.payload,'$.result.claims') c
         WHERE r.kind='run' AND (r.owner=? OR r.owner LIKE 'imported:%')
      ) WHERE instr(lower(title),lower(?))>0 ORDER BY title,ref LIMIT 51 OFFSET ?
    """,(OWNER,OWNER,term,offset)).fetchall()
    return {'items':[dict(r) for r in rows[:50]],'next_offset':offset+50 if len(rows)>50 else None}

def material(db,ref):
    parts=ref.split('/')
    if len(parts)==2 and parts[0]=='L1':
        row=db.execute("SELECT payload FROM nodes WHERE id=? AND kind!='ArticleRevision'",(parts[1],)).fetchone()
        if not row:raise ValueError('Unknown L1 revision')
        node=json.loads(row[0])
        edges=[json.loads(r[0]) for r in db.execute("""SELECT payload FROM edges WHERE target=?
            AND json_extract(payload,'$.relation_type') IN ('SUPPORTS','CONTRADICTS')
            ORDER BY json_extract(payload,'$.relation_type'),id""",(parts[1],))]
        citations=[('citation',c) for c in node.get('citations',[])]
        citations.extend((e['relation_type'],c) for e in edges for c in e.get('evidence_refs',[]))
        result={'ref':ref,'title':node['title'],'statement':node['summary'],'scope':node['scope'],
                'available_at':node.get('available_at'),'conditions':node.get('opinion_metadata',{})}
    elif len(parts)==3 and parts[0]=='L2':
        row=db.execute("""SELECT owner,payload FROM research_objects WHERE kind='run' AND id=?
            AND (owner=? OR owner LIKE 'imported:%')""",(parts[1],OWNER)).fetchone()
        if not row:raise ValueError('Unknown L2 run')
        run=json.loads(row['payload'])
        snapshot=db.execute("SELECT owner,payload FROM research_objects WHERE kind='snapshot' AND id=?",(run['snapshot'],)).fetchone()
        if not snapshot:raise ValueError('Missing L2 snapshot')
        bundle=json.loads(snapshot['payload'])
        if run['snapshot']!='snapshot-'+digest(bundle):
            raise ValueError('L2 snapshot reference mismatch')
        claim=next((c for c in run['result']['claims'] if c['id']==parts[2]),None)
        if not claim:raise ValueError('Unknown L2 claim')
        premises=[o for o in bundle['opinions'] if o['claim_id'] in claim['derived_from']]
        if set(claim['derived_from'])!={o['claim_id'] for o in premises}:raise ValueError('Missing L1 premise')
        citations=[('citation',c) for o in premises for c in o['evidence']]
        premise_ids={o['revision_id'] for o in premises}
        for edge in bundle.get('relations',[]):
            if edge['target']['revision_id'] in premise_ids and edge['relation_type'] in ('SUPPORTS','CONTRADICTS'):
                citations.extend((edge['relation_type'],c) for c in edge['evidence_refs'])
        result={'ref':ref,'statement':claim['statement'],'snapshot':run['snapshot'],'question':bundle['lens']['query'],
                'window':bundle['lens']['time_spec'],'premises':[{k:o[k] for k in ('revision_id','statement')} for o in premises],
                'argument_roles':[role for role in ('support','counter') if claim['id'] in run['result'].get(role,[])],
                'assumptions':claim['assumptions'],'invalidating_conditions':claim['invalidating_conditions']}
    else:raise ValueError('Choose an L1 revision or an L2 claim')
    evidence={}
    for role,c in citations:
        if c.get('quote') and c.get('article_revision_id'):
            evidence[(role,c['article_revision_id'],c.get('field'),c.get('start'),c['quote'])]={
                'role':role,**{k:c[k] for k in ('article_revision_id','quote','field','start','end','url','published_at') if k in c}}
    if parts[0]=='L1':
        ids=sorted({c['article_revision_id'] for c in evidence.values()})
        sources={r['id']:json.loads(r['payload']) for r in db.execute(
            'SELECT id,payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(encode(ids),))}
        for c in evidence.values():
            article=sources.get(c['article_revision_id'],{})
            c.update({k:article[k] for k in ('url','published_at') if k in article})
    result['evidence']=list(evidence.values())
    return result

def enqueue(db,body):
    refs=body.get('refs')
    if not isinstance(refs,list) or len(refs)!=2 or not all(isinstance(r,str) and len(r)<=250 for r in refs) or refs[0]==refs[1]:
        raise ValueError('請選擇兩個不同的觀點')
    model=body.get('model');effort=body.get('reasoning_effort','medium')
    if not isinstance(model,str) or not model or len(model)>100 or effort not in ('low','medium','high','xhigh','max','ultra'):
        raise ValueError('請選擇有效模型與推理深度')
    db.execute('BEGIN IMMEDIATE')
    if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone() or db.execute(
            "SELECT 1 FROM research_jobs WHERE json_extract(payload,'$.operation')='classify_l1' AND status IN ('queued','running')").fetchone():
        raise ValueError('請先停止 L1 維護')
    pair=[material(db,r) for r in sorted(refs)]
    if len(encode(pair).encode())>140000:raise ValueError('這組證據超過模型輸入範圍，請選擇較精確的論點')
    for index,source in enumerate(pair):
        for i,cite in enumerate(source['evidence']):cite['id']=f'{index+1}.{i+1}'
    key=digest([OPERATION,pair,model,effort])
    existing=db.execute("""SELECT id,status FROM research_jobs WHERE owner=? AND json_extract(payload,'$.key')=?
            AND status IN ('queued','running','completed') ORDER BY created_at DESC LIMIT 1""",(OWNER,key)).fetchone()
    if existing:return {'job_id':existing['id'],'status':existing['status']}
    payload={'operation':OPERATION,'key':key,'model':model,'reasoning_effort':effort,'pair':pair}
    ident=uuid.uuid4().hex;stamp=now()
    db.execute('INSERT INTO research_jobs VALUES (?,?,?,?,?,?,NULL)',(ident,OWNER,'queued',stamp,stamp,encode(payload)))
    return {'job_id':ident,'status':'queued'}

def complete(service,store,job,p):
    response=service.run_model(store,{'id':job['id'],'payload':p},{'viewpoints':p['pair']},[])
    report=response.get('proposal',{});refs=report.get('citations')
    if report.get('verdict') not in VERDICTS or not all(isinstance(report.get(k),str) and 0<len(report[k])<=4000 for k in ('summary','reason')):
        raise ValueError('Invalid comparison proposal')
    allowed=[{c['id'] for c in source['evidence']} for source in p['pair']]
    if not isinstance(refs,list) or any(not isinstance(r,str) or r not in allowed[0]|allowed[1] for r in refs):
        raise ValueError('Comparison cites unknown evidence')
    if report['verdict'] in ('similar','conflicting') and any(not group.intersection(refs) for group in allowed):
        raise ValueError('Both viewpoints need cited evidence')
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT status FROM research_jobs WHERE id=?',(job['id'],)).fetchone()[0]!='running':return
        result={k:report[k] for k in ('verdict','summary','reason','citations')}
        p['comparison_id']=put(db,'viewpoint_comparison',{'inputs':p['pair'],'result':result,'model':p['model'],
            'reasoning_effort':p['reasoning_effort'],'usage':response.get('usage',{}),'job_id':job['id']})
        db.execute("UPDATE research_jobs SET status='completed',payload=?,updated_at=? WHERE id=?",(encode(p),now(),job['id']))
