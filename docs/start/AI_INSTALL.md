# Windows 首次安装与 AI 接入

Windows 电脑采集并保存触摸记录，通过 MCP 提供给聊天客户端。安装分为启动、连接设备、接入 AI 三步。[教程目录](../README.md)

本页对应 **v0.1.2 内测版**。需要仅用安卓手机或自己部署服务时，分别查看 [Operit 直连](../integrations/OPERIT_NO_PC.md) 与 [Linux 部署](../integrations/REMOTE_SERVER_SETUP.md)。

## 准备好这三样

- 一台 Windows 64 位电脑，能联网。
- 已烧录并供电的娃娃；空白开发板先按 [一键烧录](QUICK_FLASH.md)。
- [Windows完整包](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v0.1.2/AI_Doll_Code_v0.1.2.zip)，按本版Release的`SHA256SUMS.txt`校验后完整解压，保留 `python/`、`src/`、`tools/`、`clients/`、`delivery/`。GitHub 的“Download ZIP”是源码，不能替代自带运行环境的完整包。

## 第一步：打开管理中心

在解压后的目录中双击 **AI_Doll.cmd**。浏览器会打开本机管理中心 `http://127.0.0.1:8769/`。完整包自带 Python。

如果没有打开，在这台电脑浏览器手动输入该地址；仍打不开时看 [故障排查](../TROUBLESHOOTING.md)。

## 第二步：连接娃娃

先用 USB 数据线连接开发板。在“设备连接”选择 **USB** 和当前串口，再保存。串口拿不准时，观察插入开发板后新增的 COM 项。看到设备 ID、在线状态和新的同步时间后再继续。

想改用无线时，先给娃娃配家庭 Wi-Fi，再在管理中心点“一键识别并配对 Wi-Fi”。确认连接方式切换为 Wi-Fi 且同步时间更新后，可拔掉数据线并给娃娃独立供电。[配网与无线配对](../daily/WIFI_CONNECTION.md)

“配网”让娃娃连上路由器；“配对”让电脑认出你的娃娃。两步都完成，电脑才可无线读取。

## 第三步：连接你的 AI

| 你使用什么 | 接下来做什么 |
| --- | --- |
| ChatGPT | 按 [ChatGPT 连接教程](../integrations/SECURE_MCP.md)创建并保存隧道 |
| 支持本地 MCP 的客户端 | 在“AI / MCP 连接”复制本机配置，合并到客户端原设置 |
| 自己开发的聊天应用 | 用 [本机接收服务](../integrations/SERVER_QUICKSTART.md)；接口在开发者区 |

MCP 就是 AI 读取娃娃的工具接口。配置保存在 `build/device-lab/mcp-client-config.json`，里面使用本安装目录的完整路径。移动软件后要重新生成。

## 第四步：确认聊天连接

在已经添加连接的原聊天发这句话：

> 请调用 get_installation_status 和 doll_get_status，按本次结果告诉我设备 ID 和连接状态。

核对设备 ID 与管理中心一致，再按[聊天测试](../integrations/CHAT_MCP.md)查询历史、体验限时互动。

## 安装完成后每天怎么用

给娃娃供电，双击 **AI_Doll.cmd**，在原聊天里问“查询今天的互动”。关闭管理页面后，后台采集仍继续；要停止，到“维护与诊断”选择停止服务。

只有实体传感器接好后才把对应端口设为“已接入”，再做 [压力校准](../daily/CALIBRATION_AND_DAILY_MODE.md)。全新固件默认 CH0 已接入；未安装时先关闭。没接传感器也可按 [独立模拟分支](../integrations/CHAT_MCP.md#可选没有传感器时做模拟测试)测试。

日常操作和页面位置见 [日常指南](../daily/USER_GUIDE.md)。给 AI 代办时，交给它独立的 [AI 执行指南](../ai/AI_GUIDE.md)。
