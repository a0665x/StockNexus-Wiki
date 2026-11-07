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
        if path.startswith('research/'):
            from .research import handle_research
            handle_research(handler,service,path.removeprefix('research/'),params,writable(handler));return
        if handler.command=='GET':
            if path=='models':
                handler.json_response(200,service.bridge_request('/wiki/models',timeout=20));return
            if path=='status':
                handler.json_response(200,{**service.info(),'writable':writable(handler)});return
            ident=params.get('instrument',[''])[0]
            from .store import instrument,folder_name
            instrument(ident)
            if not (service.root/folder_name(ident)/'wiki.sqlite3').exists(): raise ValueError('此股票尚未建立Wiki')
            store=service.store(ident)
            version=params.get('version',[None])[0]
            if path=='graph': data={**store.graph(version,params.get('as_of',[None])[0],start=params.get('start',[None])[0],end=params.get('end',[None])[0]),'coverage':service.coverage(store)}
            elif path=='jobs':
                with store.connection() as db: latest=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
                data={'jobs':store.jobs(),'config':store.config(),'version':latest,'coverage':service.coverage(store)}
            elif path=='node':
                with store.connection() as db:row=db.execute('SELECT payload FROM nodes WHERE id=? AND created_version<=?',(params.get('id',[''])[0],int(version) if version else 2147483647)).fetchone()
                if not row:raise ValueError('此版本找不到觀點')
                data=json.loads(row[0])
                from .evidence import cached_market
                refs=[c['article_revision_id'] for c in data.get('citations',[])]
                with store.connection() as db:articles=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(refs),))]
                horizon=int(params.get('price_horizon',['3'])[0])
                if horizon not in (1,3,5,7):raise ValueError('無效股價交易日範圍')
                data['current_market']=list(cached_market(service.news,store.instrument,articles,horizon).values())
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
        action={'plan':service.plan,'apply':service.apply,'jobs':service.start,'configure':service.configure,'cancel':service.cancel,'resume':service.resume}.get(path)
        if not action: handler.json_response(404,{'error':'Unknown Wiki endpoint'});return
        handler.json_response(202 if path=='jobs' else 200,action(body))
    except (ValueError,TypeError,KeyError) as error: handler.json_response(400,{'error':str(error)})
    except Exception:
        logging.getLogger(__name__).exception('Wiki API request failed path=%s',path)
        handler.json_response(503,{'error':'Wiki服務暫時無法使用，請檢查服務log後重試。'})
