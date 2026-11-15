# 第一代 · ESP32-C3 共感娃娃核心

本目录收纳全部C3硬件。产品名称统一为“第一代”，PCB修订仍可用V2／V2.2等历史板次区分；软件版本0.1.x独立维护。

## 按实物选资料

| 板型／用途 | 对应文件 |
| --- | --- |
| 已制双排通孔SuperMini带线板 | [PCB、BOM与制造文件](pcb/README.md#早期已制带线板) · [带线板堆叠壳](enclosure/ordered-v2-stacked/README.md) |
| 居中靠下开关的C3 PCB修订 | [历史扩展接线](expansion/current-board/README.md)；仍属第一代，按实际固件能力选择扩展 |
| 第一代最终PA2.0锁扣插座板 | [工程与制造资料](pcb/candidates/c3-socket-20261105/README.md) · [配套103450电池壳](enclosure/c3-socket-stacked/README.md) |
| 独立Type-C充电／升压小板 | [保护壳与四线接法](enclosure/charger-inline/README.md) |
| NTC温度与湿润感应片 | [现板扩展接线、配件和配置](expansion/resistive-inputs/README.md) |

SuperMini手焊焊盘的后续修改也归第一代板型修订，不据此升级产品代际。制造数据、原生工程文件名和现有STL／STEP保留，避免与实物批次混淆。

## 软件和能力

当前 [C3固件](../../firmware/README.md)提供压力、两线NTC、湿润片及干接点；标准八个传感器口可配置为6路压力＋1路温度＋1路湿润。早期姿态、马达、数字温度与外接灯设计仅作接线参考，不能据此认为当前固件仍有相应驱动。

- [PCB与采购](pcb/README.md)
- [外壳分类与打印](enclosure/README.md)
- [通道、接线与校准](../../docs/daily/SENSOR_CHANNELS.md)
- [当前功能和客户端范围](../../README.md#适用范围)
- [第二代研发状态](../gen2/README.md)

USB、设备身份、校准、历史和已发布安装包的版本保持各自原约定。旧Release内的目录结构是发布时快照，仍可使用；新源码从本目录查找硬件。
