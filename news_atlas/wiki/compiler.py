"""Bounded incremental compiler; the LLM can propose JSON, never write the DB."""
import json
import datetime as dt
import threading
import time
import uuid
import sqlite3
import logging
from .store import WikiStore, capture, instrument, digest, now, PROMPT_VERSION, validate_proposal, migrate_legacy
from ..chat_proxy import UnixConnection
from ..search import query_key
from .workbench import settings, batches, usage_summary, news_day

from .evidence import OPTION_KEYS, selected_graph_rows, bounded_groups, cached_market

log=logging.getLogger(__name__)

class WikiService:
    def __init__(self,news,runner=None,start_worker=True):
        self.news=news;self.data_root=getattr(news,'data_root',news.path.parent);migrate_legacy(self.data_root);self.root=self.data_root/'llm_wiki'
        self.runner=runner or self.bridge
        self.plans={};self.lock=threading.RLock();self.stop=threading.Event();self.wake=threading.Event()
        self.thread=None;self.active=None
        # A crashed model call is not silently retried (it may have consumed quota).
        for store in self.stores():
            with store.connection() as db:
                interrupted=db.execute("UPDATE jobs SET status='interrupted',error='服務重啟；可預覽後續跑',updated_at=? WHERE status='running'",(now(),)).rowcount
            if interrupted:
                cfg=store.config();cfg["enabled"]=False;cfg['catch_up']=False;store.configure(cfg)
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
        conn=UnixConnection(self.data_root/'private/chat.sock');conn.timeout=timeout
        try:
            conn.request('GET' if body is None else 'POST',path,body=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            response=conn.getresponse();payload=json.loads(response.read(1024*1024))
            if response.status!=200: raise RuntimeError(payload.get('error','LLM橋接失敗'))
            return payload
        except (OSError,json.JSONDecodeError) as error: raise RuntimeError('LLM橋接無法連線；請檢查 Chat 服務及登入狀態') from error
        finally: conn.close()

    def bridge(self,store,job,article,context):
        return self.bridge_request('/wiki/compile',{'job_id':job['id'],'instrument':store.instrument,'model':job['payload']['model'],'article':{k:v for k,v in article.items() if k!='_covered_articles'},'context':context,'operation':job['payload'].get('operation','update'),'repair':job.get('repair'),**{k:job['payload'].get(k) for k in ('reasoning_effort','languages')}},timeout=640)

    def info(self):
        try: bridge=self.bridge_request('/status',timeout=2)
        except RuntimeError: bridge={'ready':False}
        stocks=[]
        for store in self.stores():
            with store.connection() as db:
                version=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
                total=db.execute('SELECT count(*) FROM nodes').fetchone()[0]
            stocks.append({'instrument':store.instrument,'version':version,'nodes':total,'enabled':store.config()['enabled']})
        return {'instruments':stocks,'bridge_ready':bridge.get('wiki_ready',False),'default_model':bridge.get('wiki_model',''),'storage':'llm_wiki/<ticker>/wiki.sqlite3','prompt_version':PROMPT_VERSION}

    @staticmethod
    def options(body):
        model=body.get('model','')
        if not isinstance(model,str) or not 1<=len(model)<=100 or not all(c.isalnum() or c in '-_./:' for c in model): raise ValueError('請指定有效模型名稱')
        return model

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

    def subscribed(self,subscriptions,dates,ident=None):
        rows=[]
        from ..graph_storage import select
        news=select(self.news,ident.split(':',1)[1] if ident else '')
        with news.connection() as db:
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
        model=self.options(body);options=settings(body);store=self.store(body.get('instrument'))
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
            if not subscriptions and not rows:
                cfg=store.config();subscriptions=cfg.get('subscriptions',[])
                # Reopening a saved Wiki must not depend on the News Graph being mounted.
                with store.connection() as db:
                    saved=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles ORDER BY captured_at,id')]
                rows=list({(a['provider'],a['id']):a for a in saved}.values())
            latest={(a['provider'],a['id']):a for a in rows}
            latest.update({(a['provider'],a['id']):a for a in self.subscribed(subscriptions,dates,store.instrument)})
            rows=list(latest.values())
        elif body.get('scope','loaded') not in ('loaded','focus'):raise ValueError('無效選取範圍')
        context_rows=[]
        if options['strategy']=='root':
            if not body.get('graph_settings'):options['graph_settings']=store.config().get('graph_settings',options['graph_settings'])
            universe=body.get('graph_universe') or store.config().get('graph_universe')
            if universe:
                from .forest import prepare
                rows,context_rows,options['graph_selection']=prepare(self.news,store.instrument,universe,options['graph_settings'],dates)
                options['graph_universe']=universe;options['graph_context_revisions']=[a['revision_id'] for a in context_rows]
            else:
                selection=body.get('graph_selection',store.config().get('graph_selection'))
                raw=selected_graph_rows(self.news,store.instrument,selection,dates)
                options['graph_selection']=selection
                rows=list(map(capture,raw))
        rows=list({a['revision_id']:a for a in rows if self.in_range(a,dates)}.values())
        if len(rows)>10000:raise ValueError('範圍超過10000篇，請縮小日期範圍')
        ids={a['id'] for a in rows}
        supplied=options['graph_edges'] or store.config().get('graph_edges',[])
        options['graph_edges']=[e for e in supplied if e['source'].split('::')[-1] in ids and e['target'].split('::')[-1] in ids]
        unseen=store.known(rows);pending=len(store.pending(limit=10000,revision_ids=[a['revision_id'] for a in rows],review=True)) if operation=='review' else len(unseen)
        with store.connection() as db: base=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
        plan={**options,'settings_version':store.config().get('settings_version',0),'id':uuid.uuid4().hex,'instrument':store.instrument,'model':model,'rows':rows,'context_rows':context_rows,'subscriptions':subscriptions,'date_range':dates,'operation':operation,'base_version':base,'expires':time.time()+600}
        with self.lock:
            self.plans={k:p for k,p in self.plans.items() if p['expires']>time.time()}
            if len(self.plans)>=4: self.plans.pop(next(iter(self.plans)))
            self.plans[plan['id']]=plan
        with store.connection() as db:used=db.execute('SELECT count(*) FROM calls WHERE day=?',(now()[:10],)).fetchone()[0]
        dated=sorted(news_day(a['published_at']) for a in rows if a['published_at'])
        return {'date_bounds':{'start':dated[0],'end':dated[-1]} if dated else None,'graph_selection':options.get('graph_selection'),'grouping_edges':len(options['graph_edges']),'usage':usage_summary(store,(dates or {}).get('start'),(dates or {}).get('end')),**{k:options[k] for k in ('reasoning_effort','languages','evidence_size','strategy')},'daily_used':used,'plan_id':plan['id'],'instrument':store.instrument,'base_version':base,'selected':len(rows),'pending':pending,'next_batch':pending,'reused':len(rows)-len(unseen),'model':model,'date_range':dates,'operation':operation,'watch_sources':subscriptions,'expires_in':600,'note':'只處理本次日期範圍；增量模式跨模型重用既有成果，不受新聞edge設定與渲染數影響。局部校正需另行明確選擇，仍會消耗token。'}

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
            pending=store.pending(limit=1,revision_ids=[a['revision_id'] for a in plan['rows']],review=True) if plan['operation']=='review' else store.known(plan['rows'])
            if not pending:
                self.plans.pop(plan['id'],None)
                return {'job_id':None,'instrument':store.instrument,'status':'noop','message':'此範圍沒有待辦；未啟動模型，原設定保留。'}
            store.ingest([*plan.get('context_rows',[]),*plan['rows']])
            cfg={**{k:plan[k] for k in OPTION_KEYS if k in plan},'enabled':body.get('continuous',False),'catch_up':plan['operation']=='update','model':plan['model'],'subscriptions':plan['subscriptions'],'date_range':plan['date_range'],'revision_ids':[a['revision_id'] for a in plan['rows']]}
            store.configure(cfg)
            ident=store.enqueue(cfg['model'],revision_ids=cfg['revision_ids'],operation=plan['operation'])
            self.plans.pop(plan['id'],None);self.wake.set()
        return {'job_id':ident,'instrument':store.instrument}

    def apply(self,body):
        # Validate/rebuild before cancellation: a bad setting must leave the old work alive.
        if not isinstance(body.get('continuous',False),bool):raise ValueError('無效持續維護設定')
        if body.get('operation')=='review' and body.get('continuous'):raise ValueError('重審不能持續重跑')
        preview=self.plan(body)
        with self.lock:
            plan=self.plans[preview['plan_id']];store=self.store(plan['instrument'])
            active=[j for j in store.jobs() if j['status'] in ('queued','running')]
            cfg=store.config();continuing=bool(active or cfg.get('catch_up') or cfg.get('enabled'))
            for job in active:self._cancel({'instrument':store.instrument,'job_id':job['id']})
            # Late results are rejected by publish's status check. Old failure handlers
            # must not disable this new config. The single worker waits for abort to finish.
            with store.connection() as db:plan['base_version']=db.execute('SELECT COALESCE(max(version),0) FROM versions').fetchone()[0]
            plan['settings_version']=int(cfg.get('settings_version',0))+1
            cfg.update({k:plan[k] for k in OPTION_KEYS if k in plan})
            store.ingest([*plan.get('context_rows',[]),*plan['rows']])
            cfg.update(model=plan['model'],enabled=False,catch_up=False,subscriptions=plan['subscriptions'],date_range=plan['date_range'],revision_ids=[a['revision_id'] for a in plan['rows']])
            if continuing and plan['operation']=='review':
                with store.connection() as db:done={r[0] for j in active for r in db.execute('SELECT revision FROM reviews WHERE job_id=?',(j['id'],))}
                plan['rows']=[a for a in plan['rows'] if a['revision_id'] not in done]
            store.configure(cfg)
            if continuing:
                result=self.start({'plan_id':plan['id'],'continuous':bool(body.get('continuous',False))})
            else:
                self.plans.pop(plan['id'],None);result={'status':'saved','job_id':None,'instrument':store.instrument}
            log.info('wiki_settings applied instrument=%s version=%s resumed=%s',store.instrument,plan['settings_version'],continuing)
            return {**result,'settings_version':plan['settings_version'],'resumed':bool(continuing and result.get('job_id'))}

    def scope_rows(self,store,dates=None):
        cfg=store.config();dates=cfg.get('date_range') if dates is None else dates
        if cfg.get('strategy')=='root' and cfg.get('graph_universe'):
            from .forest import universe_rows,in_range
            return [capture(a) for a in universe_rows(self.news,store.instrument,cfg['graph_universe']) if in_range(a,dates)]
        if cfg.get('strategy')=='root':return list(map(capture,selected_graph_rows(self.news,store.instrument,cfg.get('graph_selection'),dates)))
        with store.connection() as db:
            initial=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(cfg.get('revision_ids',[])),))]
        rows={(a['provider'],a['id']):a for a in initial if self.in_range(a,dates)}
        fresh=map(capture,selected_graph_rows(self.news,store.instrument,cfg.get('graph_selection'),dates)) if cfg.get('strategy')=='root' else self.subscribed(cfg.get('subscriptions',[]),dates,store.instrument)
        rows.update({(a['provider'],a['id']):a for a in fresh})
        return list(rows.values())

    def coverage(self,store):
        cfg=store.config()
        try:rows=self.scope_rows(store)
        except ValueError as error:return {'unavailable':True,'instrument':store.instrument,'error':str(error)+'；舊 Wiki 仍可閱讀，請縮小日期後重新預覽。'}
        missing=store.known(rows);ids=[a['revision_id'] for a in rows]
        with store.connection() as db:
            captured=db.execute('SELECT count(*) FROM articles').fetchone()[0]
            extracted=db.execute('SELECT count(DISTINCT revision) FROM extractions').fetchone()[0]
            used=db.execute('SELECT count(*) FROM calls WHERE day=?',(now()[:10],)).fetchone()[0]
            rejected=db.execute('SELECT count(*) FROM rejected_proposals').fetchone()[0]
        review_pending=len(store.pending(limit=10000,revision_ids=ids,review=True));done=len(rows)-len(missing)
        with store.connection() as db:
            reviewed=db.execute('SELECT count(*) FROM review_coverage WHERE revision IN (SELECT value FROM json_each(?))',(json.dumps(ids),)).fetchone()[0]
        return {'scope_total':len(rows),'scope_done':done,'scope_pending':len(missing),'scope_percent':round(100*done/len(rows),2) if rows else 0,
            'review_done':reviewed,'review_total':done,'captured_revisions':captured,'extracted_revisions':extracted,
            'daily_calls':used,'rejected_responses':rejected,'usage':usage_summary(store,(cfg.get('date_range') or {}).get('start'),(cfg.get('date_range') or {}).get('end')),
            'storage':str(store.path.relative_to(self.data_root)),'instrument':store.instrument,'date_range':cfg.get('date_range'),
            'subscriptions':cfg.get('subscriptions',[]),'note':'分母為已確認查詢及日期範圍的最新新聞版本，不是全部新聞DB或渲染節點；校正覆蓋不代表正確率。'}

    def resume(self,body):
        with self.lock:
            store=self.store(body.get('instrument'));cfg=store.config();self.options(cfg)
            if any(j['status'] in ('queued','running') for j in store.jobs()):raise ValueError('此股票已有工作，請等待完成或先停止')
            dates=cfg.get('date_range')
            if dates:dates={**dates,'end':max(dates['end'],now()[:10])}
            rows=self.scope_rows(store,dates)
            if len(rows)>10000:raise ValueError('範圍超過10000篇，請重新預覽較小範圍')
            store.ingest(rows);cfg.update(date_range=dates,revision_ids=[a['revision_id'] for a in rows],catch_up=True)
            store.configure(cfg);self._refresh(store);self.wake.set()
            return {'instrument':store.instrument,'coverage':self.coverage(store),'config':store.config()}

    def configure(self,body):
        with self.lock:return self._configure(body)

    def _configure(self,body):
        store=self.store(body.get('instrument'));cfg=store.config()
        enabled=body.get('enabled')
        if not isinstance(enabled,bool): raise ValueError('enabled必須是boolean')
        if enabled: self.options(cfg)
        cfg['enabled']=enabled;cfg['catch_up']=False;store.configure(cfg);self.wake.set()
        return cfg

    def cancel(self,body):
        with self.lock:return self._cancel(body)

    def _cancel(self,body):
        store=self.store(body.get('instrument'));store.cancel(body.get('job_id'))
        try: self.bridge_request('/wiki/cancel',{'job_id':body.get('job_id')},timeout=2)
        except RuntimeError: pass
        cfg=store.config();cfg['enabled']=False;cfg['catch_up']=False;store.configure(cfg)
        return {'cancelled':True,'continuous':False}

    def refresh(self,store):
        with self.lock:return self._refresh(store)

    def _refresh(self,store):
        cfg=store.config()
        if not (cfg['enabled'] or cfg.get('catch_up')): return
        # Active jobs already own a frozen universe; rebuild only after they drain.
        with store.connection() as db:
            if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone():return
        # Only memberships explicitly authorized in preview; no provider calls here.
        if cfg.get('strategy')=='root' and cfg.get('graph_universe'):
            from .forest import prepare
            rows,context,cfg['graph_selection']=prepare(self.news,store.instrument,cfg['graph_universe'],cfg['graph_settings'],cfg.get('date_range'))
            store.ingest(context);cfg['graph_context_revisions']=[a['revision_id'] for a in context];cfg['revision_ids']=[a['revision_id'] for a in rows];store.configure(cfg)
        elif cfg.get('strategy')=='root':
            rows=list(map(capture,selected_graph_rows(self.news,store.instrument,cfg.get('graph_selection'),cfg.get('date_range'))))
        else:rows=self.subscribed(cfg['subscriptions'],cfg.get('date_range'),store.instrument)
        store.ingest(rows)
        with store.connection() as db:
            initial=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(cfg.get('revision_ids',[])),))]
        latest={(a['provider'],a['id']):a for a in initial}
        latest.update({(a['provider'],a['id']):a for a in rows})
        ids=[a['revision_id'] for a in latest.values()]
        if store.pending(limit=1,revision_ids=ids):
            store.enqueue(cfg['model'],revision_ids=ids)
        elif cfg.get('catch_up'):
            cfg['catch_up']=False;store.configure(cfg)

    def process(self,store,max_groups=None):
        with store.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            raw=db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not raw: return
            job=dict(raw);job['payload']=json.loads(job['payload'])
            db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?",(now(),job['id']))
        self.active=(store,job['id'])
        try:
            with store.connection() as db:
                rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(job['payload']['revisions']),))]
            if job['payload'].get('operation')!='review':rows=store.known(rows)
            else:
                with store.connection() as db:reviewed={r[0] for r in db.execute('SELECT revision FROM reviews WHERE job_id=?',(job['id'],))}
                rows=[a for a in rows if a['revision_id'] not in reviewed]
            forest=job['payload'].get('graph_selection',{})
            if forest.get('mode')=='coverage':
                from .forest import groups
                with store.connection() as db:context_rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(job['payload']['context_revisions']),))]
                work=groups(rows,context_rows,forest);market_rows=context_rows
            else:
                work=((g,meta,g) for g,meta in bounded_groups(batches(rows,job['payload'])));market_rows=rows
            market=cached_market(self.news,store.instrument,market_rows,job['payload'].get('price_horizon',3))
            completed_groups=0
            for group,group_info,covered in work:
                article={**group[0],'_evidence':group,'_market':{a['revision_id']:market[a['revision_id']] for a in group},'_group':group_info,'_context_revisions':job['payload'].get('context_revisions')};article['_covered_articles']=covered
                if forest.get('mode')=='coverage':article['_context_revisions']=[a['revision_id'] for a in group]
                revision=article['revision_id']
                if self.stop.is_set(): return
                with store.connection() as db:
                    if job['payload'].get('operation')!='review' and db.execute('SELECT 1 FROM extractions WHERE revision=?',(revision,)).fetchone(): continue
                    pass
                if not store.reserve_call(job,revision): return
                context=store.context({**article,'summary':' '.join(a['title']+' '+a['summary'][:1500] for a in group)})
                refs=[n['id'] for n in context if n['kind']=='ArticleRevision']
                with store.connection() as db:article['_related_articles']=[json.loads(r[0]) for r in db.execute('SELECT payload FROM articles WHERE id IN (SELECT value FROM json_each(?))',(json.dumps(refs),))]
                job['current_title']=article['title']
                with store.connection() as db:
                    db.execute("UPDATE jobs SET payload=json_set(payload,'$.current_title',?,'$.current_date',?,'$.current_size',?,'$.group_info',json(?)) WHERE id=?",(article['title'],article['published_at'],len(group),json.dumps(group_info),job['id']))
                for attempt in range(2):
                    store.stage(job,'repairing' if attempt else 'compiling',revision)
                    output=self.runner(store,job,article,context)
                    if not isinstance(output,dict) or not isinstance(output.get('usage',{}),dict): raise ValueError('LLM回覆格式錯誤')
                    try:
                        validate_proposal(article,output.get('proposal'),context)
                        if job['payload'].get('operation')=='review':
                            targets={n['id'] for n in context}
                            revised={r['source'] for r in output.get('proposal',{}).get('relations',[]) if r.get('type')=='UPDATES' and r.get('target') in targets}
                            if any(n['key'] not in revised for n in output.get('proposal',{}).get('nodes',[])):raise ValueError('重新檢視只可新增以 UPDATES 連向既有觀點的修訂；未需修訂請回傳空提案')
                    except ValueError as error:
                        store.reject(job,article,output.get('proposal'),error,output.get('usage',{}))
                        if attempt:raise
                        job['repair']={'error':str(error),'proposal':output.get('proposal')}
                        if not store.reserve_call(job,revision):return
                        continue
                    store.stage(job,'publishing',revision)
                    if not store.publish(job,article,output.get('proposal'),context,output.get('usage',{})): return
                    job.pop('repair',None)
                    break
                # Yield only after an entire tree has committed its coverage. Splitting
                # earlier would replay already published segments on the next turn.
                if covered:
                    completed_groups+=1
                    if max_groups is not None and completed_groups>=max_groups:
                        with store.connection() as db:
                            changed=db.execute("UPDATE jobs SET status=CASE WHEN done>=json_array_length(payload,'$.revisions') THEN 'completed' ELSE 'queued' END,updated_at=? WHERE id=? AND status='running'",(now(),job['id'])).rowcount
                        if changed:self.wake.set()
                        return
            with store.connection() as db: db.execute("UPDATE jobs SET status='completed',updated_at=? WHERE id=? AND status='running'",(now(),job['id']))
            if store.config().get('catch_up'):self.wake.set()
            log.info('wiki_job completed instrument=%s job=%s',store.instrument,job['id'])
        except Exception as error:
            with self.lock:
                with store.connection() as db: failed=db.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=? AND status='running'",(str(error)[:600],now(),job['id'])).rowcount
                if failed:
                    cfg=store.config();cfg['enabled']=False;cfg['catch_up']=False;store.configure(cfg)
            log.warning('wiki_job failed instrument=%s job=%s error_type=%s',store.instrument,job['id'],type(error).__name__)
        finally: self.active=None

    def tick(self,max_groups=None):
        for store in self.stores():
            if self.stop.is_set(): break
            self.refresh(store);self.process(store,max_groups=max_groups)

    def loop(self):
        while not self.stop.is_set():
            try: self.tick(max_groups=1)
            except Exception: log.exception('Wiki worker cycle failed')
            self.wake.wait(60);self.wake.clear()

    def close(self):
        self.stop.set();self.wake.set()
        if self.active:
            try: self.bridge_request('/wiki/cancel',{'job_id':self.active[1]},timeout=2)
            except RuntimeError: pass
