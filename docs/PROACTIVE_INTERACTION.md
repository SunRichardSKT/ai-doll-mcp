# 主动互动与跨平台接入（Bridge v2.5）

更新日期：2026-10-09。电脑服务 `doll-bridge-2.5.0`，开发板为 `doll-lab-2.3.0`。从 v2.2 升级需要重新烧录；新增功能见 [校准与日常模式](CALIBRATION_AND_DAILY_MODE.md)。保留压力、NTC 温度输入与震动输出、16 个逻辑通道和历史。可通过 [Wi-Fi 无线采集](WIFI_CONNECTION.md) 解除电脑 USB 数据连接；以下事件桥功能保持不变。

## 已实现和使用边界

- 新事件与待投递消息在同一个 SQLite 事务内保存，普通模式只归档。
- 用户明确开始互动并订阅后，把新的有效输入送到一个绑定的回复目标；不自动抢占别的聊天。
- 默认只触发压力开始；300ms 内多个通道合并，后续消息间隔至少 1500ms。释放和所有输出指令不触发，防止震动命令导致反馈循环。
- 温度触发默认关闭；开启后按每个通道独立比较，变化达到默认 1°C 才触发，故障值不触发。
- 模拟输入带 simulation 标签，可在反馈偏好中禁止触发；数据、部位名称不是模型指令。
- 提供本机认证 SSE 流、自建应用浏览器适配器，以及 MCP 2.0 的事件发现／订阅／取消和签名 webhook 投递适配。
- 实测验证了本机页面自动接收真实 USB 链路的模拟按压。页面的“演示回执”是程序测试反馈，不是模型生成。
- v2.4 在实际 Wi-Fi 采集链路上重复验证页面推送、ACK 和会话结束；USB 串口独占且不发数据时，Wi-Fi 历史与互动仍通过。
- 尚未验证用户账号里的 ChatGPT Work 订阅；需要可用入口、平台权限、认证远程连接／隧道和实际回调后才能验收。没有宣称能向任意 ChatGPT／Claude 网页聊天主动写消息。

## 统一入口

新电脑在项目根目录运行（需要 Python，首次安装依赖需要联网）：

```powershell
.\tools\install_bridge.ps1 -Platform generic -Port COM3
```

已无线配对时加 `-DeviceHost 192.168.1.50`（替换实际 IP），或复用保存的连接方式。无线配对、独立供电和重连见 [无线指南](WIFI_CONNECTION.md)。

已有依赖的开发电脑：

```powershell
.\tools\install_bridge.ps1 -Platform api -Port COM3 -SkipDependencies
```

可选平台：`generic`、`claude-desktop`、`chatgpt-work`、`api`。入口创建／使用项目 Python 环境，生成通用 STDIO 配置及桥接说明，按需启动服务；不自动修改 AI 客户端账号、配置文件，不部署公网服务。不同平台仍需完成其自身的连接授权。

只生成配置、不启动服务：加 `-NoStart`。如果旧服务占用 8768，先关闭旧服务，避免两个程序抢占 COM3。脚本不会自动终止其他进程。

生成的 `build/device-lab/bridge-install.json` 与 `mcp-client-config.json` 为本机信息；密钥、订阅签名秘密和历史都在 `build/`，不要分享。

## 先做本机主动推送测试

1. 运行采集服务，打开 <http://127.0.0.1:8768/bridge>。
2. 设置回应语气、回复长度和是否允许模拟输入。保存后下次开始互动生效。
3. 点击“开始主动互动”。页面会创建属于这个窗口的互动会话并订阅；已有其他聊天互动时会拒绝抢占。
4. 在此页模拟按压，或另开 <http://127.0.0.1:8768/companion> 模拟按压。
5. 接收窗口无需再发送用户消息，会自动出现标明 simulation／非 AI 的演示回执，确认后写入历史。
6. 点击“结束互动”停止投递，普通归档继续。当前示例订阅最长 5 分钟；空闲、订阅过期或会话结束也会停止。

