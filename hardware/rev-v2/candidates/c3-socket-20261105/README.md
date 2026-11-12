# 共感娃娃第一代主板 · 最终版

PCB、BOM 和制造设计使用 CERN-OHL-S-2.0。[许可范围](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/LICENSING.md)。

[项目首页](../../../../README.md) · [主板资料](../../README.md) · [核心电池外壳](../../../enclosure/c3-socket-stacked/README.md) · [独立充电板外壳](../../../enclosure/charger-inline/README.md)

本目录为**第一代C3八路锁扣插座板最终版**，保留用户2026-11-09最后修改的丝印。板框、元件位置、走线、电气参数和固件引脚不变；历史工程名中的日期及目录名仅为内部来源标识。

| 项目 | 最终配置 |
| --- | --- |
| 主控 / 采样 | ESP32-C3 SuperMini / 74HC4051，八路FSR |
| PCB | 34.29 × 44.45 mm，双层板 |
| 传感器 | J1～J8，PA2.0 2P侧插锁扣座 |
| 主板电源 | J9，PA2.0 3P侧插锁扣座，5V输入 |
| 电池 | 103450聚合物锂电池，3.7V 2000mAh，PH2.0端子 |
| 外壳 | 电池下置、主板在上，核心与充电板各用独立壳体 |

## 下载与制造

[嘉立创原生工程](AI_Doll_Gen1_Final.epro2) · [Gerber与钻孔](manufacturing/) · [顶面图](pcb-top.svg) · [底面图](pcb-bottom.svg) · [检查摘要](audit.json)

制造时使用本目录整套文件。原生工程、Gerber和正反面图均来自最后保存重开的同一版；正反面图展示Gerber丝印及回读焊盘，不显示走线和钻孔。完整制造数据见Gerber。

本轮原生DRC为零项。此前P03是机械和接线基线，用户最新丝印已经覆盖该版；不要再把旧版文字位置或镜像设置批量写回来。

## 传感器插座

J1～J8使用**JST PA 2.0 mm、2P、通孔侧插、带锁扣**的S02B-PASK-2(LF)(SN)，嘉立创库料号C265094。左右各四座，中心间距8 mm，入口朝外。

线端用PAP-02V-S及配套端子，优先购买压接好的线束。SM2.54不能直接插入；可以更换主板侧插头或使用转接线。

**1脚为各路EXC激励，2脚为各路CH信号，并非一脚接地。** J1～J8依次对应CH0～CH7。FSR不分极性，其他器件按电路核对接法。

来源：[JST PA系列](https://www.jst-mfg.com/product/index.php?lang=2&series=189)、[原厂尺寸手册](https://www.jst-mfg.com/product/pdf/eng/ePA-F.pdf)。

## 电池、充电板与J9

J9板端为**S03B-PASK-2(LF)(SN)**、C265095，线端为**PAP-03V-S**：

| J9针号 | 连接 |
| --- | --- |
| 1 | GND，充电板输入输出负极 |
| 2 | NC，不接 |
| 3 | +5V / PWR5V_RAW，充电板输入输出正极 |

103450电池放入核心壳底层，PH2.0线从BAT口引出，接独立充电板B+/B−。充电板仍用此前选定的Type-C充放升压模块，USB-C用于充电；它的输入输出正负端接主板J9。[分体接线图](../../../enclosure/c3-socket-stacked/output/wiring.svg) · [四线取电说明](../../../enclosure/charger-inline/POWER_WIRING.md)。

**主板不集成充电、升压或锂电保护，不能把3.7V电池并到J9当作5V输入。** 不按线色推断正负；旧两针板J9.2为正极，本版J9.2空置，不能混用针序。

## 开关与外壳

开关在板尾右侧，J9在板尾左侧；C13、C14在底面前侧，避开插座和USB。TP4（ADC）在底面。保留SuperMini天线双面禁铜区。

[核心电池壳](../../../enclosure/c3-socket-stacked/README.md)长56.45 × 宽42.89 × 高33.9 mm，三件打印：底壳、绝缘托板、卡扣上盖。电池仓净空52 × 36 × 12 mm，PH2.0接头留在壳外；前侧直头USB口、右后下沉开关口和指示灯窗口保留，侧面接口上部合并为连续窗口。[加固结构说明](../../../enclosure/PRINT_STRENGTHENING.md)。

[独立充电板壳](../../../enclosure/charger-inline/README.md)长36 × 宽22 × 高11 mm，两件打印，带灯窗和四根线的夹持结构。核心与充电板不合并。

第一次打印先断电试装实际PA插头、SuperMini、USB线和成品103450电池，再验证供电与八路采样。元件高度、打印配合及电池封边按实物确认。
