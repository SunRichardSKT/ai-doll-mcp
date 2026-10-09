# 在聊天窗口使用娃娃

先确认聊天客户端支持什么连接方式，再安装 MCP。阅读 GitHub 只能取得代码和说明，不能直接读取用户局域网中的设备。

| 环境 | 接入方式 | 主动反馈 |
|---|---|---|
| 支持本机 STDIO 的客户端 | 导入生成的 ai_doll MCP 配置 | 可查询或在运行中的任务内等待；后台唤醒取决于宿主 |
| 用户自建前后端/API 应用 | 本机事件桥和模型回调 | 可在绑定的聊天追加回复 |
| 远程网页 AI | 平台支持的认证远程 MCP 连接/隧道 | 还需平台提供事件订阅能力 |

## 本机客户端

按 [安装指南](AI_INSTALL.md) 安装电脑服务、无线配对并导入 STDIO 配置。重新连接 MCP，在正在使用的聊天让 AI 调用 `get_installation_status`、`doll_get_status` 和 `get_channel_config`。真实返回的设备 ID、版本与通道是连接证据。具体操作与可选提示模板见 [接入现有对话](EXISTING_CHAT.md)。

未接传感器时保持模拟模式：在 `/companion` 模拟按压，再让 AI 查询历史和人设。互动测试使用 `start_interaction` 与 `get_interaction_device_events`，单次最多等待 20 秒；结束调用 `end_interaction`。这验证当前运行任务内的反馈，不等同于唤醒空闲聊天。

## 远程 ChatGPT 连接

需要平台可达的认证 MCP 地址，仓库没有替用户部署远程服务。GitHub 地址、设备私网 IP、远端所见的 localhost 都不能代替这个地址。本地 MCP 2.0 上游为 `POST /bridge/mcp`，协议 2026-07-28；需要保留 Bearer 认证和正确的本机 Host。

平台入口、账号权限和连接方式以 [官方连接文档](https://developers.openai.com/plugins/deploy/connect-chatgpt) 为准。添加并刷新后，在实际聊天中验证工具。按压后触发消息还需要支持事件的宿主：官方目前列出的 MCP Events 场景为网页 Work、桌面 Work Cloud 和 dots，见 [MCP Events](https://developers.openai.com/plugins/build/mcp-events)。普通聊天的工具可用不证明后台事件可用。

仅计划在局域网使用时，无需部署公网网关，优先选择本机客户端或自建应用。远程服务若另行部署，认证和租户隔离需单独设计；当前是单用户本机服务。

## 可交给 AI 的测试请求

> 请阅读 README 和 AI_INSTALL.md，检查当前窗口是否有 ai_doll MCP。实际读取设备状态、通道和人设，然后协助进行模拟按压测试。没有工具时说明缺少什么连接，不凭阅读仓库声称已经安装。保持真实输入和输出关闭，回应中标明模拟来源。互动时保存会话和游标，结束关闭会话。

自建应用与事件接入详见 [主动互动指南](PROACTIVE_INTERACTION.md)。
