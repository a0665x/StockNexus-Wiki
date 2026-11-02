"""Source-independent article normalization and evidence-based relation rules."""
import datetime as dt
import bisect
import copy
import functools
import json
import email.utils
import hashlib
import html
import re
import urllib.parse

SCHEMA_VERSION = '2.0'
TICKER = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.\-^]{0,19}$')
ENTITY_ALIASES = {
    'TSLA': ('Tesla', '特斯拉'), 'NVDA': ('NVIDIA', '輝達', '英伟达', '英偉達'),
    'AAPL': ('Apple', '蘋果', '苹果'), 'MSFT': ('Microsoft', '微軟', '微软'),
    'GOOGL': ('Google', 'Alphabet', '谷歌'), 'AMZN': ('Amazon', '亞馬遜', '亚马逊'),
    'META': ('Meta Platforms', 'Facebook', '臉書'), 'AMD': ('Advanced Micro Devices', '超微'),
    'TSM': ('TSMC', '台積電', '台积电', '2330.TW'), 'ASML': ('艾司摩爾', '艾司摩尔'),
    'NFLX': ('Netflix', '網飛'), 'BYD': ('比亞迪', '比亚迪'),
}
TOPICS = {
    'earnings': ('財報', '财报', 'earnings', 'revenue', '營收', '营收'),
    'ev': ('電動車', '电动车', 'electric vehicle', 'EV', 'autonomous', '自動駕駛', '自动驾驶'),
    'ai': ('人工智慧', '人工智能', 'AI', 'large language model', '大模型'),
    'chips': ('semiconductor', '半導體', '半导体', 'chip', 'GPU', '晶片', '芯片'),
    'energy': ('電力', '电力', 'energy', '能源', '電網', '电网'),
    'rates': ('interest rate', '利率', '降息', '升息', 'Federal Reserve', '聯準會'),
}
TOPIC_LABELS = {'earnings': '財報／營收', 'ev': '電動車／自駕', 'ai': '人工智慧', 'chips': '半導體', 'energy': '能源', 'rates': '利率'}

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))).strip()

def timestamp(value):
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value) if ',' in value else dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, TypeError, OverflowError, AttributeError):
        return None

def canonical_url(value):
    try:
        p = urllib.parse.urlsplit(value)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
            return None
        pairs = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid', 'guccounter')]
        return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), p.path or '/', urllib.parse.urlencode(sorted(pairs)), ''))
    except (ValueError, TypeError):
        return None

