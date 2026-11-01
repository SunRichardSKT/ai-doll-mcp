# 下载与交付文件

**0.1.1 · 内测0.1.1版 / 固件0.1.1**，更新于2026-11-02。[下载本版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1)。

增加Wi-Fi扫描与连接提示、网络恢复，并精简温度、动作及外接物理输出驱动，保留压力、干接点与历史。电脑／服务器与手机包同版更新，保留原数据。Windows完整包内置Python，无需另装。

## 应该下载哪个

| 包 | 适合谁 | 解压后做什么 |
| --- | --- | --- |
| AI_Doll_Code_v0.1.1.zip · 30.58 MiB | Windows 用户 / 软件开发者 | 普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd |
| AI_Doll_Firmware_v0.1.1.zip · 0.74 MiB | 已有软件／仅升级开发板 | 按固件说明使用OTA应用镜像或配套烧录工具，不全片擦除 |
| AI_Doll_PCB_v0.1.1.zip · 11.38 MiB | 采购和手工焊接主板 | 打开新版丝印工程与 BOM；重新下单前核对现有网表不匹配 |
| AI_Doll_Server_v0.1.1.tar.gz · 0.30 MiB | 远程 Linux 服务器 | 运行 sudo bash Install_Server.sh，按提示填写域名 |
| AI_Doll_Operit.toolpkg · 0.20 MiB | Operit 安卓用户 | 在包管理中导入，选择电脑、服务器或仅手机连接，按标题绑定原聊天 |
| AI_Doll_Enclosures_v0.1.1.zip · 4.05 MiB | 3D打印与机械修改 | 已制板堆叠壳与紧凑板平铺壳；按主板选STL或STEP |
| AI_Doll_Stacked_Enclosure_v0.1.1.zip · 1.24 MiB | 已制板上下堆叠壳 | 保持原长宽46.29×56.45mm，总厚35.2mm；打印底壳、绝缘载架、上盖 |

Operit 无需为了取得手机工具包下载 Windows 包。服务器管理页可导出连接文件、连接码与临时二维码；仅手机模式默认从设备热点读取，不要求实体标签。原电脑入口继续兼容，完整包内含相同工具包。[统一安装](../docs/integrations/OPERIT_SETUP.md) · [免电脑指南](../docs/integrations/OPERIT_NO_PC.md)。

Windows 包内置 Python，无需另装。Linux 小型包不含 Windows Python，由容器准备运行环境。PCB 包使用当前丝印工程并修正背面文字，电路与原下单文件保持；当前仍有 1 项网表不匹配，重新下单前须核对。[丝印与 3D 核对](../hardware/rev-v2/丝印镜像修正说明_20261016.md)。

[Windows 首次安装](../docs/start/AI_INSTALL.md) · [远程部署](../docs/integrations/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/ai/AI_GUIDE.md) · [全部文档](../docs/README.md)

## 如何校验发布包

使用[本版Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1)附带的固定清单。

[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 与 [SHA256SUMS.txt](SHA256SUMS.txt) 记录哈希；ZIP / TAR 内的 MANIFEST.json 记录逐文件校验，ToolPkg 使用 CHECKSUMS.json。Linux 包另有同目录 `.sha256`。

Linux安装入口位于本版TAR内和Release附件 `Install_Server.sh`；使用同版安装器，保留原目录、项目名与数据卷。大型文件仅放在Releases，源码目录保留下载链接与校验元数据。

- `AI_Doll_Code_v0.1.1.zip`：`cafe4d34543bafe5cab0a5226d44ab625257d82175499e9ccbb0683867c6b60d`
- `AI_Doll_Firmware_v0.1.1.zip`：`9984fffa60e51f0f89e1dea5522777c637fce5b500c783113003a6174ef09aa2`
- `AI_Doll_PCB_v0.1.1.zip`：`543e3fef7857742c600f36fbe730e1aad96b36150d47f464f67ad8b91ecdf905`
- `AI_Doll_Server_v0.1.1.tar.gz`：`c868b812c8268317bab87e8eb82c2b4fcd8ebc83771400404baec36ca14f7102`
- `AI_Doll_Operit.toolpkg`：`55bddf419b7688c1655407e8c371a252b3c9ca96fc125aac33659e0a6a2cfde8`
- `AI_Doll_Enclosures_v0.1.1.zip`：`21e6d655a01b54655ea0e15ee483e7aaf7dc0168a7b57c12ba13337efad8784b`
- `AI_Doll_Stacked_Enclosure_v0.1.1.zip`：`f465623703fe3f34689c51ea627103ce6a3727adf8397f7c69f526a49109c11b`

## 交付范围

公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。

新板烧录：双击 Flash_ESP32.cmd，点击一键烧录。日常管理：双击 AI_Doll.cmd。手机连接娃娃热点后，固定设置页为 http://192.168.4.1/，首次热点最长10分钟，新配网成功后约90秒关闭；正常重启不开热点，运行中长按BOOT约3秒重新开启。

每次 USB 烧录产生新内部配对编号；可选择自定义显示名和热点名并保留独立日志；标准烧录保留设置，恢复出厂才清空设备。CH0 实体按压/释放及电脑归档已实测；其他硬件、普通 Chat 空闲唤醒和真实公网部署仍按 [验证汇总](../docs/reports/VALIDATION.md)列出的范围。
