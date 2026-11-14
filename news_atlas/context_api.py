"""Bounded, cache-only research reads, independent of browser rendering budgets."""
import contextlib
import datetime as dt
import json
import sqlite3
import urllib.parse
from pathlib import Path
from .wiki.store import instrument

RESOURCES = ('catalog', 'news', 'related', 'prices', 'l1', 'l2')

@contextlib.contextmanager
def connect(path):
    if not path.is_file():
        raise FileNotFoundError('Database not found')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        yield db
    finally:
        db.close()

def catalog(root):
    result = []
    for path in sorted((root/'graph').glob('*/news-atlas.sqlite3')):
        if path.parent.name == '_unassigned': continue
        with connect(path) as db:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            row = db.execute("SELECT value FROM graph_metadata WHERE key='instrument'").fetchone() if 'graph_metadata' in tables else None
            ident = row[0] if row else None
            count = db.execute('SELECT count(*) FROM articles').fetchone()[0]
        wiki = root/'llm_wiki'/path.parent.name/'wiki.sqlite3'
        if wiki.exists():
            with connect(wiki) as db:
                row = db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
                saved = json.loads(row[0]) if row else None
                if ident and saved and saved != ident: continue
                ident = ident or saved
        try: instrument(ident)
        except ValueError: continue
        if ident.split(':')[1] != path.parent.name: continue
        result.append({'instrument':ident, 'articles':count, 'wiki_available':wiki.exists()})
    return {'instruments':result, 'network_requests':0}

def integer(params, key, default, minimum, maximum):
    raw=params.get(key,default)
    if isinstance(raw,bool): raise ValueError('Invalid '+key)
    try: value=int(raw)
    except (ValueError,TypeError): raise ValueError('Invalid '+key) from None
    if str(value)!=str(raw) or not minimum<=value<=maximum: raise ValueError('Invalid '+key)
    return value

def window(params, now):
    cutoff=now.astimezone(dt.timezone.utc)
    if 'end' in params:
        cutoff=dt.datetime.fromisoformat(params['end'].replace('Z','+00:00'))
        if cutoff.tzinfo is None: raise ValueError('end requires timezone')
        cutoff=cutoff.astimezone(dt.timezone.utc)
    if cutoff>now: raise ValueError('Future end is not supported')
    days=integer(params,'days',7,1,3660)
    start=cutoff-dt.timedelta(days=days)
    return start.isoformat(),cutoff.isoformat()

