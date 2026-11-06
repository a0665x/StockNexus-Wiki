#!/usr/bin/env python3
"""Transactional union of stock data; no network or model calls."""
import argparse
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from news_atlas.storage import Store
from news_atlas.wiki.store import WikiStore, digest, instrument, folder_name

NEWS = {'articles','memberships','membership_origins','coverage','attempts','snapshots','snapshot_articles','snapshot_relations','channels','daily_prices','price_downloads','graph_metadata'}
WIKI = {'metadata','articles','versions','nodes','edges','extractions','jobs','review_coverage','reviews','calls','rejected_proposals'}
AUX = {'merge_conflicts','merge_versions','merge_records'}

def encoded(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def ident(x):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', x):
        raise ValueError('Unsupported SQL identifier')
    return '"'+x+'"'

def connect(path, readonly=False):
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro' if readonly else str(path),uri=readonly,timeout=2)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA trusted_schema=OFF')
    return db

def tables(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
        raise ValueError('Database contains unsupported triggers/views')
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}

def schema(db,table):
    return [dict(r) for r in db.execute('PRAGMA table_info('+ident(table)+')')]

def aux(db):
    for sql in [
        'CREATE TABLE IF NOT EXISTS merge_conflicts (id TEXT PRIMARY KEY, table_name TEXT NOT NULL, local_json TEXT NOT NULL, incoming_json TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS merge_versions (origin TEXT PRIMARY KEY, local_version INTEGER NOT NULL)',
        'CREATE TABLE IF NOT EXISTS merge_records (origin TEXT PRIMARY KEY, table_name TEXT NOT NULL, local_id INTEGER NOT NULL)',
    ]: db.execute(sql)

def put(db,t,row):
    db.execute('INSERT INTO '+ident(t)+' ('+','.join(map(ident,row))+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))

def archive(db,t,old,new,stats):
    key=digest([t,old,new])
    n=db.execute('INSERT OR IGNORE INTO merge_conflicts VALUES (?,?,?,?)',(key,t,encoded(old),encoded(new))).rowcount
    stats['conflicts']+=n

def union_row(db,t,row,stats,ignore=()):
    cols=schema(db,t);keys=[c['name'] for c in sorted(cols,key=lambda c:c['pk']) if c['pk']]
    keys=keys or list(row)
    where=' AND '.join(ident(k)+' IS ?' for k in keys)
    old=db.execute('SELECT * FROM '+ident(t)+' WHERE '+where,tuple(row[k] for k in keys)).fetchone()
    if old is None:
        try: put(db,t,row);stats['inserted']+=1
        except sqlite3.IntegrityError:
            # For example channel names may be UNIQUE independently of their IDs.
            archive(db,t,{'reason':'secondary unique constraint'},row,stats)
        return
    old=dict(old)
    a={k:v for k,v in old.items() if k not in ignore};b={k:v for k,v in row.items() if k not in ignore}
    if a!=b: archive(db,t,old,row,stats)
    else:stats['duplicates']+=1

def auto_row(db,t,row,stats):
    content={k:v for k,v in row.items() if k!='id'}
    origin=digest([t,content])
    if db.execute('SELECT 1 FROM merge_records WHERE origin=?',(origin,)).fetchone():
        stats['duplicates']+=1;return
    where=' AND '.join(ident(k)+' IS ?' for k in content)
    old=db.execute('SELECT id FROM '+ident(t)+' WHERE '+where,tuple(content.values())).fetchone()
    if old:local=old[0];stats['duplicates']+=1
    else:
        put(db,t,content);local=db.execute('SELECT last_insert_rowid()').fetchone()[0];stats['inserted']+=1
    db.execute('INSERT INTO merge_records VALUES (?,?,?)',(origin,t,local))

def ensure_schema(src,dst,allowed):
    st=tables(src);unknown=st-allowed-AUX
    if unknown:raise ValueError('Unsupported tables: '+','.join(sorted(unknown)))
    for t in st-AUX:
        a=schema(src,t)
        if t not in tables(dst):
            # Build only plain table definitions from validated identifiers/types.
            fields=[]
            for c in a:
                typ=c['type'].upper()
                if typ not in ('TEXT','INTEGER','REAL','BLOB','NUMERIC',''):raise ValueError('Unsupported column type')
                fields.append(ident(c['name'])+' '+typ+(' NOT NULL' if c['notnull'] else ''))
            keys=[ident(c['name']) for c in sorted(a,key=lambda c:c['pk']) if c['pk']]
            if keys:fields.append('PRIMARY KEY ('+','.join(keys)+')')
            dst.execute('CREATE TABLE '+ident(t)+' ('+','.join(fields)+')')
        b=schema(dst,t)
        if [(c['name'],c['type'].upper(),c['pk']) for c in a]!=[(c['name'],c['type'].upper(),c['pk']) for c in b]:
            raise ValueError('Schema mismatch: '+t+'; use matching project versions')
    return st

