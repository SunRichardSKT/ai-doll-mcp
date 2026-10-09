# 将娃娃接入正在使用的 AI 对话

安装一次 MCP 后，用户继续使用原来的 AI 聊天窗口、模型和聊天上下文。娃娃提供身体互动数据，回复由当前 AI 产生；设备设置页面用于配网、校准、部位配置和日志，不承担聊天功能。无需为了娃娃另填一份模型 API 密钥。

## 用户操作

1. 按 [安装指南](AI_INSTALL.md) 安装电脑采集服务并配对设备。设备可用 Wi-Fi，电脑服务仍需运行。
2. 在原 AI 客户端导入生成的 `ai_doll` MCP 配置，刷新工具连接。如果客户端只能在创建聊天时启用工具，这是该客户端的限制，不能由设备绕过。
3. 让当前 AI 读取设备状态、通道、人设与反馈偏好。正常聊天时触摸安静记录；想回顾时直接说“查询今天的互动”。
4. 想即时互动时说“我要和你互动，先测试 60 秒”。AI 进入本对话的互动会话并等待新事件。按压后由当前 AI 结合本对话内容回应。
5. 说“结束互动”后停止即时反馈，普通归档继续。

支持 MCP prompts 的客户端可以在提示模板菜单选择 `doll_chat_companion`，将操作指引加入当前对话。它只是可选指引，不会自动开始监控或修改设备。MCP prompts 由用户选择，是否显示该菜单取决于客户端，见 [协议说明](https://modelcontextprotocol.io/specification/draft/server/prompts)。没有菜单时，把下面的请求发送给当前 AI 即可。

> 请在我们当前对话使用 ai_doll MCP。先实际检查连接，读取通道、人设和反馈偏好，保留我们现有的聊天上下文。正常触摸只归档；我说开始互动时进入本对话的会话，按新事件的部位、数据和来源回应。我说结束时结束会话。不要擅自开启真实采样或震动，不凭文档声称设备已连接。先进行 60 秒测试，每次等待不超过 20 秒，保存会话 ID 和游标；没有动作时保持安静。当前是无传感器开发板，我会从设备设置页模拟按压，请明确区分模拟和真实触摸。

## 主动反馈需要哪一层支持

| 当前环境 | 本项目接入方式 | 能做到什么 |
|---|---|---|
| 本机工具型 MCP 客户端 | 原聊天启用 STDIO MCP | AI 查询历史；正在运行的互动任务可有限等待新事件并在原对话回答 |
| 有事件能力的 AI 宿主 | 原聊天授权订阅 `doll.interaction` | 宿主收到新事件后运行当前 AI；需实际验收订阅、接收和展示 |
| 用户自建应用 | 原前端/后端接入 `DollBridgeClient` | 原后端使用同一聊天上下文和模型，原消息列表追加回复 |

普通 MCP 工具可调用，不等于聊天空闲后还能自动唤醒。单独运行一个监听脚本只能收集事件；脚本必须有宿主提供的对话投递入口，才能让该 AI 回应。项目不会通过抓取窗口或模拟按键发送消息来伪装统一适配。

OpenAI 当前文档列出的 MCP Events 场景为网页 Work、桌面 Work Cloud 和 dots；其接入采用 webhook，且要求 MCP 2.0。不能把这个能力泛化为所有普通聊天。见 [官方事件说明](https://developers.openai.com/plugins/build/mcp-events)。本项目事件端点已提供，但用户账号、连接授权和实际聊天投递仍需验证。

## 给已有应用的开发者

接入原消息处理流程，不另外建立聊天产品。传感器事件作为附加上下文，并不代替用户输入；上下文由你的现有后端读取，模型、密钥和计费方式也沿用该后端。

使用 [事件桥适配器](PROACTIVE_INTERACTION.md) 时：

- `targetId` 使用原应用稳定的聊天 ID，切换聊天或结束互动时取消旧订阅；不能把事件发往当前恰好可见的其他窗口。
- `onInteraction(event, context)` 把事件送进原后端的聊天任务队列，等待正在生成的普通回复完成，再使用最新上下文生成互动回复。队列需支持 `context.signal`，取消后不得开始新的生成。
- `context.idempotencyKey` 是事件 ID，后端持久保存生成结果；重复投递返回原结果。`subscriptionId` 与 `lease` 可供后端验证投递归属。
- `onDeliveryState(busy, event)` 覆盖生成、ACK 和展示过程，供原界面显示互动状态或安排输入队列；它不承担模型调用。
- 仅在 `onReply(answer, event)` 中按事件 ID 去重追加原消息列表。适配器先完成 ACK，再调用它；结束互动后不展示迟到生成。
- 提供明确的“开始/结束互动”入口，普通模式不订阅；模型失败不要用固定演示文字冒充 AI 回复。

### 与普通消息共享顺序

`tools/conversation_queue.js` 提供 `DollConversationQueue`，可在浏览器或 Node 中使用，不包含聊天页面和模型服务。必须让普通消息和完整事件投递经过同一个队列，不能只给模型生成排队；否则下一条消息可能在互动回复写入记录前读取上下文。

下面接入片段中的 `existingSendAndSave`、`existingGenerateDollReply`、`existingAppendAssistant` 都是原应用已有的处理函数，不是本项目另建的模型接口。在原页面加载 `/conversation-queue.js` 和 `/bridge-client.js`，或把这两个文件接入原应用构建：

```javascript
const queue = new DollConversationQueue(); // 应用只创建一个共享实例
const chatId = currentConversation.id;     // 固定捕获原对话 ID，不读取切换后的窗口 ID
const bridge = new DollBridgeClient({
  csrf: pageCsrf,
  targetId: `my-app-chat:${chatId}`,
  runDelivery: (operation, {signal}) => queue.run(chatId, operation, {signal}),
  onInteraction: (event, context) => existingGenerateDollReply(chatId, event, context),
  onReply: async (answer, event, {signal}) => {
    if (signal.aborted) return;
    // 异步持久化应由原后端验证取消/归属并按 eventId 幂等提交。
    await existingAppendAssistant(chatId, answer.text, event.eventId, {signal});
  }
});

// 替换原“发送消息”入口的外层，内部仍使用原来的生成和保存流程。
function sendOrdinaryMessage(text, signal) {
  return queue.run(chatId, () => existingSendAndSave(chatId, text, {signal}), {signal});
}
// 用户开始互动：await bridge.start();
// 用户结束/切换聊天：await bridge.stop();
```

`runDelivery` 将生成、ACK、写入原消息记录作为一个任务。等待原聊天生成期间继续续租；取消等待中的互动不会运行模型，也不会阻止后续普通消息。活动任务取消后仍需等原处理函数结束才能让下一任务进入，避免未完成生成与新请求并行。原处理函数必须处理传入的 `signal`，尤其异步写入期间需要在实际提交前检查，不能依靠前端撤回已提交内容。

队列默认每个聊天最多 64 个活动/等待任务；不同聊天互不阻塞。队列只在当前进程/窗口内有效，多个窗口或后端工作进程仍要使用原后端共享的会话锁和持久去重。网络重试、页面重载及 ACK 后应用写入失败的恢复也由原后端处理；本地队列不保证分布式恰好一次。

### 开始、结束与切换聊天

重复调用同一实例的 `start()` 会共享同一次启动，返回同一订阅；不会创建两个监听。启动过程中调用 `stop()` 会立即取消本地启动意图，等待已发出的创建请求返回真实 ID 后清理。新的 `start()` 会等这次结束完成，再进入互动。

切换聊天时先停止旧实例，再为新聊天创建实例；原对话的普通消息处理照常继续。取消订阅失败时仍会尝试结束会话；结束失败时保留未清理的 ID，`stop()` 返回错误。恢复连接后重试 `stop()`，清理成功前不会自动重新监听。不要把本地停止等同于服务器操作已经完成，尤其请求响应遗失时应重新核对 `get_interaction_status` 和事件桥状态。

接口保留稳定聊天 ID 的归属检查，不会因为别的聊天占用而抢占。旧流在停止后返回的迟到响应会被忽略，不能关闭新聊天的监听。

设置页和 `/bridge` 是设备管理与传输诊断。`/bridge` 的演示回执带有“非 AI”标记，不能当作原聊天响应验收。

## 验收

正确验收要在用户原来的聊天内完成：普通消息可正常回复；普通触摸只归档；开始互动后的新按压得到同一 AI 的上下文相关反馈；重复事件不重复展示；结束或切换聊天后不再追加迟到消息。实际 AI 客户端和实体 FSR 接好后的效果仍待验证，测试替身只能证明传输和控制流程。

当前本机工作任务已经通过 Wi-Fi 模拟按压→真实 MCP 工具读取→同对话 AI 反馈。普通 Chat 需要独立验证它实际能看到的工具，不能用这个结果代替。

普通 Chat 的插件连接操作见 [聊天窗口指南](CHAT_MCP.md#chatgpt-普通-chat-的操作)。先核对本聊天的工具，再开始会话；本机 Work 能读取设备不等于普通 Chat 已接通。可发送下面的请求进行检查：

> 我要测试共感娃娃。请先检查这个聊天是否实际有 ai_doll MCP 工具，并读取设备状态、通道和反馈偏好。有工具时开始 60 秒互动并等待我模拟按压，保存会话 ID 与游标，在这个聊天里回应，最后结束会话。没有工具时直接说明缺少哪一层连接，不要读取 GitHub 后假称已连接，也不要要求我为了测试换成 Work。
