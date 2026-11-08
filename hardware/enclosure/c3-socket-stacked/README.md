# C3 板载锁扣插座 · 直头 USB 堆叠外壳 P03

[外壳目录](../README.md) · [旋转预览](output/preview.html) · [对应 PCB](../../rev-v2/candidates/c3-socket-20261105/README.md)

适配本轮板尾开关 PCB 修订。外形宽 42.89 × 长 56.45 × 高 33.5 mm，103450 电池在下层。开关在右后方，J9 电源入口在左后方。正面开有 15 × 9 mm Type-C 维护口。

## 打印与安装

打印 [底壳](output/base.stl)、[绝缘托板](output/tray.stl)、[卡扣上盖](output/lid.stl) 各一件。建议 PETG、0.4 mm 喷嘴、0.16～0.20 mm 层高、至少 3 道壁，100% 比例。STL 已摆好打印方向。

先断电试装电池、托板与主板，再整理线束并扣盖。电池按 34 × 50 × 10 mm 建模，保留 36 × 52 × 12 mm 净空。托板隔开电芯与底面元件，底面焊脚按不超过 2.8 mm 校核。卡扣盖保留四处可释放卡扣和 14 × 12 mm 指示灯窗口。

八个侧插窗口对应 PA2.0 传感器接口。BAT 线从左前方出壳，主板电源连接在左后方。开关可从顶部凹口及右侧拨动；BOOT、RST 开盖维护。

## 直头 Type-C 空间

按胶壳宽 14 × 长 24 × 高 8 mm 的直头线预留，从壳外到 USB 座前端连续检查插入空间。正面维护口为 15 × 9 mm。开关、J9 及两颗电容均已移出这条通道。

[装配参考 STEP](output/assembly_reference.step) 用于查看主板和电池位置。实际线材的胶壳尺寸、模块安装高度及插拔手感请先用实物核对。

## 设计与检查

[参数](parameters.json) · [PCB 参考](pcb_reference.json) · [几何报告](output/audit.json) · [独立检查](output/independent_validation.json)

检查覆盖实体、STL 水密、STEP 回读、三件装配、电池净空、直头插入通道及插座包络。机械尺寸来自本轮 PCB 回读，元件高度使用已声明的名义值。首次打印须试装。

安装 requirements-cad.txt 后，在本目录运行以下命令。

```text
python build_enclosure.py
python render_preview.py
python validate_and_package.py
```

预览截图使用 capture_preview.cjs，需要 Node.js、Playwright 和 Edge。默认保留普通文件夹，准备上传压缩包时再运行 `python validate_and_package.py --package`。
