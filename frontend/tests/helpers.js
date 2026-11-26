/** 提供无浏览器、无音频设备的测试替身，只模拟边界，不复制教学判断。 */

/** 用 Map 实现 Storage 的最小接口，便于测试刷新后的请求恢复。 */
export class MemoryStorage {
  /** 为每个测试提供隔离的数据集。 */
  constructor() {
    this.values = new Map();
  }
  /** 返回保存值，缺失时与 localStorage 一样返回 null。 */
  getItem(key) {
    return this.values.get(key) ?? null;
  }
  /** 按 Storage 约定保存字符串。 */
  setItem(key, value) {
    this.values.set(key, String(value));
  }
  /** 仅删除指定键。 */
  removeItem(key) {
    this.values.delete(key);
  }
}

/** 可手动发送 ended/error 的媒体替身，不生成虚构浏览器验收证据。 */
export class FakeAudio extends EventTarget {
  /** 记录播放器设置，并允许测试控制 play Promise。 */
  constructor() {
    super();
    this.volume = 1;
    this.paused = true;
    this.playBehavior = () => Promise.resolve();
  }
  /** 模拟播放启动，音频结束必须由测试另行发送事件。 */
  play() {
    this.paused = false;
    return this.playBehavior();
  }
  /** 模拟立即停声，不自动触发 ended。 */
  pause() {
    this.paused = true;
  }
}

/** 创建固定播放命令，测试关注回执关联而非具体语音内容。 */
export function audioCommand(id = "audio-01") {
  return {
    command_id: id,
    session_id: "session-01",
    task_id: "find_cow",
    audio_id: "find_cow_en",
    hint_level: 0,
  };
}

/** 提供事件构造所需的最小权威快照。 */
export function lessonState() {
  return {
    session_id: "session-01",
    player_id: "local_player_01",
    current_task: { task_id: "find_cow" },
    sequences: { game: 4, control: 2 },
    state: "AWAITING_GAME_ACTION",
    active_audio_id: "audio-01",
    audio_finished: false,
  };
}

/** 构造标准 JSON 响应，沿用实际客户端的解析逻辑。 */
export function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