def busy(db):
    if 'jobs' not in tables(db):return
    if db.execute("SELECT 1 FROM jobs WHERE status IN ('running','queued')").fetchone():
        raise ValueError('Target Wiki has running/queued work; stop the work before merging')
    row=db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
    cfg=json.loads(row[0]) if row else {}
    if cfg.get('enabled') or cfg.get('catch_up'):
        raise ValueError('Target Wiki background maintenance is enabled; stop it before merging')

def wiki_merge(src,dst,stats,stamp):
    st=ensure_schema(src,dst,WIKI)
    source_ident=json.loads(src.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()[0])
    target_ident=json.loads(dst.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()[0])
    if source_ident!=target_ident:raise ValueError('Instrument mismatch')
    for t in ('articles',):
        for r in src.execute('SELECT * FROM '+t):union_row(dst,t,dict(r),stats,ignore=('captured_at',))
    # Keep local settings. New stocks inherit a paused configuration; never import work to run.
    cfgrow=dst.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
    incoming=src.execute("SELECT value FROM metadata WHERE key='config'").fetchone()
    if incoming:
        cfg=json.loads(incoming[0]);cfg['enabled']=False;cfg['catch_up']=False
        if not cfgrow:dst.execute('INSERT INTO metadata VALUES (?,?)',('config',encoded(cfg)))
        elif json.loads(cfgrow[0])!=cfg:archive(dst,'metadata.config',json.loads(cfgrow[0]),cfg,stats)
    version_map={}
    for local in dst.execute('SELECT created_at,job_id,model,version FROM versions').fetchall():
        value=dict(local);number=value.pop('version')
        dst.execute('INSERT OR IGNORE INTO merge_versions VALUES (?,?)',(digest(value),number))
    for r in src.execute('SELECT * FROM versions ORDER BY version'):
        r=dict(r);old=r.pop('version');origin=digest(r)
        aliases=[origin]
        if 'merge_versions' in st:aliases += [v[0] for v in src.execute('SELECT origin FROM merge_versions WHERE local_version=?',(old,))]
        found=None
        for key in aliases:
            found=dst.execute('SELECT local_version FROM merge_versions WHERE origin=?',(key,)).fetchone()
            if found:break
        if not found:found=dst.execute('SELECT version FROM versions WHERE created_at=? AND job_id=? AND model=?',(r['created_at'],r['job_id'],r['model'])).fetchone()
        if found:new=found[0]
        else:
            # Imported knowledge becomes available now, without rewriting prior target history.
            r['created_at']=stamp;put(dst,'versions',r);new=dst.execute('SELECT last_insert_rowid()').fetchone()[0];stats['inserted']+=1
        version_map[old]=new
        for key in aliases:dst.execute('INSERT OR IGNORE INTO merge_versions VALUES (?,?)',(key,new))
    for t in ('nodes','edges','extractions'):
        for raw in src.execute('SELECT * FROM '+t):
            r=dict(raw);v='version' if t=='extractions' else 'created_version';r[v]=version_map[r[v]]
            if t=='nodes':
                p=json.loads(r['payload']);p['version']=r[v]
                old=dst.execute('SELECT payload FROM nodes WHERE id=?',(r['id'],)).fetchone()
                if old:
                    a=json.loads(old[0]);b=dict(p)
                    for obj in (a,b):
                        for k in ('available_at','version'):obj.pop(k,None)
                    if a!=b:archive(dst,t,json.loads(old[0]),p,stats)
                    else:stats['duplicates']+=1
                    continue
                p['available_at']=stamp;r['payload']=encoded(p)
            elif t=='edges':
                old=dst.execute('SELECT payload FROM edges WHERE id=?',(r['id'],)).fetchone()
                if old:
                    a=json.loads(old[0]);b=json.loads(r['payload'])
                    for obj in (a,b):
                        for k in ('available_at','produced_at','decision_as_of','run_id','provenance'):obj.pop(k,None)
                    if a!=b:archive(dst,t,json.loads(old[0]),json.loads(r['payload']),stats)
                    else:stats['duplicates']+=1
                    continue
                p=json.loads(r['payload']);p['available_at']=stamp;p['decision_as_of']=stamp;r['payload']=encoded(p)
            union_row(dst,t,r,stats,ignore=(v,))
    for t in ('jobs','calls','reviews','rejected_proposals'):
        if t not in st:continue
        for raw in src.execute('SELECT * FROM '+t):
            r=dict(raw)
            if t=='jobs' and r['status'] in ('queued','running'):
                r['status']='interrupted';r['error']='Imported snapshot; explicitly resume to continue'
            if t=='rejected_proposals':auto_row(dst,t,r,stats)
            else:union_row(dst,t,r,stats)
    # An evidence-count epoch is machine-local; never mark imported evidence as already reviewed.
    if 'review_coverage' in st:
        for r in src.execute('SELECT * FROM review_coverage'):
            union_row(dst,'review_coverage',{'revision':r['revision'],'evidence_epoch':0},stats)
    if dst.execute('SELECT 1 FROM edges e LEFT JOIN nodes a ON a.id=e.source LEFT JOIN nodes b ON b.id=e.target WHERE a.id IS NULL OR b.id IS NULL').fetchone():raise ValueError('Wiki has dangling edges')
    if dst.execute('SELECT 1 FROM extractions e LEFT JOIN articles a ON a.id=e.revision WHERE a.id IS NULL').fetchone():raise ValueError('Wiki has missing article revisions')
    for r in dst.execute('SELECT payload FROM nodes'):
        for cite in json.loads(r[0]).get('citations',[]):
            if not dst.execute('SELECT 1 FROM articles WHERE id=?',(cite['article_revision_id'],)).fetchone():raise ValueError('Missing citation revision')

