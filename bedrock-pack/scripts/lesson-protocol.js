import { eventId } from "./protocol.js";

const CONTROL = new Set(["START", "CONTINUE", "HELP", "REPLAY", "SKIP", "PAUSE", "RESUME", "EXIT"]);
const TARGETS = {
  UNLOCK_GATE: ["gate_01"],
  GRANT_COSMETIC: ["farm_helper"],
  PLAY_FEEDBACK: ["correct", "try_again"],
  SHOW_TITLE: ["audio_unavailable", "check_controls"],
  SHOW_HINT: ["cow", "pig"],
  HIGHLIGHT_ENTITY: ["cow", "pig"],
};

/** 只允许当前课次的固定动作；旧任务仅保留已经签发的持久奖励。 */
export function validateAction(command, session) {
  if (command.audience !== "game" || command.session_id !== session.session_id)
    throw new Error("ACTION_OWNER");
  if (!TARGETS[command.type]?.includes(command.target_id)) throw new Error("ACTION_NOT_ALLOWED");
  validateHint(command.hint_level);
  const durable = ["UNLOCK_GATE", "GRANT_COSMETIC", "PLAY_FEEDBACK"].includes(command.type);
  return durable || command.task_id === session.current_task.task_id;
}

/** 提示等级只能来自固定 H0–H4 范围。 */
function validateHint(level) {
  if (!Number.isInteger(level) || level < 0 || level > 4) throw new Error("ACTION_HINT");
}

/** 构造 M3 的游戏意图；事件在交互时冻结，不在重试时改任务。 */
export function lessonEnvelope(context, kind, sequence, fields = {}) {
  const session = context.session;
  return {
    bridge_id: context.bridge_id,
    event: {
      event_id: eventId(),
      session_id: session.session_id,
      player_id: session.player_id,
      task_id: session.current_task.task_id,
      kind,
      sequence,
      occurred_at: new Date().toISOString(),
      provider: "bedrock.m3",
      ...fields,
    },
  };
}

/** Lily 的继续操作不会绕过听力选择；口语只提供自愿跳过。 */
export function lilyIntent(session) {
  if (session.state === "READY") return "START";
  if (["PAUSED", "EXITED"].includes(session.state)) return "RESUME";
  if (session.state === "OPTIONAL_SPEAK") return "SKIP";
  if (
    session.state === "AWAITING_GAME_ACTION" &&
    ["EXPLORE", "OBSERVE"].includes(session.current_task.type)
  )
    return "CONTINUE";
  return null;
}

/** 脚本指令仅映射到明确的用户控制，禁止从字符串执行游戏命令。 */
export function controlIntent(id) {
  const kind = id.replace("farm:", "").toUpperCase();
  return CONTROL.has(kind) ? kind : null;
}

/** 暂停、完成和未开始时不执行教学场景动作。 */
export function activeLesson(session) {
  return !["READY", "PAUSED", "EXITED", "COMPLETE"].includes(session.state);
}
