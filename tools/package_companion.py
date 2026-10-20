"""Package the current code and PCB with explicit public-file allowlists."""
import hashlib
import json
import pathlib
import zipfile
import gzip
import io
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
RELEASE_BASE = 'https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0'
TOOLS = (
    'test_operit_phone.cjs', 'test_operit_server.py', 'operit_server_sdk_runner.cjs', 'test_operit_no_pc_ui.cjs',
    '_source_path.py', 'test_shared_core.py',
    'test_operit_registration.cjs', 'prepare_operit_registration_check.py', 'test_operit_ui_bridge.cjs',
    'test_companion_startup.py', 'test_flash_ui.cjs', 'test_operit_address.cjs', 'test_developer_ui.cjs',
    'companion_experience.py', 'companion_experience.js', 'test_companion_experience.py', 'test_companion_experience_sdk.py', 'test_companion_experience_ui.cjs',
    'flash_esp32.py', 'test_flash_esp32.py', 'flash_server.py', 'flash.html', 'open_flash.ps1', 'test_flash_server.py', 'export_firmware.py', 'test_network_policy.cpp',
    'check_documentation.py', 'operit_service.py', 'package_operit.py', 'test_operit_service.py', 'test_operit_unified.cjs', 'operit_test_host.cjs', 'test_operit_unified_sdk.py', 'operit_unified_sdk_runner.cjs', 'test_operit_setup_ui.cjs',
    'delivery_archive.py', 'test_remote_server_install.py',
    'open_direct_server.ps1', 'start_direct_server.py', 'direct_setup.py', 'test_direct_setup.py', 'test_server_launcher.py',
    'runtime_python.ps1', 'build_portable_python.py', 'test_portable_runtime.py',
    'direct_server.py', 'direct_mcp.py', 'test_direct_mcp.py', 'direct_server.html', 'direct_server.js', 'test_direct_server.py', 'test_direct_frontend.cjs', 'test_uplink_portal.cjs',
    'host_event_forwarder.py', 'test_host_event_forwarder.py', 'test_operit_package.cjs',
    'start_operit_prototype.ps1', 'operit_demo.py', 'test_operit_startup.py', 'test_operit_prototype.cjs',
    'test_operit_prototype_sdk.py', 'operit_prototype_sdk_runner.cjs', 'package_operit_prototype.py', 'test_operit_chat_probe.cjs',
    'control_panel.py', 'control_panel.html', 'control_panel.js', 'console_embed.js', 'open_control_panel.ps1', 'test_control_panel.py', 'test_control_panel_ui.cjs',
    'install_tunnel_client.py', 'secure_mcp.py', 'secure_mcp.ps1', 'test_secure_mcp.py', 'verify_chat_calls.py',
    'remote_mcp.py', 'private_storage.py', 'sakura_frp.py', 'owned_processes.py', 'deploy_mcp.py',
    'remote_mcp.ps1', 'install_chat_mcp.ps1', 'package_remote_plugin.py', 'audit_delivery.py',
    'test_private_mcp.py', 'test_remote_deployment.py', 'test_private_mcp_device.py',
    'Start_Remote_MCP.cmd', 'Stop_Remote_MCP.cmd',
    'chat_mcp_gateway.py', 'test_chat_gateway.py', 'verify_mcp_connection.py',
    'test_bridge_lifecycle.cjs', 'test_bridge_lifecycle_device.cjs',
    'conversation_queue.js', 'test_conversation_queue.cjs',
    'test_existing_chat_mcp.py', 'test_device_contention.py', 'package_chatgpt_plugin.py', 'launch_companion_mcp.ps1',
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
    'channel_editor.js', 'embed_channel_editor.py', 'test_embed_assets.py', 'test_channel_devices.py',
    'test_channel_ui.cjs', 'test_pressure_calibration.cpp',
    'test_sensor_experience.py', 'test_sensor_experience_ui.cjs',
    'interaction_bridge.py', 'webhook_delivery.py', 'mcp_events_adapter.py',
    'bridge_client.js', 'bridge_demo.html', 'install_bridge.ps1',
    'test_interaction_bridge.py', 'test_bridge_ui.cjs', 'test_bridge_protocol.py', 'test_bridge_client.cjs',
    'device_transport.py', 'pair_wifi_device.py', 'test_device_transport.py', 'test_wifi_companion.py',
    'input_observations.py', 'test_input_observations.py',
    'test_feedback_features.py', 'test_feedback_features_ui.cjs',
    'device_discovery.py', 'discover_device.py', 'service_lifecycle.py',
    'run_background.py', 'configure_startup.py', 'test_device_discovery.py', 'test_connection_recovery.py',
    'test_service_lifecycle.py', 'test_wireless_recovery.py', 'test_wireless_recovery_ui.cjs',
)
DOCS = ('integrations/REMOTE_SERVER_SETUP.md', 'integrations/SERVER_QUICKSTART.md', 'reports/SIMPLE_SETUP_ACCEPTANCE.md','daily/RUNTIME_AND_LOGIN.md','developers/DIRECT_SERVER.md', 'reports/DIRECT_SERVER_ACCEPTANCE.md', 'daily/USER_GUIDE.md', 'reports/GUI_ACCEPTANCE_2_14.md', 'developers/EXISTING_CHAT.md', 'developers/MCP_TOOLS.md', 'daily/DIGITAL_TEMPERATURE.md', 'daily/OTA_UPDATE.md', 'daily/HISTORY_MANAGEMENT.md', 'daily/OFFLINE_RECORDS.md', 'start/AI_INSTALL.md', 'daily/USER_GUIDE.md', 'reports/DEVICE_LAB_TEST_REPORT.md', 'daily/SENSOR_CHANNELS.md', 'developers/PROACTIVE_INTERACTION.md', 'integrations/CHAT_MCP.md', 'daily/WIFI_CONNECTION.md', 'daily/CALIBRATION_AND_DAILY_MODE.md', 'developers/DEVELOPMENT_PLAN.md', 'daily/INTERACTION_OBSERVATIONS.md', 'daily/WIFI_CONNECTION.md')
DOCS += ('daily/NATURAL_COMPANION.md', 'reports/RELEASE_2_18.md', 'ai/AI_GUIDE.md', 'TROUBLESHOOTING.md', 'reports/VALIDATION.md', 'developers/DEVELOPER_GUIDE.md', 'start/QUICK_FLASH.md')
DOCS += ('integrations/OPERIT_PROTOTYPE.md', 'reports/OPERIT_PROTOTYPE_VALIDATION.md')
DOCS += ('developers/UNIFIED_DELIVERY_PLAN.md', 'integrations/OPERIT_SETUP.md', 'reports/RELEASE_2_19.md')
DOCS += ('reports/RELEASE_2_19_1.md',)
DOCS += ('integrations/OPERIT_NO_PC.md', 'reports/RELEASE_2_20.md')
DOCS += ('reports/UPDATE_20261019.md', 'reports/RELEASE_2_21.md', 'developers/STABILITY_AND_DAILY_USE_PLAN.md')
SOURCE = ('remote_uplink.h', 'digital_temperature.h', 'ota_update.h', 'event_storage.h', 'event_integrity.h', 'lab_main.cpp', 'device_page.h', 'touch_events.h', 'network_state.h', 'network_policy.h',
          'channel_devices.h', 'channel_rpc.h', 'pressure_calibration.h', 'device_discovery.h')