def merge(src,dst,kind,stamp):
    ceiling={'news':4,'wiki':1,'prices':0}[kind]
    if src.execute('PRAGMA user_version').fetchone()[0]>ceiling or dst.execute('PRAGMA user_version').fetchone()[0]>ceiling:
        raise ValueError('Newer database format; update this tool first')
    aux(dst);stats={'inserted':0,'duplicates':0,'conflicts':0}
    if kind=='wiki':wiki_merge(src,dst,stats,stamp)
    else:
        st=ensure_schema(src,dst,NEWS if kind=='news' else {'series'})
        snapshot_map={}
        if kind=='news' and 'snapshots' in st:
            for raw in src.execute('SELECT * FROM snapshots'):
                r=dict(raw);old=dst.execute('SELECT * FROM snapshots WHERE id=?',(r['id'],)).fetchone()
                same=dst.execute('SELECT id FROM snapshots WHERE name=? AND created_at=? AND search_json=? AND view_json=? ORDER BY id LIMIT 1',tuple(r[k] for k in ('name','created_at','search_json','view_json'))).fetchone()
                if same:snapshot_map[r['id']]=same[0]
                elif old and dict(old)!=r:
                    snapshot_map[r['id']]='import-'+digest(r)
        for t in sorted(st-AUX):
            for raw in src.execute('SELECT * FROM '+ident(t)):
                row=dict(raw)
                if t=='snapshots':row['id']=snapshot_map.get(row['id'],row['id'])
                if t in ('snapshot_articles','snapshot_relations'):
                    row['snapshot_id']=snapshot_map.get(row['snapshot_id'],row['snapshot_id'])
                pk=[c for c in schema(src,t) if c['pk']]
                if len(pk)==1 and pk[0]['name']=='id' and pk[0]['type'].upper()=='INTEGER':auto_row(dst,t,row,stats)
                else:union_row(dst,t,row,stats)
    if 'merge_conflicts' in tables(src):
        for r in src.execute('SELECT * FROM merge_conflicts'):union_row(dst,'merge_conflicts',dict(r),stats)
    if dst.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure')
    return stats

