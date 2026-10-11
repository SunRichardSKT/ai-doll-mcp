# Windows 首次安装

这份指南给使用者看。想让 AI 帮你安装，请交给它 [AI 执行指南](AI_GUIDE.md)。远程 Linux 部署请直接读 [远程快捷部署](REMOTE_SERVER_SETUP.md)。

## 1. 下载并完整解压

从 [交付目录](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)下载 `AI_Doll_Code_v2.16.2.zip`，解压到固定、可写的目录。保留根目录的 `python/` 和 `tools/`。

这是 Windows 64 位完整包，已内置 Python 和依赖。GitHub 的源码 ZIP 不含完整运行环境，普通用户应选交付软件包。

## 2. 打开管理中心

双击根目录 **AI_Doll.cmd**。浏览器会打开 `http://127.0.0.1:8769/`，自动检查环境并生成本机配置。

管理中心只负责设备设置；AI 回复仍留在你的原聊天。启动失败时先看 [故障排查](TROUBLESHOOTING.md)，不必先重刷固件。

## 3. 给娃娃配网并配对

1. 按 [配网步骤](USER_GUIDE.md#首次配网)连接 2.4 GHz Wi-Fi，让电脑和设备处于可互通的局域网。
2. 已配网设备可用 USB 接电脑，在“设备连接”填写实际串口，点击 **一键识别并配对 Wi-Fi**。
3. 配对通过后可拔掉 USB 数据连接，改用独立供电。

也可在设备页启用 MCP，填写设备 IP 与 MCP 令牌，点击 **验证并保存配对**。验证失败不会覆盖原配对。未接传感器时保持模拟模式，真实输入和物理输出关闭。

## 4. 接入你的原聊天

| 客户端 | 如何连接 |
| --- | --- |
| ChatGPT 普通 Chat | 按 [Secure 配置](SECURE_MCP.md)，在原聊天添加自定义 MCP 隧道 |
| 支持本地 MCP 的客户端 | 复制生成的 `mcpServers.ai_doll` 到客户端设置，保留其他服务 |
| 自己开发的聊天应用 | 看 [原聊天接入](EXISTING_CHAT.md)；设备直接上传可选 [本机服务](SERVER_QUICKSTART.md) |

本机客户端配置保存在 `build/device-lab/mcp-client-config.json`，使用本安装的绝对路径。移动软件目录后需重新生成，不能复制别人的配置直接使用。

## 5. 实际验证

在已经添加连接的原聊天发送：

> 请实际调用 get_installation_status 和 doll_get_status，返回真实设备状态；有 verification.call_id 时返回两个调用编号。没有工具请如实说明。

确认后按 [聊天测试步骤](CHAT_MCP.md)查询历史、进行 60 秒模拟互动。上传插件 ZIP、工具发现成功或本机检查成功，都不能代替原聊天的实际调用。

第一次安装完成后，日常只需给娃娃供电、双击 `AI_Doll.cmd`。关闭浏览器不停止后台服务；停止操作在“维护与诊断”。全部操作见 [管理中心指南](GUI_GUIDE.md)。
