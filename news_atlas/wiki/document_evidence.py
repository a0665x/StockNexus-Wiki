"""Pinned passages offered to a stock's incremental L1 compiler."""
import contextlib
import itertools
from functools import lru_cache
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlencode

from ..documents import DB_NAME, folder, has_bindings, records_schema
from .store import digest, encode

PART_SIZE = 4000

# The original of an imported claim can be an older, explicitly cited revision.
# Only selected sources contribute originals. Never use a claim as primary text.
ORIGINALS = """
WITH bound AS (SELECT source,bound_at FROM wiki_bindings WHERE instrument=?),
selected(source,id,revision) AS (
    SELECT c.source,c.id,c.revision FROM current_nodes c JOIN bound USING(source)
    UNION
    SELECT coalesce(json_extract(l.value,'$.source'),c.source),json_extract(l.value,'$.id'),
           json_extract(l.value,'$.revision')
    FROM current_nodes c JOIN bound USING(source), json_each(c.body,'$.links') l
    WHERE json_extract(c.body,'$.kind')='claim' AND json_extract(l.value,'$.type')='cites'
)
SELECT v.source,v.id,v.revision,v.body,t.imported_at,b.bound_at
FROM selected JOIN versions v USING(source,id,revision) JOIN bound b USING(source)
LEFT JOIN import_times t USING(source,id,revision)
WHERE json_extract(v.body,'$.kind') IN ('section','document','note')
  AND length(trim(json_extract(v.body,'$.text')))>0
ORDER BY v.source,v.id,v.revision
"""


def snapshot(root, instrument):
    rows, sources = [], []
    for path in sorted((Path(root)/'graph').glob('*/'+DB_NAME)):
        collection = path.parent.name
        if not records_schema.SLUG.fullmatch(collection) or path.parent.is_symlink() or path.is_symlink():
            continue
        path = folder(root,collection)/DB_NAME
        signatures=[]
        for candidate in (path,Path(str(path)+'-wal')):
            try:
                st=candidate.stat()
                signatures.append((st.st_ino,st.st_mtime_ns,st.st_size))
            except FileNotFoundError:
                signatures.append(None)
        parts,bindings=_source_snapshot(path,collection,instrument,tuple(signatures))
        rows.extend(parts)
        sources.extend(bindings)
    return rows,sources


@lru_cache(maxsize=8)
def _source_snapshot(path,collection,instrument,signature):
    # Both SQLite files participate in the cache key, including for an empty binding.
    rows=[]
    with contextlib.closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        if not has_bindings(db):
            return (),()
        sources=[dict(collection=collection,source=source,records=count) for source,count in db.execute(
            'SELECT b.source,count(DISTINCT v.id) FROM wiki_bindings b JOIN versions v USING(source) '
            'WHERE b.instrument=? GROUP BY b.source',(instrument,))]
        if not sources:
            return (),()
        for source,ident,rev,body,imported,bound in db.execute(ORIGINALS,(instrument,)):
            record = json.loads(body)
            url = '/documents?'+urlencode(dict(collection=collection,source=source,id=ident,revision=rev))
            stable = digest([collection,source,ident])
            text = record['text']
            for offset in range(0,len(text),PART_SIZE):
                segment = text[offset:offset+PART_SIZE]
                if not segment.strip():
                    continue
                fingerprint = digest([collection,source,ident,rev,offset,segment,record['title']])
                doc = dict(collection=collection,source=source,id=ident,revision=rev,offset=offset,
                           kind=record['kind'],locator=record.get('locator',{}),imported_at=imported,
                           available_at=max(imported or bound,bound))
                published = record.get('published_at')
                rows.append(dict(id=stable,provider='document',title=record['title'],summary=segment,
                                 document=doc,url=url,content_hash=fingerprint,revision_id='article-'+fingerprint,
                                 published_at=published+'T00:00:00Z' if published else None))
    return rows,sources


def workload(store, rows, sources, *, details=True):
    """Count logical passages once, regardless of model-sized input chunks."""
    receipts = {}
    if store and rows:
        with store.connection() as db:
            receipts = {r[0]:(r[1],json.loads(r[2])) for r in db.execute(
                'SELECT revision,version,result FROM document_reviews WHERE revision IN (SELECT value FROM json_each(?))',
                (encode([r['revision_id'] for r in rows]),))}
    items = []
    total = done = 0
    for _,parts in itertools.groupby(rows,key=lambda a:a['url']):
        parts = list(parts)
        first = parts[0]
        reviewed = [receipts[a['revision_id']] for a in parts if a['revision_id'] in receipts]
        total+=1
        complete=len(reviewed)==len(parts)
        done+=complete
        if not details:
            continue
        outcomes = sorted({outcome for _,result in reviewed for outcome in result['outcomes']})
        items.append(dict(collection=first['document']['collection'],title=first['title'],url=first['url'],revision=first['document']['revision'],
                            source=first['document']['source'],done=complete,
                            outcomes=outcomes,opinions=sorted({n for _,result in reviewed for n in result['opinions']}),
                            versions=sorted({v for v,_ in reviewed})))
    result=dict(total=total,done=done,pending=total-done,sources=sources)
    if details:
        result['passages']=items
    return result


def groups(rows):
    # Keep revisions and chunks of the same passage in reading order on one lane.
    ordered=sorted(rows,key=lambda a:(a['id'],a['document']['revision'],a['document']['offset']))
    sections=[list(parts) for _,parts in itertools.groupby(ordered,key=lambda a:a['id'])]
    for index,parts in enumerate(sections,1):
        for part,row in enumerate(parts,1):
            yield [row],dict(group=index,groups=len(sections),part=part,parts=len(parts),targets=1,
                             context_articles=1,root_id='doc-'+row['id'],kind='document'),[row]
