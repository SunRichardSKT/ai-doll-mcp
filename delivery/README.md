# 下载与交付文件

**2.20.0 预发布版 / 固件 2.9.0**，发布更新于 2026-10-16。[本版 Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.20.0)。新增服务器与仅手机模式仍需目标环境实测。普通 Windows 用户使用完整包，无需安装 Python 或 Arduino。

## 应该下载哪个

| 包 | 适合谁 | 解压后做什么 |
| --- | --- | --- |
| [AI_Doll_Code_v2.20.0.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.20.0/AI_Doll_Code_v2.20.0.zip) · 30.82 MiB | Windows 用户 / 软件开发者 | 普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd |
| [AI_Doll_PCB_V2_20261016.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.20.0/AI_Doll_PCB_V2_20261016.zip) · 11.10 MiB | 采购和手工焊接主板 | 打开新版丝印工程与 BOM；重新下单前核对现有网表不匹配 |
| [AI_Doll_Server_v2.20.0.tar.gz](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.20.0/AI_Doll_Server_v2.20.0.tar.gz) · 0.11 MiB | 远程 Linux 服务器 | 运行 sudo bash Install_Server.sh，按提示填写域名 |
| [AI_Doll_Operit.toolpkg](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.20.0/AI_Doll_Operit.toolpkg) · 0.03 MiB | Operit 安卓用户 | 在包管理中导入，选择电脑、服务器或仅手机连接，按标题绑定原聊天 |

Operit 无需为了取得手机工具包下载 Windows 包。服务器管理页可导出连接文件；仅手机模式填写家庭设备 IP。原电脑入口继续兼容，完整包仍内含相同工具包。[统一安装](../docs/integrations/OPERIT_SETUP.md) · [免电脑指南](../docs/integrations/OPERIT_NO_PC.md)。

Windows 包内置 Python，无需另装。Linux 小型包不含 Windows Python，由容器准备运行环境。20261016 PCB 包已优化丝印并修正背面文字，电路与原下单文件保持；当前仍有 1 项网表不匹配，重新下单前须核对。[丝印与 3D 核对](../hardware/rev-v2/丝印镜像修正说明_20261016.md)。

[Windows 首次安装](../docs/start/AI_INSTALL.md) · [远程部署](../docs/integrations/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/ai/AI_GUIDE.md) · [全部文档](../docs/README.md)

## 如何校验下载

[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 与 [SHA256SUMS.txt](SHA256SUMS.txt) 记录下载哈希；ZIP / TAR 内的 MANIFEST.json 记录逐文件校验，ToolPkg 使用 CHECKSUMS.json。Linux 包另提供 [.sha256](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.20.0/AI_Doll_Server_v2.20.0.tar.gz.sha256)，可运行 sha256sum -c 对应文件名。

[单独下载 Linux 安装入口](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.20.0/Install_Server.sh)。大型文件只存 GitHub Releases，不加入源码仓库。

- `AI_Doll_Code_v2.20.0.zip`：`206df3bf4030d40c31c25d5031ad6d5ea60f17ec398fc43b9071b6d0c84df41c`
- `AI_Doll_PCB_V2_20261016.zip`：`76002d02cb0267b1fe54ad440b96a978f4e614d720bd4b540ad23e98adc7d0eb`
- `AI_Doll_Server_v2.20.0.tar.gz`：`f621a087eb0af390b66e8b8312b8a57012848c8ccc3bb9828ab1ac353c2e7046`
- `AI_Doll_Operit.toolpkg`：`a2a143396259533fc32225a44ff409611b6a45379eee745a867def32f12f2944`

## 交付范围

公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。

新板烧录：双击 Flash_ESP32.cmd，点击一键烧录。日常管理：双击 AI_Doll.cmd。手机连接娃娃热点后，固定设置页为 http://192.168.4.1/，配家庭 Wi-Fi 后仍保留。

每次 USB 烧录产生新设备名称并保留独立日志；标准烧录保留设置，恢复出厂才清空设备。CH0 实体按压/释放及电脑归档已实测；其他硬件、普通 Chat 空闲唤醒和真实公网部署仍按 [验证汇总](../docs/reports/VALIDATION.md)列出的范围。
