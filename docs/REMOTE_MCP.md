# 普通 Chat：Sakura 私密地址 MCP

Bridge 2.13.0，固件仍为 2.7.0。保留当前聊天、模型、人设和上下文；不建立娃娃账号、不要求娃娃密码、不另接模型服务。此流程使用 ChatGPT 已有账号以及 Sakura 的隧道账号。

## 连接路径

ESP32（Wi-Fi）→ 本机采集服务 → SQLite → 专用 MCP → Sakura HTTPS → 原 Chat。

普通触摸持续记录。历史工具直接读电脑数据库，后台采集器负责同步。设备离线仍能读已有记录；返回 `history_source`、`last_sync`、`sync_age_sec`、`collector_error`，不能将旧记录误报为当前动作。通道配置是后台缓存，返回 `configuration_saved_at`；首次同步前明确 `available=false`。

本机 STDIO 仍有 45 个工具；本机 HTTP 保持 `http://127.0.0.1:8771/mcp`，仅监听电脑。远程默认使用另外的入口：

```text
https://已绑定的主机及端口/64位随机十六进制串/mcp
```

随机串来自 32 字节安全随机数，重启保留，可在本机重置。完整地址就是访问凭据，知道地址的人可以调用该配置的工具。所有其他路径返回 404，不转发设备设置、数据库、电脑管理页或 OAuth 登录页。两个入口使用同一端口，不能同时启动。

## 第一次安装

### 已经登录 Sakura 客户端：无需向项目提供访问密钥

推荐直接沿用已经登录的 Sakura 客户端。访问密钥由 Sakura 客户端保管，AI Doll 不读取、不保存，也不再启动第二个 frpc。电脑采集服务和本机 MCP 仍由项目启动、停止和检查。

在 Sakura 客户端编辑专用隧道：TCP、本地地址 `127.0.0.1`、本地端口 `8771`、自动 HTTPS 为“自动”，并绑定受信任证书的子域。开启这一条隧道，保持客户端运行。

安装本机桥后，在项目根目录运行：

```powershell
.\tools\remote_mcp.ps1 -Action configure -ClientManaged -Profile interaction
.\tools\remote_mcp.ps1 -Action start
```

配置只询问 HTTPS 主机地址（TCP 通常带外网端口），不询问隧道 ID 或 Sakura 访问密钥。项目配置记录 `tunnel_management=client`，不包含 `token`。之后仍使用下文的一键启动、状态、停止、验证和地址重置入口。停止项目服务不会停止 Sakura 客户端或它管理的任何隧道。

状态必须通过真实 HTTPS 和 MCP 工具发现才显示连接成功；仅客户端已登录或已开启不算成功。设备暂不可用时，本机历史仍能查询，不能将采集忙碌或缓存数据当作设备离线或实时动作。完整连接地址由项目生成，不能只把域名或普通 `/mcp` 填入 Chat。

### 需要程序自行管理 Sakura 隧道：可选自动部署

先安装 Python 3.12，将代码包解压至固定目录，在项目根目录打开 PowerShell。设备和电脑应处于互通局域网，设备使用独立电源即可。

```powershell
.\tools\install_chat_mcp.ps1 -DeviceHost 192.168.1.50
```

将 IP 换成设备地址。安装器创建环境、安装固定依赖、首次配对、发现已有设备、启动采集器、实际调用本机状态工具，并下载校验官方 Sakura 客户端。已有配对可省略 `-DeviceHost`。设备令牌由配对程序在本机隐藏输入。

在 Sakura 管理面板完成一次：

1. 选择专用 TCP 隧道，将本地地址设为 `127.0.0.1`、本地端口 `8771`。不要复用设备设置页的 8768 端口。
2. 在隧道的额外配置开启 `auto_https = auto`，然后绑定 Sakura 子域及受信任 HTTPS 证书。官方 `nyat.app` 子域方案无需另外购买域名；首次签发可能需要等待。
3. 记下专用隧道 ID、完整 HTTPS 主机地址（TCP 隧道通常需要带外网端口），取得 Sakura 访问令牌。