def query(root, resource, params, now=None):
    root=Path(root)
    allowed={'instrument','days','end'}
    if resource=='catalog': allowed=set()
    if resource in ('news','related','l2'): allowed|={'query','limit','offset'}
    if resource=='l1': allowed.add('query')
    if resource in ('related','l2'): allowed.add('id')
    if set(params)-allowed: raise ValueError('Unknown parameters: '+','.join(sorted(set(params)-allowed)))
    if resource not in RESOURCES: raise FileNotFoundError('Unknown context resource')
    cat=catalog(root)
    if resource=='catalog': return cat
    ident=instrument(params.get('instrument',''))
    if ident not in {r['instrument'] for r in cat['instruments']}: raise FileNotFoundError('Unknown instrument; read catalog first')
    ticker=ident.split(':')[1]
    start,end=window(params,now or dt.datetime.now(dt.timezone.utc))
    limit=integer(params,'limit',20,1,100);offset=integer(params,'offset',0,0,100000)
    text=params.get('query','')
    if not isinstance(text,str) or len(text)>2000: raise ValueError('Invalid query')
    meta={'instrument':ident,'window':{'start':start,'end_exclusive':end,'basis':'published_at'},'network_requests':0,'model_calls':0}
    def page(rows):
        return {**meta,'items':rows[offset:offset+limit],'total':len(rows),'next_offset':offset+limit if offset+limit<len(rows) else None}
    news=root/'graph'/ticker/'news-atlas.sqlite3'
    if resource in ('news','related'):
        with connect(news) as db:
            rows=[json.loads(r[0]) for r in db.execute("SELECT payload FROM articles WHERE julianday(published_at)>=julianday(?) AND julianday(published_at)<julianday(?) ORDER BY published_at DESC,id,provider",(start,end))]
            seed=None
            if resource=='related':
                seed=db.execute('SELECT payload FROM articles WHERE id=? ORDER BY provider LIMIT 1',(params.get('id',''),)).fetchone()
                if not seed: raise FileNotFoundError('News ID not found in this stock')
                seed=json.loads(seed[0])
        # Deduplicate identical IDs across providers; retain origin attribution.
        from .model import deduplicate
        rows=deduplicate(rows)
        if text: rows=[r for r in rows if text.casefold() in (r.get('title','')+' '+(r.get('summary') or '')).casefold()]
        if seed:
            symbols=set(seed.get('symbols',[]))
            entities={e['id'] for e in seed.get('entities',[])}
            topics={t['id'] for t in seed.get('topics',[])}
            related=[]
            for row in rows:
                common_s=sorted(symbols & set(row.get('symbols',[])))
                common_e=sorted(entities & {e['id'] for e in row.get('entities',[])})
                common_t=sorted(topics & {t['id'] for t in row.get('topics',[])})
                if row['id']!=seed['id'] and (common_s or common_e or common_t):
                    related.append({**row,'relation_evidence':{'shared_symbols':common_s,'shared_entities':common_e,'shared_topics':common_t}})
            rows=related
            meta.update(seed_id=seed['id'],relation_method='shared_symbol_entity_or_topic_v1',relation_scope='date-window candidates; not saved graph edges')
        return {**page(rows),'knowledge_mode':'current_cache','content_completeness':'title_and_source_summary','coverage':'stored articles only; not exhaustive provider coverage'}
    if resource=='prices':
        path=Path(str(news)+'.prices.sqlite3');bars={};receipts=[]
        if path.exists():
            with connect(path) as db:
                for row in db.execute('SELECT payload,fetched FROM series ORDER BY fetched'):
                    payload=json.loads(row[0])
                    if payload.get('ticker')!=ticker: continue
                    selected=[b for b in payload.get('bars',[]) if start[:10]<=b['date']<end[:10]]
                    for bar in selected: bars[bar['date']]={**bar,'fetched_at':payload.get('fetched_at')}
                    if selected:receipts.append(payload.get('fetched_at'))
        values=[bars[d] for d in sorted(bars)]
        change=(values[-1]['close']/values[0]['close']-1)*100 if len(values)>1 else None
        return {**meta,'bars':values,'status':'cached' if values else 'unavailable','provider':'massive','adjusted':True,'includes_dividends':False,'knowledge_mode':'latest_cached_vintage_not_historical_as_known','change_percent':change,'metric':'last_close / first_close - 1, percent','actual_start':values[0]['date'] if values else None,'actual_end':values[-1]['date'] if values else None,'coverage':'available cached trading sessions only','institutional_flows':'unavailable'}
    wiki=root/'llm_wiki'/ticker/'wiki.sqlite3'
    if not wiki.exists(): return {**page([]),'status':'unavailable','reason':'No L1 Wiki created'}
    from .wiki.research import taxonomy,parse_lens,bundle,obj,OWNER
    with connect(wiki) as db:
        if json.loads(db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()[0])!=ident: raise ValueError('Wiki instrument mismatch')
        if resource=='l1':
            if not db.execute("SELECT 1 FROM research_objects WHERE kind='taxonomy' AND owner=''").fetchone():
                return {**page([]),'status':'unavailable','reason':'Taxonomy not initialized'}
            tax=taxonomy(db)
            lens=parse_lens({'query':text or 'overview','lookback_days':integer(params,'days',7,1,3660),'as_of':end},ident,tax)
            result=bundle(db,lens)
            return {**meta,**result,'knowledge_mode':'as_known','retrieval_limit':24}
        if params.get('id'):
            run=obj(db,params['id'],'run');snapshot=obj(db,run['snapshot'],'snapshot')
            if snapshot['lens']['instrument']!=ident: raise ValueError('Research instrument mismatch')
            return {**meta,'run_id':params['id'],**run,'bundle':snapshot,'knowledge_mode':'saved_snapshot','window_applied':False}
        rows=[]
        for row in db.execute("SELECT id,created_at,payload FROM research_objects WHERE kind='run' AND owner=? AND julianday(created_at)>=julianday(?) AND julianday(created_at)<julianday(?) ORDER BY created_at DESC,id",(OWNER,start,end)):
            run=json.loads(row['payload']);snapshot=obj(db,run['snapshot'],'snapshot');lens=snapshot['lens']
            if lens['instrument']!=ident: continue
            if text and text.casefold() not in lens['query'].casefold(): continue
            rows.append({'id':row['id'],'created_at':row['created_at'],'lens':lens,'claim_count':len(run['result']['claims'])})
        meta['window']['basis']='run_created_at'
        return page(rows)

def handle(handler):
    from .wiki.http import writable
    if not writable(handler):
        handler.json_response(403,{'error':'Context reads require an allowed same-origin host'});return
    url=urllib.parse.urlsplit(handler.path)
    try:
        pairs=urllib.parse.parse_qs(url.query,keep_blank_values=True)
        if any(len(v)!=1 for v in pairs.values()): raise ValueError('Duplicate parameters')
        root=getattr(handler.store,'data_root',handler.store.path.parent)
        handler.json_response(200,query(root,url.path.removeprefix('/api/context/'),{k:v[0] for k,v in pairs.items()}))
    except FileNotFoundError as error: handler.json_response(404,{'error':str(error)})
    except (ValueError,TypeError,KeyError) as error: handler.json_response(400,{'error':str(error)})
    except sqlite3.Error:
        handler.json_response(503,{'error':'Data temporarily unavailable; retry this read'})
