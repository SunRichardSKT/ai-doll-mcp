# AI 共感娃娃

把娃娃的触摸与按压，接入你正在使用的 AI 聊天。继续使用原来的模型、人设和上下文，让 AI 在原对话中回应身体互动，也能查询过去的互动记录。

**当前发布：2.21.0 · ESP32-C3 固件：2.10.0**

[下载与发布说明](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.21.0) · [完整教程目录](docs/README.md) · [故障排查](docs/TROUBLESHOOTING.md) · [给 AI 的安装指南](docs/ai/AI_GUIDE.md)

## 目录

- [项目能做什么](#项目能做什么)
- [最近更新](#最近更新)
- [选择适合你的使用方式](#选择适合你的使用方式)
- [下载哪个文件](#下载哪个文件)
- [第一次使用](#第一次使用)
- [文档导航](#文档导航)
- [项目目录](#项目目录)
- [已验证与待验证的能力](#已验证与待验证的能力)
- [常见问题与访问地址](#常见问题与访问地址)
- [数据与许可证](#数据与许可证)

## 项目能做什么

- **在原聊天中回应触摸**：读取已配置部位的按压与释放，结合当前话题自然回应。
- **查询互动历史**：查看记录、摘要与统计，保留事件来源、部位和时间信息。
- **设置部位与反馈**：调整部位名称、人设补充、回应偏好和聊天融入开关。
- **通过 MCP 接入 AI**：提供本机 STDIO、HTTP 和服务器 MCP，沿用已有聊天客户端。
- **使用 Operit 主动陪伴**：绑定已有聊天，明确开启后进行限时互动；支持电脑、服务器或安卓手机直连。

项目不提供新的聊天模型或第二套聊天窗口。**触摸主动回应默认关闭**，需要用户开启；能否在后台触发回复取决于客户端及其运行状态，不代表所有 AI 客户端都支持空闲唤醒。

## 最近更新

2026-10-19 源码更新：改进已配对设备的快速搜索、IP 变化恢复和 USB 失效后的 Wi-Fi 恢复，保留历史与校准。相关 59 项测试通过，本机已验证恢复链路；无需重新烧录。操作见 [连接恢复](docs/daily/WIFI_CONNECTION.md)。

硬件新增 [V2.2 双层布线候选](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/candidates/pcb-v22-routed-20261017/README.md)和 [外壳设计入口](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/README.md)。平铺电池仓包括旧板 P03、新紧凑板 P02；另有旧板 [上下堆叠 P01](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/ordered-v2-stacked/README.md)，保持原无电池壳46.29×56.45mm长宽，总厚35.2mm，带可拆绝缘载架和下沉开关口。三种候选均有103450电池空间与指示灯窗口，均待打印试装。

[2.21 改动与验证范围](docs/reports/RELEASE_2_21.md)：完整启动恢复、Operit 修改电脑 IP、自定义烧录名称、真实 CH0 默认和开发者调试窗口。Windows、Linux、Operit、PCB及独立外壳模型均从本版Release下载；目标手机、新固件实机升级和外壳试装边界见更新记录。[此前更新](docs/reports/UPDATE_20261019.md)。

## 选择适合你的使用方式

先选一条路线，不必把所有入口都安装一遍。

| 你的环境或目标 | 从这里开始 | 使用期间需要运行 |
| --- | --- | --- |
| ChatGPT 普通 Chat，使用 Windows 电脑连接设备 | [Windows 安装](docs/start/AI_INSTALL.md) → [Secure MCP 隧道](docs/integrations/SECURE_MCP.md) | 娃娃、电脑采集服务、隧道 |
| Operit，使用电脑采集 | [Operit 统一安装](docs/integrations/OPERIT_SETUP.md) | 娃娃、电脑服务、Operit |
| Operit，只有安卓手机与家庭 Wi-Fi | [手机直连家庭设备](docs/integrations/OPERIT_NO_PC.md#只有安卓手机没有电脑和服务器) | 娃娃、同一家庭网络中的 Operit |
| Operit，设备直传自己的服务器 | [Operit 服务器模式](docs/integrations/OPERIT_NO_PC.md#有自己的服务器) | 娃娃、服务器、Operit；电脑无需常开 |
| 本机支持 MCP 的其他 AI 客户端 | [Windows 安装](docs/start/AI_INSTALL.md) → [MCP 工具与接入](docs/developers/MCP_TOOLS.md) | 娃娃、电脑采集服务 |
| 自己的聊天前后端，需要本机或服务器接入 | [本机接收服务](docs/integrations/SERVER_QUICKSTART.md) / [Linux 部署](docs/integrations/REMOTE_SERVER_SETUP.md) | 娃娃、接收服务、原聊天应用 |

更详细的区别见 [连接方式选择](docs/start/MCP_TRANSPORT_DECISION.md)。服务器与仅手机模式是 2.20 新增能力，仍需在自己的手机、网络和部署环境中验收。

## 下载哪个文件

| 使用者 | 下载 | 下载后做什么 |
| --- | --- | --- |
| Windows 用户 | [Windows 完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Code_v2.21.0.zip) | 完整解压，保留内置 Python，双击对应入口 |
| Operit 安卓用户 | [AI_Doll_Operit.toolpkg](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Operit.toolpkg) | 在 Operit 包管理中导入，选择连接方式并绑定原聊天 |
| Linux 服务器用户 | [Linux 小型服务包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Server_v2.21.0.tar.gz) | 按 [服务器指南](docs/integrations/REMOTE_SERVER_SETUP.md)运行安装脚本 |
| 采购、制作或焊接主板 | [PCB 与硬件交付包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_PCB_V2_20261016.zip) | 新版丝印与背面镜像已修正；重新下单前核对现有网表不匹配 |
| 3D打印外壳 | [全部模型](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Enclosures_103450_20261020.zip) / [旧板上下堆叠版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Enclosure_Stacked_103450_20261020.zip) | 含STL、STEP、离线预览及检查说明；先按实物主板选择版本 |

Windows 完整包自带运行环境，**无需另装 Python 或 Arduino**。仅使用 Operit 手机直连时，不需要下载 Windows 包，也不需要安装额外的服务器软件。

文件校验与交付范围见 [下载目录](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)；历史版本见 [GitHub Releases](https://github.com/SunRichardSKT/ai-doll-mcp/releases)。源码仓库用于阅读和开发，大型完整包统一放在 Releases。

## 第一次使用

1. **准备已安装固件的开发板与传感器。** 新板可在 Windows 完整包中双击 `Flash_ESP32.cmd`，按 [快速烧录指南](docs/start/QUICK_FLASH.md)完成写入、启动和设备身份确认。已有正常固件时，按对应升级说明操作。
2. **给娃娃配网。** 手机连接设备显示的 `AI-Doll-…` 热点，打开 `http://192.168.4.1/`，配置家庭 2.4 GHz Wi-Fi。参见 [配网与设置页](docs/daily/WIFI_CONNECTION.md)。
3. **只启用实际安装的通道。** 核对 [通道与接线](docs/daily/SENSOR_CHANNELS.md)，再按 [压力校准与日常模式](docs/daily/CALIBRATION_AND_DAILY_MODE.md)确认按压和释放。
4. **连接你原来的 AI 聊天。** 按上方选定路线安装，先查询实际设备状态，再测试一次按压反馈。Operit 用户按标题绑定已有聊天，不用手填聊天 ID 或状态文件路径。

仅安卓手机路线要求开发板已安装本项目固件；目前不提供安卓 USB 烧录流程。先测试硬件时，可以暂不配置 AI，直接使用设备设置页。

**Windows 完整包的三个入口：**

| 入口 | 用途 |
| --- | --- |
| `Flash_ESP32.cmd` | 快速烧录、设备身份确认与日志 |
| `AI_Doll.cmd` | 电脑管理中心、采集、MCP 与 Operit 连接 |
| `AI_Doll_Server.cmd` | 在本机启动供自建应用使用的接收服务 |

## 文档导航

### 入门与安装

| 文档 | 解决的问题 |
| --- | --- |
| [完整教程目录](docs/README.md) | 按入门、日常、接入和开发分类查找全部教程 |
| [连接方式选择](docs/start/MCP_TRANSPORT_DECISION.md) | 判断自己需要电脑、手机直连还是服务器 |
| [快速烧录](docs/start/QUICK_FLASH.md) | 新板写入固件、确认启动与新设备名称 |
| [新板与恢复出厂设置](docs/start/FACTORY_SETTINGS.md) | 默认开关、恢复出厂和配置保留规则 |
| [Wi-Fi 配置与连接恢复](docs/daily/WIFI_CONNECTION.md) | 配网、查看设备 IP、热点与断线恢复 |
| [Windows 首次安装](docs/start/AI_INSTALL.md) | 用完整包连接设备与原 AI 客户端 |

### AI 聊天接入

| 文档 | 适用场景 |
| --- | --- |
| [ChatGPT Secure MCP](docs/integrations/SECURE_MCP.md) | 将电脑 MCP 接入普通 Chat |
| [ChatGPT 调用与互动验收](docs/integrations/CHAT_MCP.md) | 实际状态查询、历史和限时互动 |
| [Operit 统一安装](docs/integrations/OPERIT_SETUP.md) | 一个工具包、聊天绑定、自动工作流与互动开关 |
| [Operit 免电脑使用](docs/integrations/OPERIT_NO_PC.md) | 服务器直传，或安卓手机直连家庭设备 |
| [自建应用本机接收](docs/integrations/SERVER_QUICKSTART.md) | 先在本机运行设备接收服务 |
| [Linux 服务器部署](docs/integrations/REMOTE_SERVER_SETUP.md) | 部署接收服务与 MCP，让电脑无需常开 |
| [其他宿主与转发模板](docs/integrations/HOST_INTEGRATIONS.md) | 对接自有客户端、事件接收与生成队列 |

### 日常设置与维护

| 文档 | 解决的问题 |
| --- | --- |
| [日常使用与管理页面](docs/daily/USER_GUIDE.md) | 启动、页面入口、设备状态与日常操作 |
| [自然陪伴与部位设置](docs/daily/NATURAL_COMPANION.md) | 部位名称、别名、回应等级与聊天融入 |
| [人设、反馈与互动解释](docs/daily/INTERACTION_OBSERVATIONS.md) | 人设补充、回应语气、安静时段与事件含义 |
| [通道与接线](docs/daily/SENSOR_CHANNELS.md) | 配置各路传感器与硬件绑定 |
| [压力校准与日常模式](docs/daily/CALIBRATION_AND_DAILY_MODE.md) | 校准输入、按压阈值与重启后的采样恢复 |
| [互动历史](docs/daily/HISTORY_MANAGEMENT.md) | 查询、摘要、统计、导出与保留设置 |
| [断网缓存](docs/daily/OFFLINE_RECORDS.md) | 离线记录、补传和丢失计数 |
| [无线升级](docs/daily/OTA_UPDATE.md) | 给已联网设备更新固件 |
| [DS18B20 温度](docs/daily/DIGITAL_TEMPERATURE.md) | 数字温度探头的接线与配置 |
| [运行环境与账号密码](docs/daily/RUNTIME_AND_LOGIN.md) | Python、设置页登录和不同连接令牌的用途 |

### 硬件、开发与 AI 助手

| 文档 | 内容 |
| --- | --- |
| [硬件与 BOM](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md) | PCB 工程、采购与装配资料 |
| [开发、测试与打包](docs/developers/DEVELOPER_GUIDE.md) | 环境准备、固件构建、检查与交付 |
| [项目结构与文件规则](docs/developers/REPOSITORY_LAYOUT.md) | 源码、生成物和本机数据各放哪里 |
| [MCP 工具目录](docs/developers/MCP_TOOLS.md) | 本机、HTTP 和设备 MCP 的范围与接口 |
| [直传与同机部署接口](docs/developers/DIRECT_SERVER.md) | 自建前后端、服务器 MCP 和 HTTPS 代理 |
| [接入原聊天](docs/developers/EXISTING_CHAT.md) | 沿用原模型、上下文与消息队列 |
| [主动互动与事件桥](docs/developers/PROACTIVE_INTERACTION.md) | 订阅、租约、去重、取消与确认 |
| [后续计划](docs/developers/DEVELOPMENT_PLAN.md) | 尚待开发或实际环境验收的工作 |
| [统一代码与交付规划](docs/developers/UNIFIED_DELIVERY_PLAN.md) | 入口、配置和代码整理的阶段进度 |
| [给 AI 的安装与验证指南](docs/ai/AI_GUIDE.md) | 交给 AI 助手执行安装、调用和硬件检查 |
| [AI 维护入口](AGENTS.md) | 本仓库的维护约定 |

旧原型、兼容通路与历史报告从 [教程总目录](docs/README.md)查阅。新用户优先使用上方当前入口。

## 项目目录

| 目录 | 用途 |
| --- | --- |
| [firmware/](firmware/) | ESP32 固件源码、设备网页与预编译镜像 |
| [hardware/](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/hardware) | PCB、BOM、制造文件与核对资料 |
| [clients/operit/](clients/operit/) | Operit 手机工具包与设置面板源码 |
| [src/ai_doll/](src/ai_doll/) | 共享互动策略、上下文、摘要与历史核心 |
| [tools/](tools/) | 采集服务、MCP、管理页面、安装与测试工具 |
| [deploy/](deploy/) | Linux 容器与服务部署配置 |
| [templates/](templates/) | 公共接入模板与兼容示例 |
| [docs/](docs/) | 使用教程、开发资料与验证记录 |
| [delivery/](delivery/) | Release 下载入口、交付清单与校验值 |
| [python/](python/) | 内置 Python 的说明与版本元数据；运行文件随完整包提供 |

运行后的个人配置、数据库与日志放在本机 `build/` 或对应服务器／手机的数据目录，不随源码仓库发布。

## 已验证与待验证的能力

| 范围 | 当前状态 |
| --- | --- |
| CH0 实体 FSR | 已有真实按压、释放与电脑归档记录；不能据此确认其他通道 |
| ChatGPT 普通 Chat | Secure 状态、历史与限时模拟文字反馈已有验证；空闲主动唤醒未验证 |
| Operit 原聊天 | 用户已报告能回应触摸；不能据此确认所有部署与后台场景 |
| 新增免电脑模式 | 代码、本机 SDK 与明确的接口替身测试已通过；目标手机、实际服务器、15 分钟持续运行及锁屏仍需实测 |
| 其他硬件 | 温度、电机、其他压力通道及整机电池体验需分别验收 |

完整证据与边界见 [当前验证范围](docs/reports/VALIDATION.md)和 [2.20 实施记录](docs/reports/RELEASE_2_20.md)。模拟数据会保留来源标记，不能用来证明实体传感器或执行器工作正常。

## 常见问题与访问地址

| 要做什么 | 地址或处理方式 |
| --- | --- |
| 打开设备配置页 | 连接设备热点后访问 `http://192.168.4.1/`；家庭 Wi-Fi 下使用设备实际 IP |
| 打开 Windows 管理中心 | 在运行软件的电脑访问 `http://127.0.0.1:8769/` |
| 打开 Windows 烧录页面 | 启动烧录入口后，在该电脑访问 `http://127.0.0.1:8770/` |
| 手机连接电脑服务 | 使用手机可达的电脑局域网地址，不能使用电脑的 `127.0.0.1` |
| 设备离线、连接失败或没有反馈 | 先看 [故障排查](docs/TROUBLESHOOTING.md)，再核对所选路线的操作指南 |

配网成功后，设备热点和固定配置页仍保留；`192.168.4.1` 不是设备在家庭网络中的固定地址。每次 USB 烧录会生成新内部设备编号，显示名可自定义，日常重启保持名称；标准烧录保留配置，恢复出厂才按对应流程清空。

## 数据与许可证

电脑、服务器与手机直连路线分别保存自己的记录。使用云端 AI 时，提供给模型的互动内容会发送到该平台。更新软件时保留已有数据与校准，具体保留范围见对应升级指南。

原创代码与文档使用 [MIT License](LICENSE)。第三方依赖许可随完整包保留。
