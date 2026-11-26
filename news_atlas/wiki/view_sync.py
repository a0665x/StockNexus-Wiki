"""Incremental views of a saved Wiki. The server retains hashes, the tab retains the data."""
from collections import OrderedDict
import hashlib
import json
import threading

from .store import digest


# Each key is unique within the ordered projection. Other sections are replaced as a unit.
ROW_KEYS = {'nodes':'id', 'edges':'revision_id', 'opinion_index':'id', 'versions':'version',
            'changes':'version', 'timeline':'date'}
MAP_FIELDS = ('histories','opinion_groups')


def graph_epoch(db, store):
    """Published revisions and derived classifications have independent identities."""
    photo = db.execute('''SELECT (SELECT COALESCE(max(version),0) FROM versions),
        (SELECT count(*) FROM nodes),(SELECT count(*) FROM edges),(SELECT count(*) FROM articles),
        count(*), COALESCE(max(rowid),0) FROM research_objects
        WHERE owner='' AND kind IN ('taxonomy','classification')''').fetchone()
    stat = store.path.stat()
    return digest([stat.st_dev, stat.st_ino, *photo])


def disk_stamp(store):
    result = []
    for path in (store.path, store.path.with_name(store.path.name+'-wal')):
        try:
            stat = path.stat()
            result.append((stat.st_dev,stat.st_ino,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_size))
        except FileNotFoundError:
            result.append(None)
    return result


def manifest(graph):
    rows = {field:{row[key]:digest(row) for row in graph[field]} for field,key in ROW_KEYS.items()}
    maps = {field:{key:digest(value) for key,value in graph[field].items()} for field in MAP_FIELDS}
    other = {key:digest(value) for key,value in graph.items() if key not in rows and key not in maps}
    return rows, maps, other


def graph_delta(graph, old, new):
    rows, maps, fields = new
    delta = {'set':{k:graph[k] for k in fields if fields[k]!=old[2].get(k)}, 'rows':{}, 'maps':{}}
    for field, hashes in rows.items():
        previous = old[0][field]
        order_changed = list(hashes) != list(previous)
        if order_changed or hashes != previous:
            key = ROW_KEYS[field]
            updated = [row for row in graph[field] if hashes[row[key]] != previous.get(row[key])]
            delta['rows'][field] = {'key':key,'upsert':updated}
            if order_changed:
                delta['rows'][field]['order'] = list(hashes)  # excludes removed IDs, preserves render order
    for field, hashes in maps.items():
        previous = old[1][field]
        if hashes != previous:
            delta['maps'][field] = {'set':{k:graph[field][k] for k in hashes if hashes[k] != previous.get(k)},
                                    'remove':sorted(previous.keys()-hashes.keys())}
    return delta


class GraphViews:
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def read(self, store, params):
        options = {name:params.get(name,[None])[0] for name in ('version','as_of','start','end')}
        scope = (store.instrument, *options.values())
        since = params.get('since',[''])[0]
        stamp = disk_stamp(store)
        with self.lock:
            old = self.entries.get((scope,since))
            if old and old[0] == stamp:
                self.entries.move_to_end((scope,since))
                return {'kind':'unchanged','instrument':store.instrument,'token':since,'epoch':old[1]}
        with store.connection() as db:
            db.execute('BEGIN')
            epoch = graph_epoch(db,store)
            graph = store.graph(**options, connection=db, include_activity=False)
        hashes = manifest(graph)
        # Normal JSON sorting loses array order. Include ordered keys in the snapshot identity.
        token = digest([scope, hashes, {k:list(v) for k,v in hashes[0].items()}])
        with self.lock:
            self.entries[(scope,token)] = (stamp if stamp==disk_stamp(store) else None, epoch, hashes)
            self.entries.move_to_end((scope,token))
            while len(self.entries)>12:
                self.entries.popitem(last=False)
        reply = {'instrument':store.instrument,'epoch':epoch,'token':token}
        if old and token == since:
            return {**reply,'kind':'unchanged'}
        if old:
            return {**reply,'kind':'delta','base':since,**graph_delta(graph,old[2],hashes)}
        return {**reply,'kind':'full','graph':graph}


