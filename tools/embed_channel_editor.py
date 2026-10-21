"""PlatformIO pre-build: embed gzip copies of the shared browser scripts."""
import gzip
import io
from pathlib import Path


def build_assets(root):
    for name, symbol in (('channel_editor','CHANNEL_EDITOR_GZIP'), ('ota_manager','OTA_MANAGER_GZIP'), ('device_page','DEVICE_PAGE_GZIP')):
        source=((root/'firmware/src/device_page.h').read_bytes().split(b'R"HTML(',1)[1].split(b')HTML"',1)[0]
                if name=='device_page' else (root/'tools'/f'{name}.js').read_bytes())
        buffer=io.BytesIO()
        with gzip.GzipFile(fileobj=buffer,mode='wb',filename='',mtime=0) as compressed:
            compressed.write(source)
        data=buffer.getvalue()
        rows=[','.join(f'0x{byte:02x}' for byte in data[offset:offset+24]) for offset in range(0,len(data),24)]
        origin='firmware/src/device_page.h' if name=='device_page' else f'tools/{name}.js'
        text=(f'#pragma once\n// Generated from {origin}; edit that source.\n'
              f'static const unsigned char {symbol}[] PROGMEM={{\n'+',\n'.join(rows)+'\n};\n')
        target=root/'firmware/src'/f'{name}_asset.h'
        if not target.exists() or target.read_text(encoding='utf-8')!=text:
            target.write_text(text,encoding='utf-8')


if '__file__' not in globals():
    Import('env')
    build_assets(Path(env['PROJECT_DIR']).parent)
elif __name__=='__main__':
    build_assets(Path(__file__).resolve().parents[1])
