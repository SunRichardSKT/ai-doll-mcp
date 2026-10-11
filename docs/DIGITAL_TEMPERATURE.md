# DS18B20 温度探头

用于真实数字温度输入。没有探头时可以模拟摄氏度，但不能当作探头验收。最多 16 个逻辑通道与八路 MUX 的限制见 [通道指南](SENSOR_CHANNELS.md)。

## 先接线

三线外部供电：**VDD → 3V3，GND → 公共地，DQ → GPIO1**，DQ 与 3V3 之间接 4.7k 上拉。确认实际探头线序，不接 5V，不接 FSR 端子。当前不支持寄生供电。

多个探头共享 GPIO1，但 ROM 地址必须不同；GPIO1 不能同时用于 `gpio_adc`。原八路 MUX ADC 使用 GPIO0。线长和多探头电气效果仍需实测，参考 [制造商手册](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf)。

## 页面配置

1. 关闭真实输入，移除 GPIO1 ADC 冲突绑定并保存。
2. 添加温度通道，选择 DS18B20、GPIO1。
3. 扫描并选择实际地址，填写部位；扫描不自动保存或开启输入。
4. 保存全部通道，确认旧压力行仍保留。
5. 检查接线后启用输入，需要重启恢复时保存日常模式。

ROM 为总线字节顺序的 16 位十六进制字符串，含型号与 CRC。不要填测试地址；换探头后重新扫描。

## 参数和故障

采样至少 1000ms，报告间隔不小于采样，偏移 −30～30℃。数字温度不用 NTC 电阻或毫伏参数。正常单位 `degC`；断线、CRC、寄生供电、越界返回故障及空值，不是 0℃。

驱动分阶段转换，至少等待 750ms 再读。85℃保守标记 `power_on_or_85c`，因上电默认值与真实 85℃无法只凭数值区别；此实现不适合必须判断恰好 85℃的用途。关闭输入 / 改配置 / 重启取消未完成转换。

## MCP 配置参考

`scan_input_devices(driver="ds18b20", gpio=1)` 仅输入关闭且无 GPIO1 ADC 绑定时允许；无探头返回 `no_device_found`。读取旧通道后追加如下结构，替换真实 ROM，再完整保存：

```json
{
  "channel": 8, "name": "腹部温度", "type": "temperature",
  "driver": "ds18b20", "gpio": 1, "rom": "替换为16位实际地址",
  "enabled": true,
  "options": {"model":"ds18b20","offset_c":0,"sample_ms":1000,"report_ms":30000}
}
```

算法、扫描页面、配置冲突及无探头提示通过软件 / 裸板测试；真实精度、线长和多探头时序尚未验证。见 [验证汇总](VALIDATION.md)。
