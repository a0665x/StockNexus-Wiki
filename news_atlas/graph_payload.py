"""Complete News graph builder shared by HTTP and Wiki root coverage."""
import itertools,time,json,logging
from .model import SCHEMA_VERSION,deduplicate,build_relations
from .channels import definitions,annotate,version as channel_version
cache_logger=logging.getLogger('news_atlas.graph_cache')

def graph_payload(rows, channels=None, relation_settings=None, include_relations=True):
    from news_atlas.relation_settings import settings
    cfg=settings(relation_settings)
    stage_times={}
    def relations_for(label, subset, cross_only=False):
        tick=time.perf_counter()
        result=build_relations(subset,cross_only=cross_only,relation_settings=cfg)
        stage_times[label]=round((time.perf_counter()-tick)*1000,2)
        return result
    channels = channels or definitions()
    all_rows = annotate(deduplicate(rows), channels)
    shown = all_rows
    source_graphs = {}
    for provider in ('google', 'yahoo', 'massive'):
        own = annotate(deduplicate([r for r in rows if r['source']['provider'] == provider]), channels)
        subset = own
        source_graphs[provider] = {'articles': subset, 'relations': relations_for(provider,subset) if include_relations else [], 'total_articles': len(own)}
    # Separate cross-source budgets preserve all existing within-source relations.
    cross = {}
    for left, right in itertools.combinations(source_graphs,2):
        a,b = source_graphs[left]['articles'],source_graphs[right]['articles']
        if not include_relations or not a or not b:
            continue
        candidates=deduplicate(a+b)
        for edge in relations_for(left+'_'+right,candidates,True):
            cross[tuple(sorted((edge['source'],edge['target'])))]={**edge,'cross_sources':[left,right]}
    combined=relations_for('combined',shown) if include_relations else []
    if include_relations:
        cache_logger.info('graph_compute_ms %s',json.dumps(stage_times))
    return {'schema_version': SCHEMA_VERSION, 'articles': shown, 'relations': combined,
            'source_graphs': source_graphs, 'cross_relations': list(cross.values()),
            'channel_definitions': channels, 'channel_version': channel_version(channels),
            'total_articles': len(all_rows), 'display_limit': None,
            'relation_settings': cfg, 'relations_pending': not include_relations,
            'relation_note': '規則關聯並非因果；分數為排序用啟發式指標，不是機率。'}
