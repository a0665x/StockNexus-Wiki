#!/usr/bin/env python3
"""Read-only Wiki preflight. Legacy omissions are not corrupt source evidence."""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from news_atlas.wiki.store import capture, instrument


def audit(path, ident):
    instrument(ident)
    report={'instrument':ident,'schema':None,'integrity':None,'counts':{},'errors':{},'examples':{},'legacy':{}}
    errors=Counter();legacy=Counter()
    def fail(code,key):
        errors[code]+=1
        examples=report['examples'].setdefault(code,[])
        if len(examples)<3:examples.append(str(key))
    def read(row):
        try:
            value=json.loads(row['payload'])
            if not isinstance(value,dict):raise ValueError()
            return value
        except (ValueError,TypeError):fail('invalid_json',row['id']);return {}
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row;db.execute('BEGIN')
        report['schema']=db.execute('PRAGMA user_version').fetchone()[0]
        report['integrity']=db.execute('PRAGMA quick_check').fetchone()[0]
        if report['schema']>1:fail('future_schema',report['schema'])
        if report['integrity']!='ok':fail('sqlite_integrity',report['integrity'])
        if errors:
            report['errors']=dict(errors);report['ready']=False;return report
        row=db.execute("SELECT value FROM metadata WHERE key='instrument'").fetchone()
        if not row or json.loads(row[0])!=ident:fail('stock_identity',ident)
        versions={r[0] for r in db.execute('SELECT version FROM versions')}
        arts={};nodes={}
        for row in db.execute('SELECT * FROM articles'):
            a=read(row);arts[row['id']]=a
            try:
                expected=capture({**a,'source':{'provider':a.get('provider')}})
                if row['id']!=expected['revision_id'] or any(a.get(k)!=expected[k] for k in ('revision_id','content_hash')):fail('article_hash',row['id'])
                if row['source_id']!=a['provider']+':'+a['id']:fail('article_source_id',row['id'])
            except (ValueError,KeyError,TypeError):fail('article_format',row['id'])
        def citations(values,key):
            if not isinstance(values,list):fail('citations_format',key);return
            for c in values:
                if not isinstance(c,dict):fail('citation_format',key);continue
                a=arts.get(c.get('article_revision_id'));field=c.get('field');start=c.get('start');end=c.get('end')
                if not a:fail('missing_citation',key);continue
                text=a.get(field) if field in ('title','summary') else None
                if not isinstance(text,str) or type(start)!=int or type(end)!=int or not 0<=start<end<=len(text) or text[start:end]!=c.get('quote') or a.get('content_hash')!=c.get('content_hash'):fail('citation_span_hash',key)
        for row in db.execute('SELECT * FROM nodes'):
            n=read(row);nodes[row['id']]=n
            if n.get('id')!=row['id'] or n.get('kind')!=row['kind']:fail('node_identity',row['id'])
            if n.get('version')!=row['created_version'] or row['created_version'] not in versions:fail('node_version',row['id'])
            if not isinstance(n.get('scope'),str) or not n['scope']:fail('node_scope',row['id'])
            if row['kind']=='ArticleRevision':
                if row['id'] not in arts:fail('source_node_missing_article',row['id'])
            else:
                if row['kind'] not in ('Claim','Event','Thesis'):fail('node_kind',row['id'])
                if not n.get('citations'):fail('node_no_citations',row['id'])
                for f in ('opinion_metadata','translations'):
                    if not n.get(f):legacy['missing_'+f]+=1
            citations(n.get('citations',[]),row['id'])
        edge_count=0
        for row in db.execute('SELECT * FROM edges'):
            edge_count+=1;e=read(row)
            if row['source'] not in nodes or row['target'] not in nodes:fail('dangling_edge',row['id'])
            for side in ('source','target'):
                endpoint=e.get(side,{})
                if not isinstance(endpoint,dict) or endpoint.get('stable_id')!=row[side]:fail('edge_endpoint',row['id'])
            if row['created_version'] not in versions:fail('edge_version',row['id'])
            if e.get('instrument_id')!=ident:fail('edge_stock',row['id'])
            citations(e.get('evidence_refs',[]),row['id'])
        for row in db.execute('SELECT * FROM extractions'):
            if row['revision'] not in arts:fail('extraction_source',row['revision'])
            if row['version'] not in versions:fail('extraction_version',row['revision'])
        report['counts']={'articles':len(arts),'nodes':len(nodes),'edges':edge_count,'versions':len(versions)}
        report['errors']=dict(errors);report['legacy']=dict(legacy);report['ready']=not errors
        report['limitations']=['Structural/reference integrity only; not a factual review.','Legacy omissions remain explicit; no invented metadata or paid calls.']
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=Path('data'));parser.add_argument('--instrument',required=True)
    args=parser.parse_args();ident=instrument(args.instrument)
    try:result=audit(args.data_root/'llm_wiki'/ident.split(':')[1]/'wiki.sqlite3',ident)
    except (sqlite3.Error,ValueError,KeyError) as e:
        result={'instrument':ident,'ready':False,'error':str(e)}
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['ready'] else 1

if __name__=='__main__':raise SystemExit(main())
