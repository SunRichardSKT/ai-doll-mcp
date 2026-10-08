# AI 共感娃娃交付说明

更新日期：2026-10-09。电脑 Bridge v2.7 支持 Wi-Fi 采集，已测试开发板固件为 v2.4。请直接发送下面的 ZIP 包；接收者按包内 README 使用。

- [AI_Doll_Code_v2.7.0.zip](AI_Doll_Code_v2.7.0.zip)：78 个公开文件，0.73 MiB。
- [AI_Doll_PCB_V2_20261003.zip](AI_Doll_PCB_V2_20261003.zip)：58 个公开文件，9.94 MiB。

代码包包含当前源码、电脑事件桥、36 工具通用 MCP、MCP Events 适配、统一安装入口、已测试 v2.4 固件四个烧录文件、使用文档及接入指南。PCB 包包含最终嘉立创 EDA 工程、采购 BOM、原下单 Gerber 和检查证据。Bridge v2.7 增加已配对设备发现、旧 IP 恢复、单实例保护和可选登录启动；保留动作摘要、安静时段与自检；校准和日常模式需使用固件 v2.4；PCB 仍为八路模拟接口，实际温度探头与震动驱动需按指南接线。两者无需本机 `.tools` 或历史版本即可解压阅读；编译/运行依赖按代码包说明另行安装。

交付包不含本机 Wi-Fi 配置、设备访问密钥或个人互动数据库。完整文件校验值在各包的 `MANIFEST.json`；ZIP 校验值在 `DELIVERY_MANIFEST.json`。

`AI_Doll_Code_v2.7.0.zip` SHA-256：`bf79e6f35dbefd50a7a8b6f36d5011f8227511d4be6c5e064a892210c2883548`。

`AI_Doll_PCB_V2_20261003.zip` SHA-256：`a5d37184fc14a4857662e0527e9a14b890342e0ca9223a5b10322d01a1d79dcb`。

