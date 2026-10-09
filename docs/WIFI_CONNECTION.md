# 不连接电脑 USB，使用 Wi-Fi 采集（Bridge v2.9）

固件为 `doll-lab-2.6.0`，电脑服务为 `doll-bridge-2.10.0`，本机 MCP 共 44 个工具。单纯无线采集仍兼容 v2.2；新增压力校准及日常模式需要升级固件，见 [校准指南](CALIBRATION_AND_DAILY_MODE.md)。

运行链路：娃娃独立供电 → ESP32 局域网 MCP → 电脑 Wi-Fi 采集 → 历史／互动会话 → 用户选择的 AI。电脑端仍可使用 STDIO MCP，传感器数据通过网络到达电脑。

## 供电与网络

- ESP32 必须保持供电。USB 可接普通 5V USB 充电器或移动电源，也可使用已确认接线的板外电池充放电模块给主板 5V/GND 供电；拔掉唯一电源会关机。
- 设备连接 2.4 GHz Wi-Fi，电脑和娃娃需要在可互通的局域网，不能开启阻止设备互访的 AP／访客隔离。
- 从设备设置页或路由器设备列表取得 ESP32 的 IPv4 地址。建议在路由器按 MAC 保留 DHCP 地址，避免重启后 IP 改变。
- 当前采集入口接受私网 IPv4，可附端口；没有 mDNS 自动发现或全网扫描。

## 已在这台电脑用过 USB 的设备

本机已有 `build/device-lab/device-private.json` 时复用已配对的令牌，不必把令牌发给 AI。

先关闭本项目正在运行的旧采集服务，再在项目根目录执行，把 `192.168.1.50` 替换为实际设备 IP：

```powershell
python tools/pair_wifi_device.py --host 192.168.1.50
.\tools\start_companion.ps1 -DeviceHost 192.168.1.50
```

第一条使用已安装项目依赖的 Python，例如 `.\.venv\Scripts\python.exe`。打开 <http://127.0.0.1:8768/companion>，确认显示“设备连接：Wi-Fi”且采集正常，再把 ESP32 从电脑 USB 移到独立电源。若换电源造成重启，等待重新联网，页面会继续采集。

连接方式保存到 `build/device-lab/connection-private.json`。后续运行 `tools/start_companion.ps1` 会复用；无线模式不会打开串口，也不会在断线后自动回退 USB。

## 新电脑，不通过 USB 配对

按 [使用指南](USER_GUIDE.md) 将设备配网并记录管理密码。在设备网页 MCP 设置中取得令牌，然后执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-companion.txt
.\.venv\Scripts\python.exe tools/pair_wifi_device.py --host 192.168.1.50
.\tools\start_companion.ps1 -DeviceHost 192.168.1.50
```

配对程序在终端隐藏输入令牌，不使用命令参数或日志传递令牌。更新令牌加 `--new-token`。连接和设备身份验证成功后才保存；失败不会覆盖原配对。

配对后按 [AI 安装文档](AI_INSTALL.md) 接入 44 工具 STDIO MCP。已有配置可复用。仅使用 MCP 令牌即可采集、设置通道和互动；未配对管理员密码时，电脑首页不能扫描／修改 Wi-Fi，直接使用 ESP32 设置页。无线模式没有远程重启工具，重启用 RST。

## 安装入口与切回 USB

统一入口也接受 IP：

```powershell
.\tools\install_bridge.ps1 -Platform generic -DeviceHost 192.168.1.50
```

已有服务使用不同连接方式时，安装器提示先关闭本项目服务，不会悄悄改变会话。指定方式可使用 `-Transport wifi` 或 `-Transport usb`。

切回 USB 前关闭无线采集服务，再运行：

```powershell
.\tools\start_companion.ps1 -Transport usb -Port COM3
```

同一数据库保留历史、人设、会话和游标。只运行一个采集服务。烧录仍需 USB，先关闭占用串口的服务。

## 断线与保存

- 每约 0.7 秒尝试采集，单次 HTTP 超时约 4 秒。恢复后重新握手，按设备／启动标识及已保存游标补采，避免重复历史。
- 断线时保留已有历史并报告采集不可用，不伪造读数，不重放超时的震动等控制命令。
- v2.5 可缓存最多 256 条 Flash 待补传事件；长时间离线和容量覆盖仍可能丢数据。重启補传、校时及未验收的断电范围见 [离线记录指南](OFFLINE_RECORDS.md)。
- 电脑服务仍需运行才能保存长期历史；本版解除的是电脑 USB 数据连接。
- 普通 ChatGPT Chat 的内网访问与后台唤醒仍取决于平台连接方式和事件支持。

## IP 变化和后台运行

Bridge v2.8 / 固件 v2.4 可查找已配对设备，并在旧地址读取失败时验证新地址。还提供单实例保护、后台启动和可选 Windows 登录启动，见 [无线恢复指南](WIRELESS_RECOVERY.md)。不会自动配对陌生设备或重发电机控制命令。

## 验证

```powershell
python tools/test_device_transport.py
# 服务已切换 Wi-Fi、无用户正在互动、设备处于模拟模式时：
python tools/test_wifi_companion.py
```

实机脚本仅生成 simulation 按压。串口仍存在时会独占它且不发送数据，在此期间验证无线采集、历史、会话和去重；这证明数据不走 USB，不等同于电池供电验收。

令牌、连接配置和个人历史只在本机 `build/`。使用可信内网，数据通过现有设备 HTTP MCP 传输；电脑管理网页仍只监听 127.0.0.1，不会随无线采集开放到公网。
