# 硬件采购与装配入口

本目录保留当前原生工程、BOM、原下单生产文件和必要核对证据。软件烧录从 [一键烧录教程](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/start/QUICK_FLASH.md)开始。

| 文件或目录 | 用途 |
| --- | --- |
| [已制旧板平铺外壳 P03](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/ordered-v2-prototype/README.md) | 按原下单位置制作；通孔架高安装，采用用户约 8 mm 叠高，总高 20.8 mm；待试装 |
| [旧板上下堆叠外壳 P01](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/ordered-v2-stacked/README.md) | 电池下置、绝缘载架、下沉开关口；46.29×56.45×35.2mm；待打印试装 |
| [外壳设计入口](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/README.md) | 区分已制旧板与 V2.2 新紧凑板，避免混用外壳 |
| [V2.2 双层布线候选（2026-10-17）](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/candidates/pcb-v22-routed-20261017/README.md) | 26 网已布线、双面地铜；网表同步后完整原生 DRC 通过，手焊封装和装配适配待定版，不能下单 |
| [V2.2 紧凑贴片布局候选（2026-10-16）](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/candidates/pcb-v22-20261016/README.md) | SuperMini 贴片安装、两组线束固定孔、原板尺寸；未布线、不能下单，先查看布局预览及封装适配限制 |
| [V2.1 装配对比草案](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/candidates/assembly-v21-20261016/README.md) | 保留先前加宽板框与线束固定的探索记录；不是当前定版或生产文件 |
| [丝印镜像修正工程（2026-10-16）](AI_Doll_V2_丝印镜像修正_20261016.epro2) | 当前编辑版本，已修正背面 33 处文字，用户提供的新版 3D 图已确认文字正向；见[修正说明](丝印镜像修正说明_20261016.md) |
| [标准化原生工程（2026-10-03）](AI_Doll_V2_标准化完成_20261003.epro2) | 保留的前版工程；嘉立创 EDA 专业版导入 |
| [采购 BOM](AI_Doll_V2_标准化采购BOM_20261003.csv) | 板上器件采购 |
| [板外器件与测试点](AI_Doll_V2_板外器件与测试点_20261003.csv) | SuperMini、传感器、电源和测量位置 |
| [器件标准化核对](元器件标准化核对记录.md) | 封装、料号与电源说明 |
| [原下单文件说明](ordered-gerber-20260920/已下单PCB封装核对.md) | 对应已经下单的焊位与 Gerber |
| verification/ | 原设计回读、DRC 和采购资料证据 |

两层板，34.29 × 44.45 mm；ESP32-C3 SuperMini、74HC4051、八路板外 FSR。主板没有充电、升压或电池保护电路。实际信号接线见 [通道教程](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/daily/SENSOR_CHANNELS.md)。

原下单 Gerber 保留，不能因为软件更新而重新生成或混用制造文件。已实测 CH0 压力输入与本机历史归档；其余通道、温度、电机和整机电源仍需分别验收。

当前丝印修正版仍有 1 项原生网表不匹配，重新下单前需核对。错误镜像草稿仅保留在本机，不进入公开源码和新版交付包。

