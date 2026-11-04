"""Bounded incremental compiler; the LLM can propose JSON, never write the DB."""
import json
import datetime as dt
import threading
import time
import uuid
import sqlite3
import logging
from .store import WikiStore, capture, instrument, digest, now, PROMPT_VERSION
from ..chat_proxy import UnixConnection
from ..search import query_key

log=logging.getLogger(__name__)

class WikiService:
    def __init__(self,news,runner=None,start_worker=True):
        self.news=news;self.root=news.path.parent/'research'
        self.runner=runner or self.bridge
        self.plans={};self.lock=threading.RLock();self.stop=threading.Event();self.wake=threading.Event()
        self.thread=None;self.active=None
        # A crashed model call is not silently retried (it may have consumed quota).
        for store in self.stores():
            with store.connection() as db:
                interrupted=db.execute("UPDATE jobs SET status='interrupted',error='服務重啟；可預覽後續跑',updated_at=? WHERE status='running'",(now(),)).rowcount
            if interrupted:
                cfg=store.config();cfg["enabled"]=False;store.configure(cfg)
        if start_worker:
            self.thread=threading.Thread(target=self.loop,daemon=True,name='wiki-worker');self.thread.start()

    def stores(self):
        if not self.root.exists(): return []
        result=[]
        for p in sorted(self.root.glob('*/wiki.sqlite3')):
            try:
                with sqlite3.connect(f'file:{p}?mode=ro',uri=True) as db:
                    row=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
                if row: result.append(WikiStore(self.root,json.loads(row[0])))
            except (sqlite3.Error,ValueError): log.warning('Wiki registry entry could not be read')
        return result

    def store(self,ident):
        return WikiStore(self.root,instrument(ident))

    def bridge_request(self,path,body=None,timeout=140):
        conn=UnixConnection(self.news.path.parent/'private/chat.sock');conn.timeout=timeout
        try:
            conn.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            response=conn.getresponse();payload=json.loads(response.read(1024*1024))
            if response.status!=200: raise RuntimeError(payload.get('error','LLM橋接失敗'))
            return payload
        except (OSError,json.JSONDecodeError) as error: raise RuntimeError('LLM橋接無法連線；請檢查 Chat 服務及登入狀態') from error
        finally: conn.close()

    def bridge(self,store,job,article,context):
        return self.bridge_request('/wiki/compile',{'job_id':job['id'],'instrument':store.instrument,'model':job['payload']['model'],'article':article,'context':context,'operation':job['payload'].get('operation','update')})

    def info(self):
        try: bridge=self.bridge_request('/status',timeout=2)
        except RuntimeError: bridge={'ready':False}
        stocks=[]
        for store in self.stores():
            with store.connection() as db:
                version=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
                total=db.execute('SELECT count(*) FROM nodes').fetchone()[0]
            stocks.append({'instrument':store.instrument,'version':version,'nodes':total,'enabled':store.config()['enabled']})
        return {'instruments':stocks,'bridge_ready':bridge.get('wiki_ready',False),'default_model':bridge.get('wiki_model',''),'storage':'research/<instrument-hash>/wiki.sqlite3','prompt_version':PROMPT_VERSION}

    @staticmethod
    def options(body):
        model=body.get('model','');batch=body.get('batch_size',5);daily=body.get('daily_limit',20)
        if not isinstance(model,str) or not 1<=len(model)<=100 or not all(c.isalnum() or c in '-_./:' for c in model): raise ValueError('請指定有效模型名稱')
        if type(batch) is not int or not 1<=batch<=20 or type(daily) is not int or not 1<=daily<=100: raise ValueError('每批1–20篇，每日1–100篇')
        return model,batch,daily

    @staticmethod
    def date_range(body):
        value=body.get('date_range')
        if value is None:return None
        if not isinstance(value,dict) or set(value)!={'start','end'}:raise ValueError('請指定完整起訖日期')
        start=dt.date.fromisoformat(value['start']);end=dt.date.fromisoformat(value['end'])
        if start>end:raise ValueError('開始日期不得晚於結束日期')
        return {'start':start.isoformat(),'end':end.isoformat()}

    @staticmethod
    def in_range(a,dates):
        if not dates:return True
        if not a['published_at']:return False
        day=dt.datetime.fromisoformat(a['published_at'].replace('Z','+00:00')).astimezone(dt.timezone.utc).date().isoformat()
        return dates['start']<=day<=dates['end']

    def subscribed(self,subscriptions,dates):
        rows=[]
        with self.news.connection() as db:
            for sub in subscriptions:
                # Date filtering precedes the cap, so expanding older ranges is usable.
                found=db.execute("""SELECT a.payload FROM articles a JOIN memberships m
                    ON a.id=m.article_id AND a.provider=m.provider WHERE m.provider=? AND m.query_key=?
                    AND (? IS NULL OR date(a.published_at) BETWEEN ? AND ?)
                    ORDER BY a.published_at DESC LIMIT 10001""",(sub['provider'],sub['query_key'],None if not dates else 1,(dates or {}).get('start'),(dates or {}).get('end'))).fetchall()
                if len(found)>10000:raise ValueError('查詢超過10000篇，請縮小日期範圍')
                rows.extend(capture(json.loads(r[0])) for r in found)
        return rows

    def plan(self,body):
        model,batch,daily=self.options(body);store=self.store(body.get('instrument'))
        operation=body.get('operation','update')
        if operation not in ('update','review'):raise ValueError('無效維護方式')
        dates=self.date_range(body)
        rows=body.get('articles',[])
        if not isinstance(rows,list) or len(rows)>10000: raise ValueError('最多選取10000篇')
        rows=list(map(capture,rows))
        search=body.get('search',{});sources=body.get('sources',[])
        if not isinstance(search,dict) or not isinstance(sources,list) or len(sources)>3 or any(p not in ('google','yahoo','massive') for p in sources): raise ValueError('無效追蹤範圍')
        subscriptions=[]
        for p in sources:
            term=search.get('ticker' if p=='massive' else 'query','')
            if not isinstance(term,str) or len(term)>200: raise ValueError('無效來源查詢')
            if term.strip(): subscriptions.append({'provider':p,'term':term,'query_key':query_key(p,term,search.get('rss_region'))})
        if search.get('ticker') and str(search['ticker']).upper()!=store.instrument.split(':')[1]: raise ValueError('搜尋股票與Wiki股票不同，請先確認選取範圍')
        if body.get('scope','loaded')=='global':
            latest={(a['provider'],a['id']):a for a in rows}
            latest.update({(a['provider'],a['id']):a for a in self.subscribed(subscriptions,dates)})
            rows=list(latest.values())
        elif body.get('scope','loaded') not in ('loaded','focus'):raise ValueError('無效選取範圍')
        rows=list({a['revision_id']:a for a in rows if self.in_range(a,dates)}.values())
        if len(rows)>10000:raise ValueError('範圍超過10000篇，請縮小日期範圍')
        unseen=store.known(rows);pending=len(store.pending(limit=10000,revision_ids=[a['revision_id'] for a in rows],review=True)) if operation=='review' else len(unseen)
        with store.connection() as db: base=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
        plan={'id':uuid.uuid4().hex,'instrument':store.instrument,'model':model,'batch_size':batch,'daily_limit':daily,'rows':rows,'subscriptions':subscriptions,'date_range':dates,'operation':operation,'base_version':base,'expires':time.time()+600}
        with self.lock:
            self.plans={k:p for k,p in self.plans.items() if p['expires']>time.time()}
            if len(self.plans)>=4: self.plans.pop(next(iter(self.plans)))
            self.plans[plan['id']]=plan
        return {'plan_id':plan['id'],'instrument':store.instrument,'base_version':base,'selected':len(rows),'pending':pending,'next_batch':min(pending,batch),'reused':len(rows)-len(unseen),'model':model,'daily_limit':daily,'date_range':dates,'operation':operation,'watch_sources':subscriptions,'expires_in':600,'note':'只處理本次日期範圍；增量模式跨模型重用既有成果，不受新聞edge設定與渲染數影響。局部校正需另行明確選擇，仍會消耗token。'}

    def start(self,body):
        if not isinstance(body.get('continuous',False),bool): raise ValueError('無效持續維護設定')
        with self.lock:
            plan=self.plans.get(body.get('plan_id'))
            if not plan or plan['expires']<time.time(): raise ValueError('預覽已失效，請重新預覽')
            store=self.store(plan['instrument'])
            with store.connection() as db:
                base=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
                if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone(): raise ValueError('此股票已有工作，請等待完成或先停止，再重新預覽')
            if base!=plan['base_version']: raise ValueError('Wiki版本已改變，請重新預覽')
            if plan['operation']=='review' and body.get('continuous'):raise ValueError('局部校正僅能手動執行，不可持續重跑')
            store.ingest(plan['rows'])
            cfg={'enabled':body.get('continuous',False),'model':plan['model'],'batch_size':plan['batch_size'],'daily_limit':plan['daily_limit'],'subscriptions':plan['subscriptions'],'date_range':plan['date_range'],'revision_ids':[a['revision_id'] for a in plan['rows']]}
            store.configure(cfg)
            ident=store.enqueue(cfg['model'],cfg['batch_size'],cfg['daily_limit'],cfg['revision_ids'],plan['operation'])
            self.plans.pop(plan['id'],None);self.wake.set()
        return {'job_id':ident,'instrument':store.instrument}

    def configure(self,body):
        with self.lock:return self._configure(body)

    def _configure(self,body):
        store=self.store(body.get('instrument'));cfg=store.config()
        enabled=body.get('enabled')
        if not isinstance(enabled,bool): raise ValueError('enabled必須是boolean')
        if enabled: self.options(cfg)
        cfg['enabled']=enabled;store.configure(cfg);self.wake.set()
        return cfg

    def cancel(self,body):
        with self.lock:return self._cancel(body)

    def _cancel(self,body):
        store=self.store(body.get('instrument'));store.cancel(body.get('job_id'))
        try: self.bridge_request('/wiki/cancel',{'job_id':body.get('job_id')},timeout=2)
        except RuntimeError: pass
        cfg=store.config();cfg['enabled']=False;store.configure(cfg)
        return {'cancelled':True,'continuous':False}

    def refresh(self,store):
        with self.lock:return self._refresh(store)

    def _refresh(self,store):
        cfg=store.config()
        if not cfg['enabled']: return
        # Only memberships explicitly authorized in preview; no provider calls here.
        rows=self.subscribed(cfg['subscriptions'],cfg.get('date_range'))
        store.ingest(rows)
        with store.connection() as db:
            initial=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(cfg.get('revision_ids',[])),))]
        latest={(a['provider'],a['id']):a for a in initial}
        latest.update({(a['provider'],a['id']):a for a in rows})
        ids=[a['revision_id'] for a in latest.values()]
        if store.pending(limit=1,revision_ids=ids):
            with store.connection() as db:
                count=db.execute('SELECT count(*) FROM calls WHERE day=?',(now()[:10],)).fetchone()[0]
            if count<cfg['daily_limit']: store.enqueue(cfg['model'],cfg['batch_size'],cfg['daily_limit'],ids)

    def process(self,store):
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            raw=db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not raw: return
            job=dict(raw);job['payload']=json.loads(job['payload'])
            db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?",(now(),job['id']))
        self.active=(store,job['id'])
        try:
            for revision in job['payload']['revisions']:
                if self.stop.is_set(): return
                with store.connection() as db:
                    if job['payload'].get('operation')!='review' and db.execute('SELECT 1 FROM extractions WHERE revision=?',(revision,)).fetchone(): continue
                    article=json.loads(db.execute('SELECT payload FROM articles WHERE id=?',(revision,)).fetchone()[0])
                if not store.reserve_call(job,revision): return
                context=store.context(article)
                output=self.runner(store,job,article,context)
                if not isinstance(output,dict) or not isinstance(output.get('usage',{}),dict): raise ValueError('LLM回覆格式錯誤')
                if not store.publish(job,article,output.get('proposal'),context,output.get('usage',{})): return
            with store.connection() as db: db.execute("UPDATE jobs SET status='completed',updated_at=? WHERE id=? AND status='running'",(now(),job['id']))
            log.info('wiki_job completed instrument=%s job=%s',store.instrument,job['id'])
        except Exception as error:
            with store.connection() as db: db.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=? AND status='running'",(str(error)[:600],now(),job['id']))
            cfg=store.config();cfg['enabled']=False;store.configure(cfg)
            log.warning('wiki_job failed instrument=%s job=%s error_type=%s',store.instrument,job['id'],type(error).__name__)
        finally: self.active=None

    def tick(self):
        for store in self.stores():
            if self.stop.is_set(): break
            self.refresh(store);self.process(store)

    def loop(self):
        while not self.stop.is_set():
            try: self.tick()
            except Exception: log.exception('Wiki worker cycle failed')
            self.wake.wait(60);self.wake.clear()

    def close(self):
        self.stop.set();self.wake.set()
        if self.active:
            try: self.bridge_request('/wiki/cancel',{'job_id':self.active[1]},timeout=2)
            except RuntimeError: pass
