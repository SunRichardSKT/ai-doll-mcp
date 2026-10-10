# Operit、OpenClaw 与自定义前端

核对日期：2026-10-10。本轮没有真实 Operit、OpenClaw 或微信账号，以下为官方接口评估、接入代码与协议测试，不算平台实测。ChatGPT 普通 Chat 的状态、历史及 60 秒模拟反馈已另行实测，见 [验收报告](MCP_ACCEPTANCE_2_13.md)。

## 接入方式

| 环境 | 按需查询 | 主动反馈 | 首次配置 |
| --- | --- | --- | --- |
| 同一 PC 的 ChatGPT 普通 Chat | Secure MCP Tunnel，13 工具 | 用户启动的限时互动期间可以等待；空闲唤醒未验证 | 一次设备配对、Platform 隧道与运行密钥、Chat 中创建连接 |
| Operit 安卓 | `ai_doll` 包通过 HTTP 调用 MCP | 安卓接收服务 → workflow → 原聊天发送接口 | PC/手机连通、导入包、绑定现有聊天、事件接收接口 |
| OpenClaw + 云服务器 + 微信 | OpenClaw 的 HTTP/STDIO MCP | PC 转发器 → 云端 hooks → 原 agent → 微信插件 | hooks 与具体 session/agent/channel/recipient；历史 MCP 网络路径 |
| 自己写的前后端 | STDIO 或 HTTP MCP | Python 转发器 / `DollBridgeClient` → 原聊天生成队列 | 实现接收接口、持久去重和原聊天回调 |

Secure MCP Tunnel 是 OpenAI 产品的私有连接通道，不能把 `tunnel_...` 当作 Operit 或 OpenClaw 的普通 HTTP URL。这两个环境使用本机 MCP、局域网私密 MCP 或用户自行建立的网络转发。[OpenAI 官方说明](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)

所有方案保留部位、通道、类型、数值、单位、质量和模拟标记，由原模型解释动作。普通状态只归档，开启互动后才向一个明确目标投递。没有新聊天页面、第二个模型密钥或键盘/DOM 自动发送。

## 通用事件转发脚本

电脑采集器已运行并与 ESP32 无线配对后，在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe tools/host_event_forwarder.py configure
.\.venv\Scripts\python.exe tools/host_event_forwarder.py run --duration 60
```

首次填写 `generic` 或 `openclaw`、原聊天目标 ID、接收 URL 和接口令牌。配置保存在本机 `build/device-lab/host-forwarder/`。以后只执行第二行，明确开启一次互动；Ctrl+C 结束。脚本未运行时，普通采集继续，不唤醒自定义前端。Linux 可用已安装依赖的 `python3` 执行同一 Python 入口。

`status` 子命令显示最近执行快照，不单凭快照判断进程仍活着。脚本在前台运行，服务器期限保证客户端意外退出后不会无限投递，不抢占其他聊天。

脚本从本机认证 SSE 取合并事件，续租后发送，接收方确认后 ACK。暂时失败在会话有效期内退避重试；成功回执持久保存在 SQLite，ACK 丢失时复用回执。静默时间、无效输入和离线补传由事件桥过滤；转发器进一步只接受 30 秒内、会话期限内的新输入。

传输为至少一次：接收方接受但回执丢失时，会重发同一 `Idempotency-Key`。接收方必须持久去重，执行前再次检查期限。正在发送的请求无法撤回，不能仅因接口返回成功便认定模型、TTS 或微信消息已完成。

### 接收接口契约

`generic` POST 到指定接口，带 Bearer 认证、JSON 和 `Idempotency-Key: evt_...`。HTTP 仅接受明确的 LAN/回环 IP；公网使用 HTTPS，拒绝重定向。JSON 字段：

| 字段 | 含义 |
| --- | --- |
| `schema` | `ai-doll.host-event.v1` |
| `event_id` | 重试保持不变的投递编号 |
| `target_id` | 绑定的原聊天 ID |
| `expires_at` | Unix 秒，过期不可再唤醒 |
| `event` | 合并事件，`data.events` 为传感器数据，`data.persona/feedback/summary` 为保存配置和事实摘要 |

接收端先验证认证、目标和期限，在同一事务中按 `(target_id,event_id)` 去重并存入原应用生成队列，再返回 200/201/202：

```json
{"accepted": true, "event_id": "收到的原事件ID", "target_id": "收到的原聊天ID"}
```

重复请求返回同一回执；失败不能返回假成功。事件与普通聊天共用模型、上下文及顺序，保存模型结果后按事件 ID 写入原消息列表。超时结果不明确时查询保存结果，不盲目重新生成。已有浏览器适配器和队列处理见 [主动互动指南](PROACTIVE_INTERACTION.md)。

## Operit：包查询与 workflow 反馈

提供 [ai_doll.js](../templates/operit/ai_doll.js)。按 Operit 自定义包流程导入并激活后，使用 `ai_doll:call_mcp`，参数为可达的 `mcp_url`、原 MCP 工具名和 `arguments_json`；代码进行初始化和实际调用。[包开发说明](https://github.com/AAswordman/Operit/blob/main/docs/SCRIPT_DEV_GUIDE.md)、[HTTP 接口](https://github.com/AAswordman/Operit/blob/main/examples/types/network.d.ts)

电脑负责 ESP32 采集，手机原有 8765 TTS 和 3100 健康服务无需修改。新接收服务可用 8780，例如 `/doll/events`。电脑转发器选 `generic`，URL 填手机实际 IP，例如 `http://192.168.1.50:8780/doll/events`，目标填选定的 Operit 原聊天 ID。

