"""PlatformIO pre-build: embed gzip copies of the shared browser scripts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from functools import lru_cache


@lru_cache(maxsize=16)
def gzip_asset(source):
    import zopfli.gzip
    return zopfli.gzip.compress(source,numiterations=15)


@lru_cache(maxsize=4)
def minifier(root):
    folder=root/'tools/vendor'
    for item in json.loads((folder/'SOURCES.json').read_text(encoding='utf-8')):
        if hashlib.sha256((folder/item['file']).read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Pinned asset minifier checksum mismatch: '+item['file'])
    spec=importlib.util.spec_from_file_location('firmware_rjsmin',folder/'rjsmin.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module._make_jsmin(python_only=True)


def asset_source(root,name):
    compact=minifier(root)
    if name=='device_page':
        html=(root/'firmware/src/device_page.h').read_text(encoding='utf-8').split('R"HTML(',1)[1].split(')HTML"',1)[0]
        return re.sub(r'<script>(.*?)</script>',lambda m:'<script>'+compact(m[1],keep_bang_comments=True)+'</script>',html,flags=re.S).encode('utf-8')
    if name=='pairing':
        # Preserve the complete MIT notice even when ordinary comments are removed.
        license=(root/'clients/operit/vendor/qrcodegen.LICENSE').read_text(encoding='utf-8')
        source=(root/'clients/operit/vendor/qrcodegen.js').read_text(encoding='utf-8')+'\n'+(root/'tools/pairing_connection.js').read_text(encoding='utf-8')
        return ('/*!\n'+license+'\n*/\n'+compact(source,keep_bang_comments=False)).encode('utf-8')
    return compact((root/'tools'/f'{name}.js').read_text(encoding='utf-8'),keep_bang_comments=True).encode('utf-8')


def build_tool_catalog(root):
    tools=json.loads((root/'firmware/src/device_tools.json').read_text(encoding='utf-8'))
    if not isinstance(tools,list) or not tools or len({t['name'] for t in tools})!=len(tools):
        raise ValueError('Device tool catalog must contain unique tool names')
    for tool in tools:
        if tool['inputSchema'].get('type')!='object':
            raise ValueError('Device tool input schema must be an object')
    data=json.dumps(tools,ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\0'
    write_header(root/'firmware/src/device_tools_asset.h','DEVICE_TOOLS_JSON',data,'firmware/src/device_tools.json')


def write_header(target,symbol,data,origin):
    rows=[','.join(f'0x{byte:02x}' for byte in data[offset:offset+24]) for offset in range(0,len(data),24)]
    text=(f'#pragma once\n// Generated from {origin}; edit that source.\n'
          f'static const unsigned char {symbol}[] PROGMEM={{\n'+',\n'.join(rows)+'\n};\n')
    if not target.exists() or target.read_text(encoding='utf-8')!=text:
        target.write_text(text,encoding='utf-8')


def build_assets(root):
    build_tool_catalog(root)
    for name, symbol in (('channel_editor','CHANNEL_EDITOR_GZIP'), ('ota_manager','OTA_MANAGER_GZIP'), ('device_page','DEVICE_PAGE_GZIP'), ('pairing','PAIRING_GZIP')):
        source=asset_source(root,name)
        data=gzip_asset(source)
        origin='firmware/src/device_page.h' if name=='device_page' else 'tools/pairing_connection.js and bundled qrcodegen' if name=='pairing' else f'tools/{name}.js'
        target=root/'firmware/src'/f'{name}_asset.h'
        write_header(target,symbol,data,origin)


if '__file__' not in globals():
    Import('env')
    build_assets(Path(env['PROJECT_DIR']).parent)
elif __name__=='__main__':
    build_assets(Path(__file__).resolve().parents[1])