def inventory(root):
    result=[]
    news_paths=[]
    if (root/'news-atlas.sqlite3').is_file():news_paths.append(root/'news-atlas.sqlite3')
    news_paths.extend(root.glob('*/news-atlas.sqlite3'))
    news_paths.extend((root/'graph').glob('*/news-atlas.sqlite3'))
    for path in sorted(set(news_paths)):
        with contextlib.closing(connect(path,True)) as db:
            ts=tables(db)
            meta=db.execute("SELECT value FROM graph_metadata WHERE key='ticker'").fetchone() if 'graph_metadata' in ts else None
        symbol=meta[0] if meta else path.parent.name if path.parent.parent.name=='graph' else '_unassigned'
        from news_atlas.graph_storage import ticker_name
        if symbol!='_unassigned':symbol=ticker_name(symbol)
        if meta and path.parent.name!=symbol:raise ValueError('Graph folder does not match ticker metadata')
        for suffix,kind in [('', 'news'),('.prices.sqlite3','prices')]:
            p=Path(str(path)+suffix)
            if p.is_file():result.append((p.relative_to(root),kind,Path('graph')/symbol/p.name))
    paths=[]
    if (root/'wiki.sqlite3').is_file():paths.append(root/'wiki.sqlite3')
    else:
        paths.extend(root.glob('*/wiki.sqlite3'))
        paths.extend((root/'llm_wiki').glob('*/wiki.sqlite3'))
        paths.extend((root/'research').glob('*/wiki.sqlite3'))
    seen=set()
    for p in sorted(set(paths)):
        with contextlib.closing(connect(p,True)) as db:
            tables(db)
            row=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
            name=instrument(json.loads(row[0]))
            if p.parent.name not in (folder_name(name),digest(name)[:24]):raise ValueError('Wiki folder does not match its instrument: '+str(p))
        canonical=Path('llm_wiki')/folder_name(name)/'wiki.sqlite3'
        if canonical in seen:raise ValueError('Source contains multiple Wikis for the same ticker; merge them separately')
        seen.add(canonical)
        result.append((p.relative_to(root),'wiki',canonical))
    for rel,_,_ in result:
        if (root/rel).resolve()!=root/rel:raise ValueError('Symlink database paths are not supported')
    if not result:raise ValueError('No supported databases found; select data, llm_wiki, or a stock folder')
    return result


def destination_entries(entries,target):
    categories={r[2].parts[0] for r in entries}
    category=target.name if target.name in ('graph','llm_wiki') else None
    if category is None and not (target/'news-atlas.sqlite3').exists() and not (target/'wiki.sqlite3').exists():
        has_wiki=any(target.glob('*/wiki.sqlite3'));has_graph=any(target.glob('*/news-atlas.sqlite3'))
        if has_wiki and has_graph:raise ValueError('Ambiguous target layout; select an explicit graph or llm_wiki root')
        if has_wiki:category='llm_wiki'
        if has_graph:category='graph'
    stock_category=None
    if (target/'wiki.sqlite3').exists():stock_category='llm_wiki'
    elif (target/'news-atlas.sqlite3').exists() and target.parent.name=='graph':stock_category='graph'
    elif len(categories)==1 and all(target.name==r[2].parent.name for r in entries):stock_category=next(iter(categories))
    elif (target/'news-atlas.sqlite3').exists():
        with contextlib.closing(connect(target/'news-atlas.sqlite3',True)) as db:
            if 'graph_metadata' in tables(db):stock_category='graph'
            else:raise ValueError('Target uses legacy root news DB; restart updated app to migrate before merging')
    if category and categories!={category}:raise ValueError('Source and target categories differ; use a data target')
    if stock_category and (categories!={stock_category} or len({r[2].parent.name for r in entries})!=1):
        raise ValueError('Multiple stocks or categories cannot be merged into one stock folder')
    out=[]
    for source_rel,kind,canonical in entries:
        if stock_category:
            if target.name!=canonical.parent.name:raise ValueError('Target stock folder must match source ticker')
            rel=Path(canonical.name)
        elif category:rel=Path(*canonical.parts[1:])
        else:rel=canonical
        if kind=='wiki' and not stock_category and not category:
            for legacy in (target/'research').glob('*/wiki.sqlite3'):
                with contextlib.closing(connect(legacy,True)) as db:
                    row=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
                if row and folder_name(json.loads(row[0]))==canonical.parent.name:
                    raise ValueError('Target uses legacy research path; restart updated app to migrate before merging')
        out.append((source_rel,kind,rel))
    if len({r[2] for r in out})!=len(out):raise ValueError('Multiple source databases map to the same target; merge separately')
    return out

