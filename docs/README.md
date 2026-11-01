# 使用教程

**v0.1.1 · 内测0.1.1版**。[下载](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1) · [本版说明](../CHANGELOG.md)

## 入门

| 你要做什么 | 教程 |
| --- | --- |
| 给新板烧录 | [一键烧录](start/QUICK_FLASH.md) · [出厂设置](start/FACTORY_SETTINGS.md) |
| 连接家庭Wi-Fi | [配网、配对与恢复](daily/WIFI_CONNECTION.md) |
| 安卓手机使用 | [Operit设置](integrations/OPERIT_SETUP.md) · [免电脑使用](integrations/OPERIT_NO_PC.md) |
| Windows电脑使用 | [首次安装](start/AI_INSTALL.md) |
| Linux服务器部署 | [快速部署](integrations/REMOTE_SERVER_SETUP.md) · [本机接收](integrations/SERVER_QUICKSTART.md) |
| 选择AI连接方式 | [连接方式](start/MCP_TRANSPORT_DECISION.md) · [ChatGPT Secure](integrations/SECURE_MCP.md) |

## 日常设置

- [管理页面](daily/USER_GUIDE.md) · [运行环境与账号密码](daily/RUNTIME_AND_LOGIN.md)
- [接线与端口](daily/SENSOR_CHANNELS.md) · [压力校准](daily/CALIBRATION_AND_DAILY_MODE.md) · [DS18B20温度](daily/DIGITAL_TEMPERATURE.md)
- [自然陪伴](daily/NATURAL_COMPANION.md) · [人设与反馈](daily/INTERACTION_OBSERVATIONS.md)
- [互动历史](daily/HISTORY_MANAGEMENT.md) · [断网缓存](daily/OFFLINE_RECORDS.md) · [OTA升级](daily/OTA_UPDATE.md)
- [ChatGPT中的状态、历史和互动](integrations/CHAT_MCP.md)
- [其他宿主接入](integrations/HOST_INTEGRATIONS.md) · [远程MCP接口](integrations/REMOTE_MCP.md)

## 制作与开发

- [主板与采购资料](../hardware/rev-v2/README.md) · [外壳模型](../hardware/enclosure/README.md)
- [现板扩展设计：开关居中靠下的内测板](../hardware/expansion/current-board/README.md)
- [开发与打包](developers/DEVELOPER_GUIDE.md) · [项目结构](developers/REPOSITORY_LAYOUT.md)
- [MCP工具](developers/MCP_TOOLS.md) · [直传接口](developers/DIRECT_SERVER.md)
- [原应用接入](developers/EXISTING_CHAT.md) · [主动事件桥](developers/PROACTIVE_INTERACTION.md)
- [后续计划](developers/DEVELOPMENT_PLAN.md) · [检查记录](reports/VALIDATION.md)
- [固件网络优化与空间评估](reports/FIRMWARE_NETWORK.md)
- [给AI的使用说明书](ai/AI_GUIDE.md)

遇到问题从[故障排查](TROUBLESHOOTING.md)开始，下载文件见[交付目录](../delivery/README.md)。

- [固件调试精简与扩展取舍](reports/FIRMWARE_TRIM.md)

当前本地固件已改为仅压力/开关的`pressure-switch-v1`，温度、动作和外接输出设计不再是当前驱动能力。见[最新固件说明](reports/FIRMWARE_INPUTS.md)。

设备配网页已增加扫描/连接等待、30秒后的排查建议及只读“检查连接状态”。保存成功不等于联网，切网失联保留入口；详见[Wi-Fi提示说明](reports/WIFI_FEEDBACK.md)。
