"""Bounded source adapters. Half-open UTC dates [start,end)."""
import datetime as dt
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from collections import deque

from .model import TICKER, article
from .regions import edition

MAX_BYTES = 8_000_000

class SourceError(Exception):
    def __init__(self, code, message, retry_after=0):
        super().__init__(message)
        self.code, self.retry_after = code, retry_after

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.has_header('Authorization') and urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            raise SourceError('redirect', '來源驗證轉址被拒絕')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(url, headers=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'NewsAtlas/2.0', **(headers or {})})
    try:
        with urllib.request.build_opener(SafeRedirect).open(req, timeout=15) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise SourceError('too_large', '來源回應過大，請縮小日期範圍')
            return data
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry = exc.headers.get('Retry-After', '60') if exc.headers else '60'
            retry = min(3600, max(1, int(retry))) if retry.isdigit() else 60
            raise SourceError('rate_limit', f'來源限流（429）；約 {retry} 秒後可重試，已取得的資料會保留', retry) from None
        if exc.code in (401, 403):
            raise SourceError('authorization', f'授權／方案或來源存取限制（{exc.code}），請檢查 API key 與資料權限') from None
        raise SourceError('http', f'來源 HTTP {exc.code}，可稍後重試') from None
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
        # Do not echo exception URLs: next-page URLs might carry provider credentials.
        raise SourceError('network', '來源連線失敗或逾時（單次請求上限 15 秒），請稍後重試') from None

@dataclass
class Batch:
    rows: list = field(default_factory=list)
    windows: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    error: str = None
    error_code: str = None
    retry_after: int = 0
    requests: int = 0

class Budget:
    def __init__(self, limit=12, seconds=90):
        self.left = limit
        self.used = 0
        self.deadline = time.monotonic() + seconds

    def get(self, url, headers=None):
        if self.left <= 0 or time.monotonic() >= self.deadline:
            raise SourceError('limit', '本次補抓已達請求／時間上限；已有資料已儲存，未完成區間不會標成完整')
        self.left -= 1
        self.used += 1
        return fetch(url, headers)

def in_range(row, start, end):
    return row and row['published_at'] and start <= row['published_at'] < end

def next_massive_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or (p.hostname != 'api.massive.com' or p.port not in (None, 443) or p.username or p.password) or p.path != '/v2/reference/news':
        raise SourceError('pagination', 'Massive 分頁網址不符合預期，已停止並保留已取得資料')
    params = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if k.lower() != 'apikey']
    return urllib.parse.urlunsplit((p.scheme, 'api.massive.com', p.path, urllib.parse.urlencode(params), ''))

def massive_window(ticker, key, start, end, budget, batch, progress):
    if not TICKER.fullmatch(ticker):
        raise SourceError('input', 'Massive 需要股票代碼，例如 TSLA')
    if not key:
        raise SourceError('missing_key', 'Massive 尚未設定 API key；可填入畫面或設定 MASSIVE_API_KEY')
    url = 'https://api.massive.com/v2/reference/news?' + urllib.parse.urlencode({
        'ticker': ticker.upper(), 'limit': 1000, 'order': 'asc', 'sort': 'published_utc',
        'published_utc.gte': start + 'T00:00:00Z', 'published_utc.lt': end + 'T00:00:00Z'})
    seen = set()
    invalid = 0
    while url:
        if url in seen:
            raise SourceError('pagination', 'Massive 分頁重複，已停止；此區間尚未抓齊')
        seen.add(url)
        progress(f'補抓 {start} 至 {end}（不含結束日）· 第 {len(seen)} 頁')
        try:
            payload = json.loads(budget.get(url, {'Authorization': 'Bearer ' + key}))
        except (json.JSONDecodeError, UnicodeError):
            raise SourceError('format', 'Massive 回應不是有效 JSON') from None
        if isinstance(payload, dict) and payload.get('status') == 'OK' and payload.get('count') == 0 and 'results' not in payload:
            payload['results'] = []
        if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
            code = 'authorization' if isinstance(payload, dict) and payload.get('status') in ('NOT_AUTHORIZED', 'UNAUTHORIZED') else 'format'
            raise SourceError(code, 'Massive 回應缺少新聞結果，請檢查帳號權限或稍後重試')
        if payload.get('status') not in (None, 'OK', 'DELAYED'):
            raise SourceError('provider', 'Massive 回報來源錯誤；區間未標為完整')
        for item in payload['results']:
            if not isinstance(item, dict):
                invalid += 1
                continue
            row = article('massive', item.get('title'), item.get('article_url', ''), item.get('published_utc'),
                          (item.get('publisher') or {}).get('name', ''), item.get('description', ''), item.get('tickers', []))
            if not row or not row['published_at']:
                invalid += 1
            elif in_range(row, start, end):
                batch.rows.append(row)
        progress({'phase': 'fetching', 'message': '讀取分頁', 'requests': budget.used, 'article_ids': list({r['id'] for r in batch.rows})})
        # Ascending pages prove preceding whole days exhausted even if a later page fails.
        if not invalid and payload.get('next_url') and batch.rows:
            frontier = max((r['published_at'][:10] for r in batch.rows if in_range(r, start, end)), default=start)
            if frontier > start:
                batch.windows.append((start, frontier, 'complete'))
        url = next_massive_url(payload['next_url']) if payload.get('next_url') else None
    if invalid:
        batch.warnings.append(f'{invalid} 筆新聞缺少必要欄位，未將此區間標為完整')
    else:
        batch.windows.append((start, end, 'complete'))

