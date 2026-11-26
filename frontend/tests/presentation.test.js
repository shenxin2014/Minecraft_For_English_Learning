/** 验证影响教学有效性的展示规则，不测试纯装饰样式。 */

import test from "node:test";
import assert from "node:assert/strict";
import { animalLayout, canPlayAudio, taskCopy } from "../js/presentation.js";
import { MemoryStorage, audioCommand, lessonState } from "./helpers.js";

test("同一视觉命令刷新后保留随机位置，新命令重新随机", () => {
  const storage = new MemoryStorage();
  assert.equal(
    animalLayout(storage, "first", () => 0.9),
    "pig",
  );
  assert.equal(
    animalLayout(storage, "first", () => 0.1),
    "pig",
  );
  assert.equal(
    animalLayout(storage, "second", () => 0.1),
    "cow",
  );
});

test("独立辨认文案不显示目标词和动物名称", () => {
  for (const task of ["find_cow", "find_pig", "rescue_cow", "review_pig", "review_cow"]) {
    const copy = taskCopy(task);
    assert.doesNotMatch(`${copy.title}${copy.detail}`, /cow|pig|小牛|小猪/i);
  }
});

test("当前未完成播放可用，已完成或旧命令不可重播", () => {
  assert.ok(canPlayAudio(lessonState(), audioCommand()));
  assert.ok(!canPlayAudio(lessonState(), audioCommand("old")));
  assert.ok(!canPlayAudio({ ...lessonState(), audio_finished: true }, audioCommand()));
});

test("本地暂停意图先于服务器响应阻止播放", () => {
  assert.ok(!canPlayAudio(lessonState(), audioCommand(), true));
  for (const state of ["READY", "PAUSED", "EXITED", "COMPLETE"]) {
    assert.ok(!canPlayAudio({ ...lessonState(), state }, audioCommand()));
  }
});
