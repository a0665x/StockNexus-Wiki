"""Versioned local document collections. No ticker, remote fetch or model dependency."""
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile
import urllib.parse

SLUG = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}')
NODE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}')
KINDS = {'folder', 'document', 'section', 'note', 'claim'}
RELATIONS = {'cites', 'supports', 'contradicts', 'updates', 'related'}
FIELDS = {'id', 'kind', 'title', 'parent_id', 'path', 'locator', 'text', 'published_at', 'links', 'layer', 'question'}
DB_NAME = 'documents.sqlite3'
SCHEMA = """CREATE TABLE IF NOT EXISTS versions (
    source TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(source,id,revision));
CREATE VIEW IF NOT EXISTS current_nodes AS
    SELECT v.* FROM versions v WHERE revision=(
        SELECT max(n.revision) FROM versions n WHERE n.source=v.source AND n.id=v.id);
"""


def slug(name):
    if not isinstance(name, str) or not SLUG.fullmatch(name):
        raise ValueError('Use 1–64 lowercase letters, numbers, underscores or hyphens for collection/source IDs')
    return name


def folder(root, collection):
    graph = Path(root).resolve() / 'graph'
    path = graph / slug(collection)
    if graph.is_symlink() or path.is_symlink() or (path / DB_NAME).is_symlink():
        raise ValueError('Unexpected symlink inside the graph directory')
    return path


def string(value, field, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'Invalid {field} (maximum {limit} characters)')
    return value


def node_id(value):
    if not isinstance(value, str) or not NODE.fullmatch(value):
        raise ValueError('Invalid node ID')
    return value


def validate(row, source):
    if not isinstance(row, dict) or set(row) - FIELDS:
        raise ValueError('Expected a record with only documented fields')
    node_id(row.get('id'))
    if row.get('kind') not in KINDS:
        raise ValueError('Invalid kind')
    string(row.get('title'), 'title', 2000)
    if 'text' in row and (not isinstance(row['text'], str) or len(row['text']) > 120000):
        raise ValueError('Invalid text (split long documents into sections)')
    if row.get('parent_id') is not None:
        node_id(row['parent_id'])
    if 'path' in row:
        path = string(row['path'], 'path', 2000)
        if '\\' in path or PurePosixPath(path).is_absolute() or '..' in path.split('/') or re.match(r'^[A-Za-z]+:', path):
            raise ValueError('path must be relative to the original document folder')
    if 'locator' in row:
        loc = row['locator']
        if not isinstance(loc, dict) or not loc or set(loc) - {'page','heading','line'}:
            raise ValueError('Use page, heading or line in locator')
        for key, value in loc.items():
            if key == 'heading':
                string(value, key, 500)
            elif type(value) is not int or value < 1:
                raise ValueError('page/line must be positive integers')
    if row.get('published_at') is not None:
        date = string(row['published_at'], 'published_at', 10)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
            raise ValueError('Use YYYY-MM-DD or null')
        dt.date.fromisoformat(date)
    links = row.get('links', [])
    if not isinstance(links, list):
        raise ValueError('Expected a links array')
    for link in links:
        if not isinstance(link, dict) or set(link) - {'type','source','id','revision'} or link.get('type') not in RELATIONS:
            raise ValueError('Invalid link')
        slug(link.get('source',source))
        node_id(link.get('id'))
        if 'revision' in link and (type(link['revision']) is not int or link['revision'] < 1):
            raise ValueError('Invalid citation revision')
    if row.get('kind') == 'claim':
        if row.get('layer') not in ('L1','L2') or not any(l['type']=='cites' and 'revision' in l for l in links):
            raise ValueError('Claims need a layer and a citation to a specific revision')
        if row['layer']=='L2':
            string(row.get('question'), 'L2 research question', 2000)
    elif 'layer' in row or 'question' in row:
        raise ValueError('Only claims have a Wiki layer or research question')


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def read_records(stream, source):
    records = {}
    duplicates = 0
    for index, line in enumerate(stream, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            validate(row, source)
            ident = row['id']
            if ident in records:
                if records[ident] != row:
                    raise ValueError('Conflicting definitions of '+ident)
                duplicates += 1
            records[ident] = row
        except (ValueError, TypeError) as exc:
            raise ValueError(f'Line {index}: {exc}') from exc
    if not records:
        raise ValueError('The JSONL input is empty')
    return records, duplicates


def validate_graph(db, source, records, revisions):
    parents = {ident:json.loads(body).get('parent_id') for ident,body in
               db.execute('SELECT id,body FROM current_nodes WHERE source=?',(source,))}
    parents.update({ident:r.get('parent_id') for ident,r in records.items()})
    done = set()
    for ident in records:
        current = ident
        trail = set()
        while current is not None and current not in done:
            if current in trail or current not in parents:
                raise ValueError(f'{ident}: cyclic or missing parent {current}')
            trail.add(current)
            current = parents[current]
        done.update(trail)
        for link in records[ident].get('links', []):
            owner, target = link.get('source',source), link['id']
            revision = link.get('revision')
            if owner == source and target in revisions and (revision is None or revision == revisions[target]):
                continue
            if not db.execute('SELECT 1 FROM versions WHERE source=? AND id=? AND (? IS NULL OR revision=?) LIMIT 1',
                              (owner,target,revision,revision)).fetchone():
                raise ValueError(f'{ident}: missing link target {owner}/{target} revision {revision}')


def archive(base, source, records):
    directory = base/'imports'/source
    if (base/'imports').is_symlink() or directory.is_symlink():
        raise ValueError('Unexpected symlink in archive directory')
    directory.mkdir(parents=True, exist_ok=True)
    data = ''.join(encode(records[k])+'\n' for k in sorted(records)).encode()
    path = directory/(hashlib.sha256(data).hexdigest()+'.jsonl')
    if not path.exists():
        fd, name = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd,'wb') as out:
                out.write(data)
            os.replace(name, path)
        finally:
            Path(name).unlink(missing_ok=True)
    return path


