import { contextIsFresh, interactionEnvelope, retryable } from "./protocol.js";

/** BDS 入站事件适配器；动作执行将在 M3 接入，不生成虚假命令 ACK。 */
export class BedrockGameAdapter {
  /** 注入传输、持久队列和时钟，使断线场景可在离线测试中复现。 */
  constructor(transport, outbox, now = () => Date.now()) {
    this.transport = transport;
    this.outbox = outbox;
    this.now = now;
    this.context = null;
    this.receivedAt = 0;
    this.busy = false;
    this.gatePassed = false;
    this.halted = false;
    this.failures = 0;
    this.nextAttempt = 0;
  }

  /** 仅本次 BDS 进程收到正确探针回执后启用事件网络通道。 */
  async probe(profile) {
    this.gatePassed = false;
    this.context = null;
    const bridgeId = this.outbox.state.bridgeId;
    const receipt = await this.transport.probe(bridgeId, profile);
    if (receipt.bridge_id !== bridgeId || receipt.http_received !== true) {
      throw new Error("PROBE_INVALID");
    }
    this.gatePassed = true;
    this.halted = false;
    this.nextAttempt = 0;
    this.failures = 0;
  }

  /** 拉取当前课次，并在持久化序号恢复完成后公开新上下文。 */
  async refresh() {
    const context = await this.transport.context(this.outbox.state.bridgeId);
    if (context.bridge_id !== this.outbox.state.bridgeId) throw new Error("CONTEXT_MISMATCH");
    this.outbox.synchronize(context.session.sequences.game || 0);
    this.context = context;
    this.receivedAt = this.now();
  }

  /** 只为本世界绑定的匿名玩家记录真实交互；过期上下文明确拒绝。 */
  capture(playerId, entityType) {
    if (!this.gatePassed || this.halted) throw new Error("BRIDGE_NOT_READY");
    if (!contextIsFresh(this.context, this.receivedAt, this.now()))
      throw new Error("CONTEXT_STALE");
    if (playerId !== this.context.session.player_id) throw new Error("PLAYER_NOT_BOUND");
    return this.outbox.enqueue((sequence) =>
      interactionEnvelope(this.context, entityType, sequence),
    );
  }

  /** 串行刷新及发送，避免网络慢时 interval 产生并发重发和乱序。 */
  async tick() {
    if (!this.gatePassed || this.halted || this.busy || this.now() < this.nextAttempt) return;
    this.busy = true;
    try {
      // 先清旧事件，再获取新任务；否则重启后的同步可能让旧序号失效。
      await this.sendFirst();
      await this.refresh();
      this.failures = 0;
    } catch (error) {
      this.handleFailure(error);
      throw error;
    } finally {
      this.busy = false;
    }
  }

  /** 只认同课次的结构化响应；200 错误页面不能导致队列丢失。 */
  async sendFirst() {
    const entry = this.outbox.first();
    if (!entry) return;
    const receipt = await this.transport.send(entry);
    if (
      receipt.session?.session_id !== entry.event.session_id ||
      typeof receipt.result !== "string" ||
      typeof receipt.duplicate !== "boolean"
    ) {
      throw new Error("RECEIPT_INVALID");
    }
    this.outbox.acknowledge(entry.event.event_id);
  }

  /** 网络失败指数退避；认证或契约错误停机保留证据，等待再次探针。 */
  handleFailure(error) {
    this.failures += 1;
    this.nextAttempt = this.now() + Math.min(30000, 1000 * 2 ** Math.min(this.failures, 5));
    if (error.status && !retryable(error.status)) this.halted = true;
  }
}
