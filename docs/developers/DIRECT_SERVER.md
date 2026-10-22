# 设备直传与自定义应用接口

> 开发者参考；普通用户可以跳过。 [全部目录](../README.md)


ESP32 主动向接收服务上传，服务保存 SQLite 历史，再向原应用提供事件。手机只负责首次配置，不中转数据；部署远程后电脑无需常开。

本地 **2.25.0 候选版／固件2.13.0** 增加动态二维码连接、稳定服务器实例标识与设备归档租约。候选包位于本机 `delivery/`，尚不代表已经公开发布；已发布旧版仍按其配套说明使用。

## 先完成安装

| 环境 | 使用指南 |
| --- | --- |
| Windows 电脑充当接收服务器 | [本机快捷连接](../integrations/SERVER_QUICKSTART.md) |
| 自己的 Linux 服务器 | [自动部署](../integrations/REMOTE_SERVER_SETUP.md) |
| 已有网站 / 反向代理 | 见下方手工部署 |

服务器管理页生成设备配置，手机在 ESP32“直连服务器”粘贴并保存。收到实际上传才显示在线。设备设置页默认免登录，服务器管理使用安装链接 / 管理令牌，不新建娃娃账号。

2.25管理页可在对应设备下临时生成“Operit连接”的文件、`AIDOLL1:`连接码和二维码，无需在主板或外壳贴标签。同一手机优先下载连接文件或复制连接码；二维码生成脚本与许可随包提供，不访问CDN。设备上传配置与Operit连接仍是不同数据，不能互相导入。

Linux 小型包现在同时启动设备接收服务和 **Streamable HTTP MCP**，共用同一份 SQLite 历史。无需电脑采集器；在管理页的已配对设备下复制 MCP 地址。管理页面本身不是 MCP 地址。Windows 原有 [Secure](../integrations/SECURE_MCP.md) 通路继续兼容。

## 手工部署与已有反向代理

Python 3.12 或以上，安装 `requirements-server.txt`（包含 MCP SDK 与时区依赖）。接收服务默认回环 8781，MCP 默认回环 8782。可在自己的环境安装后运行：

```bash
python3 -m pip install -r requirements-server.txt
python3 tools/direct_server.py --data-dir /var/lib/ai-doll --public-url https://你的域名 --mcp
```

由原 HTTPS 代理转发这个独立服务，关闭 SSE 缓冲、读取超时大于 25 秒。不要因此公开 ESP32 设置页或电脑管理中心。

也可在完整源码目录使用提供的 Compose。源码仓库不保存生成的 `.toolpkg`；从源码构建前需 Python 3.12+、Node.js 18+，在项目根目录先运行 `python3 tools/package_operit.py`。它从 `clients/operit/` 构建并检查手机工具包，供 Docker 复制。Release 的 Linux 小型包已包含该文件，无需安装 Node：

```bash
cd deploy/direct-server
cp .env.example .env
# 将 DOLL_DOMAIN 改为自己的真实域名。
docker compose up -d --build
docker compose exec doll python tools/direct_server.py --data-dir /data --show-token
```

域名 DNS 与 80 / 443 需可达，Caddy 负责 HTTPS。真实公网证书要在自己的环境验证，不能用模板存在作为成功证据。

## 同一台服务器部署原聊天与 MCP

已有网站占用 80 / 443 时，只启动后端，不启动附带的 Caddy：

```bash
cd deploy/direct-server
cp .env.example .env
# 编辑 DOLL_DOMAIN，填写设备服务自己的域名。
docker compose -f compose.backend.yml up -d --build
```

此配置只将 `8781`、`8782` 发布到服务器回环地址，不占用网站端口。接收与 MCP 同一进程、同一数据卷。原后端在宿主机时可访问回环；原后端在其他容器时，需配置共享 Docker 网络后访问 `doll:8782`，容器自己的 `127.0.0.1` 不是宿主机。

使用已有反向代理为设备服务域名提供可信 HTTPS。把 MCP 路径转发到 `127.0.0.1:8782`，其余路径转发到 `127.0.0.1:8781`。Nginx 示例：

```nginx
location ~ ^/(?:[0-9a-f]{64}/)?d/[0-9a-f]{32}/mcp$ {
    proxy_pass http://127.0.0.1:8782;
    proxy_set_header Host $http_host;
    proxy_buffering off;
    proxy_read_timeout 60s;
}
location / {
    proxy_pass http://127.0.0.1:8781;
    proxy_set_header Host $http_host;
    proxy_buffering off;
    proxy_read_timeout 60s;
}
```

管理页在每个设备下提供 `https://域名/<连接随机串>/d/<配对ID>/mcp`。把完整地址填入原客户端的 Streamable HTTP MCP 配置，选择无需身份验证。原聊天后端也可使用 `http://127.0.0.1:8782/d/<配对ID>/mcp`，并添加 `Authorization: Bearer <mcp_token>`。令牌在数据目录的 `server-private.json`，与管理及设备令牌不同；不需要新账号或模型密钥。

