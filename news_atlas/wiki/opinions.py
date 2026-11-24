"""Cross-batch L1 memory and optional, dated VIX news evidence."""
import datetime as dt
import json
import re

STOP_WORDS = set('a an the in on by to of from as with is are and for at that says reports stock shares news update market company nvidia nvda'.split())
VIX = re.compile(r'(?<![a-z0-9])VIX(?![a-z0-9])|CBOE Volatility Index|芝加哥選擇權交易所波動率指數|美股恐慌指數', re.I)


def keywords(text):
    words = set(re.findall(r'[a-z0-9][a-z0-9-]{2,}', text.lower())) - STOP_WORDS
    for run in re.findall(r'[\u3400-\u9fff]+', text):
        words.update(run[i:i+2] for i in range(len(run)-1))
    return words


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z','+00:00')) if value else None


def vix_sources(db, evidence, frozen_at):
    dates = [timestamp(a['published_at']) for a in evidence if a['published_at']]
    if not dates:
        return []
    window = dt.timedelta(days=7)
    current = {a['revision_id'] for a in evidence}
    matched = []
    # Stock-local archive only. Candidate reports must already exist at the
    # time of at least one item in this segment, including intraday ordering.
    rows = db.execute("""SELECT payload FROM articles WHERE source_id NOT LIKE 'document:%' AND captured_at<=? AND julianday(json_extract(payload,'$.published_at'))
        BETWEEN julianday(?) AND julianday(?) ORDER BY julianday(json_extract(payload,'$.published_at')) DESC,id""",
        (frozen_at,(min(dates)-window).isoformat(), max(dates).isoformat()))
    for row in rows:
        a = json.loads(row[0])
        if a['revision_id'] in current or not VIX.search(a['title']+' '+a['summary']):
            continue
        at = timestamp(a['published_at'])
        if any(at <= end <= at+window for end in dates):
            matched.append(a)
            if len(matched)==2:
                break
    return matched


def same_proposition(a,b):
    # Ancillary labels and translation wording may change without changing the
    # proposition. Preserve meaningful differences in conditions, type or horizon.
    for key in ('kind','title','summary','scope'):
        if a.get(key) != b.get(key):
            return False
    left, right = a.get('opinion_metadata',{}), b.get('opinion_metadata',{})
    return all(left.get(k)==right.get(k) for k in ('claim_type','conditions','horizon'))


def consolidate(db,nodes,edges):
    """Run under the same write lock as publication, including competing workers."""
    revisions = {e['source'] for e in edges if e['type']=='UPDATES'}
    parents = {e['source']:e['target'] for e in edges if e['type']=='EXTENDS'}
    canonical = {}
    kept = []
    for node in nodes:
        if node['id'] not in revisions:
            parent=parents.get(node['id'])
            candidates = db.execute("""SELECT payload FROM nodes WHERE kind=? AND json_extract(payload,'$.title')=?
                AND json_extract(payload,'$.scope')=? AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.target=nodes.id
                AND json_extract(e.payload,'$.relation_type')='UPDATES') AND (? IS NULL OR EXISTS
                (SELECT 1 FROM edges e WHERE e.source=nodes.id AND e.target=? AND json_extract(e.payload,'$.relation_type')='EXTENDS'))
                ORDER BY created_version DESC,id""",(node['kind'],node['title'],node['scope'],parent,parent))
            prior_nodes = (json.loads(row[0]) for row in candidates)
            previous = next((old for old in prior_nodes if same_proposition(node,old)), None)
            if previous is None:
                previous = next((old for old in kept if parents.get(old['id'])==parent and same_proposition(node,old)),None)
            if previous:
                canonical[node['id']] = previous
                continue
        kept.append(node)
    # Reusing a branch adds the new source quotes, without another parent edge.
    # Within this proposal only one copy of an identical edge is saved by SQLite.
    existing_branches={key for key,prior in canonical.items() if key in parents and
                       db.execute('SELECT 1 FROM nodes WHERE id=?',(prior['id'],)).fetchone()}
    edges=[e for e in edges if e['type']!='EXTENDS' or e['source'] not in existing_branches]
    for edge in edges:
        for end in ('source','target'):
            if edge[end] in canonical:
                edge[end] = canonical[edge[end]]['id']
    return kept, [edge for edge in edges if edge['source']!=edge['target']], list(canonical.values())


