"""Build the offline Windows x64 runtime from official CPython and PyPI wheels."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3.14.8'
URL = f'https://www.python.org/ftp/python/{VERSION}/python-{VERSION}-embed-amd64.zip'
# Published SHA-256 from python.org's release page.
OFFICIAL_SHA256 = 'a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310'


def main():
    cache = ROOT / 'build/portable-python'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / Path(URL).name
    if not archive.exists():
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as out:
            shutil.copyfileobj(response, out)
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != OFFICIAL_SHA256:
        raise ValueError('Official CPython archive checksum mismatch')
    dest = ROOT / 'python'
    if dest.exists() and any(p.name not in {'README.md','RUNTIME.json','LICENSE.txt'} for p in dest.iterdir()):
        raise ValueError('Runtime already exists; move it aside before rebuilding')
    dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for name in package.namelist():
            target = (dest / name).resolve()
            if not target.is_relative_to(dest.resolve()):
                raise ValueError('Unsafe runtime archive entry')
        package.extractall(dest)
    (dest / 'python314._pth').write_text(
        'python314.zip\n.\nLib/site-packages\n../tools\nimport site\n', encoding='utf-8')
    wheels = cache / 'wheels'
    wheels.mkdir(exist_ok=True)
    lock = ROOT / 'requirements-windows-runtime.lock'
    requirements = lock if lock.exists() else ROOT / 'requirements-companion.txt'
    platform = ['--only-binary=:all:', '--python-version', '3.14', '--implementation', 'cp',
                '--abi', 'cp314', '--platform', 'win_amd64']
    subprocess.run([sys.executable, '-m', 'pip', 'download', *platform, '--dest', str(wheels),
                    '-r', str(requirements)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', *platform, '--no-index',
                    '--find-links', str(wheels), '--no-compile', '--target', str(dest / 'Lib/site-packages'),
                    '-r', str(requirements)], check=True)
    # esptool 4.8.1 publishes an sdist; build its platform-independent wheel
    # once on the developer machine, never on the end user's computer.
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
                    '--wheel-dir', str(wheels), 'esptool==4.8.1'], check=True)
    flash_requirements = ROOT/'requirements-flash-runtime.txt'
    subprocess.run([sys.executable, '-m', 'pip', 'download', *platform, '--no-deps',
                    '--find-links', str(wheels), '--dest', str(wheels),
                    '-r', str(flash_requirements)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', *platform, '--no-deps',
                    '--no-index', '--find-links', str(wheels), '--no-compile',
                    '--target', str(dest/'Lib/site-packages'),
                    '-r', str(flash_requirements)], check=True)
    probe = subprocess.run([str(dest / 'python.exe'), '-I', '-c',
        'import mcp,httpx,serial,sqlite3,ssl,esptool; from importlib.metadata import distributions; '
        'import json,sys; print(json.dumps({"python":sys.version.split()[0],'
        '"packages":{d.metadata["Name"]:d.version for d in distributions()}}))'],
        check=True, capture_output=True, text=True)
    metadata = json.loads(probe.stdout)
    metadata.update(source=URL, archive_sha256=hashlib.sha256(raw).hexdigest(), architecture='win_amd64',
        wheels={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(wheels.glob('*.whl'))})
    (dest / 'RUNTIME.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    # Console shims installed by pip bind to the build interpreter. The app
    # invokes modules directly, so none are part of the relocatable runtime.
    shims = dest / 'Lib/site-packages/bin'
    if shims.exists() and shims.resolve().is_relative_to(dest.resolve()):
        shutil.rmtree(shims)
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
