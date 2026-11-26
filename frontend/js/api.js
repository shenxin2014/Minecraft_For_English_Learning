/** 同源 HTTP 客户端：保存未确认请求，让断线重试沿用同一个事件 ID。 */

/** 用类型化错误区分认证和连接问题，避免界面依赖错误文本。 */
export class HttpError extends Error {
  /** 保存 HTTP 状态码，供界面区分口令、会话缺失与服务故障。 */
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/** 从固定事件类型选择通道，语音不能通过该映射伪装成游戏事件。 */
export function eventChannel(kind) {
  if (["VISUAL_READY", "LAYOUT_READY", "ENTITY_INTERACTED"].includes(kind)) return "game";
  if (["AUDIO_FINISHED", "AUDIO_FAILED"].includes(kind)) return "voice";
  return "control";
}

/** 封装课堂 API 和持久化请求收据，不负责展示或判分。 */
export class FarmApi {
  /** 注入存储和 fetch，使网络故障可以在单元测试中重现。 */
  constructor(storage = localStorage, fetcher = (path, options) => fetch(path, options)) {
    this.storage = storage;
    this.fetcher = fetcher;
    this.token = "";
  }

  /** 读取仅属于本应用的保存项，不接触其他网站的数据。 */
  read(key) {
    const value = this.storage.getItem(`farm.${key}`);
    return value ? JSON.parse(value) : null;
  }

  /** 保存课次标识或幂等请求，不保存录音和转录。 */
  save(key, value) {
    this.storage.setItem(`farm.${key}`, JSON.stringify(value));
  }

  /** 删除已经确认的单个请求，不做全局浏览器清理。 */
  remove(key) {
    this.storage.removeItem(`farm.${key}`);
  }

  /** 执行有超时限制的 JSON 请求；口令仅保留在当前对象内存。 */
  async request(path, body = undefined) {
    const response = await this.fetcher(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", "X-API-Token": this.token },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(6000),
      cache: "no-store",
    });
    if (!response.ok) throw new HttpError(response.status, "课堂暂时没有连接成功");
    return response.json();
  }

  /** 幂等创建课次；创建响应丢失时不会生成第二个会话。 */
  async create() {
    const body = this.read("creating") ?? { event_id: crypto.randomUUID() };
    this.save("creating", body);
    const state = await this.request("/v1/sessions", body);
    this.save("session", state.session_id);
    this.remove("creating");
    return state;
  }

  /** 读取权威状态，历史事件响应不作为最新进度使用。 */
  state(sessionId) {
    return this.request(`/v1/sessions/${encodeURIComponent(sessionId)}`);
  }

  /** 构造并保存一个事件，事件结果未知时拒绝生成后续新事件。 */
  async send(state, kind, fields = {}) {
    if (this.read("pending")) throw new Error("仍有待确认事件，请先重新连接");
    const channel = eventChannel(kind);
    const body = {
      event_id: crypto.randomUUID(),
      session_id: state.session_id,
      player_id: state.player_id,
      task_id: state.current_task.task_id,
      kind,
      sequence: (state.sequences[channel] ?? 0) + 1,
      ...fields,
    };
    const suffix = kind === "START" ? "start" : "control";
    const path =
      channel === "control"
        ? `/v1/sessions/${state.session_id}/${suffix}`
        : `/v1/${channel}/events`;
    this.save("pending", { path, body });
    return this.flush();
  }

  /** 重发原请求直到获得确认；失败时保留请求供刷新后继续。 */
  async flush() {
    const pending = this.read("pending");
    if (!pending) return null;
    const result = await this.request(pending.path, pending.body);
    this.remove("pending");
    return result;
  }

  /** 拉取某个设备通道的待执行动作，拉取本身不等于执行成功。 */
  commands(sessionId, audience) {
    return this.request(`/v1/${audience}/actions?session_id=${encodeURIComponent(sessionId)}`);
  }

  /** 在设备执行完成后确认动作，服务端允许安全重发该确认。 */
  ack(command) {
    return this.request(`/v1/${command.audience}/actions/${command.command_id}/ack`, {
      session_id: command.session_id,
    });
  }

  /** 获取本次学习观察报告，不从客户端操作推算成绩。 */
  progress(sessionId) {
    return this.request(`/v1/progress/${sessionId}`);
  }
}
