"""Split-adjusted daily-price evidence for an explicit ticker; never news inference."""
import bisect
import datetime as dt
import hashlib
import json
from pathlib import Path
import math
import re
import sqlite3
import threading
import time
import urllib.parse
from zoneinfo import ZoneInfo
from .providers import fetch, SourceError
ET=ZoneInfo('America/New_York')
HORIZONS=(1,3,5,7)
_lock=threading.Lock()

def instant(value):
    if not isinstance(value,str):return None
    try:
        stamp=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if stamp.tzinfo is None:return None
        return stamp.astimezone(ET)
    except ValueError:return None

def measurements(articles,bars):
    days=[b['date'] for b in bars];out={}
    for article in articles:
        stamp=instant(article.get('published_at'))
        item={'published_at':article.get('published_at'),'baseline_date':None,'baseline_close':None,'returns':{str(n):None for n in HORIZONS}}
        if stamp:
            # Before the regular session opens, that day can be a complete session.
            first=stamp.date()+(dt.timedelta(days=1) if stamp.time()>=dt.time(9,30) else dt.timedelta())
            i=bisect.bisect_left(days,first.isoformat())
            if i<len(bars):
                base=bars[i];item.update(baseline_date=base['date'],baseline_close=base['close'])
                for n in HORIZONS:
                    if i+n<len(bars):item['returns'][str(n)]=sum(bars[j]['close']/base['close']-1 for j in range(i+1,i+n+1))/n
        out[article['id']]=item
    return out

def load(store,body,key,now=None):
    ticker=body.get('ticker','')
    if not isinstance(ticker,str) or not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',ticker):raise ValueError('請填入明確的 Massive 股票代碼')
    rows=body.get('articles')
    if not isinstance(rows,list) or len(rows)>100000 or any(not isinstance(r,dict) or not isinstance(r.get('id'),str) or len(r['id'])>100 or (r.get('published_at') is not None and not instant(r['published_at'])) for r in rows):raise ValueError('新聞日期格式錯誤')
    stamps=[instant(r.get('published_at')) for r in rows];stamps=[s for s in stamps if s]
    now=now or dt.datetime.now(dt.timezone.utc)
    cutoff=now.astimezone(ET).date()-dt.timedelta(days=1)
    result={'ticker':ticker,'provider':'massive','market':'US','currency':'USD','adjusted':True,'includes_dividends':False,'method':'mean_forward_close_return_v1','horizons':list(HORIZONS),'as_of':cutoff.isoformat(),'bars':[],'observations':{},'cached':False}
    if not stamps:return {**result,'observations':measurements(rows,[])}
    start=min(s.date() for s in stamps);end=min(max(s.date() for s in stamps)+dt.timedelta(days=32),cutoff)
    if (max(s.date() for s in stamps)-start).days>400:raise ValueError('股價視窗最多涵蓋 400 天新聞')
    if start>end:return {**result,'observations':measurements(rows,[])}
    cache_key=hashlib.sha256(f'{ticker}:{start}:{end}:split-adjusted-ohlc-v2'.encode()).hexdigest()
    with _lock:
        with sqlite3.connect(str(store.path)+'.prices.sqlite3',timeout=15) as db:
            db.execute('CREATE TABLE IF NOT EXISTS series (key TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched REAL NOT NULL)')
            cached=db.execute('SELECT payload,fetched FROM series WHERE key=?',(cache_key,)).fetchone()
            if not cached and hasattr(store,'data_root'):
                legacy=store.data_root/'graph/_unassigned/news-atlas.sqlite3.prices.sqlite3'
                if legacy.exists() and legacy!=Path(str(store.path)+'.prices.sqlite3'):
                    # The key includes the exact ticker/range/method even in older payloads.
                    with sqlite3.connect(legacy.resolve().as_uri()+'?mode=ro',uri=True) as old:
                        cached=old.execute('SELECT payload,fetched FROM series WHERE key=?',(cache_key,)).fetchone()
                    if cached:db.execute('INSERT OR IGNORE INTO series VALUES (?,?,?)',(cache_key,*cached))
            if cached and time.time()-cached[1]<21600:
                payload=json.loads(cached[0]);result.update(bars=payload['bars'],fetched_at=payload['fetched_at'],cached=True)
            else:
                if not key:raise ValueError('需要 Massive API key 才能讀取股價')
                url='https://api.massive.com/v2/aggs/ticker/'+urllib.parse.quote(ticker,safe='')+'/range/1/day/'+str(start)+'/'+str(end)+'?adjusted=true&sort=asc&limit=50000'
                try:raw=json.loads(fetch(url,{'Authorization':'Bearer '+key}))
                except (ValueError,TypeError):raise SourceError('format','股價來源格式錯誤') from None
                if not isinstance(raw,dict):raise SourceError('format','股價來源格式錯誤')
                if raw.get('status') not in ('OK','DELAYED') or raw.get('next_url') or raw.get('adjusted') is False:raise SourceError('incomplete','股價來源未回傳完整調整後資料')
                bars={}
                if not isinstance(raw.get('results',[]),list):raise SourceError('format','股價來源格式錯誤')
                for bar in raw.get('results',[]):
                    if not isinstance(bar,dict):raise SourceError('format','股價來源格式錯誤')
                    close=bar.get('c');stamp=bar.get('t')
                    if isinstance(close,bool) or not isinstance(close,(int,float)) or not math.isfinite(close) or close<=0 or isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp) or not 0<=stamp<=4102444800000:raise SourceError('format','股價資料含無效價格')
                    day=dt.datetime.fromtimestamp(stamp/1000,ET).date()
                    ohlc={name:bar.get(field) for name,field in [('open','o'),('high','h'),('low','l')]}
                    for value in ohlc.values():
                        if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0):raise SourceError('format','Invalid OHLC price')
                    if all(v is not None for v in ohlc.values()) and not ohlc['low']<=min(ohlc['open'],close)<=max(ohlc['open'],close)<=ohlc['high']:raise SourceError('format','Invalid OHLC range')
                    if start<=day<=end:bars[day.isoformat()]={'date':day.isoformat(),'close':close,**ohlc}
                result.update(bars=[bars[k] for k in sorted(bars)],fetched_at=dt.datetime.now(dt.timezone.utc).isoformat())
                db.execute('INSERT OR REPLACE INTO series VALUES (?,?,?)',(cache_key,json.dumps({'ticker':ticker,'bars':result['bars'],'fetched_at':result['fetched_at']}),time.time()))
                db.execute('DELETE FROM series WHERE key NOT IN (SELECT key FROM series ORDER BY fetched DESC LIMIT 64)')
    result['observations']=measurements(rows,result['bars'])
    return result