按 [Sakura 子域与证书说明](https://doc.natfrp.com/bestpractice/domain-bind.html) 操作；自动 HTTPS 将公网 TLS 转为本机 HTTP，见 [官方说明](https://doc.natfrp.com/frpc/auto-https.html)。不能将原始 HTTPS 隧道直接指向本机 HTTP 服务。

在本机运行配置入口：

```powershell
.\tools\remote_mcp.ps1 -Action configure -Profile interaction
```

此可选模式输入 HTTPS 主机地址、隧道 ID 和访问令牌。令牌隐藏输入并保存到本机私有目录，不发送到聊天。先关闭已有客户端中的这一条专用隧道，避免两个客户端重复连接。配置程序生成随机地址；不会为娃娃创建账号。已登录客户端的用户优先使用上面的 `-ClientManaged` 模式。

然后启动并验证：

```powershell
.\tools\remote_mcp.ps1 -Action start
.\tools\remote_mcp.ps1 -Action verify
```

`start` 会复用本项目已运行的服务。状态只有在实际进程存在、HTTPS 证书受信任且官方 SDK 已发现正确工具后才显示远程连接成功；不会忽略证书错误。首次证书签发、网络故障会重试，间隔从 1 秒退避到 60 秒。Sakura 客户端通过私有配置文件启动，访问令牌不进入进程参数，原始客户端输出不保存。

## 添加到普通 Chat

打开本机 `build/device-lab/remote-mcp/chatgpt-connection-private.json`，复制其中完整 URL。文件含访问凭据，请勿公开或放入 GitHub。

在 ChatGPT **Plugins → 添加 → 创建自定义 MCP 服务器** 填写 URL，身份验证选“无”。核对实际发现的工具，再在原普通 Chat 用 `@` 选中连接。平台操作见 [OpenAI 官方连接说明](https://developers.openai.com/plugins/deploy/connect-chatgpt)。云端不能直接调用用户电脑的 localhost。

三个配置：

| 配置 | 工具数 | 用途 |
| --- | --- | --- |
| `status` | 2 | 安装状态、实时设备状态 |
| `history` | 9 | 两个状态、通道能力与配置、人设、偏好、历史、摘要、统计；均为只读 |
| `interaction`（默认） | 13 | history 加会话开始、状态、新事件、结束 |

远程不提供模拟注入、改人设、开真实采样、控制震动或删除历史。模拟测试在本机 <http://127.0.0.1:8768/companion> 操作。

先在 Chat 发送：

> 请实际调用 get_installation_status 和 doll_get_status，返回设备状态及各自 verification.call_id。没有工具时如实说明。

再发送：

> 查询今天的互动，保留通道、部位、时间、数值、单位和模拟来源，按照保存的人设和本聊天上下文回应。

互动测试请求：

> 开始 60 秒互动。为本聊天保存独立 chat_id，实际调用 start_interaction(duration_sec=60)，记住返回 id、deadline；每次等待最多 20 秒，用 session_id 和 next_cursor 读取新事件。收到模拟按压后在当前聊天按保存的人设回应。同一 touch_id 的 start 只给一次主要反馈，end 用来更新持续时间。到期或我说结束时结束；没有事件不要编造反馈。

期限由服务器负责，不依赖 AI 计时。相同 chat_id 重试不会延长会话；不匹配的 chat_id 不能抢占、读取或结束该会话。新事件读取和结束会话必须同时提供原 `chat_id` 与 `session_id`，这用于防止会话误串，不代表独立用户身份认证。结束/到期后，新事件接口返回 `session_closed=true` 和空事件，不继续投递旧动作；普通历史仍可查询。一次单通道按压不能直接称为拥抱。

## 日常操作

| 操作 | 入口 |
| --- | --- |
| 一键启动 | 双击 `tools/Start_Remote_MCP.cmd` |
| 检查状态 | `remote_mcp.ps1 -Action status` |
| 实际 SDK 验证 | `remote_mcp.ps1 -Action verify` |
| 停止远程 MCP 与隧道 | 双击 `tools/Stop_Remote_MCP.cmd` |
| 重新生成私密地址 | `remote_mcp.ps1 -Action reset-address` |

停止仅终止本项目记录且进程创建时间与可执行文件仍匹配的远程服务，不停止已有电脑采集器或其他 Sakura 隧道。电脑后台采集可继续。重置地址使旧地址的新请求立即返回 404，历史不删除；已执行的请求不能撤销。重置后请更新 ChatGPT 连接并刷新工具。

进程、连接和错误状态存于本机私有目录。`status` 显示上次检查时间；`verify` 是即时检查。详细 SDK 结果见 `remote-check.json`，服务调用编号见 `calls.jsonl`。后者仅记录编号、时间、工具名称、配置与完成状态，不记录地址或互动内容。SDK 验证结果不会自动算作普通 Chat 验收。

创建连接失败时，检查私有运行目录的 `connection-diagnostics.jsonl`，并记录目标 Chat 重试时间。同一 `request_id` 关联 `received`（请求到达）、`response`（响应开始）及未响应退出阶段，能够识别“已到达但未返回”的情况。该诊断只保留编号、时间、HTTP 方法、路径是否匹配、Host 分类、是否存在 Origin、Accept 类型、已知 RPC 方法、有限退出分类和响应状态；不保存实际地址、请求参数、设备数据或响应内容。日志自动轮换，诊断写入失败不影响 MCP。`initialize` 和 `tools/list` 的 `response` 均为 200 才表示握手与工具发现成功。

部署自检的 `probe_kind=health`，手动 SDK 验证为 `verification`，其他请求为 `unmarked`。这个标记只是诊断提示，不能作为身份认证，也不能单独证明请求来自 ChatGPT。结合实际重试时间、未标记请求和工具返回的调用编号验收；不能将后台成功当成 Chat 成功。若有 `received` 而没有对应 `response`，先检查请求处理；若重试期间没有到达记录，再排查公网可达性、DNS、TLS 和目标平台连接限制。旧版只记录响应开始的日志不能证明请求从未到达。

远程入口使用 POST 返回 MCP JSON；GET 在通过地址与 Host/Origin 检查后返回 405，并提供 `Allow: POST`，不打开闲置 SSE 流。浏览器打开地址看到 405 不表示服务离线，应使用 MCP 客户端完成初始化和工具发现。添加失败时可暂用 `status` 的两个状态工具作最小对照，成功后恢复 `interaction` 并刷新工具；这不会删除历史或改变传感器配置。

如果本机 SDK 通过，而目标 Chat 重试期间没有额外请求，先确认完整地址，再准备一条不同节点的标准 HTTPS 入口作对照。Sakura 的 HTTPS 隧道使用远程 443；TCP 隧道使用自定义远程端口。选择有“建站”标记的非内地节点，新建专用 HTTPS 隧道，本地仍为 127.0.0.1:8771，使用自动 HTTPS 和已绑定子域的受信任证书。新入口须完成证书、官方 SDK 和实际 Chat 验证后，才能报告接入成功。不能直接从旧 TCP 地址删掉端口，也不能仅凭错误推断平台禁止非 443 端口。具体配置见 [Sakura Web 应用指南](https://doc.natfrp.com/app/http.html)、[自动 HTTPS 配置](https://doc.natfrp.com/frpc/manual#自动-https-功能) 和 [子域绑定](https://doc.natfrp.com/bestpractice/domain-bind.html)。

运行目录只对当前 Windows 用户及 SYSTEM 授予权限。无需公开密钥、配对配置或 SQLite。公共交付仅包含模板。可安装的私人插件 ZIP 仅在 HTTPS 实际通过验证后生成，不能公开；上传成功也不等于工具接通。

## 验收边界

电脑和服务必须运行才能持续采集和供云端调用。云端 AI 查询的数据会发送给该平台。普通 Chat 空闲唤醒不在本轮承诺内；MCP Events 当前支持范围应按 [OpenAI 官方事件说明](https://developers.openai.com/plugins/build/mcp-events) 单独验收。

本机状态、SDK 协议、Sakura HTTPS 和目标 Chat 实测分别记录。无可信 HTTPS 和实际 MCP 连接结果时，不能报告 Sakura 部署成功。当前未接实体传感器，所有压力验收为模拟，物理输出关闭。Cloudflare 与 Claude 在 ChatGPT 完整验收后再安排。
