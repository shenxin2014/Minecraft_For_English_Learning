import test from "node:test";
import assert from "node:assert/strict";
import { BedrockCompanion, canHear, scopedStorage } from "../js/bedrock-companion.js";
import { FarmApi } from "../js/api.js";
import { MemoryStorage, audioCommand, lessonState, jsonResponse } from "./helpers.js";

/** 提供不产生自动 ended 的播放器和可控网络。 */
function fixture() {
  const view = {
    session: {
      ...lessonState(),
      visual_ready: true,
      current_task: { task_id: "find_cow", target: "cow" },
    },
    visible: true,
    epoch: 3,
  };
  const posts = [];
  const command = { ...audioCommand(), audience: "voice", type: "PLAY_AUDIO" };
  const fetcher = async (path, options) => {
    if (options.body) {
      posts.push({ path, body: JSON.parse(options.body) });
      return jsonResponse({ result: "accepted" });
    }
    return jsonResponse(path.includes("actions") ? [command] : view);
  };
  const api = new FarmApi(new MemoryStorage(), fetcher);
  const audio = {
    plays: 0,
    stops: 0,
    play: async () => {
      audio.plays += 1;
    },
    stop: () => {
      audio.stops += 1;
    },
  };
  const companion = new BedrockCompanion(api, audio, "world_1");
  return { companion, api, audio, view, command, posts };
}

test("companion waits for actual game evidence and never emits game events", async () => {
  const f = fixture();
  f.view.session.visual_ready = false;
  await f.companion.pulse();
  assert.equal(f.audio.plays, 0);
  f.view.session.visual_ready = true;
  await f.companion.pulse();
  await f.companion.pulse();
  assert.equal(f.audio.plays, 1);
  assert.equal(f.posts.length, 0);
});

test("visibility generation change stops old playback and restarts without completion receipt", async () => {
  const f = fixture();
  await f.companion.pulse();
  f.view.epoch += 1;
  await f.companion.pulse();
  assert.equal(f.audio.stops, 1);
  assert.equal(f.audio.plays, 2);
  assert.equal(f.posts.length, 0);
});

test("audio ends once and retry after lost ACK keeps same event and epoch", async () => {
  const f = fixture();
  await f.companion.pulse();
  const ack = f.api.ack.bind(f.api);
  f.api.ack = async () => {
    throw new Error("lost ACK");
  };
  await f.companion.finished("AUDIO_FINISHED", f.command);
  const finishing = f.api.read("finishing");
  assert.equal(finishing.body.visibility_epoch, 3);
  f.api.ack = ack;
  const restored = new BedrockCompanion(f.api, f.audio, "world_1");
  await restored.settle();
  const sent = f.posts.filter((post) => post.path === "/v1/bedrock/audio");
  assert.equal(sent.length, 2);
  assert.deepEqual(sent[0].body, sent[1].body);
  assert.equal(f.api.read("finishing"), null);
});

test("server rejected visual lease does not ACK audio or pretend it played successfully", async () => {
  const f = fixture();
  await f.companion.pulse();
  f.api.flush = async () => {
    f.api.remove("pending");
    return { result: "ignored_bds_visibility" };
  };
  let acked = false;
  f.api.ack = async () => {
    acked = true;
  };
  await f.companion.finished("AUDIO_FINISHED", f.command);
  assert.equal(acked, false);
  assert.equal(f.companion.settling, false);
});

test("paused or disconnected views cannot play and storage is isolated from M1", () => {
  const f = fixture();
  assert.equal(canHear({ ...f.view, visible: false }), false);
  assert.equal(canHear({ ...f.view, session: { ...f.view.session, state: "PAUSED" } }), false);
  const disk = new MemoryStorage();
  const one = scopedStorage(disk, "one");
  const two = scopedStorage(disk, "two");
  one.setItem("farm.pending", "first");
  assert.equal(two.getItem("farm.pending"), null);
  assert.equal(disk.getItem("farm.pending"), null);
});