默认提供 19 个工具：原有状态、历史、会话工具，加六个自然陪伴工具（设置入口、设备概览、互动上下文、确认处理、部位局部更新、陪伴偏好局部更新）。Compose 可用 `DOLL_MCP_PROFILE=history` 仅开放 9 个查询工具，`status` 仅开放 2 个状态工具；修改后重新创建容器。手工 Python 使用 `--mcp-profile`。撤销设备后相应 MCP 地址失效；正常重启和升级保留地址及历史。

在原聊天实际调用 `get_installation_status`、`doll_get_status`，核对设备信息与两个新的 `verification.call_id`，再查询模拟历史。开始互动需传稳定且非 `main` 的 `chat_id`；读取和结束都必须传该 `chat_id` 及 `session_id`。每次等待最多 20 秒，使用返回游标避免重复，60 秒测试传 `duration_sec=60`。离线时可查询已有历史；状态快照会明确标记是否在线和最后同步时间。

MCP 不负责模型调用或手机后台唤醒。需要按压后主动向原聊天回复时，原应用后端还要监听下方事件接口，并调用原模型与原对话队列。

## TLS、配对与路径切换

设备配置含 `server_url` 和专用 `device_token`；首次有效上传锁定硬件 ID，撤销绑定后拒绝上传。管理令牌、设备令牌与 MCP 配对令牌分别使用。

2.25导出的Operit连接沿用 `schema:1/kind:ai-doll-operit-connection/mode:server`，新增 `server_instance_id`、`pairing_id`、`expected_device_id`。实例标识持久保存在服务器私有配置，配对ID对应既有设备记录；首次上传前设备ID可为空，不能因此声称设备在线。`get_installation_status` 返回这些字段供手机核对，同一实例和配对的地址变更可保留聊天、历史与回执。每次启动变化的 `verification.run_id` 仅用于调用核验，不能作为服务器身份。

普通 HTTPS 使用证书包与网络时间；自签仅在设备显式保存根证书后校验主机名。HTTP 只允许用户确认的本地测试，主机为 10/8、172.16/12 或 192.168/16 字面 IP，公网 HTTP 拒绝。

直传开启时电脑采集器不消费缓存；切回电脑模式先关闭直传。两边历史分别保留。管理为单用户自部署模式，多用户应用需在原后端实现身份、设备权限与租户隔离。

固件2.13.0启用直传时，在设备主循环保留内部 `server` 归档租约（90秒期限、每30秒续租）；网络线程只执行HTTP，仍不操作Flash。手机／电脑的租约申请会得到归档占用错误。已有其他端有效租约时，启用直传明确失败，需先停止该端；不抢占或清除其未提交记录。关闭直传释放内部租约，设备重启清空后按已保存直传配置重新取得。

## 接入原前端的示例

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

2.13.0内部ACK还校验上传作业保存的租约ID及该持有者实际读取的游标；服务器HTTP响应不新增租约凭据，也不能直接清Flash。旧电脑／手机客户端的无租约ACK会被设备拒绝，应同步升级采集端。HTTP `status/history` 权限不扩大，新增内部租约工具不开放给远程模型。完整设备接口见 [工具目录](MCP_TOOLS.md#设备内部归档接口2130)。

尚未升级的旧固件仍执行其原有设备直传／ACK逻辑，更新服务器代码不能给设备凭空增加租约。新电脑及新手机连接旧固件则默认 `legacy_copy_only`、复制而不确认；两者与旧设备直传是不同兼容路径。要取得归档端独占保证，必须核对实际固件2.13能力并配套升级采集端。

一次上传最多 24 条持久记录与有限实时页。旧启动 / 超过五秒的补传仅归档，不主动触发旧回复。事件保留类型、部位、数值、单位、质量及模拟来源；AI 自行判断动作含义，不把一个通道的按压直接当成拥抱。

远程配置只在设备在线时排队，默认 30 秒期限。同步页面工具等待最多约 8 秒。服务器**最多一次下发**，设备返回回执后才显示完成；响应丢失或重启可能出现未知执行结果，先查命令状态，不自动重试控制。截止后 pending 不再下发，设备也检查期限。不要让电脑采集器与直连服务器争用同一份 Flash 消费游标；一种主归档通路对应一个设备使用模式。

电脑采集器发现设备直传开关已开启时停止读取与 ACK，保留原电脑历史供查询；需要切回电脑模式时先在设备页关闭直传。Windows 上再次启动同端口接收服务会失败，避免请求随机落到另一进程。已开启的历史保留策略在上传时维护；关闭策略不会自行删除记录。

这套服务不直接调用模型。模型访问权限、对话身份、原上下文及持久幂等由你的现有应用提供。真实传感器与震动输出仍需接线和校准，测试模拟不表示实物验收。

## 验收

先核对真实设备 ID 与同步，再注入明确标记的模拟事件，检查归档、ACK、原队列回调与结束后停止。测试替身不证明真实模型回复。见 [直传报告](../reports/DIRECT_SERVER_ACCEPTANCE.md)和 [当前验证汇总](../reports/VALIDATION.md)。
