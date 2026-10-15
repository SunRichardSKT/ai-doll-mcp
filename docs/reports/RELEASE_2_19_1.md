# 2.19.1～2.19.3：Operit 1.12.2 兼容性修正

用户报告 `Failed to parse toolpkg file`，随后确认使用 Operit **1.12.2**。这与联网和传感器数据无关。

## 已定位的错误

使用官方 `v1.12.2` 标签（提交 `dbf71916fae9750cfdc9f9a774f5a0fee56633fb`）对应的 JavaScript 注册运行时，在 Node 中复现旧入口失败：

```text
registerToolPkgToolboxUiModule requires a serializable screen reference
```

该版本在注册时将 `.ui.js` 模块作为带路径标记的占位函数返回。旧入口直接取 `.default`，得到空引用；普通 CommonJS 模块测试没有覆盖这个差异。现已同时接受函数引用和 `exports.default`，保留宿主所需的模块路径标记。

新子包使用独立名称 `ai_doll_companion`，避免与旧独立 `ai_doll.js` 冲突；工具元数据显式默认启用。容器 ID 和插件数据目录保持不变，既有手机设置不删除；电脑 MCP 工具名称不变。

## 检查与交付

- 新回归会先证明旧入口失败，再检查修正后的两种模块返回格式。
- 使用该标签的实际 JS 注册运行时复现错误并验证修正；Android 原生桥用明确的替身，不能据此称手机已安装成功。
- 构建入口先运行注册格式检查，失败不生成工具包。官方源码只缓存于本机 `build`，不加入交付包。
- 原配置、工作流归属、发送恢复和模拟互动检查继续使用统一源码。
- 提供更新后的单个 ToolPkg 以及 Windows / Linux 完整 **2.19.1** 制品，不制作另一个增量安装包。

维护者可运行：

```powershell
.\python\python.exe tools/prepare_operit_registration_check.py
node tools/test_operit_registration.cjs --upstream build/integration-research/operit-1.12.2/runtime
node tools/test_operit_unified.cjs
```

手机需重新下载并导入新版 `.toolpkg`。解析通过后的设置显示、后台自检输入与实际回复仍须在用户手机分别确认。[统一操作指南](../integrations/OPERIT_SETUP.md)。

依据：[1.12.2 模块执行器](https://github.com/AAswordman/Operit/blob/v1.12.2/app/src/main/java/com/ai/assistance/operit/core/tools/javascript/JsExecutionScriptBuilder.kt)、[注册引用解析](https://github.com/AAswordman/Operit/blob/v1.12.2/app/src/main/java/com/ai/assistance/operit/core/tools/javascript/JsToolPkgRegistration.kt)。

## 2.19.2：面板找不到 list_chats

用户随后报告 `Tool not found org.ai_doll.companion:list_chats`。工具注册在子包 `ai_doll_companion`，容器 `org.ai_doll.companion` 仅拥有设置页面，不提供同名工具。

1.12.2 的 Compose JS 桥在原生命名解析没有有效结果时，会用 `packageName` 拼接工具名；旧面板同时传容器和子包，回退结果落到了容器。现改为所有面板操作直接调用 `ai_doll_companion:<工具名>`，不在失败后尝试另一个写入目标，避免重复执行。

旧测试只取冒号后的方法名，没能发现错误前缀。现已严格校验完整名称，并通过官方该版本的 JS Context 桥重现旧错误，验证实际设置页面能够列出聊天、确认绑定和执行连接检查。Android 工具仍为替身，真实手机结果继续单独验收。

```powershell
node tools/test_operit_ui_bridge.cjs
```

电脑管理页下载和完整包更新至 **2.19.2**。手机替换工具包后重新打开面板；如宿主提示同名包已存在，使用包管理删除旧的外部工具包文件条目再导入，不清理 `plugins/org.ai_doll.companion` 数据目录。此前的连接文件、绑定和发送记录保持同一路径。

依据：[1.12.2 UI Context 桥](https://github.com/AAswordman/Operit/blob/v1.12.2/app/src/main/java/com/ai/assistance/operit/core/tools/javascript/JsComposeDslBridge.kt)。

## 2.19.3：工作流结构误判

用户报告“AI Doll 工作流结构不完整”。核对 1.12.2 的 `ToolResultData.toJson()` 和 `WorkflowNode` 模型：序列化使用 `__type` 类别标记，未开启默认字段输出。节点的 `type="trigger"` / `type="execute"`、手动触发的 `triggerType="manual"` 可被省略；执行参数则返回 `ParameterValue.StaticValue` 对象，而不是创建时传入的字符串。

旧测试直接回传创建参数，未覆盖上述差异。将替身改为该版本原生序列化形状后，旧代码复现了用户的同一报错。修正后按明确节点类别还原默认值，兼容显式类型，并在安排任务后回读核对任务编号、一次性时间、连线和启用状态。

“一键检查”只修复已保存编号且安装归属一致的工作流；原地更新后保持停用，不新建重复项。后台任务尚未停止时不修复；归属不符或写入失败时保留原状态并报错。停止操作仍可停用本安装的残缺工作流。连接、聊天绑定、发送记录及未决回执保持原样。

回归覆盖省略默认字段、显式类型、残缺连线修复、外部工作流拒绝、活动任务保护、修复失败、创建回读失败后的幂等重试、任务参数核对，以及官方 1.12.2 JS UI 桥和声明的 MCP SDK。Android 工作流原生接口仍使用替身，手机调度和原模型实际回复需继续实测，不能用本机结果替代。

交付更新为单个 `AI_Doll_Operit.toolpkg` 和完整 2.19.3 制品，不制作增量修复包。

依据：[结果序列化](https://github.com/AAswordman/Operit/blob/v1.12.2/app/src/main/java/com/ai/assistance/operit/core/tools/ToolResultDataClasses.kt)、[工作流模型](https://github.com/AAswordman/Operit/blob/v1.12.2/app/src/main/java/com/ai/assistance/operit/data/model/Workflow.kt)。
