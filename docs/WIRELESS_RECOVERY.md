# 无线发现、地址恢复和 Windows 登录启动

2026-10-09，Bridge v2.9 / 设备固件 v2.5。电脑 MCP 提供 44 个工具，开发板为 25 个。现有 Wi-Fi、通道参数和个人历史沿用；开发板需 v2.4 或以上才能回复发现请求。压力校准仍需真实传感器接线。离线缓存需 v2.5，见 [离线记录指南](OFFLINE_RECORDS.md)。

## 日常无线使用

设备用电池或独立电源供电，电脑和设备连接同一可互通局域网。先完成一次配网和配对，见 [无线连接指南](WIFI_CONNECTION.md)。GitHub 代码地址用于安装，不能代替运行中的 MCP 服务地址。

按已保存方式启动电脑采集服务：

```powershell
.\tools\start_companion.ps1 -Background
```

打开 <http://127.0.0.1:8768/>。无线模式显示当前设备 IP，提供“查找已配对娃娃并更新地址”按钮。也可让已安装本机 MCP 的 AI 调用：

```json
{"name":"discover_paired_device","arguments":{"update_connection":true}}
```

默认 `update_connection=false`，只查找。找到设备后才会显示 `found=true`、`verified=true`；明确更新且地址发生改变时 `updated=true`。未收到回复不能证明设备损坏，应检查供电、同一网络、路由器客户端隔离、MCP 开关和防火墙 UDP 广播权限。

电脑服务定时读取失败后，也会尝试查找已配对设备。获得验证正确的新 IP 才保存地址并重试当前读取；发现失败最多每 10 秒尝试一次。不会切换到 USB，也不会重发超时的震动、灯光或配置命令。设备仍在原 IP 时，下一次定时读取会正常重新连接。

独立终端查找：

```powershell
python tools/discover_device.py
```

只有需要在服务停止时把保存方式切换为 Wi-Fi，才运行 `python tools/discover_device.py --save`。运行中的服务请用页面或 MCP 按钮更新，避免外部文件写入与服务状态不一致。

## 可选登录启动

默认不开启。使用项目已安装依赖的 Python；如果按安装指南建立了虚拟环境，就使用该虚拟环境。先预览命令，再按需安装：

```powershell
.\.venv\Scripts\python.exe tools/configure_startup.py install --dry-run
.\.venv\Scripts\python.exe tools/configure_startup.py install
```

安装后，在此 Windows 用户下次登录时隐藏启动电脑采集服务，沿用保存的连接方式和配对。它不会在安装时启动或停止当前服务；也不会启动 AI 客户端、注册客户端 MCP 或保证聊天自动回复。电脑睡眠、关机或服务停止期间不会持续采集长期历史。

查询或取消：

```powershell
.\.venv\Scripts\python.exe tools/configure_startup.py status
.\.venv\Scripts\python.exe tools/configure_startup.py remove
```

只修改当前项目对应的一个用户启动项。移动项目或虚拟环境后，用原目录移除旧启动项，再从新目录安装。路径含空格可用。日志在本机 `build/device-lab/background-service.log`，最大 512 KiB，最多两份轮转文件；不进入交付包。

同一项目只能持有一个采集服务锁，重复启动会退出。服务崩溃后操作系统自动释放锁；磁盘上遗留 `companion.lock` 文件不是“服务仍运行”的证据，无需手动删除。另一个程序占用 8768 时会先退出，不会打开串口或修改设备配对、连接信息和互动数据库。

## 发现协议与范围

电脑在实际私有 IPv4 接口的广播地址向 UDP 28768 发送协议名、一次性随机码和已配对设备 ID。请求不含密码或 MCP 令牌。ESP32 在已连接 Wi-Fi 且启用 MCP 时，向同一子网的请求者回复设备 ID、固件版本、端口和 HMAC-SHA256 证明；电脑验证随机码、身份和证明后，才采用 UDP 来源 IP。

这不能代替首次配对，也不提供加密 HTTP。只在可信局域网使用；不要将管理页面、设备 HTTP MCP 或发现端口直接公开到互联网。广播发现不跨 VLAN；路由器隔离或 UDP 被拦截时，可按原指南手动输入设备 IP。Windows 多网卡按各自实际前缀广播，不假定所有网络都是 `/24`。

## 已测试和待验收

自动化测试覆盖伪造、旧随机码、错误身份、错误端口、公开地址、异常 JSON、UDP 往返、读取恢复、修改操作不重发、保存失败不更换地址、单实例锁和异常退出释放。

真实裸开发板验收记录见 [实测报告](DEVICE_LAB_TEST_REPORT.md)。使用故意错误的旧地址验证恢复，不等同于实际强制更换路由器 DHCP 租约。Windows 登录启动只预览检查，不默认替用户启用；真正重新登录与电池供电仍需使用环境验收。无传感器时仅验证模拟事件，不代表真实压力校准通过。

v2.5 已实现有界持久缓存和软件重启补传，见 [离线记录指南](OFFLINE_RECORDS.md)。容量覆盖、写入失败或未提交时断电仍可能丢数据，不能承诺保存全部互动。电脑 v2.9 已提供默认关闭的保留策略，见 [历史管理指南](HISTORY_MANAGEMENT.md)。