def validate_lineage(node, decision, candidates, relations):
    """Require a comparison before starting a separate thesis in the model contract."""
    if not isinstance(decision,dict) or set(decision)!={'action','compared_id'}:
        raise ValueError('Invalid lineage decision')
    action, base = decision['action'], decision['compared_id']
    if action not in ('observation','new_topic','update','extend') or not isinstance(base,str):
        raise ValueError('Invalid lineage action or comparison ID')
    if not node.get('opinion_metadata',{}).get('change_reason','').strip():
        raise ValueError('Explain what changed or why the closest prior thesis does not apply')
    prior = {n['id'] for n in candidates if n['kind']==node['kind']}
    parents = [(r.get('type'),r.get('target')) for r in relations if isinstance(r,dict)
               and r.get('source')==node['key'] and r.get('type') in ('EXTENDS','UPDATES')]
    if action in ('update','extend'):
        relation = 'UPDATES' if action=='update' else 'EXTENDS'
        if base not in prior or parents!=[(relation,base)] or (action=='extend' and node['kind']!='Thesis'):
            raise ValueError('Point the lineage relation to one supplied prior opinion of the same kind')
        previous=next(n for n in candidates if n['id']==base)
        if same_proposition(node,previous):
            raise ValueError('The prior proposition is unchanged. Attach fresh corroboration or skip the restatement')
    elif parents:
        raise ValueError('The lineage action must agree with the revision or extension relation')
    elif action=='new_topic':
        if node['kind']!='Thesis' or (prior and base not in prior) or (not prior and base!=''):
            raise ValueError('Compare the new topic with the closest supplied thesis and explain the difference')
    elif node['kind']=='Thesis' or base:
        raise ValueError('A thesis needs a new_topic, update or extend decision')


def node_evidence_and_lineage(db,node,version):
    """Follow one revision in either direction, independent of the canvas budget."""
    ident=node['id']
    links=[]; evidence=[]
    for row in db.execute("""SELECT e.payload,n.id,n.kind,json_extract(n.payload,'$.title') AS title,
            json_extract(n.payload,'$.translations.en.title') AS en,json_extract(n.payload,'$."translations"."zh-Hant".title') AS zh
            FROM edges e JOIN nodes n ON n.id=CASE WHEN e.source=? THEN e.target ELSE e.source END
            WHERE (e.source=? OR e.target=?) AND e.created_version<=? AND n.created_version<=?
            AND json_extract(e.payload,'$.relation_type') IN ('SUPPORTS','UPDATES','EXTENDS')
            ORDER BY e.created_version,e.id""",(ident,ident,ident,version,version)):
        edge=json.loads(row['payload'])
        if edge['relation_type']=='SUPPORTS':
            evidence.append(edge)
        else:
            links.append({'id':row['id'],'title':row['title'],'titles':{'en':row['en'],'zh-Hant':row['zh']},
                          'relation':edge['relation_type'],'parent':edge['source']['stable_id']==ident})
    return {'lineage_links':links,'corroborating_citations':additional_sources({ident:node}, evidence).get(ident,[])}


def additional_sources(nodes, edges):
    # A frozen node retains its original citations. Supporting quotes accumulate
    # on versioned edges and are projected only from the caller's snapshot.
    seen={}
    result={}
    for edge in edges:
        source=edge.get('source',{})
        target=edge.get('target',{}).get('stable_id')
        if edge['relation_type']!='SUPPORTS' or source.get('kind')!='ArticleRevision' or target not in nodes:
            continue
        if target not in seen:
            seen[target]={(c['article_revision_id'],c['field'],c['quote']) for c in nodes[target].get('citations',[])}
        for c in edge.get('evidence_refs',[]):
            key=(c['article_revision_id'],c['field'],c['quote'])
            if key[0]==source['stable_id'] and key not in seen[target]:
                seen[target].add(key)
                result.setdefault(target,[]).append(c)
    return result
