"""Explicit-ticker graph storage and lossless legacy migration.

The repository's path is a credential/socket anchor, not a live news database.
Request-scoped Store instances own actual graph files; never mutate global routing.
"""
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import threading
from .storage import Store, DEFAULT_DB
from .model import TICKER


def ticker_name(value):
    if not isinstance(value,str):raise ValueError('股票代碼必須是文字')
    value=value.strip().upper()
    if not value:return '_unassigned'
    if not TICKER.fullmatch(value):raise ValueError('無效股票代碼')
    return value


def select(store,ticker=''):
    return store.for_ticker(ticker) if isinstance(store,GraphRepository) else store


def mark_stock(store,symbol):
    with store.connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS graph_metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        old=db.execute("SELECT value FROM graph_metadata WHERE key='ticker'").fetchone()
        if old and old[0]!=symbol:raise ValueError('Graph stock folder does not match database ticker')
        db.execute("INSERT OR IGNORE INTO graph_metadata VALUES ('ticker',?)",(symbol,))


def _copy_rows(src,dst,table,where='',args=()):
    for row in src.execute('SELECT * FROM '+table+(' WHERE '+where if where else ''),args):
        columns=row.keys();keys=[r[1] for r in src.execute('PRAGMA table_info('+table+')') if r[5]]
        old=dst.execute('SELECT * FROM '+table+' WHERE '+' AND '.join(k+' IS ?' for k in keys),tuple(row[k] for k in keys)).fetchone()
        if old:
            if dict(old)!=dict(row):raise ValueError('Migration conflict in '+table+'; original data retained')
        else:dst.execute('INSERT INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',tuple(row))


