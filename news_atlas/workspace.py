"""Same-origin UI workspace, independent from inference and acquisition state."""
import json,sqlite3,datetime as dt
from pathlib import Path
from .snapshots import validate_snapshot
from .wiki.store import instrument

def path(store):
    root=getattr(store,'data_root',store.path.parent)/'private'
    root.mkdir(parents=True,exist_ok=True)
    return root/'workspace.sqlite3'

def read(store):
    with sqlite3.connect(path(store)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS state (name TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        result={k:json.loads(v) for k,v in db.execute('SELECT name,payload FROM state')}
    if 'wiki' not in result:
        candidates=[]
        for p in (getattr(store,'data_root',store.path.parent)/'llm_wiki').glob('*/wiki.sqlite3'):
            with sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True) as db:
                ident=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
                latest=db.execute('SELECT max(updated_at) FROM jobs').fetchone()[0]
                if ident and latest:candidates.append((latest,json.loads(ident[0])))
        if candidates:result['wiki']={'instrument':max(candidates)[1],'controls':{}}
    return result

def save(store,section,value):
    if section not in ('news','wiki') or not isinstance(value,dict):raise ValueError('Invalid workspace section')
    allowed={'news':{'draft','snapshot','camera'},'wiki':{'instrument','controls','layout','root_selection','graph_universe','graph_settings','camera','root','selected'}}[section]
    if set(value)-allowed:raise ValueError('Unknown workspace fields')
    if section=='news':
        if 'snapshot' in value:value['snapshot']=validate_snapshot(value['snapshot'])
        if 'draft' in value:
            draft=value['draft']
            if not isinstance(draft,dict) or set(draft)-{'query','ticker','sources','rss_region','dates'}:raise ValueError('Invalid search draft')
            if len(json.dumps(draft))>4000:raise ValueError('Search draft too large')
    else:
        if value.get('instrument'):instrument(value['instrument'])
        controls=value.get('controls',{})
        keys={'wikiScope','wikiModel','wikiOperation','wikiRange','wikiStartDate','wikiEndDate','wikiRangeStart','wikiRangeEnd','wikiVersion','wikiKind','wikiRelation','wikiBudget','wikiAssessment','wikiLanguages','wikiEvidenceSize','wikiStrategy','wikiContinuous'}
        if not isinstance(controls,dict) or set(controls)-keys or any(not isinstance(v,(str,bool,int,float)) or len(str(v))>150 for v in controls.values()):raise ValueError('Invalid Wiki controls')
        layout=value.get('layout')
        if layout is not None:
            if not isinstance(layout,dict) or set(layout)-{'left','right','bottom'} or any(type(v) not in (int,float) or not (140 if k=='bottom' else 220)<=v<=(700 if k=='bottom' else 620) for k,v in layout.items()):raise ValueError('Invalid Wiki layout')
        selection=value.get('root_selection')
        if selection is not None:
            if not isinstance(selection,dict) or set(selection)-{'ticker','trees'} or not isinstance(selection.get('trees'),list) or len(selection['trees'])>10:raise ValueError('Invalid saved roots')
            for tree in selection['trees']:
                if not isinstance(tree,dict) or set(tree)-{'root_id','title','articles'} or not isinstance(tree.get('articles'),list) or len(tree['articles'])>150:raise ValueError('Invalid saved tree')
                if any(not isinstance(a,dict) or set(a)!={'id','provider'} for a in tree['articles']):raise ValueError('Invalid saved article')
        universe=value.get('graph_universe')
        if universe is not None:
            if not isinstance(universe,dict) or set(universe)-{'ticker','articles','separate'} or not isinstance(universe.get('articles'),list) or len(universe['articles'])>10000:raise ValueError('Invalid graph universe')
            if not isinstance(universe.get('ticker'),str) or len(universe['ticker'])>20 or not isinstance(universe.get('separate',False),bool):raise ValueError('Invalid universe identity')
            for a in universe['articles']:
                if not isinstance(a,dict) or set(a)!={'id','provider'} or a['provider'] not in ('google','yahoo','massive') or not isinstance(a['id'],str) or len(a['id'])>100:raise ValueError('Invalid universe member')
        if value.get('graph_settings') is not None:
            from .wiki.evidence import graph_options
            value['graph_settings']=graph_options(value['graph_settings'])
        if len(json.dumps(value))>2000000:raise ValueError('Wiki state too large')
    if value.get('camera'):
        c=value['camera']
        import math
        if not isinstance(c,dict) or set(c)!={'x','y','z'} or any(type(n) not in (int,float) or not math.isfinite(n) or abs(n)>1e7 for n in c.values()):raise ValueError('Invalid camera')
    read(store)
    with sqlite3.connect(path(store)) as db:
        old=db.execute('SELECT payload FROM state WHERE name=?',(section,)).fetchone()
        merged={**(json.loads(old[0]) if old else {}),**value}
        db.execute('INSERT OR REPLACE INTO state VALUES (?,?)',(section,json.dumps(merged,ensure_ascii=False)))
    return {'saved':True}

def handle(handler):
    from .wiki.http import writable
    if not writable(handler):handler.json_response(403,{'error':'Workspace requires a trusted local origin'});return
    try:
        if handler.command=='GET':result=read(handler.store)
        else:
            size=int(handler.headers.get('Content-Length','0'))
            if not 0<size<=64000000:raise ValueError('Workspace too large')
            body=json.loads(handler.rfile.read(size));result=save(handler.store,body.get('section'),body.get('value'))
        handler.json_response(200,result)
    except (ValueError,TypeError) as error:handler.json_response(400,{'error':str(error)})
