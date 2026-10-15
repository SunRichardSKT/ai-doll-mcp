# Operit 旧原型说明（0.1.x）

新安装请使用 [统一工具包与管理入口](OPERIT_SETUP.md)。本页仅保留旧版本排错过程，不再作为默认安装步骤。

本原型沿用 Operit 已有聊天、模型和角色，只做有限时间的触摸接入。不购买服务器、域名或隧道。第一步可完全不接开发板，使用单独的模拟演示数据库；真实设备模式继续使用已保存的校准和历史。

## 1. 准备

1. 从 [Operit 官方 Releases](https://github.com/AAswordman/Operit/releases)下载安装 Android APK。不要下载本项目的 ZIP 当作 Operit APK。
2. 手机和电脑连接同一个家庭 Wi-Fi／局域网。电脑通过网线接同一路由器也可以；先避免访客网络和隔离网络。
3. 电脑使用现有完整 AI Doll 软件包，根目录应有 `python/` 和 `tools/`。把本原型增量包解压到同一根目录，保留目录结构。增量包不包含另一份 Python，也不是独立服务完整包。
4. Operit 先配置一个可用模型，并确认能在普通聊天正常回复。模型由用户选择：本机模型不需要云端 API 费用，云端模型是否免费取决于服务提供方和账号额度。本项目不预置模型密钥，不默认替你选择提供方。

本轮核对了 Operit main 的 `Tools.Chat`、`Tools.Files` 和 `Tools.Net` 文档。你的 APK 版本仍需实际验收，尚未保证所有历史版本兼容。

## 2. 先用模拟演示

双击根目录 `Start_Operit_Demo.cmd`（仅旧原型包），从列表选择手机可访问的电脑地址。窗口会打印类似下面的完整 MCP 地址：

```text
http://电脑局域网IP:8775/本机生成的随机串/mcp
```

不要复制上面的示例，复制你窗口的实际输出。这里的 IP 不能填手机的 `127.0.0.1`。此地址接受 MCP POST；浏览器直接打开返回 405 并不代表连接失败。

保持窗口运行。演示使用 `build/operit-demo/`，身份明确为 `operit-demo-not-hardware`，来源为 `simulation`，不会连接串口、改动真实历史、校准或开启物理输出。每次新会话开始约 3 秒后自动产生一次头顶模拟按压，约 2 秒后释放。

如果 Windows 弹出网络访问提示，只对你当前使用的可信私人网络放行。打不开时先检查 IP、同一路由器和私人网络防火墙；本项目不会自动修改系统防火墙。

如果旧 0.1.0 包启动时报中文乱码、UnexpectedToken 或缺少右大括号，更新到 0.1.1 并覆盖同名文件；这是 Windows PowerShell 5.1 的脚本编码问题，不需要重装 Python 或刷开发板。

## 3. 手机导入和绑定

将以下两个 JS 文件传到手机，在 Operit 的包管理／沙盒包导入入口导入并启用：

- [ai_doll.js](../../templates/operit/ai_doll.js)：19 个 MCP 互动工具的查询和配置入口。
- [ai_doll_prototype.js](../../templates/operit/ai_doll_prototype.js)：有限时间的手机主动读取与原聊天发送。

JS 是 Operit 沙盒工具包，不是 ChatGPT 插件 ZIP。具体入口以你安装版本为准。[官方包管理说明](https://github.com/AAswordman/Operit/blob/main/examples/operit_editor.ts)。

在原聊天可以让 AI 使用 `ai_doll:call_mcp` 实际调用 `get_installation_status`、`doll_get_status`，`mcp_url` 填刚复制的地址。演示状态必须显示模拟身份，不能当作真实 ESP32 在线证明。

调用 `ai_doll_prototype:list_existing_chats`，选中你已经使用的聊天，保存真实 `id`。不要写通用 `main`，也不要让脚本创建另一个聊天。列表工具可以由 AI 调用，但监听必须在独立 Workflow 中启动。

## 4. 运行一次 60 秒工作流

创建一个独立工作流，增加“触发器”节点并选择“手动触发”，再增加工具调用节点，选择 `ai_doll_prototype:listen_interaction`。必须将触发器输出连接到工具节点输入并保存，不能只有工具节点：

```text
手动触发 → ai_doll_prototype:listen_interaction
```

然后填写工具参数：

| 参数 | 填法 |
| --- | --- |
| `mcp_url` | 电脑窗口输出的完整地址 |
| `chat_id` | 上一步已有聊天的真实 ID |
| `state_path` | Operit 有读写权限的 Android JSON 文件绝对路径；父目录需已存在 |
| `workflow_confirmed` | 布尔值 `true` |
| `duration_sec` | `60`；初次也可先填 `15` |

状态路径可以选择你已授权给 Operit 的工作目录，例如该目录下的 `ai_doll_delivery.json`。确认文件权限后再运行；无法读写时原型会停止，不绕过权限。每个聊天／MCP 地址使用独立文件，不覆盖其他用途的文件。

首次推荐填 `/storage/emulated/0/Download/ai_doll_operit_delivery.json`，前提是手机存在 Download 文件夹且 Operit 有文件访问权限。JSON 文件不必预建，脚本首次运行自动创建。`/storage/emulated/0/Download/Operit/` 只有文件夹名，不能直接作为 state_path；若要放在 Operit 子文件夹中，先创建该子文件夹，再填到 `.../Operit/ai_doll_operit_delivery.json`。0.1.3 会在会话开始前检查文件名、目录类型与父目录。

同一个目标只运行一个工作流实例。版本允许设置执行超时时，给该节点至少 120 秒；不允许时先使用 15 秒测试并回报实际错误，不声称已验收 60 秒。禁止让目标 AI 在自己的工具执行轮中调用监听：这会与发送给自己的新一轮消息冲突。

运行工作流后回到原聊天，先不要再发消息。模拟按压到来时，应由原聊天模型产生一次简短回应，并说明是模拟触摸。释放不应再产生第二次主要回应。角色、人设、模型继续沿用原聊天。

Operit 的 `hide_user_message` 隐藏触摸输入正文，但宿主可能显示占位标记，不能保证界面完全没有痕迹。工具卡片和权限提示由 Operit 控制。

## 5. 真实 FSR 模式

停止演示窗口，再启动 `AI_Doll.cmd`，核对真实设备当前身份、采集状态和 CH0 校准。采集未在线时不能把演示模式的结果冒充真实设备结果。

在设备陪伴设置中明确开启“聊天融入”和“触摸主动回应”，并确认 CH0 的部位反馈等级为正常。也可通过 `ai_doll:call_mcp` 调用：

```json
{
  "tool": "update_companion_preferences",
  "arguments_json": "{\"changes\":{\"chat_integration_enabled\":true,\"proactive_enabled\":true}}"
}
```

双击 `Start_Operit_Prototype.cmd`（仅旧原型包），复制真实模式的新 MCP 地址。它与演示地址属于不同安装，请改用另一份状态文件，再启动相同工作流。运行后按压实际连接的 J1；只有 CH0 接入时只验收 CH0。

轻回应部位保留给正常聊天融入，关闭部位不主动回应。温度和震动不会触发本轮压力原型；震动不作为用户触摸。

## 6. 停止与异常恢复

- 到期自动结束服务器会话。独立工作流调用 `stop_interaction` 可提前结束，参数使用原地址、聊天 ID 和状态路径。
- 在真实设置页关闭主动开关会阻止后续新发送。已经提交给 Operit 的模型请求，目前不能保证撤回；不要把“停止监听”解释为已经取消宿主正在生成的回复。
- 发送前将待发送事件写入状态文件；发送超时、回复缺失或结果不明确会暂停，后续启动也不会自动重复发送。
- 在原聊天核对后，由用户调用 `reconcile_delivery`，已收到回复选 `delivered`，确定完全没发送选 `not_sent`。前者只补服务器确认，不重新调用模型；后者仅解除阻塞，过期触摸仍不会重放。
- 如果输入已出现但模型超时／只有不完整回复，用户确认放弃本次触摸后可选 `discard`。这将本次上下文标记已处理并解除阻塞，不重发，也不声称模型回复已完整展示。
- 发送成功但 MCP 确认失败时，恢复只重试确认，不重新生成。
- 不删除状态文件来绕过发送结果不明确的问题。文件损坏会停止；先核对原聊天再恢复。

### 工作流启动报错

- `Workflow has no trigger node`：补上“手动触发”节点，并连接到工具节点，保存后从工作流运行。
- `AI Doll [delivery_state]: File does not exist` 且路径以 `/` 结尾：填入了目录，改成包含 `.json` 文件名的完整路径。父目录先创建并授权，JSON 文件由脚本生成，不要手动填入空文件或覆盖旧发送恢复记录。
- `Chat service not connected`：0.1.0／0.1.1 在主聊天发送前调用了依赖悬浮窗服务的 `agentStatus`。手机重新导入 0.1.2 的 `ai_doll_prototype.js`，刷新／重新启用包；原工作流和参数保留。只更新电脑文件不会更新已导入手机的脚本。
- 0.1.2 改为用 `findChat` 精确核对已有聊天 ID，并使用 `runtime: main` 的原生发送等待；不以悬浮窗状态判断主聊天是否忙碌。等待及生成超时受上下文新鲜度和会话期限共同限制。用户仍须从独立工作流启动，不能在目标 AI 工具轮里递归运行。
- 若只有 `Workflow execution failed`，打开该次执行日志，找到最下面的节点错误。0.1.2 会附带 `AI Doll [chat_binding]`、`[mcp_connection]`、`[delivery_state]`、`[event_read]`、`[main_chat_send]` 等阶段。提供该节点错误和 Operit 版本后继续定位，不能把总失败提示当成 MCP 网络错误。
- `AI Doll [main_chat_send]: Timeout waiting for AI reply`：已经调用原聊天发送 API，但没有按时取得完整回复。先查看绑定聊天是否有模拟输入、部分回复，以及手动发送“你好”能否正常回复。不要删状态文件后反复运行；先核对再用上述恢复工具。0.1.4 修复短会话把回复等待一并截短的问题：15 秒／60 秒限制新触摸的接收和新发送；已发送的回复可在此后完成。由于 Operit 原生 API 对排队和生成共用一个超时，仍保留上下文的新鲜度限制，默认等待上限约 30 秒，不能承诺慢模型无限等待或自动续接。新工作流执行可先用 60 秒；修改此值不会替代模型配置检查。

### 手动聊天正常，但工作流收不到回复

先用独立的 [ai_doll_chat_probe.js](../../templates/operit/ai_doll_chat_probe.js) 排查。它不连接 MCP，不依赖电脑或传感器，也不会改动触摸状态文件，不替换模型或新建聊天。手机导入启用该独立沙盒包。

1. 先在原聊天实际调用 `ai_doll_chat_probe:inspect_chat`，参数 `chat_id` 填工作流绑定的 ID。核对结果中的 `title` 与 `is_current`，确认测试的是你手动聊天的那个已有对话。它只返回近期消息的发送者、时间与模型元数据，不发送消息。
2. 新建一个独立手动工作流：手动触发 → 工具节点 `ai_doll_chat_probe:send_probe`。必填只有 `chat_id` 和布尔 `workflow_confirmed=true`。`state_path` 可以不填，默认在手机 Download 目录生成单独的诊断文件；父目录需可读写。不要填触摸原型的状态文件。
3. 可选 `timeout_sec` 默认 90，范围 30～120 秒。工作流／节点执行时限应至少覆盖该值再加少量文件操作时间；如版本不能配置，提供实际执行日志，不把外层工作流超时当作模型成功或失败证据。
4. 从工作流界面手动启动，回到原聊天观察。应出现一条可见的“AI Doll 后台发送自检 probe_…”输入，期望模型回复“后台连接正常 probe_…”。此诊断有意显示输入，避免隐藏触摸输入影响排查。
5. 查看工具节点输出：`target.title`／`target.is_current` 确认目标；`reply_returned` 表示发送 API 返回完整非空回复；`reply_nonce_matches` 检查本次编号；`history_probe_present` 表示数据库里找到了此次自检输入或回复；`history_ai_reply_present` 表示数据库里找到带本次编号的 AI 回复。数据库记录仍不等于已验证屏幕展示，`display_verified` 保持 false，由用户观察确认。

诊断结束但发送失败时，节点可能仍显示“检查完成”；以 `reply_returned`、`error` 和记录证据为准，不把工作流绿色完成图标视为聊天已成功。没有取得完整回复时保留诊断文件并阻止同一次检查自动重发；再次运行会返回之前状态。不要删除旧触摸 JSON 来绕过未确认记录。请提供该次诊断输出与 Operit 版本，再决定是否需要其他接入方式。

## 7. 验收边界

本原型是手机主动轮询的有限时间工作流，不是正式 MCP Events 的宿主后台订阅。电脑窗口和工作流需要运行；当前未承诺锁屏、强制停止应用或全天后台持续监听。

本机已验证真实 MCP HTTP、19 工具、模拟压力入库、原型发送回调、按聊天确认、重复／释放过滤和异常恢复；Android 聊天与模型发送在本机测试中是明确的测试替身。完整结果见 [原型验证记录](../reports/OPERIT_PROTOTYPE_VALIDATION.md)。

手机实测时依次记录：实际工具调用 → 独立工作流收到新事件 → 原模型回复 → 原聊天可见。发送接口成功与服务器 ACK 都不能单独证明最终展示。之后再分别测试锁屏、切换聊天、断网和结束。
