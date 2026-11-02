"""Search orchestration: reuse covered windows, fetch gaps, commit partial successes."""
import datetime as dt
import threading
from .model import TICKER, deduplicate
from .providers import acquire
from .storage import Store, dates
from .regions import validate_region,edition
from .relation_settings import settings as relation_settings

_LOCKS = [threading.Lock() for _ in range(32)]

def normalize_request(body, today=None):
    if not isinstance(body, dict):
        raise ValueError('搜尋內容必須是 JSON object')
    today = today or dt.datetime.now(dt.timezone.utc).date()
    query, ticker = str(body.get('query', '')).strip(), str(body.get('ticker', '')).strip().upper()
    if len(query) > 200 or len(ticker) > 20:
        raise ValueError('搜尋文字太長')
    if not query:
        query = ticker
    sources = body.get('sources', [])
    if not isinstance(sources, list) or not sources or any(not isinstance(s, str) or s not in ('google','yahoo','massive') for s in sources) or len(sources) > 3 or len(set(sources)) != len(sources):
        raise ValueError('請選擇至少一個有效來源')
    if any(s in ('google', 'yahoo') for s in sources) and not query:
        raise ValueError('Google / Yahoo 需要搜尋關鍵字')
    if ticker and not TICKER.fullmatch(ticker):
        raise ValueError('股票代碼只能包含英數字、句點、連字號或 ^；請勿在代碼欄填入句子')
    if sources == ['massive'] and not ticker:
        raise ValueError('請在股票代碼欄填寫 Massive 要查詢的代碼')
    start = dt.date.fromisoformat(body.get('start') or (today - dt.timedelta(days=6)).isoformat())
    last = dt.date.fromisoformat(body.get('end') or today.isoformat())
    if start > last or last > today or (last - start).days > 365:
        raise ValueError('日期需為過去至今天，且一次不超過 366 天')
    if not isinstance(body.get('force_refresh', False), bool):
        raise ValueError('force_refresh 必須是布林值')
    return {'relation_settings':relation_settings(body.get('relation_settings')),'rss_region':validate_region(body.get('rss_region')),'query': query, 'ticker': ticker, 'sources': sources, 'start': start.isoformat(),
            'end': (last + dt.timedelta(days=1)).isoformat(), 'display_end': last.isoformat(),
            'force_refresh': body.get('force_refresh', False)}

def query_key(provider, term, rss_region=None):
    # Include adapter/locale version so changing retrieval semantics invalidates coverage.
    validate_region(rss_region)
    if provider!='massive' and rss_region is not None and not (provider=='google' and rss_region=='TW'):
        selected=edition(provider,rss_region)
        return f"rss-v4:{rss_region}:{selected['language']}:"+term.strip()
    return ('rss-v2:zh-TW:' if provider == 'google' else 'rss-v3:en-US:' if provider == 'yahoo' else 'massive-v2:') + (term.strip() if provider in ('google', 'yahoo') else term.upper())

def search_source(source, query, ticker, key, start=None, end=None, store=None, force_refresh=False, progress=lambda _: None, rss_region=None):
    store = store or Store()
    today = dt.datetime.now(dt.timezone.utc).date()
    start = start or (today - dt.timedelta(days=6)).isoformat()
    end = end or (today + dt.timedelta(days=1)).isoformat()
    term = ticker if source == 'massive' else query
    cache_key = query_key(source, term, rss_region)
    # Avoid duplicate concurrent fills for the same source/query, including overlapping dates.
    lock = _LOCKS[hash((str(store.path), source, cache_key)) % len(_LOCKS)]
    progress('檢查本地 DB／等待同查詢補抓')
    with lock:
        existing = store.read(source, cache_key, start, end)
        fresh, gaps = store.coverage(source, cache_key, start, end)
        if force_refresh:
            gaps = [(start, end)]
        progress(f'本地 {len(existing)} 篇；需更新 {len(gaps)} 個日期區間')
        error = code = None
        warnings, requests = [], 0
        retry = store.cooldown(source) if gaps else 0
        if retry:
            error, code = f'來源仍在限流等待期，約 {retry} 秒後重試；先顯示本地資料', 'rate_limit'
        elif gaps:
            old_ids = {a['id'] for a in existing}
            def report(message):
                if isinstance(message, dict):
                    ids = set(message.pop('article_ids', []))
                    message.update(cached=len(old_ids), new=len(ids - old_ids), total=len(old_ids | ids))
                progress(message)
            batch = acquire(source, term, key, gaps, report, **({'rss_region':rss_region} if rss_region is not None else {}))
            # Persist good pages even if a later page failed; only known windows become covered.
            store.save(source, cache_key, batch.rows, batch.windows)
            error, code, retry, warnings, requests = batch.error, batch.error_code, batch.retry_after, batch.warnings, batch.requests
            store.record_attempt(source, cache_key, start, end, code, retry)
        rows = deduplicate(store.read(source, cache_key, start, end))
        coverage, remaining = store.coverage(source, cache_key, start, end)
        complete_days = sum(c['kind'] == 'complete' for c in coverage)
        snapshot_days = sum(c['kind'] == 'snapshot' for c in coverage)
        if source != 'massive':
            warnings.insert(0, 'RSS 是來源索引快照，不保證該日期區間全部新聞已收錄')
        return {'source': source, 'rss_region':edition(source,rss_region)['country'] if source!='massive' else None,'articles': rows, 'error': error, 'error_code': code, 'retry_after': retry,
                'warnings': warnings, 'cache': {'existing_articles': len(existing), 'returned_articles': len(rows),
                    'new_articles': len({r['id'] for r in rows} - {r['id'] for r in existing}),
                    'network_requests': requests, 'reused': not gaps, 'complete_days': complete_days,
                    'snapshot_days': snapshot_days, 'requested_days': len(list(dates(start, end))),
                    'missing_ranges': [{'start': a, 'end_exclusive': b} for a, b in remaining],
                    'refresh_failed': bool(error), 'checked_at': max((c['checked_at'] for c in coverage), default=None)}}
