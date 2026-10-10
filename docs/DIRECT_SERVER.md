# 设备直连服务器与原聊天主动反馈

设备固件 2.8.1 支持第二种数据通路。现有电脑采集 / MCP 接入保留。

```text
手机 → ESP32 设置页：配 Wi-Fi、粘贴服务器配置
ESP32 → HTTPS 服务器：事件页 + 通道/读数快照 → SQLite 持久归档
服务器 → SSE / 后端等待接口 → 原聊天生成队列 → 原模型 → 原对话
服务器 → 待执行配置 → ESP32 的下一次连接 → 执行回执
```

使用设备向外连接，无需家中端口映射、Sakura 或 Secure 隧道，不要求本地电脑常开。手机不是数据中转器，配好后可以离开。远端服务器需要运行；本地自定义前端可运行同一服务，设备直接上传到其局域网 IP。

## 部署到自己的服务器

推荐使用根目录 **Install_Server.sh**，填写真实域名，由入口自动准备 Docker、配置、持久卷、服务与 HTTPS，并在验证通过后提供管理链接。可以只下载独立 Linux 服务包；步骤见 [远程快捷部署](REMOTE_SERVER_SETUP.md)。以下手工命令保留给已有反向代理或定制部署。

暂时没有服务器时，Windows 用户完整解压软件包，双击根目录 **AI_Doll_Server.cmd**。它使用内置 Python，自动生成本机配置并打开管理页；填写已配网设备的局域网 IP，点击“连接设备”，服务会自动写入设备直连设置。无需运行安装命令或手动复制管理 / 设备令牌。步骤及两种入口的选择见 [简化安装指南](SERVER_QUICKSTART.md)。此时电脑充当接收服务器，需保持运行，设备与电脑必须在可互通的局域网。

Python 服务只依赖标准库和时区数据。已安装 Python 3.12 时可运行 `pip install -r requirements-server.txt`，再启动 `python tools/direct_server.py --data-dir /var/lib/ai-doll --public-url https://doll.example.com`。默认只监听回环 8781，由已有 HTTPS 反向代理转发整个独立设备服务。反向代理需要关闭 SSE 缓冲，读取超时大于 25 秒；设备网页和电脑管理程序没有因此公开。

也提供 Docker Compose：

```sh
cd deploy/direct-server
cp .env.example .env
# 编辑 .env，将 DOLL_DOMAIN 改为指向此服务器的真实域名。
docker compose up -d --build
docker compose exec doll python tools/direct_server.py --data-dir /data --show-token
```

