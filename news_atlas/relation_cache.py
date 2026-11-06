"""Persistent pair scores, separate from view-dependent edge selection.

Compressed blocks include negative results. Keys cover content and scoring rules,
not visibility or neighbor limits. Eviction affects cost only, never correctness.
"""
import hashlib
import json
import sqlite3
import time
import zlib

VERSION = 'pair-score-v1'
MISSING = object()
MAX_BLOCK_PAIRS = 4096
MAX_DISK_BYTES = 128 * 1024 * 1024


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class PairCache:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=15)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS pair_blocks (rules TEXT, anchor TEXT, payload BLOB NOT NULL, touched REAL NOT NULL, PRIMARY KEY(rules,anchor))')
        self.db.commit()
        self.blocks = {}
        self.dirty = set()
        self.hits = self.computed = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        try:
            self.flush()
        finally:
            self.db.close()

    def bind(self, rows, cfg):
        # Selection changes re-rank cached scores; content/rule changes invalidate them.
        rules = fingerprint([VERSION, {k:v for k,v in cfg.items() if k not in ('adaptive', 'coverage_first', 'internal_neighbors', 'cross_neighbors')}])
        revisions = [fingerprint({k:row.get(k) for k in ('id','title','entities','topics','published_at','analysis_version')}) for row in rows]
        if getattr(self, 'allowed', None) != set(revisions):
            self.flush()
            self.blocks.clear()
        self.allowed = set(revisions)
        return rules, revisions

    def _block(self, rules, a, b):
        a, b = sorted((a, b))
        key = (rules, a)
        if key not in self.blocks:
            row = self.db.execute('SELECT payload FROM pair_blocks WHERE rules=? AND anchor=?', key).fetchone()
            self.blocks[key] = {k:v for k,v in json.loads(zlib.decompress(row[0])).items() if k in self.allowed} if row else {}
        return key, b, self.blocks[key]

    def get(self, rules, a, b):
        _, b, block = self._block(rules, a, b)
        value = block.get(b, MISSING)
        if value is not MISSING:
            self.hits += 1
        return value

    def put(self, rules, a, b, score):
        key, b, block = self._block(rules, a, b)
        block[b] = score
        self.dirty.add(key)
        self.computed += 1

    def flush(self):
        # Short transaction; never hold the writer lock during relation computation.
        if not self.dirty:
            return
        with self.db:
            for key in self.dirty:
                row = self.db.execute('SELECT payload FROM pair_blocks WHERE rules=? AND anchor=?', key).fetchone()
                merged = json.loads(zlib.decompress(row[0])) if row else {}
                merged.update(self.blocks[key])
                merged = dict(list(merged.items())[-MAX_BLOCK_PAIRS:])
                packed = zlib.compress(json.dumps(merged, separators=(',', ':')).encode(), 1)
                self.db.execute('INSERT OR REPLACE INTO pair_blocks VALUES (?,?,?,?)', (*key, packed, time.time()))
            size = self.db.execute('SELECT COALESCE(SUM(length(payload)),0) FROM pair_blocks').fetchone()[0]
            if size > MAX_DISK_BYTES:
                for rules, anchor, length in self.db.execute('SELECT rules,anchor,length(payload) FROM pair_blocks ORDER BY touched').fetchall():
                    self.db.execute('DELETE FROM pair_blocks WHERE rules=? AND anchor=?', (rules, anchor))
                    size -= length
                    if size <= MAX_DISK_BYTES * .9:
                        break
        self.dirty.clear()
        self.blocks.clear()
