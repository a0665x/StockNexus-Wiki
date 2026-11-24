#!/usr/bin/env python3
"""Summarize private stage JSONL; never sum overlapping stages into wall time."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics


def summarize(folder,job=None,instrument=None):
    rows=[];bad=0
    for path in Path(folder).glob('*.jsonl*'):
        for line in path.read_text(errors='replace').splitlines():
            try:r=json.loads(line)
            except (ValueError,TypeError):bad+=1;continue
            if not isinstance(r,dict):bad+=1;continue
            if job and r.get('job_id')!=job:continue
            if instrument and r.get('instrument')!=instrument:continue
            rows.append(r)
    rows.sort(key=lambda r:r.get('ts',''))
    groups=defaultdict(list);open_spans={};errors=[];states={}
    for r in rows:
        key=(r.get('process'),r.get('span_id') or r.get('call_id'),r.get('stage'))
        if r.get('event')=='begin':open_spans[key]=r
        if r.get('event') in ('end','error'):
            open_spans.pop(key,None)
            if isinstance(r.get('elapsed_ms'),(int,float)):
                groups[(r.get('process'),r.get('operation',''),r.get('stage'))].append(r['elapsed_ms'])
        if r.get('event')=='error':errors.append({k:r[k] for k in ('ts','job_id','call_id','stage','error_code','error_type','sdk_stage','last_event_ms','deadline','frames') if k in r})
        if r.get('stage')=='job' and r.get('status'):states[r.get('job_id')]=r['status']
    stages=[{'process':p,'operation':op,'stage':s,'count':len(v),'sum_ms':round(sum(v),3),'p50_ms':round(statistics.median(v),3),'max_ms':max(v)} for (p,op,s),v in groups.items()]
    return {'events':len(rows),'malformed_lines':bad,'jobs':states,'stages':sorted(stages,key=lambda x:-x['sum_ms']),
            'errors':errors,'unfinished_spans':list(open_spans.values()),
            'note':'Durations overlap across workers and nested/Python/bridge stages; never sum them as job wall time. An unfinished span may be active, interrupted or missing rotated history. SDK time includes provider queue/network/reasoning/output; these are not separately exposed.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',default=str(Path(__file__).resolve().parents[1]/'data/private/wiki-trace'))
    p.add_argument('--job');p.add_argument('--instrument');p.add_argument('--json',action='store_true')
    a=p.parse_args();result=summarize(a.directory,a.job,a.instrument)
    if a.json:print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print(f"Events: {result['events']} | Errors: {len(result['errors'])} | Unfinished: {len(result['unfinished_spans'])} | Malformed: {result['malformed_lines']}")
        print('process  operation           stage                         count    sum(s)    p50(s)    max(s)')
        for r in result['stages']:print(f"{r['process']:8} {r['operation']:19} {r['stage']:29} {r['count']:5} {r['sum_ms']/1000:9.3f} {r['p50_ms']/1000:9.3f} {r['max_ms']/1000:9.3f}")
        for job,status in result['jobs'].items():print('Job',job,status)
        for r in result['errors'][-10:]:print('Error',json.dumps(r,ensure_ascii=False))
        print(result['note'])
