/** 当前游戏租约和教学状态允许播放时才启动；不生成任何游戏视觉事件。 */
export function canHear(view) {
  const state = view?.session;
  if (!state || !view.visible || ["READY", "PAUSED", "EXITED", "COMPLETE"].includes(state.state))
    return false;
  return !state.current_task.target || state.visual_ready;
}

/** 将本页的重试记录与 M1 离线课堂隔离，避免共享待发送事件。 */
export function scopedStorage(storage, bridgeId) {
  const prefix = `bedrock.${bridgeId}.`;
  return {
    getItem: (key) => storage.getItem(prefix + key),
    setItem: (key, value) => storage.setItem(prefix + key, value),
    removeItem: (key) => storage.removeItem(prefix + key),
  };
}

/** 复用真实媒体播放器与 API，串行协调伴随音频，不模拟游戏动作。 */
export class BedrockCompanion {
  /** 依赖注入便于检查音频结果丢失、断线和可见性变化。 */
  constructor(api, audio, bridgeId, render = () => {}) {
    this.api = api;
    this.audio = audio;
    this.bridgeId = bridgeId;
    this.render = render;
    this.view = null;
    this.playback = null;
    this.settling = Boolean(api.read("finishing"));
    this.chain = Promise.resolve();
    this.busy = false;
  }

  /** 将用户控制、网络恢复与播放结束放入同一串行队列。 */
  run(action) {
    this.chain = this.chain
      .then(async () => {
        this.busy = true;
        try {
          await action();
        } finally {
          this.busy = false;
        }
      })
      .catch(() => {
        this.audio.stop();
        this.playback = null;
        this.render(this.view, "连接中断或口令无效，恢复连接后自动重试。");
      });
    return this.chain;
  }

  /** 获取最新可见性，不从上一次成功请求推断当前游戏仍在运行。 */
  async refresh() {
    this.view = await this.api.request(`/v1/bedrock/companion/${this.bridgeId}`);
    this.render(this.view, "");
  }

  /** 先恢复未完成回执，再考虑播放新命令，避免重复播报。 */
  async pulse() {
    if (this.api.read("finishing")) await this.settle();
    else await this.api.flush();
    await this.refresh();
    this.guardPlayback();
    const commands = await this.api.commands(this.view.session.session_id, "voice");
    for (const command of commands) await this.consume(command);
  }

  /** 可见性代次变化意味着期间中断过，必须停止并从头播放。 */
  guardPlayback() {
    if (!this.playback) return;
    if (
      !canHear(this.view) ||
      this.playback.epoch !== this.view.epoch ||
      this.playback.command.command_id !== this.view.session.active_audio_id
    ) {
      this.audio.stop();
      this.playback = null;
    }
  }

  /** STOP_AUDIO 随时生效；实际 ended 之前不确认播放命令。 */
  async consume(command) {
    if (command.type === "STOP_AUDIO") {
      this.audio.stop();
      this.playback = null;
      await this.api.ack(command);
      return;
    }
    const state = this.view.session;
    if (!canHear(this.view) || this.settling || this.playback || state.audio_finished) return;
    if (command.command_id !== state.active_audio_id) return;
    this.playback = { command, epoch: this.view.epoch, state: structuredClone(state) };
    await this.audio.play(command);
  }

  /** 保存完成事件后才发请求，关闭页面或 ACK 丢失仍可重试原正文。 */
  finished(kind, command) {
    const playback = this.playback;
    if (!playback || playback.command.command_id !== command.command_id) return;
    this.settling = true;
    const state = playback.state;
    this.api.save("finishing", {
      command,
      body: {
        visibility_epoch: playback.epoch,
        event: {
          event_id: crypto.randomUUID(),
          session_id: state.session_id,
          player_id: state.player_id,
          task_id: state.current_task.task_id,
          kind,
          sequence: (state.sequences.voice ?? 0) + 1,
          command_id: command.command_id,
        },
      },
    });
    this.playback = null;
    return this.run(() => this.settle());
  }

  /** 回执被可见性规则拒绝时不 ACK，等待游戏恢复后重新真实播放。 */
  async settle() {
    const finishing = this.api.read("finishing");
    if (!finishing) return;
    // 控制请求可能先发生断线，必须先清理原控制请求而不覆盖它。
    const pending = this.api.read("pending");
    if (pending && pending.path !== "/v1/bedrock/audio") await this.api.flush();
    this.api.save("pending", { path: "/v1/bedrock/audio", body: finishing.body });
    const receipt = await this.api.flush();
    if (receipt.result === "accepted") await this.api.ack(finishing.command);
    this.api.remove("finishing");
    this.settling = false;
  }

  /** 用户控制仍由 LessonEngine 判定，暂停意图立即停止本地声音。 */
  async control(kind) {
    if (["PAUSE", "EXIT", "SKIP"].includes(kind)) {
      this.audio.stop();
      this.playback = null;
    }
    if (this.api.read("finishing")) await this.settle();
    await this.api.flush();
    await this.refresh();
    await this.api.send(this.view.session, kind);
    await this.pulse();
  }
}
