# AI 共感娃娃

把娃娃的按压记录接入你正在使用的 AI 聊天。继续使用原模型和人设，可以查询互动历史，也可以开始限时互动。

**2.20.0 预发布版 · ESP32-C3 固件 2.9.0**。Windows 完整包自带运行环境，无需安装 Python 或 Arduino。[下载本版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.20.0)。新增免电脑模式仍需在自己的手机与网络实测。

## 第一次使用，只做这几步

1. 从 [下载入口](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)取得 **Windows 完整包**并完整解压。
2. 开发板还没装程序：接 USB 数据线，双击 **Flash_ESP32.cmd**，点击 **一键烧录**。看见成功后进入下一步。[图文步骤](docs/start/QUICK_FLASH.md)
3. 手机连接烧录成功页显示的 **AI-Doll-…** 热点，打开 **http://192.168.4.1/**，选择家庭的 2.4 GHz Wi-Fi 并保存。[配网步骤](docs/daily/WIFI_CONNECTION.md)
4. 双击 **AI_Doll.cmd**，按 [首次安装](docs/start/AI_INSTALL.md)连接你的原 AI 聊天。

**配网成功后，娃娃热点和 192.168.4.1 设置页仍保留。** 每次要修改设置，连接娃娃热点即可。这个地址在家庭 Wi-Fi 下不是娃娃的固定局域网 IP。

## 三个入口，各做一件事

| 双击哪个文件 | 用来做什么 | 这台电脑上的地址 |
| --- | --- | --- |
| Flash_ESP32.cmd | USB 烧录，保存日志并生成新设备名称 | http://127.0.0.1:8770/ |
| AI_Doll.cmd | 管理娃娃、保存历史、接入原 AI | http://127.0.0.1:8769/ |
| AI_Doll_Server.cmd | 给自建应用启动本机接收服务 | 以启动页面显示为准 |

自己有 Linux 服务器、希望电脑不用常开时，用 [远程部署教程](docs/integrations/REMOTE_SERVER_SETUP.md)。不确定选哪条路线，先看 [连接方式选择](docs/start/MCP_TRANSPORT_DECISION.md)。

**Operit 用户无需电脑也能使用**：可让设备直传自己的服务器，或由安卓手机在家庭 Wi-Fi 内直接读取设备。两种方式使用同一个手机工具包，继续原聊天。见 [免电脑使用指南](docs/integrations/OPERIT_NO_PC.md)。

## 烧录和首次启动

每次 USB 烧录产生新设备后缀，并在 `build/flash/日期时间-编号/` 保存日志与结果；日常重启保持名称。标准烧录保留已有配置，明确选择“恢复出厂”才清空设备。新板默认未配网、手动模式、真实输入和电机输出关闭。[默认设置说明](docs/start/FACTORY_SETTINGS.md)

## 接好传感器后

只启用已安装的通道，确认读数随按压变化，再做 [压力校准](docs/daily/CALIBRATION_AND_DAILY_MODE.md)。日常模式可在重启后恢复输入，电机输出不会自动恢复。

已实测 CH0 实体 FSR 的按压、释放和本机历史保存。其他通道、温度探头、电机及整机电池仍需分别验收；限时互动不等于 AI 空闲时自动唤醒。[当前验证范围](docs/reports/VALIDATION.md)

## 完整目录

[新手与日常教程](docs/README.md) · [故障排查](docs/TROUBLESHOOTING.md) · [给 AI 的执行指南](docs/ai/AI_GUIDE.md) · [AI 维护入口](AGENTS.md) · [开发与打包](docs/developers/DEVELOPER_GUIDE.md) · [硬件与 BOM](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md)

电脑模式需要电脑采集服务运行，直传模式需要接收服务器运行，手机直连模式需要 Operit 在设备所在家庭网络运行。查询云端 AI 时，所查询的记录会提供给该平台。个人配置与历史保存在各自电脑、服务器或手机，不随公共包发布。

原创代码与文档使用 [MIT License](LICENSE)。第三方依赖的许可随完整包保留。

Operit 手机接入：[下载独立工具包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.20.0/AI_Doll_Operit.toolpkg)，按环境选择电脑、服务器或仅安卓手机，按标题绑定原聊天。[操作指南](docs/integrations/OPERIT_SETUP.md) · [免电脑指南](docs/integrations/OPERIT_NO_PC.md) · [2.20 验证边界](docs/reports/RELEASE_2_20.md)。
