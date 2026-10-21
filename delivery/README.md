# 下载与交付文件

**2.24.1 预发布 / 固件 2.12.1**，构建更新于2026-10-22。稳定版仍为[2.21.0](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.21.0)。本版修复Linux安装漏文件并统一18项文档问题；保留Operit自动检查、完整触摸队列与独立历史页面。电脑／服务器模式需同步更新服务端和手机包。服务器与仅手机模式仍需目标环境实测，外壳仍需打印试装。普通Windows用户使用完整包，无需安装Python或Arduino。

## 应该下载哪个

| 包 | 适合谁 | 解压后做什么 |
| --- | --- | --- |
| [AI_Doll_Code_v2.24.1.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/AI_Doll_Code_v2.24.1.zip) · 30.94 MiB | Windows 用户 / 软件开发者 | 普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd |
| [AI_Doll_PCB_V2_20261016.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/AI_Doll_PCB_V2_20261016.zip) · 11.10 MiB | 采购和手工焊接主板 | 打开新版丝印工程与 BOM；重新下单前核对现有网表不匹配 |
| [AI_Doll_Server_v2.24.1.tar.gz](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/AI_Doll_Server_v2.24.1.tar.gz) · 0.14 MiB | 远程 Linux 服务器 | 运行 sudo bash Install_Server.sh，按提示填写域名 |
| [AI_Doll_Operit.toolpkg](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/AI_Doll_Operit.toolpkg) · 0.04 MiB | Operit 安卓用户 | 在包管理中导入，选择电脑、服务器或仅手机连接，按标题绑定原聊天 |
| [AI_Doll_Enclosures_103450_20261020.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/AI_Doll_Enclosures_103450_20261020.zip) · 4.44 MiB | 3D打印与机械修改 | 三个候选：旧板平铺、新板平铺、旧板堆叠；按主板选STL或STEP |
| [AI_Doll_Enclosure_Stacked_103450_20261020.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/AI_Doll_Enclosure_Stacked_103450_20261020.zip) · 1.31 MiB | 只需要旧板上下堆叠壳 | 保持原长宽46.29×56.45mm，总厚35.2mm；打印底壳、绝缘载架、上盖 |

Operit 无需为了取得手机工具包下载 Windows 包。服务器管理页可导出连接文件；仅手机模式填写家庭设备 IP。原电脑入口继续兼容，完整包仍内含相同工具包。[统一安装](../docs/integrations/OPERIT_SETUP.md) · [免电脑指南](../docs/integrations/OPERIT_NO_PC.md)。

Windows 包内置 Python，无需另装。Linux 小型包不含 Windows Python，由容器准备运行环境。20261016 PCB 包已优化丝印并修正背面文字，电路与原下单文件保持；当前仍有 1 项网表不匹配，重新下单前须核对。[丝印与 3D 核对](../hardware/rev-v2/丝印镜像修正说明_20261016.md)。

[Windows 首次安装](../docs/start/AI_INSTALL.md) · [远程部署](../docs/integrations/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/ai/AI_GUIDE.md) · [全部文档](../docs/README.md)

## 如何校验下载

本目录仅记录2.24.1；稳定版与旧版必须使用其Release内的固定清单，不使用这里校验同名旧手机包。[2.21校正版入口](../docs/start/STABLE_2_21.md)。

[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 与 [SHA256SUMS.txt](SHA256SUMS.txt) 记录下载哈希；ZIP / TAR 内的 MANIFEST.json 记录逐文件校验，ToolPkg 使用 CHECKSUMS.json。Linux 包另提供 [.sha256](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/AI_Doll_Server_v2.24.1.tar.gz.sha256)，可运行 sha256sum -c 对应文件名。

[单独下载 Linux 安装入口](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/Install_Server.sh)。大型文件只存 GitHub Releases，不加入源码仓库。

- `AI_Doll_Code_v2.24.1.zip`：`3ff7fd17cb2d1b3e6c3133433f8f1b37ba196a09417ee5c2cbb8d49a1c05d12e`
- `AI_Doll_PCB_V2_20261016.zip`：`eaca9c0ea31840a33b1d0637fd15ee6bd3260a1611119d23256e51f799e530d7`
- `AI_Doll_Server_v2.24.1.tar.gz`：`50b625fa0ff45591d87c5c00e3c3cd2f95ee2f438e8f631af7a3fcfd43a3c647`
- `AI_Doll_Operit.toolpkg`：`131a1f22cf0e91223154554d19cb4721013523f8952cb926f063d91d29c5c975`
- `AI_Doll_Enclosures_103450_20261020.zip`：`1904338094c2246c1dcabaf534a88af1550b948ba622a022567c94b655861005`
- `AI_Doll_Enclosure_Stacked_103450_20261020.zip`：`76b6ff720db7e472b97f6fc3c72ca80886a9c0a32159ae77b64811ef216a8da5`

## 交付范围

公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。

新板烧录：双击 Flash_ESP32.cmd，点击一键烧录。日常管理：双击 AI_Doll.cmd。手机连接娃娃热点后，固定设置页为 http://192.168.4.1/，配家庭 Wi-Fi 后仍保留。

每次 USB 烧录产生新内部配对编号；可选择自定义显示名和热点名并保留独立日志；标准烧录保留设置，恢复出厂才清空设备。CH0 实体按压/释放及电脑归档已实测；其他硬件、普通 Chat 空闲唤醒和真实公网部署仍按 [验证汇总](../docs/reports/VALIDATION.md)列出的范围。
