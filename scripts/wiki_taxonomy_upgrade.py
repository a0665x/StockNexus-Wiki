#!/usr/bin/env python3
"""Append quality terms through the public API; no reclassification or history rewrite.
Dry-run by default. Deploy compatible-assignment support before using --apply.
"""
import argparse
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from news_atlas.wiki.research import quality_terms
from news_atlas.wiki.store import instrument


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8765')
    parser.add_argument('--instrument',required=True,action='append')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    for stock in dict.fromkeys(map(instrument,args.instrument)):
        endpoint=args.url.rstrip('/')+'/api/wiki/research/taxonomy'
        with urllib.request.urlopen(endpoint+'?'+urllib.parse.urlencode({'instrument':stock}),timeout=60) as r:old=json.load(r)
        ids={t['id'] for t in old['terms']};missing=[t for t in quality_terms() if t['id'] not in ids]
        report={'instrument':stock,'previous_revision':old['revision_id'],'added':[t['id'] for t in missing],'status':'preview' if missing else 'unchanged'}
        if args.apply and missing:
            body={'instrument':stock,'expected_revision':old['revision_id'],'terms':old['terms']+missing}
            request=urllib.request.Request(endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':args.url.rstrip('/')},method='POST')
            with urllib.request.urlopen(request,timeout=60) as r:new=json.load(r)
            report.update(status='updated',revision=new['revision_id'])
        print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
