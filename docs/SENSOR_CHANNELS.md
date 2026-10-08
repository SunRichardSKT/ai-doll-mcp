# 多传感器与震动输出使用说明（v2.3）

电脑服务为 Bridge v2.5，STDIO 为 33 工具；支持 [Wi-Fi 采集](WIFI_CONNECTION.md)，v2.3 增加压力校准、日常模式和诊断曲线，原驱动保持。主动订阅及反馈偏好见 [主动互动指南](PROACTIVE_INTERACTION.md)。

固件 `doll-lab-2.3.0`。通道不再只能表示 FSR；每个通道保存类型、部位/用途、接口、启用状态和参数。当前提供压力、温度、震动三种预设。

## 通道与硬件

最多配置 16 个**逻辑通道**，ID 为 0～15，可以保留空号。现有 PCB 的 74HC4051 仍只有 8 个物理输入端口，逻辑通道数量增加不会增加物理接口，也不会改动已下单 PCB。

| 类型 | 方向 | 单位 | 已实现接口 |
|---|---|---|---|
| `pressure` 压力 | 输入 | `adc_raw`，0～4095 | 模拟、4051 输入、GPIO1 ADC |
| `temperature` 温度 | 输入 | `degC`，℃ | 模拟、NTC10k/B3950 经 4051 或 GPIO1 ADC |
| `vibration` 震动 | 输出 | `percent`，0～100% 命令强度 | 模拟、独立 GPIO6/7/10 PWM |

每个通道可自由命名为部位/用途，例如“左手压力”“腹部温度”“胸口震动”。类型和接口需从已支持的选项中选择；名称只作为数据标签，不是对 AI 的指令。

八个已有压力通道自动沿用旧的部位名称，并映射到原来的 4051 端口 0～7。新配置保存在 ESP32 NVS，重启恢复；超过 NVS 字符串大小的配置使用 blob 保存。默认手动模式重启关闭真实采样；用户确认接线并保存日常模式后可恢复输入。真实输出始终不会自动恢复。完整配置保存会取消日常模式。见 [校准与日常模式](CALIBRATION_AND_DAILY_MODE.md)。

## 在页面上设置

电脑通过 Wi-Fi 或 USB 运行采集服务后打开 <http://127.0.0.1:8768/companion>，或在同一局域网打开设备设置页。

1. 在“通道类型与部位”中修改名称、选择类型和接口。添加通道时分配一个未使用的 ID，默认“仅模拟”。改变类型也先切回“仅模拟”，请再选择所需接口。
2. 真实 4051 输入选择 `mux_adc`，填写端口 0～7；不同通道不能占用同一端口。独立 ADC 使用 `gpio_adc`，当前只允许 GPIO1。
3. 展开“阈值 / 温度参数”可设置压力阈值和温度换算参数。保留 `{}` 时使用该类型默认值。
4. 点击“保存全部配置”。这是完整配置替换，不是仅修改一行；保存会结束当前按压/震动命令，并关闭真实输入、输出。历史记录不改写。
5. 在模拟输入区域选择压力或温度通道，发送数值。震动输出在独立区域测试。“仅模拟”震动只记录命令，不会驱动电机。
6. 实物传感器接好后才勾选真实输入。电机驱动接好并确认后，才允许真实 PWM 输出。手动模式重启、再次保存完整通道配置后需要重新启用；日常模式只恢复输入。

压力模拟 0 表示释放，非零值最多保持 5 秒。温度模拟是一个采样值，不会被当作触摸开始/结束。震动持续时间为 1～5000ms，超时自动停止，强度 0 可立即停止。

## 温度预设与接线

此版本的真实温度预设是**NTC 10kΩ / B3950 热敏电阻**，不是 DS18B20、DHT 或其他数字探头；这些探头需要以后增加对应驱动，不能仅改名称就接入。

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

越界、ADC 饱和或无效电阻会返回 `value=null` 和故障状态，AI 不能把故障解释成有效的冷热读数。温度暂支持 -40～125℃ 的软件范围；实际探头精度、安装热传导及整机测温效果仍需实测。

