"""Package the current code and PCB with explicit public-file allowlists."""
import hashlib
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = (
    'test_bridge_lifecycle.cjs', 'test_bridge_lifecycle_device.cjs',
    'conversation_queue.js', 'test_conversation_queue.cjs',
    'test_existing_chat_mcp.py', 'package_chatgpt_plugin.py', 'launch_companion_mcp.ps1',
    'test_digital_temperature.cpp', 'test_digital_mcp.py', 'test_digital_ui.cjs', 'test_digital_device.py',
    'ota_device.py', 'ota_manager.js', 'test_ota.py', 'test_ota_ui.cjs',
    'history_management.py', 'history_manager.js', 'test_history_management.py',
    'test_history_ui_fixture.py', 'test_history_ui.cjs', 'test_history_sdk.py', 'test_history_mcp.py',
    'test_offline_archive.py', 'test_offline_device.py', 'test_offline_ui.cjs',
    'test_serial_transport.py', 'test_event_integrity.cpp',
    'build_lab.ps1', 'start_companion.ps1', 'install_companion_mcp.py',
    'device_setup_server.py', 'device_lab.py', 'companion.py',
    'companion_mcp.py', 'companion.html', 'test_companion.py',
    'test_companion_device.py', 'test_companion_ui.cjs',
    'test_mcp_sdk_device.py', 'test_device_portal.cjs', 'package_companion.py',
    'channel_editor.js', 'embed_channel_editor.py', 'test_channel_devices.py',
    'test_channel_ui.cjs', 'test_pressure_calibration.cpp',
    'test_sensor_experience.py', 'test_sensor_experience_ui.cjs',
    'interaction_bridge.py', 'webhook_delivery.py', 'mcp_events_adapter.py',
    'bridge_client.js', 'bridge_demo.html', 'install_bridge.ps1',
    'test_interaction_bridge.py', 'test_bridge_ui.cjs', 'test_bridge_protocol.py', 'test_bridge_client.cjs',
    'device_transport.py', 'pair_wifi_device.py', 'test_device_transport.py', 'test_wifi_companion.py',
    'input_observations.py', 'test_input_observations.py',
    'test_feedback_features.py', 'test_feedback_features_ui.cjs',
    'device_discovery.py', 'discover_device.py', 'service_lifecycle.py',
    'run_background.py', 'configure_startup.py', 'test_device_discovery.py',
    'test_service_lifecycle.py', 'test_wireless_recovery.py', 'test_wireless_recovery_ui.cjs',
)
DOCS = ('EXISTING_CHAT.md', 'MCP_TOOLS.md', 'DIGITAL_TEMPERATURE.md', 'OTA_UPDATE.md', 'HISTORY_MANAGEMENT.md', 'OFFLINE_RECORDS.md', 'AI_INSTALL.md', 'USER_GUIDE.md', 'DEVICE_LAB_TEST_REPORT.md', 'SENSOR_CHANNELS.md', 'PROACTIVE_INTERACTION.md', 'CHAT_MCP.md', 'WIFI_CONNECTION.md', 'CALIBRATION_AND_DAILY_MODE.md', 'DEVELOPMENT_PLAN.md', 'INTERACTION_OBSERVATIONS.md', 'WIRELESS_RECOVERY.md')
SOURCE = ('digital_temperature.h', 'ota_update.h', 'ota_manager_asset.h', 'event_storage.h', 'event_integrity.h', 'lab_main.cpp', 'device_page.h', 'touch_events.h', 'network_state.h',
          'channel_devices.h', 'channel_rpc.h', 'channel_editor_asset.h', 'pressure_calibration.h', 'device_discovery.h')
