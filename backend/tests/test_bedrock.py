"""检验 BDS 来源、绑定、重试和真实游戏证据之间的边界。"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

BDS_HEADERS = {"X-BDS-Token": "test-bds-token"}


@pytest.fixture
def bds_client(tmp_path):
    """创建明确启用测试网络来源的应用，与生产 loopback 配置分开。"""
    app = create_app(
        tmp_path / "bds.sqlite3", api_token="", bds_token="test-bds-token", bds_hosts={"testclient"}
    )
    with TestClient(app) as client:
        yield client


def bind(client, bridge_id="world_1", creation_id="create_1"):
    """创建新的匿名诊断课次并交给指定世界。"""
    session = client.post("/v1/sessions", json={"event_id": creation_id}).json()
    response = client.post(
        "/v1/bds/bindings",
        json={
            "bridge_id": bridge_id,
            "session_id": session["session_id"],
        },
    )
    assert response.status_code == 200
    client.post(
        "/v1/bds/probe",
        headers=BDS_HEADERS,
        json={
            "bridge_id": bridge_id,
            "pack_version": "0.3.0",
            "runtime_profile": "unit-test",
        },
    ).raise_for_status()
    return session


def envelope(session, event_id="interaction_1", sequence=1):
    """构建最小实体交互，不伪造视觉、布局或语音回执。"""
    return {
        "bridge_id": "world_1",
        "event": {
            "event_id": event_id,
            "session_id": session["session_id"],
            "player_id": session["player_id"],
            "task_id": session["current_task"]["task_id"],
            "kind": "ENTITY_INTERACTED",
            "sequence": sequence,
            "entity_type": "minecraft:cow",
            "provider": "bedrock.playerInteractWithEntityAfterEvent",
        },
    }


def test_probe_does_not_claim_gameplay_or_change_lesson(bds_client):
    """网络通路通过后仍不能声称实机交互或学习结果通过。"""
    session = bind(bds_client)
    response = bds_client.post(
        "/v1/bds/probe",
        headers=BDS_HEADERS,
        json={
            "bridge_id": "world_1",
            "pack_version": "0.3.0",
            "runtime_profile": "bds-1.26.66-candidate",
        },
    )
    assert response.status_code == 200
    assert response.json()["http_received"] is True
    assert response.json()["gameplay_verified"] is False
    assert response.json()["interaction_receipts"] == 0
    assert bds_client.get(f"/v1/sessions/{session['session_id']}").json() == session


def test_duplicate_receipts_survive_restart(bds_client, tmp_path):
    """提交成功但响应丢失后重发，同一收据和序号仅保存一次。"""
    session = bind(bds_client)
    body = envelope(session)
    first = bds_client.post("/v1/bds/events", headers=BDS_HEADERS, json=body)
    assert first.status_code == 200
    assert first.json()["result"] == "ignored_not_started"
    app = create_app(
        tmp_path / "bds.sqlite3", api_token="", bds_token="test-bds-token", bds_hosts={"testclient"}
    )
    with TestClient(app) as restored:
        repeat = restored.post("/v1/bds/events", headers=BDS_HEADERS, json=body).json()
        assert repeat["duplicate"] is True
        assert repeat["session"] == first.json()["session"]
        assert restored.get("/v1/bds/status/world_1").json()["interaction_receipts"] == 1
        body["event"]["entity_type"] = "minecraft:pig"
        assert restored.post("/v1/bds/events", headers=BDS_HEADERS, json=body).status_code == 409


def test_bound_session_rejects_mock_and_other_bridge(bds_client):
    """已绑定课次不能被普通游戏端或另一个世界推进。"""
    body = envelope(bind(bds_client))
    assert bds_client.post("/v1/game/events", json=body["event"]).status_code == 409
    body["bridge_id"] = "other_world"
    assert bds_client.post("/v1/bds/events", headers=BDS_HEADERS, json=body).status_code == 409


@pytest.mark.parametrize(
    "field,value,result",
    [
        ("player_id", "other_player", "ignored_player"),
        ("task_id", "review_cow", "ignored_task"),
    ],
)
def test_wrong_context_is_ignored_without_sequence_consumption(bds_client, field, value, result):
    """旧任务和错误玩家事件留收据但不推进游标。"""
    body = envelope(bind(bds_client))
    body["event"][field] = value
    reply = bds_client.post("/v1/bds/events", headers=BDS_HEADERS, json=body).json()
    assert reply["result"] == result
    assert reply["session"]["sequences"] == {}


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "VISUAL_READY", "command_id": "made_up"},
        {"entity_type": "minecraft:sheep"},
        {"transcript": "private text"},
        {"provider": "mock"},
        {"player_name": "real name"},
    ],
)
def test_bridge_contract_rejects_unrelated_fields(bds_client, changes):
    """BDS 只能提交白名单成功交互，不能注入学习证据或身份信息。"""
    body = envelope(bind(bds_client))
    body["event"].update(changes)
    assert bds_client.post("/v1/bds/events", headers=BDS_HEADERS, json=body).status_code == 422


def test_binding_is_immutable_and_idempotent(bds_client):
    """重试原绑定成功，另一个课次不能覆盖世界的旧绑定。"""
    session = bind(bds_client)
    original = {"bridge_id": "world_1", "session_id": session["session_id"]}
    assert bds_client.post("/v1/bds/bindings", json=original).status_code == 200
    other = bds_client.post("/v1/sessions", json={"event_id": "create_2"}).json()
    original["session_id"] = other["session_id"]
    assert bds_client.post("/v1/bds/bindings", json=original).status_code == 409


def test_started_mock_session_cannot_be_bound(bds_client):
    """已使用离线场景的课次不能通过改绑混合两种来源的历史证据。"""
    session = bds_client.post("/v1/sessions", json={"event_id": "create_1"}).json()
    event = envelope(session)["event"]
    event.update(kind="START", provider=None, entity_type=None)
    bds_client.post(f"/v1/sessions/{session['session_id']}/start", json=event).raise_for_status()
    response = bds_client.post(
        "/v1/bds/bindings",
        json={
            "bridge_id": "world_1",
            "session_id": session["session_id"],
        },
    )
    assert response.status_code == 409


def test_bridge_needs_distinct_token_and_actual_source(tmp_path):
    """API 凭据不能代替 BDS 凭据，伪造转发头不能绕过 IP 白名单。"""
    app = create_app(tmp_path / "auth.sqlite3", api_token="operator", bds_token="test-bds-token")
    with TestClient(app) as client:
        assert (
            client.get(
                "/v1/bds/context/world_1",
                headers={
                    **BDS_HEADERS,
                    "X-Forwarded-For": "127.0.0.1",
                },
            ).status_code
            == 403
        )
        app.state.bds_hosts = {"testclient"}
        assert (
            client.get(
                "/v1/bds/context/world_1",
                headers={
                    "X-API-Token": "operator",
                },
            ).status_code
            == 401
        )
        assert client.get("/v1/sessions/missing", headers=BDS_HEADERS).status_code == 401
        app.state.bds_token = ""
        assert client.get("/v1/bds/context/world_1", headers=BDS_HEADERS).status_code == 503


def test_api_requires_probe_before_events(bds_client):
    """即使跳过适配器直接调用接口，服务端仍要求网络探针收据。"""
    session = bind(bds_client)
    with bds_client.app.state.service.database.transaction() as store:
        store.connection.execute("DELETE FROM bedrock_probes")
    response = bds_client.post("/v1/bds/events", headers=BDS_HEADERS, json=envelope(session))
    assert response.status_code == 409
    assert bds_client.get(f"/v1/sessions/{session['session_id']}").json()["sequences"] == {}
