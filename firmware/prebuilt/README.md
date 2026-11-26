# 第一代 ESP32-C3 预编译固件 0.1.5

本项目固件及源码使用 AGPL-3.0-only，第三方组件保留原许可，范围见 [项目许可](../../LICENSING.md)。0.1.5 在 10 kΩ B3950 预设之外增加 2～4 点自定义曲线。温度端口显示 ADC 毫伏和换算阻值，湿润片可独立触发或与压力联动。

[本版附件](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.5) · [对应源码](https://github.com/SunRichardSKT/ai-doll-mcp/tree/v0.1.5) · [构建指南](../../docs/developers/DEVELOPER_GUIDE.md) · [烧录教程](../../docs/start/QUICK_FLASH.md)

## 完整四文件

| 文件 | 地址 |
| --- | --- |
| bootloader.bin | 0x0000 |
| partitions.bin | 0x8000 |
| boot_app0.bin | 0xe000 |
| firmware.bin | 0x10000 |

芯片ESP32-C3，4MB，DIO，80MHz。应用不能写到0x0000。镜像与SHA-256见[FLASH_MANIFEST.json](FLASH_MANIFEST.json)。标准更新保留NVS、历史分区与校准；明确恢复出厂才全片擦除。每次USB烧录生成新内部配对编号，可选择显示名和热点名；日常重启保留身份。

## 使用与能力

- 首次热点最长10分钟，新配网成功后约90秒关闭。正常重启不开热点；运行中长按BOOT约3秒重新开启，连接后访问`http://192.168.4.1/setup`。
- 支持真实／模拟端口独立设置、压力校准、部位命名、固定`.local`名称和身份查询。全新安装只启用CH0真实采样，其余压力端口关闭；升级保留已有设置。
- 本版固件公开23个工具，保留内部归档租约接口，支持两线 NTC 10 kΩ B3950 与湿润片；动作、数字温度和外接输出仍不支持。租约默认90秒，每30秒续租，持久记录确认需匹配启动、epoch、持有者及其已读取游标。
- 支持连接文件、连接码和临时二维码、设备直传、断网缓存及OTA。不增加物理输出；原压力端口、校准与电气参数保留，不自动转换成扩展类型。

## 构建与空间

应用镜像 **1,215,488 字节**，单个 OTA 槽 **1,310,720 字节**，剩余 **95,232 字节**。设置网页和工具清单在构建时压缩，SuperMini 无线功率为 8.5 dBm。

导出门禁：OTA余量低于24KiB阻止交付，低于32KiB告警。不能缩减历史分区换空间。源码修改后按[开发指南](../../docs/developers/DEVELOPER_GUIDE.md)重新编译，再运行`tools/export_firmware.py`更新四文件与清单。局域网升级见[OTA教程](../../docs/daily/OTA_UPDATE.md)。

实现资料：[网络与空间](../../docs/reports/FIRMWARE_NETWORK.md) · [固件精简](../../docs/reports/FIRMWARE_TRIM.md) · [温度／擦眼泪迁移](../../docs/reports/RESISTIVE_INPUTS_012.md) · [检查记录](../../docs/reports/VALIDATION.md)
