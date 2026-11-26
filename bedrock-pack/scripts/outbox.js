/** 持久发件箱：先保存再发送，容量超限明确报错，绝不悄悄丢事件。 */
export class EventOutbox {
  /** 读取世界动态属性；损坏数据禁止自动重建，防止序号和收据丢失。 */
  constructor(storage, bridgeId) {
    this.storage = storage;
    const raw = storage.read();
    this.state = raw ? JSON.parse(raw) : { bridgeId, sequence: 0, pending: [] };
    this.validate(bridgeId);
  }

  /** 检查世界是否仍属于同一桥接，避免旧事件迁移到新课次。 */
  validate(bridgeId) {
    const state = this.state;
    if (state.bridgeId !== bridgeId || !Number.isSafeInteger(state.sequence)) {
      throw new Error("OUTBOX_BINDING_OR_SEQUENCE_INVALID");
    }
    if (!Array.isArray(state.pending) || state.pending.length > 32 || state.sequence < 0) {
      throw new Error("OUTBOX_INVALID");
    }
    this.validateEntries();
  }

  /** 拒绝缺少固定 ID 或属于其他世界的持久队列条目。 */
  validateEntries() {
    for (const entry of this.state.pending) {
      if (entry.bridge_id !== this.state.bridgeId || !entry.event?.event_id) {
        throw new Error("OUTBOX_ENTRY_INVALID");
      }
    }
  }

  /** 只有持久化成功才替换内存状态，避免写失败后发送未保存事件。 */
  commit(next) {
    const encoded = JSON.stringify(next);
    if (encoded.length > 30000) throw new Error("OUTBOX_STORAGE_FULL");
    this.storage.write(encoded);
    this.state = next;
  }

  /** 从服务器恢复序号上界，未确认事件保持原标识和原序号。 */
  synchronize(sequence) {
    if (sequence > this.state.sequence) this.commit({ ...this.state, sequence });
  }

  /** 保存新的不可变事件快照；队列满时保留原内容并拒绝新增。 */
  enqueue(create) {
    if (this.state.pending.length >= 32) throw new Error("OUTBOX_FULL");
    const sequence = this.state.sequence + 1;
    const envelope = create(sequence);
    this.commit({ ...this.state, sequence, pending: [...this.state.pending, envelope] });
    return envelope;
  }

  /** 返回一个副本，传输层不能意外修改持久化事件。 */
  first() {
    const first = this.state.pending[0];
    return first ? JSON.parse(JSON.stringify(first)) : null;
  }

  /** 只在服务端明确返回合法收据后移除队首。 */
  acknowledge(eventId) {
    if (this.state.pending[0]?.event.event_id !== eventId) throw new Error("OUTBOX_ACK_MISMATCH");
    this.commit({ ...this.state, pending: this.state.pending.slice(1) });
  }
}
