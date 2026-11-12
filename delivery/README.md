# 下载与交付文件

**0.1.1 · 内测0.1.1版 / 固件0.1.1**，更新于2026-11-13。[下载本版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1)。

本次更新烧录器：支持选择本地项目固件、查询和下载GitHub最新正式版，配网入口为`http://192.168.4.1/setup`。三种外壳均改为加固结构，核心壳底壳、托板和上盖须整套重打。Windows完整包内置Python，无需另装；保留原有配置和历史。固件镜像与电气参数未变。

## 应该下载哪个

| 包 | 适合谁 | 解压后做什么 |
| --- | --- | --- |
| AI_Doll_Code_v0.1.1.zip · 30.63 MiB | Windows 用户 / 软件开发者 | 普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd |
| AI_Doll_Firmware_v0.1.1.zip · 0.76 MiB | 已有软件／仅升级开发板 | 按固件说明使用OTA应用镜像或配套烧录工具，不全片擦除 |
| AI_Doll_PCB_v0.1.1.zip · 11.04 MiB | 采购和手工焊接主板 | 按实物版本选择工程、BOM与制造文件，下单前复核 |
| AI_Doll_Server_v0.1.1.tar.gz · 0.34 MiB | 远程 Linux 服务器 | 运行 sudo bash Install_Server.sh，按提示填写域名 |
| AI_Doll_Operit.toolpkg · 0.22 MiB | Operit 安卓用户 | 在包管理中导入，选择电脑、服务器或仅手机连接，按标题绑定原聊天 |
| AI_Doll_Enclosures_v0.1.1.zip · 4.93 MiB | 3D打印与机械修改 | 最终插座板、已制带线板及独立充电模块的加固壳；按实物选STL或STEP |
| AI_Doll_Stacked_Enclosure_v0.1.1.zip · 1.11 MiB | 已制带线板上下堆叠壳 | 长宽46.29×56.45mm，总高35.6mm；底壳、绝缘托板、上盖整套打印 |

Operit 无需为了取得手机工具包下载 Windows 包。服务器管理页可导出连接文件、连接码与临时二维码；仅手机模式默认从设备热点读取，不要求实体标签。原电脑入口继续兼容，完整包内含相同工具包。[统一安装](../docs/integrations/OPERIT_SETUP.md) · [免电脑指南](../docs/integrations/OPERIT_NO_PC.md)。

Windows包内置Python。Linux小型包不含Windows运行环境，由容器准备。PCB包保留第一代最终版与已制板参考资料；按[硬件目录](../hardware/rev-v2/README.md)区分版本，第一代最终版见[锁扣插座板](../hardware/rev-v2/candidates/c3-socket-20261105/README.md)。

[Windows 首次安装](../docs/start/AI_INSTALL.md) · [远程部署](../docs/integrations/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/ai/AI_GUIDE.md) · [全部文档](../docs/README.md)

## 许可

软件 AGPL-3.0-only，硬件 CERN-OHL-S-2.0，第三方资源保留各自声明。具体适用范围见 [项目许可](../LICENSING.md)。

## 如何校验发布包

使用[本版Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1)附带的固定清单。

[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 与 [SHA256SUMS.txt](SHA256SUMS.txt) 记录哈希；ZIP / TAR 内的 MANIFEST.json 记录逐文件校验，ToolPkg 使用 CHECKSUMS.json。Linux 包另有同目录 `.sha256`。

Linux安装入口位于本版TAR内和Release附件 `Install_Server.sh`；使用同版安装器，保留原目录、项目名与数据卷。大型文件仅放在Releases，源码目录保留下载链接与校验元数据。

- `AI_Doll_Code_v0.1.1.zip`：`fa052c84b6ec8bae3669363ce57a1f211c69065fa85d1098cc5bf1b6829ebc0f`
- `AI_Doll_Firmware_v0.1.1.zip`：`b86fe3e3e489d7ca1ad60be2ebef1996e38f0def040e577ca3f2181cb4f5654d`
- `AI_Doll_PCB_v0.1.1.zip`：`27a2c64822eb7242f5df582467ea99f393fbf0106cc3e62bfb1d077935f892bd`
- `AI_Doll_Server_v0.1.1.tar.gz`：`3c6e1cddfd06e57e4d1f7c496a80d42b9db84358fe33d5fb879a64cca675e8e0`
- `AI_Doll_Operit.toolpkg`：`812e3c56b914ae11b81de0a61ead621b9ed67f00b396b278b62fa9f7579f6bac`
- `AI_Doll_Enclosures_v0.1.1.zip`：`42abc897919df195f2b38b2e0c03754b8d214893d5fe93d5cc8817c0a4723375`
- `AI_Doll_Stacked_Enclosure_v0.1.1.zip`：`b7493b9e3b84840065408e17d7e3735d340699f27f19f1c4e8a546aa3f4f5645`

## 交付范围

公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。

新板烧录：双击 Flash_ESP32.cmd，可选随包固件、本地项目固件 ZIP 或查询 GitHub 最新正式版，校验后点击一键烧录。日常管理：双击 AI_Doll.cmd。手机连接娃娃热点后，配网页为 http://192.168.4.1/setup，首次热点最长10分钟，新配网成功后约90秒关闭；正常重启不开热点，运行中长按BOOT约3秒重新开启。

每次 USB 烧录产生新内部配对编号；可选择自定义显示名和热点名并保留独立日志；标准烧录保留设置，恢复出厂才清空设备。CH0 实体按压/释放及电脑归档已实测；其他硬件、普通 Chat 空闲唤醒和真实公网部署仍按 [验证汇总](../docs/reports/VALIDATION.md)列出的范围。
