"""LLM labels are a versioned index of L1, never a new evidence source.

Backfill is explicitly queued by catch-up. Reads do not spend tokens. A classification
batch publishes atomically. Timeout recovery is bounded and scoped to its revisions.
"""
from .trace import span, emit, job_fields, admitted, job_state, error_fields
import json
import datetime as dt
import uuid
from .store import now, digest, encode
from .research import taxonomy, put, instant, OWNER

COLORS=['#7de3bd','#7db6f2','#d3a5ef','#efbc78','#ec9da6','#91cbd3','#c7cb80']

def assignments(db,revision,cutoff=None):
    # Additive definitions do not invalidate labels whose complete old vocabulary
    # is unchanged. Keep their exact original revision; never pretend new terms
    # have been evaluated, and never borrow future knowledge for a cutoff.
    taxonomies={}
    for r in db.execute("SELECT payload FROM research_objects WHERE kind='taxonomy' AND owner=''"):
        tax=json.loads(r[0])
        if cutoff and instant(tax['available_at'])>cutoff:continue
        taxonomies[tax['revision_id']]={t['id']:t for t in tax['terms']}
    target=taxonomies.get(revision,{})
    compatible={key:sorted(set(target)-set(terms)) for key,terms in taxonomies.items() if terms and all(target.get(i)==t for i,t in terms.items())}
    out={}
    for r in db.execute("SELECT payload FROM research_objects WHERE kind='classification' AND owner='' ORDER BY created_at,id"):
        a=json.loads(r[0]);source=a.get('taxonomy_revision')
        if a.get('classifier_version')!='llm-v1' or source not in compatible:continue
        if cutoff and instant(a['available_at'])>cutoff:continue
        previous=out.get(a['opinion_revision'])
        if previous and previous['taxonomy_revision']==revision and source!=revision:continue
        if source!=revision:a={**a,'unassessed_term_ids':compatible[source]}
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
        n['classification_taxonomy_revision']=(own or {}).get('taxonomy_revision');n['unassessed_term_ids']=(own or {}).get('unassessed_term_ids',[])
        n.update(layer='L1',classification_terms=sorted(labels[n['id']]),classification_status=(own or {}).get('status','pending'),opinion_roots=[r for r,ids in members.items() if n['id'] in ids])
    graph['taxonomy']={**tax,'terms':[{**t,'color':COLORS[int(digest(t['id'])[:8],16)%len(COLORS)],'opinion_ids':[r for r in members if t['id'] in labels[r]],'node_ids':[i for i in labels if t['id'] in labels[i]]} for t in tax['terms']]}
    graph['opinion_groups']=members
    from .workbench import news_day
    byid={n['id']:n for n in graph['nodes']}
    refs={c['article_revision_id'] for n in graph['nodes'] for c in [*n.get('citations',[]),*n.get('corroborating_citations',[])]}
    dates={r['id']:news_day(json.loads(r['payload']).get('published_at')) for r in db.execute('SELECT id,payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(encode(sorted(refs)),))}
    graph['opinion_index']=[{**{k:byid[root][k] for k in ('id','kind','title','translations','classification_terms','classification_status') if k in byid[root]},
        'dates':sorted({dates[c['article_revision_id']] for i in ids for c in [*byid[i].get('citations',[]),*byid[i].get('corroborating_citations',[])] if dates.get(c['article_revision_id'])})} for root,ids in members.items()]
    return graph

def enqueue(store,model,effort,date_range=None):
    if date_range is not None:
        if not isinstance(date_range,dict) or set(date_range)!={'start','end'}:raise ValueError('Invalid classification date range')
        start=dt.date.fromisoformat(date_range['start']);end=dt.date.fromisoformat(date_range['end'])
        if start>end:raise ValueError('Invalid classification date range')
        date_range={'start':start.isoformat(),'end':end.isoformat()}
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE');tax=taxonomy(db);done=assignments(db,tax['revision_id'])
        graph={'nodes':[json.loads(r[0]) for r in db.execute('SELECT payload FROM nodes ORDER BY created_version,id')],'edges':[json.loads(r[0]) for r in db.execute('SELECT payload FROM edges')]}
        superseded={e['target']['stable_id'] for e in graph['edges'] if e['relation_type']=='UPDATES'}
        roots=groups(graph)
        eligible=set(roots)
        if date_range is not None:
            from .workbench import news_day
            selected={r['id'] for r in db.execute('SELECT id,payload FROM articles') if (day:=news_day(json.loads(r['payload']).get('published_at'))) and date_range['start']<=day<=date_range['end']}
            byid={n['id']:n for n in graph['nodes']}
            eligible={root for root,members in roots.items() if any(i in selected or any(c['article_revision_id'] in selected for c in byid[i].get('citations',[])) for i in members)}
        pending=[n for n in graph['nodes'] if n['id'] in eligible and n['id'] not in done and n['id'] not in superseded]
        active=db.execute("SELECT id,status,payload FROM research_jobs WHERE json_extract(payload,'$.operation')='classify_l1' AND status IN ('queued','running')").fetchone()
        if active:
            if json.loads(active['payload']).get('date_range')!=date_range:raise ValueError('分類工作日期範圍不同，請先停止舊工作再開始')
            return {'job_id':active['id'],'status':active['status']}
        if not pending:return {'status':'unchanged','pending':0}
        ident=uuid.uuid4().hex;stamp=now();payload={'operation':'classify_l1','date_range':date_range,'key':ident,'model':model,'reasoning_effort':effort,'taxonomy':tax,'opinion_ids':[n['id'] for n in pending],'done':0,'total':len(pending)}
        db.execute('INSERT INTO research_jobs VALUES (?,?,?,?,?,?,NULL)',(ident,OWNER,'queued',stamp,stamp,encode(payload)))
        return {'job_id':ident,'status':'queued','pending':len(pending)}

# Limits cover the serialized evidence packet including its frozen taxonomy.
MAX_OPINIONS = 4
PACKET_BYTES = 48 * 1024
DEPENDENCY_CHARS = 18000


class InvalidBatch(ValueError):
    """An unusable reply for these specific opinions."""


class OversizeOpinion(ValueError):
    """The full target and frozen taxonomy alone exceed the packet budget."""


def classification_batch(ids, by_id, membership, tax):
    """Intern node bodies and exact citation objects once, preserving revision membership."""
    # The frozen taxonomy in the job remains authoritative at validation time.
    terms = []
    for original in tax['terms']:
        term = dict(original)
        for key, default in (('status','active'), ('exclude',[]), ('related_terms',[]),
                             ('include',term.get('aliases',[]))):
            if term.get(key) == default:
                del term[key]
        terms.append(term)
    vocabulary = {**tax, 'terms':terms}

    def pack(targets):
        nodes = {}
        citations = []
        citation_index = {}
        for target in targets:
            for ident in [target['id'], *target['dependency_ids']]:
                if ident in nodes:
                    continue
                original = by_id[ident]
                node = {key: value for key, value in original.items() if key not in ('id','citations','batch_id')}
                if 'translations' in original:
                    canonical = {key:original[key] for key in ('title','summary') if key in original}
                    canonical.update({key:value for key,value in (original.get('assessment') or {}).items() if key=='rationale'})
                    node['translations'] = {lang:{k:v for k,v in fields.items() if k not in canonical or v!=canonical[k]}
                                            for lang,fields in original['translations'].items()}
                if 'citations' in original:
                    node['citation_ids'] = []
                    for citation in original['citations']:
                        key = encode(citation)
                        if key not in citation_index:
                            citation_index[key] = len(citations)
                            compact = dict(citation)
                            if 'content_hash' in compact and compact.get('article_revision_id') == 'article-'+str(compact['content_hash']):
                                del compact['content_hash']
                            citations.append(compact)
                        node['citation_ids'].append(citation_index[key])
                nodes[ident] = node
        return {'opinions': targets, 'nodes': nodes, 'citations': citations, 'taxonomy': vocabulary}

    targets = []
    result = None
    for ident in ids[:MAX_OPINIONS]:
        available = [dep for dep in membership.get(ident, []) if dep != ident]
        selected = []
        chars = 0
        for dep in available:
            chars += len(encode(by_id[dep]))
            if chars > DEPENDENCY_CHARS:
                break
            selected.append(dep)
        target = {'id':ident, 'dependency_ids':selected, 'dependency_context_truncated':len(selected) < len(available)}
        while True:
            candidate = pack([*targets, target])
            if len(encode(candidate).encode('utf-8')) <= PACKET_BYTES:
                break
            if targets:
                return result  # leave this target intact for the next batch
            if not selected:
                raise OversizeOpinion('單一觀點與分類表超過輸入上限，已保留待處理')
            selected.pop()
            target['dependency_context_truncated'] = True
        targets.append(target)
        result = candidate
    return result


def _validate_batch(response, packet, taxonomy):
    try:
        rows = response['proposal']['opinions']
        targets = {opinion['id'] for opinion in packet['opinions']}
        if not isinstance(rows, list) or len(rows) != len(targets) or {r['opinion_revision'] for r in rows} != targets:
            raise ValueError('Classification must cover each exact L1 revision once')
        return [validate({k:v for k,v in r.items() if k != 'opinion_revision'},
                         {'id':r['opinion_revision']}, taxonomy) for r in rows]
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidBatch(str(error)) from error


def _unresolved(payload, known):
    return [ident for ident in payload['opinion_ids'] if ident not in known]


def _save_progress(db, key, payload, known, expected):
    missing = _unresolved(payload, known)
    failed = set(payload.get('failed_ids', []))
    # A different publisher may have assigned one of these revisions during the model call.
    if missing and all(ident in failed for ident in missing):
        missing = _unresolved(payload, assignments(db, payload['taxonomy']['revision_id']))
    payload['failed_ids'] = [ident for ident in missing if ident in failed]
    payload['done'] = len(payload['opinion_ids']) - len(missing)
    if any(ident not in failed for ident in missing):
        status, error = 'queued', None
    elif missing:
        status = 'failed'
        error = f'尚有 {len(missing)} 個觀點未分類。已保存其他批次，可按繼續整理補做。'
    else:
        status, error = 'completed', None
    db.execute('UPDATE research_jobs SET status=?,payload=?,error=?,updated_at=? WHERE id=? AND status=?',
               (status, encode(payload), error, now(), key, expected))
    return status


def process(store, service):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM research_jobs WHERE status='queued' AND json_extract(payload,'$.operation')='classify_l1' ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            return
        job = dict(row)
        payload = json.loads(row['payload'])
        fields = job_fields(store, job)
        tax = payload['taxonomy']
        known = assignments(db, tax['revision_id'])
        failed = set(payload.get('failed_ids', []))
        remaining = [ident for ident in _unresolved(payload, known) if ident not in failed]
        if not remaining:
            _save_progress(db, job['id'], payload, known, 'queued')
            return
        waiting = payload.setdefault('retry_batches', [])
        pending = set(remaining)
        retry_ids = []
        while waiting and not retry_ids:
            retry_ids = [ident for ident in waiting.pop(0) if ident in pending]
        ids = retry_ids or remaining[:MAX_OPINIONS]
        with span(store, 'classification_prepare', **fields):
            graph = {'nodes':[json.loads(r[0]) for r in db.execute('SELECT payload FROM nodes')],
                     'edges':[json.loads(r[0]) for r in db.execute('SELECT payload FROM edges')]}
            by_id = {node['id']:node for node in graph['nodes']}
            absent = [ident for ident in ids if ident not in by_id]
            payload.setdefault('failed_ids', []).extend(absent)
            ids = [ident for ident in ids if ident in by_id]
            try:
                packet = classification_batch(ids, by_id, groups(graph), tax)
            except OversizeOpinion as error:
                payload['last_batch_error'] = str(error)
                payload['failed_ids'].append(ids[0])
                emit(store, 'state', 'classification_batch', **fields, status='input_too_large', opinions=1)
                packet = None
            if packet is None:
                if retry_ids and len(ids)>1:
                    waiting.insert(0, ids[1:])
                if _save_progress(db, job['id'], payload, known, 'queued') == 'queued':
                    service.wake.set()
                return
            batch = [target['id'] for target in packet['opinions']]
            if retry_ids and len(batch)<len(ids):
                waiting.insert(0, ids[len(batch):])
            payload.update(current_title=by_id[batch[0]]['title'], current_size=len(batch), current_batch=batch,
                           recovering=bool(retry_ids))
            db.execute("UPDATE research_jobs SET status='running',payload=?,updated_at=? WHERE id=?", (encode(payload),now(),job['id']))
    service.active = (store, job['id'])
    admitted(store, job)
    try:
        emit(store, 'state', 'classification_batch', **fields, opinions=len(batch), nodes=len(packet['nodes']),
             citations=len(packet['citations']), input_bytes=len(encode(packet).encode()), recovering=bool(retry_ids))
        call = {'id':job['id'], 'payload':payload}
        response = service.run_model(store, call, packet, [])
        if not isinstance(response, dict):
            raise InvalidBatch('Expected a classification response object')
        usage = response.get('usage') or {}
        totals = payload.setdefault('usage', {})
        for key,value in usage.items():
            if type(value) is int and value >= 0:
                totals[key] = totals.get(key, 0) + value
        with store.connection() as db:
            put(db, 'model_receipt', {'job_id':job['id'], 'phase':'classify_l1','usage':usage,'recorded_at':now()})
        with span(store, 'classification_validate', **fields):
            records = _validate_batch(response, packet, tax)
        with span(store, 'classification_publish', **fields), store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT status FROM research_jobs WHERE id=?',(job['id'],)).fetchone()[0] != 'running':
                return
            for record in records:
                save(db, record)
            status = _save_progress(db, job['id'], payload, {*known, *batch}, 'running')
        if status == 'queued':
            service.wake.set()
    except Exception as error:
        # Only a confirmed timeout or a rejected per-batch proposal has a useful smaller retry.
        local_failure = (isinstance(error, (TimeoutError, InvalidBatch)) or
                         str(error).startswith(('Wiki compilation timed out after 600 seconds','Invalid Wiki classification response')))
        emit(store, 'error', 'classification_batch', **fields, **error_fields(error), opinions=len(batch))
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT status FROM research_jobs WHERE id=?',(job['id'],)).fetchone()[0] != 'running':
                return
            if not local_failure:
                db.execute("UPDATE research_jobs SET status='failed',payload=?,error=?,updated_at=? WHERE id=?",
                           (encode(payload),str(error)[:600],now(),job['id']))
                return
            if len(batch)>1 and not retry_ids:
                mid = (len(batch)+1)//2
                waiting[:0] = [batch[:mid], batch[mid:]]
                emit(store, 'state', 'classification_split', **fields, opinions=len(batch), children=2)
            else:
                payload['failed_ids'].extend(batch)
            payload['last_batch_error'] = str(error)[:600]
            status = _save_progress(db, job['id'], payload, known, 'running')
        if status == 'queued':
            service.wake.set()
    finally:
        job_state(store, job, 'research_jobs')
        service.active = None
