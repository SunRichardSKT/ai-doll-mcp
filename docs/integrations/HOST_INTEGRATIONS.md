# 其他客户端与事件转发模板

> 给维护原聊天应用的开发者；普通用户先读入门区。 [全部目录](../README.md)


此页给开发者。普通 Chat 推荐 [Secure](SECURE_MCP.md)。Operit、OpenClaw / 微信尚未用真实账号验收，以下是模板和接口契约，不是开箱即用的账号连接。

## 先选通路

| 客户端 | 查询通路 | 事件反馈需要 |
| --- | --- | --- |
| 本机 MCP 客户端 | STDIO 45 工具 | 宿主提供实际事件 / 消息入口 |
| 手机客户端 | 可达的有限范围 LAN HTTP MCP | 手机原应用接收服务和原聊天回调 |
| 云端自建宿主 | HTTPS MCP 或自行配置的网络转发 | 云端原聊天生成队列与去重 |
| 自定义前后端 | 电脑事件桥或设备直传 | `DollBridgeClient` / 后端接收接口 |

Secure ID 不是通用 URL。模板不能自动取得用户原对话上下文，也不会替用户登录微信或配置模型。

## 通用转发器

采集已配对并运行后，在根目录执行：

```powershell
.\python\python.exe tools/host_event_forwarder.py configure
.\python\python.exe tools/host_event_forwarder.py run --duration 60
```

填写 generic / openclaw、原聊天目标、接收 URL 和接口令牌。配置在 `build/device-lab/host-forwarder/`，前台运行，Ctrl+C 结束；status 仅为最近快照，不能单凭它认定进程存活。

只转发会话期内且 30 秒内的新输入，成功回执持久保存，ACK 丢失复用。至少一次传输，接收方必须持久去重、检查目标和期限。

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

重复请求返回同一回执；失败不能返回假成功。事件与普通聊天共用模型、上下文及顺序，保存模型结果后按事件 ID 写入原消息列表。超时结果不明确时查询保存结果，不盲目重新生成。已有浏览器适配器和队列处理见 [主动互动指南](../developers/PROACTIVE_INTERACTION.md)。

## Operit 模板

`templates/operit/ai_doll.js` 提供 `call_mcp` 与 `respond_to_event`。前者查询实际 HTTP MCP，后者供外部工作流把通知送往明确的原聊天，不能在 AI 同一执行轮里递归调用。

用户需按自己的 Operit 版本导入包、提供接收服务与现有工作流。目标必须是真实原聊天 ID，不猜测。包接口已用测试替身验证，真实账号和发送效果待验收。

## OpenClaw 模板

`templates/openclaw-hook.example.json` 配置已有 agent、会话路由、channel 和 recipient，不覆盖模型。转发器送到现有 hooks；接收回执只证明接受任务，不证明微信送达。

必须核对所用插件的实际聊天路由与权限，不能新造 ID 后称为沿用原上下文。网络转发、云端安装和账号由用户实际环境配置；本项目没有完成该平台部署。

## 有限范围 LAN MCP

替换电脑实际私有 IP，可单独启动只读网关：

```powershell
.\python\python.exe tools/remote_mcp.py --listen-host 192.168.1.20 --port 8775 --profile history --folder build/device-lab/custom-host-mcp --print-address
```

手机填输出的完整地址。history 为 9 个只读工具，interaction 为 13 个；只开放 MCP，不开放数据库和管理页。默认仍是回环，明确选可信 LAN 地址；跨网络需实际受信任的连接方式。

## 验证顺序

先实际工具发现与查询，再检查原聊天目标、模拟新事件、持久去重、结束 / 过期不投递，最后验证真实模型和消息展示。模板通过的协议测试不能替代真实宿主。见 [验证汇总](../reports/VALIDATION.md)和 [模板索引](../../templates/README.md)。
