"""Package the current code and PCB with explicit public-file allowlists."""
import hashlib
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = (
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
)
DOCS = ('AI_INSTALL.md', 'USER_GUIDE.md', 'DEVICE_LAB_TEST_REPORT.md', 'SENSOR_CHANNELS.md', 'PROACTIVE_INTERACTION.md', 'CHAT_MCP.md', 'WIFI_CONNECTION.md', 'CALIBRATION_AND_DAILY_MODE.md', 'DEVELOPMENT_PLAN.md', 'INTERACTION_OBSERVATIONS.md')
SOURCE = ('lab_main.cpp', 'device_page.h', 'touch_events.h', 'network_state.h',
          'channel_devices.h', 'channel_rpc.h', 'channel_editor_asset.h', 'pressure_calibration.h')
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
CODE_README = '''# AI 共感娃娃代码 · Bridge v2.6.0 / 固件 v2.3.0

ESP32-C3 SuperMini + 74HC4051。保留现有八路压力接口，支持最多 16 个可配置逻辑通道；预设压力、NTC 温度输入和震动输出。本机 STDIO MCP 提供 35 个工具，开发板 HTTP MCP 提供 22 个工具。电脑桥接服务增加会话绑定事件、可靠投递、SSE 接入与 MCP Events 适配。

- 日常操作：[使用指南](docs/USER_GUIDE.md)。
- 压力校准、启动恢复及曲线：[校准指南](docs/CALIBRATION_AND_DAILY_MODE.md)。
- 动作摘要、安静时段和安装自检：[互动优化指南](docs/INTERACTION_OBSERVATIONS.md)。
- 通道配置与扩展接线：[多传感器指南](docs/SENSOR_CHANNELS.md)。
- 用户自选 AI 接入：[AI 安装文档](docs/AI_INSTALL.md)。
- 无需电脑 USB 数据连接：[Wi-Fi 无线采集](docs/WIFI_CONNECTION.md)。设备独立供电，电脑服务通过局域网保存历史。
- 新建普通聊天与远程连接：[Chat 窗口 MCP 接入指南](docs/CHAT_MCP.md)。GitHub 仓库地址不能代替 MCP 服务地址。
- 主动反馈与统一安装：[事件桥接指南](docs/PROACTIVE_INTERACTION.md)。运行 `tools/install_bridge.ps1`，或使用原入口启动服务。
- 编译目标：`firmware/platformio.ini` 中的 `supermini-lab`。
- 当前源码仅在 `firmware/src/`；已测试镜像和烧录地址见 [固件说明](firmware/prebuilt/README.md)。
- 电脑端入口：`tools/start_companion.ps1 -Port COM3`；MCP 配置生成：`python tools/install_companion_mcp.py`。
- 依赖：Python 3.12，`python -m pip install -r requirements-companion.txt`；编译另需 PlatformIO。
- 本包不包含 Wi-Fi 配置、访问令牌、个人历史或本机依赖。运行数据会在本机 `build/device-lab/` 创建。

默认手动模式关闭真实输入。接线确认后可保存日常模式，重启恢复输入；输出始终不恢复。真实 ADC 需在传感器电路接好后启用；震动电机需外置驱动电路并单独确认启用，不能直接接 GPIO 或 4051。现有 PCB 没有增加物理端口。电脑长期历史支持 Wi-Fi 或 USB 采集，服务需保持运行。普通模式安静归档；主动反馈需要订阅，并由支持事件的宿主或用户 API 应用调用模型。演示页只生成明确标记的测试回执，未选择任何模型或部署公网服务。

每个文件的 SHA-256 见 `MANIFEST.json`。解压后可运行 `python tools/test_companion.py` 检查归档逻辑；设备测试会产生明确标记的模拟记录，使用前请读安装文档。
'''
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
    outputs = [package(delivery/'AI_Doll_Code_v2.6.0.zip', files, CODE_README, 'doll-bridge-2.6.0')]
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
    readme = '# AI 共感娃娃交付说明\n\n更新日期：2026-10-09。电脑 Bridge v2.6 支持 Wi-Fi 采集，已测试开发板固件为 v2.3。请直接发送下面的 ZIP 包；接收者按包内 README 使用。\n\n'
    for item in outputs:
        readme += f"- [{item['file']}]({item['file']})：{item['files']} 个公开文件，{item['bytes']/1048576:.2f} MiB。\n"
    readme += '\n代码包包含当前源码、电脑事件桥、35 工具通用 MCP、MCP Events 适配、统一安装入口、已测试 v2.3 固件四个烧录文件、使用文档及接入指南。PCB 包包含最终嘉立创 EDA 工程、采购 BOM、原下单 Gerber 和检查证据。Bridge v2.6 增加动作摘要、安静时段与自检；校准和日常模式需使用固件 v2.3；PCB 仍为八路模拟接口，实际温度探头与震动驱动需按指南接线。两者无需本机 `.tools` 或历史版本即可解压阅读；编译/运行依赖按代码包说明另行安装。\n\n'
    readme += '交付包不含本机 Wi-Fi 配置、设备访问密钥或个人互动数据库。完整文件校验值在各包的 `MANIFEST.json`；ZIP 校验值在 `DELIVERY_MANIFEST.json`。\n\n'
    for item in outputs:
        readme += f"`{item['file']}` SHA-256：`{item['sha256']}`。\n\n"
    (delivery/'README.md').write_text(readme, encoding='utf-8')
    for item in outputs:
        print(item['file'], item['files'], 'files, verified')


if __name__ == '__main__':
    main()
