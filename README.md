# AI 共感娃娃

让 AI 接收真实的触摸与按压，回应身体互动，并记录相处中的小动作。

**当前版本：v0.1.0 · 内测第一版**

[下载内测版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.0) · [使用教程](docs/README.md) · [更新说明](CHANGELOG.md) · [故障排查](docs/TROUBLESHOOTING.md)

## 能做什么

- **触摸回应**：将压力传感器的按压与释放送入聊天，支持连续互动排队。
- **部位与反馈设置**：设置端口状态、身体部位、回应语气与自定义提示词。
- **互动记录**：保存历史、按日期查询、统计与导出，支持断网缓存补传。
- **安卓独立使用**：Operit 可在家庭网络直连设备，不必常开电脑。
- **MCP 接入**：支持电脑 STDIO、HTTP、Secure MCP Tunnel，以及 Linux 服务器 MCP。
- **配对与恢复**：热点向导、连接文件／码／二维码，按设备身份找回变化的地址。

触摸主动回应默认关闭，可开启限时或常开。后台运行取决于聊天客户端和手机省电设置。

## 选择使用方式

| 场景 | 从这里开始 |
| --- | --- |
| 安卓手机 + Operit | [手机配置](docs/integrations/OPERIT_SETUP.md) · [没有电脑](docs/integrations/OPERIT_NO_PC.md) |
| Windows电脑 | [首次安装](docs/start/AI_INSTALL.md)，完整包自带Python |
| 自己的Linux服务器 | [远程快速部署](docs/integrations/REMOTE_SERVER_SETUP.md) |
| ChatGPT | [Secure MCP连接](docs/integrations/SECURE_MCP.md) |
| 其他AI应用 | [宿主接入](docs/integrations/HOST_INTEGRATIONS.md) |

## 下载哪个文件

所有文件从[内测第一版Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.0)下载。

| 文件 | 用途 |
| --- | --- |
| `AI_Doll_Code_v0.1.0.zip` | Windows完整包：管理、MCP、烧录与内置Python |
| `AI_Doll_Server_v0.1.0.tar.gz` | Linux接收服务、管理页与MCP |
| `AI_Doll_Operit.toolpkg` | Operit手机工具包 |
| `AI_Doll_PCB_v0.1.0.zip` | 当前主板工程、BOM、制造资料及紧凑板研发参考 |
| `AI_Doll_Enclosures_v0.1.0.zip` | 当前两种主板对应的外壳模型 |
| `AI_Doll_Stacked_Enclosure_v0.1.0.zip` | 已制板上下堆叠壳；包含P02加紧上盖 |

校验使用同一Release附带的`SHA256SUMS.txt`。GitHub“Download ZIP”是源码，不含Windows运行环境。

## 第一次使用

1. 空白开发板先[烧录固件](docs/start/QUICK_FLASH.md)。已有设备保留原配置，不要先恢复出厂。
2. 连接设备临时热点，打开`http://192.168.4.1/`，配置家庭2.4GHz Wi-Fi。
3. 按所选手机／电脑／服务器教程完成配对，确认设备在线。
4. 设置已安装的传感器部位，选择聊天，按需开启触摸主动回应。

设备正常重启不开配网热点；运行中长按BOOT约3秒可重新开窗。电脑管理中心为`http://127.0.0.1:8769/`，仅在运行软件的电脑打开。

## 硬件与外壳

[采购与主板资料](hardware/rev-v2/README.md) · [接线](docs/daily/SENSOR_CHANNELS.md) · [压力校准](docs/daily/CALIBRATION_AND_DAILY_MODE.md) · [外壳选择](hardware/enclosure/README.md)

已制板堆叠壳保持46.29 × 56.45 × 35.2 mm，使用103450电池仓。P02扩大、降低电源开关凹槽并加紧卡扣，已有底壳只需换上盖。

## 开发与维护

[开发和构建](docs/developers/DEVELOPER_GUIDE.md) · [工具目录](docs/developers/MCP_TOOLS.md) · [AI使用说明书](docs/ai/AI_GUIDE.md) · [项目结构](docs/developers/REPOSITORY_LAYOUT.md) · [当前检查记录](docs/reports/VALIDATION.md)

源码保留当前功能与必要测试；完整安装包放在Releases。个人配置、配对密钥、数据库、日志和本机生成素材不进入公开仓库。升级保留历史、校准和聊天绑定。

## 许可证

项目使用[MIT许可证](LICENSE)。随包第三方资源附带各自许可。
