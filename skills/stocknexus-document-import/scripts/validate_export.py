"""Check a self-contained research document export before handing it to the Web UI."""
import argparse
from pathlib import Path

from document_records import read_records, slug

MAX_UPLOAD = 32 * 1024 * 1024


def check_hierarchy(rows):
    # Cache each node's document ancestor to keep deep hierarchies linear.
    owners = {}
    for ident in rows:
        current = ident
        trail = []
        seen = set()
        while current is not None and current not in owners:
            if current in seen:
                raise ValueError(f'{ident}: parent cycle at {current}')
            if current not in rows:
                raise ValueError(f'{ident}: missing parent {current}')
            seen.add(current)
            trail.append(current)
            current = rows[current].get('parent_id')
        owner = owners.get(current)
        for item in reversed(trail):
            row = rows[item]
            if row['kind'] == 'document':
                if not row.get('path'):
                    raise ValueError(f'{item}: missing original document path')
                # Compare the declared folder chain with the path on disk.
                parent = row.get('parent_id')
                for directory in reversed(Path(row['path']).parts[:-1]):
                    folder = rows.get(parent, {})
                    if folder.get('kind') != 'folder' or folder.get('title') != directory:
                        raise ValueError(f'{item}: expected parent folder {directory!r} for {row["path"]}')
                    parent = folder.get('parent_id')
                owner = item
            if row['kind'] == 'section' and owner is None:
                raise ValueError(f'{item}: section must descend from a document')
            owners[item] = owner


def check_files(input_path, rows, skipped):
    if input_path.is_file():
        expected = {input_path.name}
    elif input_path.is_dir():
        expected = {p.relative_to(input_path).as_posix() for p in input_path.rglob('*')
                    if p.is_file() and not p.is_symlink()
                    and not any(part.startswith('.') for part in p.relative_to(input_path).parts)}
    else:
        raise ValueError(f'Input does not exist: {input_path}')
    paths = {row['path'] for row in rows.values() if row.get('path') and row['kind'] in ('document', 'note')}
    for problem, names in [('unknown document paths', paths - expected),
                           ('invalid exclusions', skipped - (expected - paths)),
                           ('missing input files', expected - paths - skipped)]:
        if names:
            raise ValueError(problem + ': ' + ', '.join(sorted(names)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('--input', type=Path, required=True, help='Original input file or folder')
    parser.add_argument('--source', default='manuals')
    parser.add_argument('--skip', action='append', default=[], help='Explicitly excluded relative path (repeatable)')
    parser.add_argument('--existing-target', action='store_true',
                        help='Defer external and historical link checks to a subsequent target DB preview')
    args = parser.parse_args()
    try:
        slug(args.source)
        if args.export.stat().st_size > MAX_UPLOAD:
            raise ValueError('File exceeds the 32 MiB Web UI limit')
        with args.export.open(encoding='utf-8-sig') as stream:
            rows, duplicates = read_records(stream, args.source)
        if duplicates:
            raise ValueError(f'{duplicates} repeated ID(s); keep one record per node')
        check_hierarchy(rows)
        check_files(args.input, rows, set(args.skip))
        for ident, row in rows.items():
            for link in row.get('links', []):
                if link.get('source', args.source) == args.source and link['id'] in rows and link.get('revision', 1) == 1:
                    continue
                if not args.existing_target:
                    raise ValueError(f'{ident}: unresolved reference; verify against its existing target DB')
        print(f'Validated {len(rows)} unique nodes; skipped files: {len(set(args.skip))}.')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
