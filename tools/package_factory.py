"""Build the offline Windows production station. SPDX-License-Identifier: AGPL-3.0-only."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def publish_bundle(staged, destination):
    """Update application files without replacing the operator's build/ records."""
    destination.mkdir(parents=True, exist_ok=True)
    if (staged/'build').exists():
        raise ValueError('生产记录不能作为程序文件发布')
    shutil.copytree(staged, destination, dirs_exist_ok=True)
    for obsolete in ('先读我.txt', '使用说明.md', 'esptool-worker.exe'):
        (destination/obsolete).unlink(missing_ok=True)


def archive_bundle(bundle, target, firmware):
    target.parent.mkdir(parents=True, exist_ok=True)
    hashes = {}
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(bundle.rglob('*')):
            if source.is_file():
                name = source.relative_to(bundle).as_posix()
                data = source.read_bytes()
                archive.writestr(name, data)
                hashes[name] = hashlib.sha256(data).hexdigest()
        archive.writestr('MANIFEST.json', json.dumps({'version': firmware, 'files': hashes}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-zip', type=Path, help='Archive the clean build for GitHub Releases')
    args = parser.parse_args()
    from check_firmware import check
    firmware = check(ROOT)['firmware']
    output = ROOT/'build/factory-dist'
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                    '--distpath', str(output), '--workpath', str(ROOT/'build/factory-pyinstaller'),
                    str(ROOT/'tools/factory_check.spec')], check=True, cwd=ROOT)
    package = output/'一代批量检测'
    # The worker shares this runtime; only the GUI is exposed as a root entry.
    if (package/'esptool-worker.exe').is_file():
        (package/'esptool-worker.exe').replace(package/'_internal/esptool-worker.exe')
    guide=(ROOT/'docs/start/FACTORY_CHECK.md').read_text(encoding='utf-8')
    tag = 'v' + firmware.removeprefix('doll-lab-')
    source_url = f'https://github.com/SunRichardSKT/ai-doll-mcp/blob/{tag}/'
    guide=guide.replace('(../README.md)',f'({source_url}docs/README.md)')
    guide=guide.replace('(../../hardware/gen1/README.md)',f'({source_url}hardware/gen1/README.md)')
    guide=guide.replace('(SINGLE_CHANNEL_TEST.md)', '(对应源码/docs/start/SINGLE_CHANNEL_TEST.md)')
    guide=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1（\2）',guide)
    guide=re.sub(r'^#{1,6}\s+', '', guide, flags=re.M).replace('**','').replace('`','')
    (package/'使用说明.txt').write_text(guide,encoding='utf-8-sig')
    shutil.copyfile(ROOT/'LICENSE', package/'LICENSE')
    shutil.copyfile(ROOT/'LICENSING.md', package/'LICENSING.md')
    notices = package/'第三方许可'
    notices.mkdir(exist_ok=True)
    names = ('pyinstaller','pyserial','esptool','cryptography','cffi','pycparser','ecdsa',
             'bitstring','reedsolo','intelhex','PyYAML','packaging')
    for name in names:
        dist = importlib.metadata.distribution(name)
        for entry in dist.files or []:
            if Path(str(entry)).name.upper().startswith(('LICENSE','COPYING','NOTICE')) and dist.locate_file(entry).is_file():
                target = notices/name/Path(str(entry)).name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(dist.locate_file(entry), target)
    shutil.copyfile(Path(sys.base_prefix)/'LICENSE.txt', notices/'Python-LICENSE.txt')
    shutil.copyfile(ROOT/'tools/vendor/pyserial-3.5.LICENSE', notices/'pyserial-3.5.LICENSE')
    shutil.copyfile(ROOT/'tools/vendor/tcl-8.6.12.LICENSE', notices/'Tcl-8.6.12.LICENSE')
    for folder in (package/'_internal/_tcl_data', package/'_internal/_tk_data'):
        license=folder/'license.terms'
        if license.is_file():
            shutil.copyfile(license,notices/(folder.name+'-LICENSE.txt'))
    # Include the actual project sources used by the station and its firmware.
    source = package/'对应源码'
    for name in ('factory_check.py','factory_esptool.py','factory_check.spec','package_factory.py',
                 'device_lab.py','flash_esp32.py','flash_sources.py','service_lifecycle.py','check_firmware.py',
                 'test_factory_check.py','test_factory_probe.py','test_package_factory.py','test_serial_transport.py','test_flash_esp32.py','test_flash_sources.py',
                 'embed_channel_editor.py','firmware_link.py','export_firmware.py','build_lab.ps1',
                 'wifi_feedback.js','channel_editor.js','ota_manager.js','pairing_connection.js'):
        target=source/'tools'/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'tools'/name, target)
    shutil.copytree(ROOT/'firmware', source/'firmware', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.pio', '__pycache__', '*_asset.h'))
    shutil.copytree(ROOT/'tools/vendor', source/'tools/vendor', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('qrcodegen.js','qrcodegen.LICENSE','SOURCES.json'):
        target=source/'clients/operit/vendor'/name;target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/'clients/operit/vendor'/name,target)
    (source/'hardware').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'hardware/LICENSE', source/'hardware/LICENSE')
    (source/'docs/start').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'docs/start/FACTORY_CHECK.md', source/'docs/start/FACTORY_CHECK.md')
    shutil.copyfile(ROOT/'docs/start/SINGLE_CHANNEL_TEST.md', source/'docs/start/SINGLE_CHANNEL_TEST.md')
    for name in ('LICENSE','LICENSING.md','requirements-flash.txt','requirements-firmware.txt','requirements-factory-build.txt'):
        shutil.copyfile(ROOT/name, source/name)
    (package/'hardware').mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'hardware/LICENSE', package/'hardware/LICENSE')
    # Fail packaging if the actual console worker cannot load its resources.
    result = subprocess.run([str(package/'_internal/esptool-worker.exe'), '--help'],
                            capture_output=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode or b'esptool' not in result.stdout:
        raise RuntimeError(result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
    if args.release_zip:
        archive_bundle(package, args.release_zip, firmware)
        print(f'Release archive ready: {args.release_zip}')
        return
    destination=ROOT/'output/factory/一代批量检测'
    publish_bundle(package,destination)
    size=sum(p.stat().st_size for p in package.rglob('*') if p.is_file())
    print(f'Portable station ready: {destination} ({size/1024/1024:.1f} MiB)')

if __name__=='__main__':
    main()
