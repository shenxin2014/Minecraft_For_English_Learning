import { validateAction } from "./lesson-protocol.js";

/** 串行执行白名单游戏动作并重试 ACK，不把拉取当成成功。 */
export class ActionWorker {
  /** 注入世界与网络边界，使奖励重投和崩溃恢复可独立测试。 */
  constructor(transport, ledger, scene, clock = () => Date.now()) {
    this.transport = transport;
    this.ledger = ledger;
    this.scene = scene;
    this.clock = clock;
    this.started = new Map();
  }

  /** 记录本进程发生的事件时间；重启缺失的时间不会补成零耗时。 */
  track(eventId) {
    this.started.set(eventId, this.clock());
    if (this.started.size > 128) this.started.delete(this.started.keys().next().value);
  }

  /** 获取原子快照后逐个处理，暂停时既不执行也不确认。 */
  async poll(bridgeId) {
    const batch = await this.transport.actions(bridgeId);
    if (["READY", "PAUSED", "EXITED"].includes(batch.session.state)) return batch.session;
    for (const command of batch.commands) await this.execute(command, batch.session, bridgeId);
    await this.reportSamples(bridgeId);
    return batch.session;
  }

  /** 奖励使用固定世界状态，覆盖“效果已发生但 ledger 尚未保存”的崩溃间隙。 */
  async execute(command, session, bridgeId) {
    if (!validateAction(command, session)) {
      await this.transport.ack(bridgeId, command);
      return;
    }
    const record = this.ledger.prepare(command);
    if (!record.done) {
      this.scene.apply(command, session, record);
      const start = this.started.get(command.caused_by_event_id);
      this.ledger.complete(command.command_id, start === undefined ? null : this.clock() - start);
    }
    const receipt = await this.transport.ack(bridgeId, command);
    if (
      receipt.command_id !== command.command_id ||
      !["acked", "cancelled"].includes(receipt.status)
    )
      throw new Error("ACK_INVALID");
    this.ledger.save(command.command_id, {
      ...this.ledger.records[command.command_id],
      acked: receipt.status === "acked",
    });
  }

  /** ACK 后独立恢复统计上报，指标网络故障不会重复执行奖励。 */
  async reportSamples(bridgeId) {
    for (const [id, record] of Object.entries(this.ledger.records)) {
      if (
        !record.acked ||
        !record.sampleEligible ||
        record.reported ||
        record.elapsed === null ||
        record.elapsed > 60000
      )
        continue;
      await this.transport.latency(bridgeId, id, record.elapsed);
      this.ledger.save(id, { ...record, reported: true });
    }
  }
}
