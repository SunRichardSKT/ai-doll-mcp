# 第二版PCB外壳 · P03 紧凑堆叠版

适配V2.2紧凑贴片PCB，电池在下、主板在上。外形 **46.29 × 56.45 × 33 mm**，使用103450电池，前后四点可释放卡扣，不用螺丝。J9日常供电；USB、BOOT和RST开盖维护。

[离线旋转预览](output/preview.html) · [整体图](output/preview.png) · [合盖图](output/assembled.png) · [侧剖图](output/stack.svg)

## 打印文件

需要打印三件，单位mm、比例100%，STL已摆好打印方向：

| 打印件 | STL | 可编辑STEP |
| --- | --- | --- |
| 底壳 | [base.stl](output/base.stl) | [base.step](output/base.step) |
| 可拆绝缘载架 | [tray.stl](output/tray.stl) | [tray.step](output/tray.step) |
| 卡扣上盖 | [lid.stl](output/lid.stl) | [lid.step](output/lid.step) |

绝缘载架同时支撑PCB，隔开底面元件、焊脚和电池。先取出载架即可从上方装卸电池，不能省略。黄色电池、绿色PCB、灰色元件及[装配参考STEP](output/assembly_reference.step)是装配参考，不打印。

## 本版调整

- **缩小长宽**：相较原第二版平铺壳62 × 100.45 × 20.4 mm，改为46.29 × 56.45 × 33 mm。第二版与已制通孔板的零件位置不同，不能混用外壳。
- **开关容易拨动**：顶部扩口净尺寸15.4 × 12.4 mm，拨杆高出局部凹槽底面2.4 mm；另开14 mm宽前侧入口，可从边缘伸入拨动。
- **加紧卡扣**：导向单边间隙0.15 mm，卡钩咬合0.55 mm，上下游隙0.15 mm，悬臂厚1.1 mm。前后各两扣，释放窗避开左右线槽。
- **103450电池仓**：名义34 × 50 × 10 mm，保留36 × 52 × 12 mm净空。电池出线朝后、向上穿过载架缺口，PH2.0插头及弯线区预留12 × 8 × 10 mm，不挤压电芯。
- **观察与走线**：14 × 12 mm指示灯观察口；八路传感器顶开线槽可放入已焊带线接口。J9右侧出线口与传感器槽错开。

## 高度与安装

| 位置 | 距壳底高度 |
| --- | --- |
| 电池参考顶 | 12.2 mm |
| 绝缘载架底／顶 | 13.8／15.2 mm |
| 底面元件最低处 | 16.2 mm |
| PCB底／顶 | 19.0／20.6 mm |
| 开关拨杆顶 | 25.1 mm |
| SuperMini参考最高处 | 26.6 mm |
| 主盖内／外顶 | 31.2／33.0 mm |

按1.6 mm板厚、底面元件及修剪后焊脚不超过2.8 mm、贴片SuperMini高出主板6 mm、开关拨杆高出主板4.5 mm设计；不适用于5 mm长底针或8 mm架高模块。高度和LED中心需按实物核对，[参数文件](parameters.json)可以调整。

建议非导电PETG、0.2 mm层高、至少3道外壁。先不装电池试扣合及释放，再用断电主板试放；最后放电池并整理引线。先释放卡扣再开盖，确认无夹线、顶焊脚或压紧电芯，可加非导电提拉带。

电池末端到后内壁约1.85 mm，出线向上转弯，封边、原厂引线和接头需要试装。仓位不包含充电、保护或升压电路；J9仍要求合适的5V输入，单节锂电池不能直接接J9。

## 检查与重建

已检查STEP回读、STL单实体与水密、壳体装配、元件及电池净空、载架和电池装入路径、开关前侧与顶部操作空间、观察口及卡扣释放空间。见[几何报告](output/audit.json)、[独立导出检查](output/independent_validation.json)及[预览检查](output/preview_check.json)。扣合手感以实物试装为准。

在本目录安装[CAD依赖](requirements-cad.txt)，然后运行：

```text
python build_enclosure.py
python render_preview.py
node capture_preview.cjs
python validate_and_package.py
```

截图需要另装Playwright和Edge；HTML预览本身可离线打开。最后一步生成独立的`AI_Doll_V22_Stacked_Enclosure_P03.zip`及[校验清单](SHA256SUMS.txt)。不修改PCB、固件、接线或设备设置。

PCB来源：[第二版布线工程](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/candidates/pcb-v22-routed-20261017/README.md)。新PCB的焊盘及制造适配仍按该工程说明核对，本外壳不代替制造确认。
