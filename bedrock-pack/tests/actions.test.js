import test from "node:test";
import assert from "node:assert/strict";
import { ActionLedger } from "../scripts/action-ledger.js";
import { ActionWorker } from "../scripts/action-worker.js";
import { validateAction, lilyIntent, controlIntent } from "../scripts/lesson-protocol.js";
import { visiblePoint } from "../scripts/farm-visibility.js";

/** 构造固定的后端动作样本。 */
function action(type = "UNLOCK_GATE", target = "gate_01") {
  return {
    command_id: "command_1",
    session_id: "session_1",
    task_id: "find_cow",
    type,
    target_id: target,
    audience: "game",
    hint_level: 0,
    caused_by_event_id: "event_1",
  };
}

/** 提供可跨适配器重建保留的模拟世界存档。 */
function storage() {
  let value;
  return {
    read: () => value,
    write: (next) => {
      value = next;
    },
  };
}

/** 使用固定效果集合，模拟幂等的世界状态赋值。 */
function fixture(command = action()) {
  const disk = storage();
  const session = {
    session_id: "session_1",
    state: "INTRODUCING",
    current_task: { task_id: "find_pig" },
  };
  const effects = new Set();
  const scene = {
    count: 0,
    apply: (cmd) => {
      scene.count += 1;
      effects.add(cmd.target_id);
    },
  };
  const transport = {
    actions: async () => ({ session, commands: [command] }),
    ack: async (_bridge, cmd) => ({ command_id: cmd.command_id, status: "acked" }),
    latency: async () => {},
  };
  return { disk, session, effects, scene, transport, command };
}

test("lost ACK and restarted worker do not repeat a completed reward", async () => {
  const f = fixture();
  const ack = f.transport.ack;
  f.transport.ack = async () => {
    throw new Error("lost ACK");
  };
  const worker = new ActionWorker(f.transport, new ActionLedger(f.disk), f.scene);
  await assert.rejects(worker.poll("world_1"));
  assert.equal(f.effects.size, 1);
  f.transport.ack = ack;
  const restored = new ActionWorker(f.transport, new ActionLedger(f.disk), f.scene);
  await restored.poll("world_1");
  assert.equal(f.scene.count, 1);
});

test("crash after world effect before ledger commit preserves reward cardinality", async () => {
  const f = fixture();
  const ledger = new ActionLedger(f.disk);
  ledger.complete = () => {
    throw new Error("crash before commit");
  };
  await assert.rejects(new ActionWorker(f.transport, ledger, f.scene).poll("world_1"));
  await new ActionWorker(f.transport, new ActionLedger(f.disk), f.scene).poll("world_1");
  assert.equal(f.scene.count, 2);
  assert.equal(f.effects.size, 1);
});

test("random layout persists before execution and reused ID with changed content is rejected", () => {
  const disk = storage();
  const first = new ActionLedger(disk).prepare(action(), () => 0.1);
  const restored = new ActionLedger(disk).prepare(action(), () => 0.9);
  assert.equal(first.cowOnLeft, restored.cowOnLeft);
  assert.throws(
    () => new ActionLedger(disk).prepare(action("GRANT_COSMETIC", "farm_helper")),
    /COMMAND_ID_REUSED/,
  );
});

test("pause never applies or ACKs pending rewards; complete still delivers earned rewards", async () => {
  const f = fixture();
  const worker = new ActionWorker(f.transport, new ActionLedger(f.disk), f.scene);
  f.session.state = "PAUSED";
  await worker.poll("world_1");
  assert.equal(f.effects.size, 0);
  f.session.state = "COMPLETE";
  await worker.poll("world_1");
  assert.equal(f.effects.size, 1);
});

test("latency retry after ACK uses first execution time and does not repeat feedback", async () => {
  const f = fixture(action("PLAY_FEEDBACK", "correct"));
  let now = 100;
  const worker = new ActionWorker(f.transport, new ActionLedger(f.disk), f.scene, () => now);
  worker.track("event_1");
  now = 420;
  f.transport.latency = async () => {
    throw new Error("metrics offline");
  };
  await assert.rejects(worker.poll("world_1"));
  now = 900;
  const samples = [];
  f.transport.actions = async () => ({ session: f.session, commands: [] });
  f.transport.latency = async (_bridge, _command, ms) => {
    samples.push(ms);
  };
  await worker.poll("world_1");
  assert.deepEqual(samples, [320]);
  assert.equal(f.scene.count, 1);
});

test("unknown targets, cross-session actions and stale hints cannot mutate world", () => {
  const f = fixture();
  assert.throws(() => validateAction(action("UNLOCK_GATE", "arbitrary_gate"), f.session));
  assert.throws(() => validateAction({ ...action(), session_id: "other" }, f.session));
  assert.equal(validateAction(action("SHOW_HINT", "cow"), f.session), false);
});

test("Lily cannot skip listening verification and control commands are allowlisted", () => {
  assert.equal(lilyIntent({ state: "READY" }), "START");
  assert.equal(lilyIntent({ state: "OPTIONAL_SPEAK" }), "SKIP");
  assert.equal(
    lilyIntent({ state: "AWAITING_GAME_ACTION", current_task: { type: "LISTEN_FIND" } }),
    null,
  );
  assert.equal(controlIntent("farm:kill"), null);
  assert.equal(controlIntent("farm:pause"), "PAUSE");
});

test("visibility requires distance, narrow view cone and unblocked line of sight", () => {
  const eye = { x: 0, y: 2, z: 0 };
  const view = { x: 0, y: 0, z: 1 };
  const target = { x: 2, y: 2, z: 6 };
  assert.equal(
    visiblePoint(eye, view, target, () => false),
    true,
  );
  assert.equal(
    visiblePoint(eye, view, target, () => true),
    false,
  );
  assert.equal(
    visiblePoint(eye, view, { ...target, z: -6 }, () => false),
    false,
  );
  assert.equal(
    visiblePoint(eye, view, { ...target, z: 20 }, () => false),
    false,
  );
});
