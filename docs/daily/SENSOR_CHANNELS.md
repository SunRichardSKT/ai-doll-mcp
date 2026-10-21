# 通道、压力、温度与震动

> 按本页步骤操作即可；无需读完开发者资料。 [全部目录](../README.md)


每个通道保存类型、部位、接口和参数。先选真实已安装的驱动，再设置部位名称。当前 2.12.1 预发布固件支持关闭／模拟／已接入三态；该能力从 2.11 引入，以实际 `get_channel_capabilities` 返回的 `per_port_v1` 为准。

新手先看这一例：FSR 接主板 J1，对应 **CH0、压力、mux_adc、端口 0**；J2 对应 CH1/端口 1，依此类推。“驱动”表示读取传感器的方法，“部位”只是你给这路起的名称。没有安装的通道先关闭。配置完成后按 [压力校准](CALIBRATION_AND_DAILY_MODE.md)检查。

## 可以接什么

| 类型 | 单位 | 已实现接口 |
| --- | --- | --- |
| 压力 `pressure` | `adc_raw`，0～4095 | 模拟、4051 的 8 路 `mux_adc`、GPIO1 `gpio_adc` |
| 温度 `temperature` | `degC` | 模拟、NTC10k/B3950 模拟量、GPIO1 DS18B20 |
| 震动 `vibration` | `percent` 命令强度 | 模拟、GPIO6 / 7 / 10 PWM 加板外驱动 |

最多 16 个逻辑通道，ID 0～15；现有 PCB 只有 8 个 4051 物理输入。增加逻辑 ID 不会增加焊盘。DS18B20 和 GPIO1 ADC 不能同时使用。

## 页面设置步骤

1. 打开设备页或管理中心“通道与校准”，修改类型、部位和驱动。新通道默认模拟。
2. 真实 4051 输入填端口 0～7，不重复占用；GPIO ADC 目前只允许 GPIO1。
3. DS18B20 输入关闭后扫描实际地址，按 [探头指南](DIGITAL_TEMPERATURE.md)绑定。
4. 普通操作直接改部位、端口状态并点**保存此端口**，保留阈值、校准、其他端口和旧历史。已接入表示由用户确认并保存在内核，不靠瞬时零值判断。
5. 换驱动或接线时才展开**硬件高级设置**，参数按实际电路填写；点击**保存硬件高级配置**前保留所有通道。新版全量保存结束当前动作，按明确端口状态恢复输入；物理输出仍关闭。旧版全量调用没有mode时暂停全部输入，需显式重新设置。

部位只是标签，不是执行指令。配置存于设备NVS，重启保留；普通界面无需理解日常／手动模式。见[校准与端口状态](CALIBRATION_AND_DAILY_MODE.md)。

## 压力与模拟

默认八路压力对应 MUX 0～7。保留主板的 4.7k 串联、10k 下拉与滤波电容。真实 FSR 接好后逐路校准。

模拟压力 0 表示释放，非零最多 5 秒自动释放。模拟温度为采样值，不是按压开始 / 结束；模拟震动只记录命令。所有模拟数据标记 `simulation`。

## NTC 温度：接线与参数

模拟量温度使用 **NTC 10kΩ / B3950** 换算；数字温度使用 **DS18B20**，接线和地址绑定见 [数字温度指南](DIGITAL_TEMPERATURE.md)。DHT 等其他驱动尚未安装，不能仅修改名称接入。以下分压和 Beta 参数仅适用于 NTC。

对应分压方向：

```text
3V3 → 串联电阻 → NTC → ADC 节点 → 下拉电阻 → GND
```

如果使用现有 FSR 分支，将 NTC 接在该路原 FSR 的两个端子上，保留已有 4.7k 串联、10k 下拉。温度选项默认如下：

```json
{
  "model": "ntc_b3950",
  "r0_ohm": 10000,
  "beta_kelvin": 3950,
  "pull_down_ohm": 10000,
  "series_ohm": 4700,
  "supply_mv": 3300,
  "offset_c": 0,
  "sample_ms": 1000,
  "report_ms": 30000
}
```

独立 GPIO1 ADC 的串联电阻默认 0Ω，其余值相同；实际有串联电阻时填实际值。这里的电阻参数必须与接线一致，不能拿一组参数套用不同的分压方向。Beta 换算基准为 25℃，未作整机温度标定；`offset_c` 用于实测校准偏移。

换算使用校准后的 ADC 毫伏读数：`R_NTC = R_down × (V_supply / V_ADC − 1) − R_series`，再由 Beta 公式计算温度。温度采样默认每秒一次；变化达到 0.2℃、状态改变或达到报告周期时才记录事件，减少重复日志。

越界、ADC 饱和或无效电阻会返回 `value=null` 和故障状态，AI 不能把故障解释成有效的冷热读数。NTC 暂支持 -40～125℃ 的软件范围；实际探头精度、安装热传导及整机测温效果仍需实测。

ADC 引脚及校准依据见 [Espressif ESP32-C3 ADC 文档](https://docs.espressif.com/projects/esp-idf/en/release-v4.4/esp32c3/api-reference/peripherals/adc.html)。固件使用当前 Arduino 核心的 `analogReadMilliVolts`，没有把 4095 直接视为精确 3.3V。

## 震动：需要板外驱动

FSR 接口是模拟输入，不能接电机。使用独立 GPIO6、7 或 10，通过合适的板外驱动控制；电源、公共 GND 和续流保护按驱动规格连接。

真实输出默认关闭，只有用户确认驱动后才调用 `set_output_enabled(enabled=true, external_driver_confirmed=true)`。PWM 为 200Hz、8 位，强度 0～100%，时长 1～5000ms，超时关闭；强度 0 立即停止。

重启或关闭输出不会重放命令。日志 `direction=output` / `source=actuator` 只证明控制命令，不证明电机实际转动。NTC、DS18B20 和电机仍未接线验收；CH0 压力输入已实测。

## AI 和开发者怎样加通道

先读完整 `get_channel_config().channels`，保留全部旧行，再追加 / 修改后提交 `set_channel_config`。只提交新行会替换旧配置。不要把模拟 ID 8 / 9 当成第九 / 第十个 MUX 接口。

逐事件用 `query_device_history` / `get_interaction_device_events`；压力汇总用 `query_touch_history` / `get_interaction_events`，游标不混用。记录包括类型、方向、单位、质量、来源、通道及发生时部位。

新增驱动需实际实现：`channel_devices.h` 声明能力和资源，`touch_events.h` 负责采样 / 输出，`channel_rpc.h` 提供接口。只改名称不能接入 DHT、I²C 或 SPI 新硬件。开发与测试见 [开发指南](../developers/DEVELOPER_GUIDE.md)。
