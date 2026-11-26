/** 只提供页面文案与布局选择，不判断正确答案或学习等级。 */

const TASK_COPY = {
  welcome: [
    "先和动物朋友打个招呼吧。",
    "试着点一点动物。准备好了，再继续。",
    "熟悉小农场",
    "开始探索",
  ],
  introduce_cow: [
    "Look! A cow!",
    "看一看，听一听。也可以轻轻点它一下。",
    "认识新朋友",
    "认识下一位朋友",
  ],
  introduce_pig: [
    "Look! A pig!",
    "这是另一位动物朋友，仔细听听它的名字。",
    "认识新朋友",
    "一起找一找",
  ],
  find_cow: ["听听 Lily 在找谁。", "听完声音，再点一点动物。不着急。", "听声音找朋友", ""],
  find_pig: ["这次，Lily 在找谁呢？", "动物换了位置，小耳朵再来听一听。", "听声音找朋友", ""],
  rescue_cow: ["有个朋友走到草地上了。", "听听 Lily 的声音，帮它找到回家的路。", "帮朋友回家", ""],
  optional_say_cow: [
    "想和 Lily 一起说说看吗？",
    "可以跟着念，也可以直接继续。这里不会录音。",
    "想说就说",
    "继续玩",
  ],
  free_explore: [
    "现在，农场交给你啦。",
    "点点动物，种一朵小花。想玩多久都可以。",
    "自由探索",
    "最后再找一找",
  ],
  review_pig: [
    "换个地方，再认一认。",
    "先听声音，再选朋友。需要帮助就点“帮帮我”。",
    "再见，小伙伴",
    "",
  ],
  review_cow: ["最后一位朋友是谁呢？", "听一听，点一点。完成后就可以休息啦。", "再见，小伙伴", ""],
};

/** 返回稳定的场景文案；辨认任务不会把目标词显示给孩子。 */
export function taskCopy(taskId) {
  const [title, detail, stage, next] = TASK_COPY[taskId] ?? TASK_COPY.welcome;
  return { title, detail, stage, next };
}

/** 按视觉命令保存随机位置，刷新页面不会重新洗牌或泄露答案。 */
export function animalLayout(storage, visualId, random = Math.random) {
  const key = `farm.layout.${visualId}`;
  const existing = storage.getItem(key);
  if (existing === "cow" || existing === "pig") return existing;
  const leftAnimal = random() < 0.5 ? "cow" : "pig";
  storage.setItem(key, leftAnimal);
  return leftAnimal;
}

/** 判断当前状态是否允许开始音频，暂停、退出和完成都不能自动播放。 */
export function canPlayAudio(state, command, suspended = false) {
  if (suspended || ["PAUSED", "EXITED", "COMPLETE", "READY"].includes(state.state)) return false;
  return command.command_id === state.active_audio_id && !state.audio_finished;
}
