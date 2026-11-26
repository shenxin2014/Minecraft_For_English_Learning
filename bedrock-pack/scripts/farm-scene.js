import { world } from "@minecraft/server";
import { farmOrigin, farmPoint } from "./farm-map.js";
import { animalVisible } from "./farm-visibility.js";

const STATIONS = {
  entrance: 6,
  cow_pen: 6,
  pig_pen: 6,
  mixed_pen: 6,
  meadow: 17,
  home_pen: 17,
  farm: 17,
  review_pen: 28,
};

/** 只在本项目保留区执行白名单效果，任何远端字符串都不作为游戏命令。 */
export class FarmScene {
  /** 保存角色查找入口和动作 ledger，用于重启后恢复同一随机布局。
   * @param {() => import('@minecraft/server').Player | undefined} player
   * @param {import('./action-ledger.js').ActionLedger} ledger
   */
  constructor(player, ledger) {
    this.player = player;
    this.ledger = ledger;
  }

  /** 通过唯一标签查找角色，缺失或重复都停止执行而不猜测目标。 */
  entity(kind) {
    const origin = farmOrigin();
    const matches = world.getDimension(origin.dimension).getEntities({ tags: [`farm:m3:${kind}`] });
    if (matches.length !== 1) throw new Error("FARM_ACTOR_MISSING_OR_DUPLICATED");
    return matches[0];
  }

  /** 当前课次视觉命令决定位置，重启与 ACK 重试均复用已存的随机结果。 */
  layout(session, record) {
    const origin = farmOrigin();
    const z = STATIONS[session.current_task.context];
    if (z === undefined) throw new Error("UNKNOWN_FARM_CONTEXT");
    const cowX = record.cowOnLeft ? -2 : 2;
    this.entity("cow").teleport(farmPoint(origin, cowX, 1, z));
    this.entity("pig").teleport(farmPoint(origin, -cowX, 1, z));
    this.entity("lily").teleport(farmPoint(origin, -4, 1, z - 3));
    return { origin, z };
  }

  /** 初次执行当前视觉命令时移动到观察点；后续刷新不会抢夺玩家视角。 */
  prepare(command, session, record) {
    const { origin, z } = this.layout(session, record);
    const player = this.player();
    if (!player) throw new Error("PLAYER_DISCONNECTED");
    player.teleport(farmPoint(origin, 0, 1, z - 5), {
      dimension: world.getDimension(origin.dimension),
      facingLocation: farmPoint(origin, 0, 2, z),
    });
    if (!command.randomize_positions) this.highlight(command.target_id);
  }

  /** 将每种命令交给一个固定效果，不执行多用途任意命令解释器。 */
  apply(command, session, record) {
    if (command.command_id === session.active_visual_id)
      return this.prepare(command, session, record);
    const handlers = {
      UNLOCK_GATE: () => this.unlockGate(),
      GRANT_COSMETIC: () => this.decorate(),
      PLAY_FEEDBACK: () =>
        this.message(command.target_id === "correct" ? "Lily: Great!" : "Lily: Try again!"),
      SHOW_TITLE: () => this.message("Lily: Ask a grown-up for help."),
      HIGHLIGHT_ENTITY: () => this.highlight(command.target_id),
      SHOW_HINT: () => this.hint(command),
    };
    const handler = handlers[command.type];
    if (!handler) throw new Error("UNKNOWN_WORLD_ACTION");
    handler();
  }

  /** 将固定门洞设置为空气，重复执行不会多开一扇门。 */
  unlockGate() {
    const origin = farmOrigin();
    const dimension = world.getDimension(origin.dimension);
    for (let x = -1; x <= 1; x += 1)
      dimension.setBlockType(farmPoint(origin, x, 1, 10), "minecraft:air");
  }

  /** 装饰奖励是固定位置的花，不向背包追加可复制物品。 */
  decorate() {
    const origin = farmOrigin();
    world
      .getDimension(origin.dimension)
      .setBlockType(farmPoint(origin, 6, 1, 2), "minecraft:poppy");
  }

  /** 使用短期粒子提示目标，避免下一个任务遗留位置答案。 */
  highlight(target) {
    const entity = this.entity(target);
    entity.dimension.spawnParticle("minecraft:heart_particle", {
      ...entity.location,
      y: entity.location.y + 2,
    });
  }

  /** H2 使用动物声音，H3 高亮，H4 用粒子提示行进方向。 */
  hint(command) {
    const entity = this.entity(command.target_id);
    if (command.hint_level === 2)
      entity.dimension.playSound(`mob.${command.target_id}.say`, entity.location);
    if (command.hint_level >= 3) this.highlight(command.target_id);
    if (command.hint_level === 4) this.route(entity);
  }

  /** 在玩家和目标之间生成短期引导点，离开任务后自然消失。 */
  route(entity) {
    const player = this.player();
    if (!player) return;
    for (let step = 1; step <= 5; step += 1) {
      const fraction = step / 6;
      entity.dimension.spawnParticle("minecraft:heart_particle", {
        x: player.location.x + (entity.location.x - player.location.x) * fraction,
        y: entity.location.y + 0.5,
        z: player.location.z + (entity.location.z - player.location.z) * fraction,
      });
    }
  }

  /** 反馈只显示固定短句，不把服务端文本原样注入游戏。 */
  message(text) {
    this.player()?.onScreenDisplay.setActionBar(text);
  }

  /** 维护教学动物的位置；必须有当前视觉执行记录才可确认呈现。 */
  visible(session) {
    const player = this.player();
    if (!player) return false;
    if (!session.current_task.target) return true;
    const record = this.ledger.records[session.active_visual_id];
    if (!record?.done) return false;
    this.layout(session, record);
    const kinds = session.current_task.randomize_positions
      ? ["cow", "pig"]
      : [session.current_task.target];
    return kinds.every((kind) => animalVisible(player, this.entity(kind)));
  }
}
