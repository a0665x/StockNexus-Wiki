#!/usr/bin/env python3
"""One read-only StockNexus context query, using Python's standard library."""
import argparse,json,sys,urllib.parse,urllib.request,urllib.error
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('resource',choices=['catalog','news','related','prices','l1','l2'])
p.add_argument('--base-url',default='http://127.0.0.1:8765')
for name in ('instrument','days','end','query','id','limit','offset'):p.add_argument('--'+name)
a=p.parse_args();params={k:v for k,v in vars(a).items() if k not in ('base_url','resource') and v is not None}
url=a.base_url.rstrip('/')+'/api/context/'+a.resource+'?'+urllib.parse.urlencode(params)
try:
    with urllib.request.urlopen(url,timeout=20) as r:print(json.dumps(json.load(r),ensure_ascii=False,indent=2))
except urllib.error.HTTPError as e:
    print(e.read().decode(),file=sys.stderr);sys.exit(1)
except (OSError,ValueError) as e:
    print(str(e),file=sys.stderr);sys.exit(1)
