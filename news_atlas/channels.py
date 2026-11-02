"""Explainable multi-label news channels. Definitions are persisted independently of articles."""
import copy
import functools
import hashlib
import json
import re
from .model import mention

DEFAULT_CHANNELS = [
    {'id':'chip-manufacturing','name':'晶片製造','color':'#80b4ff','keywords':['晶圓','晶圆','製程','制程','半導體製造','半导体制造','先進封裝','先进封装','foundry','wafer','fabrication','semiconductor manufacturing']},
    {'id':'production','name':'生產／供應鏈','color':'#72dfbd','keywords':['生產','生产','量產','量产','產能','产能','供應鏈','供应链','擴廠','扩厂','production','manufacturing','supply chain','factory','capacity']},
    {'id':'financial-reports','name':'財務報告','color':'#f4cd84','keywords':['財報','财报','營收','营收','獲利','获利','盈餘','盈余','資本支出','资本支出','earnings','revenue','quarterly results','profit','EPS','capex']},
    {'id':'stock-prices','name':'股價／交易','color':'#c59cfc','keywords':['股價','股价','漲幅','涨幅','跌幅','目標價','目标价','stock price','share price','shares','stocks','stock','trading','股票','股市','price target','rally','selloff']},
    {'id':'products','name':'產品／技術','color':'#f69fb4','keywords':['新品','新款','發布','发布','產品','产品','研發','研发','技術','技术','launch','launches','technology','product','research','AI model']},
    {'id':'policy','name':'政策／法規','color':'#92d7ed','keywords':['政策','法規','法规','監管','监管','關稅','关税','出口管制','regulation','regulatory','tariff','policy','export control']},
]
for _channel in DEFAULT_CHANNELS:
    _channel.update(match='any', builtin=True)
OTHER = {'id':'other','name':'其他／未分類','color':'#98a9ba','keywords':[],'match':'any','builtin':True}

def definitions(custom=()):
    return [dict(c) for c in DEFAULT_CHANNELS] + [dict(c) for c in custom] + [dict(OTHER)]

def version(channels):
    return hashlib.sha256(json.dumps(channels, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

def validate_custom(body):
    if not isinstance(body, dict):
        raise ValueError('Channel 格式錯誤')
    name = body.get('name')
    terms = body.get('keywords')
    if not isinstance(name,str) or not 1 <= len(name.strip()) <= 40:
        raise ValueError('分類名稱需為 1–40 字')
    if not isinstance(terms,list) or not 1 <= len(terms) <= 30 or any(not isinstance(t,str) or not 1 <= len(t.strip()) <= 60 for t in terms):
        raise ValueError('請提供 1–30 個關鍵字，每個最多 60 字')
    mode = body.get('match','any')
    if mode not in ('any','all'):
        raise ValueError('分類規則需為 any 或 all')
    color = body.get('color','#9dd6c4')
    if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):
        raise ValueError('分類顏色格式錯誤')
    return {'name':name.strip(),'keywords':list(dict.fromkeys(t.strip() for t in terms)),'match':mode,'color':color,'builtin':False}

def _classify(article, channels):
    hits = []
    for order, channel in enumerate(channels):
        if channel['id'] == 'other':
            continue
        evidence, matched = [], set()
        for term in channel['keywords']:
            for field in ('title','summary'):
                text = article.get(field) or ''
                match = mention(text, term)
                if match:
                    evidence.append({'field':field,'term':term,'match':match})
                    matched.add(term)
                    break  # Avoid counting a title echoed by RSS summary twice.
        if not matched or (channel.get('match')=='all' and len(matched)!=len(channel['keywords'])):
            continue
        score = sum(3 if e['field']=='title' else 1 for e in evidence)
        hits.append({'id':channel['id'],'name':channel['name'],'score':score,'method':'channel_keywords_v1','evidence':evidence,'_order':order})
    hits.sort(key=lambda h:(-h['score'],h['_order']))
    for hit in hits:
        hit.pop('_order')
    if not hits:
        hits = [{'id':'other','name':OTHER['name'],'score':0,'method':'unclassified','evidence':[]}]
    return {'channels':hits,'primary_channel':hits[0]['id'],'channel_version':version(channels)}

@functools.lru_cache(maxsize=8192)
def _classification(title, summary, encoded):
    return _classify({'title':title,'summary':summary},json.loads(encoded))


def classify(article, channels):
    encoded=json.dumps(channels,sort_keys=True,ensure_ascii=False)
    return copy.deepcopy(_classification(article.get('title') or '',article.get('summary') or '',encoded))


def annotate(rows, channels):
    encoded=json.dumps(channels,sort_keys=True,ensure_ascii=False)
    return [{**r, **copy.deepcopy(_classification(r.get('title') or '',r.get('summary') or '',encoded))} for r in rows]