页面刷新后同一目标可重新连接并续订，不重复创建订阅。无人确认的消息使用租约恢复；关闭窗口不会把消息送到别的聊天，订阅到期后停止。

## 自建前后端／模型 API

`tools/bridge_client.js` 提供 `DollBridgeClient`。调用方指定稳定、唯一的应用聊天 ID，并提供模型回调：

```javascript
const bridge = new DollBridgeClient({
  csrf: pageCsrf, // 同源本机页面；后端接入则使用本机 Bearer 令牌
  targetId: 'my-app-chat:123',
  onInteraction: async (event, {signal, idempotencyKey}) => {
    // 你的后端获取这个聊天的上下文、人设和用户反馈偏好，再调用用户选定的模型。
    const response = await fetch('/api/doll-reply', {
      method: 'POST', signal,
      headers: {'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey},
      body: JSON.stringify({chatId: '123', event})
    });
    if (!response.ok) throw new Error('模型暂不可用');
    const answer = await response.json();
    // 先返回结果供桥接服务确认；避免会话已结束时仍向窗口追加迟到的回复。
    return {text: answer.text, source: 'model'};
  },
  onReply: (answer, event) => {
    // 确认投递后，应用再按 event.eventId 去重，把 answer.text 显示在绑定聊天里。
    appendAssistantMessage('123', answer.text, event.eventId);
  }
});
await bridge.start();
// 结束时：await bridge.stop();
```

这里的 `/api/doll-reply` 是用户应用实现的接口，本项目没有替用户选择模型、填写密钥或调用收费 API。模型密钥放在自己的后端，不放到浏览器。API 会话属于自建应用，不会因此访问官方网页聊天的私有上下文。

适配器在生成过程中自动续租，完成后 ACK；同一目标只放行一个未确认消息。客户端缓存已完成事件以处理本次运行中的重复投递。应用后端仍需持久保存 `Idempotency-Key` 对应的生成结果，再次收到同一 ID 时返回原结果；无法承诺网络故障下恰好只调用一次模型。

HTTP 接口都只监听本机，要求现有 Host／Origin 校验及 Bearer 或 CSRF。SSE 使用 `fetch` 加认证头，令牌不出现在 URL。其他源的网页应通过自己的后端连接桥接服务，不要直接跨域访问本机。

| 接口 | 用途 |
|---|---|
| `POST /companion/tool` | 原 MCP 工具调用，包括开始／结束会话 |
| `POST /bridge/subscriptions` | 提交 target_id、session_id、device_id；创建／续订本机目标 |
| `GET /bridge/events?subscription_id=...` | 认证 SSE 流；发送事件和租约，定期重连 |
| `POST /bridge/renew` | event_id、subscription_id、lease；每 4 秒续租 |
| `POST /bridge/ack` | 确认同一租约；可提交 reply、source=model/demo |
| `POST /bridge/unsubscribe` | 停止指定目标，取消待投递消息 |
| `GET /bridge/status` | 当前订阅、投递计数、已保存反馈；不返回签名密钥／回调 URL |
| `POST /bridge/preferences` | 保存 policy 与 feedback |

## ChatGPT MCP Events

独立端点：`POST /bridge/mcp`，强制 Bearer 认证。现有设备 `/mcp` 和本机 STDIO 继续支持旧协议；不要修改 ESP32 的协议版本来冒充事件支持。

新端点按 `2026-07-28` 提供 `server/discover`、`tools/list`、`tools/call`、`events/list`、`events/subscribe`、`events/unsubscribe` 与 `ping`。普通请求使用 `_meta.io.modelcontextprotocol/protocolVersion`；不支持的版本或头部／元数据冲突会拒绝。

事件名为 `doll.interaction`。先通过工具读取设备 ID、调用 `start_interaction` 获得会话 ID，再由宿主订阅：

