# 教程目录

零基础从“入门”开始，只读当前需要的页面。技术接口放在开发者区，给 AI 的操作规则单独存放。

## 01 入门：先把设备用起来

| 顺序 | 教程 | 完成后应该看到 |
| --- | --- | --- |
| 1 | [一键烧录（含实际截图）](start/QUICK_FLASH.md) | 程序写入、启动和新编号均成功 |
| 2 | [新板与恢复出厂设置](start/FACTORY_SETTINGS.md) | 了解默认行为和保留范围 |
| 3 | [配网与固定设置页（含实际截图）](daily/WIFI_CONNECTION.md) | 已联网，192.168.4.1 入口仍可用 |
| 4 | [Windows 首次安装](start/AI_INSTALL.md) | 原 AI 能实际调用设备状态 |
| 选择 | [四种连接方式](start/MCP_TRANSPORT_DECISION.md) | 选定一条运行通路 |

## 02 日常：记录、传感器与维护

| 教程 | 解决什么问题 |
| --- | --- |
| [日常使用与管理页面](daily/USER_GUIDE.md) | 开机、灯、按钮、页面位置、查询和互动 |
| [配网、无线配对与断线恢复](daily/WIFI_CONNECTION.md) | 修改网络、找回 IP、切换 USB、启动项 |
| [运行环境与账号密码](daily/RUNTIME_AND_LOGIN.md) | 是否装 Python、网页密码、各类令牌 |
| [通道与接线](daily/SENSOR_CHANNELS.md) | 接压力、温度或电机前看这里 |
| [压力校准与日常模式](daily/CALIBRATION_AND_DAILY_MODE.md) | 静置、轻按、较强按和重启策略 |
| [DS18B20 温度](daily/DIGITAL_TEMPERATURE.md) | 数字温度探头接线与扫描 |
| [互动历史](daily/HISTORY_MANAGEMENT.md) | 查询、统计、导出、删除和保留期限 |
| [人设与反馈](daily/INTERACTION_OBSERVATIONS.md) | 语气、安静时段与动作摘要 |
| [自然陪伴与聊天内设置](daily/NATURAL_COMPANION.md) | 部位别名、回应强度、聊天融入与主动开关 |
| [断网缓存](daily/OFFLINE_RECORDS.md) | 补传容量、时间与丢失计数 |
| [无线升级](daily/OTA_UPDATE.md) | 已安装固件的局域网升级 |

## 03 AI 接入：继续用原聊天

- [ChatGPT 连接教程](integrations/SECURE_MCP.md)：设置私有隧道。
- [原聊天实际验证](integrations/CHAT_MCP.md)：状态、历史、60 秒互动。
- [自己的应用：本机接收](integrations/SERVER_QUICKSTART.md)。
- [自己的应用：Linux 远程部署](integrations/REMOTE_SERVER_SETUP.md)。
- [其他宿主与模板](integrations/HOST_INTEGRATIONS.md)。
- [Operit 一次配置与原聊天验收](integrations/OPERIT_SETUP.md)：一个工具包，自动绑定与准备工作流。
- [Operit 无电脑使用](integrations/OPERIT_NO_PC.md)：服务器直传，或安卓手机直连家庭设备。
- [Sakura 兼容入口](integrations/REMOTE_MCP.md)：保留技术路线，普通 Chat 添加仍未通过。

## 04 开发者参考

[开发与打包](developers/DEVELOPER_GUIDE.md) · [项目文件与清理规则](developers/REPOSITORY_LAYOUT.md) · [MCP 工具目录](developers/MCP_TOOLS.md) · [直传接口](developers/DIRECT_SERVER.md) · [接入原聊天](developers/EXISTING_CHAT.md) · [事件桥](developers/PROACTIVE_INTERACTION.md) · [后续计划](developers/DEVELOPMENT_PLAN.md)

[统一代码、安装与日常使用规划](developers/UNIFIED_DELIVERY_PLAN.md)说明分阶段合并入口、配置和手机工具包；[2.19 实施记录](reports/RELEASE_2_19.md)区分已实现与待手机验收。

## 05 给 AI 执行

[AI 安装、调用、硬件与验证指南](ai/AI_GUIDE.md)。提供给帮你操作设备的 AI；普通用户无需照着调用工具。

## 06 验证记录

先看 [当前验证范围](reports/VALIDATION.md)和 [2.20 交付记录](reports/RELEASE_2_20.md)。[2.17 记录](reports/RELEASE_2_17.md)及其他历史报告保留当时版本，不代表新版本或你的新安装已经通过。

[2.18 自然陪伴本地交付记录](reports/RELEASE_2_18.md)说明本轮软件新增和目标聊天待验收范围。

[MCP 阶段报告](reports/MCP_ACCEPTANCE_2_13.md) · [设备基础报告](reports/DEVICE_LAB_TEST_REPORT.md) · [管理中心报告](reports/GUI_ACCEPTANCE_2_14.md) · [直传报告](reports/DIRECT_SERVER_ACCEPTANCE.md) · [旧安装入口报告](reports/SIMPLE_SETUP_ACCEPTANCE.md)

## 卡住时

直接找 [故障排查](TROUBLESHOOTING.md)，按现象处理。下载见 [交付说明](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)，板子采购和装配见 [硬件目录](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md)。

[2.19.1 Operit 1.12.2 导入兼容性](reports/RELEASE_2_19_1.md)记录旧工具包解析失败的原因与修正。
