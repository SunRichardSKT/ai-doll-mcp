# AI 共感娃娃 _(ai-doll-mcp)_

![AI 共感娃娃 Logo](docs/images/ai-doll-logo.svg)

[![Release](https://img.shields.io/github/v/release/SunRichardSKT/ai-doll-mcp)](https://github.com/SunRichardSKT/ai-doll-mcp/releases/latest)
[![Checks](https://img.shields.io/github/actions/workflow/status/SunRichardSKT/ai-doll-mcp/checks.yml?branch=main)](https://github.com/SunRichardSKT/ai-doll-mcp/actions/workflows/checks.yml)
[![License](https://img.shields.io/github/license/SunRichardSKT/ai-doll-mcp)](LICENSE)
[![Hardware](https://img.shields.io/badge/Hardware-ESP32--C3-blue)](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md)

让 AI 感知你对娃娃的真实触摸，在聊天里回应，并留下可查询的互动记录。

[下载 v0.1.1 内测版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1) · [完整教程](docs/README.md) · [故障排查](docs/TROUBLESHOOTING.md) · [AI 使用说明书](docs/ai/AI_GUIDE.md)

## 目录

- [背景](#背景)
- [安装](#安装)
  - [安卓手机直连](#安卓手机直连)
  - [Windows 采集](#windows-采集)
  - [Linux 服务器](#linux-服务器)
- [使用](#使用)
  - [第一次互动](#第一次互动)
  - [日常操作](#日常操作)
- [主板与外壳](#主板与外壳)
- [开发与接口](#开发与接口)
- [维护者](#维护者)
- [如何贡献](#如何贡献)
- [许可证](#许可证)

## 背景

摸摸娃娃的头，也可以成为聊天的一部分。AI 共感娃娃是硬件和软件的项目名称，`ai-doll-mcp` 是源码仓库。主板使用 ESP32-C3，接入薄膜压力传感器后，由手机、电脑或服务器读取触摸事件。

- **触摸回应**。支持按压与释放识别，连续触摸可排队、合并回应。
- **自定义部位**。按端口设置是否接入、身体部位和反馈偏好。
- **互动记录**。支持查询、统计、导出，并在重连后补传设备仍保留的记录。
- **多种接入方式**。Operit 可在家中直连娃娃。电脑和 Linux 服务器可向兼容客户端提供 MCP 接口。

## 安装

普通用户从 [v0.1.1 内测版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1) 下载对应附件。Windows 请下载完整包，GitHub 的 **Download ZIP** 用于获取开发源码。需要核对附件完整性时，使用同版 [SHA256SUMS.txt](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/SHA256SUMS.txt)。

| 你的使用方式 | 下载 | 使用时需要运行 |
| --- | --- | --- |
| 只有安卓手机，使用 Operit | [Operit 工具包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Operit.toolpkg) | 已烧录的娃娃和同一局域网内的手机 |
| Windows 采集，接 Operit 或本地 MCP | [Windows 完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Code_v0.1.1.zip) | 娃娃和运行采集服务的电脑 |
| Windows 采集，接 ChatGPT | [Windows 完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Code_v0.1.1.zip) | 娃娃、电脑采集服务和 Secure MCP Tunnel |
| 自有 Linux 服务器，接 Operit 或其他客户端 | [Linux 服务包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Server_v0.1.1.tar.gz) | 娃娃和接收服务器 |

### 安卓手机直连

1. 给已烧录的娃娃供电。在 Operit 的“包管理”导入 `AI_Doll_Operit.toolpkg`，再从工具箱打开“AI Doll · 连接与互动”。
2. 点击“添加娃娃”。按提示连上设备热点、读取设备、配置家庭 **2.4 GHz Wi-Fi**，再把手机切回家庭网络完成配对。
3. 要在聊天里收到触摸回复，按标题选择聊天并确认绑定。只同步历史时可以先跳过绑定。

手机通常无需手填 IP、令牌或聊天 ID。升级工具包、从电脑或服务器导入连接、换网恢复的步骤见 [Operit 完整指南](docs/integrations/OPERIT_SETUP.md)。

### Windows 采集

1. 完整解压 Windows 包并双击 `AI_Doll.cmd`。包内已带 Python。管理中心地址为 `http://127.0.0.1:8769/`，在运行软件的电脑上打开。
2. 用 USB 数据线连接开发板，在“设备连接”选 USB 和实际 COM 口，保存后确认设备 ID 和同步时间。改用无线时，先配家庭 Wi-Fi，再点“一键识别并配对 Wi-Fi”。
3. 按客户端完成接入。Operit 使用“Operit 手机陪伴”导出的连接文件。本地 MCP 客户端使用“AI / MCP 连接”提供的配置。ChatGPT 路线需要有隧道权限的账号，按教程建立 Secure MCP Tunnel。

[Windows 首次安装](docs/start/AI_INSTALL.md) · [Operit 电脑采集](docs/integrations/OPERIT_SETUP.md#电脑采集首次使用) · [ChatGPT 隧道配置](docs/integrations/SECURE_MCP.md)

### Linux 服务器

准备可通过 SSH 访问的 Ubuntu 或 Debian 服务器和已解析的域名。上传服务包与同版 [校验文件](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Server_v0.1.1.tar.gz.sha256)，在 SSH 终端运行以下命令。

```bash
sha256sum -c AI_Doll_Server_v0.1.1.tar.gz.sha256
mkdir ai-doll-server-0.1.1
tar -xzf AI_Doll_Server_v0.1.1.tar.gz -C ai-doll-server-0.1.1
cd ai-doll-server-0.1.1
sudo bash Install_Server.sh
```

打开安装完成时显示的 HTTPS 管理页，按向导配置设备直传，再把 MCP 地址接入支持的客户端。使用 Operit 时，从管理页导出连接文件，再在手机上导入。已有网站占用 80 或 443 时，先查看同机部署说明。 [Linux 部署教程](docs/integrations/REMOTE_SERVER_SETUP.md)

## 使用

### 第一次互动

1. **准备设备。** 空白开发板用 Windows 完整包内的 `Flash_ESP32.cmd` 烧录。已有设备先核对版本和连接，保留原校准、配对及历史。 [一键烧录](docs/start/QUICK_FLASH.md)
2. **确认在线。** 在手机或电脑核对设备 ID。首次无线配网时，连着娃娃热点才能打开 `http://192.168.4.1/`。完成配网后，切回家庭网络使用设备。 [配网与找回设备](docs/daily/WIFI_CONNECTION.md)
3. **试一个部位。** 把实际装好的端口设为“已接入”，填入部位并完成校准。按压并松开一次，检查历史是否出现该部位的记录。 [接线与端口](docs/daily/SENSOR_CHANNELS.md) · [压力校准](docs/daily/CALIBRATION_AND_DAILY_MODE.md)
4. **核对聊天接入。** Operit 绑定聊天后可开启“触摸主动回复”。使用 MCP 的客户端可以先让 AI 查询设备，核对返回的 ID。 [MCP 聊天验证](docs/integrations/CHAT_MCP.md)

### 日常操作

| 你想做什么 | 怎么做 |
| --- | --- |
| 让 Operit 在触摸后回复 | 在已绑定的聊天上开启“触摸主动回复”，可先试 1 分钟再选常开。常开取决于安卓后台任务和网络。 |
| 在普通 ChatGPT 体验触摸 | 在已连接的聊天里说“开始 60 秒互动”，等待会话开始后按压。普通 Chat 的空闲主动唤醒尚未验证。 |
| 查询或导出互动记录 | 在 Operit 查看历史，或在已连接 MCP 的聊天里说“查询今天的互动，按部位汇总”。已经同步的历史在设备离线时仍可查询。 |
| 暂停回复但保留历史同步 | 关闭“触摸主动回复”，保留“自动同步记录”。 |
| 打开设备设置或更换 Wi-Fi | 从已配对客户端打开“设备设置”。需要重新配网时，在设备运行中长按 BOOT 约 3 秒，再连娃娃热点。 |

[日常指南](docs/daily/USER_GUIDE.md) · [历史管理](docs/daily/HISTORY_MANAGEMENT.md) · [升级与备份](CHANGELOG.md)

## 主板与外壳

| 你手里的板或模块 | 对应资料 |
| --- | --- |
| 已制带线板 | [主板、采购与制造资料](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md) · [按板型选外壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/README.md) |
| C3 八路 PA2.0 锁扣插座样板 | [嘉立创工程、Gerber 和正反面图](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/hardware/rev-v2/candidates/c3-socket-20261105) · [配套堆叠壳 P02](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/c3-socket-stacked/README.md) |
| 独立 Type-C 充放模块 | [四线防拉脱保护壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/charger-inline/README.md) |

按实际 PCB 选打印件。插座样板的首板实体装配和八路采样待验证。当前固件支持压力与干接点输入。 [固件功能范围](docs/reports/FIRMWARE_INPUTS.md) · [固件、PCB 与外壳下载清单](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)

## 开发与接口

固件使用 C++、Arduino 和 PlatformIO，电脑端与服务器使用 Python，Operit 工具包使用 JavaScript。

- 构建和测试见 [开发指南](docs/developers/DEVELOPER_GUIDE.md) 与 [项目结构](docs/developers/REPOSITORY_LAYOUT.md)。
- 自建聊天客户端可查阅 [MCP 工具目录](docs/developers/MCP_TOOLS.md) 和 [宿主接入指南](docs/integrations/HOST_INTEGRATIONS.md)。
- AI 协助安装、调用和测试时使用 [AI 使用说明书](docs/ai/AI_GUIDE.md)。

## 维护者

[SunRichardSKT](https://github.com/SunRichardSKT)

## 如何贡献

欢迎在 [Issues](https://github.com/SunRichardSKT/ai-doll-mcp/issues) 提问或反馈。报告问题时请附上设备版本、连接方式、复现步骤和报错，分享截图前请遮盖配对码或密钥。

欢迎提交 Pull Request，请说明改动场景并附上相关检查结果。现有实测记录见 [验证汇总](docs/reports/VALIDATION.md)。

如果项目帮到了你，欢迎在 GitHub 点一个 Star，支持后续维护。 [项目主页](https://github.com/SunRichardSKT/ai-doll-mcp)

## 许可证

[MIT 许可证](LICENSE) © 2026 SunRichardSKT。第三方资源附带各自的许可证。
