# 第一次使用：把娃娃接入原来的 AI 聊天

> 按本页步骤操作即可；无需读完开发者资料。 [全部目录](../README.md)


这条路线适合 Windows 用户。完成后仍在原 AI 聊天中提问，电脑负责保存娃娃的记录。远程服务器用户直接读 [远程部署](../integrations/REMOTE_SERVER_SETUP.md)。

本页按 **2.25.0 本地候选**说明；使用本机 `delivery/` 的配套文件，本版尚未上传 GitHub Release。电脑／服务器与 Operit 手机包一起升级；新固件 2.13.1 的归档租约需另行核对实际开发板能力。

公开已发布的最新预发布仍为[2.24.1](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.24.1)，其操作说明在[固定版本教程](https://github.com/SunRichardSKT/ai-doll-mcp/blob/v2.24.1/docs/start/AI_INSTALL.md)。仍选择 2.21 稳定版时，使用[稳定版校正版入口](STABLE_2_21.md)和同一 Release 的校验文件。

## 准备好这三样

- 一台 Windows 64 位电脑，能联网。
- 已烧录并供电的娃娃；空白开发板先按 [一键烧录](QUICK_FLASH.md)。
- 本地候选 `delivery/AI_Doll_Code_v2.25.0.zip`，按同目录 `SHA256SUMS.txt` 校验后完整解压，保留 `python/`、`src/`、`tools/`、`clients/`、`delivery/`。GitHub 的“Download ZIP”是源码，不能替代自带运行环境的完整包；没有本地候选时使用上述已发布版本和固定教程。

## 第一步：打开管理中心

双击 **AI_Doll.cmd**，浏览器打开 `http://127.0.0.1:8769/`。完整包自带运行环境，不用另装 Python。

如果没有打开，在这台电脑浏览器手动输入该地址；仍打不开时看 [故障排查](../TROUBLESHOOTING.md)。

## 第二步：连接娃娃

先用 USB 数据线连接开发板。在“设备连接”选 **USB**、填写当前串口并保存，确认出现实际设备 ID。只有一块板时，从列表找到新增的 COM 项。

想拔掉 USB 数据线使用，再按 [配网与无线配对](../daily/WIFI_CONNECTION.md)：先给设备配家庭 Wi-Fi，再点击“一键识别并配对 Wi-Fi”。配对成功后保持独立供电。

“配网”让娃娃连上路由器；“配对”让电脑认出你的娃娃。两步都完成，电脑才可无线读取。

## 第三步：连接你的 AI

| 你使用什么 | 接下来做什么 |
| --- | --- |
| ChatGPT | 按 [ChatGPT 连接教程](../integrations/SECURE_MCP.md)创建并保存隧道 |
| 支持本地 MCP 的客户端 | 在“AI / MCP 连接”复制本机配置，合并到客户端原设置 |
| 自己开发的聊天应用 | 用 [本机接收服务](../integrations/SERVER_QUICKSTART.md)；接口在开发者区 |

MCP 就是 AI 读取娃娃的工具接口。配置保存在 `build/device-lab/mcp-client-config.json`，里面使用本安装目录的完整路径。移动软件后要重新生成。

## 第四步：让 AI 真正调用一次

在已经添加连接的原聊天发这句话：

> 请实际调用 get_installation_status 和 doll_get_status，告诉我设备 ID 和当前连接状态。没有工具就说明没有工具，不要用文档或旧结果代替。

设备 ID 应与管理中心一致。工具连接成功后，按 [聊天测试](../integrations/CHAT_MCP.md)查一次历史和试一次限时互动。上传说明 ZIP 并不等于连接了运行中的服务。

## 安装完成后每天怎么用

给娃娃供电，双击 **AI_Doll.cmd**，在原聊天里问“查询今天的互动”。关闭管理页面后，后台采集仍继续；要停止，到“维护与诊断”选择停止服务。

只有实体传感器接好后才把对应端口设为“已接入”，再做 [压力校准](../daily/CALIBRATION_AND_DAILY_MODE.md)。全新固件默认 CH0 已接入；未安装时先关闭。没接传感器也可按 [独立模拟分支](../integrations/CHAT_MCP.md#可选没有传感器时做模拟测试)测试。

日常操作和页面位置见 [日常指南](../daily/USER_GUIDE.md)。给 AI 代办时，交给它独立的 [AI 执行指南](../ai/AI_GUIDE.md)。
