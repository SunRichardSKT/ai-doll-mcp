"""Build one deterministic ToolPkg directly from current, allowlisted source."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from _source_path import load

ROOT = Path(__file__).resolve().parents[1]
VERSION = load('ai_doll.core.version').VERSION
FILES = ('manifest.json', 'main.js', 'core/settings.js', 'core/workflows.js',
         'core/interaction.js', 'core/probe.js', 'core/mcp.js', 'core/device.js', 'core/controls.js',
         'core/archive.js', 'core/recovery.js', 'core/collector.js', 'core/pairing.js', 'core/qr.js',
         'packages/companion.js', 'ui/settings.ui.js', 'vendor/jsQR.js', 'vendor/qrcodegen.js',
         'vendor/jsQR.LICENSE', 'vendor/qrcodegen.LICENSE', 'vendor/qrcodegen.ts', 'vendor/SOURCES.json')


def build(output=None):
    base = ROOT / 'clients/operit'
    output = output or ROOT / 'delivery/AI_Doll_Operit.toolpkg'
    contents = {name: (base / name).read_bytes() for name in FILES}
    for asset in json.loads(contents['vendor/SOURCES.json']):
        raw = contents.get('vendor/'+asset['file'])
        if raw is None or hashlib.sha256(raw).hexdigest() != asset['sha256']:
            raise ValueError('Pinned QR resource checksum mismatch: '+asset['file'])
    # Operit's CommonJS loader cannot read arbitrary assets from a ToolPkg ZIP.
    # Materialize the pinned scripts as text only in the generated package.
    contents['core/qr_assets.js'] = ('exports.decoder='+json.dumps(contents['vendor/jsQR.js'].decode('utf-8'))+
        ';\nexports.generator='+json.dumps(contents['vendor/qrcodegen.js'].decode('utf-8'))+';\n').encode('utf-8')
    from audit_delivery import local_credentials, PRIVATE_URL
    secrets = local_credentials()
    for raw in contents.values():
        if PRIVATE_URL.search(raw) or any(secret in raw for secret in secrets):
            raise ValueError('Local installation data found in ToolPkg source')
    manifest = json.loads(contents['manifest.json'])
    if manifest['version'] != VERSION or manifest['toolpkg_id'] != 'org.ai_doll.companion':
        raise ValueError('Unexpected Operit identity/version')
    from operit_metadata import validate_archive, validate_contents
    validate_contents(contents)
    regression = subprocess.run([sys.executable, '-m', 'unittest', 'test_operit_metadata'],
                                capture_output=True, text=True, encoding='utf-8', cwd=ROOT/'tools', timeout=20)
    if regression.returncode:
        raise ValueError('ToolPkg metadata regression failed: '+regression.stderr[-2000:])
    # Import metadata, JS registration and executable tools are separate gates.
    node = shutil.which('node')
    if not node:
        raise ValueError('Developer build requires Node.js for the ToolPkg registration check')
    checks = ['test_operit_registration.cjs', 'test_operit_unified.cjs', 'test_operit_phone.cjs', 'test_operit_address.cjs', 'test_operit_continuous.cjs', 'test_operit_controls.cjs', 'test_operit_queue.cjs']
    checks += ['test_operit_pairing.cjs', 'test_operit_pairing_ui.cjs', 'test_operit_qr.cjs',
               'test_operit_archive.cjs', 'test_operit_storage.cjs', 'test_operit_sync.cjs', 'test_operit_sync_lifecycle.cjs']
    upstream = ROOT / 'build/integration-research/operit-1.12.2/runtime/context.js'
    if upstream.is_file():
        checks.append('test_operit_ui_bridge.cjs')
    for entry in checks:
        command = [node, str(ROOT / 'tools' / entry)]
        if entry in ('test_operit_registration.cjs', 'test_operit_pairing_ui.cjs') and upstream.is_file():
            command += ['--upstream', str(upstream.parent)]
        check = subprocess.run(command,
                               capture_output=True, text=True, encoding='utf-8', timeout=20, cwd=ROOT)
        if check.returncode:
            raise ValueError('ToolPkg validation failed (' + entry + '): ' + check.stderr[-2000:])
    contents['CHECKSUMS.json'] = json.dumps({name: hashlib.sha256(data).hexdigest()
                                           for name, data in contents.items()}, indent=2).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() or set(archive.namelist()) != set(contents):
            raise ValueError('ToolPkg integrity check failed')
        for name, digest in json.loads(archive.read('CHECKSUMS.json')).items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('ToolPkg checksum mismatch')
    validate_archive(output)
    return dict(file=output.name, version=manifest['version'], files=len(contents),
                sha256=hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
