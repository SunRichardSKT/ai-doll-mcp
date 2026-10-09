# MCP 工具目录

电脑端 STDIO MCP 提供 **45 个工具**。完整历史、人设、会话和事件桥请连接 `tools/companion_mcp.py`。设备 `/mcp` 提供 **26 个设备工具**，包含采集器使用的补传确认和校时；它不保存电脑长期历史，也不直接调用模型。

## 设备与通道（10）

| 工具 | 用途 |
|---|---|
| `doll_get_status` | 设备、网络、存储和 OTA 状态 |
| `doll_set_led` | 测试板载灯，随后恢复网络指示 |
| `get_body_map` / `set_body_map` | 读取/保存全部通道部位名称 |
| `get_channel_capabilities` | 类型、驱动、单位、资源和物理限制 |
| `get_channel_config` / `set_channel_config` | 读取/原子替换完整通道配置 |
| `read_channel_values` | 当前读数、单位、来源、有效性与故障 |
| `scan_input_devices` | 输入关闭时扫描 GPIO1 DS18B20 地址 |
| `set_input_enabled` | 真实输入开关，保留各路参数 |

## 输入、输出与运行模式（8）

| 工具 | 用途 |
|---|---|
| `get_sensor_config` / `set_sensor_config` | 压力采样状态及统一阈值设置；独立阈值使用通道配置 |
| `doll_simulate_press` | 压力模拟，0 释放，非零最多 5 秒 |
| `simulate_channel_input` | 按类型模拟压力或温度；数字温度不接受毫伏换算 |
| `set_output_enabled` | 关闭全部输出或确认外置驱动后开启许可 |
| `set_vibration` | 指定通道强度/时长，最长 5 秒 |
| `get_operating_mode` / `set_operating_mode` | 手动/日常启动策略；daily 要求硬件确认 |

## 压力校准（4）

| 工具 | 用途 |
|---|---|
| `capture_pressure_calibration` | channel、stage=0/1/2、duration_ms=500..10000，非阻塞采集 |
| `get_pressure_calibration` | 进度、统计、推荐阈值和失败原因 |
| `apply_pressure_calibration` | 显式保存有效推荐值 |
| `cancel_pressure_calibration` | 取消且不保存 |

见 [八路 FSR 校准](CALIBRATION_AND_DAILY_MODE.md)。未接传感器、采样关闭或模拟数据不能完成真实校准。

## 人设、历史与互动（11）

| 工具 | 用途 |
|---|---|
| `get_persona` / `set_persona` | 读取/保存用户指定的人设 |
| `query_touch_history` | 压力按压汇总，释放后补充时长 |
| `query_device_history` | 压力/温度/输出逐事件历史 |
| `start_interaction` / `end_interaction` | 开始/结束绑定到一个聊天的互动会话 |
| `get_interaction_status` | 当前会话及采集状态 |
| `get_interaction_events` | 会话内压力记录；独立游标 |
| `get_interaction_device_events` | 会话内混合事件；独立游标，可等待最多 20 秒 |
| `summarize_interactions` | 带原始事件引用的客观压力动作摘要 |
| `get_event_storage_status` | 设备离线缓存、覆盖计数和时间状态 |

查询按日期使用 Asia/Shanghai；处理 has_more/next_cursor。模拟不表示实物互动，输出不表示用户触摸，无效温度不当有效读数。互动会话不自动替用户订阅后台事件。

## 反馈与安装（5）

| 工具 | 用途 |
|---|---|
| `get_feedback_preferences` / `set_feedback_preferences` | 语气、称呼、避用词、触发策略和安静时段 |
| `get_reply_bridge_status` | 订阅、投递及保存的模型/演示回执 |
| `get_installation_status` | 本机环境、连接和设备自检；不声称宿主已注册或支持事件 |
| `discover_paired_device` | 验证已配对设备，显式选择是否更新 IP |

## 历史管理（7）

| 工具 | 用途 |
|---|---|
| `export_history` | 分页 JSON/CSV 导出 |
| `get_history_statistics` | 完整筛选范围统计 |
| `preview_history_deletion` / `delete_history` | 删除预览和带确认的执行 |
| `get_history_retention` | 保留策略、最近执行及异常 |
| `preview_history_retention` / `set_history_retention` | 保留期限预览和保存，默认不启用 |

删除和启用保留期限遵循用户明确意图，先检查具体预览。详见 [历史管理](HISTORY_MANAGEMENT.md)。无线升级通过设备设置页或专用命令行，不由传感器事件自动触发，见 [OTA](OTA_UPDATE.md)。
