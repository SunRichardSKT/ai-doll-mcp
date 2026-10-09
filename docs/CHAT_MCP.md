# 新聊天窗口接入 AI 共感娃娃

本指南可以直接在线交给 AI 阅读，不要求聊天窗口读取用户电脑文件。仓库是代码和文档的来源，实际传感器数据由连接娃娃的电脑服务提供。

## 先区分三种地址

| 地址 | 用途 | 能否直接作为远程 MCP 地址 |
|---|---|---|
| GitHub 仓库网址 | 阅读文档、下载代码和 PCB | 不能 |
| `http://127.0.0.1:8768/companion` | 在娃娃所在电脑设置通道、查询历史、模拟输入 | 不能，远端的 127.0.0.1 不指向用户电脑 |
| 已配置的认证 HTTPS MCP 地址／平台安全隧道连接 | 让支持该连接的聊天宿主调用设备服务 | 可以，需要另行注册并验证 |

上传 GitHub 不会自动启动服务器、关联用户设备或安装 ChatGPT 插件。不要把 GitHub Pages 当成 Python／USB MCP 后端。

## 用户所在电脑的准备

1. 下载仓库或克隆代码。安装 Python 3.12，设备接通电源并配网。按 [无线连接指南](WIFI_CONNECTION.md) 配对即可无需电脑 USB；USB 方式仍保留。
2. 无线配对后运行 `tools/install_bridge.ps1 -Platform generic -DeviceHost 192.168.1.50`，替换实际 IP。USB 方式用 `-Transport usb -Port COM3`。依赖已安装时可加 `-SkipDependencies`。
3. 打开 `http://127.0.0.1:8768/companion`，确认设备连接、采集正常。已有服务时复用，不重复占用串口。
4. 当前固件为 `doll-lab-2.5.0`、电脑 Bridge 为 `2.9.0`。已升级设备只需连接；从 v2.2 使用新校准功能需升级固件，保留 Wi-Fi 和互动历史。

详细步骤见 [本机 AI 安装文档](AI_INSTALL.md) 与 [主动互动指南](PROACTIVE_INTERACTION.md)。本机运行配置和个人数据保存在 `build/device-lab/`，不上传仓库。

## 普通 ChatGPT Chat 的连接步骤

普通 Chat 的工具调用和后台事件唤醒是两种能力。先完成连接并验证工具，不能在缺少连接时只凭阅读代码宣称能读取设备。

1. 用户在 ChatGPT 支持的开发者／插件入口创建 MCP 连接。具体入口及权限以账号实际界面和 [官方连接文档](https://developers.openai.com/plugins/deploy/connect-chatgpt) 为准。
2. 为本机服务配置该平台支持的 Secure MCP Tunnel，或单用户认证 HTTPS 网关。仓库当前没有运行中的远程地址；不能填入仓库网址、设备局域网 IP 或占位地址。
3. 本机 MCP 2.0 上游端点为 `POST http://127.0.0.1:8768/bridge/mcp`，协议版本 `2026-07-28`，提供 44 个工具和 `doll.interaction` 事件定义。普通工具调用不要求订阅事件。旧本机 STDIO 和开发板 `/mcp` 是不同入口。
4. 上游必须携带 Bearer 认证头。该令牌由服务生成，仅在本机 `build/device-lab/companion-private.json` 中读取，并通过所选连接方式的私密设置配置。不要发到聊天、URL、GitHub issue 或仓库中。
5. 自行配置反向代理时只转发 `/bridge/mcp`，上游 Host 使用 `127.0.0.1:8768`；本机 Host／Origin 校验仍保留。不要同时开放配网页、日志管理页或其他 HTTP 路由。当前是单用户服务，没有多用户 OAuth 授权服务器；所选平台的认证要求必须单独满足。
6. 在平台执行连接／重新扫描，检查工具是否真实可见。新建普通 Chat，选择该插件，让 AI 调用 `doll_get_status` 和 `get_channel_config`。以实际返回的设备 ID、固件版本与通道确认成功。

安全隧道的工作区关联、认证和本机连接程序另见 [Secure MCP Tunnel 官方说明](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)。GitHub 上传验收不包含远程 ChatGPT 连接验收。

## 第一次测试

尚未连接传感器时保留模拟模式，不启用真实 ADC 或电机输出。

1. 在普通 Chat 让 AI 调用 `doll_get_status`，确认真实工具结果显示 `sensor_mode=simulation`。
2. 在娃娃所在电脑打开 `/companion` 页面，选择一个已启用的压力通道，点击“发送模拟输入”。
3. 在 Chat 发送“查询刚才的按压，读取部位和已保存的人设，给我回应”。AI 应调用历史工具，保留来源为 simulation，不把原始压力值解释成未经标定的牛顿。
4. 若宿主能持续执行工具，可要求一次 60 秒有界互动测试：调用 `start_interaction`，保存会话 ID，通过 `get_interaction_device_events` 等待新事件；单次等待最多 20 秒。等待期间收到按压后回应，结束时调用 `end_interaction`。这只验证活跃任务内的反馈，不证明后台唤醒。

查看不到工具时明确报告连接缺失；HTTP 401／403 时检查认证与 Host／Origin；设备离线时检查 USB 及采集服务。不得用编造结果或程序演示回执冒充 AI 实机测试。

## 按压后主动发消息

普通 Chat 当前不在官方 MCP Events 公布的支持场景内。官方列出 ChatGPT Work 网页、桌面 Work Cloud 和 dots，详见 [MCP Events](https://developers.openai.com/plugins/build/mcp-events)。普通工具连接不能自行向空闲对话追加助手消息。

本项目自建前后端可以订阅事件，在绑定的聊天上下文中调用用户选择的模型 API 并显示回复。示例 `/bridge` 页面仅给出标明“非 AI”的演示回执；模型 API 回调由用户应用提供。没有通用安装方式能保证所有官方网页／客户端聊天都被外部设备唤醒。

## 可交给新聊天的请求

> 请先阅读此仓库的 README、docs/CHAT_MCP.md 和 docs/AI_INSTALL.md。检查当前窗口是否有已连接的 ai_doll MCP 工具。如果有，实际读取设备状态、通道配置和人设，再协助我进行模拟按压测试。如果没有，请告诉我需要在平台添加什么 MCP 连接，不要声称通过阅读 GitHub 就完成了本机安装。测试过程中标明模拟来源，不启用真实传感器或电机输出，不重新刷固件，也不要把有界等待反馈说成后台主动唤醒。
