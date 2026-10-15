# 当前验证范围

> 此页说明验证范围，不能替代你自己的安装测试。 [全部目录](../README.md)


文档更新：2026-10-16。当前交付为 **Bridge / ToolPkg 2.20.0 预发布版，固件 2.9.0**。下列历史报告保留当时版本与证据；当前 STDIO 51 个工具，HTTP 状态／历史／互动配置为 2／9／19 个，不能由旧工具数量推断现版本能力。

## 已有真实证据

| 能力 | 已验证什么 | 证据 |
| --- | --- | --- |
| CH0 实体压力 | 7 组完整真实按压/释放与电脑归档；其余通道未装 | [本轮记录](RELEASE_2_17.md) |
| 一键烧录与固定页面 | 真实 USB 标准烧录、独立新名称、保留校准，联网后热点固定页 HTTP 200 | [本轮记录](RELEASE_2_17.md) |
| 配网与 Wi-Fi | 裸 ESP32、热点 / 恢复、无线采集模拟事件 | [设备报告](DEVICE_LAB_TEST_REPORT.md) |
| MCP 本机工具 | SDK 发现 45 个 STDIO 工具，HTTP 2 / 9 / 13 范围 | [MCP 报告](MCP_ACCEPTANCE_2_13.md) |
| 普通 Chat Secure | 状态、历史、60 秒模拟文字反馈、到期和重启后调用；编号与服务记录匹配 | [MCP 报告](MCP_ACCEPTANCE_2_13.md) |
| Operit 原聊天 | 用户报告原 Operit 已能回应触摸；不据此推断来源为真实传感器或新增部署路径已通过 | [2.20 记录](RELEASE_2_20.md) |
| Windows 完整包 | 内置 Python，在中文 / 空格路径及无系统 Python 环境启动 | [安装报告](SIMPLE_SETUP_ACCEPTANCE.md) |
| 设备直传 | 实际 Wi-Fi / TLS 上传、SQLite、回执、原应用测试回调 | [直传报告](DIRECT_SERVER_ACCEPTANCE.md) |
| Linux 容器 | 隔离 Ubuntu 安装、TLS 信任校验、真实 ESP32 上传、重启 / 更新保留数据 | [安装报告](SIMPLE_SETUP_ACCEPTANCE.md) |
| 接收服务内置 MCP | 当前 SDK 实测 19 工具，历史／摘要／统计、自然陪伴、会话隔离、到期、地址鉴权与撤销 | `tools/test_direct_mcp.py`；[2.20 记录](RELEASE_2_20.md)，新增容器与目标客户端仍待实测 |
| Operit 免电脑代码 | 服务器实际 HTTP／MCP 与模拟上传；手机直连的身份、历史、回执、去重、期限和停止；Android、模型及手机直连设备接口使用明确替身 | [2.20 记录](RELEASE_2_20.md) |
| OTA 与离线 | 裸板正常无线升级；容量、软件重启补传和去重 | [设备报告](DEVICE_LAB_TEST_REPORT.md) |
| PCB 标准化 | 原生 PCB DRC 0，原理图无 error / fatal、2 个聚合 warn；几何保持 | [硬件核对](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/元器件标准化核对记录.md) |

## 明确未完成的验收

- CH1～CH7、FSR 三阶段校准、温度探头、电机与电池供电下的整机体验；CH0 基础压力输入已通过。
- Flash / OTA 写入过程中强制物理断电。
- 普通 Chat 空闲主动唤醒、用户账号的 MCP Events 后台送达。
- Operit 新增服务器／手机直连模式的目标环境、15 分钟持续运行与锁屏；原路径已有用户反馈，新增模式不能沿用该验收结论。
- OpenClaw / 微信的真实账号与原对话路由。
- 固定 Cloudflare 域名、Claude 连接、真实公网服务器与 ACME 证书。
- 用户自定义前后端的真实模型生成；已验证回调使用明确的测试替身。

Sakura 的公网 TLS / SDK 成功不能覆盖普通 Chat 添加失败。Cloudflare 临时通路仅验证两个状态工具。Secure 完成的是限时执行中的模拟反馈，不是无限后台监听。

## 如何验证自己的新安装

1. 检查版本、设备 ID、传感器模式、真实同步时间和错误。
2. 在目标原聊天实际调用工具，取得新返回；网关提供编号时与服务器记录匹配。
3. 查询一条明确模拟来源的新记录，核对通道、部位、单位和时间。
4. 开启 60 秒会话，读新事件、生成原聊天回应，到期 / 结束后不重复投递。
5. 再分别验证自己的硬件、账号和部署环境，不能用 SDK 或旧报告代替。

步骤见 [聊天测试](../integrations/CHAT_MCP.md)。AI 安装助手使用 [执行指南](../ai/AI_GUIDE.md)。

原始调用编号、个人数据和运行诊断保留在各安装者本机 `build/`；公开报告只总结版本与范围。
