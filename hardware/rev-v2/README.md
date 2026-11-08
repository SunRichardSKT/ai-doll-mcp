# 主板与采购资料

> [项目首页](../../README.md) · [接线教程](../../docs/daily/SENSOR_CHANNELS.md) · [外壳选择](../enclosure/README.md)

## 第一代最终版 · C3板载锁扣插座

[第一代最终版](candidates/c3-socket-20261105/README.md)使用八个 PA2.0 双针侧插锁扣座。开关移到板尾右侧，J9 移到板尾左侧，为直头 Type-C 留出插线通道。配套 [第一代最终版电池壳](../enclosure/c3-socket-stacked/README.md) 含103450、3.7V 2000mAh、PH2.0电池仓；充电模块使用独立外壳。

早期 V2.2 居中开关布局及其外壳已撤下。已有板子的 [扩展接线资料](../expansion/current-board/README.md) 继续用于核对既有接线。

## 早期已制带线板

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
