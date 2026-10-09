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

OpenAI 官方文档说明，安装后的插件可以向 Chat 和 Work 提供工具；本机 Codex MCP 配置与托管插件连接是不同的安装路径。见 [插件说明](https://learn.chatgpt.com/docs/plugins) 和 [MCP 配置说明](https://learn.chatgpt.com/docs/extend/mcp)。本项目已验证本机 Work 的 STDIO 工具。2026-10-10 已核实桌面缓存安装了 AI Doll Local 0.1.0，配置与测试包一致；用户在普通 Chat 中用 `@` 选择它后，工具清单和搜索仍没有 ai_doll，两个状态工具未能调用。因此这条 ZIP 路径在该普通 Chat 上未接通，不应继续重复上传或只改提示词。

官方包装流程要求先注册 MCP 连接，再将返回的 `plugin_asdk_app...` 技术 ID 映射到插件；上传本机启动配置不能代替这一步。见 [包装与连接映射](https://developers.openai.com/plugins/build/plugins)。目前上传的包没有这个已注册连接的映射。下一步是建立账号侧实际可达的 MCP 连接，而不是将“插件已加入”当成“工具已可用”。

1. 打开 **Plugins → 添加 → 创建自定义 MCP 服务器**（Add custom MCP server）。当前电脑服务提供 45 个工具；GitHub 仓库公开不代表已有官方目录插件。
2. 在“连接”下点击 **隧道**（Tunnel），不要停留在“服务器 URL”的 `https://example.com/mcp` 输入框。先查看是否已有可用隧道；没有时需按下一节创建并关联目标工作区。已有认证公网 MCP 的用户也可以使用“服务器 URL”。详见 [连接与测试](https://developers.openai.com/plugins/deploy/connect-chatgpt)。
3. 连接成功后，核对服务器发现的工具列表，必须包含 `get_installation_status` 和 `doll_get_status`。安装创建的插件，新建普通 **Chat**，输入 `@` 选择该连接对应的插件，再发送下面的测试请求。账号与工作区权限仍适用；不存在工具列表时不能继续按压验收。
4. 本聊天确实能调用工具后，在设备管理页模拟按压，检查它是否读取新事件并在这个聊天中回应，最后结束会话。

> 请实际检查这个聊天是否能调用 ai_doll MCP，读取设备状态、通道、人设和反馈偏好。能调用时开始 60 秒互动，保存会话 ID 与游标，等待我模拟按压；每次等待最多 20 秒，在本聊天回应并标明模拟来源，最后结束会话。没有工具就说明缺少连接，不凭阅读文档声称已连接，也不要切换成 Work。

### 本机插件 ZIP 的测试范围

这是供支持本机 STDIO 的宿主验证启动配置的包，不是已接通普通 Chat 的安装方案。本轮普通 Chat 已出现“安装成功、工具未暴露”的实际结果，优先使用上面的连接流程；无需为了重试而生成或上传第二个本机包。

代码交付 ZIP 不是插件包。完成本机安装后，在项目根目录使用安装依赖的 Python 生成专用包：

```powershell
.\.venv\Scripts\python.exe tools/package_chatgpt_plugin.py
```

生成位置为 `build/device-lab/AI_Doll_ChatGPT_Local_Test_v2.zip`。只在目标宿主明确支持本机 STDIO 插件时使用 **插件 → 添加 → 上传插件压缩包**，并在实际目标聊天调用两个状态工具。当前打包器采用 [官方包装指南](https://developers.openai.com/plugins/build/plugins) 的根目录 `plugin.json` 和 `mcp.json`，明确声明 STDIO，通过 Windows PowerShell 启动已安装的 MCP；没有密码、令牌、个人历史或模型密钥。包绑定生成时的项目和 Python 路径，移动项目或换电脑需重新生成，不应作为通用安装包发布。

本机 MCP 的实际启动命令需通过 SDK 验证；上传器和普通 Chat 是否接受、是否暴露工具仍需分别实测。ZIP 不会自动注册远程服务、启动采集器或安装依赖。若平台提示不支持本机 STDIO、要求已注册的 MCP，或装好后只有说明没有工具，使用它支持的私有隧道/远程连接。网页和手机不能运行此包的本机路径，亦不能凭 ZIP 安装推断空闲聊天可被唤醒。

### 私有服务与 Tunnel

Secure MCP Tunnel 可以保留本机服务的私有地址，通过电脑向 OpenAI 发起出站连接。它需要账号侧的隧道、运行密钥和相应权限，请按 [官方隧道指南](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) 配置。

1. 在 [Platform 隧道设置](https://platform.openai.com/settings/organization/tunnels) 创建或选择隧道，关联将使用它的 ChatGPT 工作区。创建需要 Tunnels Read + Manage，使用需要 Read + Use。当前登录是否具备这些权限必须实际查看，不能从界面里有“隧道”按钮推断。
2. 使用该页提供的官方 `tunnel-client`，在本机配置 `tunnel_id` 和运行密钥。密钥不发到聊天或仓库。使用本机 STDIO 的 `tools/companion_mcp.py` 作为上游，继续访问现有采集服务；这不另接模型，也不需要模型调用代码。
3. 按官方指南运行 `tunnel-client doctor` 和 `run`。采集服务和隧道需持续运行；检查隧道健康后才在 ChatGPT 中创建连接。
4. 回到 **创建自定义 MCP 服务器 → 隧道**，选择或填入同一个 `tunnel_id`，按实际服务器认证方式完成连接。当前本机 STDIO 服务没有 OAuth 授权服务器，不应把默认显示的 OAuth 当成已经配置完成。
5. 核对发现的工具、创建并安装插件，在普通 Chat 实际调用两个状态工具，再进行限时模拟互动。隧道健康不等同于普通 Chat 已可用，工具可用也不等同于空闲聊天可被唤醒。

这条路径不要求另选模型或另建聊天页面，但 MCP 请求和返回会经过 OpenAI，不能称为完全在局域网内传输。本项目没有替用户创建账户侧隧道或注册插件。若只接受本机/局域网 MCP，使用支持本机连接的客户端或已有应用即可。

## 远程 ChatGPT 连接

需要平台可达的认证 MCP 地址，仓库没有替用户部署远程服务。GitHub 地址、设备私网 IP、远端所见的 localhost 都不能代替这个地址。本地 MCP 2.0 上游为 `POST /bridge/mcp`，协议 2026-07-28；需要保留 Bearer 认证和正确的本机 Host。

平台入口、账号权限和连接方式以 [官方连接文档](https://developers.openai.com/plugins/deploy/connect-chatgpt) 为准。添加并刷新后，在实际聊天中验证工具。按压后触发消息还需要支持事件的宿主：官方目前列出的 MCP Events 场景为网页 Work、桌面 Work Cloud 和 dots，见 [MCP Events](https://developers.openai.com/plugins/build/mcp-events)。普通聊天的工具可用不证明后台事件可用。

仅计划在局域网使用时，无需部署公网网关，优先选择本机客户端或自建应用。远程服务若另行部署，认证和租户隔离需单独设计；当前是单用户本机服务。

## 可交给 AI 的测试请求

> 请阅读 README 和 AI_INSTALL.md，检查当前窗口是否有 ai_doll MCP。实际读取设备状态、通道和人设，然后协助进行模拟按压测试。没有工具时说明缺少什么连接，不凭阅读仓库声称已经安装。保持真实输入和输出关闭，回应中标明模拟来源。互动时保存会话和游标，结束关闭会话。

自建应用与事件接入详见 [主动互动指南](PROACTIVE_INTERACTION.md)。
