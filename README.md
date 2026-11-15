# AI 共感娃娃 _(ai-doll-mcp)_

[![Release](https://img.shields.io/github/v/release/SunRichardSKT/ai-doll-mcp)](https://github.com/SunRichardSKT/ai-doll-mcp/releases/latest)
[![Checks](https://img.shields.io/github/actions/workflow/status/SunRichardSKT/ai-doll-mcp/checks.yml?branch=main)](https://github.com/SunRichardSKT/ai-doll-mcp/actions/workflows/checks.yml)
[![Software License: AGPL v3](https://img.shields.io/badge/software-AGPL--3.0--only-blue)](LICENSE)
[![Hardware License: CERN OHL S v2](https://img.shields.io/badge/hardware-CERN--OHL--S--2.0-green)](hardware/LICENSE)
[![Hardware](https://img.shields.io/badge/Hardware-ESP32--C3-blue)](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md)

让 AI 感知你对娃娃的真实触摸，在聊天里回应，并留下可查询的互动记录。

[下载 v0.1.3 内测版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.3) · [完整教程](docs/README.md) · [故障排查](docs/TROUBLESHOOTING.md) · [AI 使用说明书](docs/ai/AI_GUIDE.md)

当前公开版本为 **内测0.1.3版**，支持三步连接、USB 配网、多个 AI 客户端和自定义部位组合。下表列出客户端、运行环境和现板硬件的适用范围。

Claude Code 专用入口和配置导出已加入 `main` 源码；已发布的0.1.3包可通过原有通用 MCP 配置接入，见下方[兼容用法](#claude-code快速接入)。

## 目录

- [适用范围](#适用范围)
  - [AI 客户端](#ai-客户端)
  - [运行环境与连接](#运行环境与连接)
  - [现板功能与硬件](#现板功能与硬件)
- [背景](#背景)
- [安装](#安装)
  - [安卓手机直连](#安卓手机直连)
  - [Windows 采集](#windows-采集)
  - [Claude Code快速接入](#claude-code快速接入)
  - [Linux 服务器](#linux-服务器)
- [使用](#使用)
  - [第一次互动](#第一次互动)
  - [日常操作](#日常操作)
- [主板与外壳](#主板与外壳)
- [开发与接口](#开发与接口)
- [维护者](#维护者)
- [如何贡献](#如何贡献)
- [许可证](#许可证)

## 适用范围

### AI 客户端

接入后，AI 可读取设备状态、近期互动和历史记录，并按用户要求配置部位与互动规则。具体连接方式由客户端决定。

| 客户端 | 可用连接方式 | 使用条件与入口 |
| --- | --- | --- |
| **Operit · 安卓** | 手机直连娃娃、电脑采集或服务器连接 | 手机直连时与娃娃处于同一局域网；支持绑定聊天、自动同步和触摸主动回复。[安装](docs/integrations/OPERIT_SETUP.md) |
| **ChatGPT · 官方网页版** | 电脑私有隧道，或自有服务器的 HTTPS MCP | 账号／工作区需开放自定义 MCP；电脑私有隧道另需隧道权限，并保持采集与隧道运行。[连接步骤](docs/integrations/OFFICIAL_CLIENTS.md#chatgpt) |
| **Claude Desktop · 官方桌面版** | 本机 MCP（STDIO）；远程连接器使用 HTTPS | Windows 提供配置生成和一键合并；本机路线保持采集服务运行，远程连接器使用公网 HTTPS 443。[本机连接](docs/integrations/OFFICIAL_CLIENTS.md#claude-desktop本机连接) |
| **Claude Code · 官方 CLI** | 本机 MCP（STDIO）或可达的 HTTP MCP | 安装 Claude Code；本机配置与运行 CLI 的系统对应，可用 `/mcp` 检查连接。[快速接入](#claude-code快速接入) |
| **Claude · 官方网页／手机** | 自有服务器的 HTTPS MCP | 在连接器设置添加设备地址；连接由 Claude 云端发起，需要公网 HTTPS 443。[远程连接](docs/integrations/OFFICIAL_CLIENTS.md#claude-网页和手机远程连接) |
| **DeepSeek DSH · 官方 Harness** | 本机 MCP（STDIO）或 HTTP MCP | 适用于 DSH 桌面、Web、CLI profile；在运行 DSH 的主机配置服务。[DSH 配置](docs/integrations/OFFICIAL_CLIENTS.md#deepseek-dsh官方-harness) |
| **Gemini · 官方网页／手机** | 自有服务器的 HTTPS MCP | 当前要求美国地区、18岁以上个人账号、英文界面及开启 Keep Activity；先在网页添加，连接后手机可用。[Google 条件](https://support.google.com/gemini/answer/17209137?hl=en-45) · [步骤](docs/integrations/OFFICIAL_CLIENTS.md#gemini-官方网页与手机) |
| **Gemini CLI · Google 官方** | 本机 MCP（STDIO）或 HTTP MCP | 安装 CLI，将配置加入 `.gemini/settings.json`；远程连接使用 `httpUrl`。[CLI 配置](docs/integrations/OFFICIAL_CLIENTS.md#gemini-cli) |
| **Codex · 本机 MCP** | 本机 MCP（STDIO） | 项目提供 `tools/install_companion_mcp.py --codex` 登记入口；电脑采集保持运行。[开发与配置](docs/developers/DEVELOPER_GUIDE.md) |
| **其他支持 MCP 的客户端** | 按客户端支持选择本机配置或 HTTP MCP | 添加当前设备对应的配置／地址，并在客户端授权工具调用。[接口说明](docs/integrations/CHAT_MCP.md) |
| **自建应用、OpenClaw 等宿主** | MCP 查询、事件桥或设备直传服务 | 自动接收互动需宿主提供消息接收入口与聊天回调，按接入指南配置。[宿主接入](docs/integrations/HOST_INTEGRATIONS.md) |

**触摸后主动回复：** Operit 提供后台任务与聊天绑定，开启后可在触摸时触发回复，生成期间继续排队。其他客户端可按需查询或开始限时互动；空闲主动唤醒需要该宿主实际提供事件接收与聊天触发能力，接入 MCP 本身不等于已开启主动回复。

**DeepSeek 普通官方网页／App：** 本项目目前没有确认其自定义 MCP 接入入口。使用 DeepSeek 模型时，可选 DSH，或在 Operit 等支持 MCP 的客户端中配置该模型。[平台说明](docs/integrations/OFFICIAL_CLIENTS.md#普通-deepseek-网页与-app)

### 运行环境与连接

| 环境 | 适用方式 | 使用时保持运行 |
| --- | --- | --- |
| **安卓手机** | Operit 直连同一局域网中的娃娃，可独立使用，无需电脑常驻 | 娃娃、手机网络与 Operit 后台任务；后台权限按手机系统设置 |
| **Windows 64位电脑** | 完整包内置 Python，提供管理中心、USB 烧录／配网、Wi-Fi 采集及本机 MCP | 娃娃与采集服务；使用 ChatGPT 隧道时再保持隧道运行 |
| **Linux 服务器** | 提供 Ubuntu／Debian 安装入口，接收设备上传并开放 MCP 服务 | 娃娃、联网服务器及部署服务；官方云端客户端使用公网域名与 HTTPS |
| **macOS、Linux 桌面、WSL** | 可连接可达的服务器 MCP；本机源码运行需自行准备 Python 环境，项目未提供这些系统的成品桌面包 | 对应环境中的客户端与采集／服务器服务；Windows 包内 Python 路径用于原生 Windows |
| **iPhone／iPad** | 可用浏览器给娃娃配网，并使用平台已开放的官方 AI 手机客户端远程连接 | 对应服务器与 AI 平台连接；本项目的 Operit 工具包适用于安卓 |
| **暂无实体硬件** | 可用独立模拟分支体验记录、设置与聊天工具，界面和事件标明模拟来源 | 对应的电脑模拟与接收服务。[模拟步骤](docs/integrations/CHAT_MCP.md#可选没有传感器时做模拟测试) |

娃娃使用 **2.4 GHz Wi-Fi**，当前未提供蓝牙配网。`192.168.4.1/setup` 仅在连接娃娃热点时用于配网；家庭网络访问使用设备当前地址，`127.0.0.1` 管理页只在运行软件的电脑上打开。设备本身不承担 AI 模型推理；AI 服务由所选客户端提供。

### 现板功能与硬件

| 产品代际 | 当前范围 | 资料 |
| --- | --- | --- |
| **第一代 · ESP32-C3** | 所有已制带线板、V2／V2.2 PCB修订、最终PA2.0插座板及手焊焊盘改进 | [一代文件总览](hardware/gen1/README.md) |
| **第二代 · ESP32-S3路线** | 开发板与模块化多媒体核心预研；问卷已有模板及发布记录，原理图／PCB／专用固件尚未交付 | [二代研发进度](hardware/gen2/README.md) |

适用于第一代 **ESP32-C3 SuperMini 核心**，包括已制带线板及最终 PA2.0 锁扣插座板；外壳按实际 PCB 型号选择。

| 功能或硬件 | 当前支持范围 |
| --- | --- |
| **压力／触摸输入** | 标准现板8路薄膜压力输入，支持按压、释放、部位命名、端口开关、阈值校准和互动记录。 |
| **温度感知** | 两线无源 NTC 10kΩ／B3435 探头，占用一个现有传感器口，感知探头附近温度。 |
| **湿润／擦眼泪互动** | 两片导电材料组成湿润感应片，占用一个现有口，与另一路压力事件共同触发擦眼泪互动。 |
| **压力＋温度＋湿润组合** | 例如6路压力＋1路 NTC＋1路湿润，共用原有8路接口。[接线与制作](hardware/gen1/expansion/resistive-inputs/README.md) |
| **干接点开关与独立 ADC** | 固件保留 GPIO21 干接点、GPIO1 独立 ADC 扩展；需按电路另行接线与配置，不是新增的板载插座。[通道说明](docs/daily/SENSOR_CHANNELS.md) |
| **自定义组合动作** | 可保存多组压力部位组合，例如“前胸＋后背＝拥抱”；各部位在设定时间内按下并同时保持，沿用现有回复队列。 |
| **记录与维护** | 支持历史查询、统计、导出、设备有限离线缓存与重连补传、网络状态灯、Wi-Fi 找回、USB 烧录及 OTA。 |
| **供电与接口** | 最终板传感器使用 PA2.0 2P，J9 使用 PA2.0 3P 接5V；电池方案使用独立充放电／升压模块。核心 USB 用于供电、烧录和调试，电池从独立模块充电。 |

**当前一代固件未提供的功能：** 摄像头、麦克风／扬声器、语音输入输出、振动马达、舵机、轮式底盘、外接灯效、DS18B20 数字温度探头，以及 LIS3DH／MPU6050 姿态模块。多媒体与动作模块属于后续核心研发方向；板载网络指示灯保留。

## 背景

摸摸娃娃的头，也可以成为聊天的一部分。AI 共感娃娃是硬件和软件的项目名称，`ai-doll-mcp` 是源码仓库。主板使用 ESP32-C3，接入薄膜压力传感器后，由手机、电脑或服务器读取触摸事件。

- **触摸回应**。支持按压与释放识别，连续触摸可排队、合并回应。
- **自定义部位**。按端口设置是否接入、身体部位和反馈偏好。
- **组合动作**。自定义前胸＋后背＝拥抱等动作，按同时受压识别，原始记录保留。
- **互动记录**。支持查询、统计、导出，并在重连后补传设备仍保留的记录。
- **多种接入方式**。Operit 可在家中直连娃娃。电脑和 Linux 服务器可向兼容客户端提供 MCP 接口。

## 安装

普通用户从 [v0.1.3 内测版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.3) 下载对应附件。Windows 请下载完整包，GitHub 的 **Download ZIP** 用于获取开发源码。需要核对附件完整性时，使用同版 [SHA256SUMS.txt](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.3/SHA256SUMS.txt)。

| 你的使用方式 | 下载 | 使用时需要运行 |
| --- | --- | --- |
| 只有安卓手机，使用 Operit | [Operit 工具包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.3/AI_Doll_Operit.toolpkg) | 已烧录的娃娃和同一局域网内的手机 |
| Windows 采集，接 Operit 或本地 MCP | [Windows 完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.3/AI_Doll_Code_v0.1.3.zip) | 娃娃和运行采集服务的电脑 |
| Windows 采集，接 ChatGPT | [Windows 完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.3/AI_Doll_Code_v0.1.3.zip) | 娃娃、电脑采集服务和 Secure MCP Tunnel |
| 自有 Linux 服务器，接 Operit 或其他客户端 | [Linux 服务包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.3/AI_Doll_Server_v0.1.3.tar.gz) | 娃娃和接收服务器 |

成品用户可先看[6页图文新手说明书](docs/product/抱抱星_共感娃娃核心_新手说明书.pdf)；[产品介绍与图片](docs/product/README.md)可用于介绍和随包说明。

先按上方[适用范围](#适用范围)选择客户端与运行环境，再按[完整平台步骤](docs/integrations/OFFICIAL_CLIENTS.md)连接。

### 安卓手机直连

1. 给已烧录的娃娃供电。在 Operit 的“包管理”导入 `AI_Doll_Operit.toolpkg`，再从工具箱打开“AI Doll · 连接与互动”。
2. 点击“连接娃娃”。读取热点、配置家庭2.4 GHz Wi-Fi，点“返回向导并检查联网”保存地址，再切回家庭网络完成连接。
3. 要在聊天里收到触摸回复，按标题选择聊天并确认绑定。只同步历史时可以先跳过绑定。

手机通常无需手填 IP、令牌或聊天 ID。升级工具包、从电脑或服务器导入连接、换网恢复的步骤见 [Operit 完整指南](docs/integrations/OPERIT_SETUP.md)。

### Windows 采集

1. 完整解压 Windows 包并双击 `AI_Doll.cmd`。包内已带 Python。管理中心地址为 `http://127.0.0.1:8769/`，在运行软件的电脑上打开。
2. 用 USB 数据线连接开发板，按向导选择实际串口，通过 USB 配网并自动配对 Wi-Fi；已联网设备跳过填写网络。
3. 按客户端完成接入。Operit 使用“Operit 手机陪伴”导出的连接文件。本地 MCP 客户端使用“AI / MCP 连接”提供的配置。ChatGPT 路线需要有隧道权限的账号，按教程建立 Secure MCP Tunnel。

[Windows 首次安装](docs/start/AI_INSTALL.md) · [Operit 电脑采集](docs/integrations/OPERIT_SETUP.md#电脑采集首次使用) · [ChatGPT 隧道配置](docs/integrations/SECURE_MCP.md)

### Claude Code快速接入

已下载0.1.3 Windows 完整包时，在解压后的项目目录运行：

```powershell
.\python\python.exe -X utf8 tools/install_companion_mcp.py
claude --mcp-config ./build/device-lab/mcp-client-config.json
```

保持 `AI_Doll.cmd` 启动的采集服务运行，在 Claude Code 输入 `/mcp` 查看 `ai_doll`。当前 `main` 源码还提供 `--client claude_code` 专用导出与管理中心入口；服务器用户可复制 `type: "http"` 配置。[CLI 完整说明](docs/integrations/OFFICIAL_CLIENTS.md#claude-codecli)

### Linux 服务器

准备可通过 SSH 访问的 Ubuntu 或 Debian 服务器和已解析的域名。上传服务包与同版 [校验文件](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.3/AI_Doll_Server_v0.1.3.tar.gz.sha256)，在 SSH 终端运行以下命令。

```bash
sha256sum -c AI_Doll_Server_v0.1.3.tar.gz.sha256
mkdir ai-doll-server-0.1.3
tar -xzf AI_Doll_Server_v0.1.3.tar.gz -C ai-doll-server-0.1.3
cd ai-doll-server-0.1.3
sudo bash Install_Server.sh
```

打开安装完成时显示的 HTTPS 管理页，按向导配置设备直传，再把 MCP 地址接入支持的客户端。使用 Operit 时，从管理页导出连接文件，再在手机上导入。已有网站占用 80 或 443 时，先查看同机部署说明。 [Linux 部署教程](docs/integrations/REMOTE_SERVER_SETUP.md)

## 使用

### 第一次互动

1. **准备设备。** 空白开发板用 Windows 完整包内的 `Flash_ESP32.cmd` 烧录。已有设备先核对版本和连接，保留原校准、配对及历史。 [一键烧录](docs/start/QUICK_FLASH.md)
2. **确认在线。** 在手机或电脑核对设备 ID。首次无线配网时，连着娃娃热点才能打开 `http://192.168.4.1/setup`。完成配网后，切回家庭网络使用设备。 [配网与找回设备](docs/daily/WIFI_CONNECTION.md)
3. **试一个部位。** 把实际装好的端口设为“已接入”，填入部位并完成校准。按压并松开一次，检查历史是否出现该部位的记录。 [接线与端口](docs/daily/SENSOR_CHANNELS.md) · [压力校准](docs/daily/CALIBRATION_AND_DAILY_MODE.md)
4. **核对聊天接入。** Operit 绑定聊天后可开启“触摸主动回复”。使用 MCP 的客户端可以先让 AI 查询设备，核对返回的 ID。 [MCP 聊天验证](docs/integrations/CHAT_MCP.md)

### 日常操作

| 你想做什么 | 怎么做 |
| --- | --- |
| 让 Operit 在触摸后回复 | 在已绑定的聊天上开启“触摸主动回复”，可先试 1 分钟再选常开。常开取决于安卓后台任务和网络。 |
| 在普通 ChatGPT 体验触摸 | 在已连接的聊天里说“开始 60 秒互动”，等待会话开始后按压。 |
| 查询或导出互动记录 | 在 Operit 查看历史，或在已连接 MCP 的聊天里说“查询今天的互动，按部位汇总”。已经同步的历史在设备离线时仍可查询。 |
| 暂停回复但保留历史同步 | 关闭“触摸主动回复”，保留“自动同步记录”。 |
| 打开设备设置或更换 Wi-Fi | 从已配对客户端打开“设备设置”。需要重新配网时，在设备运行中长按 BOOT 约 3 秒，再连娃娃热点。 |

[日常指南](docs/daily/USER_GUIDE.md) · [历史管理](docs/daily/HISTORY_MANAGEMENT.md) · [升级与备份](CHANGELOG.md)

## 主板与外壳

全部C3硬件已统一到[第一代目录](hardware/gen1/README.md)；历史工程名中的V2／V2.2表示PCB修订。软件版本与产品代际分别管理。[完整硬件分类](hardware/README.md)

| 你手里的板或模块 | 对应资料 |
| --- | --- |
| 已制带线板 | [主板、采购与制造资料](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/gen1/pcb/README.md) · [按板型选外壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/gen1/enclosure/README.md) |
| 第一代最终版 · C3八路锁扣插座板 | [嘉立创工程、Gerber 和正反面图](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/hardware/gen1/pcb/candidates/c3-socket-20261105) · [第一代最终版电池壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/gen1/enclosure/c3-socket-stacked/README.md) |
| 独立 Type-C 充放模块 | [四线防拉脱保护壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/gen1/enclosure/charger-inline/README.md) |

[下载第一代硬件最终版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/hardware-gen1-final)：PCB工程与制造文件、103450核心电池壳、独立充电板壳。

按实际 PCB 选择打印件，核心壳的底壳、托板和上盖配套打印。[结构加固与打印说明](hardware/gen1/enclosure/PRINT_STRENGTHENING.md)提供装配尺寸和建议。

0.1.1 固件支持压力与干接点，0.1.2 增加 NTC 和湿润片。[固件功能](docs/reports/FIRMWARE_INPUTS.md) · [交付文件](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md) · [检查记录](docs/reports/VALIDATION.md)

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

© 2026 SunRichardSKT。软件与固件使用 [AGPL-3.0-only](LICENSE)；PCB、外壳及制造设计使用 [CERN-OHL-S-2.0](hardware/LICENSE)。第三方资源保留原许可。适用范围与网络服务源码要求见 [项目许可](LICENSING.md)。
