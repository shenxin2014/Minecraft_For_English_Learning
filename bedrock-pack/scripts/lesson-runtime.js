import { BedrockGameAdapter } from "./adapter.js";
import { lessonEnvelope, activeLesson } from "./lesson-protocol.js";
import { contextIsFresh } from "./protocol.js";

/** 协调事件发件箱、游戏动作和可见性心跳，不复制课程判分逻辑。 */
export class LessonRuntime {
  /** 保持网络操作串行，渲染与交互由 Minecraft 主线程触发。 */
  constructor(transport, outbox, worker, scene) {
    this.adapter = new BedrockGameAdapter(transport, outbox);
    this.worker = worker;
    this.scene = scene;
    this.busy = false;
    this.lastChoice = 0;
  }

  /** 上下文超过短期租约时拒绝新操作，只允许重发已保存事件。 */
  enqueue(kind, fields = {}) {
    const adapter = this.adapter;
    if (
      !adapter.gatePassed ||
      adapter.halted ||
      !contextIsFresh(adapter.context, adapter.receivedAt)
    )
      throw new Error("LESSON_OFFLINE");
    const entry = adapter.outbox.enqueue((sequence) =>
      lessonEnvelope(adapter.context, kind, sequence, fields),
    );
    this.worker.track(entry.event.event_id);
    return entry;
  }

  /** 短暂去抖只防止一次长按生成多次选择，不推测孩子是否理解。 */
  choose(kind) {
    if (Date.now() - this.lastChoice < 500) return;
    this.enqueue("ENTITY_INTERACTED", { entity_type: `minecraft:${kind}` });
    this.lastChoice = Date.now();
  }

  /** 一轮完成事件投递、动作执行及心跳；失败不会继续发送成功回执。 */
  async tick() {
    const adapter = this.adapter;
    if (!this.readyToTick()) return;
    this.busy = true;
    try {
      await adapter.tick();
      const session = await this.worker.poll(adapter.outbox.state.bridgeId);
      adapter.context = { bridge_id: adapter.outbox.state.bridgeId, session };
      adapter.receivedAt = Date.now();
      const visible = activeLesson(session) && this.scene.visible(session);
      await adapter.transport.presence(adapter.context, visible);
      this.confirmVisual(session, visible);
      if (session.state === "COMPLETE") this.scene.message("Lily: Well done! See you next time.");
    } catch (error) {
      // 任务刚切换时，旧心跳冲突是可恢复的，不永久关闭新课次。
      if (error.status !== 409) adapter.handleFailure(error);
      throw error;
    } finally {
      this.busy = false;
    }
  }

  /** 探针、退避和并发状态共同决定是否允许开启下一轮同步。 */
  readyToTick() {
    return (
      !this.busy &&
      this.adapter.gatePassed &&
      !this.adapter.halted &&
      Date.now() >= this.adapter.nextAttempt
    );
  }

  /** 视觉真的可见后才投递一次绑定命令的回执，重试使用同一个队列条目。 */
  confirmVisual(session, visible) {
    if (!visible || !session.active_visual_id || session.visual_ready) return;
    const pending = this.adapter.outbox.state.pending;
    if (pending.some((entry) => entry.event.command_id === session.active_visual_id)) return;
    this.enqueue(session.current_task.randomize_positions ? "LAYOUT_READY" : "VISUAL_READY", {
      command_id: session.active_visual_id,
    });
  }
}