def migrate_graph(root,legacy_name='news-atlas.sqlite3'):
    """Offline startup migration. Unattributable data remains in _unassigned."""
    root=Path(root);legacy=root/legacy_name;folder=root/'graph'/'_unassigned';base=folder/'news-atlas.sqlite3'
    marker=root/'graph'/'.layout-v1.json'
    if marker.exists() and legacy.exists():raise ValueError('Legacy and partitioned graph DB both exist; import legacy with merge_data.sh instead of overwriting')
    if marker.exists():return
    if legacy.exists():
        if base.exists():raise ValueError('Both legacy and unassigned databases exist; resolve before migration')
        # Keep a complete consistent backup before moving any data or sidecars.
        backup=root/'private'/('graph-layout-backup-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
        backup.mkdir(parents=True,exist_ok=False,mode=0o700)
        with sqlite3.connect(legacy.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(backup/legacy_name) as out:src.backup(out)
        folder.mkdir(parents=True,exist_ok=True)
        for suffix in ('','-wal','-shm','.prices.sqlite3','.prices.sqlite3-wal','.prices.sqlite3-shm','.graphs.sqlite3','.graphs.sqlite3-wal','.graphs.sqlite3-shm','.pairs.sqlite3','.pairs.sqlite3-wal','.pairs.sqlite3-shm'):
            old=Path(str(legacy)+suffix)
            if old.exists():old.rename(Path(str(base)+suffix))
    catalog=Store(base);mark_stock(catalog,'_unassigned')
    from .search import query_key
    assignments={};snapshots={}
    def assign(ticker,provider,key):
        ticker=ticker_name(ticker)
        if ticker!='_unassigned':assignments.setdefault(ticker,set()).add((provider,key))
    with catalog.connection() as src:
        for r in src.execute("SELECT DISTINCT query_key FROM memberships WHERE provider='massive'"):
            if r[0].startswith('massive-v2:'):assign(r[0].split(':',1)[1],'massive',r[0])
        for r in src.execute('SELECT id,search_json FROM snapshots'):
            search=json.loads(r['search_json']);symbol=ticker_name(search.get('ticker',''))
            if symbol=='_unassigned':continue
            snapshots.setdefault(symbol,[]).append(r['id']);assignments.setdefault(symbol,set())
            for provider in ('google','yahoo','massive'):
                term=search.get('ticker' if provider=='massive' else 'query','')
                if term:assign(symbol,provider,query_key(provider,term,search.get('rss_region')))
        for p in sorted((root/'llm_wiki').glob('*/wiki.sqlite3')):
            with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:
                ident=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
                cfg=db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
            if ident and cfg:
                symbol=json.loads(ident[0]).split(':',1)[1]
                for sub in json.loads(cfg[0]).get('subscriptions',[]):assign(symbol,sub['provider'],sub['query_key'])
        # Commit complete stock copies before deleting any catalog rows. A retry is idempotent.
        for symbol,queries in sorted(assignments.items()):
            stock=Store(root/'graph'/symbol/'news-atlas.sqlite3');mark_stock(stock,symbol)
            with stock.connection() as dst:
                _copy_rows(src,dst,'channels')
                for provider,key in sorted(queries):
                    for table in ('memberships','membership_origins','coverage','attempts'):
                        _copy_rows(src,dst,table,'provider=? AND query_key=?',(provider,key))
                    _copy_rows(src,dst,'articles','provider=? AND id IN (SELECT article_id FROM memberships WHERE provider=? AND query_key=?)',(provider,provider,key))
                for sid in snapshots.get(symbol,[]):
                    _copy_rows(src,dst,'snapshots','id=?',(sid,))
                    for table in ('snapshot_articles','snapshot_relations'):_copy_rows(src,dst,table,'snapshot_id=?',(sid,))
        moved=set().union(*assignments.values()) if assignments else set()
        src.execute('BEGIN IMMEDIATE')
        # Only delete articles fully accounted for in a copied membership. Keep orphan articles.
        copied_articles=set()
        for provider,key in moved:
            copied_articles.update((provider,r[0]) for r in src.execute('SELECT article_id FROM memberships WHERE provider=? AND query_key=?',(provider,key)))
            for table in ('memberships','membership_origins','coverage','attempts'):src.execute('DELETE FROM '+table+' WHERE provider=? AND query_key=?',(provider,key))
        for provider,aid in copied_articles:
            src.execute('DELETE FROM articles WHERE provider=? AND id=? AND NOT EXISTS (SELECT 1 FROM memberships WHERE provider=? AND article_id=?)',(provider,aid,provider,aid))
        for sids in snapshots.values():
            for sid in sids:
                for table in ('snapshot_articles','snapshot_relations'):src.execute('DELETE FROM '+table+' WHERE snapshot_id=?',(sid,))
                src.execute('DELETE FROM snapshots WHERE id=?',(sid,))
    # Price cache keys do not expose ticker. Payload does, so split only attributable entries.
    prices=Path(str(base)+'.prices.sqlite3')
    if prices.exists():
        with sqlite3.connect(prices) as src:
            if src.execute("SELECT 1 FROM sqlite_master WHERE name='series'").fetchone():
                for key,payload,fetched in src.execute('SELECT key,payload,fetched FROM series').fetchall():
                    value=json.loads(payload);symbol=value.get('ticker')
                    if not symbol:continue
                    dest=root/'graph'/ticker_name(symbol)/'news-atlas.sqlite3.prices.sqlite3';dest.parent.mkdir(parents=True,exist_ok=True)
                    with sqlite3.connect(dest) as out:
                        out.execute('CREATE TABLE IF NOT EXISTS series (key TEXT PRIMARY KEY,payload TEXT NOT NULL,fetched REAL NOT NULL)')
                        old=out.execute('SELECT payload,fetched FROM series WHERE key=?',(key,)).fetchone()
                        if old and old!=(payload,fetched):raise ValueError('Price migration conflict; original retained')
                        out.execute('INSERT OR IGNORE INTO series VALUES (?,?,?)',(key,payload,fetched))
                    src.execute('DELETE FROM series WHERE key=?',(key,))
    marker.write_text(json.dumps({'version':1,'stocks':sorted(assignments),'unassigned':'Unattributed source queries retained; no title-based guesses'},indent=2)+'\n')


class GraphRepository:
    def __init__(self,path=None):
        self.path=Path(path or os.environ.get('NEWS_ATLAS_DB',DEFAULT_DB)).resolve()
        self.data_root=self.path.parent
        from .wiki.store import migrate_legacy
        migrate_legacy(self.data_root)
        migrate_graph(self.data_root,self.path.name)
        self.catalog=Store(self.data_root/'graph'/'_unassigned'/'news-atlas.sqlite3')
        self._lock=threading.RLock()

    def for_ticker(self,ticker=''):
        symbol=ticker_name(ticker)
        with self._lock:
            store=Store(self.data_root/'graph'/symbol/'news-atlas.sqlite3')
            mark_stock(store,symbol)
            store.data_root=self.data_root
            # Global user categories are available to new stock scopes, while stock imports retain theirs.
            with self.catalog.connection() as src,store.connection() as dst:
                for row in src.execute('SELECT * FROM channels'):
                    dst.execute('INSERT OR IGNORE INTO channels VALUES (?,?,?)',tuple(row))
            return store

    def for_query(self,request):
        store=self.for_ticker(request.get('ticker',''))
        if store.path==self.catalog.path:return store
        if request.get('instrument'):
            from .wiki.store import instrument
            ident=instrument(request['instrument'])
            if ident.split(':')[1]!=request.get('ticker'):raise ValueError('股票識別不一致')
            with store.connection() as db:
                db.execute("INSERT OR REPLACE INTO graph_metadata VALUES ('instrument',?)",(ident,))
        from .search import query_key
        # A newly explicit ticker can reuse matching previously-unassigned searches.
        # The user's current query authorizes this association; never infer it from a title.
        with self.catalog.connection() as src,store.connection() as dst:
            for provider in request.get('sources',[]):
                term=request.get('ticker' if provider=='massive' else 'query','')
                if not term:continue
                key=query_key(provider,term,request.get('rss_region'))
                for table in ('memberships','membership_origins','coverage'):
                    for row in src.execute('SELECT * FROM '+table+' WHERE provider=? AND query_key=?',(provider,key)):
                        dst.execute('INSERT OR IGNORE INTO '+table+' VALUES ('+','.join('?' for _ in row)+')',tuple(row))
                for row in src.execute('SELECT * FROM articles WHERE provider=? AND id IN (SELECT article_id FROM memberships WHERE provider=? AND query_key=?)',(provider,provider,key)):
                    dst.execute('INSERT OR IGNORE INTO articles VALUES (?,?,?,?)',tuple(row))
        return store

    def stores(self):
        return [Store(p) for p in sorted((self.data_root/'graph').glob('*/news-atlas.sqlite3'))]

    def connection(self):return self.catalog.connection()
    def list_channels(self):return self.catalog.list_channels()
    def save_channel(self,body):
        result=self.catalog.save_channel(body)
        for store in self.stores():
            if store.path==self.catalog.path:continue
            with store.connection() as db:
                db.execute('INSERT INTO channels VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload',(result['id'],result['name'],json.dumps(result)))
        return result
    def delete_channel(self,ident):
        found=False
        for store in self.stores():found=store.delete_channel(ident) or found
        return found
    def stats(self):
        counts={k:0 for k in ('articles','coverage','attempts','snapshots')};seen=set()
        for store in self.stores():
            values=store.stats()
            for k in counts:
                if k!='articles':counts[k]+=values[k]
            with store.connection() as db:seen.update(tuple(r) for r in db.execute('SELECT provider,id FROM articles'))
        counts['articles']=len(seen);return counts
    def list_snapshots(self):
        rows={}
        for store in self.stores():
            for row in store.list_snapshots():rows.setdefault(row['id'],row)
        return sorted(rows.values(),key=lambda r:r['created_at'],reverse=True)[:50]
    def load_snapshot(self,ident):
        for store in self.stores():
            saved=store.load_snapshot(ident)
            if saved:return saved
    def save_snapshot(self,body):
        return self.for_ticker(body.get('search',{}).get('ticker','')).save_snapshot(body)
    def article_rows(self,ident):
        rows={}
        for store in self.stores():
            with store.connection() as db:
                for r in db.execute('SELECT provider,payload FROM articles WHERE id=?',(ident,)):rows.setdefault(r['provider'],{'payload':r['payload']})
        return list(rows.values())
