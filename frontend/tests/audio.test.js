/** 验证真实播放器边界：播放开始、结束、取消、拒绝和失败必须区分。 */

import test from "node:test";
import assert from "node:assert/strict";
import { LessonAudio } from "../js/audio.js";
import { FakeAudio, audioCommand } from "./helpers.js";

test("只有 ended 才提交一次成功回执", async () => {
  const media = new FakeAudio();
  const results = [];
  const player = new LessonAudio(
    media,
    () => {},
    (...args) => results.push(args),
  );
  await player.play(audioCommand());
  assert.equal(results.length, 0);
  media.dispatchEvent(new Event("ended"));
  media.dispatchEvent(new Event("ended"));
  assert.equal(results.length, 1);
  assert.equal(results[0][0], "AUDIO_FINISHED");
  assert.equal(results[0][1].command_id, "audio-01");
});

test("暂停后迟到的 ended 和 error 不产生回执", async () => {
  const media = new FakeAudio();
  const results = [];
  const player = new LessonAudio(
    media,
    () => {},
    (...args) => results.push(args),
  );
  await player.play(audioCommand());
  player.stop();
  media.dispatchEvent(new Event("ended"));
  media.dispatchEvent(new Event("error"));
  assert.equal(media.paused, true);
  assert.deepEqual(results, []);
});

test("自动播放限制保留原命令，手动解锁后仍只回执一次", async () => {
  const media = new FakeAudio();
  media.playBehavior = () => Promise.reject(new DOMException("blocked", "NotAllowedError"));
  const statuses = [];
  const results = [];
  const player = new LessonAudio(
    media,
    (value) => statuses.push(value),
    (...args) => results.push(args),
  );
  await player.play(audioCommand());
  assert.equal(statuses.at(-1), "blocked");
  assert.equal(results.length, 0);
  assert.equal(player.active.command_id, "audio-01");
  media.playBehavior = () => Promise.resolve();
  await player.retry();
  media.dispatchEvent(new Event("ended"));
  assert.equal(results.length, 1);
  assert.equal(results[0][1].command_id, "audio-01");
});

test("媒体解码失败只提交失败，不计为播放完成", async () => {
  const media = new FakeAudio();
  const results = [];
  const player = new LessonAudio(
    media,
    () => {},
    (...args) => results.push(args),
  );
  await player.play(audioCommand());
  media.dispatchEvent(new Event("error"));
  media.dispatchEvent(new Event("ended"));
  assert.equal(results.length, 1);
  assert.equal(results[0][0], "AUDIO_FAILED");
});

test("旧播放 Promise 的迟到拒绝不会终止新播放", async () => {
  const media = new FakeAudio();
  let rejectOld;
  media.playBehavior = () =>
    new Promise((_resolve, reject) => {
      rejectOld = reject;
    });
  const results = [];
  const player = new LessonAudio(
    media,
    () => {},
    (...args) => results.push(args),
  );
  const old = player.play(audioCommand("old"));
  media.playBehavior = () => Promise.resolve();
  await player.play(audioCommand("new"));
  rejectOld(new Error("old media aborted"));
  await old;
  assert.equal(player.active.command_id, "new");
  assert.equal(results.length, 0);
  player.stop();
});

test("H1 略微减速，普通语音使用自然速率", async () => {
  const media = new FakeAudio();
  const player = new LessonAudio(media);
  await player.play({ ...audioCommand(), hint_level: 1 });
  assert.equal(media.playbackRate, 0.88);
  await player.play(audioCommand("next"));
  assert.equal(media.playbackRate, 1);
  player.stop();
});

test("音量不允许静音，防止静音播放被当作有效输入", () => {
  const media = new FakeAudio();
  const player = new LessonAudio(media);
  player.setVolume(0);
  assert.equal(media.volume, 0.25);
  player.setVolume(2);
  assert.equal(media.volume, 1);
});
