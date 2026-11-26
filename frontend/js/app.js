/** 页面入口：绑定用户意图，生命周期变化时立即停止声音。 */

import { Classroom } from "./classroom.js";
import { element } from "./ui.js";

/** 将简单按钮绑定到单一意图，避免把事件与界面逻辑堆在一起。 */
function bindControls(classroom) {
  element("start-button").addEventListener("click", () => classroom.start());
  element("fresh-button").addEventListener("click", () => classroom.start(true));
  element("again-button").addEventListener("click", () => classroom.start(true));
  element("pause-button").addEventListener("click", () => classroom.pause());
  element("resume-button").addEventListener("click", () => classroom.resume());
  element("exit-button").addEventListener("click", () => classroom.exit());
  element("replay-button").addEventListener("click", () => classroom.control("REPLAY"));
  element("help-button").addEventListener("click", () => classroom.control("HELP"));
  element("skip-button").addEventListener("click", () => classroom.control("SKIP"));
  element("continue-button").addEventListener("click", () =>
    classroom.control(classroom.state.current_task.type === "OPTIONAL_SPEAK" ? "SKIP" : "CONTINUE"),
  );
  element("plant-button").addEventListener("click", () => classroom.scene.plant());
  element("reconnect-button").addEventListener("click", () => classroom.recover());
  element("unlock-button").addEventListener("click", () => {
    classroom.ui.clearNotice();
    classroom.audio.retry();
  });
  for (const animal of document.querySelectorAll(".animal"))
    animal.addEventListener("click", () => classroom.choose(animal.dataset.animal));
}

/** 家长面板打开时先暂停课堂，音量变化不影响已有学习判断。 */
function bindParentPanels(classroom) {
  element("parent-button").addEventListener("click", () => {
    classroom.pause();
    element("parent-dialog").showModal();
  });
  element("close-parent").addEventListener("click", () => element("parent-dialog").close());
  element("close-report").addEventListener("click", () => element("report-dialog").close());
  element("report-button").addEventListener("click", () =>
    classroom.run(async () => {
      classroom.ui.showReport(await classroom.api.progress(classroom.state.session_id));
    }),
  );
  element("volume-control").addEventListener("input", (event) =>
    classroom.audio.setVolume(event.target.value),
  );
  element("access-form").addEventListener("submit", (event) => {
    event.preventDefault();
    classroom.api.token = element("access-token").value;
    element("access-token").value = "";
    element("access-dialog").close();
    classroom.recover();
  });
}

/** 隐藏标签或目标离开视野时暂停，避免把后台播放当作同步输入。 */
function bindLifecycle(classroom) {
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) classroom.pause();
  });
  window.addEventListener("pagehide", () => {
    classroom.audio.stop();
    classroom.releaseLock?.();
  });
  window.addEventListener(
    "scroll",
    () => {
      const target = classroom.state?.current_task.target;
      if (classroom.audio.active && target && !classroom.scene.visible(target)) classroom.pause();
    },
    { passive: true },
  );
  window.addEventListener("resize", () => {
    const target = classroom.state?.current_task.target;
    if (classroom.audio.active && target && !classroom.scene.visible(target)) classroom.pause();
  });
  setInterval(() => {
    if (
      classroom.active &&
      !classroom.busy &&
      !classroom.offline &&
      !classroom.suspended &&
      !document.hidden
    )
      classroom.run(async () => {});
  }, 800);
}

const classroom = new Classroom();
bindControls(classroom);
bindParentPanels(classroom);
bindLifecycle(classroom);
classroom.initialize();
