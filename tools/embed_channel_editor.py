"""PlatformIO pre-build: embed the same JS used by the computer page in flash."""
from pathlib import Path
if '__file__' in globals():
    root=Path(__file__).resolve().parents[1]
else:
    Import('env')
    root=Path(env['PROJECT_DIR']).parent
source=(root/'tools/channel_editor.js').read_text(encoding='utf-8')
assert ')CHANNEL_JS"' not in source
target=root/'firmware/src/channel_editor_asset.h'
text='#pragma once\n// Generated from tools/channel_editor.js; edit that source.\nstatic const char CHANNEL_EDITOR_JS[] PROGMEM=R"CHANNEL_JS('+source+')CHANNEL_JS";\n'
if not target.exists() or target.read_text(encoding='utf-8')!=text:
    target.write_text(text,encoding='utf-8')
source=(root/'tools/ota_manager.js').read_text(encoding='utf-8')
assert ')OTA_JS"' not in source
target=root/'firmware/src/ota_manager_asset.h'
text='#pragma once\n// Generated from tools/ota_manager.js.\nstatic const char OTA_MANAGER_JS[] PROGMEM=R"OTA_JS('+source+')OTA_JS";\n'
if not target.exists() or target.read_text(encoding='utf-8')!=text:
    target.write_text(text,encoding='utf-8')
