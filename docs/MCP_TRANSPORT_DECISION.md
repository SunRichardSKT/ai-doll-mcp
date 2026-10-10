# 普通 Chat 连接方式评估

评估日期：2026-10-10。目标是每位用户自己下载开源代码，让同一台 Windows 电脑采集局域网 ESP32 数据，并在原 ChatGPT 普通聊天中使用 MCP。首次允许少量配置，日常尽量双击启动；不新建娃娃账号，不另接模型。

## 选择结论

对于长期使用 ChatGPT 的用户，**推荐 Secure MCP Tunnel**：使用固定隧道 ID，本机服务保持私有，无需用户管理域名或公网证书。前提是用户能在 OpenAI Platform 创建隧道、取得运行密钥，并关联自己的 ChatGPT 账号/工作区。当前已完成部署，并通过普通 Chat 状态读取、历史查询和 60 秒模拟按压反馈；目标 Chat 的实际调用编号与本机记录已匹配。

**保留已经实测通过的 Cloudflare Quick Tunnel 作为免账号体验和备用入口。** 它的首次操作更少，但每次创建隧道都会换主机地址。不能将它包装成永久地址，也不能承诺电脑重启后 ChatGPT 连接无需更新。需要通用公网地址或连接其他云端 MCP 客户端时，可另外选择 Cloudflare 固定域名隧道。

这个推荐根据首次配置、日常维护及当前实测作出，不代表 Secure 的延迟、可用性或当前账号权限已优于 Cloudflare。

| 项目 | Cloudflare Quick Tunnel | Cloudflare 固定域名隧道 | Secure MCP Tunnel |
| --- | --- | --- | --- |
| 首次准备 | 不需要 Cloudflare 账号和域名 | Cloudflare 账号、域名和专用隧道配置 | Platform 隧道权限、运行 API 密钥、ChatGPT 关联 |
| 添加到 ChatGPT | 填完整 HTTPS MCP URL | 填完整 HTTPS MCP URL | 选“隧道”并填写/选择 tunnel_id |
| 重启后的连接标识 | 新建隧道会更换主机地址 | 可保留固定域名 | 保留同一个 tunnel_id |
| 本机服务的可达方式 | 对外提供专用 MCP HTTPS 地址 | 对外提供专用 MCP HTTPS 地址 | 默认轮询链路通过出站 HTTPS，不需要公开本机 MCP |
| 适配范围 | 支持远程 HTTP MCP 的宿主，逐个平台验收 | 同左 | 支持该隧道的 OpenAI 产品，不能直接当成 Claude 通用 URL |
| 日常双击启动 | 可实现，但地址变化需更新 Chat 连接 | 可实现，初次域名配置较多 | 初次账号配置后可实现，仍需客户端持续运行 |
| 当前项目的实际证据 | 普通 Chat 添加和两个状态调用已通过 | 尚未部署验收 | 本机 13 工具发现、控制服务轮询及普通 Chat 状态、历史、60 秒模拟反馈通过 |

Cloudflare Quick Tunnel 不支持 SSE，但当前 MCP 使用 Streamable HTTP 的 JSON 响应，两个状态工具已实际验证可用。这个限制不等于所有远程 MCP 都不兼容；历史和限时会话仍要分别验收。官方说明见 [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)，固定地址方案见 [Cloudflare 隧道配置](https://developers.cloudflare.com/tunnel/get-started/)。

Secure MCP Tunnel 的运行密钥用于连接 OpenAI 隧道控制服务，不是给娃娃另接一个收费聊天模型的密钥，也不能用 ChatGPT 登录状态代替。创建需要 Tunnels Read + Manage；运行需要 Read + Use；关联及账号策略另行生效。官方支持说明包含个人账号的 Platform 组织，不能仅凭权限错误断言该能力只供企业账号使用。见 [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)。本轮不作其独立收费或免费承诺。

## 开源交付与安装流程

开源的是电脑采集器、MCP、安装器及模板。每位用户使用自己的设备配对及隧道配置；不把开发者的隧道 ID 和运行密钥发给所有下载者。官方文档所述的“不能用于公开插件上架”不等于不能开源本地代码供用户自装；本项目走每人创建私有 MCP 连接的方式。

Secure 路线的首次操作设计为：

1. 设备完成 Wi-Fi 配网，电脑进行一次设备配对。
2. 用户在 Platform 创建自己的隧道与运行密钥，并关联将使用的 ChatGPT 账号/工作区。
3. 本机安装器下载校验官方客户端、保存配置并检查本地 MCP；用户在 ChatGPT 的“创建自定义 MCP → 隧道”选择该隧道，首次完成真实工具发现和调用。

后续启动入口复用已有采集器和隧道运行实例，显示进程、健康及就绪状态。只有目标普通 Chat 实际返回调用编号并与本机审计匹配，才报告 Chat 接入通过；doctor/健康检查不能替代 Chat 验收。已实现 Windows 安装、配置和日常启动入口，见 [Secure 操作指南](SECURE_MCP.md)。官方客户端入口和管理方式见 [openai/tunnel-client](https://github.com/openai/tunnel-client)。

如果账号没有隧道权限，或用户不愿配置 Platform 运行密钥，选 Cloudflare Quick Tunnel。安装器应自动启动专用网关与隧道，提供复制完整地址的按钮；地址改变时显示“需更新 ChatGPT 连接”。不通过模拟键盘或抓取聊天页面自动添加插件。

## 共用接口与验收范围

两条路线共用 ESP32 Wi-Fi → 电脑 SQLite → MCP 的数据链路，保持本地 STDIO 工具兼容。远程网关保留 status/history/interaction 三种配置；首次连接可以先用两个状态工具，用户选择范围后再提供历史或 13 个互动工具。

设置页面、电脑管理接口和数据库文件不作为隧道目的地。模拟记录保留来源、通道、部位、单位和质量；真实传感器未接好时，物理输入/输出保持关闭。限时会话继续使用服务器期限、chat_id、session_id 和游标。

两个方案都需要电脑和后台服务运行；使用云端 AI 查询时，选中的数据会交给该平台。隧道可用不表示普通 Chat 空闲时能主动收到回复，主动事件需要宿主单独支持和验收。

当前 Cloudflare 的两个工具已通过普通 Chat 验收，见 [分阶段记录](MCP_ACCEPTANCE_2_13.md)。Sakura 仍保留，但普通 Chat 添加失败原因未确定；不把它的 SDK 成功或 Cloudflare 成功记成 Sakura 成功。Secure 使用独立网关和官方运行目录，未扩大现有 Cloudflare 工具范围；GitHub 发布仍等待目标聊天及交付验收。
