import test from "node:test";
import assert from "node:assert/strict";
import { EventOutbox } from "../scripts/outbox.js";
import { BedrockGameAdapter } from "../scripts/adapter.js";
import { selectedAnimal } from "../scripts/protocol.js";

/** 创建可保存到重启后的存储替身，不依赖 Minecraft 运行时。 */
function storage() {
  let value;
  return {
    read: () => value,
    write: (next) => {
      value = next;
    },
  };
}

/** 用可控传输和时钟复现服务端成功、响应丢失和任务切换。 */
async function fixture() {
  const disk = storage();
  const outbox = new EventOutbox(disk, "world_1");
  const context = {
    bridge_id: "world_1",
    session: {
      session_id: "session_1",
      player_id: "anonymous_1",
      current_task: { task_id: "find_cow" },
      sequences: {},
    },
  };
  const receipts = new Map();
  const transport = {
    probe: async () => ({ bridge_id: "world_1", http_received: true }),
    context: async () => JSON.parse(JSON.stringify(context)),
    send: async (entry) => {
      const duplicate = receipts.has(entry.event.event_id);
      receipts.set(entry.event.event_id, entry);
      return { result: "accepted", duplicate, session: context.session };
    },
  };
  const clock = { value: 1000 };
  const adapter = new BedrockGameAdapter(transport, outbox, () => clock.value);
  await adapter.probe("test");
  await adapter.tick();
  return { adapter, transport, context, outbox, disk, clock, receipts };
}

test("successful server commit plus lost response retries original event after restart", async () => {
  const f = await fixture();
  const captured = f.adapter.capture("anonymous_1", "minecraft:cow");
  const send = f.transport.send;
  f.transport.send = async (entry) => {
    await send(entry);
    throw new Error("lost response");
  };
  await assert.rejects(f.adapter.tick());
  assert.equal(f.outbox.state.pending.length, 1);
  f.context.session.current_task.task_id = "find_pig";
  f.transport.send = send;
  const restored = new BedrockGameAdapter(f.transport, new EventOutbox(f.disk, "world_1"));
  await restored.probe("test");
  await restored.tick();
  assert.equal(restored.outbox.state.pending.length, 0);
  assert.equal(f.receipts.size, 1);
  assert.deepEqual(f.receipts.get(captured.event.event_id), captured);
  assert.equal(captured.event.task_id, "find_cow");
});

test("expired context and wrong anonymous player never create an event", async () => {
  const f = await fixture();
  assert.throws(() => f.adapter.capture("intruder", "minecraft:cow"), /PLAYER_NOT_BOUND/);
  f.clock.value += 5001;
  assert.throws(() => f.adapter.capture("anonymous_1", "minecraft:cow"), /CONTEXT_STALE/);
  assert.equal(f.outbox.state.pending.length, 0);
});

test("queue overflow and failed persistence preserve already stored evidence", async () => {
  const f = await fixture();
  for (let i = 0; i < 32; i += 1) f.adapter.capture("anonymous_1", "minecraft:cow");
  const before = f.disk.read();
  assert.throws(() => f.adapter.capture("anonymous_1", "minecraft:cow"), /OUTBOX_FULL/);
  assert.equal(f.disk.read(), before);
  f.disk.write = () => {
    throw new Error("disk failure");
  };
  assert.throws(() => f.outbox.acknowledge(f.outbox.first().event.event_id));
  assert.equal(f.outbox.state.pending.length, 32);
});

test("invalid response and 401 preserve queue; corrected probe permits retry", async () => {
  const f = await fixture();
  f.adapter.capture("anonymous_1", "minecraft:pig");
  const send = f.transport.send;
  f.transport.send = async () => ({ ok: true });
  await assert.rejects(f.adapter.tick(), /RECEIPT_INVALID/);
  f.clock.value += 4000;
  f.transport.send = async () => {
    throw Object.assign(new Error("denied"), { status: 401 });
  };
  await assert.rejects(f.adapter.tick());
  assert.equal(f.adapter.halted, true);
  assert.equal(f.outbox.state.pending.length, 1);
  f.transport.send = send;
  f.clock.value += 4000;
  await f.adapter.probe("test");
  await f.adapter.tick();
  assert.equal(f.outbox.state.pending.length, 0);
});

test("HTTP gate closes again if a subsequent probe fails", async () => {
  const f = await fixture();
  f.transport.probe = async () => {
    throw new Error("offline");
  };
  await assert.rejects(f.adapter.probe("test"));
  assert.throws(() => f.adapter.capture("anonymous_1", "minecraft:cow"), /BRIDGE_NOT_READY/);
});

test("parallel ticks cannot send the same head concurrently", async () => {
  const f = await fixture();
  f.adapter.capture("anonymous_1", "minecraft:cow");
  let finish;
  let calls = 0;
  f.transport.send = () => {
    calls += 1;
    return new Promise((resolve) => {
      finish = resolve;
    });
  };
  const first = f.adapter.tick();
  await f.adapter.tick();
  assert.equal(calls, 1);
  finish({ result: "accepted", duplicate: false, session: f.context.session });
  await first;
  assert.equal(f.outbox.state.pending.length, 0);
});

test("restored outbox refuses different bridge or corrupted data", () => {
  const disk = storage();
  disk.write('{"bridgeId":"old","sequence":0,"pending":[]}');
  assert.throws(() => new EventOutbox(disk, "new"));
  disk.write("corrupt");
  assert.throws(() => new EventOutbox(disk, "new"));
});

test("only tagged cow and pig events qualify", () => {
  assert.equal(selectedAnimal({ typeId: "minecraft:cow", hasTag: () => false }), null);
  assert.equal(selectedAnimal({ typeId: "minecraft:sheep", hasTag: () => true }), null);
  assert.equal(selectedAnimal({ typeId: "minecraft:pig", hasTag: () => true }), "minecraft:pig");
});
