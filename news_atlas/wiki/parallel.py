"""Bounded tree workers. Shared publication stays transactional and append-only."""
import concurrent.futures
import itertools
import json
import threading
import uuid
from .store import now, digest, PROMPT_VERSION, validate_proposal
from .forest import groups


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


def state(store, job, slot, **values):
    """Update one lane without overwriting another lane's progress or receipts."""
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload,status FROM jobs WHERE id=?', (job['id'],)).fetchone()
        if not row or row['status'] != 'running':
            return False
        payload = json.loads(row['payload'])
        lanes = payload.setdefault('workers_state', {})
        lanes.setdefault(str(slot), {}).update(values)
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
    service.active = (store, job['id'])
    halt = threading.Event()
    context_guard = threading.Condition()
    held = set()
    width = job['payload'].get('workers', 1)
    errors = []
    try:
        with store.connection() as db:
            rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))', (json.dumps(job['payload']['revisions']),))]
            context_rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))', (json.dumps(job['payload']['context_revisions']),))]
        rows = store.known(rows)
        forest = job['payload']['graph_selection']
        work = groups(rows, context_rows, forest)
        trees = (list(parts) for _, parts in itertools.groupby(work, lambda part: part[1]['root_id']))
        queue_guard = threading.Lock()

        def lane(slot):
            completed = 0
            while not halt.is_set() and running(service, store, job):
                # One whole tree per lane in a fair scheduling round. Subsequent
                # rounds consume only pending targets; no tree has two owners.
                if max_groups is not None and completed >= max_groups:
                    break
                with queue_guard:
                    tree = next(trees, None)
                if tree is None:
                    break
                info = tree[0][1]
                worker_job = {**job, 'call_id': uuid.uuid4().hex}
                state(store, job, slot, status='running', model=job['payload']['model'],
                      root_id=info['root_id'], tree=info['group'], total_trees=info['groups'],
                      title=tree[0][0][0]['title'], parts=len(tree), completed_parts=0,
                      targets=info['targets'], context_articles=info['context_articles'], error=None)
                try:
                    for group, meta, covered in tree:
                        if halt.is_set() or not running(service, store, job):
                            return
                        checkpoint = digest([PROMPT_VERSION, meta['root_id'],
                            [a['revision_id'] for a in group],
                            sorted(a['revision_id'] for _, _, targets in tree for a in targets), meta['part']])
                        with store.connection() as db:
                            saved = db.execute('SELECT 1 FROM wiki_segments WHERE key=?', (checkpoint,)).fetchone()
                        if saved:
                            state(store, job, slot, completed_parts=meta['part'], stage='reused')
                            continue
                        article = {**group[0], '_evidence':group, '_market':{}, '_group':meta,
                                   '_context_revisions':[a['revision_id'] for a in group],
                                   '_covered_articles':covered, '_checkpoint':checkpoint}
                        # Workers may share evidence, but never concurrently use
                        # the same mutable opinion revision as an update base.
                        claimed = set()
                        with context_guard:
                            while running(service, store, job) and not halt.is_set():
                                context = store.context({**article,'summary':' '.join(a['title']+' '+a['summary'][:1500] for a in group)})
                                claimed = {n['id'] for n in context if n['kind'] != 'ArticleRevision'}
                                if not (claimed & held):
                                    held.update(claimed)
                                    break
                                state(store, job, slot, stage='waiting_context')
                                context_guard.wait(.25)
                            else:
                                return
                        try:
                            refs = [n['id'] for n in context if n['kind'] == 'ArticleRevision']
                            with store.connection() as db:
                                from .research import taxonomy
                                article['_taxonomy'] = taxonomy(db)
                                article['_related_articles'] = [json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))', (json.dumps(refs),))]
                            for attempt in range(2):
                                if halt.is_set() or not store.reserve_call(job, article['revision_id']):
                                    return
                                stage = 'repairing' if attempt else 'compiling'
                                state(store, job, slot, stage=stage, part=meta['part'])
                                output = service.runner(store, worker_job, article, context)
                                if not isinstance(output, dict) or not isinstance(output.get('usage',{}), dict):
                                    raise ValueError('LLM回覆格式錯誤')
                                try:
                                    validate_proposal(article, output.get('proposal'), context)
                                except ValueError as error:
                                    store.reject(job, article, output.get('proposal'), error, output.get('usage',{}))
                                    if attempt:
                                        raise
                                    worker_job['repair'] = {'error':str(error), 'proposal':output.get('proposal')}
                                    continue
                                state(store, job, slot, stage='publishing')
                                try:
                                    if not store.publish(job, article, output['proposal'], context, output.get('usage',{})):
                                        return
                                except ValueError as error:
                                    store.reject(job, article, output['proposal'], error, output.get('usage',{}))
                                    raise
                                worker_job.pop('repair', None)
                                state(store, job, slot, completed_parts=meta['part'], stage='published')
                                break
                        finally:
                            with context_guard:
                                held.difference_update(claimed)
                                context_guard.notify_all()
                    completed += 1
                    state(store, job, slot, status='completed', stage='completed')
                except Exception as error:
                    state(store, job, slot, status='failed', error=str(error)[:600])
                    errors.append(error)
                    halt.set()
                    return
            if not completed:
                state(store, job, slot, status='idle', stage='idle')

        with concurrent.futures.ThreadPoolExecutor(max_workers=width, thread_name_prefix='wiki-tree') as pool:
            futures = [pool.submit(lane, slot) for slot in range(1, width+1)]
            for future in futures:
                future.result()
        if errors:
            raise errors[0]
        with store.connection() as db:
            db.execute("UPDATE jobs SET status=CASE WHEN done>=json_array_length(payload,'$.revisions') THEN 'completed' ELSE 'queued' END,updated_at=? WHERE id=? AND status='running'", (now(),job['id']))
        service.wake.set()
    except Exception as error:
        with service.lock, store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=? AND status='running'", (str(error)[:600],now(),job['id'])).rowcount
            if changed:
                cfg = store.config()
                cfg.update(enabled=False,catch_up=False)
                db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', ('config',json.dumps(cfg)))
    finally:
        service.active = None
