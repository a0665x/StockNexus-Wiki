"""Validated, reproducible edge definitions; defaults preserve rules-v1 exactly."""
import math

DEFAULTS = dict(entity=True, topic=True, title=True, entity_days=30, topic_days=7,
                title_days=3, topic_similarity=.18, title_similarity=.5,
                internal_neighbors=6, cross_neighbors=2, half_life=0, title_terms_min=4, coverage_first=False, adaptive=False)
LIMITS = dict(entity_days=(1,366,True), topic_days=(1,366,True), title_days=(1,366,True),
              topic_similarity=(0,1,False), title_similarity=(0,1,False),
              internal_neighbors=(0,6,True), cross_neighbors=(0,2,True), half_life=(0,366,True), title_terms_min=(2,6,True))

GENERAL = {**DEFAULTS, 'entity_days':180, 'topic_days':60, 'title_days':30, 'topic_similarity':.10, 'title_similarity':.25, 'title_terms_min':3, 'coverage_first':True}

UNIFIED = {**GENERAL, 'adaptive':True}

def settings(value=None):
    if value is None: value={}
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):
        raise ValueError('無效 relation_settings 欄位')
    result={**DEFAULTS,**value}
    for key in ('entity','topic','title','coverage_first','adaptive'):
        if not isinstance(result[key],bool): raise ValueError('無效 relation_settings.'+key)
    for key,(low,high,integer) in LIMITS.items():
        v=result[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high or (integer and int(v)!=v):
            raise ValueError('無效 relation_settings.'+key)
    return result
