# AI 共感娃娃

让娃娃的触摸记录进入你正在使用的 AI 对话。你可以问“今天有哪些互动”，也可以开启限时互动，让原聊天中的 AI 根据新动作回应。继续使用原模型、人设和上下文。

当前版本：**软件 2.16.2 · ESP32 固件 2.8.1**。Windows 完整包自带 Python，无需另装运行环境。没有传感器也能进行模拟测试。

## 第一次使用，从这里选

| 你想怎么用 | 下载什么 | 第一步 |
| --- | --- | --- |
| 在 ChatGPT 普通 Chat 或本机 MCP 客户端里使用 | Windows 完整软件包 | 解压后双击 `AI_Doll.cmd`，按 [首次安装](docs/AI_INSTALL.md)操作 |
| 让自己的聊天应用接收娃娃事件，先在电脑测试 | Windows 完整软件包 | 双击 `AI_Doll_Server.cmd`，按 [本机接收服务](docs/SERVER_QUICKSTART.md)操作 |
| 部署到自己的 Linux 服务器，电脑不用常开 | 小型 Linux 服务包或安装脚本 | 按 [远程快捷部署](docs/REMOTE_SERVER_SETUP.md)填写域名 |

[下载与交付文件](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md) · [全部文档](docs/README.md) · [给 AI 的安装与验证指南](docs/AI_GUIDE.md)

## 安装完成后怎么用

1. 给娃娃配好 2.4 GHz Wi-Fi，设置每路传感器的部位。
2. 将 MCP 接入原聊天，实际调用状态工具确认连通。
3. 平时触摸只记录；询问“查询今天的互动”时，AI 读取历史并回应。
4. 说“开始 60 秒互动测试”，然后模拟按压。AI 在这次会话中读取新动作，并结合原对话回应。

日常操作见 [使用指南](docs/USER_GUIDE.md)，遇到问题看 [故障排查](docs/TROUBLESHOOTING.md)。MCP 是让 AI 调用工具的接口，不会自行生成回复。

## 当前哪些已经验证

- **ChatGPT 普通 Chat + Secure MCP Tunnel**：状态查询、历史查询、60 秒模拟按压文字反馈，以及服务重启后的连接。
- **设备直传服务**：真实 ESP32 通过 Wi-Fi / TLS 上传模拟事件、保存历史，并触发原自定义聊天的测试回调。
- **硬件文件**：双层 PCB，34.29 × 44.45 mm；保存重载后原生 PCB DRC 为 0。保留 SuperMini、74HC4051 和手焊方案。

真实 FSR、温度探头和电机尚未接线验收；普通 Chat 空闲主动唤醒未验证。Sakura 的 SDK 调用通过，普通 Chat 添加仍失败。模拟读数不代表实体传感器测量，测试回调不代表真实模型生成。详见 [验证汇总](docs/VALIDATION.md)。

## 需要保持什么运行

电脑 MCP 模式需要电脑及采集服务运行，设备可独立供电，不必一直连接 USB。直传模式需要接收服务器运行；设备主动上传，家中无需端口映射。两条通路分别保存历史，不要同时消费同一设备的缓存。

查询云端 AI 时，所查询的记录会发送给该平台。设备设置页默认免登录，可按需开启保护；配对令牌和隧道运行密钥用途见 [运行环境与登录](docs/RUNTIME_AND_LOGIN.md)。

## 硬件与开发

[PCB 工程、BOM 与装配核对](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/hardware/rev-v2) · [通道与接线](docs/SENSOR_CHANNELS.md) · [开发指南](docs/DEVELOPER_GUIDE.md) · [后续工作](docs/DEVELOPMENT_PLAN.md)

原创代码与文档使用 [MIT License](LICENSE)。第三方依赖、客户端和资料保留各自许可。
