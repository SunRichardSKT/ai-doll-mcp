# 选择 AI 平台并完成连接

先给娃娃配网，再按正在使用的应用选择连接方式。Windows 管理中心第3步分别提供以下入口；已有选择会保留。

| 使用的应用 | 连接方式 | 从哪里开始 |
| --- | --- | --- |
| ChatGPT 官方网页，电脑采集 | OpenAI 私有隧道 | 选择“ChatGPT · 电脑私有隧道”，保存并启动后在 ChatGPT 添加隧道 |
| ChatGPT 官方网页，自有服务器 | 公网 HTTPS MCP | 复制服务器设备卡片的完整 MCP 地址，在 Plugins 添加 Server URL |
| Claude Desktop 本机连接 | 本机 MCP 配置 | 选择“Claude 桌面版”，一键写入配置或下载后合并 |
| Claude Code（CLI） | 本机 STDIO 或服务器 HTTP | 选择“Claude Code · 命令行”，下载专用配置；服务器设备卡可复制 HTTP 配置 |
| Claude 网页／手机 | 远程 HTTPS MCP | 选择“Claude 网页／手机”，在官方连接器中添加设备专用地址 |
| DeepSeek DSH（官方 Harness） | STDIO 或 Streamable HTTP | 选择“DeepSeek DSH”生成配置；服务器设备卡可复制远程配置 |
| Gemini 官方网页／手机 | 公网 HTTPS MCP | 网页 Connected Apps 添加自定义应用，连接后可在手机使用 |
| Gemini CLI（Google 官方） | STDIO 或 Streamable HTTP | 选择“Gemini CLI”生成配置，合并到 `.gemini/settings.json` |
| DeepSeek 官方网页／手机 | 暂无已确认的自定义 MCP 步骤 | 先看下方支持范围；不能把模型名称当成客户端能力 |
| Operit 安卓手机 | 手机直连、电脑或服务器 | 使用[三步连接](OPERIT_NO_PC.md)，或导入对应连接文件 |
| 其他 MCP 客户端 | 本机配置或远程地址 | 按客户端支持的传输方式选择 |

## ChatGPT

电脑采集使用[私有隧道指南](SECURE_MCP.md)，保留既有隧道、运行密钥和设备配对。已有 HTTPS 服务器时，可直接复制该设备 MCP 地址，选择 Server URL，按本项目连接选择无需身份验证。创建后安装插件，在聊天中启用。

