#!/usr/bin/env python3
"""Read-only, bounded audit for Temporal Wiki planning. No providers or LLM calls."""
import argparse
import datetime as dt
import importlib.metadata
import json
from pathlib import Path
import sqlite3


def audit(path, sample_size=30):
    path = Path(path).resolve()
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        report = {
            'audited_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'read_only': True, 'llm_calls': 0, 'network_requests': 0,
            'schema_version': db.execute('PRAGMA user_version').fetchone()[0],
            'tables': sorted(tables), 'article_counts': {}, 'samples': {},
        }
        fields = ('published_at', 'fetched_at', 'first_seen_at', 'ingested_at',
                  'available_at', 'revision_id', 'content_hash', 'full_text')
        for provider, count in db.execute('SELECT provider,count(*) FROM articles GROUP BY provider'):
            report['article_counts'][provider] = count
            rows = [json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM articles WHERE provider=? ORDER BY id LIMIT ?',
                (provider, sample_size))]
            report['samples'][provider] = {
                'selection': 'ORDER BY id; bounded sample, not a population estimate',
                'sample_size': len(rows),
                'nonempty_fields': {key: sum(bool(r.get(key)) for r in rows) for key in fields},
                'with_summary': sum(bool(r.get('summary')) for r in rows),
                'max_summary_chars': max((len(r.get('summary') or '') for r in rows), default=0),
                'payload_fields': sorted({key for row in rows for key in row}),
            }
        report['coverage'] = [list(r) for r in db.execute(
            'SELECT provider,kind,count(*) FROM coverage GROUP BY provider,kind')]
        report['attempt_errors'] = [list(r) for r in db.execute(
            'SELECT error_code,count(*) FROM attempts GROUP BY error_code')]
        report['source_query_count'] = db.execute(
            'SELECT count(*) FROM (SELECT DISTINCT provider,query_key FROM memberships)').fetchone()[0]
        if 'daily_prices' in tables:
            report['daily_prices'] = {
                'columns': [r[1] for r in db.execute('PRAGMA table_info(daily_prices)')],
                'by_ticker': [list(r) for r in db.execute(
                    'SELECT ticker,count(*),min(day),max(day) FROM daily_prices GROUP BY ticker')],
            }
        report['sidecars_present'] = {
            suffix: Path(str(path) + suffix).exists()
            for suffix in ('.prices.sqlite3', '.graphs.sqlite3')
        }
        report['optional_installed_versions'] = {}
        for name in ('jsonschema', 'scikit-learn', 'exchange-calendars'):
            try:
                report['optional_installed_versions'][name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                report['optional_installed_versions'][name] = None
        return report
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path(__file__).resolve().parents[1] / 'data/news-atlas.sqlite3')
    parser.add_argument('--sample-size', type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 100:
        parser.error('sample-size must be between 1 and 100 per provider')
    print(json.dumps(audit(args.db, args.sample_size), ensure_ascii=False, indent=2))
