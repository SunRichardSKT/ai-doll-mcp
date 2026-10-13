"""Verify public allowlists/checksums and exclude installation credentials before release."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile
from delivery_archive import open_delivery

ROOT=Path(__file__).resolve().parents[1]
SECRET_NAMES=re.compile(r'password|token|secret|api.?key|^key$',re.I)
PRIVATE_URL=re.compile(rb'https?://[^\s"<>]+/[0-9a-f]{64}/mcp')


def local_credentials():
    values=set()
    def collect(value,key=''):
        if isinstance(value,dict):
            for name,item in value.items():collect(item,name)
        elif isinstance(value,list):
            for item in value:collect(item,key)
        elif isinstance(value,str) and len(value)>=8 and (SECRET_NAMES.search(key) or PRIVATE_URL.search(value.encode())):
            values.add(value.encode())
    paths = [p for folder in ('device-lab', 'direct-server', 'direct-device-test', 'linux-deploy-test')
             for p in (ROOT/'build'/folder).rglob('*-private.json')]
    for path in paths:
        try:collect(json.loads(path.read_text(encoding='utf-8-sig')))
        except (OSError,ValueError):raise RuntimeError('Cannot audit a private installation file') from None
    return values


def audit(path,secrets=None):
    secrets=local_credentials() if secrets is None else secrets
    with open_delivery(path) as archive:
        if archive.testzip():raise ValueError('Archive integrity failure')
        manifest=json.loads(archive.read('MANIFEST.json'))
        files=manifest['files']
        if set(archive.namelist())!=set(files)|{'MANIFEST.json'}:raise ValueError('File outside public allowlist')
        for name,digest in files.items():
            item=PurePosixPath(name)
            if item.is_absolute() or '..' in item.parts or any(p in {'build','.tools','.git','.venv','_local','__pycache__'} for p in item.parts):
                raise ValueError('Private or unsafe archive path')
            if name not in {'deploy/direct-server/.env.example','python/Lib/site-packages/certifi/cacert.pem'} and re.search(r'private\.json$|\.sqlite3(?:-wal|-shm)?$|\.env(?:\.|$)|\.log$|\.(pem|key)$',name,re.I):raise ValueError('Private file in public package')
            raw=archive.read(name)
            if name=='python/Lib/site-packages/certifi/cacert.pem' and (b'-----BEGIN CERTIFICATE-----' not in raw or b'PRIVATE KEY' in raw):
                raise ValueError('Runtime CA bundle must contain public certificates only')
            if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Manifest checksum mismatch')
            if any(secret in raw for secret in secrets) or PRIVATE_URL.search(raw):raise ValueError('Installation credential found in public package')
        return dict(file=Path(path).name,files=len(files),passed=True,
                    sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path,nargs='?',default=ROOT/'delivery/AI_Doll_Code_v2.17.0.zip')
    args=parser.parse_args()
    print(json.dumps(audit(args.package),indent=2))


if __name__=='__main__':main()