ChatGPT 的自定义 MCP 入口和隧道权限分别受账号、工作区设置管理。[官方连接说明](https://developers.openai.com/api/docs/guides/custom-mcp-server) · [隧道说明](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)

## Claude Desktop：本机连接

1. 完成电脑与娃娃配对，在管理中心选择“Claude 桌面版 · 本机连接”。
2. 点击“写入 Claude 桌面版配置”。软件只合并 `mcpServers.ai_doll`，保留其他服务和设置；首次写入前备份原文件。
3. 完全退出并重新打开 Claude Desktop，在聊天中启用 AI Doll。

Windows 配置位于 `%APPDATA%\Claude\claude_desktop_config.json`。未安装或未初始化时，先启动一次 Claude Desktop。配置格式错误时原文件保持。也可下载本机配置并手动合并；移动项目目录后重新生成。

本机连接不需要公网域名，使用期间保持电脑采集服务运行。[Claude 本机说明](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) · [MCP SDK 配置说明](https://py.sdk.modelcontextprotocol.io/get-started/real-host/)

## Claude Code（CLI）

### 电脑采集：下载配置即可使用

从 v0.1.5 的 Windows 管理中心直接下载 Claude Code 配置。

1. 启动 `AI_Doll.cmd`，完成娃娃连接，让电脑采集保持运行。
2. 在 AI 接入步骤选择“Claude Code · 命令行”，下载 `AI_Doll_Claude_Code.json`。
3. 在文件保存目录打开终端，运行：

```text
claude --mcp-config ./AI_Doll_Claude_Code.json
```

在 Claude Code 中输入 `/mcp` 查看 `ai_doll`，按提示允许工具使用，再让它调用 `get_installation_status`、`doll_get_status` 和 `get_chat_context`。配置使用本机 Python 与适配器的绝对路径，移动安装目录后重新生成。

也可在项目根目录直接导出并启动：

```powershell
.\python\python.exe -X utf8 tools/install_companion_mcp.py --client claude_code
claude --mcp-config ./build/device-lab/AI_Doll_Claude_Code.json
```

源码开发环境使用开发指南中的 `.venv` Python 运行导出命令。文件加载方式保留现有客户端设置；如需跨项目保存，可使用 Claude Code 官方 `claude mcp add --transport stdio --scope user`，参数使用导出文件中的 `command` 和 `args`。

### 自有服务器：复制 HTTP 配置

在服务器设备卡选择“Claude Code · CLI”，复制配置并保存为 `AI_Doll_Claude_Code.json`，再用同一条启动命令加载。远程条目包含 `type: "http"` 和完整 `url`；保留设备专用私密路径，仅在自己电脑保存。

连接由运行 CLI 的环境发起：同一网络可使用可达的局域网 HTTP 服务，公网使用 HTTPS。Windows 导出的本机配置供原生 Windows CLI 使用；在 WSL、Linux 或 macOS 中运行时，可选择服务器路线，或在对应系统准备 Python 后重新导出本机配置。

互动仍通过现有查询和限时互动工具进入当前会话。空闲主动唤醒需要宿主事件支持。[Claude Code 官方 MCP 说明](https://code.claude.com/docs/en/mcp)

## Claude 网页和手机：远程连接

在[自有服务器](REMOTE_SERVER_SETUP.md)收到设备上传后，复制该设备的完整 MCP 地址，在 Claude 连接器设置中添加自定义远程连接。此服务按设备私密路径授权，选择无需登录，在聊天中启用并调用设备状态。

远程连接由 Claude 云端发起，需要公网可达的 HTTPS 443 地址。即使在 Claude Desktop 中添加“远程连接器”，也与上面的本机配置不同；设备热点、电脑内网地址和 OpenAI 隧道编号均不能作为远程地址。[Claude 官方说明](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)

## DeepSeek DSH：官方 Harness

在管理中心选择“DeepSeek DSH”，生成并下载配置，把条目合并到当前 profile 的 `cordis.patch.yml`，保留原条目。导出的 JSON 数组也是合法 YAML。重启对应 profile，再调用设备状态。路径含空格时保留导出的 `command` 和 `args`。

服务器用户在设备卡选择 DeepSeek DSH，复制 `streamable-http` 配置，或在当前 profile 的 MCP 设置添加服务和完整地址。DSH 的桌面、Web、CLI profile 由运行 Harness 的主机建立连接。[官方客户端配置](https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md) · [官方 MCP 子系统](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/mcp.md)

### 普通 DeepSeek 网页与 App

截至2026-11-15，本次未查到 DeepSeek 官方网页／手机应用的自定义 MCP 接入说明。其官方 Responses API 将内置 `mcp` 类型列为忽略，因此不能将远程 MCP 地址直接填入 API 后期待自动连接。

可在支持 MCP 的客户端中使用 DeepSeek 模型；或由已有应用把 MCP 工具桥接为函数调用。配置在该客户端或应用中完成，项目不会因此更换用户的聊天模型。[DeepSeek 官方支持表](https://api-docs.deepseek.com/guides/responses_api/)

## Gemini 官方网页与手机

管理中心选择“Gemini 网页／手机”，或在服务器设备卡选择 Gemini 网页／手机，复制设备专用公网 HTTPS MCP 地址。在 Gemini 网页的 Settings → Connected Apps → Custom apps 添加地址，按提示完成，在聊天中输入 `@` 选择应用；首次连接在网页完成，之后手机也可使用。

Google 当前要求美国地区、18岁以上的个人账号、英文界面，并开启 Keep Activity。入口尚未对自己的账号开放时，可以选择下方 CLI 路线。[Google 官方说明](https://support.google.com/gemini/answer/17209137?hl=en-45)

开发者也可在 `gemini.google.com/devmode` 创建自定义 MCP 应用，输入公网 HTTPS 地址，检查工具发现并调用。项目使用设备私密路径，未配置 OAuth 时不填写 OAuth 客户端密钥。[官方开发模式步骤](https://developers.google.com/connected-apps/mcp/dev-mode/usage)

## Gemini CLI

管理中心选择“Gemini CLI”，生成本机配置，将 `mcpServers.ai_doll` 合并到用户目录的 `.gemini/settings.json`，保留其他设置。保持电脑采集服务运行，重开 CLI，用 `/mcp` 查看连接并按提示批准工具调用。

服务器用户在设备卡选择 Gemini CLI，复制含 `httpUrl` 的配置，合并到同一设置文件。`httpUrl` 表示 Streamable HTTP，不能改成用于 SSE 的 `url`。这条路线适用于 Google 官方 CLI。[官方 MCP 配置说明](https://geminicli.com/docs/tools/mcp-server/)

## 连接完成后检查什么

在所选 AI 中实际调用 `get_installation_status` 和 `doll_get_status`，核对设备身份与在线状态，再查询历史。ChatGPT 私有隧道可核对返回的调用编号；其他通路按实际工具结果判断。

页面打开、地址格式正确、配置写入成功，分别表示对应步骤完成。官方聊天能按需调用 MCP，并不代表空闲聊天会被设备主动唤醒。[实际调用与互动](CHAT_MCP.md)

MCP 地址含私密访问路径，只在自己的平台账号中配置。`192.168.4.1/setup` 用于设备热点配网；电脑管理页和 MCP 接口各使用自己的地址。
