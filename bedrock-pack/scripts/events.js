import { Player, system, world } from "@minecraft/server";
import { selectedAnimal } from "./protocol.js";
import { setupScene } from "./scene.js";

/** 只打印固定错误标识；不输出原始网络错误、凭据、玩家名或请求正文。 */
export function reportFailure(code) {
  console.warn(`[Farm M2] ${code}`);
}

/** 记录官方 after-event 的实际字段是否存在；不给日志附加教学结果。
 * @param {import('@minecraft/server').PlayerInteractWithEntityAfterEvent} event
 * @param {string} entityType
 */
export function logInteraction(event, entityType) {
  console.warn(
    JSON.stringify({
      source: "playerInteractWithEntityAfterEvent",
      entity_type: entityType,
      player_present: Boolean(event.player),
      before_item_present: Boolean(event.beforeItemStack),
      after_item_present: Boolean(event.itemStack),
    }),
  );
}

/** 注册成功交互事件；普通空手点击是否产生事件必须在实机测试。
 * @param {(player: Player, entityType: string) => void} onInteraction
 */
export function subscribeInteractions(onInteraction) {
  world.afterEvents.playerInteractWithEntity.subscribe((event) => {
    const entityType = selectedAnimal(event.target);
    if (!entityType) return;
    logInteraction(event, entityType);
    try {
      onInteraction(event.player, entityType);
    } catch {
      reportFailure("INTERACTION_NOT_QUEUED_CHECK_BINDING_OR_QUEUE");
    }
  });
}

/** 测试指令必须由玩家主动执行；非玩家来源不能修改场景或绑定。
 * @param {(id: string, player: Player) => void} onCommand
 */
export function subscribeCommands(onCommand = () => {}) {
  system.afterEvents.scriptEventReceive.subscribe((event) => {
    if (!event.id.startsWith("farm:")) return;
    const player = event.sourceEntity;
    if (!(player instanceof Player)) return;
    try {
      if (event.id === "farm:setup") setupScene(player);
      else onCommand(event.id, player);
    } catch {
      reportFailure("COMMAND_FAILED_CHECK_SETUP_OR_BRIDGE");
    }
  });
}
