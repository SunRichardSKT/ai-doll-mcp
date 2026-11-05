# C3板载锁扣插座 · 堆叠外壳 P02

[外壳目录](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/README.md) · [旋转预览](output/preview.html) · [PCB候选](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/rev-v2/candidates/c3-socket-20261105/README.md)

专用于本轮C3插座改版，不能给原来的带线焊接板直接套用。PCB仍为34.29 × 44.45 mm，左右各四个PA2.0侧插座，103450电池位于下层。

- 外形 **42.89 × 56.45 × 33.5 mm**，比之前紧凑堆叠壳窄3.4 mm，高0.5 mm。
- 打印三件：[底壳](output/base.stl)、[可拆绝缘载架](output/tray.stl)、[卡扣上盖](output/lid.stl)。没有螺丝或螺母。
- 电池名义34 × 50 × 10 mm，保留36 × 52 × 12 mm净空。1.4 mm载架隔开电芯与底面元件、焊脚；焊脚超过2.8 mm需修剪或修改参数。
- 侧面7.0 mm宽窗口按8 mm节距排列，CH0～CH3在一侧、CH4～CH7在另一侧；窗口有效高8.8 mm，为固定座和插头锁扣留余量。
- 槽从壳顶敞开，带插座的PCB和载架可以整体放入；合盖后由盖上的挡片补齐上沿。不会让已焊插座被封闭小孔卡住。
- 开关保留低位指拨口，指示灯留14 × 12 mm观察口。USB、BOOT、RST开盖维护。
- 开关端两侧各有一个3.6 mm出线槽，左侧BAT接电池，右侧5V接J9。每槽容纳两根名义外径1.5 mm的线。SM2.54三针插头保留正负两根线，插头和PH2.0接头都放在壳外。充电模块使用[独立四线保护壳](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/hardware/enclosure/charger-inline/README.md)，放在开关端外侧，USB-C朝外。

## 打印与安装

推荐PETG、0.4 mm喷嘴、0.16～0.20 mm层高、至少3道壁，100%比例。STL已摆好打印方向；先看切片中的卡扣与窗口，不自动缩放。

先断电，取下上盖与载架，放入电池；让电池出线端朝向开关，从载架前侧缺口将线向上引，安装载架和PCB。把BAT和J9线分别放入两侧敞口槽后扣盖，在线束两端留出弯曲余量。插拔传感器时握住插头塑壳、按锁扣释放，不拉导线。电池不能靠夹紧或挤压固定。

插头需使用与S02B-PASK-2匹配的PA系列2P线端；PH2.0、XH2.54和SM2.54不能因为针数相同就直接替代。先用一组实际插头试装，确认能插到底、能按到锁扣。

## 设计与检查范围

[参数](parameters.json)和[PCB参考](pcb_reference.json)记录了来源：XY来自本轮原生PCB回读；板厚1.6 mm、SuperMini顶高6 mm、侧插座高6.5 mm及底面包络采用标注的名义值。当前为试装版，实体装配和打印拉力待检查。

[STEP装配](output/assembly_reference.step)含PCB、电池、元件参考件，不要整件打印。`output/audit.json`保存了实体、STL/STEP一致性及声明包络的干涉检查。独立检查另见`output/independent_validation.json`。

安装`requirements-cad.txt`中的依赖后，依次运行：

```text
python build_enclosure.py
python render_preview.py
python validate_and_package.py
```

可选`capture_preview.cjs`需Node.js、Playwright及Edge，用于检查本地预览和截图。PCB布线和原生DRC已完成，建议先打印试装。
