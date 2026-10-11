# IP 改变、断线与登录自动启动

适用于已经配对的电脑 MCP 通路。配对身份不变时，程序验证新 IP 后更新，不清空网络、通道或历史。

## 找回已配对设备

在管理中心“设备连接”点击查找已配对设备。先检查供电、同一可互通局域网、MCP 已开启，访客网或 VLAN 广播隔离可能阻止发现。

本机 MCP 可调用 `discover_paired_device(update_connection=true)`。默认只查找；`found=true` 与 `verified=true` 才说明找到并验证，`updated=true` 表示明确更新了地址。失败不能说明设备损坏。

读取失败后采集器也会尝试查找，发现失败最多每 10 秒再试。它不切换 USB，不重发超时控制。设备回到原 IP 时下一轮读取可恢复。

独立终端可运行：

```powershell
.\python\python.exe tools/discover_device.py
```

服务停止时才用 `--save` 更新保存方式；运行中优先用页面或 MCP，避免文件与进程状态不一致。

## 可选：Windows 登录后自动采集

默认不开启。在管理中心维护页按需设置；命令入口：

```powershell
.\python\python.exe tools/configure_startup.py install --dry-run
.\python\python.exe tools/configure_startup.py install
.\python\python.exe tools/configure_startup.py status
.\python\python.exe tools/configure_startup.py remove
```

它只在下次当前用户登录时隐藏启动采集，不启动 AI 客户端，不证明聊天会主动回复。只修改本项目启动项。移动目录前移除旧项，移动后重新安装。

同一项目只有一个采集实例。锁文件留在磁盘不表示进程仍在，崩溃后锁由系统释放；不要靠删锁文件启动第二个采集器。其他程序占用 8768 时退出，不接管。

## 开发参考与验证边界

发现使用 UDP 28768：请求包含一次性随机码和已配对 ID，响应验证 HMAC-SHA256、随机码及来源，采用实际子网广播地址，不假定 /24。它不是首次配对，也不加密后续 HTTP，不跨 VLAN。

自动化覆盖伪造、重放、错误身份、保存失败、单实例和读取恢复；裸板测试用错误旧地址验证恢复，不等于强制修改真实 DHCP 租约。Windows 真实重新登录、电池供电另行验收。

补传容量有限，见 [离线记录](OFFLINE_RECORDS.md)；一般错误见 [故障排查](TROUBLESHOOTING.md)。
