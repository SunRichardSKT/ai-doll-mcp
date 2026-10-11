# 下载与交付文件

当前软件 **2.16.2** / 固件 **2.8.1**，文档整理于 2026-10-11。请选择与你的使用方式对应的包，完整解压后按包内 README 操作。

## 应该下载哪个

| 包 | 适合谁 | 解压后做什么 |
| --- | --- | --- |
| [AI_Doll_Code_v2.16.2.zip](AI_Doll_Code_v2.16.2.zip) · 28.63 MiB | Windows 用户 / 软件开发者 | 普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd |
| [AI_Doll_PCB_V2_20261003.zip](AI_Doll_PCB_V2_20261003.zip) · 9.94 MiB | 采购和手工焊接主板 | 用嘉立创 EDA 专业版打开原生工程，核对 BOM 与装配面 |
| [AI_Doll_Server_v2.16.2.tar.gz](AI_Doll_Server_v2.16.2.tar.gz) · 0.06 MiB | 远程 Linux 服务器 | 运行 sudo bash Install_Server.sh，按提示填写域名 |

Windows 包内置 Python，无需另装。Linux 小型包不含 Windows Python，由容器准备运行环境。PCB 包只因文档整理更新说明，物理工程和原下单文件保持。

[Windows 首次安装](../docs/AI_INSTALL.md) · [远程部署](../docs/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/AI_GUIDE.md) · [全部文档](../docs/README.md)

## 如何校验下载

[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 记录整包 SHA-256；每个包的 MANIFEST.json 记录逐文件校验。Linux 包另提供 .sha256 文件，可运行 sha256sum -c 对应文件名。

- `AI_Doll_Code_v2.16.2.zip`：`f852d1a8719ed7bffe0dffcaecee1d2e5aa0f662264e29b28a0a54b797a6407a`
- `AI_Doll_PCB_V2_20261003.zip`：`f266c34b0afee4e681cd604355e1441881263c7136ca69a9efad0ccf633de730`
- `AI_Doll_Server_v2.16.2.tar.gz`：`1db8fde5668529911c2d16db5ac1ce15bae06be775a0386ea1df0af9b0401aab`

## 交付范围

公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。

已验证普通 Chat Secure 的模拟状态 / 历史 / 限时反馈；实体传感器、普通 Chat 空闲唤醒和真实公网部署仍待验收。见 [验证汇总](../docs/VALIDATION.md)。