PREBUILT = ('firmware.bin', 'bootloader.bin', 'partitions.bin', 'boot_app0.bin', 'FLASH_MANIFEST.json', 'README.md')
PCB_FILES = (
    'AI_Doll_V2_标准化完成_20261003.epro2', 'AI_Doll_V2_标准化采购BOM_20261003.csv',
    'AI_Doll_V2_板外器件与测试点_20261003.csv', '元器件标准化核对记录.md',
)
PROOF = (
    'standardize-completion-proof.json', 'standardize-sch-final.json',
    'standardize-pcb-list-final.json', 'standardize-pcb-final.json',
    'standardize-pcb-20261003-before.json', 'standardize-pcb-drc-final.json',
    'standardize-sch-drc-final.json', 'standardize-sch-check-final.json',
)
CODE_README = '# AI 共感娃娃代码交付\n\n固件 2.7.0 / 电脑 Bridge 2.12.2。ESP32-C3 SuperMini + 74HC4051，保留八路模拟接口和最多 16 个逻辑通道。电脑 MCP 45 个工具，设备 MCP 26 个工具。\n\n先读 [安装指南](docs/AI_INSTALL.md)，完成配网、电脑服务、无线配对和客户端 MCP 导入。日常操作见 [使用指南](docs/USER_GUIDE.md)，FSR402 校准和手动阈值见 [校准指南](docs/CALIBRATION_AND_DAILY_MODE.md)。\n\n- [接入现有对话](docs/EXISTING_CHAT.md)\n- [完整 MCP 工具目录](docs/MCP_TOOLS.md)\n- [通道与接线](docs/SENSOR_CHANNELS.md)、[DS18B20 数字温度](docs/DIGITAL_TEMPERATURE.md)\n- [主动互动与 API 接入](docs/PROACTIVE_INTERACTION.md)、[聊天窗口](docs/CHAT_MCP.md)\n- [无线采集](docs/WIFI_CONNECTION.md)、[地址恢复与登录启动](docs/WIRELESS_RECOVERY.md)\n- [反馈偏好与自检](docs/INTERACTION_OBSERVATIONS.md)\n- [离线缓存](docs/OFFLINE_RECORDS.md)、[历史管理](docs/HISTORY_MANAGEMENT.md)\n- [无线升级](docs/OTA_UPDATE.md)、[烧录镜像](firmware/prebuilt/README.md)\n- [实际验收范围](docs/DEVICE_LAB_TEST_REPORT.md)、[剩余工作](docs/DEVELOPMENT_PLAN.md)\n\n在项目根目录运行 tools/install_bridge.ps1。首次安装需要 Python 3.12 和依赖，详见安装指南；无需交付者本机依赖。源码在 firmware/src，编译目标为 supermini-lab。\n\n未接传感器保持模拟/手动模式。真实震动需要板外驱动，不能直接接 GPIO 或 4051。普通触摸只记录，用户开始互动后才投递新事件；自建应用接入用户选择的模型回调，官方客户端的后台唤醒取决于其实际事件能力。\n\n此包不含 Wi-Fi、令牌、个人日志或历史版本。运行数据在本机 build/device-lab 创建。MANIFEST.json 包含每个文件的 SHA-256。真实传感器、用户模型和写 Flash 时物理断电仍需验收。\n'
PCB_README = '''# AI_Doll_V2 PCB 交付

最终工程在 `hardware/rev-v2/AI_Doll_V2_标准化完成_20261003.epro2`，使用嘉立创 EDA 专业版打开/导入原生工程。BOM 和检查记录在同一目录。

- 两层，34.29 × 44.45 mm，74HC4051 / SOIC-16，ESP32-C3 SuperMini 模块。
- 八路外置 FSR402，主板仅接板外充放电模块的 5V/GND。
- 手焊方案：阻容以 0805 为主；C13/C14 保留已下单板的 1206。
- 45 个板上采购器件已核对立创编号，SuperMini 自行采购，5 个裸铜测试点不采购。
- PCB 原生 DRC 为 0 项违规；原理图 DRC 无 error/fatal，仍有 2 项聚合警告，详见核对记录。
- SW1 手册未明确额定电流，采购时向卖家确认。

`ordered-gerber-20260920/` 是已下单文件及封装核对资料，保留为实物板依据，并非本次重新导出的生产文件。本次标准化前后焊盘、走线、铺铜、板框及位号镜像相同，不需仅因料号标准化重新下单。

`verification/` 保留最终回读、DRC、几何比较和数据手册证据。截图为客户端整板视口图，不是对象级图像导出。工程导出结构已核验，本轮未将其导入另一工程测试恢复。

每个文件的 SHA-256 见 `MANIFEST.json`。
'''


