"""Bounded tree workers. Shared publication stays transactional and append-only."""
from .trace import span, emit, job_fields, admitted, job_state, error_fields
import concurrent.futures
import itertools
import json
import threading
import uuid
from .store import now, digest, PROMPT_VERSION, validate_proposal
from .forest import groups
from . import document_evidence


def tree_coverage(config, rows, missing):
    forest = config.get('graph_selection', {})
    if forest.get('mode') != 'coverage':
        return None
    keys = {(r['provider'], r['id']) for r in rows}
    pending = {(r['provider'], r['id']) for r in missing}
    targets = [keys & {(a['provider'], a['id']) for a in t['targets']} for t in forest['trees']]
    targets = [t for t in targets if t]
    return {'total': len(targets), 'done': sum(not (t & pending) for t in targets),
            'pending': sum(bool(t & pending) for t in targets)}


def state(store, job, slot, *, failure=None, **values):
    """Update one lane without overwriting another lane's progress or receipts."""
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload,status FROM jobs WHERE id=?', (job['id'],)).fetchone()
        if not row or row['status'] != 'running':
            return False
        payload = json.loads(row['payload'])
        lanes = payload.setdefault('workers_state', {})
        if 'root_id' in values or values.get('status') == 'idle':
            lanes[str(slot)] = {}
        lanes.setdefault(str(slot), {}).update(values)
        if failure:
            payload.setdefault('failed_trees', {})[failure['root_id']] = failure
            payload['failed_tree_count'] = len(payload['failed_trees'])
            payload['last_tree_failure'] = failure
        db.execute('UPDATE jobs SET payload=?,updated_at=? WHERE id=?', (json.dumps(payload), now(), job['id']))
    return True


def running(service, store, job):
    if service.stop.is_set():
        return False
    with store.connection() as db:
        return db.execute("SELECT 1 FROM jobs WHERE id=? AND status='running'", (job['id'],)).fetchone() is not None


