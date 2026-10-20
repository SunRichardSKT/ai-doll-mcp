"""Build one deterministic ToolPkg directly from current, allowlisted source."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ('manifest.json', 'main.js', 'core/settings.js', 'core/workflows.js',
         'core/interaction.js', 'core/probe.js', 'core/mcp.js', 'core/device.js', 'packages/companion.js', 'ui/settings.ui.js')


def build(output=None):
    base = ROOT / 'clients/operit'
    output = output or ROOT / 'delivery/AI_Doll_Operit.toolpkg'
    contents = {name: (base / name).read_bytes() for name in FILES}
    from audit_delivery import local_credentials, PRIVATE_URL
    secrets = local_credentials()
    for raw in contents.values():
        if PRIVATE_URL.search(raw) or any(secret in raw for secret in secrets):
            raise ValueError('Local installation data found in ToolPkg source')
    manifest = json.loads(contents['manifest.json'])
    if manifest['version'] != '2.21.0' or manifest['toolpkg_id'] != 'org.ai_doll.companion':
        raise ValueError('Unexpected Operit identity/version')
    # Archive integrity and MCP tests cannot detect registration failures. Check
    # both of Operit's module export shapes before producing any downloadable file.
    node = shutil.which('node')
    if not node:
        raise ValueError('Developer build requires Node.js for the ToolPkg registration check')
    checks = ['test_operit_registration.cjs', 'test_operit_unified.cjs', 'test_operit_phone.cjs', 'test_operit_address.cjs']
    upstream = ROOT / 'build/integration-research/operit-1.12.2/runtime/context.js'
    if upstream.is_file():
        checks.append('test_operit_ui_bridge.cjs')
    for entry in checks:
        check = subprocess.run([node, str(ROOT / 'tools' / entry)],
                               capture_output=True, text=True, timeout=20, cwd=ROOT)
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
    return dict(file=output.name, version=manifest['version'], files=len(contents),
                sha256=hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
