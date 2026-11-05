# 主板与采购资料

> [项目首页](../../README.md) · [接线教程](../../docs/daily/SENSOR_CHANNELS.md) · [外壳选择](../enclosure/README.md)

## 在用通孔主板

两层板34.29 × 44.45 mm，使用ESP32-C3 SuperMini、74HC4051和八路板外FSR。主板没有锂电池充电、升压或保护电路，J9需要5V输入。

| 文件 | 用途 |
| --- | --- |
| [当前原生工程](AI_Doll_V2_丝印镜像修正_20261016.epro2) | 嘉立创EDA专业版工程，背面丝印方向已修正 |
| [采购BOM](AI_Doll_V2_标准化采购BOM_20261003.csv) | 板上元器件 |
| [板外器件和测试点](AI_Doll_V2_板外器件与测试点_20261003.csv) | SuperMini、FSR、电源及测量位置 |
| [器件与电源核对](元器件标准化核对记录.md) | 封装、供应商资料和电源边界 |
| [在用制造Gerber](ordered-gerber-20260920/已下单PCB封装核对.md) | 对应当前已制作主板，不混用研发板制造资料 |
| [丝印与DRC说明](丝印镜像修正说明_20261016.md) | 当前工程的排版核对与网表事项 |
| [堆叠外壳](../enclosure/ordered-v2-stacked/README.md) | 电池下置、P02加紧上盖 |

## 紧凑贴片主板

[开关居中靠下现板的扩展设计](../expansion/current-board/README.md)单独维护接线、配件及软件交付边界，保留原八路压力。它不改变下述历史工程的制造核对状态，也不把扩展设计标为已实测。

[当前布线工程与说明](candidates/pcb-v22-routed-20261017/README.md)保留最新紧凑方案。SuperMini手焊焊盘、底面元件与USB净空仍需适配确认，不能直接按研发工程下单；推荐[紧凑堆叠外壳P03](../enclosure/v22-stacked/README.md)，也保留[低矮平铺外壳](../enclosure/v22-prototype/README.md)。

`verification/`保留当前丝印核对、DRC与元器件资料。早期装配草案、未布线布局、前版原生工程和重复预览已清理。实际接线和校准按当前硬件操作，不因软件版本统一修改电气参数。

## C3板载锁扣插座改版

[插座布局P01](candidates/c3-socket-20261105/README.md)保留原C3八路电路，改用PA2.0带锁扣侧插座；[配套外壳](../enclosure/c3-socket-stacked/README.md)缩窄并保留103450电池层。本版为独立布局候选，尚未布线，不能直接下单。旧板工程和制造资料仍供在用硬件维护。
