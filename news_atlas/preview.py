"""Bounded view-only relation work. Never persisted as a complete graph cache."""
import contextlib
import itertools
import queue
import threading
import time
from . import api
from .model import _build_relations, deduplicate
from .relation_settings import settings, DEFAULTS


def validate(body, store):
    groups = body.get('source_graphs')
    if not isinstance(groups, dict) or sum(len(g.get('articles', [])) for g in groups.values() if isinstance(g, dict)) > 7200:
        raise ValueError('視圖最多 2400 個節點（每個來源各一份）')
    # Reuse the public build endpoint's complete article/settings validation.
    rows = api.dispatch('/api/graph/build', body, store, lambda rows, channels, relation_settings: rows)
    if len({r['id'] for r in rows}) > 2400:
        raise ValueError('視圖最多 2400 個節點')
    stage = body.get('stage', 'complete')
    if stage not in ('strict', 'complete'):
        raise ValueError('無效計算階段')
    return {p: deduplicate([r for r in rows if r['source']['provider'] == p]) for p in groups}, settings(body.get('relation_settings')), stage


def stream(groups, cfg, stage, cache_path=None, include_cross=True):
    events = queue.Queue(maxsize=16)
    stopped = threading.Event()

    def emit(value):
        while not stopped.is_set():
            try:
                events.put(value, timeout=.1)
                return
            except queue.Full:
                pass
        raise InterruptedError()

    def work():
        checked = 0
        last_report = 0
        cache = None
        stack = contextlib.ExitStack()
        try:
            if cache_path is not None:
                from .relation_cache import PairCache
                cache = stack.enter_context(PairCache(cache_path))
            rules = dict(cfg)
            if stage == 'strict' and cfg['adaptive']:
                rules.update(adaptive=False, coverage_first=False)
                for key in ('entity_days', 'topic_days', 'title_days'):
                    rules[key] = min(cfg[key], DEFAULTS[key])
                for key in ('topic_similarity', 'title_similarity', 'title_terms_min'):
                    rules[key] = max(cfg[key], DEFAULTS[key])
            output = {p: {'relations': []} for p in groups}
            cross = {}
            tasks = [(p, rows, False) for p, rows in groups.items()]
            tasks += [(a+'_'+b, deduplicate(groups[a]+groups[b]), True) for a,b in itertools.combinations(groups,2) if include_cross and groups[a] and groups[b]]
            for index, (label, rows, cross_only) in enumerate(tasks):
                def progress(delta, done, total):
                    nonlocal checked, last_report
                    checked += delta
                    if stopped.is_set(): raise InterruptedError()
                    now = time.monotonic()
                    if done not in (0, total) and now - last_report < .1: return
                    last_report = now
                    emit({'type':'progress','stage':stage,'group':label,'pairs_checked':checked,
                          'pairs_computed':cache.computed if cache else checked,'pairs_reused':cache.hits if cache else 0,
                          'nodes_checked':done,'nodes_total':total,'task':index+1,'tasks':len(tasks)})
                result = _build_relations(rows, cross_only=cross_only, relation_settings=rules, progress=progress, pair_cache=cache)
                if cache: cache.flush()
                if cross_only:
                    for edge in result:
                        cross[tuple(sorted((edge['source'],edge['target'])))] = {**edge, 'cross_sources':label.split('_')}
                else:
                    output[label] = {'relations':result}
            emit({'type':'result','stage':stage,'pairs_checked':checked,'source_graphs':output,
                  'pairs_computed':cache.computed if cache else checked,'pairs_reused':cache.hits if cache else 0,
                  'cross_relations':list(cross.values()),'relation_settings':cfg,'scope':'view'})
        except InterruptedError:
            pass
        except Exception:
            emit({'type':'error','message':'視圖關聯計算失敗；可重試。'})
        finally:
            try:
                stack.close()
            except Exception:
                if not stopped.is_set(): emit({'type':'error','message':'關聯快取保存失敗；可重試。'})
            if not stopped.is_set():
                emit({'type':'done'})

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    try:
        while True:
            try:
                event = events.get(timeout=1)
            except queue.Empty:
                event = {'type':'heartbeat'}
            yield event
            if event['type'] == 'done':
                break
    finally:
        stopped.set()