def article(provider, title, url, published, publisher='', summary='', symbols=None):
    title, url = clean(title), canonical_url(url)
    if not title or not url:
        return None
    return {'id': hashlib.sha256(url.encode()).hexdigest()[:24], 'title': title[:2000], 'summary': clean(summary)[:12000],
            'url': url, 'published_at': timestamp(published), 'source': {'provider': provider, 'publisher': clean(publisher)},
            'symbols': sorted({s.upper() for s in (symbols or []) if isinstance(s, str) and TICKER.fullmatch(s)}),
            'language': None, 'fetched_at': dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')}

def mention(text, alias):
    # ASCII aliases need word boundaries; Chinese names need literal matching.
    pattern = re.escape(alias)
    if alias.isascii():
        pattern = r'(?<![A-Za-z0-9_])' + pattern + r'(?![A-Za-z0-9_])'
    match = re.search(pattern, text, re.I)
    return match.group(0) if match else None

def _enrich(raw):
    result = dict(raw)
    entities = {}
    for symbol in raw.get('symbols', []):
        canonical = 'TSM' if symbol == '2330.TW' else symbol
        entities[canonical] = {'id': canonical, 'label': canonical, 'method': 'provider_ticker', 'evidence': symbol}
    for symbol, aliases in ENTITY_ALIASES.items():
        if symbol in entities:
            continue
        for field in ('title', 'summary'):
            hit = next((m for alias in (symbol, *aliases) if (m := mention(raw.get(field, ''), alias))), None)
            if hit:
                entities[symbol] = {'id': symbol, 'label': aliases[0] if aliases else symbol,
                                    'method': 'text_alias', 'field': field, 'evidence': hit}
                break
    topics = []
    text = raw['title'] + ' ' + raw.get('summary', '')
    for topic, aliases in TOPICS.items():
        hits = [m for alias in aliases if (m := mention(text, alias))]
        if hits:
            topics.append({'id': topic, 'label': TOPIC_LABELS[topic], 'evidence': hits})
    result.update(entities=list(entities.values()), topics=topics, analysis_version='rules-v1')
    return result

@functools.lru_cache(maxsize=8192)
def _enrichment(title, summary, symbols):
    result=_enrich({'title':title,'summary':summary,'symbols':list(symbols)})
    return {key:result[key] for key in ('entities','topics','analysis_version')}


def enrich(raw):
    # Cache derived features only; provenance and retrieval metadata stay current.
    return {**raw, **copy.deepcopy(_enrichment(raw['title'],raw.get('summary',''),tuple(raw.get('symbols',[]))))}


def deduplicate(rows):
    """Merge identical URLs only; keep publisher and provider provenance."""
    unique = {}
    for raw in rows:
        key = canonical_url(raw['url'])
        if key not in unique:
            unique[key] = {**raw, 'symbols': list(raw.get('symbols', [])), 'origins': list(raw.get('origins', [raw['source']]))}
        else:
            existing = unique[key]
            existing['symbols'] = sorted(set(existing['symbols']) | set(raw.get('symbols', [])))
            for origin in raw.get('origins', [raw['source']]):
                if origin not in existing['origins']:
                    existing['origins'].append(origin)
            if len(raw.get('summary', '')) > len(existing.get('summary', '')):
                existing['summary'] = raw['summary']
    return [enrich(row) for row in sorted(unique.values(), key=lambda a: (a.get('published_at') or '', a['id']), reverse=True)]

def title_tokens(title):
    stop = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'news', 'yahoo', 'finance', 'stock', 'stocks', 'shares', 'will', 'after'}
    tokens = set(re.findall(r'[a-z0-9]{3,}', title.lower())) - stop
    for run in re.findall(r'[\u3400-\u9fff]+', title):
        tokens.update(run[i:i+2] for i in range(len(run)-1))
    return tokens

