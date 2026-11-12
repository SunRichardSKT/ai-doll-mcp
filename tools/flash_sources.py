"""Select verified project firmware without changing the bundled image set."""
import base64
import hashlib
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
import zipfile

from flash_esp32 import EXPECTED_OFFSETS, validate_images

REPOSITORY = 'https://github.com/SunRichardSKT/ai-doll-mcp'
MANIFEST = 'FLASH_MANIFEST.json'
FILES = {MANIFEST, *EXPECTED_OFFSETS}
MAX_DOWNLOAD = 128 * 1024 * 1024


def describe(folder, kind, label, **extra):
    manifest, _ = validate_images(folder)
    digest = hashlib.sha256((Path(folder) / MANIFEST).read_bytes()).hexdigest()
    return dict(kind=kind, label=label, firmware=manifest['firmware'],
                source_id=digest, **extra)


def prepare_files(files, cache):
    """Publish only a complete, validated five-file set into the private cache."""
    if set(files) != FILES:
        raise ValueError('请选择项目固件 ZIP，或同时选择 FLASH_MANIFEST.json 和四个 BIN 文件。')
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='firmware-', dir=cache))
    try:
        for name, data in files.items():
            if len(data) > (65536 if name == MANIFEST else 4 * 1024 * 1024):
                raise ValueError('固件文件过大：' + name)
            (folder / name).write_bytes(data)
        try:
            validate_images(folder)
        except (KeyError, TypeError, AttributeError, UnicodeError) as error:
            raise ValueError('固件清单内容不完整或格式不正确。') from error
        return folder
    except Exception:
        # The only deletion target is the new task-owned directory under cache.
        if folder.resolve().parent == cache:
            shutil.rmtree(folder)
        raise


def prepare_zip(archive, cache):
    """Read just the firmware set; never extract paths from the archive."""
    try:
        with zipfile.ZipFile(archive) as package:
            manifests = [entry for entry in package.infolist()
                         if PurePosixPath(entry.filename).name == MANIFEST]
            if len(manifests) != 1:
                raise ValueError('ZIP 中需要且只能有一套 FLASH_MANIFEST.json 固件清单。')
            parent = PurePosixPath(manifests[0].filename).parent
            files = {}
            for name in FILES:
                matches = [entry for entry in package.infolist()
                           if entry.filename == str(parent / name)]
                if len(matches) != 1:
                    raise ValueError('ZIP 缺少或重复包含固件文件：' + name)
                entry = matches[0]
                limit = 65536 if name == MANIFEST else 4 * 1024 * 1024
                if entry.file_size > limit:
                    raise ValueError('ZIP 内固件文件过大：' + name)
                files[name] = package.read(entry)
        return prepare_files(files, cache)
    except (zipfile.BadZipFile, RuntimeError, KeyError) as error:
        raise ValueError('无法读取项目固件 ZIP：' + str(error)) from error


def prepare_upload(data, cache):
    if not isinstance(data, dict) or set(data) != {'files'} or not isinstance(data['files'], list):
        raise ValueError('本地固件文件格式不正确。')
    files = {}
    for item in data['files']:
        if not isinstance(item, dict) or set(item) != {'name', 'data'}:
            raise ValueError('本地固件文件格式不正确。')
        name = item['name']
        if not isinstance(name, str) or name not in FILES or name in files:
            raise ValueError('文件名称不正确或重复，请选择一套完整项目固件。')
        try:
            files[name] = base64.b64decode(item['data'], validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError('文件内容编码不正确：' + name) from error
    return prepare_files(files, cache)


def open_github(url):
    try:
        return urlopen(Request(url, headers={'User-Agent': 'AI-Doll-Flasher',
                                            'Accept': '*/*'}), timeout=25)
    except HTTPError as error:
        if error.code in (403, 429):
            raise ValueError('GitHub 暂时限制访问，请稍后重试，或选择已下载的本地固件 ZIP。') from error
        raise ValueError('GitHub 下载失败（HTTP %s），可改选本地固件。' % error.code) from error
    except (URLError, TimeoutError) as error:
        raise ValueError('暂时连不上 GitHub，可稍后重试或选择本地固件。') from error


class AssetLinks(HTMLParser):
    def __init__(self, prefix):
        super().__init__()
        self.prefix = prefix
        self.assets = {}

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get('href', '')
        if tag == 'a' and href.startswith(self.prefix):
            name = unquote(href[len(self.prefix):])
            if '/' not in name:
                self.assets[name] = 'https://github.com' + href


def latest_release():
    # Public Release pages avoid the 60/hour unauthenticated API quota.
    with open_github(REPOSITORY + '/releases/latest') as response:
        release_url = response.geturl()
    prefix = REPOSITORY + '/releases/tag/'
    if not release_url.startswith(prefix):
        raise ValueError('没有找到 GitHub 的最新正式 Release。')
    encoded_tag = release_url[len(prefix):]
    tag = unquote(encoded_tag)
    if not tag or '/' in tag or '?' in tag or '#' in tag:
        raise ValueError('GitHub Release 版本名称无法识别。')
    path = urlsplit(REPOSITORY).path + '/releases/download/' + encoded_tag + '/'
    links = AssetLinks(path)
    with open_github(REPOSITORY + '/releases/expanded_assets/' + encoded_tag) as response:
        links.feed(response.read(2 * 1024 * 1024).decode('utf-8'))
    preferred = ['AI_Doll_Firmware_' + tag + '.zip', 'AI_Doll_Code_' + tag + '.zip']
    name = next((name for name in preferred if name in links.assets), None)
    if not name or 'SHA256SUMS.txt' not in links.assets:
        raise ValueError('最新 Release 缺少配套固件 ZIP 或 SHA256SUMS.txt，请选择本地完整固件。')
    return dict(tag=tag, release_url=release_url, asset_name=name,
                download_url=links.assets[name], checksums_url=links.assets['SHA256SUMS.txt'])


def download_release(release, cache):
    with open_github(release['checksums_url']) as response:
        lines = response.read(1024 * 1024).decode('utf-8-sig').splitlines()
    hashes = {}
    for line in lines:
        fields = line.split(maxsplit=1)
        if len(fields) == 2:
            hashes[fields[1].lstrip('*')] = fields[0]
    expected = hashes.get(release['asset_name'], '')
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('本版 SHA256SUMS.txt 未包含所选固件包的有效校验值。')
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=cache) as archive:
        digest, total = hashlib.sha256(), 0
        with open_github(release['download_url']) as response:
            while block := response.read(128 * 1024):
                total += len(block)
                if total > MAX_DOWNLOAD:
                    raise ValueError('发布包超过 128MB，请使用项目专用固件包。')
                digest.update(block)
                archive.write(block)
        if digest.hexdigest() != expected:
            raise ValueError('下载包 SHA-256 校验失败，未更换当前固件。')
        archive.seek(0)
        return prepare_zip(archive, cache)