def run(source,target,dry_run=False):
    source=Path(source).expanduser().resolve();target=Path(target).expanduser().resolve()
    if not source.is_dir():raise ValueError('--from must be a data directory')
    if source==target or source in target.parents or target in source.parents:raise ValueError('Source and target must be separate, non-nested directories')
    entries=destination_entries(inventory(source),target);stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    report={'dry_run':dry_run,'source':str(source),'target':str(target),'databases':{},'committed':[],
            'excluded':['private/','graph/pair caches','unknown files'],'policy':'local wins; conflicting incoming values retained in merge_conflicts'}
    with tempfile.TemporaryDirectory(prefix='stocknexus-merge-') as tmp, contextlib.ExitStack() as stack:
        tmp=Path(tmp);prepared=[]
        for i,(source_rel,kind,rel) in enumerate(entries):
            dstpath=target/rel
            if dstpath.resolve()!=dstpath:raise ValueError('Symlink targets are not supported')
            snap=tmp/f'source-{i}.sqlite3';stage=tmp/f'stage-{i}.sqlite3';base=tmp/f'base-{i}.sqlite3'
            s=stack.enter_context(contextlib.closing(connect(snap)))
            with contextlib.closing(connect(source/source_rel,True)) as original:original.backup(s)
            tables(s)
            if s.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Invalid source database')
            d=None
            if dstpath.exists():
                d=stack.enter_context(contextlib.closing(connect(dstpath)))
                d.execute('BEGIN IMMEDIATE') # Hold out writers until all databases are validated.
                if kind=='wiki':busy(d)
                with contextlib.closing(connect(dstpath,True)) as original,contextlib.closing(connect(base)) as b:original.backup(b)
                with contextlib.closing(connect(base,True)) as b,contextlib.closing(connect(stage)) as out:b.backup(out)
            else:
                if kind=='news':Store(stage)
                elif kind=='wiki':
                    name=json.loads(s.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()[0])
                    fresh=WikiStore(tmp/f'init-{i}',name)
                    with contextlib.closing(connect(fresh.path,True)) as b,contextlib.closing(connect(stage)) as out:b.backup(out)
            with contextlib.closing(connect(stage)) as out:
                stats=merge(s,out,kind,stamp);out.commit()
            report['databases'][str(rel)]=stats
            prepared.append((rel,kind,s,d,stage,base,snap))
        if dry_run:return report
        target.mkdir(parents=True,exist_ok=True)
        backup=target/'.merge-backups'/(dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);backup.mkdir(parents=True,mode=0o700)
        report['backup']=str(backup)
        # Save complete consistent source and target snapshots before changing any target.
        for rel,kind,s,d,stage,base,snap in prepared:
            for label,path in [('source',snap),('before',base)]:
                if not path.exists():continue
                dest=backup/label/rel;dest.parent.mkdir(parents=True,exist_ok=True)
                with contextlib.closing(connect(path,True)) as original,contextlib.closing(connect(dest)) as out:original.backup(out)
        def save_report():
            (backup/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        save_report()
        for rel,kind,s,d,stage,base,snap in prepared:
            report['pending_database']=str(rel);save_report()
            dstpath=target/rel
            if d is not None:
                merge(s,d,kind,stamp);d.commit()
            else:
                dstpath.parent.mkdir(parents=True,exist_ok=True)
                # Exclusive creation prevents overwriting a database created after preflight.
                with tempfile.TemporaryDirectory(prefix='.merge-publish-',dir=dstpath.parent) as publish:
                    ready=Path(publish)/'ready.sqlite3'
                    with contextlib.closing(connect(stage,True)) as original,contextlib.closing(connect(ready)) as out:original.backup(out)
                    os.chmod(ready,0o600)
                    os.link(ready,dstpath)
            report['committed'].append(str(rel));report['pending_database']=None;save_report()
        report['ui_refresh']='Saved Wikis refreshes automatically within 6 seconds. Select an imported stock; current selections are preserved.'
        save_report()
        return report

def main():
    parser=argparse.ArgumentParser(description='Union stock data. The web UI may stay open; pause target Wiki jobs/watchers first; local conflicting values are retained, incoming conflicts archived. Never copies private credentials or calls LLMs.')
    parser.add_argument('--from',dest='source',required=True,help='Source data, graph, llm_wiki, or stock directory')
    parser.add_argument('--to',dest='target',required=True,help='Target data, graph, llm_wiki, or stock directory')
    parser.add_argument('--dry-run',action='store_true',help='Validate and report without changing target contents')
    args=parser.parse_args()
    try:print(json.dumps(run(args.source,args.target,args.dry_run),ensure_ascii=False,indent=2))
    except (ValueError,sqlite3.Error,OSError,KeyError,TypeError) as e:
        print('Merge stopped: '+str(e)+'\nExisting committed databases, if any, are listed in .merge-backups/*/report.json. No automatic background work was started.',file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
