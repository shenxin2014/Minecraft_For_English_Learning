/** 验证客户端的幂等、通道和认证边界，包含网络断开后重建客户端。 */

import test from "node:test";
import assert from "node:assert/strict";
import { FarmApi, HttpError, eventChannel } from "../js/api.js";
import { MemoryStorage, jsonResponse, lessonState } from "./helpers.js";

test("响应丢失后刷新客户端仍重发原事件 ID 和序号", async () => {
  const storage = new MemoryStorage();
  const sent = [];
  const failed = new FarmApi(storage, async (_path, options) => {
    sent.push(JSON.parse(options.body));
    throw new TypeError("connection lost after submit");
  });
  await assert.rejects(
    failed.send(lessonState(), "ENTITY_INTERACTED", { entity_type: "minecraft:cow" }),
  );
  const restored = new FarmApi(storage, async (_path, options) => {
    sent.push(JSON.parse(options.body));
    return jsonResponse({ duplicate: true });
  });
  await restored.flush();
  assert.deepEqual(sent[0], sent[1]);
  assert.equal(sent[0].sequence, 5);
  assert.equal(restored.read("pending"), null);
});

test("旧事件结果未知时不能提交后续新事件", async () => {
  const storage = new MemoryStorage();
  const api = new FarmApi(storage, () => {
    throw new Error("不应发起新请求");
  });
  api.save("pending", { body: { event_id: "existing" } });
  await assert.rejects(api.send(lessonState(), "HELP"), /待确认事件/);
  assert.equal(api.read("pending").body.event_id, "existing");
});

test("创建会话响应丢失时复用原创建请求", async () => {
  const storage = new MemoryStorage();
  const sent = [];
  const api = new FarmApi(storage, async (_path, options) => {
    sent.push(JSON.parse(options.body));
    if (sent.length === 1) throw new TypeError("offline");
    return jsonResponse({ session_id: "created-once" });
  });
  await assert.rejects(api.create());
  await api.create();
  assert.deepEqual(sent[0], sent[1]);
  assert.equal(api.read("session"), "created-once");
  assert.equal(api.read("creating"), null);
});

test("认证失败保留未确认事件，口令不写入存储", async () => {
  const api = new FarmApi(new MemoryStorage(), async () => jsonResponse({}, 401));
  api.token = "in-memory-only";
  await assert.rejects(
    api.send(lessonState(), "REPLAY"),
    (error) => error instanceof HttpError && error.status === 401,
  );
  assert.ok(api.read("pending"));
  assert.ok(!JSON.stringify([...api.storage.values]).includes("in-memory-only"));
});

test("默认 fetch 以浏览器全局函数调用，不绑定到 FarmApi 实例", async (context) => {
  context.mock.method(globalThis, "fetch", function () {
    assert.ok(!(this instanceof FarmApi));
    return Promise.resolve(jsonResponse({ status: "ok" }));
  });
  const api = new FarmApi(new MemoryStorage());
  assert.deepEqual(await api.request("/health"), { status: "ok" });
});

test("开始和控制共享序号，游戏与语音分开", () => {
  assert.equal(eventChannel("START"), "control");
  assert.equal(eventChannel("PAUSE"), "control");
  assert.equal(eventChannel("AUDIO_FINISHED"), "voice");
  assert.equal(eventChannel("ENTITY_INTERACTED"), "game");
});
