/** 协调 HTTP、播放器和农场视图；所有教学推进仍交给 LessonEngine。 */

import { FarmApi, HttpError } from "./api.js";
import { LessonAudio } from "./audio.js";
import { FarmScene } from "./scene.js";
import { ClassroomUi, element } from "./ui.js";
import { canPlayAudio } from "./presentation.js";

/** 串行编排设备与服务端之间的事件，隔离本地暂停和网络故障。 */
export class Classroom {
  /** 组装单职责组件和串行操作队列，防止点击与播放回执争抢序号。 */
  constructor() {
    this.api = new FarmApi();
    this.ui = new ClassroomUi();
    this.scene = new FarmScene();
    this.state = null;
    this.active = false;
    this.busy = false;
    this.suspended = false;
    this.offline = false;
    this.preparedVisual = null;
    this.settlingAudio = null;
    this.queue = Promise.resolve();
    this.hasLock = false;
    this.audio = new LessonAudio(
      new Audio(),
      (status) => this.audioStatus(status),
      (kind, command) => this.audioResult(kind, command),
    );
  }

  /** 读取上一课入口；页面加载本身不自动开始播放或创建课次。 */
  async initialize() {
    try {
      await this.api.request("/health");
      const sessionId = this.api.read("session");
      if (sessionId) this.state = await this.api.state(sessionId);
      this.render();
    } catch (error) {
      if (error.status === 404) {
        this.api.remove("session");
        this.render();
      } else this.fail(error);
    }
  }

  /** 对一个浏览器来源只允许一个活动课堂，避免两个标签同时控制同一进度。 */
  acquireLock() {
    if (this.hasLock || !navigator.locks) return Promise.resolve(true);
    return new Promise((resolve, reject) => {
      navigator.locks
        .request("english-farm-classroom", { ifAvailable: true }, async (lock) => {
          this.hasLock = Boolean(lock);
          resolve(this.hasLock);
          if (lock)
            await new Promise((release) => {
              this.releaseLock = release;
            });
        })
        .catch(reject);
    });
  }

  /** 用户明确点击后解锁声音、恢复未确认事件并进入课程。 */
  async start(fresh = false) {
    await this.audio.unlock();
    if (!(await this.acquireLock())) {
      this.ui.notice("另一个页面正在玩这节课，请先关闭那个页面。");
      return;
    }
    return this.run(async () => {
      await this.loadCourse(fresh);
      this.active = true;
      this.suspended = false;
      this.offline = false;
      this.ui.clearNotice();
      if (["PAUSED", "EXITED"].includes(this.state.state)) await this.dispatch("RESUME");
      if (this.state.state === "READY") await this.dispatch("START");
      this.scene.farm.scrollIntoView({ block: "center", behavior: "instant" });
    });
  }

  /** 优先恢复未知结果的旧请求，再决定复用会话或创建新课。 */
  async loadCourse(fresh) {
    await this.api.flush();
    const saved = this.api.read("session");
    this.state = saved ? await this.api.state(saved) : null;
    if (fresh && this.state && this.state.state !== "COMPLETE") await this.dispatch("EXIT");
    if (fresh || !this.state || this.state.state === "COMPLETE")
      this.state = await this.api.create();
  }

  /** 串行执行操作并刷新设备动作，网络失败后停止自动提交新请求。 */
  run(action) {
    this.queue = this.queue.then(async () => {
      this.busy = true;
      this.render();
      try {
        await action();
        if (this.active && !this.offline) await this.tick();
      } catch (error) {
        this.fail(error);
      } finally {
        this.busy = false;
        this.render();
      }
    });
    return this.queue;
  }

  /** 发送单个事件并采用服务端返回的结果，不在浏览器内推断下一任务。 */
  async dispatch(kind, fields = {}) {
    const result = await this.api.send(this.state, kind, fields);
    this.state = result.duplicate ? await this.api.state(this.state.session_id) : result.session;
    this.render();
    return result;
  }

  /** 读取最新状态，然后依次安排视觉和语音，防止先听到看不见的目标。 */
  async tick() {
    this.state = await this.api.state(this.state.session_id);
    if (["PAUSED", "EXITED"].includes(this.state.state)) {
      this.audio.stop();
      return;
    }
    this.scene.showTask(this.state);
    if (this.state.state !== "COMPLETE") await this.prepareVisual();
    await this.pumpGame();
    await this.pumpVoice();
    this.render();
  }

  /** 图片解码且目标进入视野后才回传视觉证据；新页面会恢复原随机布局。 */
  async prepareVisual() {
    const visualId = this.state.active_visual_id;
    if (!visualId || this.preparedVisual === visualId) return;
    this.scene.farm.scrollIntoView({ block: "center", behavior: "instant" });
    if (!(await this.scene.prepare(this.state))) throw new Error("请让动物完整显示在画面中");
    if (!this.state.visual_ready || !this.state.layout_ready) {
      const kind = this.state.current_task.randomize_positions ? "LAYOUT_READY" : "VISUAL_READY";
      await this.dispatch(kind, { command_id: visualId });
    }
    this.preparedVisual = visualId;
    if (this.state.hint_level >= 2)
      this.scene.showHint({
        target_id: this.state.current_task.target,
        hint_level: this.state.hint_level,
      });
  }

