"""Install the official Windows Secure MCP Tunnel CLI, verifying the release ZIP."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASES = 'https://github.com/openai/tunnel-client/releases'
CACHE = ROOT / '.tools/secure-mcp-tunnel'
MAX_ARCHIVE = 160 * 1024 * 1024


def fetch(url, limit=262144):
    request = urllib.request.Request(url, headers={'User-Agent': 'AI-Doll-Secure-MCP'})
    with urllib.request.urlopen(request, timeout=30) as response:
        if urlsplit(response.url).scheme != 'https':
            raise RuntimeError('Official download must remain HTTPS')
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise RuntimeError('Official download exceeded its size limit')
        return raw, response.url


def checksum(text, asset):
    matches = []
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?([^\s]+)', line.strip())
        if match and match[2] == asset:
            matches.append(match[1].lower())
    if len(matches) != 1:
        raise RuntimeError('No unique official checksum for the requested archive')
    return matches[0]


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def extract_verified(raw, folder):
    """Validate every member before writing; no links, traversal or ZIP bombs."""
    archive_path = folder / 'release.zip'
    archive_path.write_bytes(raw)
    with zipfile.ZipFile(archive_path) as archive:
        names = set()
        size = 0
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            canonical = path.as_posix().casefold()
            if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                    or ':' in item.filename or canonical in names
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise RuntimeError('Unsafe member in official release archive')
            names.add(canonical)
            size += item.file_size
            if size > 240 * 1024 * 1024:
                raise RuntimeError('Official archive expansion exceeded its size limit')
        if archive.testzip() is not None:
            raise RuntimeError('Official archive integrity check failed')
        archive.extractall(folder)


def installed(folder=CACHE):
    receipt = Path(folder) / 'installed.json'
    if not receipt.exists():
        return None
    data = json.loads(receipt.read_text(encoding='utf-8'))
    version = data.get('version', '')
    relative = Path(data.get('executable', ''))
    target = (Path(folder) / relative).resolve()
    if (not re.fullmatch(r'v\d+\.\d+\.\d+', version) or relative.is_absolute()
            or not target.is_relative_to(Path(folder).resolve())
            or target.name != 'tunnel-client.exe' or not target.is_file()
            or digest(target) != data.get('executable_sha256')):
        raise RuntimeError('Installed tunnel client is invalid; download a verified release again')
    return target, version


def install(folder=CACHE, *, update=False, version=None):
    folder = Path(folder).resolve()
    if not update and version is None and (cached := installed(folder)):
        return cached
    if os.name != 'nt':
        raise RuntimeError('This installer supports Windows; use the official client on other systems')
    architecture = platform.machine().lower()
    arch = {'amd64': 'amd64', 'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(architecture)
    if arch is None:
        raise RuntimeError('A 64-bit Windows system is required')
    if version is None:
        _, url = fetch(RELEASES + '/latest', limit=2 * 1024 * 1024)
        parsed = urlsplit(url)
        if parsed.netloc != 'github.com' or not parsed.path.startswith('/openai/tunnel-client/releases/tag/'):
            raise RuntimeError('Unexpected official release redirect')
        version = parsed.path.rsplit('/', 1)[-1]
    if not re.fullmatch(r'v\d+\.\d+\.\d+', version):
        raise ValueError('Only stable official release tags are accepted')
    asset = f'tunnel-client-{version}-windows-{arch}.zip'
    base = RELEASES + '/download/' + version + '/'
    sums, _ = fetch(base + 'SHA256SUMS.txt')
    expected = checksum(sums.decode('utf-8'), asset)
    raw, _ = fetch(base + asset, MAX_ARCHIVE)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError('Official tunnel client checksum mismatch')
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{version}-{arch}'
    # Never overwrite a binary in use. A verified previous version can remain cached.
    with tempfile.TemporaryDirectory(prefix='install-', dir=folder) as temporary:
        stage = Path(temporary)
        extract_verified(raw, stage)
        executables = list(stage.rglob('tunnel-client.exe'))
        if len(executables) != 1:
            raise RuntimeError('Official archive does not contain one tunnel-client.exe')
        executable = executables[0]
        result = subprocess.run([str(executable), '--version'], capture_output=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        actual = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        if result.returncode != 0 or version.lstrip('v') not in actual:
            raise RuntimeError('Official tunnel client version check failed')
        relative = executable.relative_to(stage)
        binary_hash = digest(executable)
        if target.exists():
            existing = target / relative
            if not existing.is_file() or digest(existing) != binary_hash:
                raise RuntimeError('Existing release directory differs from the verified archive')
        else:
            shutil.copytree(stage, target)
    receipt = dict(version=version, architecture=arch, asset=asset, archive_sha256=expected,
                   executable=(target / relative).relative_to(folder).as_posix(),
                   executable_sha256=binary_hash, source=RELEASES + '/latest')
    temporary_receipt = folder / 'installed.tmp'
    temporary_receipt.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    temporary_receipt.replace(folder / 'installed.json')
    return installed(folder)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update', action='store_true')
    arguments = parser.parse_args()
    try:
        executable, version = install(update=arguments.update)
        print(json.dumps(dict(installed=True, version=version, checksum_verified=True)))
    except Exception as error:
        print(json.dumps(dict(installed=False, error_type=type(error).__name__)))
        raise SystemExit(1)