def process(service, store, max_groups=None):
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if not row:
            return
        job = dict(row)
        job['payload'] = json.loads(job['payload'])
        db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?", (now(), job['id']))
    service.active = (store, job['id']);admitted(store,job)
    halt = threading.Event()
    width = job['payload'].get('workers', 1)
    errors = []
    try:
        if width>1 and service.runner==service.bridge:
            capacity=service.bridge_request('/status',timeout=5).get('wiki_worker_limit',1)
            if capacity<width:
                raise ValueError(f'Wiki bridge supports {capacity} worker(s), job requests {width}. Restart the host bridge: ./run.sh chat stop && ./run.sh chat start')
        with store.connection() as db:
            rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))', (json.dumps(job['payload']['revisions']),))]
            context_rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))', (json.dumps(job['payload']['context_revisions']),))]
        rows = store.known(rows)
        forest = job['payload']['graph_selection']
        work = itertools.chain(document_evidence.groups([a for a in rows if a.get('document')]),
                               groups([a for a in rows if not a.get('document')],context_rows,forest))
        failed_roots = job['payload'].get('failed_trees', {})
        trees = (list(parts) for root, parts in itertools.groupby(work, lambda part: part[1]['root_id'])
                 if root not in failed_roots)
        queue_guard = threading.Lock()
        first_wave = set(range(1, width+1))

        def lane(slot):
            attempted = 0
            while not halt.is_set() and running(service, store, job):
                if max_groups is not None and attempted >= max_groups:
                    with queue_guard:
                        first_wave.discard(slot)
                        peers_still_on_first_trees = bool(first_wave)
                    # A slow initial tree already keeps this stock's turn open.
                    # Fill idle lanes until the stock can yield to a waiting peer.
                    if not peers_still_on_first_trees and (width == 1 or service.other_work_waiting(store)):
                        break
                with span(store,'tree_dispatch',**job_fields(store,job),worker=slot), queue_guard:
                    tree = next(trees, None)
                if tree is None:
                    break
                info = tree[0][1]
                attempted += 1
                stage = 'context'
                worker_job = {**job, 'worker':slot, 'call_id': uuid.uuid4().hex}
                state(store, job, slot, status='running', stage=stage, model=job['payload']['model'],
                      root_id=info['root_id'], tree=info['group'], total_trees=info['groups'],
                      title=tree[0][0][0]['title'], parts=len(tree), completed_parts=0,
                      targets=info['targets'], context_articles=info['context_articles'], error=None)
                try:
                    for group, meta, covered in tree:
                        stage = 'context'
                        if halt.is_set() or not running(service, store, job):
                            return
                        segment=[meta['root_id'],[a['revision_id'] for a in group],
                                 sorted(a['revision_id'] for _, _, targets in tree for a in targets),meta['part']]
                        keys=[digest([PROMPT_VERSION, *segment, 'vix'])] if job['payload'].get('include_vix') else [
                            digest([PROMPT_VERSION, *segment]),digest(['wiki-extract-v8', *segment])]
                        checkpoint=keys[0]
                        with store.connection() as db:
                            saved=db.execute('SELECT 1 FROM wiki_segments WHERE key IN (SELECT value FROM json_each(?))',(json.dumps(keys),)).fetchone()
                        if saved:
                            emit(store,'state','checkpoint',**job_fields(store,job),worker=slot,root_id=meta['root_id'],part=meta['part'],status='reused')
                            state(store, job, slot, completed_parts=meta['part'], stage='reused')
                            continue
                        article = {**group[0], '_evidence':group, '_market':{}, '_group':meta,
                                   '_context_revisions':None if group[0].get('document') else [a['revision_id'] for a in group],
                                   '_covered_articles':covered, '_checkpoint':checkpoint}
                        # Reading immutable revisions does not reserve them. An actual
                        # UPDATES collision is checked inside the publish transaction.
                        state(store, job, slot, stage=stage, part=meta['part'])
                        context,reuse = store.prepare_segment(job, article)
                        for attempt in range(2):
                            if halt.is_set() or (reuse is None and not store.reserve_call(job, article['revision_id'])):
                                return
                            stage = 'reused' if reuse else 'repairing' if attempt else 'compiling'
                            state(store, job, slot, stage=stage, part=meta['part'], bridge_call_id=worker_job['call_id'])
                            output = reuse if reuse is not None else service.run_model(store, worker_job, article, context)
                            stage = 'validating'
                            if not isinstance(output, dict) or not isinstance(output.get('usage',{}), dict):
                                raise ValueError('LLM回覆格式錯誤')
                            try:
                                with span(store,'validate',**job_fields(store,job),worker=slot):
                                    validate_proposal(article, output.get('proposal'), context)
                            except ValueError as error:
                                store.reject(job, article, output.get('proposal'), error, output.get('usage',{}))
                                if attempt:
                                    raise
                                worker_job['repair'] = {'error':str(error), 'proposal':output.get('proposal')}
                                continue
                            stage = 'publishing'
                            state(store, job, slot, stage=stage)
                            try:
                                if not store.publish(job, article, output['proposal'], context, output.get('usage',{})):
                                    return
                            except ValueError as error:
                                store.reject(job, article, output['proposal'], error, output.get('usage',{}))
                                raise
                            worker_job.pop('repair', None)
                            state(store, job, slot, completed_parts=meta['part'], stage='published')
                            break
                    state(store, job, slot, status='completed', stage='completed')
                except Exception as error:
                    code = getattr(error, 'code', None) or error_fields(error)['error_code']
                    if code in ('authentication','quota','bridge_unavailable','catalog') or not isinstance(error, (ValueError, RuntimeError, TimeoutError)):
                        errors.append(error)
                        halt.set()
                        state(store, job, slot, status='failed', error=str(error)[:600])
                        return
                    failure = {'root_id':info['root_id'], 'tree':info['group'], 'part':meta['part'],
                               'stage':stage, 'code':code, 'sdk_stage':getattr(error,'sdk_stage',None), 'error':str(error)[:600]}
                    state(store, job, slot, failure=failure, status='failed', error=failure['error'], error_code=code, sdk_stage=failure['sdk_stage'])
                    emit(store,'state','tree_failure',**job_fields(store,job),worker=slot,
                         root_id=info['root_id'],part=meta['part'],failed_stage=stage,error_code=code)
            if not attempted:
                state(store, job, slot, status='idle', stage='idle')

        with concurrent.futures.ThreadPoolExecutor(max_workers=width, thread_name_prefix='wiki-tree') as pool:
            futures = [pool.submit(lane, slot) for slot in range(1, width+1)]
            for future in futures:
                future.result()
        if errors:
            raise errors[0]
        if service.stop.is_set():
            # Startup recovery owns interrupted turns with potentially unreported usage.
            return
        more = next(trees, None) is not None
        with service.lock, store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT json_extract(payload,'$.failed_tree_count'), json_extract(payload,'$.last_tree_failure.error') FROM jobs WHERE id=? AND status='running'", (job['id'],)).fetchone()
            if row:
                failed, last_error = row
                status = 'queued' if more else ('failed' if failed else 'completed')
                message = last_error if status == 'failed' else None
                db.execute('UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=?',(status,message,now(),job['id']))
                if status == 'failed':
                    # Keep an enabled news watcher available for fresh evidence.
                    # Only explicit continuation should submit these revisions again.
                    db.execute("""INSERT OR REPLACE INTO metadata(key,value)
                        SELECT 'deferred_l1_revisions',json_group_array(revision) FROM (
                            SELECT value AS revision FROM json_each((SELECT value FROM metadata WHERE key='deferred_l1_revisions'))
                            UNION SELECT r.value FROM jobs j,json_each(j.payload,'$.revisions') r WHERE j.id=?
                        ) AS revision_list WHERE NOT EXISTS (SELECT 1 FROM extractions e WHERE e.revision=revision_list.revision)""",(job['id'],))
                    db.execute("UPDATE metadata SET value=json_set(value,'$.catch_up',json('false')) WHERE key='config'")
        service.wake.set()
    except Exception as error:
        emit(store,'error','job',**job_fields(store,job),**error_fields(error))
        with service.lock, store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=? AND status='running'", (str(error)[:600],now(),job['id'])).rowcount
            if changed:
                cfg = store.config()
                cfg.update(enabled=False,catch_up=False)
                db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('config',json.dumps(cfg)))
    finally:
        job_state(store,job)
        service.active = None
