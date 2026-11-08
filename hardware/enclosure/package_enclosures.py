"""Package current printable models only when preparing an upload."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODELS = ('c3-socket-stacked', 'ordered-v2-stacked', 'charger-inline')
COMMON = ('README.md', 'preview.html', 'package_enclosures.py')


def model_files(model):
    directory = HERE / model
    contents = {}
    for line in (directory / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, name = line.split(None, 1)
        name = name.strip().lstrip('*')
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError('Checksum path outside model: ' + name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Regenerate and validate changed model: ' + model + '/' + name)
        contents[model + '/' + name] = raw
    contents[model + '/SHA256SUMS.txt'] = (directory / 'SHA256SUMS.txt').read_bytes()
    for path in directory.iterdir():
        if path.is_file() and path.suffix in {'.md', '.py', '.js', '.json', '.cjs', '.txt'}:
            contents[model + '/' + path.name] = path.read_bytes()
    for path in (directory / 'output').iterdir():
        if model == 'charger-inline' and path.name in {'base.png', 'lid.png', 'overview.png'}:
            continue
        if path.is_file() and path.name != 'meshes.json' and path.suffix in {'.stl', '.step', '.png', '.svg', '.html', '.json'}:
            contents[model + '/output/' + path.name] = path.read_bytes()
    validation = directory / 'output/independent_validation.json'
    if validation.exists() and not json.loads(validation.read_text(encoding='utf-8'))['passed']:
        raise ValueError('Model validation failed: ' + model)
    return contents


def write_archive(target, files, **metadata):
    target = Path(target)
    files = dict(files)
    if 'README.md' in files:
        files['README.md'] = files['README.md'].decode('utf-8').replace(
            '](../../LICENSING.md)', '](LICENSING.md)').replace(
            '](../LICENSE)', '](hardware/LICENSE)').encode('utf-8')
    for name in ('LICENSE', 'LICENSING.md', 'LICENSES/MIT-legacy.txt', 'hardware/LICENSE'):
        files[name] = (ROOT / name).read_bytes()
    files['MANIFEST.json'] = json.dumps(dict(metadata,
        files={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}),
        ensure_ascii=False, indent=2).encode('utf-8')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read('MANIFEST.json'))
        assert set(archive.namelist()) == set(manifest['files']) | {'MANIFEST.json'}
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix + '.sha256').write_text(
        digest + '  ' + target.name + '\n', encoding='ascii')
    print(json.dumps(dict(file=str(target), files=len(files), sha256=digest), ensure_ascii=False))


def build(target, stacked_target=None):
    files = {name: (HERE / name).read_bytes() for name in COMMON}
    for model in MODELS:
        files.update(model_files(model))
    write_archive(target, files, version='0.1.1', physical_fit_tested=False)
    if stacked_target is not None:
        prefix = 'ordered-v2-stacked/'
        standalone = {name[len(prefix):]: raw for name, raw in files.items() if name.startswith(prefix)}
        write_archive(stacked_target, standalone, physicalFitTested=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Upload ZIP path')
    parser.add_argument('--stacked-output', type=Path)
    args = parser.parse_args()
    build(args.output, args.stacked_output)
