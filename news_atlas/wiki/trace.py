"""Private, bounded stage traces. Never serialize evidence, prompts or exception text."""
import contextvars
import datetime as dt
import functools
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import uuid
from contextlib import contextmanager

_scope=contextvars.ContextVar('wiki_trace_scope',default={})
_locks={}
_guard=threading.Lock()
_warned=False
MAX_BYTES=8*1024*1024
BACKUPS=5

def root(owner):
    if hasattr(owner,'data_root'):return Path(owner.data_root)
    if hasattr(owner,'store') and not callable(owner.store):return root(owner.store)
    path=Path(owner.path)
    return path.parents[2] if path.name=='wiki.sqlite3' else path.parent

def error_fields(error):
    text=str(error).lower()
    code='timeout' if 'timed out' in text or isinstance(error,TimeoutError) else 'cancelled' if 'cancel' in text else 'quota' if any(x in text for x in ('429','quota','usage limit')) else 'authentication' if any(x in text for x in ('401','unauthorized','refresh token')) else 'validation' if isinstance(error,ValueError) else 'runtime'
    return {'error_type':type(error).__name__,'error_code':code,
            'frames':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)[-8:]]}

def emit(owner,event,stage,**fields):
    global _warned
    try:
        path=(root(owner)/'private/wiki-trace/python.jsonl').resolve()
        with _guard:lock=_locks.setdefault(str(path),threading.RLock())
        row={'schema':1,'ts':dt.datetime.now(dt.timezone.utc).isoformat(),'process':'python','pid':os.getpid(),
             'thread':threading.current_thread().name,**_scope.get(),'event':event,'stage':stage,**fields}
        line=(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        with lock:
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            if path.exists() and path.stat().st_size+len(line)>MAX_BYTES:
                for n in range(BACKUPS,0,-1):
                    src=path if n==1 else Path(str(path)+'.'+str(n-1))
                    if src.exists():os.replace(src,Path(str(path)+'.'+str(n)))
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
            with os.fdopen(fd,'ab') as out:out.write(line)
    except Exception:
        if not _warned:
            _warned=True;print('Wiki trace write failed; check private log storage. Model work is unchanged.',file=sys.stderr)

@contextmanager
def span(owner,stage,**fields):
    parent=_scope.get();ident=uuid.uuid4().hex
    token=_scope.set({**parent,**fields,'span_id':ident,'parent_span_id':parent.get('span_id')})
    started=time.monotonic();metrics={}
    emit(owner,'begin',stage)
    try:
        yield metrics
    except BaseException as error:
        emit(owner,'error',stage,elapsed_ms=round((time.monotonic()-started)*1000,3),**error_fields(error));raise
    else:emit(owner,'end',stage,elapsed_ms=round((time.monotonic()-started)*1000,3),**metrics)
    finally:_scope.reset(token)

def job_fields(store,job):
    p=job.get('payload',{});p=json.loads(p) if isinstance(p,str) else p
    return {'instrument':store.instrument,'job_id':job['id'],'operation':p.get('operation','update'),
            'model':p.get('model'),'reasoning_effort':p.get('reasoning_effort')}

def job_state(store,job,table='jobs'):
    try:
        with store.connection() as db:
            row=db.execute('SELECT status,updated_at FROM '+table+' WHERE id=?',(job['id'],)).fetchone()
        if row:emit(store,'state','job',**job_fields(store,job),status=row['status'])
    except Exception:emit(store,'state','job_state_unavailable',**job_fields(store,job))

def admitted(store,job):
    updated=job.get('updated_at') or job.get('created_at')
    queued=max(0,(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(updated)).total_seconds()*1000) if updated else None
    emit(store,'state','job',**job_fields(store,job),status='running',queued_ms=round(queued,3) if queued is not None else None)

def timed(stage):
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(owner,*args,**kwargs):
            fields={'instrument':getattr(owner,'instrument',None)}
            if args and isinstance(args[0],dict):
                a=args[0]
                if 'payload' in a and 'id' in a:fields.update(job_fields(owner,a))
                else:fields.update({k:a[k] for k in ('instrument','model','plan_id','job_id') if k in a and isinstance(a[k],str) and len(a[k])<=100})
            if len(args)>1 and isinstance(args[1],dict):
                group=args[1].get('_group',{})
                fields.update({k:group[k] for k in ('root_id','part') if k in group})
            with span(owner,stage,**fields) as metrics:
                result=fn(owner,*args,**kwargs)
                if isinstance(result,dict):
                    for k in ('job_id','plan_id','status','version'):
                        if k in result:metrics[k]=result[k]
                return result
        return wrapped
    return decorate
