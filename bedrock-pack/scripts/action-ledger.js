/** 保存动作执行意图与回执；世界效果本身也必须可重复设置。 */
export class ActionLedger {
  /** 损坏数据不静默清空；每个课次有独立持久化记录。 */
  constructor(storage) {
    this.storage = storage;
    this.records = JSON.parse(storage.read() || "{}");
    if (!this.records || Array.isArray(this.records) || typeof this.records !== "object")
      throw new Error("LEDGER_INVALID");
  }

  /** 先持久化随机结果，再执行世界变化，重启不会重新随机。 */
  prepare(command, random = Math.random) {
    const id = command.command_id;
    const signature = JSON.stringify(command);
    const old = this.records[id];
    if (old && old.signature !== signature) throw new Error("COMMAND_ID_REUSED");
    if (old) return old;
    if (Object.keys(this.records).length >= 128) throw new Error("LEDGER_FULL");
    const record = {
      signature,
      cowOnLeft: random() < 0.5,
      done: false,
      elapsed: null,
      sampleEligible: command.type === "PLAY_FEEDBACK",
    };
    this.save(id, record);
    return record;
  }

  /** 写入成功后才更新内存，写失败时保留原状态。 */
  save(id, record) {
    const next = { ...this.records, [id]: record };
    const encoded = JSON.stringify(next);
    if (encoded.length > 30000) throw new Error("LEDGER_FULL");
    this.storage.write(encoded);
    this.records = next;
  }

  /** 世界效果完成后记录执行结果；ACK 丢失不会再次执行已完成动作。 */
  complete(id, elapsed) {
    this.save(id, { ...this.records[id], done: true, elapsed });
  }
}
