/** 只接受当前测试动物；不读取或输出玩家真实名字、位置和聊天。 */
export function selectedAnimal(target) {
  if (!target.hasTag("farm:m2")) return null;
  return ["minecraft:cow", "minecraft:pig"].includes(target.typeId) ? target.typeId : null;
}

/** 生成匿名事件标识；重试直接读取持久队列，不重新生成。 */
export function eventId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

/** 在交互发生时冻结任务、玩家和序号，禁止重试时套用后续任务。 */
export function interactionEnvelope(context, entityType, sequence, id = eventId()) {
  const session = context.session;
  return {
    bridge_id: context.bridge_id,
    event: {
      event_id: id,
      session_id: session.session_id,
      player_id: session.player_id,
      task_id: session.current_task.task_id,
      kind: "ENTITY_INTERACTED",
      sequence,
      occurred_at: new Date().toISOString(),
      entity_type: entityType,
      provider: "bedrock.playerInteractWithEntityAfterEvent",
    },
  };
}

/** 过期上下文不能用来猜测当前任务；短暂断网时只重发已有事件。 */
export function contextIsFresh(context, receivedAt, now = Date.now()) {
  return Boolean(context && now - receivedAt <= 5000);
}

/** 客户端错误需人工修复；限流及服务端故障保留事件并退避重试。 */
export function retryable(status) {
  return status === 408 || status === 429 || status >= 500;
}
