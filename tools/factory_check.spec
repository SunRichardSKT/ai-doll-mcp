# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parent
excluded = ['control_panel', 'device_transport', 'private_storage', 'http_mcp_server',
            'numpy', 'pandas', 'matplotlib', 'scipy', 'PIL', 'flask', 'pytest', 'mcp']
assets = [(str(root/'firmware/prebuilt'/name), 'firmware/prebuilt')
          for name in ('FLASH_MANIFEST.json', 'bootloader.bin', 'partitions.bin', 'boot_app0.bin', 'firmware.bin')]
a = Analysis([str(root/'tools/factory_check.py')], pathex=[str(root/'tools')],
             datas=assets, excludes=excluded)
worker = Analysis([str(root/'tools/factory_esptool.py')], pathex=[str(root/'tools')],
                  datas=collect_data_files('esptool'), excludes=['tkinter', *excluded])
gui = EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True,
          name='AI_Doll_Factory', console=False, icon='NONE')
cli = EXE(PYZ(worker.pure), worker.scripts, [], exclude_binaries=True,
          name='esptool-worker', console=True, icon='NONE', contents_directory='.')
package = COLLECT(gui, cli, a.binaries, a.datas, worker.binaries, worker.datas,
                  name='一代批量检测')
