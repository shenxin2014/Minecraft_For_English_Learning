import { world } from "@minecraft/server";

/** 读取仅属于 M3 的场景保留区；未建场景时拒绝任何方块操作。 */
export function farmOrigin() {
  const raw = world.getDynamicProperty("farm:m3_origin");
  if (typeof raw !== "string") throw new Error("BUILD_FARM_FIRST");
  return JSON.parse(raw);
}

/** 把固定的小范围局部坐标转换成世界坐标，禁止任意坐标执行。 */
export function farmPoint(origin, x, y, z) {
  if (Math.abs(x) > 8 || z < 0 || z > 32 || y < 0 || y > 5) throw new Error("FARM_BOUNDS");
  return { x: origin.x + x, y: origin.y + y, z: origin.z + z };
}

/** 检查整个保留空间都是空气，避免覆盖用户既有建筑。
 * @param {import('@minecraft/server').Dimension} dimension
 * @param {{x:number,y:number,z:number}} origin
 */
function requireEmpty(dimension, origin) {
  for (let x = -8; x <= 8; x += 1) {
    for (let z = 0; z <= 32; z += 1) {
      for (let y = 0; y <= 4; y += 1) {
        const block = dimension.getBlock(farmPoint(origin, x, y, z));
        if (!block?.isAir) throw new Error("FARM_AREA_NOT_EMPTY_OR_UNLOADED");
      }
    }
  }
}

/** 生成有围栏的入口、草地和复习区；只在明确的 build 指令下运行。
 * @param {import('@minecraft/server').Player} player
 */
export function buildFarm(player) {
  if (world.getDynamicProperty("farm:m3_origin")) throw new Error("FARM_ALREADY_RESERVED");
  const p = player.location;
  const origin = {
    x: Math.floor(p.x) + 12,
    y: Math.floor(p.y) + 8,
    z: Math.floor(p.z),
    dimension: player.dimension.id,
  };
  requireEmpty(player.dimension, origin);
  world.setDynamicProperty("farm:m3_origin", JSON.stringify(origin));
  buildFloor(player.dimension, origin);
  seedActors(player.dimension, origin);
  player.teleport(farmPoint(origin, 0, 1, 3), { facingLocation: farmPoint(origin, 0, 2, 6) });
  player.sendMessage(
    "Lily: Welcome! Connect the voice companion, then interact with Lily to begin.",
  );
}

/** 不同区域使用不同地面，复习换位置也换场景。
 * @param {import('@minecraft/server').Dimension} dimension
 * @param {{x:number,y:number,z:number}} origin
 */
function buildFloor(dimension, origin) {
  for (let x = -8; x <= 8; x += 1) {
    for (let z = 0; z <= 32; z += 1) {
      dimension.setBlockType(farmPoint(origin, x, 0, z), floorAt(z));
      if (Math.abs(x) === 8 || z === 0 || z === 32)
        dimension.setBlockType(farmPoint(origin, x, 1, z), "minecraft:oak_fence");
    }
  }
  for (let x = -1; x <= 1; x += 1)
    dimension.setBlockType(farmPoint(origin, x, 1, 10), "minecraft:oak_fence");
}

/** 各区固定地面材质，便于场景迁移时识别不同背景。 */
function floorAt(z) {
  if (z < 11) return "minecraft:grass_block";
  return z < 22 ? "minecraft:moss_block" : "minecraft:oak_planks";
}

/** 固定角色仅在首次建图时生成；重试动作不会复制实体或物品。
 * @param {import('@minecraft/server').Dimension} dimension
 * @param {{x:number,y:number,z:number}} origin
 */
function seedActors(dimension, origin) {
  const lily = dimension.spawnEntity("minecraft:villager_v2", farmPoint(origin, 0, 1, 2));
  lily.addTag("farm:m3:lily");
  lily.nameTag = "Lily";
  for (const [animal, x] of [
    ["cow", -2],
    ["pig", 2],
  ]) {
    const entity = dimension.spawnEntity(`minecraft:${animal}`, farmPoint(origin, Number(x), 1, 6));
    entity.addTag(`farm:m3:${animal}`);
  }
}
