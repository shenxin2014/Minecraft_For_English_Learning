import { subscribeCommands, subscribeInteractions } from "./events.js";
import { world } from "@minecraft/server";

// 诊断包不导入 server-net / server-admin，先独立观察本地事件字段。
world.afterEvents.worldLoad.subscribe(() => {
  subscribeCommands();
  subscribeInteractions(() => {});
  console.warn("[Farm M2] Diagnostic loaded; no HTTP, no learning score.");
});
