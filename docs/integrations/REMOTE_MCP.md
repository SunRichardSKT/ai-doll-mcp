# Sakura 私密 MCP：兼容入口

> 兼容路线排查；普通用户优先使用 Secure 教程。 [全部目录](../README.md)


**当前状态：可信 HTTPS 与 SDK 调用通过，普通 Chat 添加仍失败，原因未确定。** 新用户优先使用已验证的 [Secure 接入](SECURE_MCP.md)。本页保留 Sakura 的开发 / 排查流程。

## 数据通路与范围

ESP32 → 电脑采集 → SQLite → 专用 MCP → Sakura HTTPS。电脑需持续运行，只转发专用 MCP，不转发设置页和数据库。

入口为 `https://主机及端口/64位随机十六进制串/mcp`，随机值由本机生成，重启保留、可重置，其他路径 404。完整地址用于连接，普通 `/mcp` 或管理 URL 不能代替。

工具范围 status / history / interaction 为 2 / 9 / 19，见 [目录](../developers/MCP_TOOLS.md)。本机普通网关与此私密入口默认都用 8771，不能同时启动。

## 已登录 Sakura 客户端时

保留官方客户端的专用隧道，本地 `127.0.0.1:8771`，按 Sakura 当前配置完成 HTTPS。AI Doll 不读取客户端访问密钥，不启动第二个 frpc。

```powershell
.\tools\remote_mcp.ps1 -Action configure -ClientManaged -Profile interaction
.\tools\remote_mcp.ps1 -Action start
```

配置询问 HTTPS 主机地址；停止项目不停止外部客户端。Sakura 域名与证书操作以 [官方指南](https://doc.natfrp.com/bestpractice/domain-bind.html)为准。

## 可选：项目自行管理隧道

先完成 [电脑配对](../start/AI_INSTALL.md)，准备专用隧道 ID、HTTPS 主机和访问令牌；关闭客户端中同一条隧道，避免重复连接。

```powershell
.\tools\remote_mcp.ps1 -Action configure -Profile interaction
.\tools\remote_mcp.ps1 -Action start
```

此模式的令牌用于官方隧道 API，与娃娃设置密码无关。官方客户端下载校验，进程归属和重连由项目管理，不接管其他隧道。

## 检查与停止

```powershell
.\tools\remote_mcp.ps1 -Action status
.\tools\remote_mcp.ps1 -Action verify
.\tools\remote_mcp.ps1 -Action stop
```

verify 需可信证书、工具发现和实际调用；只能证明这次 SDK 路径。普通 Chat 必须另外实际添加并调用，不能用 Secure / Cloudflare 的成功替代。

连接配置在 `build/device-lab/remote-mcp/chatgpt-connection-private.json`。服务操作和地址重置参数可用 `tools/deploy_mcp.py --help` 查看；当前验收见 [MCP 报告](../reports/MCP_ACCEPTANCE_2_13.md)。
