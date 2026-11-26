/** 在较窄视锥、近距离和无遮挡条件同时满足时，才确认目标可见。 */
export function visiblePoint(eye, view, target, blocked) {
  const delta = { x: target.x - eye.x, y: target.y - eye.y, z: target.z - eye.z };
  const distance = Math.hypot(delta.x, delta.y, delta.z);
  if (distance < 0.5 || distance > 12) return false;
  const dot = (delta.x * view.x + delta.y * view.y + delta.z * view.z) / distance;
  return dot >= 0.9 && !blocked(eye, delta, distance);
}

/** 服务端只能检查视向和方块遮挡；实际客户端窗口仍须实机校准。
 * @param {import('@minecraft/server').Player} player
 * @param {import('@minecraft/server').Entity} entity
 */
export function animalVisible(player, entity) {
  if (player.dimension.id !== entity.dimension.id) return false;
  const target = { ...entity.location, y: entity.location.y + 0.7 };
  return visiblePoint(
    player.getHeadLocation(),
    player.getViewDirection(),
    target,
    (eye, delta, distance) =>
      Boolean(
        player.dimension.getBlockFromRay(eye, delta, {
          maxDistance: distance - 0.4,
          includeLiquidBlocks: true,
          includePassableBlocks: false,
        }),
      ),
  );
}
