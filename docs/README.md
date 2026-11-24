# 使用教程

让娃娃连接网络、记录触摸，并在聊天中回应。先按使用环境选一条安装路线。

配网后按[平台连接指南](integrations/OFFICIAL_CLIENTS.md)接入 ChatGPT、Claude、DeepSeek DSH、Gemini 或 Operit。查看[新版端口设置](daily/SENSOR_CHANNELS.md)了解温度探头的安装与读数。

[项目首页](../README.md) · [下载 v0.1.4 内测版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.4) · [更新说明](../CHANGELOG.md)

成品用户可阅读[图文新手说明书（0.1.3 界面）](product/抱抱星_共感娃娃核心_新手说明书.pdf)，产品介绍和美化图片见[产品资料](product/README.md)。

## 入门

| 你的设备与需求 | 从这里开始 |
| --- | --- |
| 新开发板 | [一键烧录](start/QUICK_FLASH.md) · [首次启动设置](start/FACTORY_SETTINGS.md) |
| 已烧录的娃娃＋安卓手机 | [Operit 首次配对](integrations/OPERIT_NO_PC.md#只有安卓手机没有电脑和服务器) |
| Windows 电脑采集 | [首次安装](start/AI_INSTALL.md) |
| 自有 Linux 服务器 | [服务器部署](integrations/REMOTE_SERVER_SETUP.md) · [本机接收](integrations/SERVER_QUICKSTART.md) |
| ChatGPT 或其他 MCP 客户端 | [选择连接方式](start/MCP_TRANSPORT_DECISION.md) · [ChatGPT 隧道](integrations/SECURE_MCP.md) |

安装后，依次完成[家庭 Wi-Fi 配网](daily/WIFI_CONNECTION.md)、[端口设置](daily/SENSOR_CHANNELS.md)和[压力校准](daily/CALIBRATION_AND_DAILY_MODE.md)。

## 日常设置

- [管理页面与开机使用](daily/USER_GUIDE.md) · [账号与密码](daily/RUNTIME_AND_LOGIN.md)
- [Operit 设置、常开与触摸排队](integrations/OPERIT_SETUP.md) · [自然陪伴](daily/NATURAL_COMPANION.md)
- [人设与反馈](daily/INTERACTION_OBSERVATIONS.md) · [互动历史](daily/HISTORY_MANAGEMENT.md)
- [断网缓存与补传](daily/OFFLINE_RECORDS.md) · [OTA 升级](daily/OTA_UPDATE.md)
- [ChatGPT 状态、历史和互动](integrations/CHAT_MCP.md) · [故障排查](TROUBLESHOOTING.md)

## 制作与扩展

- [硬件代际与文件入口](../hardware/README.md) · [第一代C3全部资料](../hardware/gen1/README.md) · [第二代S3研发进度](../hardware/gen2/README.md)

- [主板、采购与制造资料](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/gen1/pcb/README.md) · [按板型选择外壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/gen1/enclosure/README.md)
- [温度与擦眼泪制作指南](../hardware/gen1/expansion/resistive-inputs/README.md)，例如六路压力、一路 B3950 和一路湿润片。
- [现板扩展参考](../hardware/gen1/expansion/current-board/README.md) · [旧版 DS18B20 资料](daily/DIGITAL_TEMPERATURE.md)

## 开发与接口

- [开发与打包](developers/DEVELOPER_GUIDE.md) · [项目结构](developers/REPOSITORY_LAYOUT.md) · [给 AI 的使用说明书](ai/AI_GUIDE.md)
- [MCP 工具](developers/MCP_TOOLS.md) · [其他宿主接入](integrations/HOST_INTEGRATIONS.md) · [远程 MCP](integrations/REMOTE_MCP.md)
- [设备直传](developers/DIRECT_SERVER.md) · [原应用接入](developers/EXISTING_CHAT.md) · [主动事件桥](developers/PROACTIVE_INTERACTION.md)
- [后续计划](developers/DEVELOPMENT_PLAN.md) · [交付文件](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md) · [项目许可](../LICENSING.md)

## 实现与检查记录

[验证汇总](reports/VALIDATION.md) · [固件功能](reports/FIRMWARE_INPUTS.md) · [网络与空间](reports/FIRMWARE_NETWORK.md) · [Wi-Fi 提示](reports/WIFI_FEEDBACK.md) · [固件精简](reports/FIRMWARE_TRIM.md) · [0.1.2 电阻扩展](reports/RESISTIVE_INPUTS_012.md)
