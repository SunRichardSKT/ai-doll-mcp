# 外壳模型

当前按两种板型分别提供堆叠外壳，含103450电池空间、指示灯窗口与可拆卡扣上盖。第二版的[低矮平铺方案](v22-prototype/README.md)也保留作可选结构。

| 实际主板 | 选择的外壳 | 外形尺寸 |
| --- | --- | --- |
| 已制作的通孔SuperMini主板 | [上下堆叠壳P02](ordered-v2-stacked/README.md) · [旋转预览](ordered-v2-stacked/output/preview.html) | 46.29 × 56.45 × 35.2 mm |
| 第二版紧凑贴片主板 | [紧凑堆叠壳P03](v22-stacked/README.md) · [旋转预览](v22-stacked/output/preview.html) | 46.29 × 56.45 × 33 mm |

[查看两种板型](preview.html)。按实际板型选模型，勿混用。已制通孔板P02支持只换上盖；第二版PCB的P03重新对齐开关、观察口和线槽，底壳、载架、上盖须配套打印。

## C3板载锁扣插座候选

[配套堆叠壳P01](c3-socket-stacked/README.md) · [旋转预览](c3-socket-stacked/output/preview.html)：42.89 × 56.45 × 33.5 mm，103450电池下置、八个PA2.0侧插窗口、J9后端出线。仅匹配本轮新插座布局，先试装，不替换原带线板外壳。

## 独立充电模块保护壳

[Type-C 小充电／升压板保护壳 P02](charger-inline/README.md) · [旋转预览](charger-inline/output/preview.html)：36 × 22 × 11 mm，全打印双片卡扣，带灯窗、两侧走线通道与四线压线槽，无需五金件。按16.2 × 12 × 4.4 mm商品图建模，先试装。

## 打印文件

- 堆叠版打印`base.stl`、`tray.stl`、`lid.stl`，其中托板隔离约5mm底针与电池。
- 第二版紧凑堆叠壳同样打印`base.stl`、`tray.stl`、`lid.stl`；载架隔离底面元件并可取出装电池。可选平铺壳只打印底壳与上盖。
- 各自`output/`中包含STL、STEP和装配预览。模型中的PCB、电池与元件是参考件，不打印。

103450电池按50 × 34 × 10mm预留。仓位不提供充电、保护或升压功能；J9仍需合适的5V电源。先用断电实物试放，不能压紧电芯来固定。

## 修改和打包

按各目录`requirements-cad.txt`准备CAD环境，运行其生成与预览脚本。紧凑壳导出检查使用`validate_enclosures.py`；堆叠壳使用其`validate_and_package.py`。几何检查不能代替打印试装。

在项目根目录运行：

```text
python hardware/enclosure/package_enclosures.py
```

使用现有导出和校验清单生成当前`AI_Doll_Enclosures_v0.1.1.zip`及已制板独立堆叠包，不需要重新建模。第二版P03也可在`v22-stacked/`目录运行`python validate_and_package.py`生成自己的独立包。

[主板资料](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md) · [紧凑壳导出检查](validation_103450.json)
