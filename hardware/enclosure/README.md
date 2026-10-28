# 外壳模型

当前提供两种板型对应的模型，含103450电池空间、指示灯窗口与可拆卡扣上盖。

| 实际主板 | 选择的外壳 | 外形尺寸 |
| --- | --- | --- |
| 已制作的通孔SuperMini主板 | [上下堆叠壳P02](ordered-v2-stacked/README.md) · [旋转预览](ordered-v2-stacked/output/preview.html) | 46.29 × 56.45 × 35.2 mm |
| 紧凑贴片研发主板 | [平铺壳P02](v22-prototype/README.md) · [旋转预览](v22-prototype/output/preview.html) | 62 × 100.45 × 20.4 mm |

[查看两种结构](preview.html)。按实际板型选模型，勿混用。最新堆叠盖扩大开关入口、凹槽降低1.4mm并加紧卡扣；现有底壳和绝缘托板可以继续用，先只重打上盖。

## 打印文件

- 堆叠版打印`base.stl`、`tray.stl`、`lid.stl`，其中托板隔离约5mm底针与电池。
- 紧凑平铺版打印`base.stl`与`lid.stl`。
- 各自`output/`中包含STL、STEP和装配预览。模型中的PCB、电池与元件是参考件，不打印。

103450电池按50 × 34 × 10mm预留。仓位不提供充电、保护或升压功能；J9仍需合适的5V电源。先用断电实物试放，不能压紧电芯来固定。

## 修改和打包

按各目录`requirements-cad.txt`准备CAD环境，运行其生成与预览脚本。紧凑壳导出检查使用`validate_enclosures.py`；堆叠壳使用其`validate_and_package.py`。几何检查不能代替打印试装。

在项目根目录运行：

```text
python hardware/enclosure/package_enclosures.py
```

使用现有导出和校验清单生成当前`AI_Doll_Enclosures_v0.1.0.zip`及独立堆叠包，不需要重新建模。

[主板资料](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/README.md) · [紧凑壳导出检查](validation_103450.json)
