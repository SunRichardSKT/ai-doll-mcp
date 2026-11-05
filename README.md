# AI 共感娃娃

用 ESP32-C3 和压力传感器感知娃娃身上的触摸，在 AI 聊天里回应，并保存可查询的互动记录。

[![Release](https://img.shields.io/github/v/release/SunRichardSKT/ai-doll-mcp)](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1) [![Checks](https://img.shields.io/github/actions/workflow/status/SunRichardSKT/ai-doll-mcp/checks.yml?branch=main)](https://github.com/SunRichardSKT/ai-doll-mcp/actions/workflows/checks.yml) [![License](https://img.shields.io/github/license/SunRichardSKT/ai-doll-mcp)](LICENSE) [![Hardware](https://img.shields.io/badge/Hardware-ESP32--C3-blue)](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md)

[选使用方式](#选择使用方式) · [安装](#下载与安装) · [第一次互动](#第一次互动) · [日常操作](#日常操作) · [硬件](#主板与外壳) · [全部教程](docs/README.md)

## 能做什么

- **触摸回应**。把实体按压送进聊天，连续触摸可以排队和合并回应。
- **自定义触摸部位**。单独开启已接入的端口，设定部位、回应语气和提示词。
- **互动记录**。按日期查询、统计、导出，联网后补传设备仍保留的记录。
- **手机直连**。安卓 Operit 可在家里直接连娃娃，由手机同步历史。
- **接入其他 AI**。Windows 提供本地 MCP 与 Secure MCP Tunnel，Linux 可部署设备接收服务和 MCP。

## 选择使用方式

| 你的环境 | 下载 | 日常要运行什么 |
| --- | --- | --- |
| 只有安卓手机，用 Operit | [Operit 工具包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Operit.toolpkg) · [手机直连教程](docs/integrations/OPERIT_NO_PC.md#只有安卓手机没有电脑和服务器) | 娃娃和同一局域网内的手机。开发板须已烧录。 |
| Windows 采集，接本地 MCP 或 Operit | [Windows 完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Code_v0.1.1.zip) · [电脑安装](docs/start/AI_INSTALL.md) | 娃娃和运行采集服务的电脑。 |
| Windows 采集，接 ChatGPT | [Windows 完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Code_v0.1.1.zip) · [Secure MCP 配置](docs/integrations/SECURE_MCP.md) | 娃娃、电脑采集和隧道。首次配置需账号具备隧道权限。 |
| 自己的 Linux 服务器，接 Operit 或其他宿主 | [Linux 服务包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/AI_Doll_Server_v0.1.1.tar.gz) · [部署教程](docs/integrations/REMOTE_SERVER_SETUP.md) | 娃娃和接收服务器。手机访问服务器。 |

## 下载与安装

软件、固件和手机工具包使用同一批 [v0.1.1 内测版附件](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1)。校验使用本版 [SHA256SUMS.txt](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.1/SHA256SUMS.txt)。单独固件、旧板制造资料和对应外壳见 [完整下载清单](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)。

### Windows

下载并完整解压 `AI_Doll_Code_v0.1.1.zip`，双击 `AI_Doll.cmd`。完整包已包含 Python，管理中心在本机打开 `http://127.0.0.1:8769/`。用 USB 数据线接板，在“设备连接”选择实际串口，看到设备 ID 后即可先用 USB 试用。需要无线时，配好家庭 Wi-Fi 后再点“一键识别并配对 Wi-Fi”。[Windows 安装与 AI 接入](docs/start/AI_INSTALL.md)

GitHub 仓库的 **Download ZIP** 是开发源码。普通 Windows 用户下载上表中的完整包。

### 安卓 Operit

在 Operit 的“包管理”导入 `AI_Doll_Operit.toolpkg`，从工具箱打开“AI Doll · 连接与互动”。手机直连选“添加娃娃”，按提示读取设备热点、切回家庭 Wi-Fi 并确认配对。电脑采集和服务器模式则从对应管理页导出手机连接，再导入 Operit。[Operit 完整指南](docs/integrations/OPERIT_SETUP.md)

### Linux 服务器

在可通过 SSH 访问的 Ubuntu 或 Debian 服务器上解压服务包，从解压目录运行 `sudo bash Install_Server.sh`。按提示设置已解析的域名，打开安装完成时显示的管理链接。已有站点占用 80 或 443 时，先查看同机部署说明。[Linux 部署教程](docs/integrations/REMOTE_SERVER_SETUP.md)

## 第一次互动

1. **给设备供电**。空白开发板用 Windows 完整包的 `Flash_ESP32.cmd` 烧录。已有设备可先核对版本、配对和校准。[一键烧录](docs/start/QUICK_FLASH.md)
2. **确认连接**。USB 模式查看实际设备 ID。无线模式在手机连上娃娃热点后打开 `http://192.168.4.1/`，配置家庭 **2.4 GHz Wi-Fi**，切回家庭网络后在手机或电脑完成配对。[配网与找回设备](docs/daily/WIFI_CONNECTION.md)
3. **设置传感器**。把实际装好的端口设为“已接入”，填写部位并校准。按压一次再松开，检查历史里是否出现对应记录。[接线与端口](docs/daily/SENSOR_CHANNELS.md) · [压力校准](docs/daily/CALIBRATION_AND_DAILY_MODE.md)
4. **接入聊天**。Operit 按标题选择已有聊天。MCP 客户端添加对应连接，在聊天中实际查询一次设备状态，核对设备 ID。[MCP 聊天验证](docs/integrations/CHAT_MCP.md) · [其他宿主接入](docs/integrations/HOST_INTEGRATIONS.md)

## 日常操作

| 你想做什么 | 怎么做 |
| --- | --- |
| 查看今天摸过哪些部位 | 在聊天中说“查询今天的互动，按部位汇总”。已同步的历史在设备离线时也可查询。 |
| 在 Operit 让触摸触发回复 | 在已绑定的聊天上开启“触摸主动回复”，可先试 1 分钟再选常开。记录同步与主动回复分开控制，常开取决于安卓后台任务和网络。 |
| 在普通 ChatGPT 试一次互动 | 在已接入设备的聊天里说“开始 60 秒互动”，等会话开始后按压。普通 Chat 的空闲主动唤醒尚未验证。 |
| 打开设备设置或更换 Wi-Fi | 从已配对客户端打开“设备设置”。需要重新配网时，在设备运行中长按 BOOT 约 3 秒，再连设备热点打开设置页。 |

`192.168.4.1` 用于连着**娃娃热点**的手机或电脑。`127.0.0.1:8769` 用于**正在运行 Windows 软件的电脑**。两处入口找不到时，从 [故障排查](docs/TROUBLESHOOTING.md) 按现象定位。

更多操作见 [日常指南](docs/daily/USER_GUIDE.md) 和 [历史管理](docs/daily/HISTORY_MANAGEMENT.md)。升级前备份自己的历史、校准与配对数据，操作方式见 [更新说明](CHANGELOG.md)。

## 主板与外壳

| 你手里的板 | 对应资料 |
| --- | --- |
| 已制带线板 | [主板、采购与制造资料](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md) · [按板型选外壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/README.md) |
| C3 八路 PA2.0 锁扣插座样板 | [当前嘉立创工程、Gerber 和正反面图](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/hardware/rev-v2/candidates/c3-socket-20261105) · [配套堆叠壳 P02](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/c3-socket-stacked/README.md) |
| 独立 Type-C 充放模块 | [四线防拉脱保护壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/charger-inline/README.md) |

插座样板的顶面丝印随仓库工程更新，首板实体装配和八路采样仍待验证。选用与手中 PCB 对应的打印件。当前固件支持压力与干接点输入，扩展资料按历史设计参考使用。[固件功能范围](docs/reports/FIRMWARE_INPUTS.md)

## 开发与贡献

固件使用 C++、Arduino 和 PlatformIO，电脑端与服务器使用 Python，Operit 工具包使用 JavaScript。先从 [开发与构建](docs/developers/DEVELOPER_GUIDE.md) 或 [项目结构](docs/developers/REPOSITORY_LAYOUT.md) 入手。接入自己的宿主时查阅 [MCP 工具目录](docs/developers/MCP_TOOLS.md)，让 AI 协助安装或调试时使用 [AI 执行指南](docs/ai/AI_GUIDE.md)。

遇到可复现的问题，欢迎在 [Issues](https://github.com/SunRichardSKT/ai-doll-mcp/issues) 提供设备版本、连接方式、操作步骤和报错。提交改动时附上对应的检查结果。实际验证过的场景见 [验证汇总](docs/reports/VALIDATION.md)。

## 许可证

项目采用 [MIT 许可证](LICENSE)。第三方资源附带各自的许可证。
