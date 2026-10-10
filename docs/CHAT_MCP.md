# 在原聊天使用娃娃

沿用原 AI、模型、人设与上下文。设备网页用于配网、通道、校准、日志和模拟测试，回复由当前聊天的 AI 生成。

| 环境 | 接入 | 验证范围 |
| --- | --- | --- |
| 支持本机 MCP 的客户端 | STDIO，45 个工具 | 官方 SDK 已实测，目标客户端需导入配置 |
| 支持本机 HTTP 的客户端 | `chat_mcp_gateway.py`，2/9/13 个工具 | 只监听本机；history 只读，interaction 支持限时会话 |
| ChatGPT 普通 Chat | Secure MCP Tunnel + 本机专用网关，13 工具 | 已实际通过状态调用、今天历史与 60 秒模拟按压文字反馈，编号与会话记录匹配 |
| 已有 API 应用 | 原后端接事件桥 | 使用原模型回调和原消息列表；不另建聊天产品 |

普通 Chat 推荐 [Secure 操作指南](SECURE_MCP.md)：首次创建自己的 Platform 隧道与运行密钥，在 ChatGPT 添加隧道；之后双击 `Start_Secure_MCP.cmd`。无需娃娃账号，沿用原聊天模型。只连接专用回环 MCP，不转发 8768 管理页。

Sakura 入口仍保留，见 [Sakura 操作](REMOTE_MCP.md)。已登录客户端的用户使用 `remote_mcp.ps1 -Action configure -ClientManaged`，仅输入 HTTPS 主机地址，客户端自行管理隧道。此路线 SDK 通过，但当前普通 Chat 添加失败原因未确定。Cloudflare Quick Tunnel 的两个状态工具已通过普通 Chat，保留为备用；正式固定域名和 Claude 接入另行验收。

本机安装见 [AI 安装指南](AI_INSTALL.md)。本机 HTTP 启动：

```powershell
.\.venv\Scripts\python.exe tools/chat_mcp_gateway.py --profile interaction
```

只读历史可选 `--profile history`；两个状态可选 `--profile status`。地址为 `http://127.0.0.1:8771/mcp`。这个本机入口不能直接当成完整匿名公网入口；使用 `remote_mcp.py` 的私密地址校验。它们不能同时占用 8771。

普通触摸持续归档，明确互动时才开启会话。`start_interaction` 新增可选 `duration_sec`，旧调用兼容；60 秒测试设置 `duration_sec=60`。每次等新事件最多 20 秒，处理后保存游标；结束和到期后不再投递旧事件。保留类型、部位、数值、单位、质量与模拟来源，动作含义由 AI 根据对话判断。

2026-10-10，Secure 在普通 Chat 实际读取通道、人设、反馈偏好、今天历史并开启 60 秒会话，收到 4 次模拟头部按压并给出文本反馈。8 条开始/释放事件与数据库匹配，期限届满自动结束。保存的人设为空，本轮使用温柔自然偏好；模拟输入不能换算为真实力度。分阶段证据见 [验收报告](MCP_ACCEPTANCE_2_13.md)。

阅读 GitHub、上传代码 ZIP 或上传插件 ZIP 都不等于工具已经接通。插件包可以保存技能与连接信息，不会在云端运行电脑脚本。需要在目标 Chat 真实发现并调用工具，返回 `verification.call_id`，随后验证历史与限时按压反馈。

普通 Chat 空闲唤醒不属于本轮交付。宿主主动事件支持另行验收，见 [MCP Events 官方说明](https://developers.openai.com/plugins/build/mcp-events)。
