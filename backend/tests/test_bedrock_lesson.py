"""模拟游戏和伴随页走真实 HTTP 契约；不把测试替身称为 BDS 实机。"""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import utc_now

HEADERS = {"X-BDS-Token": "lesson-token"}


class LessonDriver:
    """通过 M3 公共接口驱动课程，测试中显式模拟视觉与媒体结果。"""

    def __init__(self, client):
        """创建独立匿名绑定并完成模拟网络探针。"""
        self.client = client
        created = client.post("/v1/sessions", json={"event_id": str(uuid4())}).json()
        self.session_id = created["session_id"]
        client.post(
            "/v1/bds/bindings",
            json={
                "bridge_id": "lesson_world",
                "session_id": self.session_id,
            },
        ).raise_for_status()
        client.post(
            "/v1/bds/probe",
            headers=HEADERS,
            json={
                "bridge_id": "lesson_world",
                "pack_version": "0.4.0",
                "runtime_profile": "unit-test-m3",
            },
        ).raise_for_status()

    def state(self):
        """始终获取服务端权威状态，避免用历史响应假装当前状态。"""
        return self.client.get(f"/v1/sessions/{self.session_id}").json()

    def event(self, kind, source="game", **fields):
        """构造该来源的下一个事件，所有测试共用原有序号语义。"""
        state = self.state()
        return {
            "event_id": str(uuid4()),
            "session_id": self.session_id,
            "player_id": state["player_id"],
            "task_id": state["current_task"]["task_id"],
            "kind": kind,
            "sequence": state["sequences"].get(source, 0) + 1,
            **fields,
        }

    def game(self, kind, **fields):
        """通过受限 BDS 路由提交意图或视觉证据。"""
        response = self.client.post(
            "/v1/bds/lesson/events",
            headers=HEADERS,
            json={
                "bridge_id": "lesson_world",
                "event": self.event(kind, provider="bedrock.m3", **fields),
            },
        )
        response.raise_for_status()
        return response.json()

    def presence(self, visible=True):
        """显式模拟视觉租约；生产环境必须由游戏可见性检查产生。"""
        state = self.state()
        response = self.client.post(
            "/v1/bds/lesson/presence",
            headers=HEADERS,
            json={
                "bridge_id": "lesson_world",
                "task_id": state["current_task"]["task_id"],
                "visual_id": state["active_visual_id"],
                "visible": visible,
            },
        )
        response.raise_for_status()
        return response.json()["epoch"]

    def introduce(self):
        """模拟一次实际视觉完成和媒体结束，推动介绍进入等待状态。"""
        state = self.state()
        epoch = self.presence()
        if state["active_visual_id"] and not state["visual_ready"]:
            kind = (
                "LAYOUT_READY" if state["current_task"]["randomize_positions"] else "VISUAL_READY"
            )
            self.game(kind, command_id=state["active_visual_id"])
        audio = self.event("AUDIO_FINISHED", "voice", command_id=state["active_audio_id"])
        response = self.client.post(
            "/v1/bedrock/audio",
            json={
                "event": audio,
                "visibility_epoch": epoch,
            },
        )
        response.raise_for_status()
        assert response.json()["result"] == "accepted"

    def actions(self):
        """读取游戏端动作快照。"""
        response = self.client.get("/v1/bds/lesson/actions/lesson_world", headers=HEADERS)
        response.raise_for_status()
        return response.json()["commands"]


@pytest.fixture
def lesson(tmp_path):
    """为每个场景建立独立 BDS 测试凭据和数据库。"""
    app = create_app(
        tmp_path / "lesson.sqlite3",
        api_token="",
        bds_token="lesson-token",
        bds_hosts={"testclient"},
    )
    with TestClient(app) as client:
        yield LessonDriver(client)


def test_complete_course_uses_m3_routes_and_keeps_rewards_unique(lesson):
    """首课、H2 帮助、自愿口语跳过与复习均可通过 M3 契约串联。"""
    lesson.game("START")
    while lesson.state()["state"] != "COMPLETE":
        lesson.introduce()
        task = lesson.state()["current_task"]
        if task["task_id"] == "find_cow":
            lesson.game("HELP")
            lesson.introduce()
            lesson.game("HELP")
        if task["type"] == "LISTEN_FIND":
            lesson.game("ENTITY_INTERACTED", entity_type=f"minecraft:{task['target']}")
        elif task["type"] == "OPTIONAL_SPEAK":
            lesson.game("SKIP")
        else:
            lesson.game("CONTINUE")
    report = lesson.client.get(f"/v1/progress/{lesson.session_id}").json()
    assert report["video_game_task_complete"] is True
    assert report["speaking_participations"] == 0
    assert report["vocab_mastery"]["cow"]["assisted_correct"] == 1
    assert report["vocab_mastery"]["cow"]["stable_mastery"] is False
    commands = lesson.actions()
    assert sum(c["type"] == "UNLOCK_GATE" for c in commands) == 1
    assert sum(c["type"] == "GRANT_COSMETIC" for c in commands) == 1
    for command in commands:
        body = {"bridge_id": "lesson_world", "session_id": lesson.session_id}
        path = f"/v1/bds/lesson/ack/{command['command_id']}"
        assert lesson.client.post(path, headers=HEADERS, json=body).json()["status"] == "acked"
        assert lesson.client.post(path, headers=HEADERS, json=body).json()["status"] == "acked"
    assert lesson.actions() == []


