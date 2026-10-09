# 在原聊天窗口使用娃娃

先确认聊天客户端支持什么连接方式，再安装 MCP。阅读 GitHub 只能取得代码和说明，不能直接读取用户局域网中的设备。

用户继续使用原 AI、模型、人设和聊天上下文。先完成 [本机安装和 Wi-Fi 配对](AI_INSTALL.md)，确认 <http://127.0.0.1:8768/companion> 显示设备在线。

| 环境 | 接入方式 | 主动反馈 |
|---|---|---|
| 支持本机 STDIO 的客户端 | 导入生成的 ai_doll MCP 配置 | 可查询或在运行中的任务内等待；后台唤醒取决于宿主 |
| 用户自建前后端/API 应用 | 本机事件桥和模型回调 | 可在绑定的聊天追加回复 |
| 远程网页 AI | 平台支持的认证远程 MCP 连接/隧道 | 还需平台提供事件订阅能力 |

## 本机客户端

按 [安装指南](AI_INSTALL.md) 安装电脑服务、无线配对并导入 STDIO 配置。重新连接 MCP，在正在使用的聊天让 AI 调用 `get_installation_status`、`doll_get_status` 和 `get_channel_config`。真实返回的设备 ID、版本与通道是连接证据。具体操作与可选提示模板见 [接入现有对话](EXISTING_CHAT.md)。

未接传感器时保持模拟模式：在 `/companion` 模拟按压，再让 AI 查询历史和人设。互动测试使用 `start_interaction` 与 `get_interaction_device_events`，单次最多等待 20 秒；结束调用 `end_interaction`。这验证当前运行任务内的反馈，不等同于唤醒空闲聊天。

## ChatGPT 普通 Chat 的操作

OpenAI 官方文档说明，安装后的插件可以向 Chat 和 Work 提供工具；本机 Codex MCP 配置与托管插件连接是不同的安装路径。见 [插件说明](https://learn.chatgpt.com/docs/plugins) 和 [MCP 配置说明](https://learn.chatgpt.com/docs/extend/mcp)。本项目已验证当前本机 Work 的 STDIO 工具；用户确认桌面插件已加入，普通 Chat 的实际工具调用仍待验收。

1. 打开 **Plugins**，检查是否已安装娃娃插件，并确认连接中的工具列表。当前电脑服务提供 45 个工具；GitHub 仓库公开不代表已有官方目录插件。
2. 如果尚无连接，打开 **添加 → 创建自定义 MCP 服务器**（Add custom MCP server）。当前客户端还有“上传插件压缩包”入口，本机测试包见下一节；账号连接可选择 **隧道**（Tunnel），使用已创建并关联到目标工作区的 `tunnel_id`。详见 [连接与测试](https://developers.openai.com/plugins/deploy/connect-chatgpt)。
3. 安装创建的插件，刷新连接。新建普通 **Chat**，输入 `@` 选择该插件，再发送下面的测试请求。能否使用取决于账号和工作区权限，不能仅凭添加了本机配置认定成功。
4. 本聊天确实能调用工具后，在设备管理页模拟按压，检查它是否读取新事件并在这个聊天中回应，最后结束会话。

> 请实际检查这个聊天是否能调用 ai_doll MCP，读取设备状态、通道、人设和反馈偏好。能调用时开始 60 秒互动，保存会话 ID 与游标，等待我模拟按压；每次等待最多 20 秒，在本聊天回应并标明模拟来源，最后结束会话。没有工具就说明缺少连接，不凭阅读文档声称已连接，也不要切换成 Work。

### 上传本机插件 ZIP 测试

代码交付 ZIP 不是插件包。完成本机安装后，在项目根目录使用安装依赖的 Python 生成专用包：

```powershell
.\.venv\Scripts\python.exe tools/package_chatgpt_plugin.py
```

生成位置为 `build/device-lab/AI_Doll_ChatGPT_Local_Test_v2.zip`。在 **插件 → 添加 → 上传插件压缩包** 上传，安装后新建普通 Chat，用 `@` 选择 **AI Doll Local** 并实际调用两个状态工具。当前打包器采用 [官方包装指南](https://developers.openai.com/plugins/build/plugins) 推荐的根目录 `plugin.json` 和 `mcp.json`，明确声明 STDIO，通过 Windows PowerShell 启动已安装的 MCP；没有密码、令牌、个人历史或模型密钥。包绑定生成时的项目和 Python 路径，移动项目或换电脑需重新生成，不应作为通用安装包发布。已经加入的插件先验证工具，无需为验证而重复上传。

本机 MCP 的实际启动命令需通过 SDK 验证；上传器和普通 Chat 是否接受、是否暴露工具仍需分别实测。ZIP 不会自动注册远程服务、启动采集器或安装依赖。若平台提示不支持本机 STDIO、要求已注册的 MCP，或装好后只有说明没有工具，使用它支持的私有隧道/远程连接。网页和手机不能运行此包的本机路径，亦不能凭 ZIP 安装推断空闲聊天可被唤醒。

### 私有服务与 Tunnel

Secure MCP Tunnel 可以保留本机服务的私有地址，通过电脑向 OpenAI 发起出站连接。它需要账号侧的隧道、运行密钥和相应权限，请按 [官方隧道指南](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) 配置。隧道需要持续运行；密钥在本机设置，不发到聊天或仓库。

这条路径不要求另选模型或另建聊天页面，但 MCP 请求和返回会经过 OpenAI，不能称为完全在局域网内传输。本项目没有替用户创建账户侧隧道或注册插件。若只接受本机/局域网 MCP，使用支持本机连接的客户端或已有应用即可。

## 远程 ChatGPT 连接

需要平台可达的认证 MCP 地址，仓库没有替用户部署远程服务。GitHub 地址、设备私网 IP、远端所见的 localhost 都不能代替这个地址。本地 MCP 2.0 上游为 `POST /bridge/mcp`，协议 2026-07-28；需要保留 Bearer 认证和正确的本机 Host。

平台入口、账号权限和连接方式以 [官方连接文档](https://developers.openai.com/plugins/deploy/connect-chatgpt) 为准。添加并刷新后，在实际聊天中验证工具。按压后触发消息还需要支持事件的宿主：官方目前列出的 MCP Events 场景为网页 Work、桌面 Work Cloud 和 dots，见 [MCP Events](https://developers.openai.com/plugins/build/mcp-events)。普通聊天的工具可用不证明后台事件可用。

仅计划在局域网使用时，无需部署公网网关，优先选择本机客户端或自建应用。远程服务若另行部署，认证和租户隔离需单独设计；当前是单用户本机服务。

## 可交给 AI 的测试请求

> 请阅读 README 和 AI_INSTALL.md，检查当前窗口是否有 ai_doll MCP。实际读取设备状态、通道和人设，然后协助进行模拟按压测试。没有工具时说明缺少什么连接，不凭阅读仓库声称已经安装。保持真实输入和输出关闭，回应中标明模拟来源。互动时保存会话和游标，结束关闭会话。

自建应用与事件接入详见 [主动互动指南](PROACTIVE_INTERACTION.md)。
