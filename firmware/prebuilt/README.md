# ESP32-C3 预编译固件 0.1.1

本目录镜像沿用已发布的 0.1.1 批次及既有授权；本次许可切换不改镜像或哈希。当前固件源码按 AGPL-3.0-only 授权，范围与旧版 MIT 文本见 [项目许可](../../LICENSING.md)。

配套固件为0.1.1，`feature_set=pressure-switch-v1`、`network_revision=2`。[本版Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v0.1.1)提供完整包与单独固件包。按[一键烧录教程](../../docs/start/QUICK_FLASH.md)操作；发布不会自动给已有设备烧录。

## 完整四文件

| 文件 | 地址 |
| --- | --- |
| bootloader.bin | 0x0000 |
| partitions.bin | 0x8000 |
| boot_app0.bin | 0xe000 |
| firmware.bin | 0x10000 |

芯片ESP32-C3，4MB，DIO，80MHz。应用不能写到0x0000。镜像与SHA-256见[FLASH_MANIFEST.json](FLASH_MANIFEST.json)。标准更新保留NVS、历史分区与校准；明确恢复出厂才全片擦除。每次USB烧录生成新内部配对编号，可选择显示名和热点名；日常重启保留身份。

## 使用与能力

- 首次热点最长10分钟，新配网成功后约90秒关闭。正常重启不开热点；运行中长按BOOT约3秒重新开启，连接后访问`http://192.168.4.1/`。
- 支持真实／模拟端口独立设置、压力校准、部位命名、固定`.local`名称和身份查询。全新安装只启用CH0真实采样，其余压力端口关闭；升级保留已有设置。
- 本版固件公开23个工具，保留内部归档租约接口，移除温度、动作和外接物理输出。租约默认90秒，每30秒续租，持久记录确认需匹配启动、epoch、持有者及其已读取游标。
- 支持连接文件、连接码和临时二维码、设备直传、断网缓存及OTA。不增加物理输出或改变接线、电气参数与采样阈值。

## 构建与空间

应用大小**1,198,848字节**，单个OTA槽**1,310,720字节**，余量**111,872字节**；静态RAM为73,300字节。保留原分区、完整HTTPS、64位归档与回溯支持。设置网页和静态工具清单经构建端精简、gzip压缩后嵌入；SuperMini无线功率为8.5dBm。

导出门禁：OTA余量低于24KiB阻止交付，低于32KiB告警。不能缩减历史分区换空间。源码修改后按[开发指南](../../docs/developers/DEVELOPER_GUIDE.md)重新编译，再运行`tools/export_firmware.py`更新四文件与清单。局域网升级见[OTA教程](../../docs/daily/OTA_UPDATE.md)。

本版已重新编译，不自动给已有设备烧录。[当前检查记录](../../docs/reports/VALIDATION.md)

网络恢复、简洁手机配网页和空间评估见[网络优化报告](../../docs/reports/FIRMWARE_NETWORK.md)。升级需要使用本版配套镜像，不自动给设备升级。

本版固件已清理重复调试与旧工具列表，详见[固件精简说明](../../docs/reports/FIRMWARE_TRIM.md)。

当前驱动取舍与迁移见[压力/开关固件说明](../../docs/reports/FIRMWARE_INPUTS.md)，以清单feature_set=pressure-switch-v1识别。
