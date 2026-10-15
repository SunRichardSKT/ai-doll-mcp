# 开发、接口与打包

> 开发者参考；普通用户可以跳过。 [全部目录](../README.md)


普通使用者不需要编译，按 [首次安装](../start/AI_INSTALL.md)使用完整包。本页面向维护代码、定制接口和制作交付包的开发者。

## 项目结构

| 目录 / 文件 | 用途 |
| --- | --- |
| `firmware/src/` | 设备固件、网页、传感器与上传驱动 |
| `firmware/prebuilt/` | 当前四个烧录文件与校验清单 |
| `src/ai_doll/core/` | 共享上下文、事件策略、摘要与历史管理；旧 tools 路径兼容 |
| `clients/operit/` | 统一手机 ToolPkg、配置、工作流和设置面板 |
| `tools/` | 采集、MCP、事件桥、管理页和测试 |
| `deploy/direct-server/` | Linux Docker / Caddy 配置 |
| `templates/` | 公共连接 / 宿主示例，非个人配置 |
| `docs/` | 使用、接口、AI 指引与分阶段报告 |
| `python/` | 完整包运行环境；源码仓库仅说明和元数据 |
| `build/` | 本机配置、SQLite、生成物与证据，不公开 |

硬件与交付下载见 [公开硬件目录](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/hardware/rev-v2)和 [交付说明](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)。

## 常用端口

| 默认端口 | 服务 | 默认范围 |
| --- | --- | --- |
| 8769 | Windows 管理中心 | 回环 |
| 8768 | 电脑采集 / 历史 / 事件桥 | 回环 |
| 8771 | HTTP / 私密 MCP | 回环；两种入口不要同时启动 |
| 8774 | Secure 专用 MCP 网关 | 回环 |
| 8781 | 设备直传接收服务 | 手工默认回环，本机启动器可选 LAN |
| 8782 | 直传数据库 MCP | Python `--mcp` 启用；Linux Compose 默认启用 |
| UDP 28768 | 已配对设备发现 | 可信局域网广播 |

设备根网页与 MCP 地址是不同用途。Linux 小型包共用接收数据库并提供 19 工具，地址绑定单个配对设备。接口分别见 [工具目录](MCP_TOOLS.md)、[事件桥](PROACTIVE_INTERACTION.md)、[直传服务](DIRECT_SERVER.md)。

## 编译固件

为 PlatformIO 建立独立 Python 3.12 开发环境。日常随包 Python 不等于编译工具已安装。项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-companion.txt
.\.venv\Scripts\python.exe -m pip install platformio
.\tools\build_lab.ps1
```

唯一目标 `supermini-lab`。确认用户需要烧录、实际串口和占用情况后，才用 `build_lab.ps1 -Upload -Port 实际串口`。不自动全片擦除。镜像地址见 [预编译说明](../../firmware/prebuilt/README.md)。

构建后运行 `python tools/export_firmware.py`，导出本次三个编译镜像并为完整四文件更新清单。网页嵌入头文件在构建前生成，不提交。正式 USB 烧录使用 `Flash_ESP32.cmd` 或 `tools/flash_esp32.py`，才能生成新的设备名称及完整日志；PlatformIO 的直接 Upload 仅供开发调试，保留既有设备编号。

## 验证原则与入口

本地算法 / 协议测试、真实开发板、目标聊天和真实模型分开记录。用模拟事件验证软件，不称为实体传感器验收。按改动选相关套件，不在用户互动期间执行会重启或覆盖缓存的测试。

```powershell
.\python\python.exe -m unittest discover -s tools -p test_chat_gateway.py
.\python\python.exe -m unittest discover -s tools -p test_remote_server_install.py
.\python\python.exe -m unittest discover -s tools -p test_history_management.py
```

Node / Playwright 页面测试需要开发者另装对应环境，运行 `tools/test_*.cjs`；不属于新手安装步骤。`test_private_mcp_device.py`、`test_offline_device.py` 等实机入口会产生模拟记录，后者会重启并验证容量覆盖，先读文件说明、停采集并确认没有活跃会话。

## 制作交付包

```powershell
.\python\python.exe tools/package_companion.py
.\python\python.exe tools/audit_delivery.py delivery/AI_Doll_Code_v2.20.0.zip
.\python\python.exe tools/audit_delivery.py delivery/AI_Doll_Server_v2.20.0.tar.gz
.\python\python.exe tools/check_documentation.py --archive delivery/AI_Doll_Code_v2.20.0.zip
.\python\python.exe tools/check_documentation.py --archive delivery/AI_Doll_Server_v2.20.0.tar.gz
```

ZIP / TAR 内 `MANIFEST.json` 是逐文件 SHA-256，ToolPkg 使用 `CHECKSUMS.json`。`DELIVERY_MANIFEST.json` 和 `SHA256SUMS.txt` 记录 Windows、Linux、PCB 与独立手机工具包的哈希。Windows Python 从官方 CPython 和固定 wheel 构建，入口 `tools/build_portable_python.py`；不能打包本机 `.venv`。

完整包发布到 GitHub Releases；源码中的 delivery 只保存下载入口与校验清单。Linux 安装器从相同版本的 Release 下载包和校验文件。目录与冗余清理规则见 [项目结构](REPOSITORY_LAYOUT.md)。

首页与使用指南维护在源文件中，打包复用相同文档；不得将配对、个人历史、隧道令牌或日志加入允许清单。发布前验证所有 Markdown 链接、实际下载校验、固件 / PCB 非文档文件未意外改变。

## 扩展传感器 / 宿主

新传感器需实现真实驱动、参数验证、资源冲突与故障质量，再加入能力列表，见 [通道扩展](../daily/SENSOR_CHANNELS.md)。原应用事件接入必须持久去重、处理取消和共享聊天队列，见 [原聊天指南](EXISTING_CHAT.md)。

当前范围与后续工作见 [验证汇总](../reports/VALIDATION.md)和 [开发计划](DEVELOPMENT_PLAN.md)。

## Operit 统一入口

手机主源码在 `clients/operit/`，运行 `python tools/package_operit.py` 生成单个 `.toolpkg`。完整包构建会自动包含它。旧 `templates/operit/` 为冻结的独立脚本兼容参考，不再开发新的增量安装入口。当前 Android 调度、文件选择器和真实后台回复边界见 [统一使用指南](../integrations/OPERIT_SETUP.md)。

源码构建 Docker 前同样需要先生成该 ToolPkg，要求开发环境具有 Node.js 18+；使用 Release 的 Linux 包部署时已包含工具包，用户不需要安装 Node 或另装手机服务。
