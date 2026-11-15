# 硬件代际与文件入口

产品代际按核心平台划分，与 PCB 修订号和软件版本分别管理。

| 产品代际 | 平台与状态 | 文件入口 |
| --- | --- | --- |
| **第一代** | 所有 ESP32-C3 方案：已制带线板、V2／V2.2 PCB修订、PA2.0插座板及手焊焊盘改进 | [第一代总览](gen1/README.md) |
| **第二代** | ESP32-S3开发板方案预研，目标为模块化多媒体核心；尚无本项目二代可制造PCB或专用固件 | [研发进度与下一步](gen2/README.md) |

`V2`、`V2.2`、`rev-v2`、`ordered-v2-stacked` 是第一代历史板次或目录名，不表示第二代产品。原生工程内的历史名称保留，便于对应已生产实物与制造记录。

第一代PCB、外壳、扩展接线统一存放于 `gen1/`。旧地址仅保留简短跳转说明，以兼容已发布包中的链接。当前C3固件保留在根目录的 [firmware/](../firmware/README.md)，手机、MCP、历史和聊天队列属于共享软件层。

硬件设计使用 [CERN-OHL-S-2.0](LICENSE)，软件及生成脚本按 [项目许可](../LICENSING.md)管理。

## 旧版下载包的访问入口

以下只作旧链接跳转，当前资料从上方第一代入口查看。

- [原PCB入口](rev-v2/README.md) · [原锁扣插座板入口](rev-v2/candidates/c3-socket-20261105/README.md)
- [原外壳入口](enclosure/README.md) · [原打印加固说明](enclosure/PRINT_STRENGTHENING.md)
- [原插座板壳入口](enclosure/c3-socket-stacked/README.md) · [原带线板壳入口](enclosure/ordered-v2-stacked/README.md) · [原充电板壳入口](enclosure/charger-inline/README.md)
