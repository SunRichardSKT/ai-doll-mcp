# 文档导航

不需要按顺序读完所有文档。先选择安装路径，完成一次模拟互动，再按需要查看其他页面。

## 安装与连接

| 场景 | 入口 |
| --- | --- |
| 不知道该选哪种方式 | [连接方式选择](MCP_TRANSPORT_DECISION.md) |
| Windows 第一次使用 | [首次安装](AI_INSTALL.md) → [管理中心](GUI_GUIDE.md) |
| ChatGPT 普通 Chat | [Secure MCP 配置](SECURE_MCP.md) → [原聊天测试](CHAT_MCP.md) |
| 自己的应用，电脑接收 | [本机接收服务](SERVER_QUICKSTART.md) |
| 自己的远程 Linux 服务器 | [快捷部署](REMOTE_SERVER_SETUP.md) |
| 设备直接上传和应用接口 | [直传技术说明](DIRECT_SERVER.md) |
| 交给自己的 AI 安装 | [AI 执行指南](AI_GUIDE.md) |
| 安装失败或找不到工具 | [故障排查](TROUBLESHOOTING.md) |

## 日常使用与设备维护

- [使用指南](USER_GUIDE.md)：配网、按钮、历史和模拟互动。
- [Wi-Fi 配对](WIFI_CONNECTION.md)、[IP 变化与重连](WIRELESS_RECOVERY.md)、[运行环境与登录保护](RUNTIME_AND_LOGIN.md)。
- [通道与接线](SENSOR_CHANNELS.md)、[FSR 校准](CALIBRATION_AND_DAILY_MODE.md)、[DS18B20 温度](DIGITAL_TEMPERATURE.md)。
- [人设、偏好与动作摘要](INTERACTION_OBSERVATIONS.md)、[历史管理](HISTORY_MANAGEMENT.md)、[离线记录](OFFLINE_RECORDS.md)。
- [无线升级](OTA_UPDATE.md)、[首次烧录镜像](../firmware/prebuilt/README.md)。
- [软件下载与 PCB 文件](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)。

## 给开发者

- [开发与打包](DEVELOPER_GUIDE.md)、[45 个 MCP 工具](MCP_TOOLS.md)。
- [接入原聊天队列](EXISTING_CHAT.md)、[事件桥接口](PROACTIVE_INTERACTION.md)。
- [其他宿主模板](HOST_INTEGRATIONS.md)、[公开模板说明](../templates/README.md)。
- [Sakura 兼容入口](REMOTE_MCP.md)：保留技术操作，普通 Chat 添加尚未通过。

## 几个常见词

| 名称 | 简单解释 |
| --- | --- |
| MCP | AI 调用工具的接口；安装后仍需实际连接服务 |
| AP / 配网热点 | 娃娃临时发出的 Wi-Fi，用来设置家庭网络 |
| STDIO | 本机客户端启动脚本，通过它调用 MCP，无需公网地址 |
| IP | 网络地址；设备 IP 和电脑的 127.0.0.1 不是同一个地址 |
| SSH | 登录远程 Linux 服务器的终端方式 |
| 域名 / DNS | 将易记的网站名称指向你的服务器地址 |
| 游标 | 上一次读取的位置，用来继续读新记录，避免重复 |

## 验收和后续计划

[验证汇总](VALIDATION.md)先说明目前可用范围；以下报告保留各阶段的版本、环境和证据，不等于你的新安装已经通过。

| 报告 | 记录内容 |
| --- | --- |
| [MCP 分阶段验收](MCP_ACCEPTANCE_2_13.md) | SDK、Cloudflare、Sakura、Secure 和普通 Chat |
| [设备基础报告](DEVICE_LAB_TEST_REPORT.md) | 裸板、算法、离线、OTA、Work 调用 |
| [管理中心报告](GUI_ACCEPTANCE_2_14.md) | 2.14 GUI、页面和服务生命周期 |
| [直传报告](DIRECT_SERVER_ACCEPTANCE.md) | 2.8.0 / 2.15 直传与原应用测试回调 |
| [安装入口报告](SIMPLE_SETUP_ACCEPTANCE.md) | 内置 Python、快捷配对及 Linux 部署 |
| [后续计划](DEVELOPMENT_PLAN.md) | 实物与宿主尚待完成的验收 |

硬件资料在 [GitHub 硬件目录](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/hardware/rev-v2)。公共包不包含个人历史或配对信息；本机 `build/` 为运行数据，不能拿来给其他用户安装。
