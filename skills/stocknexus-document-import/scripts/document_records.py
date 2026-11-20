"""StockNexus document record contract shared by the web importer and the portable skill."""
import datetime as dt
import json
from pathlib import PurePosixPath
import re

SLUG = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}')
NODE = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}')
KINDS = {'folder', 'document', 'section', 'note', 'claim'}
RELATIONS = {'cites', 'supports', 'contradicts', 'updates', 'related'}
FIELDS = {'id', 'kind', 'title', 'parent_id', 'path', 'locator', 'text', 'published_at', 'links', 'layer', 'question'}


def slug(name):
    if not isinstance(name, str) or not SLUG.fullmatch(name):
        raise ValueError('Use 1–64 lowercase letters, numbers, underscores or hyphens for collection/source IDs')
    return name


def string(value, field, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'Invalid {field} (maximum {limit} characters)')
    return value


def node_id(value):
    if not isinstance(value, str) or not NODE.fullmatch(value):
        raise ValueError('Invalid node ID')
    return value


def validate(row, source):
    if not isinstance(row, dict) or set(row) - FIELDS:
        raise ValueError('Expected a record with only documented fields')
    node_id(row.get('id'))
    if row.get('kind') not in KINDS:
        raise ValueError('Invalid kind')
    string(row.get('title'), 'title', 2000)
    if 'text' in row and (not isinstance(row['text'], str) or len(row['text']) > 120000):
        raise ValueError('Invalid text (split long documents into sections)')
    if row.get('parent_id') is not None:
        node_id(row['parent_id'])
    if 'path' in row:
        path = string(row['path'], 'path', 2000)
        if '\\' in path or PurePosixPath(path).is_absolute() or '..' in path.split('/') or re.match(r'^[A-Za-z]+:', path):
            raise ValueError('path must be relative to the original document folder')
    if 'locator' in row:
        loc = row['locator']
        if not isinstance(loc, dict) or not loc or set(loc) - {'page','heading','line'}:
            raise ValueError('Use page, heading or line in locator')
        for key, value in loc.items():
            if key == 'heading':
                string(value, key, 500)
            elif type(value) is not int or value < 1:
                raise ValueError('page/line must be positive integers')
    if row.get('published_at') is not None:
        date = string(row['published_at'], 'published_at', 10)
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
            raise ValueError('Use YYYY-MM-DD or null')
        dt.date.fromisoformat(date)
    links = row.get('links', [])
    if not isinstance(links, list):
        raise ValueError('Expected a links array')
    for link in links:
        if not isinstance(link, dict) or set(link) - {'type','source','id','revision','rationale'} or link.get('type') not in RELATIONS:
            raise ValueError('Invalid link')
        slug(link.get('source',source))
        node_id(link.get('id'))
        if 'revision' in link and (type(link['revision']) is not int or link['revision'] < 1):
            raise ValueError('Invalid citation revision')
        if 'rationale' in link:
            string(link['rationale'], 'link rationale', 2000)
    if row.get('kind') == 'claim':
        if row.get('layer') not in ('L1','L2') or not any(l['type']=='cites' and 'revision' in l for l in links):
            raise ValueError('Claims need a layer and a citation to a specific revision')
        if row['layer']=='L2':
            string(row.get('question'), 'L2 research question', 2000)
    elif 'layer' in row or 'question' in row:
        raise ValueError('Only claims have a Wiki layer or research question')


def read_records(stream, source):
    records = {}
    duplicates = 0
    for index, line in enumerate(stream, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            validate(row, source)
            ident = row['id']
            if ident in records:
                if records[ident] != row:
                    raise ValueError('Conflicting definitions of '+ident)
                duplicates += 1
            records[ident] = row
        except (ValueError, TypeError) as exc:
            raise ValueError(f'Line {index}: {exc}') from exc
    if not records:
        raise ValueError('The JSONL input is empty')
    return records, duplicates
