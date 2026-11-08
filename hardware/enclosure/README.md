# 外壳模型

先按主板接口选择外壳。下表的尺寸按长 × 宽 × 高标注，单位 mm。

| 对应硬件 | 当前外壳 | 外形 |
| --- | --- | --- |
| C3 八路 PA2.0 板载锁扣插座板，开关移到板尾 | [直头 USB 堆叠壳 P04](c3-socket-stacked/README.md) · [旋转预览](c3-socket-stacked/output/preview.html) | 56.45 × 42.89 × 33.5 |
| 已制双排通孔 SuperMini 带线板 | [带线板堆叠壳 P02](ordered-v2-stacked/README.md) · [旋转预览](ordered-v2-stacked/output/preview.html) | 56.45 × 46.29 × 35.2 |
| 独立 Type-C 充电／升压小板 | [四线保护壳 P02](charger-inline/README.md) · [旋转预览](charger-inline/output/preview.html) | 36 × 22 × 11 |

[查看分类](preview.html)。主板堆叠壳打印底壳、绝缘托板、卡扣上盖三件，充电模块保护壳打印底壳与上盖两件。每个目录提供 STL、STEP、参数及装配图。

当前插座版将开关和 J9 移到板尾，正面预留直头 Type-C 通道。旧 V2.2 居中开关 PCB 及其平铺、堆叠外壳已从当前文件树撤下。

电池仓按 103450 电芯预留。主板 J9 使用合适的 5 V 电源模块，装配时保持电芯与底面焊脚的间隙。打印配合按对应版本说明进行断电试装。

## 生成与上传

本地直接使用各型号目录内的文件。按各目录 requirements-cad.txt 安装 CAD 依赖，再运行生成与检查脚本。上传需要压缩包时，在项目根目录运行下列命令。

```text
python hardware/enclosure/package_enclosures.py --output build/AI_Doll_Enclosures_upload.zip
```

[主板资料](../rev-v2/README.md) · [传感器接线](../../docs/daily/SENSOR_CHANNELS.md)