def rss_window(provider, query, start, end, budget, batch, progress, rss_region=None, pending=None):
    # Query one extra boundary day, then filter exact UTC publication timestamps locally.
    # Google RSS date operators/indexing have no completeness contract.
    selected=edition(provider,rss_region)
    locale={'hl':selected['language'],'gl':selected['country'],'ceid':selected['ceid']}
    site_filter='('+' OR '.join('site:'+site for site in selected['sites'])+')'
    term=query if provider=='google' else '('+query+') '+site_filter
    before = (dt.date.fromisoformat(end) + dt.timedelta(days=1)).isoformat()
    after = (dt.date.fromisoformat(start) - dt.timedelta(days=1)).isoformat()
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q': f'({term}) after:{after} before:{before}', **locale})
    progress(f'取得 RSS {start} 至 {end}（不含結束日）')
    try:
        root = ET.fromstring(budget.get(url))
    except ET.ParseError:
        raise SourceError('format', 'RSS 回應格式錯誤') from None
    if root.tag != 'rss' or root.find('channel') is None:
        raise SourceError('format', '來源未回傳 RSS channel')
    items = root.findall('./channel/item')
    for item in items:
        source = item.find('source')
        row = article(provider, item.findtext('title'), item.findtext('link', ''), item.findtext('pubDate'),
                      source.text if source is not None else '', item.findtext('description', ''))
        if in_range(row, start, end):
            row['source'].update(via='google_news_rss',country=selected['country'],language=selected['language'])
            if selected['sites']:row['source']['sites']=selected['sites'][:]
            batch.rows.append(row)
    progress({'phase': 'fetching', 'message': '讀取 RSS', 'requests': budget.used, 'article_ids': list({r['id'] for r in batch.rows})})
    if len(items) >= 100:
        days = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days
        if days > 1:
            mid = (dt.date.fromisoformat(start) + dt.timedelta(days=days // 2)).isoformat()
            if pending is not None:
                pending.extend([(start,mid),(mid,end)])
            else:
                rss_window(provider, query, start, mid, budget, batch, progress, rss_region)
                rss_window(provider, query, mid, end, budget, batch, progress, rss_region)
        else:
            batch.warnings.append(f'{start} RSS 可能達筆數上限；保留結果但不標為已覆蓋')
    else:
        batch.windows.append((start, end, 'snapshot'))

def acquire(provider, term, key, gaps, progress=lambda _: None, rss_region=None):
    batch, budget = Batch(), Budget()
    try:
        if provider == 'massive':
            for start, end in gaps:
                massive_window(term, key, start, end, budget, batch, progress)
        else:
            # Visit the entire requested period before spending the budget on dense days.
            # At most twelve initial windows for a 366-day contiguous range.
            pending=deque()
            for start,end in gaps:
                cursor,stop=dt.date.fromisoformat(start),dt.date.fromisoformat(end)
                while cursor<stop:
                    boundary=min(stop,cursor+dt.timedelta(days=31))
                    pending.append((cursor.isoformat(),boundary.isoformat()))
                    cursor=boundary
            while pending:
                start,end=pending.popleft()
                rss_window(provider, term, start, end, budget, batch, progress, rss_region, pending)
    except SourceError as exc:
        batch.error, batch.error_code, batch.retry_after = str(exc), exc.code, exc.retry_after
    except (ValueError, TypeError, AttributeError):
        batch.error, batch.error_code = '來源欄位格式異常，已保留成功處理的資料', 'format'
    batch.requests = budget.used
    return batch
