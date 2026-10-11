# ESP32-C3 预编译固件 2.8.1

用于 ESP32-C3 SuperMini。已有本项目固件的用户优先 [无线升级](../../docs/OTA_UPDATE.md)；空白开发板首次用 USB 写入。

## 首次烧录：四个文件与地址

选择 **ESP32-C3、4MB、DIO、80MHz**，按 [FLASH_MANIFEST.json](FLASH_MANIFEST.json)填写：

| 文件 | 写入地址 |
| --- | --- |
| `bootloader.bin` | `0x0000` |
| `partitions.bin` | `0x8000` |
| `boot_app0.bin` | `0xe000` |
| `firmware.bin` | `0x10000` |

应用不能单独写到 0x0000。先关闭占用串口的程序。常规更新不全片擦除、不写空白文件系统，以免丢失 Wi-Fi、通道和待补传。

## 当前镜像校验

应用大小 **1298032 bytes**，SHA-256：

```text
b6bca8008fa5e7d4cf9f7c1a461b24fe8406093938d7f8bf2171f2952dd19daf
```

清单包含其余文件的地址、大小和 SHA-256。已在裸 ESP32 实际 OTA 并确认启动，保留原网络与通道；不含个人 NVS、Wi-Fi 或模型密钥。

## 烧录后

按 [使用指南](../../docs/USER_GUIDE.md)配网，默认设置页免登录，可 [开启保护](../../docs/RUNTIME_AND_LOGIN.md)。默认手动模式，未接传感器时只模拟；接好 FSR 后 [逐路校准](../../docs/CALIBRATION_AND_DAILY_MODE.md)。

真实传感器和电机尚未验收，见 [验证汇总](../../docs/VALIDATION.md)。自行编译的目标与入口见 [开发指南](../../docs/DEVELOPER_GUIDE.md)。
