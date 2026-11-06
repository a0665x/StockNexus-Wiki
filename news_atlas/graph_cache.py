"""Disposable, bounded graph cache; never a source of news or coverage truth."""
import concurrent.futures
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import threading
import time
import zlib

# Bump whenever normalization, classification or relation semantics change.
VERSION = 'graph-v1'
MAX_ENTRIES = 32
MAX_BYTES = 256 * 1024 * 1024
_log = logging.getLogger(__name__)
_guard = threading.Lock()
_inflight = {}


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def _connect(path):
    db = sqlite3.connect(path, timeout=1)
    try:
        db.execute('CREATE TABLE IF NOT EXISTS graphs (key TEXT PRIMARY KEY, payload BLOB NOT NULL, used REAL NOT NULL)')
        return db
    except Exception:
        db.close()
        raise


def _read(path, key):
    db = _connect(path)
    try:
        with db:
            row = db.execute('SELECT payload FROM graphs WHERE key=?', (key,)).fetchone()
            if row:
                # Decode before accepting; corrupted entries are overwritten on rebuild.
                value = json.loads(zlib.decompress(row[0]))
                db.execute('UPDATE graphs SET used=? WHERE key=?', (time.time(), key))
                if not isinstance(value, dict) or value.get("relations_pending") is not False:
                    raise ValueError("incomplete cached graph")
                return row[0], value
    finally:
        db.close()


def _write(path, key, payload):
    if len(payload) > MAX_BYTES:
        return
    db = _connect(path)
    try:
        with db:
            db.execute('INSERT OR REPLACE INTO graphs VALUES (?,?,?)', (key, payload, time.time()))
            rows = db.execute('SELECT key,length(payload) FROM graphs ORDER BY used DESC,key').fetchall()
            size = 0
            for index, (ident, length) in enumerate(rows):
                size += length
                if index >= MAX_ENTRIES or size > MAX_BYTES:
                    db.execute('DELETE FROM graphs WHERE key=?', (ident,))
    finally:
        db.close()


def _identity(store, rows, channels, cfg):
    key = hashlib.sha256(_encode([VERSION, rows, channels, cfg])).hexdigest()
    path = str(Path(str(store.path) + '.graphs.sqlite3').resolve())
    return path, key


def lookup_cached(store, rows, channels=None, relation_settings=None):
    """Read an exact completed graph only; never start or wait for computation."""
    from .channels import definitions
    from .relation_settings import settings
    started = time.perf_counter()
    path, key = _identity(store, rows, channels or definitions(), settings(relation_settings))
    try:
        cached = _read(path, key)
    except (sqlite3.Error, OSError, ValueError, zlib.error):
        cached = None
    _log.info('graph_lookup %s', json.dumps({'status':'hit' if cached else 'miss',
              'articles':len(rows), 'total_ms':round((time.perf_counter()-started)*1000,2)}))
    return cached[1] if cached else None


def build_cached(store, build, rows, channels=None, relation_settings=None, include_relations=True):
    """Exact ordered input reuse, with one in-process producer per DB/key.

    Futures contain compressed bytes, so every caller gets independent mutable data.
    Disk failures only disable caching; computation errors propagate to all waiters.
    """
    if not include_relations:
        return build(rows, channels, relation_settings, include_relations=False)
    from .channels import definitions
    from .relation_settings import settings
    started = time.perf_counter()
    channels = channels or definitions()
    cfg = settings(relation_settings)
    path, key = _identity(store, rows, channels, cfg)
    identity = (path, key)
    timings = {'key_ms': round((time.perf_counter()-started)*1000, 2)}
    with _guard:
        future = _inflight.get(identity)
        owner = future is None
        if owner:
            future = concurrent.futures.Future()
            _inflight[identity] = future
    status = 'shared'
    try:
        if not owner:
            return json.loads(zlib.decompress(future.result()))
        tick = time.perf_counter()
        try:
            cached = _read(path, key)
        except (sqlite3.Error, OSError, ValueError, zlib.error):
            cached = None
        timings['read_ms'] = round((time.perf_counter()-tick)*1000, 2)
        status = 'hit' if cached is not None else 'miss'
        if cached is not None:
            payload, result = cached
        else:
            tick = time.perf_counter()
            result = build(rows, channels, relation_settings=cfg)
            timings['compute_ms'] = round((time.perf_counter()-tick)*1000, 2)
            tick = time.perf_counter()
            payload = zlib.compress(_encode(result), level=1)
            timings['encode_ms'] = round((time.perf_counter()-tick)*1000, 2)
        if status == 'miss':
            tick = time.perf_counter()
            try:
                _write(path, key, payload)
            except (sqlite3.Error, OSError):
                status = 'uncached'
            timings['write_ms'] = round((time.perf_counter()-tick)*1000, 2)
        future.set_result(payload)
        return result
    except BaseException as error:
        if owner:
            future.set_exception(error)
        raise
    finally:
        if owner:
            with _guard:
                _inflight.pop(identity, None)
        timings['total_ms'] = round((time.perf_counter()-started)*1000, 2)
        _log.info('graph_cache %s', json.dumps({'status': status, 'articles': len(rows), **timings}))