def build_relations(rows, max_neighbors=None, cross_only=False, relation_settings=None):
    from .relation_settings import settings
    # Repeated cache/source updates must not repeat the same large calculation.
    # Copy cached evidence so callers cannot mutate another graph's rules or scores.
    encoded=json.dumps(rows,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    cfg=json.dumps(settings(relation_settings),sort_keys=True)
    return copy.deepcopy(_cached_relations(encoded,max_neighbors,cross_only,cfg))


@functools.lru_cache(maxsize=8)
def _cached_relations(encoded,max_neighbors,cross_only,cfg):
    return _build_relations(json.loads(encoded),max_neighbors,cross_only,json.loads(cfg))


def _build_relations(rows, max_neighbors=None, cross_only=False, relation_settings=None):
    from .relation_settings import settings, DEFAULTS
    cfg=settings(relation_settings)
    if max_neighbors is None: max_neighbors=cfg['cross_neighbors' if cross_only else 'internal_neighbors']
    # All candidate pairs are considered; keep strongest edges first with bounded degree.
    if not rows or max_neighbors == 0 or not any(cfg[k] for k in ('entity','topic','title')):
        return []
    candidates, degree = [], {}
    result, selected = [], set()
    if cfg['adaptive']:
        strict={**cfg,'adaptive':False,'coverage_first':False}
        for key in ('entity_days','topic_days','title_days'):strict[key]=min(cfg[key],DEFAULTS[key])
        for key in ('topic_similarity','title_similarity','title_terms_min'):strict[key]=max(cfg[key],DEFAULTS[key])
        result=_build_relations(rows,max_neighbors,cross_only,strict)
        for edge in result:
            edge['evidence'].append({'adaptive_stage':'strict'})
            selected.add(edge['id'])
            for key in ('source','target'):degree[edge[key]]=degree.get(edge[key],0)+1
    features = [(r, {e['id']: e for e in r['entities']}, {t['id'] for t in r['topics']}, title_tokens(r['title']),
                 dt.datetime.fromisoformat(r['published_at'].replace('Z','+00:00')) if r.get('published_at') else None,
                 {o['provider'] for o in r.get('origins',[r['source']])}) for r in rows]
    def evaluate(i,j,materialize=False):
        a,ae,at,aw,astamp,asources=features[i]
        b,be,bt,bw,bstamp,bsources=features[j]
        if astamp is None or bstamp is None or (cross_only and asources & bsources):return None
        days=abs((astamp-bstamp).total_seconds())/86400
        if days>max(cfg['entity_days'],cfg['topic_days'],cfg['title_days']):return None
        common=ae.keys() & be.keys()
        overlap=set();topics=set();similarity=0
        if cfg['entity'] and common and days<=cfg['entity_days']:
            kind,score='shared_entity',.72+min(.2,.07*len(common))
        else:
            if not ((cfg['topic'] and days<=cfg['topic_days'] and at & bt) or (cfg['title'] and days<=cfg['title_days'])):return None
            overlap=aw & bw
            similarity=len(overlap)/max(1,len(aw)+len(bw)-len(overlap))
            topics=at & bt
            if cfg['topic'] and days<=cfg['topic_days'] and topics and len(overlap)>=2 and similarity>=cfg['topic_similarity']:
                kind,score='shared_topic',.40+min(.25,similarity)
            elif cfg['title'] and days<=cfg['title_days'] and len(overlap)>=cfg['title_terms_min'] and similarity>=cfg['title_similarity']:
                kind,score='similar_title',.45+min(.3,similarity/2)
            else:return None
        base_score=score;factor=2**(-days/cfg['half_life']) if cfg['half_life'] else 1;score*=factor
        if not materialize:return (-round(score,3),round(days,2),a['id']+':'+b['id'],i,j)
        if kind=='shared_entity':evidence=[{'entity':entity,'source':ae[entity],'target':be[entity]} for entity in sorted(common)]
        else:
            item={'title_terms':sorted(overlap)[:12],'title_similarity':round(similarity,3)}
            if kind=='shared_topic':item={'topics':sorted(topics),**item}
            evidence=[item]
        if cfg!=DEFAULTS:evidence.append({'rule_settings':cfg,'base_score':round(base_score,3),'time_factor':round(factor,6)})
        if cfg['adaptive']:evidence.append({'adaptive_stage':'expanded'})
        return {'id':a['id']+':'+b['id'],'source':a['id'],'target':b['id'],'type':kind,'weight':round(score,3),'method':'rules-v1' if cfg==DEFAULTS else 'rules-v2','evidence':evidence,'days_apart':round(days,2)}
    # Date index skips pairs outside every enabled window without dropping candidates.
    dated=sorted((f[4],i) for i,f in enumerate(features) if f[4] is not None)
    isolated=[entry for entry in dated if not degree.get(rows[entry[1]]['id'],0)]
    window=dt.timedelta(days=max(cfg[k+'_days'] for k in ('entity','topic','title') if cfg[k]))
    for i,feature in enumerate(features):
        if feature[4] is None:continue
        index=isolated if cfg['adaptive'] and degree.get(rows[i]['id'],0) else dated
        lo=bisect.bisect_left(index,(feature[4]-window,-1))
        hi=bisect.bisect_right(index,(feature[4]+window,len(features)))
        for _,j in index[lo:hi]:
            if j<=i:continue
            candidate=evaluate(i,j)
            if candidate is not None:candidates.append(candidate)
    ranked=sorted(candidates)
    def take(candidate):
        _,_,identity,i,j=candidate
        if identity in selected or any(degree.get(rows[k]['id'],0)>=max_neighbors for k in (i,j)):return
        edge=evaluate(i,j,True)
        result.append(edge);selected.add(identity)
        for key in ('source','target'):degree[edge[key]]=degree.get(edge[key],0)+1
    if cfg['coverage_first'] or cfg['adaptive']:
        for candidate in ranked:
            if all(degree.get(rows[k]['id'],0)==0 for k in candidate[3:]):take(candidate)
        for candidate in ranked:
            if any(degree.get(rows[k]['id'],0)==0 for k in candidate[3:]):take(candidate)
    if not cfg['adaptive']:
        for candidate in ranked:take(candidate)
    return result
