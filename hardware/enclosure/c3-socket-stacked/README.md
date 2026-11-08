# 第一代最终版 · 核心电池外壳

模型与硬件设计使用 CERN-OHL-S-2.0，生成、检查及打包脚本使用 AGPL-3.0-only。[许可范围](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/LICENSING.md)。

[外壳目录](../README.md) · [旋转预览](output/preview.html) · [对应PCB](../../rev-v2/candidates/c3-socket-20261105/README.md) · [分体接线图](output/wiring.svg)

适配用户最终丝印版C3八路锁扣插座主板。**核心和充电板分开装壳**：103450电池位于核心壳底层，主板在上；充电板继续使用独立[四线保护壳](../charger-inline/README.md)。

| 项目 | 规格 |
| --- | --- |
| 核心壳外形（长×宽×高） | 56.45 × 42.89 × 33.5 mm |
| 电池 | 103450聚合物锂电池，3.7V、2000mAh、PH2.0端子 |
| 电芯名义尺寸 / 电池仓净空 | 50 × 34 × 10 / 52 × 36 × 12 mm |
| 盖板 | 四处可释放卡扣，无螺丝 |
| 指示灯窗口 | 14 × 12 mm |
| 维护USB口 | 15 × 9 mm，前侧直插 |
| 接口 | 八个7 mm传感器窗口、一个9 mm J9电源窗口 |

## 打印文件

打印[底壳](output/base.stl)、[绝缘托板](output/tray.stl)、[卡扣上盖](output/lid.stl)各一件。建议PETG、0.4 mm喷嘴、0.16～0.20 mm层高、至少3道壁、100%比例。STL已摆好打印方向。

[装配参考STEP](output/assembly_reference.step)用于核对位置，包含电池、主板和元件示意件，不整件打印。单件STEP与STL在同一output目录。

## 电池与分体充电板

1. 电池长边沿外壳长度方向平放，出线朝前侧USB端。先放电池，整理线束，再放绝缘托板和主板；托板隔开电芯、底面元件和焊脚。
2. 两根电池线从前侧托板缺口上行，经左前侧BAT槽引出。竖向通道宽5.2 mm，已避开直头USB插入区域；上方两根线的出口通道单独检查。
3. **PH2.0插头本体留在壳外**，不用穿过小线孔。装配时把导线放入敞口槽再合盖；电池原厂线保留缓弯和约12 mm整理余量，不压电芯封边。按成品电池（含封边、保护板）确认实际外形在净空内。
4. 壳外PH2.0插接到充电板BAT线；充电板独立输入输出端经PA2.0三针线束接J9：**1=GND、2=空置、3=5V**。主板不接充电板B+/B−。PH2.0按实际正负核对针序。

充电模块采用之前选定的Type-C 3.7V升5V充放模块，包络16.2 × 12 × 4.4 mm。其[独立保护壳](../charger-inline/README.md)为36 × 22 × 11 mm，保留灯窗及四条夹线槽；不装入核心壳。[完整四线说明](../charger-inline/POWER_WIRING.md)。

## 开关、USB与维护

开关在右后方，可从顶部下沉口或右侧拨动；J9位于左后方。前侧USB维护口按14 × 8 mm截面、24 mm长的直头胶壳预留插入通道。BOOT、RST开盖操作。

主板、托板和盖板配套使用。底面焊脚按修剪后不超过2.8 mm预留，焊脚到托板再留1 mm。盖板导向单边间隙0.15 mm、卡扣咬合0.55 mm；第一次打印先断电试装，核对实际插头、开关高度、卡扣及电池封边。

## 源文件与检查

[参数](parameters.json) · [当前PCB参考](pcb_reference.json) · [几何报告](output/audit.json) · [导出检查](output/independent_validation.json)

来源为本轮最终PCB的实际回读；丝印修改完整保留。检查包括三件装配、电池与线束净空、直头USB、电源插入、载架取出、STEP回读和STL水密。元件高度为已声明的名义值，几何检查不代替首次打印试装。

安装requirements-cad.txt中的依赖后，在本目录运行：

```text
python build_enclosure.py
python render_preview.py
node capture_preview.cjs
python validate_and_package.py
```

截图需要Playwright与Edge。默认生成普通文件；上传需要ZIP时再运行`python validate_and_package.py --package`。