手机接收服务由用户现有前端扩展，按上述契约持久接收。每个新事件用已授权的 Shizuku/Root shell 发送显式 Intent 广播，触发已配置的工作流。广播只传事件 ID，工作流从本机队列取完整事件。官方接收组件为 `com.ai.assistance.operit/.integrations.tasker.WorkflowTaskerReceiver`，工作流 action 可自定义。[Intent 官方接口](https://github.com/AAswordman/Operit/blob/main/docs/doc-src/feature-protocol/workflow_intent_trigger.md)

工作流调用包的 `respond_to_event(chat_id,event_json)`；它校验目标、期限和来源，使用 `Tools.Chat.sendMessage` 的 `main` runtime，向原聊天发送隐藏的感知通知，由原模型生成回复，不创建/切换聊天或单独调用模型。[原聊天发送接口](https://github.com/AAswordman/Operit/blob/main/docs/doc-src/package-dev/chat.md)

此函数只供外部工作流使用，不能在正在执行的同一 AI 轮次里递归调用。接收服务负责持久去重、普通消息与事件排队、结果保存和超时核对；包不承诺跨进程恰好一次。一次性定时唤醒可改为检查本机队列，无新事件就退出，不能反复把今天历史当新触摸。

### 手机查询电脑 MCP

电脑另开有限范围的 LAN MCP，替换为电脑实际 IP：

```powershell
.\.venv\Scripts\python.exe tools/remote_mcp.py --listen-host 192.168.1.20 --port 8775 --profile history --folder build/device-lab/custom-host-mcp --print-address
```

手机包填写显示的完整 `http://192.168.1.20:8775/随机串/mcp`。`history` 为 9 个只读工具；需要会话时明确改为 `interaction`（13 工具）。仅提供 MCP，不转发设置页面和数据库；默认仍绑定回环，不使用全接口 `0.0.0.0`。Windows 首次可能需允许本地网络访问，手机须与电脑可互通。HTTP 只用于可信 LAN，跨网使用 VPN/SSH 或受信任 HTTPS。

## OpenClaw：轻量服务器与微信

云服务器通常不能直连家中 ESP32，采集器留在本地电脑。电脑主动向云端 hooks 发事件，不映射 ESP32 或完整设置页。

OpenClaw 提供 MCP 客户端配置和实际连接探测，保存配置不等同连接成功。云端可通过 SSH 反向转发访问电脑 MCP：电脑先运行上述 8775 服务（省略 `--listen-host`，保持回环），再运行：

```text
ssh -N -R 127.0.0.1:18771:127.0.0.1:8775 user@your-server
```

云端把相同私密路径的 `http://127.0.0.1:18771/随机串/mcp` 配为 `streamable-http`，用 `openclaw mcp probe` 检查实际工具，再在微信中查询历史。SSH 要允许反向转发；断开时 MCP 暂不可达，电脑历史仍保存。[OpenClaw MCP 说明](https://docs.openclaw.ai/cli/mcp)

事件脚本选 `openclaw`，模板见 [openclaw-hook.example.json](../templates/openclaw-hook.example.json)。向 `/hooks/agent` 发送通知，指定已存在的 agent、会话 key、持久模式、channel 和 recipient，不覆盖模型或思考设置。`ok + runId` 仅证明任务获准进入执行流程。[hooks 契约](https://docs.openclaw.ai/gateway/config-hooks)

一次配置 `hooks.enabled`、专用 `hooks.token` 和目标 agent allowlist；启用请求携带会话 key，并限制为目标允许的前缀。key 必须取自现有微信会话，不能新造 ID 后宣称复用了上下文。逻辑 hook key 与存储会话可能不同，正式接入需核对原会话路由。公网 hook 使用已有可信 HTTPS，或先经 SSH/VPN 转到回环。

微信 channel ID 由所装插件决定，不能仅凭“接了微信”猜测。官方列出的腾讯插件为 `openclaw-weixin`；其他微信/企业微信插件可能不同，接收者、账号和上下文令牌要求由插件决定。[微信插件边界](https://docs.openclaw.ai/channels/wechat)

本轮不登录或部署不存在的服务器。正式接入再验收原会话上下文、插件投递限制、取消、过期及重复请求。

## 本轮验证

Python 测试覆盖错误回执、重定向、目标/会话隔离、失效租约、过期和离线排除、ACK 丢失后的持久回执、稳定重试 ID、OpenClaw 路由及模型不被覆盖。Operit 使用官方 API 形状的替身验证初始化、工具范围、原聊天发送与过期拒绝。LAN MCP 用官方 SDK 验证 9 工具、私密路径和 Host 限制。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tools -p test_host_event_forwarder.py
node tools/test_operit_package.cjs
```

这些测试没有调用真实 Operit、OpenClaw、微信或新的收费模型。
