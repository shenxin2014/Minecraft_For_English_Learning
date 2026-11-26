import { system, world } from "@minecraft/server";
import { variables } from "@minecraft/server-admin";
import { BedrockGameAdapter } from "./adapter.js";
import { EventOutbox } from "./outbox.js";
import { contextIsFresh } from "./protocol.js";
import { reportFailure, subscribeCommands, subscribeInteractions } from "./events.js";
import { BdsTransport } from "./transport.js";

/** 等世界初始化完成后读取动态属性，避免 2.x 早期执行阶段访问世界。 */
function startBridge() {
  const bridgeId = variables.get("farm_bridge_id");
  if (typeof bridgeId !== "string" || !/^[A-Za-z0-9_-]{1,100}$/.test(bridgeId)) {
    throw new Error("BRIDGE_ID_REQUIRED");
  }
  const storage = {
    read: () => world.getDynamicProperty("farm:m2_outbox"),
    write: (value) => world.setDynamicProperty("farm:m2_outbox", value),
  };
  const adapter = new BedrockGameAdapter(new BdsTransport(), new EventOutbox(storage, bridgeId));
  subscribeCommands((id, player) => handleCommand(adapter, id, player));
  subscribeInteractions((player, type) => {
    if (world.getDynamicProperty("farm:m2_owner") !== player.id) return;
    adapter.capture(player.getDynamicProperty("farm:m2_player"), type);
  });
  system.runInterval(() => {
    void adapter.tick().catch(() => reportFailure("HTTP_RETRY_OR_HALTED_CHECK_API"));
  }, 20);
  console.warn("[Farm M2] BDS candidate loaded; HTTP closed until farm:probe.");
}

/** 探针通过后手动绑定操作者；一个世界只能有一个操作者，不能静默换人。 */
function bindPlayer(adapter, player) {
  if (!contextIsFresh(adapter.context, adapter.receivedAt)) throw new Error("PROBE_FIRST");
  const previous = world.getDynamicProperty("farm:m2_owner");
  if (previous && previous !== player.id) throw new Error("WORLD_ALREADY_BOUND");
  world.setDynamicProperty("farm:m2_owner", player.id);
  player.setDynamicProperty("farm:m2_player", adapter.context.session.player_id);
  player.sendMessage(
    "[Farm M2] Anonymous player bound. Feed tagged animals to test HTTP receipts.",
  );
}

/** 只处理诊断命令，不执行任意服务端返回的 Minecraft 命令。 */
function handleCommand(adapter, id, player) {
  if (id === "farm:bind") bindPlayer(adapter, player);
  if (id === "farm:probe") {
    void adapter
      .probe("bds-1.26.66-candidate")
      .then(async () => {
        await adapter.tick();
        player.sendMessage("[Farm M2] HTTP probe passed. Run /scriptevent farm:bind now");
      })
      .catch(() => reportFailure("PROBE_FAILED_HTTP_STAYS_CLOSED"));
  }
}

world.afterEvents.worldLoad.subscribe(() => {
  try {
    startBridge();
  } catch {
    reportFailure("START_FAILED_CHECK_PROFILE_AND_CONFIG");
  }
});
