# AI 共感娃娃 · V2 交付工程

当前版本：固件 **doll-lab-2.3.0**；硬件 **AI_Doll_V2 / ESP32-C3 SuperMini + 74HC4051 / 八路模拟接口**。最多 16 个逻辑通道，预设压力、NTC 温度输入及震动输出；用户自行选择 AI 平台，通过通用 MCP 接入。

电脑服务为 **Bridge v2.5.0**，本机 STDIO MCP 为 **33 个工具**。支持局域网 Wi-Fi 采集，保留持久事件投递、会话目标绑定、自建应用 SSE、反馈偏好与 MCP Events；新增压力校准、日常模式及实时诊断，需要升级固件至 v2.3。无需电脑 USB 数据连接的运行方式见 [无线连接指南](docs/WIFI_CONNECTION.md)，跨平台接入见 [主动互动指南](docs/PROACTIVE_INTERACTION.md)。

## 在新的聊天窗口接入

让 AI 在线阅读 [Chat 窗口 MCP 接入指南](docs/CHAT_MCP.md)。GitHub 仓库提供源码、交付文件和安装说明；仓库网址不是 MCP 服务地址，GitHub Pages 也不能运行 USB 采集服务。

支持本机工具的 AI 客户端可以按 [AI 安装文档](docs/AI_INSTALL.md) 安装 STDIO MCP。普通 ChatGPT Chat 需要在平台中连接可达、经过认证的远程 MCP 服务／受支持的安全隧道，再在新聊天中选择相应插件。本项目已经提供本机 MCP 2.0 接口，但尚未注册远程连接，也没有公开用户电脑端口。

普通聊天可调用工具查询互动历史；按压后唤醒已空闲的官方聊天窗口还取决于宿主事件支持，不能仅靠发布 GitHub 仓库实现。

## 直接交付

打开 [交付说明](delivery/README.md)，其中列出代码包、PCB 包和文件校验值。交付包采用明确的文件清单，排除本机密钥、Wi-Fi 配置、个人互动历史、工具依赖和历史版本。

## 使用

1. 阅读 [使用指南](docs/USER_GUIDE.md) 和 [多传感器通道指南](docs/SENSOR_CHANNELS.md)。本地 Word v2.1 手册仅作旧版基本操作参考。
2. 设备已联网且配对时，独立供电并运行 `tools/start_companion.ps1 -DeviceHost 192.168.1.50`（替换实际 IP）。首次配对见 [无线连接指南](docs/WIFI_CONNECTION.md)。USB 方式仍可运行 `tools/start_companion.ps1 -Transport usb -Port COM3`。
3. 打开 <http://127.0.0.1:8768/companion> 设置通道类型、部位、驱动与参数，设置人设、查询混合传感器历史及模拟测试。
4. 让用户选择的 AI 阅读 [AI 安装文档](docs/AI_INSTALL.md)，安装通用 STDIO MCP。
5. 主动推送测试打开 <http://127.0.0.1:8768/bridge>；页面显示明确标记的演示回执。自建模型应用接入事件回调，ChatGPT Work 接入需要支持事件的账号和远程连接／隧道。

默认手动模式，重启关闭真实输入；装好传感器并确认保存日常模式后，重启恢复真实输入。输出始终不自动恢复。压力校准和诊断见 [校准指南](docs/CALIBRATION_AND_DAILY_MODE.md)；震动电机必须接外置驱动电路并确认启用输出。16 个逻辑通道不代表 16 个物理 ADC，现有 PCB 保持八路。BOOT 运行中长按约 3 秒重新配网；RST 重启并保留配置。长期历史由电脑采集服务保存，可通过 Wi-Fi 或 USB 连接设备；电脑服务需保持运行。

## 编译和测试

推荐 Python 3.12。新电脑先安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-companion.txt
.\.venv\Scripts\python.exe -m pip install platformio
.\tools\build_lab.ps1
```

烧录前关闭占用串口的采集服务：

```powershell
.\tools\build_lab.ps1 -Upload -Port COM3
```

`firmware/prebuilt/` 保留经过裸开发板测试的 v2.3.0 镜像、分区表、引导文件和烧录地址清单。当前唯一编译目标为 `supermini-lab`。归档逻辑测试为 `python tools/test_companion.py`；实机多传感器测试为 `python tools/test_channel_devices.py`，要求设备及采集服务运行，使用前阅读安装文档。

重新生成交付包：

```powershell
python tools/package_companion.py
```

## 目录

| 目录 | 内容 |
|---|---|
| `firmware/src/` | 当前 4051 固件及设备网页 |
| `firmware/prebuilt/` | 已测试的固件镜像与烧录说明 |
| `tools/` | 电脑采集、MCP、编译、测试和打包脚本 |
| `docs/` | 使用、多传感器扩展、AI 安装、当前测试记录和旧版 Word 参考 |
| `hardware/rev-v2/` | 最终 EDA 工程、BOM、已下单 Gerber 和检查证据 |
| `delivery/` | 可以直接发送的两个交付包及交付清单 |
| `build/device-lab/` | 本机访问配置、个人历史和实测记录，不交付 |
| `.tools/` | 本机编译及 EDA/MCP 运行依赖，不交付 |
| `_local/` | 历史资料归档及目录整理记录，不交付 |

早期 4067/Wokwi 代码、Rev A/B 设计和旧版导出已移出工作目录，集中保留于 `_local/`。当前 PCB 为两层 **34.29 × 44.45 mm**，标准化检查的 PCB DRC 为 **0 项违规**；C13/C14 保留已下单板的 1206，其余阻容为 0805。
