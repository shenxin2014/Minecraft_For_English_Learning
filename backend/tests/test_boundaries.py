"""补充真实故障边界：乱序、重放、事务回滚、隐私与动作确认。"""

import json
import sqlite3
from datetime import timedelta

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.game_adapter import MockGameAdapter
from app.main import PROJECT_ROOT, create_app
from app.models import Command, Lesson, new_id, utc_now
from app.storage import Store


def progress(client, driver):
    """读取当前会话的观察报告，简化各边界断言。"""
    return client.get(f"/v1/progress/{driver.session_id}").json()


def test_create_idempotency_and_conflict(client):
    """创建会话可重试，但事件 ID 不能承载不同请求。"""
    payload = {"event_id": new_id(), "player_id": "anonymous_01"}
    first = client.post("/v1/sessions", json=payload)
    assert client.post("/v1/sessions", json=payload).json() == first.json()
    payload["player_id"] = "anonymous_02"
    assert client.post("/v1/sessions", json=payload).status_code == 409


@pytest.mark.parametrize(
    "field,value",
    [
        ("hint_steps", ["SHOW_ROUTE"]),
        ("success_actions", [{"type": "RUN_COMMAND", "target_id": "danger"}]),
        ("randomize_positions", False),
    ],
)
def test_invalid_curriculum_rules(field, value):
    """提示顺序、动作白名单与随机布局约束在加载前生效。"""
    lesson = json.loads((PROJECT_ROOT / "lessons/lesson_farm_01.json").read_text("utf-8"))
    lesson["tasks"][3][field] = value
    with pytest.raises(ValidationError):
        Lesson.model_validate(lesson)


def test_duplicate_lesson_id_rejected(tmp_path):
    """多个文件不能静默覆盖同一个课程 ID。"""
    source = (PROJECT_ROOT / "lessons/lesson_farm_01.json").read_text("utf-8")
    (tmp_path / "lesson_a.json").write_text(source, "utf-8")
    (tmp_path / "lesson_b.json").write_text(source, "utf-8")
    with pytest.raises(ValueError, match="重复 lesson_id"):
        create_app(tmp_path / "test.sqlite3", lessons_dir=tmp_path)


def test_wrong_then_correct_not_independent(client, driver):
    """先点错再猜对不能冒充 H0 首次独立正确。"""
    driver.reach_task("find_cow")
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:pig")
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")
    word = progress(client, driver)["vocab_mastery"]["cow"]
    assert word["wrong_choices"] == 1
    assert word["unconfirmed_correct"] == 1
    assert word["independent_correct"] == 0


def test_replay_marks_h1_and_old_receipt_ignored(client, driver):
    """主动重听属于支持；旧播放回执不会对应到新播放。"""
    driver.reach_task("find_cow")
    old_audio = driver.state()["active_audio_id"]
    driver.send("REPLAY")
    assert driver.send("AUDIO_FINISHED", command_id=old_audio)["result"] == "ignored_audio"
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")
    report = progress(client, driver)
    assert report["replay_requests"] == 1
    assert report["vocab_mastery"]["cow"]["assisted_correct"] == 1


def test_missing_layout_evidence_not_independent(client, driver):
    """仅确认目标可见不能替代位置随机化确认。"""
    driver.reach_task("introduce_pig")
    driver.send("CONTINUE")
    state = driver.state()
    driver.send("VISUAL_READY", command_id=state["active_visual_id"])
    driver.send("AUDIO_FINISHED", command_id=state["active_audio_id"])
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")
    assert progress(client, driver)["vocab_mastery"]["cow"]["unconfirmed_correct"] == 1


def test_audio_requires_visual_and_counts_once(client, driver):
    """音频完成后等待视觉证据，两类回执重发也只计一次呈现。"""
    driver.reach_task("welcome")
    driver.send("CONTINUE")
    state = driver.state()
    driver.send("AUDIO_FINISHED", command_id=state["active_audio_id"])
    assert progress(client, driver)["vocab_mastery"]["cow"]["exposure_count"] == 0
    assert driver.state()["state"] == "INTRODUCING"
    driver.send("VISUAL_READY", command_id=state["active_visual_id"])
    driver.send("AUDIO_FINISHED", command_id=state["active_audio_id"])
    driver.send("VISUAL_READY", command_id=state["active_visual_id"])
    assert progress(client, driver)["vocab_mastery"]["cow"]["exposure_count"] == 1


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"player_id": "different_player"}, "ignored_player"),
        ({"sequence": 1}, "ignored_sequence"),
        ({"occurred_at": (utc_now() + timedelta(days=1)).isoformat()}, "ignored_future_time"),
    ],
)
def test_invalid_game_event_does_not_advance(driver, override, reason):
    """错玩家、乱序或未来时间事件不能改变当前任务。"""
    driver.reach_task("find_cow")
    response = driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow", **override)
    assert response["result"] == reason
    assert driver.state()["current_task"]["task_id"] == "find_cow"


def test_voice_cannot_impersonate_game_or_award(client, driver):
    """语音通道拒绝游戏事件，普通转录也不能完成听力任务。"""
    driver.reach_task("find_cow")
    payload = driver.event_payload("ENTITY_INTERACTED", entity_type="minecraft:cow")
    assert client.post("/v1/voice/events", json=payload).status_code == 422
    assert driver.send("SPEECH_RECOGNIZED", transcript="cow")["result"] == "ignored_state"
    assert driver.state()["current_task"]["task_id"] == "find_cow"


