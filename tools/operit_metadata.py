"""Check the Operit 1.12.2 import contract before executing any package code.

ToolPackage.kt requires PackageToolParameter.description (there is no default).
PackageManager.parseJsPackage injects only script, then decodes that model.
The JS registration bridge runs later and cannot detect missing metadata fields.
This is a public-schema check, not an Android installation result.
"""
import json
import posixpath
import re
import zipfile


def _field(value, key, kind, path):
    if key not in value or not isinstance(value[key], kind):
        raise ValueError(f'{path}.{key}: required {kind.__name__}')
    return value[key]


def _text(value, key, path):
    if key not in value:
        raise ValueError(f'{path}.{key}: required LocalizedText')
    text = value[key]
    if isinstance(text, str):
        return
    if isinstance(text, dict) and all(isinstance(v, str) for v in text.values()):
        return
    raise ValueError(f'{path}.{key}: expected text or a language-to-text map')


def _tool(tool, path):
    if not isinstance(tool, dict):
        raise ValueError(f'{path}: expected tool object')
    _field(tool, 'name', str, path)
    _text(tool, 'description', path)
    # Operit's loader fills script="" before decoding PackageTool.
    for i, param in enumerate(_field(tool, 'parameters', list, path)):
        label = f'{path}.parameters[{i}]'
        if not isinstance(param, dict):
            raise ValueError(f'{label}: expected parameter object')
        _field(param, 'name', str, label)
        _field(param, 'type', str, label)
        _text(param, 'description', label)
        if 'required' in param and type(param['required']) is not bool:
            raise ValueError(f'{label}.required: expected boolean')


def parse_metadata(source, entry):
    match = re.search(r'/\*\s*METADATA\s*([\s\S]*?)\*/', source)
    if not match:
        raise ValueError(f'{entry}: missing METADATA header')
    # Our packages intentionally use strict JSON, a subset of Operit's HJSON.
    data = json.loads(match[1])
    _field(data, 'name', str, entry)
    _text(data, 'description', entry)
    for i, tool in enumerate(_field(data, 'tools', list, entry)):
        _tool(tool, f'{entry}.tools[{i}]')
    for i, state in enumerate(data.get('states', [])):
        _field(state, 'id', str, f'{entry}.states[{i}]')
        for j, tool in enumerate(state.get('tools', [])):
            _tool(tool, f'{entry}.states[{i}].tools[{j}]')
    return data


def validate_contents(contents):
    def read(entry):
        if entry not in contents:
            raise ValueError(f'{entry}: archive entry not found')
        return contents[entry].decode('utf-8-sig')

    manifest = json.loads(read('manifest.json'))
    _field(manifest, 'toolpkg_id', str, 'manifest')
    read(_field(manifest, 'main', str, 'manifest'))
    packages = []
    for i, sub in enumerate(manifest.get('subpackages', [])):
        _field(sub, 'id', str, f'manifest.subpackages[{i}]')
        entry = posixpath.normpath(_field(sub, 'entry', str, f'manifest.subpackages[{i}]'))
        if entry.startswith(('../', '/')):
            raise ValueError('Subpackage entry must stay inside the archive')
        packages.append(parse_metadata(read(entry), entry))
    if not packages:
        raise ValueError('AI Doll requires at least one valid subpackage')
    return dict(version=manifest['version'], subpackages=len(packages),
                tools=sum(len(p['tools']) for p in packages),
                parameters=sum(len(t['parameters']) for p in packages for t in p['tools']))


def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip():
            raise ValueError('Corrupt ToolPkg archive')
        return validate_contents({n: archive.read(n) for n in archive.namelist()})
