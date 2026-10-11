# 主动事件桥：接入自己的聊天应用

这页面向开发者。普通 Chat 使用 [限时工具等待](CHAT_MCP.md)；本页的事件订阅需要原应用提供真实投递入口，不能自动向任意网页聊天写消息。

## 最小接入流程

1. 运行电脑采集服务，或让设备 [直传服务器](DIRECT_SERVER.md)。
2. 用户明确开始互动，创建属于原聊天的会话与订阅。
3. 新事件进入原模型生成队列，带原聊天 ID、上下文、人设和偏好。
4. 按事件 ID 持久去重，完成 ACK 后写入原消息列表。
5. 用户结束或切换聊天时停止订阅，并取消尚未完成的生成。

普通状态只归档，不订阅。默认压力开始触发，300ms 合并窗口与 1500ms 冷却；温度触发默认关闭。模拟可按偏好禁用，输出不反过来当用户触摸。

## 先验证传输，不调用模型

打开电脑 `http://127.0.0.1:8768/bridge`，开始主动互动，在设备页或 companion 模拟一次按压。出现明确标为 **非 AI** 的演示回执后结束。这只验证收取 / 确认链路。

应用的原模型回调和队列示例见 [原聊天接入](EXISTING_CHAT.md)。真实模型验收必须在原窗口中另外进行，不创建第二个聊天框或使用自动按键代替。

## 本机事件 API

接口只监听本机，要求 Host / Origin 与 Bearer 或 CSRF 校验。SSE 由带认证头的 fetch 读取。跨域应用由原后端代理，不公开完整管理页面。

| 接口 | 用途 |
| --- | --- |
| POST `/companion/tool` | 原工具，包括创建 / 结束会话 |
| POST `/bridge/subscriptions` | 绑定 target_id、session_id、device_id |
| GET `/bridge/events?subscription_id=…` | 认证 SSE，获取事件与租约 |
| POST `/bridge/renew` | event_id、subscription_id、lease，续租 |
| POST `/bridge/ack` | 确认同一租约，可保存 reply / source |
| POST `/bridge/unsubscribe` | 停止目标，取消待投递 |
| GET `/bridge/status` | 订阅、投递与保存回执状态 |
| POST `/bridge/preferences` | 保存 policy / feedback |

生成期间约每 4 秒续租；SSE 租约 15 秒。默认只投递 30 秒内的新输入，旧补传仅归档。事务同时保存事件和 outbox；重启恢复未过期消息，至少一次投递需消费者去重。会话结束使旧 ACK 无效。

## 原模型回调必须处理什么

使用 `context.signal`，实际提交前检查取消。以 `idempotencyKey` 持久保存生成结果，重试返回原结果；将生成、ACK、消息写入与普通聊天放同一队列。多窗口 / 多后端需共享锁，浏览器内队列不能代替。

不保证网络故障下模型恰好只调用一次。回调成功、HTTP 2xx 或演示回执不等于最终聊天已经展示。

## MCP Events 适配参考

独立端点：`POST /bridge/mcp`，强制 Bearer 认证。设备 `/mcp` 和本机 STDIO 提供工具调用；事件订阅由电脑端点实现，不由 ESP32 提供。

该端点按 `2026-07-28` 提供 `server/discover`、`tools/list`、`tools/call`、`events/list`、`events/subscribe`、`events/unsubscribe` 与 `ping`。普通请求使用 `_meta.io.modelcontextprotocol/protocolVersion`；不支持的版本或头部／元数据冲突会拒绝。

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

官方支持场景及接入要求见 [OpenAI MCP Events](https://developers.openai.com/plugins/build/mcp-events) 和 [插件连接测试](https://developers.openai.com/api/docs/guides/custom-mcp-server)。本机端点需要用户配置认证 HTTPS 网关或平台支持的 Secure MCP Tunnel；本次没有发布或打通该远程连接。当前为单用户安装，Bearer 对应本机唯一主体；商业多用户云网关仍需独立账号认证、租户隔离和设备配对，不能将此单用户服务直接作为多用户后台。

webhook 返回 2xx 只代表平台接收，不代表模型已经生成或展示回复；应在实际 Work 聊天里核验。Claude／其他只支持工具查询的客户端可以继续使用 45 工具 STDIO MCP，主动响应取决于宿主是否有对应事件机制，不做统一保证。

自行配置 HTTPS 反向代理时，只转发事件端点，并让上游 Host 为 `127.0.0.1:8768`，保留 Bearer 认证头。此本机服务不接受任意公网 Host／Origin；其他管理页面不要随端点一起公开。正式平台接入还需满足所用连接方式的认证要求，当前服务没有实现多用户 OAuth 授权服务器。

## 其他宿主与验证

Operit / OpenClaw 模板见 [宿主接入](HOST_INTEGRATIONS.md)。本机队列、去重、租约、签名与取消通过测试，真实宿主事件尚未验收。官方列出的 Events 支持场景为 Work 和 dots，不能据此声称普通 Chat 已实现空闲唤醒，见 [官方说明](https://developers.openai.com/plugins/build/mcp-events)。

偏好和事实摘要见 [反馈设置](INTERACTION_OBSERVATIONS.md)；回归入口见 [开发指南](DEVELOPER_GUIDE.md)。
