/** 短音频播放器：只在真实 ended 后报告完成，暂停与取消不产生完成回执。 */

/** 管理唯一的媒体元素，取消旧回调并产出真实的播放结果。 */
export class LessonAudio {
  /** 注入媒体对象和状态回调，既支持浏览器，也支持无声设备故障测试。 */
  constructor(audio = new Audio(), onStatus = () => {}, onResult = () => {}) {
    this.audio = audio;
    this.onStatus = onStatus;
    this.onResult = onResult;
    this.active = null;
    this.generation = 0;
    this.listeners = null;
    this.timer = null;
    this.audio.volume = 0.85;
    this.audio.preload = "auto";
  }

  /** 在用户点击时解锁同一媒体元素，不把静音预热计为教学播放。 */
  async unlock() {
    this.stop();
    const generation = this.generation;
    this.audio.muted = true;
    this.audio.src = "/assets/audio/welcome_en.wav";
    try {
      await this.audio.play();
    } catch {
      // 浏览器仍可能要求下一次明确点击；正式播放时显示解锁按钮。
    }
    if (generation === this.generation) this.stop();
    this.audio.muted = false;
  }

  /** 启动固定语音；返回的是播放启动结果，不等待整段音频播完。 */
  async play(command) {
    this.stop();
    this.active = command;
    const generation = this.generation;
    this.audio.src = `/assets/audio/${encodeURIComponent(command.audio_id)}.wav`;
    this.audio.playbackRate = command.hint_level === 1 ? 0.88 : 1;
    this.bindEvents(generation);
    this.onStatus("loading");
    this.timer = setTimeout(() => this.finish("AUDIO_FAILED", generation), 20000);
    try {
      await this.audio.play();
      if (generation === this.generation) this.onStatus("playing");
    } catch (error) {
      this.handlePlayError(error, generation);
    }
  }

  /** 每次播放独立绑定监听器，旧媒体事件不能冒充新播放。 */
  bindEvents(generation) {
    this.listeners = new AbortController();
    const options = { signal: this.listeners.signal };
    this.audio.addEventListener("ended", () => this.finish("AUDIO_FINISHED", generation), options);
    this.audio.addEventListener("error", () => this.finish("AUDIO_FAILED", generation), options);
  }

  /** 区分自动播放限制与文件/设备失败，未获播放许可不算播放失败。 */
  handlePlayError(error, generation) {
    if (generation !== this.generation) return;
    if (error.name === "NotAllowedError") {
      clearTimeout(this.timer);
      this.onStatus("blocked");
      return;
    }
    this.finish("AUDIO_FAILED", generation);
  }

  /** 用户明确点击后重试原命令，不为一次解锁生成新教学事件。 */
  retry() {
    if (this.active) return this.play(this.active);
  }

  /** 只提交当前播放的一次终态，排除取消后的迟到回调。 */
  finish(kind, generation) {
    if (generation !== this.generation || !this.active) return;
    const command = this.active;
    this.stop();
    this.onResult(kind, command);
  }

  /** 立即停止声音并作废回调，供暂停、退出、切换任务和隐藏页面使用。 */
  stop() {
    this.generation += 1;
    clearTimeout(this.timer);
    this.listeners?.abort();
    this.audio.pause();
    this.active = null;
    this.onStatus("idle");
  }

  /** 限制音量为非静音区间，避免把静音播放错误计为有效呈现。 */
  setVolume(value) {
    this.audio.volume = Math.max(0.25, Math.min(1, Number(value)));
  }
}
