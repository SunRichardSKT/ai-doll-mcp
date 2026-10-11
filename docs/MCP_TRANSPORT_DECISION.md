# 先选连接方式

先看你使用哪个 AI，以及数据保存在哪里。不要把 GitHub、管理页或设备设置页当成 MCP 服务地址。

| 你的场景 | 优先使用 | 是否需要电脑常开 | 项目验证 |
| --- | --- | --- | --- |
| ChatGPT 普通 Chat | [Secure MCP Tunnel](SECURE_MCP.md) | 是 | 状态、历史、60 秒模拟文字反馈通过 |
| 支持本地 MCP 的桌面客户端 | [STDIO 配置](AI_INSTALL.md) | 是 | 官方 SDK 45 工具、当前 Work 模拟互动通过 |
| 自己的前后端，先在本机测试 | [本机接收服务](SERVER_QUICKSTART.md) | 是，电脑就是服务器 | 设备直传与测试回调通过 |
| 自己的前后端，部署到云端 | [Linux 快捷部署](REMOTE_SERVER_SETUP.md) | 否，服务器需运行 | 隔离 Linux 测试通过；真实公网待验收 |

## 普通 Chat 的备用入口

| 方式 | 本项目实际结果 | 日常注意 |
| --- | --- | --- |
| Secure | 13 工具及普通 Chat 模拟互动通过 | 首次配置 Platform 隧道和运行密钥，后续使用同一隧道 ID |
| Cloudflare 临时隧道 | 普通 Chat 两个状态工具通过 | 临时地址不能当长期固定连接；完整互动未在此路线验收 |
| Cloudflare 固定域名 | 尚未部署验收 | 需用户自己的账号、域名与实际部署 |
| Sakura | HTTPS、SDK 工具调用通过，普通 Chat 添加失败 | 保留 [兼容操作](REMOTE_MCP.md)，不能宣称已修好 |

这是按项目的实际验收范围选择，不是对不同服务延迟、收费或可用性的排名。Secure 的账号权限见 [官方说明](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)。

## “完全本地”指什么

本机脚本、SQLite 和 STDIO 可不使用公网隧道；如果原 AI 使用云端模型，工具返回数据仍会发送给该平台。上传插件 ZIP 不会运行本机脚本，不能绕过服务连接。

## 什么时候可以主动发消息

普通 Chat 已验证的是主动开始后的限时等待，不是空闲自动唤醒。自己的应用可接 [事件桥](PROACTIVE_INTERACTION.md)并在原聊天回应。客户端有无后台事件能力需要各自实测。

详细证据见 [验证汇总](VALIDATION.md)。新手选定一条路径即可，不必同时安装所有隧道。
