# 下载与交付文件

当前软件 **2.17.0** / 固件 **2.9.0**，交付更新于 2026-10-13。普通 Windows 用户下载完整包，完整解压后双击入口，不需要安装 Python 或 Arduino。

## 应该下载哪个

| 包 | 适合谁 | 解压后做什么 |
| --- | --- | --- |
| [AI_Doll_Code_v2.17.0.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.17.0/AI_Doll_Code_v2.17.0.zip) · 30.65 MiB | Windows 用户 / 软件开发者 | 普通 Chat 双击 AI_Doll.cmd；自建应用本机接收双击 AI_Doll_Server.cmd |
| [AI_Doll_PCB_V2_20261003.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.17.0/AI_Doll_PCB_V2_20261003.zip) · 9.94 MiB | 采购和手工焊接主板 | 用嘉立创 EDA 专业版打开原生工程，核对 BOM 与装配面 |
| [AI_Doll_Server_v2.17.0.tar.gz](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.17.0/AI_Doll_Server_v2.17.0.tar.gz) · 0.07 MiB | 远程 Linux 服务器 | 运行 sudo bash Install_Server.sh，按提示填写域名 |

Windows 包内置 Python，无需另装。Linux 小型包不含 Windows Python，由容器准备运行环境。PCB 包只因文档整理更新说明，物理工程和原下单文件保持。

[Windows 首次安装](../docs/start/AI_INSTALL.md) · [远程部署](../docs/integrations/REMOTE_SERVER_SETUP.md) · [给 AI 的执行指南](../docs/ai/AI_GUIDE.md) · [全部文档](../docs/README.md)

## 如何校验下载

[DELIVERY_MANIFEST.json](DELIVERY_MANIFEST.json) 记录整包 SHA-256；每个包的 MANIFEST.json 记录逐文件校验。Linux 包另提供 .sha256 文件，可运行 sha256sum -c 对应文件名。

- `AI_Doll_Code_v2.17.0.zip`：`5d66b05e9f647d7d206a90543d6b9623ad9c1772b63451294a92a133de57714b`
- `AI_Doll_PCB_V2_20261003.zip`：`7d595877706d4fb9ca48edb253562f0dfa09a77b8485ff0fceae46a4c76a1946`
- `AI_Doll_Server_v2.17.0.tar.gz`：`6fafee755d228be9427c126f272fc2da89d2e2ebb8e2c154ca7075a4dbc9be5e`

## 交付范围

公共包只包含代码、文档、固件、PCB 和公共模板，不包含个人配对、Wi-Fi、令牌或互动数据库。更新保留自己的 build 数据，远程部署保留数据卷。

新板烧录：双击 Flash_ESP32.cmd，点击一键烧录。日常管理：双击 AI_Doll.cmd。手机连接娃娃热点后，固定设置页为 http://192.168.4.1/，配家庭 Wi-Fi 后仍保留。

每次 USB 烧录产生新设备名称并保留独立日志；标准烧录保留设置，恢复出厂才清空设备。CH0 实体按压/释放及电脑归档已实测；其他硬件、普通 Chat 空闲唤醒和真实公网部署仍按 [验证汇总](../docs/reports/VALIDATION.md)列出的范围。
