# 把互动接入正在使用的聊天

> 开发者参考；普通用户可以跳过。 [全部目录](../README.md)


本项目增强原聊天，不新增聊天产品。模型、历史上下文与消息展示都沿用你的原应用。

## 普通使用者

按 [安装](../start/AI_INSTALL.md)添加 MCP，在原聊天先 [调用状态工具](../integrations/CHAT_MCP.md)，日常使用近期上下文融入正常回复，也可查询历史或开启 60 秒互动。主动回应需要独立开关与聊天订阅；会话到期或结束后停止该订阅，日常融入仍按用户开关运行。

Secure 已通过普通 Chat 的模拟文字反馈；空闲自动唤醒尚未验证。能够查询工具不意味着模型会在没有用户消息时自动运行。

## 自己的应用开发者

0.1.0 增加普通聊天融入。在同一个原聊天队列中调用 `bridge.replyWithContext({generate,display,signal})`：generate 接收近期互动上下文，并使用原模型、当前人设和话题；display 幂等保存原消息。不要再将该方法放进同一个 queue.run 外层，否则会重复排队。方法已经通过 runDelivery 进入共享队列，在显示成功后确认 receipt_id；中止、过期和静音的结果不插入。服务不可用时使用空互动上下文，原聊天继续。数据不是模型指令。示例：

```javascript
function sendWithDoll(text, signal) {
  return bridge.replyWithContext({
    signal,
    generate: (context, {signal}) => existingGenerateReply(chatId, text, context, {signal}),
    display: (answer, {signal}) => existingSaveAndDisplay(chatId, answer, {signal})
  });
}
```

原后端仍需使用本轮用户消息 ID 做幂等保存；客户端返回确认不证明显示。调用失败后不要凭 receipt_id 重复插入一条已显示的回复，应先核对原消息记录。

接入 `DollBridgeClient`，将事件送入原后端的生成队列。使用原聊天稳定 ID，按持久事件 ID 去重；模型失败不返回演示文字冒充 AI。

`onInteraction` 使用原上下文、人设与反馈偏好生成；`onReply` 在 ACK 成功后写入原消息列表，处理取消和迟到结果。`onDeliveryState` 只报告状态，不调用模型。设备直传后端见 [直传接口](DIRECT_SERVER.md)，电脑事件桥见 [主动互动](PROACTIVE_INTERACTION.md)。

## 与普通消息共享顺序

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

## 开始、结束与切换聊天

重复调用同一实例的 `start()` 会共享同一次启动，返回同一订阅；不会创建两个监听。启动过程中调用 `stop()` 会立即取消本地启动意图，等待已发出的创建请求返回真实 ID 后清理。新的 `start()` 会等这次结束完成，再进入互动。

切换聊天时先停止旧实例，再为新聊天创建实例；原对话的普通消息处理照常继续。取消订阅失败时仍会尝试结束会话；结束失败时保留未清理的 ID，`stop()` 返回错误。恢复连接后重试 `stop()`，清理成功前不会自动重新监听。不要把本地停止等同于服务器操作已经完成，尤其请求响应遗失时应重新核对 `get_interaction_status` 和事件桥状态。

接口保留稳定聊天 ID 的归属检查，不会因为别的聊天占用而抢占。旧流在停止后返回的迟到响应会被忽略，不能关闭新聊天的监听。

设置页和 `/bridge` 是设备管理与传输诊断。`/bridge` 的演示回执带有“非 AI”标记，不能当作原聊天响应验收。

## 验收原聊天

普通文字可正常回应；普通触摸只归档；开始互动后新事件进入同一聊天并生成相关反馈；重复不重复显示；结束或切换后不写入迟到回复。

这需要真实原应用验证。测试替身证明队列与取消流程，不证明某个用户账号的模型反馈。当前普通 Chat 和 Work 的模拟反馈另有 [实际证据](../reports/VALIDATION.md)。