def test_transcript_not_persisted(client, driver, tmp_path):
    """自愿口语仅保存参与次数，数据库不保存完整转录。"""
    driver.reach_task("optional_say_cow")
    private_text = "private_example_do_not_store_91823"
    driver.send("SPEECH_RECOGNIZED", transcript=private_text, provider="mock")
    assert progress(client, driver)["speaking_participations"] == 1
    with sqlite3.connect(tmp_path / "progress.sqlite3") as connection:
        assert private_text not in "\n".join(connection.iterdump())


def test_timeout_checks_operation_before_hint(driver):
    """超时先检查操作困难，不直接提高英语提示级别。"""
    driver.reach_task("find_cow")
    driver.send("TIMEOUT")
    assert driver.state()["hint_level"] == 0
    assert driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")["result"] == (
        "ignored_operational_block"
    )


def test_story_and_mastery_separate_with_h4(client, driver):
    """教学演示后完成剧情仍不意味着词汇稳定掌握。"""
    driver.reach_task("rescue_cow")
    for _ in range(4):
        driver.send("HELP")
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")
    report = progress(client, driver)
    assert report["video_game_task_complete"]
    assert report["vocab_mastery"]["cow"]["assisted_correct"] == 1
    assert not report["vocab_mastery"]["cow"]["stable_mastery"]


def test_skip_story_does_not_grant_reward(client, driver):
    """跳过找回牛可继续课程，但不伪造剧情完成与奖励。"""
    driver.reach_task("rescue_cow")
    driver.send("SKIP")
    assert not progress(client, driver)["video_game_task_complete"]
    commands = client.get("/v1/game/actions", params={"session_id": driver.session_id}).json()
    assert not any(command["type"] == "GRANT_COSMETIC" for command in commands)


def test_failed_transaction_can_retry_same_event(client, driver, monkeypatch):
    """动作入队失败必须回滚状态和去重收据，之后原事件可重试。"""
    payload = driver.event_payload("START")
    path = f"/v1/sessions/{driver.session_id}/start"

    def fail_to_save(self, commands):
        """注入数据库提交前故障。"""
        raise RuntimeError("simulated failure")

    with monkeypatch.context() as patch:
        patch.setattr(Store, "add_commands", fail_to_save)
        with pytest.raises(RuntimeError, match="simulated failure"):
            client.post(path, json=payload)
    assert driver.state()["state"] == "READY"
    assert client.post(path, json=payload).json()["result"] == "accepted"


def test_command_retry_ack_and_adapter_restart(client, driver, tmp_path):
    """执行后 ACK 丢失可以重投，适配器重建后仍不会重复产生效果。"""
    driver.reach_task("find_cow")
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")
    commands = client.get("/v1/game/actions", params={"session_id": driver.session_id}).json()
    reward = Command.model_validate(
        next(item for item in commands if item["type"] == "UNLOCK_GATE")
    )
    assert driver.game.execute(reward)
    assert not MockGameAdapter(tmp_path / "world.sqlite3").execute(reward)
    path = f"/v1/game/actions/{reward.command_id}/ack"
    body = {"session_id": driver.session_id, "success": False}
    assert client.post(path, json=body).json()["status"] == "pending"
    body["success"] = True
    assert client.post(path, json=body).json()["status"] == "acked"
    assert client.post(path, json=body).json()["status"] == "acked"
    assert client.post(path.replace("/game/", "/voice/"), json=body).status_code == 404


def test_http_auth_and_remote_default(tmp_path):
    """默认拒绝远端访问；启用令牌时所有请求都要认证。"""
    with TestClient(
        create_app(tmp_path / "remote.sqlite3", api_token=""), client=("192.0.2.10", 1234)
    ) as remote:
        assert remote.get("/health").status_code == 403
    with TestClient(create_app(tmp_path / "auth.sqlite3", api_token="test-token")) as secured:
        assert secured.get("/health").status_code == 401
        assert secured.get("/health", headers={"X-API-Token": "test-token"}).status_code == 200


def test_raw_commands_and_cross_session_controls_rejected(client, driver):
    """未知字段和不同会话的控制请求必须在 HTTP 边界失败。"""
    payload = driver.event_payload("START")
    payload["raw_command"] = "danger"
    path = f"/v1/sessions/{driver.session_id}/start"
    assert client.post(path, json=payload).status_code == 422
    payload.pop("raw_command")
    payload["session_id"] = "different_session"
    assert client.post(path, json=payload).status_code == 422


def test_game_event_type_alias(client, driver):
    """保留规格示例的 event_type 写法，并沿用相同幂等语义。"""
    driver.reach_task("find_cow")
    payload = driver.event_payload("ENTITY_INTERACTED", entity_type="minecraft:cow")
    payload["event_type"] = payload.pop("kind")
    assert client.post("/v1/game/events", json=payload).json()["result"] == "accepted"
    payload["kind"] = payload.pop("event_type")
    assert client.post("/v1/game/events", json=payload).json()["duplicate"]


def test_exported_contract_matches_application(client):
    """防止提交的 OpenAPI 与实际请求响应模型发生漂移。"""
    saved = yaml.safe_load((PROJECT_ROOT / "contracts/openapi.yaml").read_text("utf-8"))
    assert saved == client.get("/openapi.json").json()