PREBUILT = ('firmware.bin', 'bootloader.bin', 'partitions.bin', 'boot_app0.bin', 'FLASH_MANIFEST.json', 'README.md')
SHARED_SOURCE = ('src/ai_doll/__init__.py', 'src/ai_doll/core/__init__.py', 'src/ai_doll/core/version.py',
                 'src/ai_doll/core/interaction_bridge.py', 'src/ai_doll/core/input_observations.py',
                 'src/ai_doll/core/history_management.py', 'src/ai_doll/core/companion_experience.py')
PCB_FILES = (
    'AI_Doll_V2_标准化完成_20261003.epro2', 'AI_Doll_V2_标准化采购BOM_20261003.csv',
    'AI_Doll_V2_板外器件与测试点_20261003.csv', '元器件标准化核对记录.md',
    'AI_Doll_V2_丝印镜像修正_20261016.epro2', '丝印镜像修正说明_20261016.md', 'README.md',
)
PCB_PACKAGE = 'AI_Doll_PCB_V2_20261016.zip'
PCB_MIRROR_PROOF = ('audit.json', '3d-confirmation.json', 'bottom-3d-confirmed.png',
                    'bottom-2d-mirrored.png', 'drc-after.json')
PROOF = (
    'standardize-completion-proof.json', 'standardize-sch-final.json',
    'standardize-pcb-list-final.json', 'standardize-pcb-final.json',
    'standardize-pcb-20261003-before.json', 'standardize-pcb-drc-final.json',
    'standardize-sch-drc-final.json', 'standardize-sch-check-final.json',
)
CODE_README = (ROOT/'README.md').read_bytes().decode('utf-8')
PCB_README = '''# AI_Doll_V2 PCB 交付

## 打开工程和准备元器件

1. 在嘉立创 EDA 专业版 V4 导入 `hardware/rev-v2/AI_Doll_V2_丝印镜像修正_20261016.epro2`，包含原理图和 PCB。20261003 工程保留供前版对照。
2. 按同目录的标准化采购 BOM 购买板上器件；SuperMini、FSR、电池与板外充放电模块单独准备。
3. 焊接前读 [器件与电源核对](hardware/rev-v2/元器件标准化核对记录.md)和 [已下单焊位](hardware/rev-v2/ordered-gerber-20260920/已下单PCB封装核对.md)。

## 板子与装配

两层 **34.29 × 44.45mm**，SuperMini 模块、74HC4051 SOIC-16、八路外置 FSR。阻容以 0805 为主，C13 / C14 为 1206。J9 1=GND、2=外部5V；主板不含充电、升压或 BMS。

45 个采购器件已核对立创编号，SuperMini 自行采购，5 个裸铜测试点不采购插针。SW1 额定电流需向卖家确认。

## 验证边界

2026-10-16 已优化丝印位置并修正背面 33 处文字，用户提供的新版 3D 图已确认背面文字正向；两轮保存重载回读通过，电路、铜图形和焊盘保持原样。当前原生 DRC 仍有 1 项网表不匹配，不能沿用 20261003 的 DRC 0 历史结论；重新下单前需单独核对。见 [本次检查说明](hardware/rev-v2/丝印镜像修正说明_20261016.md)。

`ordered-gerber-20260920/` 是原已下单文件，不是新导出的生产文件。`verification/` 保留回读、几何和 DRC 证据。新主板 CH0 实体 FSR 的按压、释放和电脑归档已实测；其余通道、温度、电机和电池仍待验收。完整 [通道教程](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/daily/SENSOR_CHANNELS.md) 与 [当前验证范围](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/reports/VALIDATION.md)分开说明。

逐文件校验见 `MANIFEST.json`。软件另从 [公开交付目录](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/delivery)下载。
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


def server_package(delivery):
    """Small Linux payload: no Windows runtime, firmware images or PCB."""
    names = ['Install_Server.sh', 'LICENSE', 'requirements-server.txt', 'docs/integrations/REMOTE_SERVER_SETUP.md', 'docs/reports/SIMPLE_SETUP_ACCEPTANCE.md', 'docs/daily/NATURAL_COMPANION.md']
    names += ['deploy/direct-server/'+name for name in ('Dockerfile','Dockerfile.dockerignore','compose.yml','compose.backend.yml','Caddyfile','.env.example')]
    names += ['tools/'+name for name in (
        'direct_server.py','direct_mcp.py','companion.py','interaction_bridge.py','input_observations.py',
        'history_management.py','private_storage.py','direct_server.html','direct_server.js',
        'bridge_client.js','conversation_queue.js','channel_editor.js','history_manager.js',
        'console_embed.js','companion.html','companion_experience.py','companion_experience.js')]
    names += list(SHARED_SOURCE) + ['tools/_source_path.py', 'delivery/AI_Doll_Operit.toolpkg', 'docs/integrations/OPERIT_NO_PC.md']
    contents = {name:(ROOT/name).read_bytes() for name in names}
    guide = contents['docs/daily/NATURAL_COMPANION.md'].decode('utf-8').replace('](../developers/EXISTING_CHAT.md)', '](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/developers/EXISTING_CHAT.md)')
    contents['docs/daily/NATURAL_COMPANION.md'] = guide.encode('utf-8')
    contents['docs/README.md'] = ('# Linux 服务包教程\n\n'
        '[远程安装与维护](integrations/REMOTE_SERVER_SETUP.md) · [Operit 无电脑使用](integrations/OPERIT_NO_PC.md) · [自然陪伴](daily/NATURAL_COMPANION.md) · '
        '[已有安装验证记录](reports/SIMPLE_SETUP_ACCEPTANCE.md)\n\n'
        '本小型包只包含服务器所需文件。设备设置、Windows 和 AI 教程见 '
        '[项目完整目录](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/README.md)。\n').encode()
    contents['README.md'] = ('# AI Doll Linux 服务包\n\n'
        '准备 Ubuntu / Debian 服务器，将域名解析到它，并放行 TCP 80 / 443。\n\n'
        '上传并解压此包，在解压目录运行：\n\n'
        '```bash\nsudo bash Install_Server.sh\n```\n\n'
        '按提示填写域名，也可粘贴 HTTPS 首页地址。安装入口自动准备 Docker、配置、持久卷与 HTTPS；'
        '完成后显示管理链接，打开即可连接，不需要娃娃账号或模型密钥。\n\n'
        '在管理页生成设备连接配置，用手机粘贴到娃娃“直连服务器”设置。收到实际上传后才显示在线。\n\n'
        '服务同时提供 Streamable HTTP MCP：在已配对设备下复制 MCP 地址，填入原聊天客户端或服务器后端。默认提供 19 个状态、历史与互动工具。\n\n'
        'Operit 手机可在管理页下载工具包与连接文件，直接使用服务器，无需电脑。见 [Operit 免电脑指南](docs/integrations/OPERIT_NO_PC.md)。\n\n'
        '完整步骤与故障处理见 [远程部署指南](docs/integrations/REMOTE_SERVER_SETUP.md)。'
        '无需上传 Windows Python；不包含个人配置或互动历史。\n').encode()
    manifest = dict(version='ai-doll-server-2.21.0',files={
        name:hashlib.sha256(raw).hexdigest() for name,raw in contents.items()})
    contents['MANIFEST.json'] = json.dumps(manifest,ensure_ascii=False,indent=2).encode()
    output = delivery/'AI_Doll_Server_v2.21.0.tar.gz'
    # Stable tar metadata and gzip timestamps produce reproducible downloads.
    with output.open('wb') as handle, gzip.GzipFile(fileobj=handle,mode='wb',filename='',mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as archive:
            for name,raw in sorted(contents.items()):
                item=tarfile.TarInfo(name);item.size=len(raw);item.mtime=0
                item.mode=0o755 if name.endswith('.sh') else 0o644
                archive.addfile(item,io.BytesIO(raw))
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    checksum=output.with_name(output.name+'.sha256')
    checksum.write_text(digest+'  '+output.name+'\n',encoding='ascii')
    return dict(file=output.name,files=len(manifest['files']),bytes=output.stat().st_size,
                sha256=digest,checksum_file=checksum.name)


def main():
    delivery = ROOT/'delivery'
    files = [ROOT/'Install_Server.sh', ROOT/'AI_Doll_Server.cmd', ROOT/'AI_Doll.cmd', ROOT/'Flash_ESP32.cmd', ROOT/'AGENTS.md', ROOT/'requirements-flash.txt', ROOT/'requirements-flash-runtime.txt', ROOT/'requirements-companion.txt', ROOT/'.gitignore', ROOT/'LICENSE', ROOT/'firmware/platformio.ini']
    from package_operit import build as build_operit, FILES as OPERIT_FILES
    phone_package = build_operit()
    files += [ROOT/'clients/operit'/name for name in OPERIT_FILES]
    files += [ROOT/'delivery/AI_Doll_Operit.toolpkg']
    files += [ROOT/'tools'/name for name in TOOLS]
    files += [ROOT/name for name in SHARED_SOURCE]
    files += [ROOT/'requirements-server.txt', ROOT/'requirements-windows-runtime.lock']
    files += [p for p in (ROOT/'python').rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc'
              and not p.is_relative_to(ROOT/'python/Lib/site-packages/bin')]
    if not (ROOT/'python/python.exe').is_file():
        raise ValueError('Build the portable Python runtime before packaging')
    files += [ROOT/'deploy/direct-server'/name for name in ('Dockerfile','Dockerfile.dockerignore','compose.yml','compose.backend.yml','Caddyfile','.env.example')]
    files += [ROOT/'docs'/name for name in DOCS+('README.md','integrations/HOST_INTEGRATIONS.md','integrations/REMOTE_MCP.md','reports/MCP_ACCEPTANCE_2_13.md','start/MCP_TRANSPORT_DECISION.md','integrations/SECURE_MCP.md')]
    files += [ROOT/'docs'/name for name in ('start/FACTORY_SETTINGS.md','developers/REPOSITORY_LAYOUT.md','reports/RELEASE_2_17.md')]
    files += sorted((ROOT/'docs/images').glob('*.png'))
    files += [ROOT/'templates'/name for name in ('chatgpt-mcp-config.json','README.md','operit/ai_doll.js','operit/ai_doll_prototype.js','operit/ai_doll_chat_probe.js','host-event.example.json','openclaw-hook.example.json')]
    files += [ROOT/'firmware/src'/name for name in SOURCE]
    files += [ROOT/'firmware/prebuilt'/name for name in PREBUILT]
    outputs = [package(delivery/'AI_Doll_Code_v2.21.0.zip', files, CODE_README, 'doll-bridge-2.21.0')]
    hardware = ROOT/'hardware/rev-v2'
    if hardware.exists():
        pcb = [hardware/name for name in PCB_FILES]
        pcb += [hardware/'verification'/name for name in PROOF]
        pcb += [p for p in (hardware/'ordered-gerber-20260920').iterdir() if p.is_file()]
        pcb += [p for p in (hardware/'verification/catalog-20261003').iterdir() if p.suffix in {'.pdf', '.json'}]
        preview = hardware/'verification/standardized-preview/standardized-complete'
        pcb += [p for p in preview.iterdir() if p.is_file() and p.suffix in {'.png','.json'}]
        pcb += [hardware/'verification/silkscreen-mirror-20261016'/name for name in PCB_MIRROR_PROOF]
        outputs.append(package(delivery/PCB_PACKAGE, pcb, PCB_README, 'AI_Doll_V2-silkscreen-corrected-20261016'))
    outputs.append(server_package(delivery))
    outputs.append(dict(phone_package, bytes=(delivery/phone_package['file']).stat().st_size))
    for name in ('AI_Doll_Enclosures_103450_20261020.zip', 'AI_Doll_Enclosure_Stacked_103450_20261020.zip'):
        path = delivery/name
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read('MANIFEST.json'))
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(manifest['files']) | {'MANIFEST.json'}
            for relative, digest in manifest['files'].items():
                assert hashlib.sha256(archive.read(relative)).hexdigest() == digest, relative
        outputs.append(dict(file=name, files=len(manifest['files']), bytes=path.stat().st_size,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (delivery/'DELIVERY_MANIFEST.json').write_text(json.dumps({'packages': outputs}, ensure_ascii=False, indent=2), encoding='utf-8')
    checksums = {item['file']: item['sha256'] for item in outputs}
    for name in ('DELIVERY_MANIFEST.json',):
        checksums[name] = hashlib.sha256((delivery/name).read_bytes()).hexdigest()
    checksums['Install_Server.sh'] = hashlib.sha256((ROOT/'Install_Server.sh').read_bytes()).hexdigest()
    (delivery/'SHA256SUMS.txt').write_text(''.join(digest+'  '+name+'\n' for name,digest in sorted(checksums.items())), encoding='ascii')
    readme = '# 下载与交付文件\n\n**2.21.0 / 固件 2.10.0**，构建更新于2026-10-20。[本版Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.21.0)。服务器与仅手机模式仍需目标环境实测，外壳仍需打印试装。普通Windows用户使用完整包，无需安装Python或Arduino。\n\n'
    readme += '## 应该下载哪个\n\n| 包 | 适合谁 | 解压后做什么 |\n| --- | --- | --- |\n'
    purposes = {
        'AI_Doll_Code_v2.21.0.zip': ('Windows 用户 / 软件开发者', '普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd'),
        'AI_Doll_Server_v2.21.0.tar.gz': ('远程 Linux 服务器', '运行 sudo bash Install_Server.sh，按提示填写域名'),
        PCB_PACKAGE: ('采购和手工焊接主板', '打开新版丝印工程与 BOM；重新下单前核对现有网表不匹配'),
        'AI_Doll_Operit.toolpkg': ('Operit 安卓用户', '在包管理中导入，选择电脑、服务器或仅手机连接，按标题绑定原聊天'),
        'AI_Doll_Enclosures_103450_20261020.zip': ('3D打印与机械修改', '三个候选：旧板平铺、新板平铺、旧板堆叠；按主板选STL或STEP'),
        'AI_Doll_Enclosure_Stacked_103450_20261020.zip': ('只需要旧板上下堆叠壳', '保持原长宽46.29×56.45mm，总厚35.2mm；打印底壳、绝缘载架、上盖'),
    }
    for item in outputs:
        who, action = purposes[item['file']]
        readme += f"| [{item['file']}]({RELEASE_BASE}/{item['file']}) · {item['bytes']/1048576:.2f} MiB | {who} | {action} |\n"
    readme += '\nOperit 无需为了取得手机工具包下载 Windows 包。服务器管理页可导出连接文件；仅手机模式填写家庭设备 IP。原电脑入口继续兼容，完整包仍内含相同工具包。[统一安装](../docs/integrations/OPERIT_SETUP.md) · [免电脑指南](../docs/integrations/OPERIT_NO_PC.md)。\n'
    readme += '\nWindows 包内置 Python，无需另装。Linux 小型包不含 Windows Python，由容器准备运行环境。20261016 PCB 包已优化丝印并修正背面文字，电路与原下单文件保持；当前仍有 1 项网表不匹配，重新下单前须核对。[丝印与 3D 核对](../hardware/rev-v2/丝印镜像修正说明_20261016.md)。\n\n'
    readme += '[Windows 首次安装](../docs/start/AI_INSTALL.md) · [远程部署](../docs/integrations/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/ai/AI_GUIDE.md) · [全部文档](../docs/README.md)\n\n'
    readme += '## 如何校验下载\n\n[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 与 [SHA256SUMS.txt](SHA256SUMS.txt) 记录下载哈希；ZIP / TAR 内的 MANIFEST.json 记录逐文件校验，ToolPkg 使用 CHECKSUMS.json。Linux 包另提供 [.sha256]('+RELEASE_BASE+'/AI_Doll_Server_v2.21.0.tar.gz.sha256)，可运行 sha256sum -c 对应文件名。\n\n'
    readme += '[单独下载 Linux 安装入口]('+RELEASE_BASE+'/Install_Server.sh)。大型文件只存 GitHub Releases，不加入源码仓库。\n\n'
    for item in outputs:
        readme += f"- `{item['file']}`：`{item['sha256']}`\n"
    readme += '\n## 交付范围\n\n公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。\n\n'
    readme += '新板烧录：双击 Flash_ESP32.cmd，点击一键烧录。日常管理：双击 AI_Doll.cmd。手机连接娃娃热点后，固定设置页为 http://192.168.4.1/，配家庭 Wi-Fi 后仍保留。\n\n'
    readme += '每次 USB 烧录产生新内部配对编号；可选择自定义显示名和热点名并保留独立日志；标准烧录保留设置，恢复出厂才清空设备。CH0 实体按压/释放及电脑归档已实测；其他硬件、普通 Chat 空闲唤醒和真实公网部署仍按 [验证汇总](../docs/reports/VALIDATION.md)列出的范围。\n'
    (delivery/'README.md').write_text(readme, encoding='utf-8')
    for item in outputs:
        print(item['file'], item['files'], 'files, verified')


if __name__ == '__main__':
    main()
