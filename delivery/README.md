# 下载与交付文件

**0.1.2 · 0.1.2 内测版 / 固件0.1.2**，更新于2026-11-15。[下载本版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.2)。

本版修复Operit配置并发覆盖和设备重启恢复，新增NTC10k/B3435和擦眼泪感应片，使用现板两个PA2.0传感器口，可保留六路压力。温度与擦眼泪分别设置只记录／允许回复；配套固件为resistive-inputs-v1。Windows完整包内置Python，保留原历史、设置及校准；未自动给已有设备烧录。接线和感应片制作见[现板电阻扩展](../hardware/expansion/resistive-inputs/README.md)。

## 应该下载哪个

| 包 | 适合谁 | 解压后做什么 |
| --- | --- | --- |
| AI_Doll_Code_v0.1.2.zip · 30.65 MiB | Windows 用户 / 软件开发者 | 普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd |
| AI_Doll_Firmware_v0.1.2.zip · 0.76 MiB | 已有软件／仅升级开发板 | 按固件说明使用OTA应用镜像或配套烧录工具，不全片擦除 |
| AI_Doll_PCB_v0.1.2.zip · 11.04 MiB | 采购和手工焊接主板 | 按实物版本选择工程、BOM与制造文件，下单前复核 |
| AI_Doll_Server_v0.1.2.tar.gz · 0.34 MiB | 远程 Linux 服务器 | 运行 sudo bash Install_Server.sh，按提示填写域名 |
| AI_Doll_Operit.toolpkg · 0.22 MiB | Operit 安卓用户 | 在包管理中导入，选择电脑、服务器或仅手机连接，按标题绑定原聊天 |
| AI_Doll_Enclosures_v0.1.2.zip · 4.93 MiB | 3D打印与机械修改 | 最终插座板、已制带线板及独立充电模块的加固壳；按实物选STL或STEP |
| AI_Doll_Stacked_Enclosure_v0.1.2.zip · 1.11 MiB | 已制带线板上下堆叠壳 | 长宽46.29×56.45mm，总高35.6mm；底壳、绝缘托板、上盖整套打印 |

Operit 无需为了取得手机工具包下载 Windows 包。服务器管理页可导出连接文件、连接码与临时二维码；仅手机模式默认从设备热点读取，不要求实体标签。原电脑入口继续兼容，完整包内含相同工具包。[统一安装](../docs/integrations/OPERIT_SETUP.md) · [免电脑指南](../docs/integrations/OPERIT_NO_PC.md)。

Windows包内置Python。Linux小型包不含Windows运行环境，由容器准备。PCB包保留第一代最终版与已制板参考资料；按[硬件目录](../hardware/rev-v2/README.md)区分版本，第一代最终版见[锁扣插座板](../hardware/rev-v2/candidates/c3-socket-20261105/README.md)。

[Windows 首次安装](../docs/start/AI_INSTALL.md) · [远程部署](../docs/integrations/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/ai/AI_GUIDE.md) · [全部文档](../docs/README.md)

## 许可

软件 AGPL-3.0-only，硬件 CERN-OHL-S-2.0，第三方资源保留各自声明。具体适用范围见 [项目许可](../LICENSING.md)。

## 如何校验发布包

使用[本版Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.2)附带的固定清单。

[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 与 [SHA256SUMS.txt](SHA256SUMS.txt) 记录哈希；ZIP / TAR 内的 MANIFEST.json 记录逐文件校验，ToolPkg 使用 CHECKSUMS.json。Linux 包另有同目录 `.sha256`。

Linux安装入口位于本版TAR内和Release附件 `Install_Server.sh`；使用同版安装器，保留原目录、项目名与数据卷。大型文件仅放在Releases，源码目录保留下载链接与校验元数据。

- `AI_Doll_Code_v0.1.2.zip`：`b769613fd1f7f8fb95cf4d77eedbbe07b4c182dac38055c467b3f768aac89a36`
- `AI_Doll_Firmware_v0.1.2.zip`：`bdc7f7177909a39106e1b60d205dd1a38af96b2ccccd9347b3a011d543f18a14`
- `AI_Doll_PCB_v0.1.2.zip`：`28f3da38d272a3b9ec49084d50dc1a51862ba443f9333988ba1f292e7af70aa4`
- `AI_Doll_Server_v0.1.2.tar.gz`：`9ddfad75d618f33077a08ebaa3aeac191cd92f66ade712b0bfcc2ae88dc31144`
- `AI_Doll_Operit.toolpkg`：`d4273aff02dd1883bae7e89ee64a7b34685322b7c647e50df987214372b2cd9b`
- `AI_Doll_Enclosures_v0.1.2.zip`：`42abc897919df195f2b38b2e0c03754b8d214893d5fe93d5cc8817c0a4723375`
- `AI_Doll_Stacked_Enclosure_v0.1.2.zip`：`b7493b9e3b84840065408e17d7e3735d340699f27f19f1c4e8a546aa3f4f5645`

## 交付范围

公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。

新板烧录：双击 Flash_ESP32.cmd，可选随包固件、本地项目固件 ZIP 或查询 GitHub 最新正式版，校验后点击一键烧录。日常管理：双击 AI_Doll.cmd。手机连接娃娃热点后，配网页为 http://192.168.4.1/setup，首次热点最长10分钟，新配网成功后约90秒关闭；正常重启不开热点，运行中长按BOOT约3秒重新开启。

每次 USB 烧录产生新内部配对编号；可选择自定义显示名和热点名并保留独立日志；标准烧录保留设置，恢复出厂才清空设备。安装后按实际通道检查采样与聊天接入，检查记录见[验证汇总](../docs/reports/VALIDATION.md)。
