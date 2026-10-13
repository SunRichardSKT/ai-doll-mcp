# ChatGPT 普通 Chat：Secure MCP 配置

> 按本页步骤操作即可；无需读完开发者资料。 [全部目录](../README.md)


用于在原 ChatGPT 对话中查询和互动。先完成 [电脑安装与设备配对](../start/AI_INSTALL.md)。数据保存在电脑，日常需要电脑与后台服务运行。

准备好：可用的 ChatGPT 账号、对应 Platform 隧道权限，以及已在线的电脑采集。完成后应在原聊天真正调用设备状态，而不只是看到插件名称。

## 第一次需要准备什么

在 [Platform 隧道设置](https://platform.openai.com/settings/organization/tunnels)创建自己的专用隧道，并关联目标 ChatGPT 工作区 / 账号。在 API keys 中创建隧道运行密钥。

创建 / 管理隧道需要 **Tunnels Read + Manage**；运行需要 **Read + Use**。运行密钥用于隧道，不是娃娃账号或模型密钥。账号策略和关联以 [官方说明](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)为准。

## 在管理中心保存

1. 双击 `AI_Doll.cmd`，进入 **AI / MCP 连接**。
2. 填写自己的 `tunnel_…` ID 和运行密钥，选择需要的工具范围。
3. 点击 **保存并启动**，等待实际连接检查通过。程序下载并校验官方客户端。
4. 已有配置的密钥输入框可留空保留；不需要因电脑界面更新重刷设备。

## 在普通 Chat 添加

1. 打开 Plugins，创建自定义 MCP 服务器。
2. 选择 **隧道**，选择或填写相同 ID。
3. 选择 **无需身份验证**，创建连接并添加到原聊天。
4. 按 [聊天验证](CHAT_MCP.md)实际调用两个状态工具，再进行历史与模拟互动测试。

若看不到隧道，检查关联的工作区和运行权限。添加步骤见 [官方连接说明](https://developers.openai.com/api/docs/guides/custom-mcp-server)。官方 UI 或权限变化时，以实际页面为准。

本页的隧道、工作区关联及连接步骤已于 2026-10-13 对照上述官方文档核对。没有创建权限时，需要对应账号/工作区管理员处理；重新烧录娃娃不会补齐平台权限。

## 工具范围怎么选

| 范围 | 数量 | 适合用途 |
| --- | --- | --- |
| `status` | 2 | 先验证安装和设备状态 |
| `history` | 9 | 只读通道、人设、偏好、历史、摘要和统计 |
| `interaction` | 13 | 在只读基础上创建、读取、检查和结束会话 |

远程不开放模拟注入、配置写入、删除或物理输出控制。修改范围后在 ChatGPT 刷新连接的工具。名称见 [工具目录](../developers/MCP_TOOLS.md)。

## 每天启动、停止和核对

- 给娃娃供电联网，双击 `AI_Doll.cmd`，复用已有采集和隧道实例。
- 点击“检查状态”，核对实际连接；只有进程或健康页存在，不代表隧道已连通。
- “停止连接”仅停止本项目 Secure 和专用网关，电脑采集继续。
- “重置连接地址”使旧内部路径失效；隧道 ID 保持不变，随后在原 Chat 再次调用验证。

状态调用编号可在管理中心核对。开发者也可用：

```powershell
.\python\python.exe tools/verify_chat_calls.py --installation-call-id 实际编号1 --device-call-id 实际编号2
```

本机配置在 `build/device-lab/secure-mcp/`，专用网关默认 8774，只监听回环。设备设置页和数据库不转发。

## 尚未保证的能力

已验证状态、历史、60 秒模拟反馈和重启后调用，不保证普通 Chat 空闲唤醒。使用云端 AI 时，查询数据会发送给该平台。连接错误见 [故障排查](../TROUBLESHOOTING.md)；阶段证据见 [MCP 报告](../reports/MCP_ACCEPTANCE_2_13.md)。
