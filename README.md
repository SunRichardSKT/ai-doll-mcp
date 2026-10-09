# AI 共感娃娃

让现实中的触摸成为 AI 聊天的上下文。ESP32-C3 采集传感器，电脑通过局域网保存互动历史，用户选择的 AI 通过 MCP 查询或在支持事件的应用中响应。

当前交付：**固件 2.7.0 / 电脑 Bridge 2.11.0**。电脑 MCP 提供 45 个工具，设备 MCP 提供 26 个工具。硬件为 ESP32-C3 SuperMini、74HC4051 和八路外置 FSR402；保持现有电阻、电容和手焊封装。

## 从这里开始

1. [首次安装与 AI 接入](docs/AI_INSTALL.md)：安装电脑服务、配对设备、生成 MCP 配置。
2. [使用指南](docs/USER_GUIDE.md)：首次配网、按钮、日常操作和一次完整互动测试。
3. [FSR 校准](docs/CALIBRATION_AND_DAILY_MODE.md)：八路分别校准、推荐阈值与手动设置。
4. [主动互动接入](docs/PROACTIVE_INTERACTION.md)：自建聊天应用、事件订阅和反馈目标绑定。
5. [交付文件](delivery/README.md)：当前代码、固件、嘉立创 EDA 工程和校验值。

设备独立供电后，通过 Wi-Fi 传输数据，不必连接电脑 USB。电脑服务需要运行；设备在断线期间最多缓存 256 条事件，恢复后补传。默认普通模式只记录，不自动回复；用户开始互动后才向绑定的聊天目标投递新事件。

## 功能

- 八路压力独立阈值、静置/轻按/用力按校准、推荐阈值、实时诊断曲线。
- 无密码配网热点、Wi-Fi 扫描选择、60 秒连接恢复和 BOOT 长按重新配网。
- 最多 16 个逻辑通道，自定义部位；支持 FSR 压力、NTC 温度、DS18B20 数字温度和板外驱动的震动输出。
- 历史查询、JSON/CSV 导出、统计、删除预览、可选保留期限。
- 用户人设、反馈偏好、安静时段、互动会话、动作摘要、SSE 和 MCP Events 适配。
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

`build` 保存本机配对、日志和验证记录，不交付；`.tools` 为本机依赖，`_local` 为非交付归档。打包运行 `python tools/package_companion.py`。PCB 两层、34.29 × 44.45 mm，原生 PCB DRC 为 0；C13/C14 为 1206，其余阻容以 0805 为主。

软件与裸板验证范围见 [测试报告](docs/DEVICE_LAB_TEST_REPORT.md)。实际 FSR、温度探头、电机和用户模型的完整反馈仍需接线与应用验收。