def test_visibility_loss_invalidates_audio_even_after_visibility_returns(lesson):
    """播放途中断开视野后恢复，原播放代次不能增加有效呈现。"""
    lesson.game("START")
    epoch = lesson.presence()
    event = lesson.event("AUDIO_FINISHED", "voice", command_id=lesson.state()["active_audio_id"])
    lesson.presence(False)
    new_epoch = lesson.presence()
    assert new_epoch > epoch
    response = lesson.client.post(
        "/v1/bedrock/audio", json={"event": event, "visibility_epoch": epoch}
    )
    assert response.json()["result"] == "ignored_bds_visibility"
    assert lesson.state()["audio_finished"] is False
    # 同一事件 ID 不能通过更换代次将原来被忽略的事件升级为成功。
    assert (
        lesson.client.post(
            "/v1/bedrock/audio",
            json={
                "event": event,
                "visibility_epoch": new_epoch,
            },
        ).status_code
        == 409
    )


def test_expired_heartbeat_cannot_finish_audio(lesson):
    """没有明确收到 false，心跳到期也会禁止音频完成计分。"""
    lesson.game("START")
    epoch = lesson.presence()
    with lesson.client.app.state.service.database.transaction() as store:
        store.connection.execute(
            "UPDATE bedrock_presence SET received_at=?",
            ((utc_now() - timedelta(seconds=3)).isoformat(),),
        )
    event = lesson.event("AUDIO_FINISHED", "voice", command_id=lesson.state()["active_audio_id"])
    assert (
        lesson.client.post(
            "/v1/bedrock/audio",
            json={
                "event": event,
                "visibility_epoch": epoch,
            },
        ).json()["result"]
        == "ignored_bds_visibility"
    )
    assert lesson.presence() > epoch


def test_generic_voice_and_game_action_routes_cannot_bypass_binding(lesson):
    """M1 通道不能绕过真实游戏的可见性与动作归属限制。"""
    lesson.game("START")
    lesson.presence()
    audio = lesson.event("AUDIO_FINISHED", "voice", command_id=lesson.state()["active_audio_id"])
    assert (
        lesson.client.post("/v1/voice/events", json=audio).json()["result"]
        == "ignored_bds_visibility"
    )
    assert lesson.client.get(f"/v1/game/actions?session_id={lesson.session_id}").status_code == 409


def test_pause_suppresses_commands_and_old_audio(lesson):
    """暂停不投递游戏动作，恢复后重新签发播放标识。"""
    lesson.game("START")
    epoch = lesson.presence()
    old_audio = lesson.state()["active_audio_id"]
    lesson.game("PAUSE")
    assert lesson.actions() == []
    response = lesson.client.post(
        "/v1/bedrock/audio",
        json={
            "event": lesson.event("AUDIO_FINISHED", "voice", command_id=old_audio),
            "visibility_epoch": epoch,
        },
    )
    assert response.json()["result"].startswith("ignored_")
    lesson.game("RESUME")
    assert lesson.state()["active_audio_id"] != old_audio


def test_action_ack_and_metrics_require_correct_binding(lesson):
    """错误世界不能 ACK，空耗时样本不伪造达标结果。"""
    assert lesson.client.get("/v1/bedrock/metrics/lesson_world").json()["p95_ms"] is None
    lesson.game("START")
    lesson.introduce()
    lesson.game("CONTINUE")
    command = lesson.actions()[0]
    response = lesson.client.post(
        f"/v1/bds/lesson/ack/{command['command_id']}",
        headers=HEADERS,
        json={"bridge_id": "other_world", "session_id": lesson.session_id},
    )
    assert response.status_code == 409
    response = lesson.client.post(
        "/v1/bds/lesson/latency",
        headers=HEADERS,
        json={
            "bridge_id": "lesson_world",
            "command_id": command["command_id"],
            "elapsed_ms": 100,
        },
    )
    assert response.status_code == 409


@pytest.mark.parametrize("kind", ["AUDIO_FINISHED", "SPEECH_RECOGNIZED"])
def test_bds_lesson_endpoint_rejects_voice_events(lesson, kind):
    """游戏秘密不能提交媒体播放或麦克风识别结果。"""
    response = lesson.client.post(
        "/v1/bds/lesson/events",
        headers=HEADERS,
        json={
            "bridge_id": "lesson_world",
            "event": lesson.event(kind, provider="bedrock.m3"),
        },
    )
    assert response.status_code == 422


def test_feedback_latency_is_deduplicated_and_p95_uses_nearest_rank(lesson):
    """只统计反馈命令；重复上报不会改变样本数或覆盖第一次耗时。"""
    lesson.game("START")
    for _ in range(3):
        lesson.introduce()
        lesson.game("CONTINUE")
    lesson.introduce()
    lesson.game("ENTITY_INTERACTED", entity_type="minecraft:pig")
    feedback = next(command for command in lesson.actions() if command["type"] == "PLAY_FEEDBACK")
    lesson.client.post(
        f"/v1/bds/lesson/ack/{feedback['command_id']}",
        headers=HEADERS,
        json={
            "bridge_id": "lesson_world",
            "session_id": lesson.session_id,
        },
    ).raise_for_status()
    sample = {"bridge_id": "lesson_world", "command_id": feedback["command_id"], "elapsed_ms": 420}
    lesson.client.post("/v1/bds/lesson/latency", headers=HEADERS, json=sample).raise_for_status()
    sample["elapsed_ms"] = 100
    lesson.client.post("/v1/bds/lesson/latency", headers=HEADERS, json=sample).raise_for_status()
    metrics = lesson.client.get("/v1/bedrock/metrics/lesson_world").json()
    assert metrics["samples"] == 1
    assert metrics["p95_ms"] == 420
    assert metrics["runtime_verified"] is False
