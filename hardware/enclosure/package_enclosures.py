"""Bundle public planar and stacked mechanical candidates, previews and source."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODELS = ('ordered-v2-prototype', 'v22-prototype')
COMMON = ('README.md', 'preview.html', 'validation_103450.json',
          'validate_enclosures.py', 'package_enclosures.py',
          'preview-assets/ordered.png', 'preview-assets/v22.png', 'preview-assets/comparison.png')
SOURCE = ('README.md', 'parameters.json', 'pcb_reference.json', 'requirements-cad.txt',
          'build_enclosure.py', 'render_preview.py', 'SHA256SUMS.txt')
OUTPUT = ('base.stl', 'lid.stl', 'base.step', 'lid.step', 'assembly_reference.step',
          'fit_tray.stl', 'audit.json', 'export_check.json', 'meshes.json', 'preview.html',
          'preview.png', 'assembled.png', 'cutaway.png')
EXTRA = {'v22-prototype': ('capture_preview.cjs', 'output/lid.png')}
STACKED = 'ordered-v2-stacked'
STACKED_SOURCE = ('README.md', 'parameters.json', 'pcb_reference.json', 'requirements-cad.txt',
                  'build_enclosure.py', 'render_preview.py', 'validate_and_package.py',
                  'capture_preview.cjs', 'SHA256SUMS.txt')
STACKED_OUTPUT = ('base.stl', 'base.step', 'tray.stl', 'tray.step', 'lid.stl', 'lid.step',
                  'assembly_reference.step', 'audit.json', 'validation.json',
                  'independent_validation.json', 'meshes.json', 'preview.html', 'preview.png',
                  'assembled.png', 'side.png', 'tray.png', 'stack.svg', 'stack.png', 'preview_check.json')


def write_archive(target, files, **metadata):
    files = dict(files)
    files['MANIFEST.json'] = json.dumps(dict(metadata,
        files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}),
        ensure_ascii=False,indent=2).encode('utf-8')
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,10,20,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,raw)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        manifest=json.loads(archive.read('MANIFEST.json'))
        assert set(archive.namelist()) == set(manifest['files'])|{'MANIFEST.json'}
        for name,digest in manifest['files'].items():
            assert hashlib.sha256(archive.read(name)).hexdigest()==digest
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix+'.sha256').write_text(digest+'  '+target.name+'\n',encoding='ascii')
    print(json.dumps(dict(file=str(target),files=len(files),sha256=digest),ensure_ascii=False,indent=2))


def build(target, stacked_target=None):
    names = list(COMMON)
    for model in MODELS:
        names.extend(model+'/'+name for name in SOURCE)
        names.extend(model+'/output/'+name for name in OUTPUT)
        names.extend(model+'/'+name for name in EXTRA.get(model, ()))
    names.extend(STACKED+'/'+name for name in STACKED_SOURCE)
    names.extend(STACKED+'/output/'+name for name in STACKED_OUTPUT)
    files = {name:(HERE/name).read_bytes() for name in names}
    report = json.loads(files['validation_103450.json'])
    assert all(r['passed'] for r in report['models'].values()), 'Model validation failed'
    for model in MODELS:
        assert files[model+'/output/base.stl'] and files[model+'/output/lid.stl']
        for relative,digest in report['models'][model]['files'].items():
            assert hashlib.sha256(files[model+'/output/'+relative]).hexdigest()==digest, 'Revalidate changed model: '+model
        for line in files[model+'/SHA256SUMS.txt'].decode('utf-8').splitlines():
            digest, relative = line.split(None,1)
            relative = relative.strip().lstrip('*')
            assert hashlib.sha256(files[model+'/'+relative]).hexdigest() == digest, relative
    stacked_report = json.loads(files[STACKED+'/output/independent_validation.json'])
    assert stacked_report['passed'], 'Stacked model validation failed'
    for relative,digest in stacked_report['files'].items():
        assert hashlib.sha256(files[STACKED+'/output/'+relative]).hexdigest()==digest, relative
    for line in files[STACKED+'/SHA256SUMS.txt'].decode('utf-8').splitlines():
        digest,relative=line.split(None,1)
        assert hashlib.sha256(files[STACKED+'/'+relative.strip()]).hexdigest()==digest, relative
    write_archive(target, files, version='103450-20261020', physical_fit_tested=False)
    if stacked_target is not None:
        prefix=STACKED+'/'
        standalone={name[len(prefix):]:raw for name,raw in files.items() if name.startswith(prefix)}
        write_archive(stacked_target, standalone, revision=stacked_report['revision'], physicalFitTested=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'delivery/AI_Doll_Enclosures_103450_20261020.zip')
    parser.add_argument('--stacked-output',type=Path,default=ROOT/'delivery/AI_Doll_Enclosure_Stacked_103450_20261020.zip')
    args=parser.parse_args()
    build(args.output, args.stacked_output)
