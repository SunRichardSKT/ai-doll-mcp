# 给开发板烧录固件

准备 ESP32-C3 SuperMini、USB 数据线和 Windows 64 位电脑。完整包自带运行环境与预编译固件。[教程目录](../README.md)

## 1. 下载并解压

从 [v0.1.4 Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.4) 下载 **Windows 完整包**，完整解压到固定目录，再打开其中的启动文件。

## 2. 接线并打开烧录页面

用 USB 数据线连接开发板，双击根目录 **Flash_ESP32.cmd**。浏览器自动打开电脑上的 `http://127.0.0.1:8770/`。

看到“已找到开发板”后，选择固件来源，保留“标准烧录”，选择名称后点击 **一键烧录**。只有一块开发板时，不用填写串口。

| 固件来源 | 怎么选 |
| --- | --- |
| 随包固件 | 默认选项，无需下载。 |
| 选择本地固件 | 选择项目固件 ZIP 或 Windows 完整包 ZIP；也可一次选中 `FLASH_MANIFEST.json`、`bootloader.bin`、`partitions.bin`、`boot_app0.bin` 和 `firmware.bin` 五个文件。 |
| GitHub 最新正式版 | 点击“查询最新版本”，核对版本后点击“下载并选用”。查询公开 Release，无需填写 GitHub 账号或令牌。 |

选定固件并校验通过后，点击“一键烧录”开始写入。USB 烧录使用完整固件 ZIP 或表中的五个文件；单独的 `firmware.bin` 用于配套 OTA 流程。在线下载失败可改选本地包。最新正式版读取 GitHub `releases/latest`。

设备名称默认自动生成，也可以选择 **自定义名称**，例如“小樱”。这个名字同时用作设备显示名和配网热点名，最多 32 个 UTF-8 字节（中文通常每字 3 字节）。重新烧录时选择随机名称，会恢复为本次自动生成的名称。

如果连接了多块板，先在“开发板连接”选择对应串口；不知道是哪块时，拔掉再插回，观察新增的那一项。

## 3. 等待成功

页面依次检查连接、写入程序、校验、启动和新设备编号。看到 **“烧录成功，设备已启动”** 才算完成。过程中保持 USB 连接。

成功后会回读设备名称、热点名和内部编号。每次 USB 烧录都会生成新的内部配对编号，例如 `AI-Doll-` 后跟 20 位编号；自定义名称不替代这个编号。名称与编号保存到板内，日常断电、重启不会改变；原 AI 配对可能需要更新。

## 4. 找到设备设置页

手机连接成功页显示的 Wi-Fi 热点（自定义名称或 `AI-Doll-…`），打开 **http://192.168.4.1/setup**。首次热点最长 10 分钟，新配网成功后约 90 秒关闭。标准升级保留家庭 Wi-Fi 时，设备直接连接家庭网络；需要热点时，在运行中长按 BOOT 约 3 秒再松开，保持 RST 不动。

手机提示“没有互联网”时，选择继续连接。这个热点用来设置娃娃；电脑的烧录页面和娃娃设置页面是两个地址。切回家庭 Wi-Fi 后，从已配对的 Operit 或电脑管理中心打开设备设置，不再使用 `192.168.4.1`。

## 自动连接失败怎么办

1. 关闭占用串口的其他烧录工具或串口监视器。
2. 按住开发板 **BOOT** 不松开，点按并松开 **RST**，最后松开 BOOT。
3. 回到页面点击刷新，重新选择串口，再点击烧录。
4. 如果写入完成但一直等启动，松开 BOOT，**只点按一次 RST**。

默认使用115200速度，减少USB串口切换高速时的连接问题。命令行可通过`--baud`自行选择更高速度；出现“Cannot configure port”或串口消失时先使用默认速度，待USB重新识别后刷新串口。

本项目自己的 USB 采集服务会暂时停止并在烧录后恢复；活跃互动会话不会被强行中断。失败不会自动连续擦写。

## 日志与出厂设置

每次尝试都有独立目录 `build/flash/日期时间-独立编号/`，保存 `flash.log` 和 `result.json`，失败也保留。页面可展开“查看本次烧录日志”。

遇到 `result.tmp → result.json` 拒绝访问时，先查看日志里的写入、校验和启动阶段。结果文件写入与固件写入分别记录，按实际阶段排查目录权限或文件占用。

标准烧录保留配网、通道、校准和板内缓存；全新板默认启用 CH0，其余端口按实际安装开启。[首次启动设置](FACTORY_SETTINGS.md)说明默认值。需要清空设备时选择“恢复出厂”并确认，电脑历史继续保留。

## Linux 或维护人员

以下在项目根目录执行；普通 Windows 用户跳过这一节。

```bash
python -m pip install -r requirements-flash.txt
python tools/flash_esp32.py --list-ports
python tools/flash_esp32.py --port /dev/ttyACM0
python tools/flash_esp32.py --port /dev/ttyACM0 --name "小樱"
python tools/flash_esp32.py --images AI_Doll_Firmware_v0.1.4.zip --check
python tools/flash_esp32.py --latest --check
```

Windows 命令行仍可运行 `Flash_ESP32.cmd --check` 只验证镜像，或 `Flash_ESP32.cmd --port COM4 --name "小樱"` 烧录并自定义名称；省略 `--name` 使用随机名称。`--images` 接受固件目录或项目 ZIP；`--latest --check` 只下载并校验最新正式版，去掉 `--check` 才开始烧录。下载仅保存到 `build/flash-sources/`，不会覆盖随包固件。`--factory` 明确清空设备。源码构建见 [开发指南](../developers/DEVELOPER_GUIDE.md)。

下一步：[连接家庭 Wi-Fi](../daily/WIFI_CONNECTION.md)，再按[压力校准](../daily/CALIBRATION_AND_DAILY_MODE.md)检查实际安装的传感器。
