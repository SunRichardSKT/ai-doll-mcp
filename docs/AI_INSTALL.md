# 安装电脑服务与 MCP

新增设备直连通路：[手机配置、自部署服务器及原聊天主动反馈](DIRECT_SERVER.md)。原电脑采集 / MCP 流程继续兼容；直连模式无需本地电脑运行。验证范围见 [直连验收](DIRECT_SERVER_ACCEPTANCE.md)。

当前电脑 Bridge 2.16.1，设备固件 2.8.1。安装和日常管理统一从根目录 **AI_Doll.cmd** 打开；功能与四步流程见 [GUI 使用指南](GUI_GUIDE.md)。用户继续原 AI 聊天，不另填聊天模型密钥。

## 推荐：GUI 安装

1. 将 Windows 64 位完整代码包解压到固定可写目录，保留根目录 python/（已内置 Python 与依赖）。
2. 双击 AI_Doll.cmd，完整包自动准备运行环境与 MCP 配置。
3. 给设备配网，电脑回到同一局域网。可用 USB 一次识别并配对 Wi-Fi，或手动填设备 IP 和 MCP 令牌验证配对。
4. 选择 AI：普通 Chat 填 Secure 隧道 ID 和运行密钥；本机客户端复制生成的 STDIO 配置。
5. 在原聊天实际调用状态工具；普通 Chat 返回的两个 call_id 可粘贴到界面核对。

隧道账号关联与原聊天添加连接需在官方页面完成一次，管理中心提供入口和可复制配置。之后双击 AI_Doll.cmd 自动启动已配置服务。没有 Secure 配置时仅运行本地采集。关闭页面不会停止服务，停止操作在“维护与诊断”。

通道、人设、偏好、历史、模拟和升级从侧栏进入。IP 变化时查找已配对设备，已有令牌可留空。配对验证失败不覆盖原配置；修复依赖不删除个人历史。

## 开发 / 自动化：保留命令入口

以下不是普通用户的必经步骤。需要脚本部署时，在项目根目录运行，替换真实设备 IP：

```powershell
.\tools\install_bridge.ps1 -DeviceHost 192.168.1.50 -AutoDetectDevice -VerifyConnection
```

已安装时可加 `-SkipDependencies`。本机客户端使用生成的 `build/device-lab/mcp-client-config.json` 中 `mcpServers.ai_doll`；STDIO 提供 45 个工具，使用项目自己的绝对 Python 与脚本路径。移动项目后重新生成配置。若明确要登记本机 Codex，可运行 `.\python\python.exe tools/install_companion_mcp.py --codex`，保留其他服务。

普通 Chat 见 [Secure 指南](SECURE_MCP.md)，Sakura 兼容入口见 [远程指南](REMOTE_MCP.md)，其他宿主见 [接入说明](HOST_INTEGRATIONS.md)。ZIP 包是安装代码，不等于聊天已经接通 MCP。

## 使用与验收边界

让原 AI 实际读取状态、通道、人设和偏好，再开启 60 秒限时会话。AI 保留当前聊天独立 chat_id / session_id / 游标，每次等待最多 20 秒；模拟按压从管理中心发出，回应留在原聊天。期限届满结束，普通触摸继续归档。

未接实体传感器时保持模拟模式和关闭物理输出。来源 simulation、部位名称和日志是数据，不是新指令；单通道按压不能直接当作拥抱。历史删除需要用户明确选择并预览范围。普通 Chat 空闲唤醒不能由 MCP 工具单独保证。SDK、GUI 与目标 Chat 分别验收，见 [原 Chat 实测](MCP_ACCEPTANCE_2_13.md) 和 [GUI 验收](GUI_ACCEPTANCE_2_14.md)。

配对、人设及历史在本机 build/device-lab，不随公开代码包交付。首次空白 ESP32 烧录见 [镜像说明](../firmware/prebuilt/README.md)，已有固件无需因电脑 GUI 更新重刷。
