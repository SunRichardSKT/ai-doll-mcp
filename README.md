# AI 共感娃娃

让现实中的触摸成为 AI 聊天的上下文。ESP32-C3 采集传感器，电脑通过局域网保存互动历史，用户选择的 AI 通过 MCP 查询或在支持事件的应用中响应。

用户继续在原来的 AI 对话中聊天，娃娃增加身体互动输入，沿用当前模型、人设和上下文。使用流程见 [接入现有对话](docs/EXISTING_CHAT.md)。

当前交付：**固件 2.7.0 / 电脑 Bridge 2.13.0**。电脑 MCP 提供 45 个工具，设备 MCP 提供 26 个工具。硬件为 ESP32-C3 SuperMini、74HC4051 和八路外置 FSR402；保持现有电阻、电容和手焊封装。

## 从这里开始

1. [首次安装与 AI 接入](docs/AI_INSTALL.md)：安装电脑服务、配对设备、生成 MCP 配置。
2. [使用指南](docs/USER_GUIDE.md)：首次配网、按钮、日常操作和一次完整互动测试。
3. [FSR 校准](docs/CALIBRATION_AND_DAILY_MODE.md)：八路分别校准、推荐阈值与手动设置。
4. [主动互动接入](docs/PROACTIVE_INTERACTION.md)：自建聊天应用、事件订阅和反馈目标绑定。
5. [普通 Chat 与 Secure MCP Tunnel](docs/SECURE_MCP.md)：首次配置、日常双击启动、真实工具核对；[Sakura 入口](docs/REMOTE_MCP.md)继续保留。
6. [交付文件](delivery/README.md)：当前代码、固件、嘉立创 EDA 工程和校验值。
7. [Operit / OpenClaw / 自定义前端](docs/HOST_INTEGRATIONS.md)：兼容评估、包模板和原聊天事件转发脚本；这两个平台本轮不做实际验收。

普通 Chat 的长期接入选择见 [Cloudflare 与 Secure MCP Tunnel 评估](docs/MCP_TRANSPORT_DECISION.md)。当前 Secure 已提供 13 个工具并通过普通 Chat 状态调用、历史查询和 60 秒模拟按压反馈；实际调用编号与审计记录已匹配。Cloudflare 的两工具连接作为备用保留。

设备独立供电后，通过 Wi-Fi 传输数据，不必连接电脑 USB。电脑服务需要运行；设备在断线期间最多缓存 256 条事件，恢复后补传。默认普通模式只记录，不自动回复；用户开始互动后才向绑定的聊天目标投递新事件。

## 功能

- 八路压力独立阈值、静置/轻按/用力按校准、推荐阈值、实时诊断曲线。
- 无密码配网热点、Wi-Fi 扫描选择、60 秒连接恢复和 BOOT 长按重新配网。
- 最多 16 个逻辑通道，自定义部位；支持 FSR 压力、NTC 温度、DS18B20 数字温度和板外驱动的震动输出。
- 历史查询、JSON/CSV 导出、统计、删除预览、可选保留期限。
- 用户人设、反馈偏好、安静时段、互动会话、动作摘要、SSE 和 MCP Events 适配。
- 本机 Streamable HTTP 三种配置；远程私密地址、Sakura 官方客户端下载校验、一键启动/停止、退避重连和地址重置。可复用已登录的 Sakura 客户端，项目无需其访问密钥；该通路已通过可信 HTTPS 和 13 工具 SDK 验证。Sakura 的普通 Chat 添加仍未通过，见 [分阶段验收](docs/MCP_ACCEPTANCE_2_13.md)。
- Secure MCP Tunnel 官方客户端自动下载校验、独立后台运行目录、本机配置窗口、启动/状态/停止及本地地址重置；沿用电脑当前出站代理，不公开设置页和数据库。
- 设备发现、地址恢复、可选 Windows 登录启动、带校验和启动回滚的无线升级。

真实传感器接好后才开启采样；日常模式可以恢复输入，震动输出不会自动恢复。未接传感器也能测试模拟链路，所有模拟数据明确标记来源。

MCP 统一提供工具接口，但聊天客户端是否接受后台事件由它自身决定。自建 API 应用可以接入事件并在当前聊天显示模型回复；官方网页聊天需要实际支持的连接和事件机制。GitHub 地址用于阅读代码，不能当成 MCP 服务地址。详见 [聊天窗口指南](docs/CHAT_MCP.md)。

## 编译

在项目根目录运行，推荐 Python 3.12：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-companion.txt
.\.venv\Scripts\python.exe -m pip install platformio
.\tools\build_lab.ps1
```

USB 烧录：先关闭串口监视器和使用 USB 的采集服务，再执行 `.\tools\build_lab.ps1 -Upload -Port COM3`，替换实际串口。当前唯一编译目标为 `supermini-lab`。已验证镜像及地址见 [固件说明](firmware/prebuilt/README.md)。日常无线升级见 [OTA 指南](docs/OTA_UPDATE.md)。

## 目录

| 目录 | 内容 |
|---|---|
| `firmware/src` | 固件、设备网页及传感器驱动 |
| `firmware/prebuilt` | 已验证镜像、分区表、引导文件和清单 |
| `tools` | 电脑采集、MCP、事件桥、安装和验证工具 |
| `docs` | 当前使用及开发文档 |
| `hardware/rev-v2` | 嘉立创 EDA 工程、BOM、已下单文件与核对证据 |
| `delivery` | 当前代码包、PCB 包和校验清单 |

`build` 保存本机配对、运行记录和验证证据，不交付；`.tools` 与 `.venv` 为本机依赖。旧备份、废弃独立聊天代码和 OAuth 实验已清理，回归测试保留用于验证当前功能。打包运行 `python tools/package_companion.py`。PCB 两层、34.29 × 44.45 mm，原生 PCB DRC 为 0；C13/C14 为 1206，其余阻容以 0805 为主。

软件与裸板验证范围见 [测试报告](docs/DEVICE_LAB_TEST_REPORT.md)。实际 FSR、温度探头、电机仍需接线验收；普通 Chat 的模拟文字反馈已通过，Operit、OpenClaw 和空闲主动唤醒未实测。

本项目原创代码与文档按 [MIT License](LICENSE) 开源。第三方依赖、官方客户端和器件数据手册遵循其各自许可；交付不包含第三方客户端二进制，安装器从官方来源下载并校验。