  /** 执行游戏视图命令，视觉回执已经在 prepareVisual 中完成。 */
  async pumpGame() {
    const commands = await this.api.commands(this.state.session_id, "game");
    for (const command of commands) {
      if (this.suspended) return;
      this.applyGameCommand(command);
      await this.api.ack(command);
    }
  }

  /** 仅映射支持的白名单动作；奖励使用幂等状态，不累计重复动画分数。 */
  applyGameCommand(command) {
    if (["UNLOCK_GATE", "GRANT_COSMETIC"].includes(command.type)) return this.scene.reward(command);
    if (command.task_id !== this.state.current_task.task_id) return;
    if (command.type === "SHOW_HINT" && !command.randomize_positions) this.scene.showHint(command);
    if (command.type === "SHOW_TITLE" && command.target_id === "audio_unavailable")
      this.ui.notice("声音没播出来。可以再听一遍，也可以继续玩。");
  }

  /** 播放命令直到 ended 才确认；刷新中断后仍可重新拉取同一命令。 */
  async pumpVoice() {
    const commands = await this.api.commands(this.state.session_id, "voice");
    for (const command of commands) {
      if (command.type === "STOP_AUDIO") {
        this.audio.stop();
        await this.api.ack(command);
      } else await this.startAudio(command);
    }
  }

  /** 过滤过期播放及重复拉取；页面暂停意图先于尚未返回的 HTTP 响应生效。 */
  async startAudio(command) {
    if (!canPlayAudio(this.state, command, this.suspended)) return;
    if (this.settlingAudio === command.command_id) return;
    if (this.audio.active?.command_id === command.command_id) return;
    await this.audio.play(command);
  }

  /** 将真实媒体终态送回后端，过期命令不会写到新的任务上。 */
  audioResult(kind, command) {
    this.settlingAudio = command.command_id;
    this.run(async () => {
      if (this.suspended || command.command_id !== this.state.active_audio_id) return;
      await this.dispatch(kind, { command_id: command.command_id, task_id: command.task_id });
      await this.api.ack(command);
      this.settlingAudio = null;
      if (kind === "AUDIO_FAILED") this.ui.notice("声音没播出来。可以再听一遍，也可以继续玩。");
    });
  }

  /** 同步播放指示与按钮可用性，不能在播放启动时就允许独立选择。 */
  audioStatus(status) {
    this.ui.sound(status);
    this.render();
  }

  /** 实际辨认交由服务器；探索时只做动画，不产生听力正确事件。 */
  choose(animal) {
    return this.run(async () => {
      if (!this.active || this.suspended || this.offline) return;
      if (this.state.current_task.type !== "LISTEN_FIND") return this.scene.celebrate(animal);
      const result = await this.dispatch("ENTITY_INTERACTED", {
        entity_type: `minecraft:${animal}`,
      });
      const message = result.result === "wrong_target" ? "再听听看，慢慢找。" : "找到啦，谢谢你！";
      this.scene.toast(message);
    });
  }

  /** 统一转发普通课程控制；跳过和重听会立即停止本地旧声音。 */
  control(kind) {
    if (this.offline || !this.active) return;
    if (["SKIP", "REPLAY"].includes(kind)) this.audio.stop();
    return this.run(async () => {
      await this.dispatch(kind);
    });
  }

  /** 先停止声音再请求暂停，慢网络也不会让孩子被迫继续听。 */
  pause() {
    if (!this.active || this.suspended || this.state?.state === "COMPLETE") return;
    this.suspended = true;
    this.audio.stop();
    this.render();
    if (!this.offline)
      return this.run(async () => {
        await this.dispatch("PAUSE");
      });
  }

  /** 恢复前让用户重新确认播放意愿，然后由后端恢复原任务。 */
  async resume() {
    await this.audio.unlock();
    return this.run(async () => {
      this.suspended = false;
      await this.dispatch("RESUME");
    });
  }

  /** 退出保留服务器进度和本地入口，不删除学习记录。 */
  exit() {
    this.audio.stop();
    this.suspended = true;
    return this.run(async () => {
      await this.dispatch("EXIT");
      this.active = false;
      this.scene.clearHints();
      this.releaseLock?.();
      this.hasLock = false;
    });
  }

  /** 优先重试未知结果的原事件，再恢复最新进度与尚未播完的音频。 */
  recover() {
    return this.run(async () => {
      await this.api.flush();
      this.state = this.api.read("session") ? await this.api.state(this.api.read("session")) : null;
      this.offline = false;
      this.suspended = ["PAUSED", "EXITED"].includes(this.state?.state);
      this.preparedVisual = null;
      this.ui.clearNotice();
    });
  }

  /** 网络或认证失败时停止本地播放，保留待确认事件而非偷偷跳过。 */
  fail(error) {
    console.warn("Classroom operation failed", error.name, error.message);
    this.offline = true;
    this.audio.stop();
    if (error instanceof HttpError && error.status === 401) {
      if (!element("access-dialog").open) element("access-dialog").showModal();
    } else this.ui.notice("课堂连接暂时中断，进度会保留。准备好后重新连接。", "reconnect");
  }

  /** 绘制页面，不将展示动作反向当作教学事件。 */
  render() {
    this.scene.farm.classList.toggle("live", this.active);
    this.ui.render(this.state, {
      active: this.active,
      busy: this.busy,
      suspended: this.suspended || this.offline,
    });
  }
}