JOB_FIELDS = ('last_decisions','model','workers','workers_state','operation','stage','strategy','current_title','current_size',
              'failed_tree_count','last_tree_failure','current_date','group_info','last_usage','reasoning_effort','done','usage','recovering','last_batch_error')


def compact_jobs(db, table):
    classifier = table == 'research_jobs'
    columns = ', '.join(f"'{k}', json_extract(payload,'$.{k}')" for k in JOB_FIELDS)
    total = "json_extract(payload,'$.total')" if classifier else "json_array_length(payload,'$.revisions')"
    where = "WHERE json_extract(payload,'$.operation')='classify_l1'" if classifier else ''
    extra = '' if classifier else ',done,usage'
    query = f'''SELECT id,status,created_at,updated_at,error{extra}, json_object({columns},'total',{total},
        'failed_count',json_array_length(payload,'$.failed_ids')) AS payload FROM {table} {where}
        ORDER BY created_at DESC LIMIT {1 if classifier else 30}'''
    jobs = []
    for row in db.execute(query):
        payload = {k:v for k,v in json.loads(row['payload']).items() if v is not None}
        job = {**dict(row),'payload':payload}
        if not classifier:
            job['usage'] = json.loads(row['usage'])
            if job['status'] in ('running','queued'):
                roots = {worker.get('root_id') for worker in (payload.get('workers_state') or {}).values()}
                roots.add((payload.get('group_info') or {}).get('root_id'))
                roots.discard(None)
                if roots:
                    trees = db.execute('''SELECT t.value FROM jobs j,json_each(j.payload,'$.graph_selection.trees') t
                        WHERE j.id=? AND json_extract(t.value,'$.root_id') IN (SELECT value FROM json_each(?))''',
                        (row['id'],json.dumps(sorted(roots))))
                    payload['graph_selection'] = {'trees':[json.loads(r[0]) for r in trees]}
        jobs.append(job)
    return jobs


def view_state(service,store,config_token):
    with store.connection() as db:
        db.execute('BEGIN')
        row = db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
        raw = row[0] if row else '{"enabled":false,"model":"","subscriptions":[]}'
        tag = hashlib.sha256(raw.encode()).hexdigest()
        data = {'instrument':store.instrument,'config_token':tag,'epoch':graph_epoch(db,store),
                'version':db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0],
                'jobs':compact_jobs(db,'jobs'),'classification_jobs':compact_jobs(db,'research_jobs')}
        if config_token != tag:
            data['config'] = {k:v for k,v in json.loads(raw).items() if k not in ('revision_ids','document_ids','graph_context_revisions','graph_edges')}
            selection = data['config'].get('graph_selection') or {}
            if selection.get('mode') == 'coverage' and data['config'].get('graph_universe'):
                # Settings rebuild the forest from its universe; open worker links use the job's frozen trees.
                data['config']['graph_selection'] = {k:v for k,v in selection.items() if k!='trees'}
    # Read transient SDK milestones outside the SQLite snapshot. Missing bridge
    # telemetry must never hide already-published database progress.
    for job in data['jobs']:
        lanes = job['payload'].get('workers_state') or {}
        if job['status']=='running' and any(w.get('status')=='running' and w.get('stage') in ('compiling','repairing') for w in lanes.values()):
            try:
                progress = service.bridge_request('/wiki/progress',{'job_id':job['id']},timeout=1)
            except RuntimeError:
                continue
            for worker in lanes.values():
                call = progress.get(worker.get('bridge_call_id'))
                if call and worker.get('status')=='running' and worker.get('stage') in ('compiling','repairing'):
                    worker['sdk_stage'] = call['sdk_stage']
                    worker['sdk_quiet_minutes'] = call['last_event_ms']//60000
    data['coverage'] = service.coverage(store)
    return data