ADC 引脚及校准依据见 [Espressif ESP32-C3 ADC 文档](https://docs.espressif.com/projects/esp-idf/en/release-v4.4/esp32c3/api-reference/peripherals/adc.html)。固件使用当前 Arduino 核心的 `analogReadMilliVolts`，没有把 4095 直接视为精确 3.3V。

## 震动输出接线与限制

当前 PCB 的 FSR 接口是模拟输入。震动电机应使用单独的 GPIO6、GPIO7 或 GPIO10，经过板外 MOSFET/三极管或适配驱动模块控制；电机供电、驱动、续流保护及公共 GND 按所用电机和驱动规格接好。GPIO 和 4051 均不直接接电机负载。

真实 PWM 默认关闭。调用 `set_output_enabled(enabled=true, external_driver_confirmed=true)` 之前，应由用户确认驱动接线；未经确认时非零震动命令会被拒绝。模拟接口不需要真实输出开关。

真实输出使用 200Hz、8 位 PWM，强度表示占空比命令，不是实测震动幅度。每次命令最长 5 秒，真实输出另有 ESP 定时器关闭 PWM；关闭输出或改配置会停止所有正在执行的命令。软件重启后不会恢复震动。

日志中的 `direction=output`、`source=actuator` 表示控制命令，不表示电机已实际转动。没有额外反馈传感器时，系统无法确认电机是否正常震动。本轮未验证实际电机驱动或实物 NTC。

## MCP 操作

电脑端 MCP 当前共 33 个工具，开发板 HTTP MCP 共 16 个。更新后重新连接 MCP 客户端，刷新工具列表。

| 新工具 | 用途 |
|---|---|
| `get_channel_capabilities` | 查询已安装类型、接口和实际资源限制 |
| `get_channel_config` / `set_channel_config` | 读取/完整替换类型、名称、绑定及参数 |
| `read_channel_values` | 查询数值、单位、来源、时间及有效性 |
| `set_input_enabled` | 开关真实输入，保留每路阈值 |
| `simulate_channel_input` | 压力/温度模拟输入；温度可用毫伏模式测试换算 |
| `set_output_enabled` | 确认驱动后启用真实 PWM，或停止全部输出 |
| `set_vibration` | 指定通道、强度和持续时间 |
| `query_device_history` | 按日期、部位、类型、输入/输出查询完整事件历史 |
| `get_interaction_device_events` | 查询当前互动会话的所有类型新事件，可有界等待 |

AI 先读取能力和现有配置，再决定工具参数。`set_channel_config` 必须提交希望保留的全部通道。比如在现有八路压力之外添加模拟温度和模拟震动时，先取 `get_channel_config().channels`，追加：

```json
[
  {"channel": 8, "name": "腹部温度", "type": "temperature", "driver": "simulation", "enabled": true, "options": {}},
  {"channel": 9, "name": "胸口震动", "type": "vibration", "driver": "simulation", "enabled": true, "options": {}}
]
```

随后把原八路和新增两路一起提交。逻辑 ID 8/9 不代表 4051 有第 9/10 路接口。

示例调用：

```text
simulate_channel_input(channel=8, value=32.5, unit="degC")
set_vibration(channel=9, intensity=40, duration_ms=500)
query_device_history(sensor_type="temperature")
query_device_history(direction="output")
```

旧 `doll_simulate_press`、部位映射、压力历史和互动查询保留。`query_touch_history`/`get_interaction_events` 只返回压力按压记录；新 `query_device_history`/`get_interaction_device_events` 返回逐条事件，有独立的游标，不能混用。

新事件包含 `sensor_type`、`direction`、`unit`、`value`、`quality`、`source`、`channel` 和发生时的部位名称。普通模式安静归档；用户主动开始互动后才按该会话的新事件反馈。温度定期报告和 AI 自己发出的震动命令不会延长互动空闲超时，也不能解释成用户又触摸了娃娃。

## 后续扩展方式

通道、驱动、当前读数和历史事件分开处理。固件在 `channel_devices.h` 中声明已安装能力、绑定和参数验证，在 `touch_events.h` 中实现采样/输出与事件生成，在 `channel_rpc.h` 中公开接口。新增硬件驱动必须实际实现后再出现在能力列表；不接受未安装类型或驱动。

电脑 MCP 配置对象允许由固件声明的类型/驱动名称，通过设备统一验证，通用归档使用类型标识、单位及方向处理事件。因此以后增加数值型传感器不必重新设计历史表，也不必每次修改 Python 的类型枚举。若新增 I²C、1-Wire、SPI 或外部多路器，需要实现相应驱动、资源冲突检查和硬件接线；当前版本尚未提供这些驱动。

测试见 `tools/test_channel_devices.py` 和 `docs/DEVICE_LAB_TEST_REPORT.md`。测试会临时配置明确标记的模拟通道、执行一次软件重启，最后恢复原通道；不要在用户正在互动或真实采样时运行。
