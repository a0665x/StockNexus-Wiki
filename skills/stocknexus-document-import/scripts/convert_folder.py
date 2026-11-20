"""Convert UTF-8 Markdown and text files into StockNexus document records."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile


def identity(*parts):
    return hashlib.sha256(json.dumps(parts,ensure_ascii=False).encode()).hexdigest()[:24]


def convert(root, path):
    relative = path.relative_to(root).as_posix()
    doc = {'id':identity(relative),'path':relative,'kind':'document','title':path.stem.strip() or 'Untitled document'}
    if path.parent != root:
        doc['parent_id'] = identity('folder', path.parent.relative_to(root).as_posix())
    current = doc
    stack, counts, lines = [], {}, []
    fence = ''
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        if path.suffix.lower() == '.md':
            delimiter = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',line)
            if delimiter:
                marker, tail = delimiter.groups()
                if not fence:
                    fence = marker
                elif marker.startswith(fence) and not tail.strip():
                    fence = ''
                lines.append(line)
                continue
        heading = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*$',line) if path.suffix.lower()=='.md' and not fence else None
        if not heading:
            lines.append(line)
            continue
        current['text']='\n'.join(lines).strip()
        yield current
        lines=[]
        level,title=len(heading[1]),heading[2].strip()
        while stack and stack[-1][0]>=level:
            stack.pop()
        parent=stack[-1][1] if stack else doc['id']
        key=(parent,title)
        counts[key]=counts.get(key,0)+1
        ident=identity(parent,title,counts[key])
        current={'id':ident,'kind':'section','parent_id':parent,'title':title,
                 'locator':{'line':number,'heading':title}}
        stack.append((level,ident))
    current['text']='\n'.join(lines).strip()
    yield current


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path,help='Markdown/text file or document folder')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.input.is_file():
        root = args.input.parent
        files = [args.input]
    elif args.input.is_dir():
        root = args.input
        files = sorted(path for path in root.rglob('*') if path.is_file() and not path.is_symlink()
                       and not any(p.startswith('.') for p in path.relative_to(root).parts))
    else:
        parser.error('Input file or directory does not exist')
    supported=[p for p in files if p.suffix.lower() in ('.txt','.md')]
    for path in files:
        if path.suffix.lower() not in ('.txt','.md') and path.resolve()!=args.output.resolve():
            print('Needs external extraction:',path.relative_to(root),file=sys.stderr)
    if not supported or args.output.suffix.lower()!='.jsonl':
        parser.error('Provide Markdown/text input and a .jsonl output path')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=args.output.parent,delete=False) as out:
        temp=Path(out.name)
    try:
        with temp.open('w',encoding='utf8') as out:
            directories = {p for f in supported for p in f.relative_to(root).parents if p != Path('.')}
            for directory in sorted(directories):
                row = {'id':identity('folder', directory.as_posix()), 'kind':'folder', 'title':directory.name}
                if directory.parent != Path('.'):
                    row['parent_id'] = identity('folder', directory.parent.as_posix())
                out.write(json.dumps(row,ensure_ascii=False)+'\n')
            for path in supported:
                for row in convert(root,path):
                    out.write(json.dumps(row,ensure_ascii=False)+'\n')
        temp.replace(args.output)
    finally:
        temp.unlink(missing_ok=True)


if __name__=='__main__':
    main()