域名的 A/AAAA 必须正确指向服务器，80/443 需要可达。Caddy 配置负责申请和续期受信任证书，普通浏览器和设备均验证证书，不关闭 TLS 校验。[Caddy 自动 HTTPS](https://caddyserver.com/docs/automatic-https)、[流式代理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)。Docker 镜像和证书申请必须在你的服务器上实际执行验收；交付配置不代表已经替你部署。

打开 `https://你的域名/`，用上述管理连接令牌连接。这是单用户、自部署服务，不创建娃娃账号；你的多用户应用应在现有后端完成身份与租户隔离，不能直接把同一个管理令牌分发给所有用户。数据卷保存设备绑定、历史、人设、会话、投递状态和回执，容器重启不会清空。

## 全程用手机完成设备配置

1. 服务器管理页面点击“生成设备连接配置”。复制包含 `server_url` 和 `device_token` 的 JSON。
2. 设备通电后，长按 BOOT 约 3 秒；连接 `AI-Doll-xxxxxx` 热点，访问 `http://192.168.4.1/`。已有 Wi-Fi 配置不会被清空。
3. 在“直连服务器”中粘贴配置、点击填入，再保存。首次配网时也选择家庭 2.4 GHz Wi-Fi。服务器地址与通道类型/部位均由手机操作。
4. 手机切回有网络的 Wi-Fi，刷新服务器管理页。设备在线后可以从服务器进入“通道、模拟、历史与人设”设置。远端无需能直连设备 IP。
5. 局域网内仍可访问设备 IP，默认免登录；可在“设置页登录保护”开启自行设置的账号密码。关闭直连开关后可回到原电脑采集模式。

设备连接令牌是服务器为此设备生成的令牌，与 ESP32 局域网 MCP 令牌、网页管理密码、模型密钥均不同。管理令牌用于服务器管理或你的后端适配，设备令牌只能上传到绑定设备的记录。首次有效上传后锁定硬件设备 ID，撤销绑定会立即拒绝后续上传。

普通可信 HTTPS 使用固件证书包；内网自签证书可在设备页提供 PEM 根证书，仍验证主机名。HTTPS 启动需网络时间，设备通过 SNTP 获取时间后再握手。[Espressif HTTPS / 证书包说明](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/api-reference/protocols/esp_http_client.html)。HTTP 仅在手机明确勾选本地测试时允许，主机必须是 10/8、172.16/12 或 192.168/16 的字面 IP，公网地址不接受 HTTP。

## 接入你已经存在的前端

使用自有证书时勾选设备页“使用自有根证书”，粘贴 PEM；已保存的证书可以留空保留。切换到普通可信域名时取消勾选，恢复固件证书包。设备上传失败也会在页面保留服务器地址和开关，方便手机修复配置。

没有新增聊天框。加载现有 `tools/bridge_client.js`、`tools/conversation_queue.js`，绑定你原聊天的稳定 ID 与生成回调。原前端与设备服务同源时使用 Cookie；不同前端建议由自己的后端代理 `/d/<设备配对ID>/`，在后端附加管理 Bearer 令牌。确需跨域时启动服务添加精确 `--origin https://app.example.com`，并在适配器中传入 token，不使用通配 Origin。

```javascript
const queue = new DollConversationQueue();
const chatId = currentChat.id; // 必须来自现有聊天，不能每次随机生成。
const bridge = new DollBridgeClient({
  baseUrl: '/d/设备配对ID', // 从管理页设备列表取得；也可使用后端代理地址。
  targetId: chatId,
  runDelivery: (operation, options) => queue.run(chatId, operation, options),
  onInteraction: async (event, {signal, idempotencyKey}) => {
    // 调用你现有的后端：带原聊天 ID、事件、人设和偏好，沿用原模型。
    // 后端须持久按 idempotencyKey 去重，避免 ACK 丢失后再次计费/生成。
    return currentChat.generateFromDevice(event, {signal, idempotencyKey});
  },
  onReply: (answer, event, {idempotencyKey}) => {
    // 在原聊天插入，并按稳定事件 ID 去重。
    return currentChat.insertAssistantMessage(answer.text, {idempotencyKey});
  }
});
await bridge.start({idle_timeout_sec:3600, ttl_sec:3600});
// 用户无需再发送文字。此后新按压会触发上述原模型回调。
// 用户关闭互动时：await bridge.stop();
```

普通状态只归档。开始互动后，浏览器可以空闲等待，事件直接调用原生成队列，不要求正在执行一轮 AI 工具调用。结束、会话空闲到期、订阅到期后不再触发。时长最多一小时；前端可以在用户明确开启的互动模式内续订，不默认永久开启。限时测试可传 `duration_sec:60, ttl_sec:60`，原无参 `start()` 继续兼容。

希望浏览器关闭后仍生成消息时，由**原服务器后端**持续监听 SSE 或调用 `POST /d/<ID>/bridge/next`（`subscription_id`、`wait_sec` 0..20），调用原模型，再经应用原有 WebSocket / SSE / 推送展示。`/bridge/next` 返回的字段与浏览器流一致，续租 `/bridge/renew`，确认 `/bridge/ack`。它不控制手机操作系统后台唤醒权限，不承诺页面关闭后浏览器脚本继续运行。

## 接口与故障约定

所有管理请求要求管理 Bearer 或同源 HttpOnly Cookie。设备只用设备 Bearer 调用 `/api/device/exchange`。

| 接口 | 用途 |
|---|---|
| POST `/api/pairings` | `{label}` 生成设备连接配置 |
| GET `/api/devices` | 设备配对 ID、名称、在线状态、最后同步 |
| POST `/api/revoke` | `{id}` 撤销设备 |
| POST `/api/device/exchange` | `{protocol:1,batch,snapshot,command_results}`；持久提交后返回 ACK、服务器时间与待执行命令 |
| GET `/d/<ID>/status` | 在线状态、最近快照、当前会话 |
| POST `/d/<ID>/companion/tool` | `{name,arguments}`；原历史、人设、偏好与会话工具名称兼容 |
| POST `/d/<ID>/commands` | 在线设备异步配置 `{name,arguments}`；202 返回命令 ID |
| GET `/d/<ID>/commands/<命令ID>` | pending / dispatched / completed / expired / cancelled 与实际回执 |
| POST `/d/<ID>/bridge/subscriptions` | 绑定 session、device、target；与原事件桥一致 |
| GET `/d/<ID>/bridge/events?subscription_id=…` | 认证 SSE，直接交给现有浏览器适配器 |
| POST `/d/<ID>/bridge/next`、`renew`、`ack`、`unsubscribe` | 后端接收、续租、回执和结束 |

ESP32 的 HTTP/TLS 在独立 FreeRTOS 任务执行，传感器、Flash 与配置更新留在主循环。平时约 2 秒心跳，有新事件尽快上传；失败退避到最多 60 秒。Flash 最多 256 条事件，保留当前容量/丢失计数。ACK 必须匹配发送时的 boot、storage_epoch 和 cursor，且服务器已提交。丢 ACK 仅导致去重补传。每个设备独立数据库，历史离线仍可查询。

一次上传最多 24 条持久记录与有限实时页。旧启动 / 超过五秒的补传仅归档，不主动触发旧回复。事件保留类型、部位、数值、单位、质量及模拟来源；AI 自行判断动作含义，不把一个通道的按压直接当成拥抱。

远程配置只在设备在线时排队，默认 30 秒期限。同步页面工具等待最多约 8 秒。服务器**最多一次下发**，设备返回回执后才显示完成；响应丢失或重启可能出现未知执行结果，先查命令状态，不自动重试控制。截止后 pending 不再下发，设备也检查期限。不要让电脑采集器与直连服务器争用同一份 Flash 消费游标；一种主归档通路对应一个设备使用模式。

电脑采集器发现设备直传开关已开启时停止读取与 ACK，保留原电脑历史供查询；需要切回电脑模式时先在设备页关闭直传。Windows 上再次启动同端口接收服务会失败，避免请求随机落到另一进程。已开启的历史保留策略在上传时维护；关闭策略不会自行删除记录。

这套服务不直接调用模型。模型访问权限、对话身份、原上下文及持久幂等由你的现有应用提供。真实传感器与震动输出仍需接线和校准，测试模拟不表示实物验收。
