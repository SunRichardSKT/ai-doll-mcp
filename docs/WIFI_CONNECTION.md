# Wi-Fi 配对与独立供电

配网和配对是两件事：配网让 ESP32 接入路由器；配对让电脑确认并读取你的设备。

## 推荐操作

1. 按 [配网步骤](USER_GUIDE.md#首次配网)连接 2.4 GHz 网络。
2. 电脑和设备连接可互通的局域网，避免访客网络或客户端隔离。
3. 双击 `AI_Doll.cmd`，在“设备连接”通过 USB 一次识别并配对 Wi-Fi，或手工输入设备 IP 与 MCP 令牌验证。
4. 检查连接方式为 Wi-Fi、最后同步时间更新，随后可用独立电源。

主板只接受外部 5V / GND：可用 USB 电源，也可从板外单节锂电充放电模块的 5V OUT 接 J9。拔掉唯一电源会关机；主板没有充电电路。

## 开发者命令入口

在项目根目录执行，替换真实 IP：

```powershell
.\python\python.exe tools/pair_wifi_device.py --host 192.168.1.50
.\tools\start_companion.ps1 -DeviceHost 192.168.1.50
```

令牌在设备页取得，输入隐藏；已有配对复用令牌，需要换令牌时使用 `--new-token`。验证成功才保存。日常使用 `AI_Doll.cmd` 或 `start_companion.ps1 -Background`。

## 切换 USB 或断线

切换 USB 前先停无线采集，再使用 `start_companion.ps1 -Transport usb -Port 实际串口`。两种方式使用同一个电脑历史库；Wi-Fi 失败不会自动退回 USB，控制命令也不会自动重发。

IP 变化按 [地址恢复](WIRELESS_RECOVERY.md)处理，旧记录按 [离线缓存](OFFLINE_RECORDS.md)补传。保持一个主采集器。局域网 HTTP 与管理页面不直接映射公网。

没有配置网页保护时，设备设置默认免登录；开启后电脑修改网络或 OTA 才需保存对应账号密码，见 [登录说明](RUNTIME_AND_LOGIN.md)。真实电池使用和实体 FSR 仍需实物验收。
