import { FarmApi } from "./api.js";
import { LessonAudio } from "./audio.js";
import { BedrockCompanion, scopedStorage } from "./bedrock-companion.js";

let companion = null;
let releaseLock = null;

/** 显示连接及流程状态，不把听力目标词作为页面答案提示。 */
function render(view, error) {
  document.querySelector("#error").textContent = error;
  if (!view) return;
  const state = view.session;
  const labels = {
    READY: "与 Lily 互动，开始探索",
    PAUSED: "课堂已暂停",
    EXITED: "本次已结束，可恢复",
    COMPLETE: "今天的探索完成了",
  };
  document.querySelector("#status").textContent =
    labels[state.state] ?? (view.visible ? "Lily 正在陪你探索" : "等待游戏连接或目标进入视野");
  document.querySelector("#step").textContent =
    `探索进度 ${state.task_index + 1} / ${state.total_tasks}`;
  document.querySelector("#controls").hidden = false;
}

/** 一个课次只允许一个伴随页消费语音命令，避免两个窗口重复播放。 */
async function connect(event) {
  event.preventDefault();
  if (companion) {
    companion.api.token = document.querySelector("#token").value;
    companion.playback = null;
    await companion.audio.unlock();
    return;
  }
  const bridgeId = document.querySelector("#bridge").value;
  if (!/^[A-Za-z0-9_-]{1,60}$/.test(bridgeId)) return;
  const api = new FarmApi(scopedStorage(localStorage, bridgeId));
  api.token = document.querySelector("#token").value;
  const audio = new LessonAudio(
    undefined,
    () => {},
    (kind, command) => companion?.finished(kind, command),
  );
  await audio.unlock();
  void navigator.locks.request(`farm-bedrock-${bridgeId}`, { ifAvailable: true }, async (lock) => {
    if (!lock) {
      render(null, "该课堂已在另一个伴随页打开。");
      return;
    }
    companion = new BedrockCompanion(api, audio, bridgeId, render);
    document.querySelector("#bridge").disabled = true;
    await companion.run(() => companion.pulse());
    await new Promise((resolve) => {
      releaseLock = resolve;
    });
  });
}

document.querySelector("#connect-form").addEventListener("submit", connect);
document.querySelectorAll("[data-control]").forEach((button) => {
  button.addEventListener("click", () => {
    if (companion) void companion.run(() => companion.control(button.dataset.control));
  });
});
document
  .querySelector("#volume")
  .addEventListener("input", (event) => companion?.audio.setVolume(event.target.value));
document.querySelector("#enable-audio").addEventListener("click", async () => {
  if (!companion) return;
  companion.playback = null;
  await companion.audio.unlock();
  await companion.run(() => companion.pulse());
});
window.addEventListener("pagehide", () => {
  companion?.audio.stop();
  releaseLock?.();
});
// Minecraft 获得焦点时页面可能隐藏；语音继续，但游戏租约失效会停止播放。
setInterval(() => {
  if (companion && !companion.busy) void companion.run(() => companion.pulse());
}, 400);
