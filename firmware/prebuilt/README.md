# ESP32-C3 预编译固件 2.9.0

普通用户按 [一键烧录教程](../../docs/start/QUICK_FLASH.md)操作，不用填写下表。设备连上家庭 Wi-Fi 后仍保留热点与固定设置页 http://192.168.4.1/。

## 维护人员：完整四文件

| 文件 | 地址 |
| --- | --- |
| bootloader.bin | 0x0000 |
| partitions.bin | 0x8000 |
| boot_app0.bin | 0xe000 |
| firmware.bin | 0x10000 |

芯片 ESP32-C3，4MB，DIO，80MHz。应用不能写到 0x0000。正常更新不擦除 NVS 或文件系统；明确恢复出厂才全片擦除。使用一键入口会为本次 USB 烧录生成并保存新设备名称，日常重启保留。

## 当前应用

大小 **1304720 bytes**；SHA-256：

```text
7359974e760e1443b4c116a63a17f0adbcf132c04819257a4e3f5cd50107982a
```

其他文件逐项校验见 [FLASH_MANIFEST.json](FLASH_MANIFEST.json)。清单与编译输出配套，不含用户 Wi-Fi、NVS、令牌或模型密钥。新固件保留 SuperMini 的 8.5dBm 无线功率设置。

2.9.0 标准 USB 烧录、启动、独立新编号及联网后固定配置页已实际检查；旧 OTA 报告不当作新版无线升级的实测结果。CH0 真实压力链路已有实物证据，其他硬件见 [验证范围](../../docs/reports/VALIDATION.md)。

源码修改后先 [重新构建](../../docs/developers/DEVELOPER_GUIDE.md)，运行 tools/export_firmware.py 更新镜像和清单。已有固件的局域网升级见 [OTA 教程](../../docs/daily/OTA_UPDATE.md)。
