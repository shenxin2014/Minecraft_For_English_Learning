/** 农场视图适配器：执行有限的视觉意图，并在可见后提供视觉回执。 */

import { animalLayout } from "./presentation.js";

/** 将后端动作投影成可点击的农场场景，不自行发奖励或判断答案。 */
export class FarmScene {
  /** 保存场景节点与布局存储，不持有或修改教学评分。 */
  constructor(storage = localStorage) {
    this.storage = storage;
    this.farm = document.querySelector("#farm");
    this.animals = [...document.querySelectorAll(".animal")];
    this.taskId = null;
    this.highlightTimer = null;
    this.toastTimer = null;
    this.flowerCount = 0;
  }

  /** 切换任务时清除旧提示，并选择真正不同的背景与场景标签。 */
  showTask(state) {
    this.farm.classList.add("live");
    if (this.taskId === state.current_task.task_id) return;
    this.taskId = state.current_task.task_id;
    this.clearHints();
    this.setBackground(state.current_task.context);
    document.querySelector("#flowers").replaceChildren();
    this.flowerCount = 0;
    this.restoreRewards(state);
  }

  /** 按课程中的场景键选择本地画面，不使用外部图片资源。 */
  setBackground(context) {
    const scenes = {
      meadow: ["meadow", "围栏外的小草地"],
      review_pen: ["orchard", "果树旁的小围栏"],
    };
    const [image, label] = scenes[context] ?? ["farm", "Lily 的小农场"];
    this.farm.dataset.context = context;
    document.querySelector(".farm-background").src = `/assets/${image}.svg`;
    document.querySelector("#scene-label").textContent = label;
  }

  /** 为当前视觉命令安排布局；独立测试不额外高亮目标。 */
  async prepare(state) {
    this.showTask(state);
    if (state.current_task.randomize_positions) this.arrange(state.active_visual_id);
    else if (state.current_task.target) this.highlight(state.current_task.target, false);
    await this.waitForImages();
    return this.visible(state.current_task.target);
  }

  /** 将随机结果映射为左右位置，图片本身不显示英文答案。 */
  arrange(visualId) {
    const left = animalLayout(this.storage, visualId);
    for (const animal of this.animals) {
      animal.classList.toggle("slot-left", animal.dataset.animal === left);
      animal.classList.toggle("slot-right", animal.dataset.animal !== left);
    }
  }

  /** 等待场景与动物图片解码，损坏素材不能产生有效视觉回执。 */
  async waitForImages() {
    const images = [...this.farm.querySelectorAll("img")];
    await Promise.all(images.map((image) => image.decode()));
  }

  /** 核对目标确实位于可见页面内，后台标签不算视觉锚点。 */
  visible(target) {
    if (document.visibilityState !== "visible") return false;
    if (!target) return true;
    const rect = document.getElementById(target).getBoundingClientRect();
    return rect.width > 0 && rect.top >= 0 && rect.bottom <= window.innerHeight;
  }

  /** 依提示级别呈现动作线索、高亮或 Lily 的指引，不自动替孩子选择。 */
  showHint(command) {
    const target = document.getElementById(command.target_id);
    if (!target) return;
    if (command.hint_level === 2) this.animate(target, "cue");
    if (command.hint_level >= 3) this.highlight(command.target_id, true);
    if (command.hint_level === 4) this.showRoute(target);
  }

  /** 限时突出目标；提示历史由后端保存，视觉消失不恢复成 H0。 */
  highlight(target, temporary) {
    this.clearHints();
    document.getElementById(target)?.classList.add("highlight");
    if (temporary) this.highlightTimer = setTimeout(() => this.clearHints(), 3500);
  }

  /** 将 Lily 的说明放到目标上方，保留儿童主动点击的机会。 */
  showRoute(target) {
    const cue = document.querySelector("#route-cue");
    cue.style.left = target.classList.contains("slot-right") ? "61%" : "15%";
    cue.hidden = false;
  }

  /** 清理上一步的高亮和带路标记，避免污染独立辨认。 */
  clearHints() {
    clearTimeout(this.highlightTimer);
    for (const animal of this.animals) animal.classList.remove("highlight", "cue");
    document.querySelector("#route-cue").hidden = true;
  }

  /** 给自由点击提供短暂动作反馈，不提交虚构的理解事件。 */
  celebrate(animalName) {
    this.animate(document.getElementById(animalName), "happy");
  }

  /** 重启单次 CSS 动画；无动画偏好由样式层尊重。 */
  animate(element, className) {
    element.classList.remove(className);
    void element.offsetWidth;
    element.classList.add(className);
  }

  /** 以幂等样式状态应用开门和装饰奖励，不使用累计加分。 */
  reward(command) {
    const key = `farm.reward.${command.session_id}.${command.type}`;
    this.storage.setItem(key, "yes");
    if (command.type === "UNLOCK_GATE") document.querySelector("#gate").classList.add("open");
    if (command.type === "GRANT_COSMETIC") document.querySelector("#helper-badge").hidden = false;
  }

  /** 刷新后恢复已执行奖励的外观，未收到的命令仍由后端重新投递。 */
  restoreRewards(state) {
    const prefix = `farm.reward.${state.session_id}.`;
    document
      .querySelector("#gate")
      .classList.toggle("open", Boolean(this.storage.getItem(`${prefix}UNLOCK_GATE`)));
    document.querySelector("#helper-badge").hidden = !this.storage.getItem(
      `${prefix}GRANT_COSMETIC`,
    );
  }

  /** 在自由探索区增加有限数量的小花，没有计时、得分或语言门槛。 */
  plant() {
    if (this.flowerCount >= 10) return this.toast("小花园已经开满啦！");
    const flower = document.createElement("span");
    flower.textContent = "✿";
    flower.style.left = `${9 + Math.random() * 80}%`;
    flower.style.bottom = `${10 + Math.random() * 30}px`;
    flower.style.color = ["#faf0b1", "#f1b6ac", "#e3d3ef"][this.flowerCount % 3];
    document.querySelector("#flowers").append(flower);
    this.flowerCount += 1;
  }

  /** 展示温和的短反馈，不覆盖当前教学音频。 */
  toast(message) {
    clearTimeout(this.toastTimer);
    const element = document.querySelector("#scene-toast");
    element.textContent = message;
    element.hidden = false;
    this.toastTimer = setTimeout(() => {
      element.hidden = true;
    }, 2500);
  }
}
