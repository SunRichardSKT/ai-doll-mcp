# 连接模板：不是已配置的安装

普通用户先用 [安装引导](../docs/start/AI_INSTALL.md)。本目录供开发者接入其他客户端，所有地址、目标和令牌需替换为自己安装的实际值。

| 文件 | 用途 |
| --- | --- |
| `chatgpt-mcp-config.json` | 连接格式示例；不是运行中的服务 |
| `operit/ai_doll.js` | Operit 查询 / 工作流模板，真实平台未验收 |
| `operit/ai_doll_prototype.js` | 独立工作流的限时主动压力回应，见 [免费原型指南](../docs/integrations/OPERIT_PROTOTYPE.md) |
| `operit/ai_doll_chat_probe.js` | 无 MCP／传感器依赖的原聊天定向发送诊断；显示自检输入并分别核对回复与历史 |
| `host-event.example.json` | 自定义接收接口事件格式 |
| `openclaw-hook.example.json` | 已有 OpenClaw 原聊天路由模板 |

普通 Chat 首选 [自定义 MCP 隧道](../docs/integrations/SECURE_MCP.md)。插件 ZIP 可以包装指引和连接信息；上传成功不会部署本机脚本，也不证明工具已开放。

复制模板后，先实际发现工具、调用状态，再验证原聊天的新事件。详细契约见 [宿主接入](../docs/integrations/HOST_INTEGRATIONS.md)，执行助手看 [AI 指南](../docs/ai/AI_GUIDE.md)。