def import_records(root, collection, source, input_path, dry_run):
    with Path(input_path).open(encoding='utf-8-sig') as stream:
        return import_stream(root, collection, source, stream, dry_run)


def import_stream(root, collection, source, stream, dry_run):
    slug(source)
    base = folder(root, collection)
    records, duplicates = read_records(stream, source)
    path = base/DB_NAME
    if dry_run:
        conn = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True) if path.exists() else sqlite3.connect(':memory:')
    else:
        base.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30)
    with contextlib.closing(conn) as db, db:
        if not dry_run or not path.exists():
            db.executescript(SCHEMA)
        db.execute('BEGIN' if dry_run else 'BEGIN IMMEDIATE')
        known = {ident:(revision,body) for ident,revision,body in
                 db.execute('SELECT id,revision,body FROM current_nodes WHERE source=?',(source,))}
        report = dict(collection=collection, source=source, dry_run=dry_run, added=0, updated=0,
                      unchanged=0, duplicate_lines=duplicates, undated=sum(not r.get('published_at') for r in records.values()))
        writes, revisions = [], {}
        for ident, row in records.items():
            previous, body = known.get(ident, (0,None))
            content = encode(row)
            changed = content != body
            report['unchanged' if not changed else 'updated' if previous else 'added'] += 1
            revisions[ident] = previous + int(changed)
            if changed:
                writes.append((source,ident,revisions[ident],content))
        validate_graph(db,source,records,revisions)
        if not dry_run:
            db.executemany('INSERT INTO versions VALUES (?,?,?,?)', writes)
            report['archive'] = str(archive(base,source,records))
    return report


def query(root, collection=None, source=None, ident=None, revision=None):
    if collection is None:
        entries = []
        for path in sorted((Path(root)/'graph').glob('*/'+DB_NAME)):
            if not SLUG.fullmatch(path.parent.name) or path.is_symlink() or path.parent.is_symlink():
                continue
            with contextlib.closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as db:
                sources = dict(db.execute('SELECT source,count(*) FROM current_nodes GROUP BY source'))
            if sources:
                entries.append({'id':path.parent.name,'sources':sources})
        return {'collections':entries}
    path = folder(root, collection)/DB_NAME
    if not path.is_file():
        raise KeyError('Unknown collection')
    with contextlib.closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as db:
        if ident is not None:
            row = db.execute('SELECT body FROM versions WHERE source=? AND id=? AND revision=?',
                             (slug(source),node_id(ident),int(revision))).fetchone()
            if not row:
                raise KeyError('Unknown revision')
            return {'record':json.loads(row[0]),'revision':int(revision),'source':source}
        clause, args = (' WHERE source=?',(slug(source),)) if source is not None else ('',())
        rows = db.execute('SELECT source,id,revision,body FROM current_nodes'+clause+' ORDER BY source,id', args)
        return {'collection':collection,'nodes':[dict(json.loads(body),source=owner,revision=rev) for owner,_,rev,body in rows]}


def handle(handler):
    from .wiki.http import writable
    if not writable(handler):
        handler.json_response(403, {'error':'Use an allowed same-origin host'}); return
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query,keep_blank_values=True)
    try:
        if set(params)-{'collection','source','id','revision'} or any(len(v)!=1 for v in params.values()):
            raise ValueError('Invalid parameters')
        if ('source' in params and 'collection' not in params) or (('id' in params or 'revision' in params)
                and not {'source','collection','id','revision'} <= params.keys()):
            raise ValueError('A revision lookup requires collection, source, id and revision')
        result = query(handler.store.path.parent, **{('ident' if k=='id' else k):v[0] for k,v in params.items()})
        handler.json_response(200,result)
    except (TypeError,ValueError) as exc:
        handler.json_response(400,{'error':str(exc)})
    except KeyError as exc:
        handler.json_response(404,{'error':str(exc)})
    except sqlite3.Error:
        handler.json_response(503,{'error':'Document collection is unavailable'})

def handle_import(handler):
    from .wiki.http import writable
    if not writable(handler):
        handler.json_response(403, {'error': 'Use an allowed same-origin host'})
        return
    if handler.headers.get_content_type() != 'application/x-ndjson':
        handler.json_response(415, {'error': 'Expected a UTF-8 JSONL file (application/x-ndjson)'})
        return
    try:
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(handler.path).query, keep_blank_values=True)
        if (set(params) != {'collection', 'source', 'mode'} or any(len(v) != 1 for v in params.values())
                or params['mode'][0] not in ('preview', 'apply')):
            raise ValueError('Provide collection, source and mode (preview or apply)')
        length = int(handler.headers.get('Content-Length', '0'))
        if length > 32 * 1024 * 1024:
            handler.json_response(413, {'error': 'Web uploads support up to 32 MiB. Use the CLI for larger exports.'})
            return
        if length <= 0:
            raise ValueError('Select a non-empty JSONL file')
        data = handler.rfile.read(length)
        if len(data) != length:
            raise ValueError('Incomplete upload')
        with io.TextIOWrapper(io.BytesIO(data), encoding='utf-8-sig') as stream:
            report = import_stream(handler.store.path.parent, params['collection'][0], params['source'][0],
                                   stream, params['mode'][0] == 'preview')
        report.pop('archive', None)
        handler.json_response(200, report)
    except ValueError as exc:
        handler.json_response(400, {'error': str(exc)})
    except (OSError, sqlite3.Error):
        handler.json_response(503, {'error': 'Document storage is unavailable'})