def package(output, files, readme, version):
    files = sorted(set(files))
    for p in files:
        if not p.is_file():
            raise FileNotFoundError(p)
        relative = p.relative_to(ROOT)
        if any(part in {'build', '.tools', '_local', '.pio', '__pycache__'} for part in relative.parts):
            raise ValueError('Local/private path cannot enter a delivery package')
    manifest = {'version': version, 'files': {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    manifest['files']['README.md'] = hashlib.sha256(readme.encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep an unchanged verified package byte-identical, including its ZIP dates.
    # This avoids republishing the PCB merely because code was updated.
    if output.exists() and zipfile.is_zipfile(output):
        try:
            with zipfile.ZipFile(output) as archive:
                cached = json.loads(archive.read('MANIFEST.json'))
                expected = set(manifest['files']) | {'MANIFEST.json'}
                if (cached == manifest and set(archive.namelist()) == expected and
                        archive.testzip() is None and all(hashlib.sha256(archive.read(name)).hexdigest() == digest
                        for name, digest in manifest['files'].items())):
                    return {'file': output.name, 'files': len(manifest['files']), 'bytes': output.stat().st_size,
                            'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
        except (OSError, ValueError, KeyError, zipfile.BadZipFile):
            pass
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in files:
            archive.write(p, p.relative_to(ROOT).as_posix())
        archive.writestr('README.md', readme)
        archive.writestr('MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Delivery ZIP integrity check failed')
        for name, digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('Delivery file checksum mismatch: ' + name)
    return {'file': output.name, 'files': len(manifest['files']), 'bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
    delivery = ROOT/'delivery'
    files = [ROOT/'requirements-companion.txt', ROOT/'.gitignore', ROOT/'firmware/platformio.ini']
    files += [ROOT/'tools'/name for name in TOOLS]
    files += [ROOT/'docs'/name for name in DOCS]
    files += [ROOT/'firmware/src'/name for name in SOURCE]
    files += [ROOT/'firmware/prebuilt'/name for name in PREBUILT]
    outputs = [package(delivery/'AI_Doll_Code_v2.12.2.zip', files, CODE_README, 'doll-bridge-2.12.2')]
    hardware = ROOT/'hardware/rev-v2'
    if hardware.exists():
        pcb = [hardware/name for name in PCB_FILES]
        pcb += [hardware/'verification'/name for name in PROOF]
        pcb += [p for p in (hardware/'ordered-gerber-20260920').iterdir() if p.is_file()]
        pcb += [p for p in (hardware/'verification/catalog-20261003').iterdir() if p.suffix in {'.pdf', '.json'}]
        preview = hardware/'verification/standardized-preview/standardized-complete'
        pcb += [p for p in preview.iterdir() if p.is_file() and p.suffix in {'.png','.json'}]
        outputs.append(package(delivery/'AI_Doll_PCB_V2_20261003.zip', pcb, PCB_README, 'AI_Doll_V2-standardized-20261003'))
    (delivery/'DELIVERY_MANIFEST.json').write_text(json.dumps({'packages': outputs}, ensure_ascii=False, indent=2), encoding='utf-8')
    readme = '# AI 共感娃娃交付说明\n\n更新日期：2026-10-10。电脑 Bridge v2.12.2 支持 Wi-Fi 采集，已测试开发板固件为 v2.7。请直接发送下面的 ZIP 包；接收者按包内 README 使用。\n\n'
    for item in outputs:
        readme += f"- [{item['file']}]({item['file']})：{item['files']} 个公开文件，{item['bytes']/1048576:.2f} MiB。\n"
    readme += '\n代码包包含当前固件四个烧录文件、源码、45 工具 MCP、电脑事件桥、安装工具和当前使用文档。支持八路 FSR 校准、首次配网、Wi-Fi 数据、温度/震动扩展、有限离线缓存、历史管理与无线升级。PCB 包包含嘉立创 EDA 工程、BOM、原下单文件和核对证据。编译/运行依赖由接收者按代码包指南安装。实物传感器和实际模型反馈验收仍待完成。\n\n'
    readme += '交付包不含本机 Wi-Fi 配置、设备访问密钥或个人互动数据库。完整文件校验值在各包的 `MANIFEST.json`；ZIP 校验值在 `DELIVERY_MANIFEST.json`。\n\n'
    for item in outputs:
        readme += f"`{item['file']}` SHA-256：`{item['sha256']}`。\n\n"
    (delivery/'README.md').write_text(readme, encoding='utf-8')
    for item in outputs:
        print(item['file'], item['files'], 'files, verified')


if __name__ == '__main__':
    main()
