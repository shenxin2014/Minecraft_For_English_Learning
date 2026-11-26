import { Player, system, world } from "@minecraft/server";
import { variables } from "@minecraft/server-admin";
import { EventOutbox } from "./outbox.js";
import { ActionLedger } from "./action-ledger.js";
import { ActionWorker } from "./action-worker.js";
import { LessonTransport } from "./lesson-transport.js";
import { LessonRuntime } from "./lesson-runtime.js";
import { FarmScene } from "./farm-scene.js";
import { buildFarm } from "./farm-map.js";
import { controlIntent, lilyIntent } from "./lesson-protocol.js";
import { reportFailure } from "./events.js";

/** 为世界动态属性提供小型可测试存储接口，不将秘密写入世界。 */
function storage(key) {
  return {
    read: () => world.getDynamicProperty(key),
    write: (value) => world.setDynamicProperty(key, value),
  };
}

/** 只寻找已绑定的在线玩家，断线时返回空而不偷偷换人。 */
function owner() {
  const id = world.getDynamicProperty("farm:m3_owner");
  return world.getAllPlayers().find((player) => player.id === id);
}

/** 探针通过且场景已建好后固定本课次操作者。 */
function bindOwner(runtime, player) {
  if (!runtime.adapter.context || !world.getDynamicProperty("farm:m3_origin"))
    throw new Error("BUILD_AND_PROBE_FIRST");
  const previous = world.getDynamicProperty("farm:m3_owner");
  if (previous && previous !== player.id) throw new Error("PLAYER_ALREADY_BOUND");
  world.setDynamicProperty("farm:m3_owner", player.id);
  player.sendMessage("Lily: Ready. Open the voice companion and interact with me to start.");
}

/** 白名单脚本指令仅用于建图、连接与明确课程控制。 */
function command(runtime, id, player) {
  if (id === "farm:build") return buildFarm(player);
  if (id === "farm:bind") return bindOwner(runtime, player);
  if (id === "farm:probe") {
    void runtime.adapter
      .probe("m3-bds-1.26.66-candidate")
      .then(() => runtime.adapter.tick())
      .then(() => player.sendMessage("HTTP probe passed. Run /scriptevent farm:bind"))
      .catch(() => reportFailure("M3_PROBE_FAILED"));
    return;
  }
  if (owner()?.id !== player.id) return;
  const intent = controlIntent(id);
  if (intent) runtime.enqueue(intent);
}

/** 从 before-event 获取选择意图并取消喂食/交易，再在可写 tick 入队。 */
function subscribeSelection(runtime) {
  world.beforeEvents.playerInteractWithEntity.subscribe((event) => {
    if (owner()?.id !== event.player.id) return;
    const kind = ["cow", "pig", "lily"].find((name) => event.target.hasTag(`farm:m3:${name}`));
    if (!kind) return;
    event.cancel = true;
    system.run(() => {
      try {
        if (kind !== "lily") runtime.choose(kind);
        else {
          const intent = lilyIntent(runtime.adapter.context?.session ?? { state: "COMPLETE" });
          if (intent) runtime.enqueue(intent);
        }
      } catch {
        reportFailure("M3_SELECTION_NOT_QUEUED");
      }
    });
  });
}

/** 在世界加载后构建运行时，每 4 tick 进行一次有并发保护的网络同步。 */
function startLesson() {
  const bridgeId = variables.get("farm_bridge_id");
  if (typeof bridgeId !== "string" || !/^[A-Za-z0-9_-]{1,100}$/.test(bridgeId))
    throw new Error("BRIDGE_ID_REQUIRED");
  const ledger = new ActionLedger(storage("farm:m3_ledger"));
  const transport = new LessonTransport();
  const scene = new FarmScene(owner, ledger);
  const worker = new ActionWorker(transport, ledger, scene);
  const runtime = new LessonRuntime(
    transport,
    new EventOutbox(storage("farm:m3_outbox"), bridgeId),
    worker,
    scene,
  );
  system.afterEvents.scriptEventReceive.subscribe((event) => {
    if (!(event.sourceEntity instanceof Player) || !event.id.startsWith("farm:")) return;
    try {
      command(runtime, event.id, event.sourceEntity);
    } catch {
      reportFailure("M3_COMMAND_FAILED");
    }
  });
  subscribeSelection(runtime);
  system.runInterval(() => {
    void runtime.tick().catch(() => reportFailure("M3_SYNC_RETRY_OR_HALTED"));
  }, 4);
  console.warn("[Farm M3] Candidate loaded. Build farm, probe, bind, then open voice companion.");
}

world.afterEvents.worldLoad.subscribe(() => {
  try {
    startLesson();
  } catch {
    reportFailure("M3_START_FAILED_CHECK_CONFIG");
  }
});
