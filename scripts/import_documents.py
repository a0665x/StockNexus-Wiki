"""Import JSONL exported by an independent agent into a local document graph."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from news_atlas.documents import import_records
from scripts.storage_paths import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', required=True, help='Knowledge base ID, e.g. my_research')
    parser.add_argument('--source', required=True, help='Source ID, e.g. manuals')
    parser.add_argument('--input', required=True, type=Path, help='UTF-8 JSONL export')
    parser.add_argument('--data-dir', type=Path, help='The data directory used by the web server')
    parser.add_argument('--dry-run', action='store_true', help='Preview only. Remove this flag to write the same import.')
    args = parser.parse_args()
    try:
        root = args.data_dir or (Path(os.environ['NEWS_ATLAS_DB']).parent if os.getenv('NEWS_ATLAS_DB') else None)
        root = root or load(ROOT) or os.getenv('ATLAS_DATA_DIR') or ROOT/'data'
        result = import_records(root,args.collection,args.source,args.input,args.dry_run)
    except (OSError,ValueError,sqlite3.Error,RuntimeError) as exc:
        parser.exit(1, str(exc)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
