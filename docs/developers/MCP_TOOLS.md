# MCP 工具目录

> 开发者参考；普通用户可以跳过。 [全部目录](../README.md)


先按 [连接方式](../start/MCP_TRANSPORT_DECISION.md)安装。工具不会自行启动 AI 对话；实际可用范围以当前客户端发现的 schema 为准。

本页跟随本地 **2.25.0 候选版／固件 2.13.0**，候选文件由本机 `delivery/` 提供，尚不表示已发布到 GitHub。2.24.1／2.12.1 等旧安装以实际工具发现为准。

## 不同连接有多少工具

| 连接 | 数量 | 数据与用途 |
| --- | --- | --- |
| 电脑 STDIO：`tools/companion_mcp.py` | 52 | 2.25.0候选；设备管理、端口状态、电脑历史、人设、会话与维护 |
| 设备 `/mcp` | 30 | 2.13.0固件；设备操作、端口状态、归档租约、缓存确认和校时；没有电脑长期历史 |
| HTTP `status` | 2 | `get_installation_status`、`doll_get_status` |
| HTTP `history` | 9 | status，加能力、配置、人设、偏好、历史、摘要、统计 |
| HTTP `interaction` | 19 | history，加会话和六个自然陪伴工具 |

history 的七个附加工具为 `get_channel_capabilities`、`get_channel_config`、`get_persona`、`get_feedback_preferences`、`query_device_history`、`summarize_interactions`、`get_history_statistics`。interaction 再增加 `start_interaction`、`get_interaction_status`、`get_interaction_device_events`、`end_interaction`。

本机 HTTP 网关默认 `127.0.0.1:8771/mcp`；私密远程网关和 Secure 使用专用入口。GET返回405时不等于服务离线，客户端使用POST。interaction允许部位、单端口状态和陪伴偏好的局部写入，不开放模拟注入、完整硬件配置、删除或执行器控制。status/history仍只读。

设备／STDIO提供`set_channel_state(channel, mode?, name?)`。mode为`off/simulation/connected`，必须先实际发现固件的`port_state_model=per_port_v1`。远程保持19个工具，经`update_body_part(channel, changes={mode:...})`使用同一局部操作，不对离线设备排队。改名不改变校准、采样和其他端口。连接状态来自保存的安装确认，不是自动插拔检测。`update_companion_preferences`另支持`persona_source=chat/doll`及`doll_persona`，只控制身体互动反馈，不改宿主聊天配置。

## 设备内部归档接口（2.13.0）

设备状态及 `event_storage` 返回 `archive_lease_supported:true`。以下三个工具用于采集器协调，未加入电脑 STDIO 或远程 HTTP 的工具允许列表；HTTP `status/history` 继续只读，`interaction` 继续保持原19个工具。

| 工具／调用 | 输入与结果 |
| --- | --- |
| `acquire_archive_lease` | `collector_id` 为1～96字符的稳定安装标识，允许字母、数字及 `_ - : .`；`collector_kind` 为 `phone/computer/server`。返回 `lease_id`、当前 `boot_id`、`expires_in_sec`。 |
| `renew_archive_lease` | 输入 `lease_id`，仅延长匹配的当前租约，返回相同字段。 |
| `release_archive_lease` | 输入 `lease_id`，释放匹配租约；已过期时可重复释放，不会清除另一持有者的租约。 |
| `get_touch_events` | 原参数保持，新增可选 `archive_lease_id`。持有者读取 `include_persistent:true` 才推进该租约的已交付游标；不带租约仍可复制读取，不获得确认权限。 |
| `acknowledge_events` | 输入当前响应外层的 `boot_id`、`storage_epoch`、`storage_cursor` 和 `archive_lease_id`；只确认该持有者已读且已可靠归档的游标。 |

租约固定90秒，采集器每30秒续租；重启清空。相同 `collector_id/collector_kind` 重新申请可恢复仍有效的租约，不更换 `lease_id` 或丢掉已交付游标；其他归档端得到占用错误。状态只给持有者类型和剩余时间，不返回租约凭据。三个租约工具明确标注 `readOnlyHint:false`，设备 OTA 期间仍允许申请、续租和释放。

