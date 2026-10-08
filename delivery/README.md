# AI 共感娃娃交付说明

更新日期：2026-10-09。电脑 Bridge v2.5 支持 Wi-Fi 采集，已测试开发板固件为 v2.3。请直接发送下面的 ZIP 包；接收者按包内 README 使用。

- [AI_Doll_Code_v2.5.0.zip](AI_Doll_Code_v2.5.0.zip)：62 个公开文件，0.69 MiB。
- [AI_Doll_PCB_V2_20261003.zip](AI_Doll_PCB_V2_20261003.zip)：58 个公开文件，9.94 MiB。

代码包包含当前源码、电脑事件桥、33 工具通用 MCP、MCP Events 适配、统一安装入口、已测试 v2.3 固件四个烧录文件、使用文档及接入指南。PCB 包包含最终嘉立创 EDA 工程、采购 BOM、原下单 Gerber 和检查证据。本次增加压力校准、日常模式和诊断，需要升级固件；PCB 仍为八路模拟接口，实际温度探头与震动驱动需按指南接线。两者无需本机 `.tools` 或历史版本即可解压阅读；编译/运行依赖按代码包说明另行安装。

交付包不含本机 Wi-Fi 配置、设备访问密钥或个人互动数据库。完整文件校验值在各包的 `MANIFEST.json`；ZIP 校验值在 `DELIVERY_MANIFEST.json`。

`AI_Doll_Code_v2.5.0.zip` SHA-256：`b5ebc63a7c6b04b7724ccf9059023df7676d7dbffa603cd96fae2238935e3fae`。

`AI_Doll_PCB_V2_20261003.zip` SHA-256：`ad2665fefd5279729f734b97bbf099d7966332770a5f412f5daa03fc50215004`。

