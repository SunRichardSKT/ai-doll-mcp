# 第一次使用：把娃娃接入原来的 AI 聊天

> 按本页步骤操作即可；无需读完开发者资料。 [全部目录](../README.md)


这条路线适合 Windows 用户。完成后仍在原 AI 聊天中提问，电脑负责保存娃娃的记录。远程服务器用户直接读 [远程部署](../integrations/REMOTE_SERVER_SETUP.md)。

## 准备好这三样

- 一台 Windows 64 位电脑，能联网。
- 已烧录并供电的娃娃；空白开发板先按 [一键烧录](QUICK_FLASH.md)。
- [Windows 完整软件包](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)，完整解压。GitHub 的“Download ZIP”是源码，普通用户应下载完整交付包。

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

实体传感器接好后才启用真实输入，并做 [压力校准](../daily/CALIBRATION_AND_DAILY_MODE.md)。没接传感器也可以使用模拟测试。

日常操作和页面位置见 [日常指南](../daily/USER_GUIDE.md)。给 AI 代办时，交给它独立的 [AI 执行指南](../ai/AI_GUIDE.md)。