电脑将稳定的 `archive_collector_id` 保存于现有 SQLite 设置中，归档提交后才 ACK，正常采集线程停止时释放；强制结束进程或断网后由设备期限回收。设备直传占用内部 `server` 租约，启用期间外部不能申请；切换归档通路先正常停止旧端。写入或 ACK 不做无条件自动重试，读取页、当前启动和租约状态需要重新核对。

旧客户端在2.13.0上仍可查询，但不带有效租约的 ACK 会失败，不能靠手工确认或清缓存跳过。新手机和新电脑采集器遇到旧固件时默认复制归档、不自动 ACK；电脑状态返回 `archive_mode:legacy_copy_only`。旧Flash接口不能在不ACK的情况下翻过最前24条，完整补传与清理需升级固件；电脑另读RAM页以免积压遮住实时输入。以上均不能证明用户已经升级固件，见 [固件清单](../../firmware/prebuilt/FLASH_MANIFEST.json)。

## 自然陪伴（新增 6 个工具）

| 工具 | 用途 |
| --- | --- |
| `get_settings_entry(section)` | body/feedback/status/hardware 链接与访问条件，不自动打开浏览器 |
| `get_device_overview()` | 在线状态、最近同步、启用通道、有效读数与订阅状态 |
| `get_chat_context(chat_id, after=0, limit=50, session_id=None, through=None)` | 最近未处理触摸、部位元数据、人设和偏好；返回稳定事件标识与 receipt_id |
| `acknowledge_chat_context(chat_id, receipt_id)` | 处理完成后确认，按聊天隔离、重复确认幂等；不证明展示 |
| `update_body_part(channel, changes)` | name/aliases/feedback_level(off/light/normal)/interaction_hint；保存名称不重置采样校准 |
| `update_companion_preferences(changes)` | 局部修改 chat_integration_enabled/proactive_enabled，以及 feedback/policy |

读取上下文不消费事件。默认 after=0 查询近期未确认事件；分页时处理并确认本页后再用 next_cursor；游标不是确认凭据。释放位于 updates，不产生主要反馈；单页最多 200。名称失败返回 updated=false、name_sync=not_confirmed，先核对设备，不能自动重发。新增工具在电脑与 Linux 直传一致提供，使用规则见 [自然陪伴](../daily/NATURAL_COMPANION.md)。

2.24的活动监听可提交当前聊天有效`session_id`及本页最大编号`through`，一次读取整批触摸而不按普通聊天冷却删除独立按压；普通调用不传时行为保持。读取后仍需要按回执确认，不能以游标代替。

## 会话调用共同规则

`start_interaction` 的可选 `duration_sec` 为 1～3600 秒，服务器到期结束；省略时兼容旧调用，重复开始不延长期限。远程读取 / 结束要提交当前聊天的 `chat_id` 与 `session_id`，每次等待 0～20 秒。

保持游标并分页；压力汇总和逐事件历史使用不同游标。历史读取不触发同步，后台采集器负责归档；离线时仍可返回已存历史和同步状态。模拟与故障值需明确标记。

## STDIO 的原有 45 个工具

以下按任务分组，斜线合并的名称分别计数。具体参数以实时 schema 为准。


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

见 [八路 FSR 校准](../daily/CALIBRATION_AND_DAILY_MODE.md)。未接传感器、采样关闭或模拟数据不能完成真实校准。

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

删除和启用保留期限遵循用户明确意图，先检查具体预览。详见 [历史管理](../daily/HISTORY_MANAGEMENT.md)。无线升级通过设备设置页或专用命令行，不由传感器事件自动触发，见 [OTA](../daily/OTA_UPDATE.md)。

## 可选提示模板

STDIO 的 `doll_chat_companion` 是提示模板，不计入工具数；不会调用设备或开启会话。客户端没有提示菜单时使用 [聊天测试请求](../integrations/CHAT_MCP.md)。AI 执行规则见 [AI 指南](../ai/AI_GUIDE.md)。
