"""SQLite article cache. Coverage is recorded from successful source requests, never article dates."""
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

DEFAULT_DB = Path(__file__).resolve().parents[1] / 'data' / 'news-atlas.sqlite3'
DAY = dt.timedelta(days=1)

def dates(start, end):
    day = dt.date.fromisoformat(start)
    stop = dt.date.fromisoformat(end)
    while day < stop:
        yield day.isoformat()
        day += DAY

def contiguous(days):
    out = []
    for day in sorted(set(days)):
        end = (dt.date.fromisoformat(day) + DAY).isoformat()
        if out and out[-1][1] == day:
            out[-1] = (out[-1][0], end)
        else:
            out.append((day, end))
    return out

class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('NEWS_ATLAS_DB', DEFAULT_DB))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            if db.execute('PRAGMA user_version').fetchone()[0]>4:raise ValueError('Newer database format; update application before opening')
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS articles (
                    provider TEXT NOT NULL, id TEXT NOT NULL, published_at TEXT, payload TEXT NOT NULL,
                    PRIMARY KEY(provider,id));
                CREATE TABLE IF NOT EXISTS memberships (
                    provider TEXT NOT NULL, query_key TEXT NOT NULL, article_id TEXT NOT NULL,
                    PRIMARY KEY(provider,query_key,article_id));
                CREATE TABLE IF NOT EXISTS membership_origins (
                    provider TEXT NOT NULL, query_key TEXT NOT NULL, article_id TEXT NOT NULL, source_json TEXT NOT NULL,
                    PRIMARY KEY(provider,query_key,article_id));
                CREATE TABLE IF NOT EXISTS coverage (
                    provider TEXT NOT NULL, query_key TEXT NOT NULL, day TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('complete','snapshot')), checked_at REAL NOT NULL,
                    PRIMARY KEY(provider,query_key,day));
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY, provider TEXT NOT NULL, query_key TEXT NOT NULL,
                    start TEXT NOT NULL, end TEXT NOT NULL, checked_at REAL NOT NULL,
                    error_code TEXT, retry_until REAL NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS memberships_article_idx ON memberships(provider,article_id);
                CREATE INDEX IF NOT EXISTS published_idx ON articles(provider,published_at);
                CREATE INDEX IF NOT EXISTS attempts_idx ON attempts(provider,retry_until);
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL,
                    search_json TEXT NOT NULL, view_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshot_articles (
                    snapshot_id TEXT NOT NULL, provider TEXT NOT NULL, article_id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(snapshot_id,provider,article_id));
                CREATE TABLE IF NOT EXISTS snapshot_relations (
                    snapshot_id TEXT NOT NULL, scope TEXT NOT NULL, edge_id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(snapshot_id,scope,edge_id));
                CREATE TABLE IF NOT EXISTS channels (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, payload TEXT NOT NULL);
                PRAGMA user_version=4;
            ''')

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def coverage(self, provider, query, start, end, now=None):
        now = time.time() if now is None else now
        today = dt.datetime.fromtimestamp(now, dt.timezone.utc).date().isoformat()
        with self.connection() as db:
            records = db.execute('SELECT day,kind,checked_at FROM coverage WHERE provider=? AND query_key=? AND day>=? AND day<?', (provider, query, start, end)).fetchall()
        fresh = []
        for r in records:
            # Latest day is refreshed often. RSS is always a short-lived snapshot.
            ttl = 300 if r['day'] >= today or r['kind'] == 'snapshot' else 86400
            if now - r['checked_at'] < ttl:
                fresh.append(dict(r))
        covered = {r['day'] for r in fresh}
        return fresh, contiguous(set(dates(start, end)) - covered)

    def read(self, provider, query, start, end):
        with self.connection() as db:
            rows = db.execute('''SELECT a.payload,o.source_json FROM articles a JOIN memberships m
                ON a.provider=m.provider AND a.id=m.article_id
                LEFT JOIN membership_origins o ON o.provider=m.provider AND o.query_key=m.query_key AND o.article_id=m.article_id
                WHERE m.provider=? AND m.query_key=? AND a.published_at>=? AND a.published_at<?
                ORDER BY a.published_at DESC''', (provider, query, start, end)).fetchall()
        result=[]
        for record in rows:
            row=json.loads(record['payload'])
            if record['source_json']:row['source']=json.loads(record['source_json'])
            result.append(row)
        return result

    def save(self, provider, query, rows, windows, now=None):
        now = time.time() if now is None else now
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            for raw in rows:
                row={**raw}
                old=db.execute('SELECT payload FROM articles WHERE provider=? AND id=?',(provider,row['id'])).fetchone()
                origins=list(row.get('origins',[row['source']]))
                if old:
                    previous=json.loads(old['payload'])
                    # Freeze legacy query context before another edition replaces shared payload.
                    db.execute('INSERT OR IGNORE INTO membership_origins SELECT provider,query_key,article_id,? FROM memberships WHERE provider=? AND article_id=?',
                               (json.dumps(previous['source'],ensure_ascii=False),provider,row['id']))
                    for origin in previous.get('origins',[previous['source']]):
                        if origin not in origins:origins.append(origin)
                row['origins']=origins
                db.execute('INSERT INTO membership_origins VALUES(?,?,?,?) ON CONFLICT(provider,query_key,article_id) DO UPDATE SET source_json=excluded.source_json',
                           (provider,query,row['id'],json.dumps(row['source'],ensure_ascii=False)))
                db.execute('INSERT INTO articles VALUES(?,?,?,?) ON CONFLICT(provider,id) DO UPDATE SET published_at=excluded.published_at,payload=excluded.payload',
                           (provider, row['id'], row['published_at'], json.dumps(row, ensure_ascii=False)))
                db.execute('INSERT OR IGNORE INTO memberships VALUES(?,?,?)', (provider, query, row['id']))
            for start, end, kind in windows:
                db.executemany('INSERT INTO coverage VALUES(?,?,?,?,?) ON CONFLICT(provider,query_key,day) DO UPDATE SET kind=excluded.kind,checked_at=excluded.checked_at',
                               [(provider, query, day, kind, now) for day in dates(start, end)])

    def record_attempt(self, provider, query, start, end, error_code=None, retry_after=0):
        with self.connection() as db:
            db.execute('INSERT INTO attempts(provider,query_key,start,end,checked_at,error_code,retry_until) VALUES(?,?,?,?,?,?,?)',
                       (provider, query, start, end, time.time(), error_code, time.time() + retry_after if retry_after else 0))

    def cooldown(self, provider):
        with self.connection() as db:
            row = db.execute("SELECT MAX(retry_until) AS until FROM attempts WHERE provider=? AND error_code='rate_limit'", (provider,)).fetchone()
        return max(0, int((row['until'] or 0) - time.time()))

    def stats(self):
        with self.connection() as db:
            return {name: db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in ('articles', 'coverage', 'attempts', 'snapshots')}

    def save_snapshot(self, payload):
        from .snapshots import validate_snapshot
        payload = validate_snapshot(payload)
        payload['view']['article_order'] = {s:[a['id'] for a in g['articles']] for s,g in payload['source_graphs'].items()}
        payload['view']['relation_order'] = {s:[r['id'] for r in g['relations']] for s,g in payload['source_graphs'].items()}
        ident = uuid.uuid4().hex
        created = dt.datetime.now(dt.timezone.utc).isoformat()
        with self.connection() as db:
            db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?)', (ident,payload['name'],created,json.dumps(payload['search'],ensure_ascii=False),json.dumps(payload['view'],ensure_ascii=False)))
            for provider, group in payload['source_graphs'].items():
                for article in group['articles']:
                    db.execute('INSERT INTO snapshot_articles VALUES(?,?,?,?)',(ident,provider,article['id'],json.dumps(article,ensure_ascii=False)))
                for edge in group['relations']:
                    db.execute('INSERT INTO snapshot_relations VALUES(?,?,?,?)',(ident,provider,edge['id'],json.dumps(edge,ensure_ascii=False)))
            for edge in payload['cross_relations']:
                db.execute('INSERT INTO snapshot_relations VALUES(?,?,?,?)',(ident,'cross',edge['id'],json.dumps(edge,ensure_ascii=False)))
        return {'id':ident,'name':payload['name'],'created_at':created}

    def list_snapshots(self):
        with self.connection() as db:
            rows=db.execute('SELECT id,name,created_at,view_json FROM snapshots ORDER BY created_at DESC LIMIT 50').fetchall()
        return [{'id':r['id'],'name':r['name'],'created_at':r['created_at'],'sources':json.loads(r['view_json'])['sources']} for r in rows]

    def load_snapshot(self, ident):
        with self.connection() as db:
            row=db.execute('SELECT * FROM snapshots WHERE id=?',(ident,)).fetchone()
            if row is None:
                return None
            articles=db.execute('SELECT provider,payload FROM snapshot_articles WHERE snapshot_id=?',(ident,)).fetchall()
            edges=db.execute('SELECT scope,payload FROM snapshot_relations WHERE snapshot_id=?',(ident,)).fetchall()
        view=json.loads(row['view_json'])
        groups={s:{'articles':[],'relations':[]} for s in view['sources']}
        cross=[]
        for r in articles:
            groups[r['provider']]['articles'].append(json.loads(r['payload']))
        for r in edges:
            (cross if r['scope']=='cross' else groups[r['scope']]['relations']).append(json.loads(r['payload']))
        for source,group in groups.items():
            for field,order_key in (('articles','article_order'),('relations','relation_order')):
                order={ident:i for i,ident in enumerate(view.get(order_key,{}).get(source,[]))}
                group[field].sort(key=lambda row:order.get(row['id'],len(order)))
            group['total_articles']=len(group['articles'])
        return {'id':ident,'name':row['name'],'created_at':row['created_at'],'search':json.loads(row['search_json']),
                'view':view,'source_graphs':groups,'cross_relations':cross}

    def list_channels(self):
        from .channels import definitions
        with self.connection() as db:
            rows=db.execute('SELECT payload FROM channels ORDER BY rowid').fetchall()
        return definitions(json.loads(r['payload']) for r in rows)

    def save_channel(self, body):
        from .channels import validate_custom, DEFAULT_CHANNELS, OTHER
        channel=validate_custom(body)
        ident=body.get('id')
        with self.connection() as db:
            if ident is not None and (not isinstance(ident,str) or not db.execute('SELECT 1 FROM channels WHERE id=?',(ident,)).fetchone()):
                raise ValueError('只能編輯已存在的自訂 channel')
            if channel['name'] in {c['name'] for c in [*DEFAULT_CHANNELS,OTHER]}:
                raise ValueError('名稱與預設 channel 重複')
            if ident is None and db.execute('SELECT COUNT(*) FROM channels').fetchone()[0] >= 25:
                raise ValueError('最多可建立 25 個自訂 channel')
            ident=ident or 'custom-'+uuid.uuid4().hex[:12]
            channel['id']=ident
            try:
                db.execute('INSERT INTO channels VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload',(ident,channel['name'],json.dumps(channel,ensure_ascii=False)))
            except sqlite3.IntegrityError:
                raise ValueError('自訂 channel 名稱已存在') from None
        return channel

    def delete_channel(self, ident):
        with self.connection() as db:
            return db.execute('DELETE FROM channels WHERE id=?',(ident,)).rowcount > 0
