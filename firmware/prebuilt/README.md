# 已测试的 ESP32-C3 固件 v2.3.0

这些镜像来自 2026-10-09 裸开发板及局域网模拟验收版本；应用为 937232 bytes，SHA-256 为 `dd430277fc56a992f5796368606fb13f14d7f203b1c6fb4a840b5f5174515b9a`。不包含设备 NVS、Wi-Fi 密码或个人历史。

首次烧录推荐使用 `tools/build_lab.ps1 -Upload -Port COM3`，由 PlatformIO 处理编译、引导程序及分区表。烧录前关闭采集服务和其他串口工具。

若使用已有的 ESP32 烧录工具，选择 ESP32-C3、4MB Flash；以下是本项目引导文件的地址配置，详见 `FLASH_MANIFEST.json`：

| 文件 | Flash 地址 |
|---|---|
| bootloader.bin | 0x0000 |
| partitions.bin | 0x8000 |
| boot_app0.bin | 0xe000 |
| firmware.bin | 0x10000 |

镜像头部对应 DIO、80MHz。`firmware.bin` 是应用分区镜像，不可单独写到 0x0000。无需为了常规升级擦除整片 Flash；全片擦除会删除设备保存的 Wi-Fi 和通道配置。

最多 16 个逻辑通道，预设压力、NTC 温度输入及震动输出；现有 4051 PCB 仍有八路物理输入。默认手动模式重启关闭真实输入；确认接线后可保存日常模式恢复输入，输出始终不恢复。压力校准见 [校准指南](../../docs/CALIBRATION_AND_DAILY_MODE.md)。震动必须接外置驱动并确认启用。实际温度探头与电机未验收。详见 [实测范围](../../docs/DEVICE_LAB_TEST_REPORT.md) 与 [扩展接线](../../docs/SENSOR_CHANNELS.md)。
