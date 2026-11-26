/** 页面状态投影：显示后端结论和设备状态，不在这里判断学习成绩。 */

import { taskCopy } from "./presentation.js";

/** 获取约定的页面节点，拼写错误在开发时直接暴露。 */
export function element(id) {
  return document.getElementById(id);
}

/** 根据课程快照更新文案、按钮与家长观察面板。 */
export class ClassroomUi {
  /** 记录播放器的展示状态，避免课程刷新覆盖实际播放指示。 */
  constructor() {
    this.soundState = "idle";
  }

  /** 将后端快照和客户端忙碌状态分别投影到页面。 */
  render(state, flags) {
    const { active, busy, suspended } = flags;
    element("welcome-panel").hidden = active;
    element("start-label").textContent =
      state && state.state !== "COMPLETE" ? "继续上次的旅程" : "去农场玩";
    element("fresh-button").hidden = !state || active;
    element("start-button").disabled = busy;
    if (!state) return;
    this.renderTask(state);
    this.renderControls(state, { active, busy, suspended });
    element("pause-panel").hidden = !active || !["PAUSED", "EXITED"].includes(state.state);
    element("complete-panel").hidden = !active || state.state !== "COMPLETE";
    element("complete-title").textContent = state.video_game_task_complete
      ? "小牛回家啦，谢谢你！"
      : "谢谢你，小小探索家！";
  }

  /** 独立辨认只显示中性说明，目标词不会出现在字幕或进度文字里。 */
  renderTask(state) {
    const copy = taskCopy(state.current_task.task_id);
    if (state.state === "COMPLETE") {
      copy.title = "今天的探索结束啦。";
      copy.detail = "休息一下，明天再来看看动物朋友。";
    }
    element("instruction").textContent = copy.title;
    element("instruction-detail").textContent = copy.detail;
    element("stage-label").textContent =
      state.state === "COMPLETE" ? "今天的旅程完成啦" : copy.stage;
    const completed = state.state === "COMPLETE" ? state.total_tasks : state.task_index;
    element("journey-fill").style.width = `${(completed / state.total_tasks) * 100}%`;
    element("journey-bar").setAttribute("aria-valuenow", completed);
    element("journey-bar").setAttribute("aria-valuemax", state.total_tasks);
    element("step-label").textContent =
      `旅程 ${Math.min(completed + 1, state.total_tasks)} / ${state.total_tasks}`;
    element("continue-button").textContent = copy.next || "继续探索";
  }

  /** 只开放当前任务可用的控制，实际事件仍由后端再次校验。 */
  renderControls(state, flags) {
    const resting = ["PAUSED", "EXITED", "COMPLETE", "READY"].includes(state.state);
    const available = flags.active && !flags.busy && !flags.suspended && !resting;
    const waiting = ["AWAITING_GAME_ACTION", "HINTING", "OPTIONAL_SPEAK"].includes(state.state);
    const listening = state.current_task.type === "LISTEN_FIND";
    this.renderSupport(flags, { resting, available, waiting, listening });
    this.renderContinue(flags, { resting, available, waiting, listening });
    this.renderAnimals(available, waiting, listening);
    element("plant-button").hidden = state.current_task.task_id !== "free_explore" || resting;
    element("plant-button").disabled = !available;
  }

  /** 控制求助和暂停等支持动作，不涉及任务推进按钮。 */
  renderSupport(flags, { resting, available, waiting, listening }) {
    element("pause-button").hidden = !flags.active || resting;
    element("replay-button").disabled = !available;
    element("help-button").disabled = !available || !listening || !waiting;
    element("skip-button").hidden = !flags.active || resting;
    element("skip-button").disabled = !available;
  }

  /** 只让观察、探索或自愿口语显示继续按钮。 */
  renderContinue(flags, { resting, available, waiting, listening }) {
    element("continue-button").hidden = !flags.active || resting || listening;
    element("continue-button").disabled = !available || !waiting || this.soundState !== "idle";
  }

  /** 播放指令期间暂不接受独立选择，防止随机抢答。 */
  renderAnimals(available, waiting, listening) {
    for (const animal of document.querySelectorAll(".animal")) {
      animal.disabled = !available || (listening && (!waiting || this.soundState !== "idle"));
    }
  }

  /** 根据媒体元素的真实状态显示加载、播放和需手动解锁提示。 */
  sound(status) {
    this.soundState = status;
    const labels = {
      idle: "Lily 陪你一起探索",
      loading: "准备声音中…",
      playing: "Lily 正在说话",
      blocked: "点一下，听 Lily 说话",
    };
    element("audio-status").textContent = labels[status];
    element("sound-bars").hidden = status !== "playing";
    if (status === "blocked") this.notice("浏览器需要你点一下，才能播放声音。", "unlock");
  }

  /** 显示可恢复的问题，只提供当前确实可执行的操作。 */
  notice(message, action = null) {
    element("notice-message").textContent = message;
    element("notice").hidden = false;
    element("reconnect-button").hidden = action !== "reconnect";
    element("unlock-button").hidden = action !== "unlock";
  }

  /** 问题解决后移除提示，不清除课程状态。 */
  clearNotice() {
    element("notice").hidden = true;
  }

  /** 用 DOM 文本生成家长报告，避免把远端字符串当作 HTML 执行。 */
  showReport(report) {
    const root = element("report-content");
    root.replaceChildren();
    const story = document.createElement("p");
    story.className = "report-story";
    story.textContent = report.video_game_task_complete
      ? "游戏故事：已经帮助小牛回家。"
      : "游戏故事：这次尚未完成找回小牛。";
    root.append(story, this.reportTable(report.vocab_mastery));
    const note = document.createElement("p");
    note.className = "dialog-note";
    note.textContent = `操作求助 ${report.operational_blocks} 次 · 主动重听 ${report.replay_requests} 次。本课未启用录音，口语不作评估。`;
    root.append(note);
    element("report-dialog").showModal();
  }

  /** 展示独立与提示结果，呈现次数不会被称为掌握程度。 */
  reportTable(words) {
    const table = document.createElement("table");
    const heading = table.createTHead().insertRow();
    for (const label of ["朋友", "独立找对", "有帮助找对", "还需观察"]) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      heading.append(cell);
    }
    const body = table.createTBody();
    for (const [word, values] of Object.entries(words)) {
      const row = body.insertRow();
      for (const value of [
        word,
        values.independent_correct,
        values.assisted_correct,
        values.unconfirmed_correct,
      ])
        row.insertCell().textContent = value;
    }
    return table;
  }
}
