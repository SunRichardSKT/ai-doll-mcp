# ESP32-C3 交付固件 2.7.0

应用镜像 1056672 bytes，SHA-256 `59359b796c57be778b7915b9c2f6434ae6968fc52a837bd67030a17c192f42eb`。该镜像已在裸开发板通过实际 Wi-Fi 上传、启动确认、MCP 配置及软件重启测试。未包含 Wi-Fi、NVS、个人日志或模型密钥。

首次安装选择 ESP32-C3、4MB、DIO、80MHz，按 `FLASH_MANIFEST.json` 烧录四个文件：

| 文件 | 地址 |
|---|---|
| bootloader.bin | 0x0000 |
| partitions.bin | 0x8000 |
| boot_app0.bin | 0xe000 |
| firmware.bin | 0x10000 |

应用不能单独写到 0x0000。常规安装无需全片擦除；擦除会丢失网络、通道和待补传记录。不要写空白文件系统覆盖记录。首次烧录也可按 [根 README](../../README.md) 编译并使用 `tools/build_lab.ps1 -Upload -Port COM3`，先关闭串口占用。

配网和 BOOT 按钮见 [使用指南](../../docs/USER_GUIDE.md)。联网后可 [无线升级](../../docs/OTA_UPDATE.md)。默认手动模式，不开启裸板真实输入；FSR 接好后逐路 [校准](../../docs/CALIBRATION_AND_DAILY_MODE.md)。温度和电机接线见 [通道指南](../../docs/SENSOR_CHANNELS.md)。实际传感器、温度精度及震动尚未实物验收。