```json
{
  "jsonrpc": "2.0", "id": "subscribe-1", "method": "events/subscribe",
  "params": {
    "_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
    "name": "doll.interaction",
    "arguments": {"device_id": "你的设备ID", "session_id": "开始互动返回的ID"},
    "delivery": {"mode": "webhook", "url": "宿主提供的HTTPS回调", "secret": "宿主提供的whsec_签名密钥"},
    "cursor": null, "ttlMs": 300000
  }
}
```

不自行猜测官方聊天 ID 或编造回调 URL／签名密钥。订阅标识由已认证主体、回调、事件及参数确定，重复请求幂等；回调 challenge 验证通过后才启用。签名采用 Standard Webhooks HMAC-SHA256，覆盖事件 ID、时间戳及精确请求体；重试保持事件 ID，更新签名时间。

只接受公开 HTTPS、443 端口，无用户名／密码／片段；验证和每次投递都检查 DNS 并固定连接到已验证地址，TLS 使用原主机名，拒绝私网与重定向。暂时失败有界退避，410 停止订阅，413 和其他永久错误不重试。订阅最长授予一小时，`ttlMs=null` 也不会承诺无限监控。当前 `cursor=null` 表示不支持主动事件历史重放；普通 MCP 历史工具仍可查询。

官方支持场景及接入要求见 [OpenAI MCP Events](https://developers.openai.com/plugins/build/mcp-events) 和 [插件连接测试](https://developers.openai.com/plugins/deploy/connect-chatgpt)。本机端点需要用户配置认证 HTTPS 网关或平台支持的 Secure MCP Tunnel；本次没有发布或打通该远程连接。当前为单用户安装，Bearer 对应本机唯一主体；商业多用户云网关仍需独立账号认证、租户隔离和设备配对，不能将此单用户服务直接作为多用户后台。

webhook 返回 2xx 只代表平台接收，不代表模型已经生成或展示回复；应在实际 Work 聊天里核验。Claude／其他只支持工具查询的客户端可以继续使用 33 工具 STDIO MCP，主动响应取决于宿主是否有对应事件机制，不做统一保证。

自行配置 HTTPS 反向代理时，只转发事件端点，并让上游 Host 为 `127.0.0.1:8768`，保留 Bearer 认证头。此本机服务不接受任意公网 Host／Origin；其他管理页面不要随端点一起公开。正式平台接入还需满足所用连接方式的认证要求，当前服务没有实现多用户 OAuth 授权服务器。

## 数据和故障处理

- 默认只投递发生后 30 秒内的新事件，过期未投递事件仍保留在原始历史，不突然补发旧按压。
- `events` 与 `bridge_outbox` 同事务，设备游标在事务提交后才前进，避免只保存游标却丢投递任务。
- SSE 租约 15 秒；生成期间续租。新消息的 30 秒陈旧期限不打断已续租的生成，但会话结束或订阅取消会使旧 ACK 无效。
- SQLite 持久保留订阅、消息状态和回复，重启可恢复未过期目标与未确认消息。投递语义为至少一次，消费方按 `eventId` 去重。
- 压力 raw 未标定力值；“拥抱”等含义由 AI 结合通道、部位、时序和聊天判断。反馈偏好只是用户配置，不保证模型一定遵守字符数。
- Bridge 不自动启用真实输入或震动输出，也不自动把生成文本转成电机动作。

## 验证

```powershell
python tools/test_companion.py
python tools/test_interaction_bridge.py
# 已运行采集服务、连接设备且无人互动时，安装 Playwright 后可运行：
node tools/test_bridge_ui.cjs
```

测试覆盖事务回滚、事件合并、旧记录排除、租约与 ACK、取消／到期、重启、温度分路基线、输出不回触摸、原生事件订阅和签名／私网回调拒绝。远程回调使用测试替身，真实 ChatGPT／Claude 账号与模型 API 调用不属于本次验收。
