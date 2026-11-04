"""Same-origin Wiki API. Cost-bearing writes require an explicitly allowed origin."""
import json
import logging
import os
import urllib.parse
from ..chat_proxy import local_peer
from .compiler import WikiService

def writable(handler):
    host=handler.headers.get('Host','')
    origin=handler.headers.get('Origin','')
    allowed={'http://127.0.0.1:8765','http://localhost:8765'}
    allowed.update(x.strip() for x in os.environ.get('NEWS_ATLAS_WIKI_ORIGINS','').split(',') if x.strip())
    if not local_peer(handler.client_address[0]) or handler.headers.get('Sec-Fetch-Site')=='cross-site': return False
    if handler.command=='GET': return any(urllib.parse.urlsplit(x).netloc==host for x in allowed)
    return origin in allowed and urllib.parse.urlsplit(origin).netloc==host

def handle(handler):
    if not hasattr(handler.server,'wiki'):
        handler.server.wiki=WikiService(handler.store)
    service=handler.server.wiki
    url=urllib.parse.urlsplit(handler.path);path=url.path.removeprefix('/api/wiki/')
    params=urllib.parse.parse_qs(url.query)
    try:
        if handler.command=='GET':
            if path=='status':
                handler.json_response(200,{**service.info(),'writable':writable(handler)});return
            ident=params.get('instrument',[''])[0]
            from .store import instrument,digest
            instrument(ident)
            if not (service.root/digest(ident)[:24]/'wiki.sqlite3').exists(): raise ValueError('此股票尚未建立Wiki')
            store=service.store(ident)
            version=params.get('version',[None])[0]
            if path=='graph': data=store.graph(version,params.get('as_of',[None])[0])
            elif path=='jobs':
                with store.connection() as db: latest=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
                data={'jobs':store.jobs(),'config':store.config(),'version':latest}
            elif path=='article':
                with store.connection() as db: row=db.execute('SELECT payload FROM articles WHERE id=?',(params.get('id',[''])[0],)).fetchone()
                if not row: raise ValueError('引用版本不存在')
                data=json.loads(row[0])
            elif path=='markdown': data={'markdown':store.markdown(version)}
            else: handler.json_response(404,{'error':'Unknown Wiki endpoint'});return
            handler.json_response(200,data);return
        if not writable(handler):
            handler.json_response(403,{'error':'此來源未開放Wiki維護；請使用本機頁面或設定NEWS_ATLAS_WIKI_ORIGINS。'});return
        length=int(handler.headers.get('Content-Length','0'))
        if handler.headers.get('Content-Type','').split(';')[0]!='application/json' or not 0<length<=32*1024*1024: raise ValueError('無效Wiki請求大小')
        body=json.loads(handler.rfile.read(length))
        if not isinstance(body,dict): raise ValueError('需要JSON object')
        action={'plan':service.plan,'jobs':service.start,'configure':service.configure,'cancel':service.cancel}.get(path)
        if not action: handler.json_response(404,{'error':'Unknown Wiki endpoint'});return
        handler.json_response(202 if path=='jobs' else 200,action(body))
    except (ValueError,TypeError,KeyError) as error: handler.json_response(400,{'error':str(error)})
    except Exception:
        logging.getLogger(__name__).exception('Wiki API request failed path=%s',path)
        handler.json_response(503,{'error':'Wiki服務暫時無法使用，請檢查服務log後重試。'})
