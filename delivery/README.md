# AI 共感娃娃交付说明

更新日期：2026-10-11。电脑 Bridge v2.16.0 支持 Wi-Fi 采集，已测试开发板固件为 v2.8.1。请直接发送下面的 ZIP 包；接收者按包内 README 使用。

- [AI_Doll_Code_v2.16.0.zip](AI_Doll_Code_v2.16.0.zip)：2470 个公开文件，28.62 MiB。
- [AI_Doll_PCB_V2_20261003.zip](AI_Doll_PCB_V2_20261003.zip)：58 个公开文件，9.94 MiB。

代码包新增设备直连服务器、手机配置、原前端事件适配和 HTTPS 部署模板，详见 docs/DIRECT_SERVER.md。代码包包含当前固件四个烧录文件、源码、45 工具 MCP、电脑事件桥、安装工具和当前使用文档。支持八路 FSR 校准、首次配网、Wi-Fi 数据、温度/震动扩展、有限离线缓存、历史管理与无线升级。PCB 包包含嘉立创 EDA 工程、BOM、原下单文件和核对证据。Windows 运行环境随代码包提供；仅固件源码编译工具需要另行安装。普通 Chat 的状态、历史和 60 秒模拟反馈已通过；实物传感器与其他宿主的真实反馈仍待验收。

交付包不含本机 Wi-Fi 配置、设备访问密钥或个人互动数据库。完整文件校验值在各包的 `MANIFEST.json`；ZIP 校验值在 `DELIVERY_MANIFEST.json`。

`AI_Doll_Code_v2.16.0.zip` SHA-256：`8885d9678e118cb8b9efbbaa7545053993b18134e95c97507cd64eeed11c27dc`。

`AI_Doll_PCB_V2_20261003.zip` SHA-256：`a5d37184fc14a4857662e0527e9a14b890342e0ca9223a5b10322d01a1d79dcb`。

