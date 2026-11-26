import { ItemStack, world } from "@minecraft/server";

/** 只在操作者身边生成两只测试动物和饲料；不改地形或原有实体。
 * @param {import('@minecraft/server').Player} player
 */
export function setupScene(player) {
  const dimension = player.dimension;
  if (world.getDynamicProperty("farm:m2_scene")) throw new Error("SCENE_ALREADY_CREATED");
  const origin = player.location;
  /** @type {[string, number][]} */
  const animals = [
    ["cow", -2],
    ["pig", 2],
  ];
  // 先记下生成意图；即使区块未加载导致部分失败，也不自动重复生成动物。
  world.setDynamicProperty("farm:m2_scene", true);
  for (const [animal, offset] of animals) {
    const entity = dimension.spawnEntity(`minecraft:${animal}`, {
      x: origin.x + offset,
      y: origin.y,
      z: origin.z + 3,
    });
    entity.addTag("farm:m2");
  }
  dimension.spawnItem(new ItemStack("minecraft:wheat", 16), origin);
  dimension.spawnItem(new ItemStack("minecraft:carrot", 16), origin);
  player.sendMessage(
    "[Farm M2] Test animals ready. Feed cow wheat / pig carrot to test successful interaction.",
  );
}
