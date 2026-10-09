# 在原聊天窗口使用娃娃

继续使用原 AI、模型、人设与上下文。设备网页用于配网、校准、通道和日志管理。MCP 提供身体互动数据，回复由正在使用的 AI 产生。

## 选择连接方式

| 使用环境 | 连接 | 已验证范围 |
| --- | --- | --- |
| 支持本机 MCP 的 Agent，例如 Claude Code、Harness | 本机 STDIO，无需公网映射 | 官方 SDK 实测 45 工具及设备状态；具体客户端仍需实际导入 |
| 支持本机 HTTP 的客户端或私有隧道上游 | Streamable HTTP，`127.0.0.1:8771/mcp` | 13 工具发现、Wi-Fi 模拟按压开始/释放、会话结束 |
| 普通 Chat | 账号侧实际可达的 HTTPS MCP 或 Secure MCP Tunnel | 本轮已通过两个只读状态工具；互动反馈尚未验收 |
| 用户已有 API 应用 | 原聊天后端接入事件桥 | 队列、会话绑定、取消和去重专项通过；原模型实测待完成 |

阅读 GitHub 或上传代码 ZIP 不能代替 MCP 连接。云端客户端所见的 localhost 也不是用户电脑。仅在局域网使用时，选择本机 Agent 或已有应用即可。

## 本地安装

按 [安装指南](AI_INSTALL.md) 运行统一入口、完成首次配对并生成 `mcp-client-config.json`。在原客户端导入 STDIO 配置，刷新工具，再实际查询状态。支持提示模板的宿主可选择 `doll_chat_companion`；没有该菜单时使用 [接入现有对话](EXISTING_CHAT.md) 的测试请求。

## 本机 HTTP 互动接口

先启动已配对的采集服务，再运行：

```powershell
.\.venv\Scripts\python.exe tools/chat_mcp_gateway.py --profile interaction
```

地址为 `http://127.0.0.1:8771/mcp`。只监听本机，进程需持续运行；按 Ctrl+C 关闭。它复用现有采集、会话、人设和历史，不额外连接模型，不开启公开隧道，不自动注册账号插件。

互动配置提供 13 个工具：两个状态工具，通道能力与配置，人设与偏好，会话开始/状态/事件/结束，以及混合历史、动作摘要和历史统计。不会提供设备输出、真实采样启用、模拟注入或历史删除工具。模拟按压由用户在本机 `/companion` 页面操作。

工具返回 `verification.run_id` 和 `verification.call_id`，本机 `calls.jsonl` 只记录调用编号、工具和完成状态，不记录人设、部位或历史内容。SDK 产生的编号只能证明 SDK 调用，不能充当目标 Chat 的证据。

可用下面的命令检查本机 HTTP 连接；它只查询状态：

```powershell
.\.venv\Scripts\python.exe tools/verify_mcp_connection.py --transport http
```

该配置会返回用户的人设与历史，仅用于可信本机客户端或私有连接。当前版本没有公网 OAuth 服务，不能将它作为匿名公网互动服务部署。私有隧道也需要正确的账号关联与权限。

## 普通 Chat 验收

2026-10-10，用户在普通 Chat 通过 `AI Doll Chat Verify` 实际调用了 `get_installation_status` 和 `doll_get_status`。两个独立调用编号及共同运行编号，与本机成功记录匹配，且已排除 SDK 调用。设备通过 Wi-Fi 在线，模拟模式，物理输出关闭。本轮临时 HTTPS 转发已结束，旧地址不可继续调用。

下一次连接需要可达的新地址或已关联的私有隧道。按 [OpenAI 连接指南](https://developers.openai.com/plugins/deploy/connect-chatgpt) 在 **Plugins → 添加 → 创建自定义 MCP 服务器** 选择连接方式，核对实际发现的工具，安装插件，在普通 Chat 中用 `@` 选择它。只有两个状态工具时不能开始互动测试。

获得完整互动工具后，发送：

> 请在我们当前聊天实际查询设备、通道、人设和偏好。开始 60 秒互动，生成并保存本聊天独立的 chat_id，将返回的会话 ID 只用于本聊天。每次等待新事件最多 20 秒，保存 next_cursor。我会在设备设置页模拟按压；收到后结合当前聊天和保存的人设回应，标明模拟来源。到期或我说结束时结束会话，没有事件就不编造反馈，不切换到 Work。

本机服务与公网可达分别验证；目标 Chat 的工具调用与反馈还要独立验证。状态查询成功不表示按压反馈或空闲唤醒已通过。

## 低成本远程连接

`status` 配置只提供两个经过筛选的只读状态工具，可用于建立 HTTPS 通路的验收：

```powershell
.\.venv\Scripts\python.exe tools/chat_mcp_gateway.py --profile status --public-origin https://mcp.example.com
```

把示例替换成实际 HTTPS 来源（只有协议、域名与可选端口，不含 `/mcp`）。公开 MCP 地址是在来源后加 `/mcp`。程序仍只监听 `127.0.0.1:8771`，参数只允许指定的 Host，不会启动隧道。

SakuraFrp 可作为隧道提供者：本地地址填 `127.0.0.1`、端口 `8771`，按本地 HTTP 服务选择匹配的隧道；TCP 路径需要 HTTPS 时可按官方说明配置自动 HTTPS 和有效证书。不要把自签证书报错忽略后当成云端可用。具体节点、账号与费用以提供者为准。见 [Web 穿透](https://doc.natfrp.com/app/http.html)、[自动 HTTPS](https://doc.natfrp.com/frpc/auto-https.html) 与 [证书](https://doc.natfrp.com/frpc/ssl.html)。

当前没有用户的 SakuraFrp 隧道配置，未启动或实测该提供者。远程自动安装、隧道配置/启动和带认证的完整互动接口仍在开发；不能将手动说明记作一键部署完成。既有临时 HTTPS 验收只证明两个状态工具，不证明 SakuraFrp 或远程互动工具。

另一种选择是 [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)：按官方指南创建账号侧隧道并运行官方客户端，可将本机 STDIO 或 HTTP 作为上游。该方式无需匿名公网地址，但依赖账号权限和运行密钥；本项目不代替用户创建平台账号或密钥。

## 互动与主动消息

普通聊天时触摸安静归档。开始互动后，AI 在正在运行的任务中有限等待事件，使用会话 ID 与游标避免重复处理；结束后普通归档继续。不要根据一次单通道按压武断称为拥抱。

空闲聊天主动消息需要宿主事件入口。OpenAI 文档当前列出的 MCP Events 场景为网页 Work、桌面 Work Cloud 和 dots，采用 MCP 2.0 webhook；不能据此声称普通 Chat 已支持唤醒。见 [官方事件说明](https://developers.openai.com/plugins/build/mcp-events)。用户自建应用沿用原后端和消息列表接入 [事件桥](PROACTIVE_INTERACTION.md)。
