"""Check Markdown links and headings in a repository or a delivered ZIP/TAR.

Examples: python tools/check_documentation.py --repository .
          python tools/check_documentation.py --archive delivery/package.zip
Checks local links in that exact context, including Unicode heading anchors.
External web availability and installation success are separate validations.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import os
import unicodedata
from urllib.parse import unquote, urlsplit

from delivery_archive import open_delivery

PUBLIC_PREFIX='https://github.com/SunRichardSKT/ai-doll-mcp/'


def headings(text):
    result=set();seen={};inside=False
    for line in text.splitlines():
        if re.match(r'^\s*(```|~~~)',line):inside=not inside;continue
        match=re.match(r'^#{1,6}\s+(.+?)\s*#*$',line)
        if inside or not match:continue
        title=re.sub(r'<[^>]*>','',match[1]).lower()
        slug=''.join(c for c in title if c in ' _-' or unicodedata.category(c)[0] in {'L','N','M'}).replace(' ','-')
        count=seen.get(slug,0);seen[slug]=count+1
        result.add(slug+(f'-{count}' if count else ''))
    return result


def check(files,repository=False):
    errors=[];links=0
    edges={name:set() for name in files if name.endswith('.md') and not name.startswith('python/Lib/')}
    for name in edges:
        text=files[name].decode('utf-8-sig')
        visible=[];inside=False
        for line in text.splitlines():
            if re.match(r'^\s*(```|~~~)',line):inside=not inside;continue
            if not inside:visible.append(line)
        if len(re.findall(r'^#\s+.+','\n'.join(visible),re.M))!=1:errors.append(f'{name}: needs exactly one H1')
        fences=re.findall(r'^\s*(```|~~~)',text,re.M)
        if len(fences)%2:errors.append(f'{name}: unclosed code fence')
        for raw in re.findall(r'\]\(([^)]+)\)',text):
            target=raw.strip().strip('<>')
            parsed=urlsplit(target)
            same_repo=target.startswith(PUBLIC_PREFIX+'blob/main/') or target.startswith(PUBLIC_PREFIX+'tree/main/')
            if parsed.scheme and not same_repo:continue
            if target.startswith('//'):continue
            if same_repo:
                path=unquote(parsed.path.split('/main/',1)[1])
                # An external link remains valid outside a bundle. If present,
                # check the target and include it in the repository graph.
                if path not in files and not any(n.startswith(path.rstrip('/')+'/') for n in files):
                    if repository:errors.append(f'{name}: missing public repository target {target}')
                    continue
            else:
                path=posixpath.normpath(posixpath.join(str(PurePosixPath(name).parent),unquote(parsed.path))) if parsed.path else name
            if path=='..' or path.startswith('../') or path.startswith('/'):
                errors.append(f'{name}: escaping link {target}');continue
            if path not in files:
                children=[n for n in files if n.startswith(path.rstrip('/')+'/')]
                if children:
                    edges[name].update(n for n in children if n.endswith('.md'));links+=1;continue
                errors.append(f'{name}: missing {target}');continue
            links+=1
            if path.endswith('.md'):
                edges[name].add(path)
                if parsed.fragment and unquote(parsed.fragment) not in headings(files[path].decode('utf-8-sig')):
                    errors.append(f'{name}: missing heading {target}')
    reached=set();pending=['README.md']
    while pending:
        name=pending.pop()
        if name in reached:continue
        reached.add(name);pending.extend(edges.get(name,()))
    orphan=sorted(set(edges)-reached)
    # Archive packages intentionally contain a smaller guide graph.
    errors.extend(f'{name}: unreachable from README' for name in orphan)
    return dict(passed=not errors,markdown_files=len(edges),checked_links=links,errors=errors)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    options=parser.add_mutually_exclusive_group(required=True)
    options.add_argument('--repository',type=Path)
    options.add_argument('--archive',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.archive:
        with open_delivery(args.archive) as archive:
            files={n:(archive.read(n) if n.endswith('.md') else b'') for n in archive.namelist()}
    else:
        files={}
        ignored={'build','.tools','.git','.venv','.pio','__pycache__','_local','node_modules'}
        for folder,directories,names in os.walk(args.repository):
            directories[:]=[name for name in directories if name not in ignored]
            if Path(folder).resolve()==(args.repository/'python').resolve():
                directories[:]=[]
            for name in names:
                p=Path(folder)/name
                files[p.relative_to(args.repository).as_posix()]=p.read_bytes() if p.suffix=='.md' else b''
    result=check(files,repository=args.repository is not None)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
