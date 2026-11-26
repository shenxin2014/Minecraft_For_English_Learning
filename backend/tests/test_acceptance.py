"""规格 T01–T12 的离线验收，经过真实 API 和 SQLite 事务。"""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import PROJECT_ROOT, create_app
from app.mock_client import MockLessonClient
from app.models import Command, Lesson, new_id
from app.speech_provider import MockSpeechProvider


def test_t01_duplicate_task_rejected():
    """重复任务 ID 必须在配置加载阶段被拒绝。"""
    payload = json.loads((PROJECT_ROOT / "lessons/lesson_farm_01.json").read_text("utf-8"))
    payload["tasks"].append(payload["tasks"][0])
    with pytest.raises(ValidationError, match="task_id 必须唯一"):
        Lesson.model_validate(payload)


def test_t02_concurrent_duplicates_reward_once(client, driver):
    """同一游戏事件并发重发三次，只增加一次理解记录和一次开门动作。"""
    driver.reach_task("find_cow")
    payload = driver.event_payload("ENTITY_INTERACTED", entity_type="minecraft:cow")
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda _: client.post("/v1/game/events", json=payload), range(3)))
    assert all(response.status_code == 200 for response in responses)
    assert sum(not response.json()["duplicate"] for response in responses) == 1
    progress = client.get(f"/v1/progress/{driver.session_id}").json()
    assert progress["vocab_mastery"]["cow"]["independent_correct"] == 1
    commands = client.get("/v1/game/actions", params={"session_id": driver.session_id}).json()
    assert len([command for command in commands if command["type"] == "UNLOCK_GATE"]) == 1


def test_t03_future_task_event_ignored(driver):
    """任务之外的正确动物点击不能推进课程。"""
    driver.reach_task("find_cow")
    response = driver.send("ENTITY_INTERACTED", task_id="rescue_cow", entity_type="minecraft:cow")
    assert response["result"] == "ignored_task"
    assert driver.state()["current_task"]["task_id"] == "find_cow"


def test_t04_h0_first_randomized_choice_independent(client, driver):
    """H0、布局确认、首次选择同时满足时才算独立理解。"""
    driver.reach_task("find_cow")
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")
    word = client.get(f"/v1/progress/{driver.session_id}").json()["vocab_mastery"]["cow"]
    assert word["independent_correct"] == 1
    assert word["assisted_correct"] == 0
    assert word["status"] == "PRACTICING"
    assert not word["stable_mastery"]


def test_t05_h3_choice_assisted(client, driver):
    """高亮后成功只能计为有提示完成。"""
    driver.reach_task("find_cow")
    for _ in range(3):
        driver.send("HELP")
    assert driver.state()["hint_level"] == 3
    driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")
    word = client.get(f"/v1/progress/{driver.session_id}").json()["vocab_mastery"]["cow"]
    assert word["assisted_correct"] == 1
    assert word["independent_correct"] == 0


def test_t06_operational_block_not_language_error(client, driver):
    """卡路和操作帮助不计英语失误，问题解决后允许继续。"""
    driver.reach_task("find_cow")
    driver.send("OPERATIONAL_HELP")
    response = driver.send("ENTITY_INTERACTED", entity_type="minecraft:pig")
    assert response["result"] == "ignored_operational_block"
    report = client.get(f"/v1/progress/{driver.session_id}").json()
    assert report["operational_blocks"] == 1
    assert report["vocab_mastery"]["cow"]["wrong_choices"] == 0
    assert driver.state()["hint_level"] == 0
    driver.send("OPERATION_READY")
    assert driver.send("ENTITY_INTERACTED", entity_type="minecraft:cow")["result"] == "accepted"


def test_t07_speech_outage_still_completes(driver):
    """云端不可用及所有播放失败时，仍可沿有提示非口语路径结束。"""
    provider = MockSpeechProvider(available=False)
    with pytest.raises(ConnectionError):
        provider.recognize("cow")
    driver.send("START")
    driver.send("SPEECH_UNAVAILABLE", provider="mock")
    report = driver.finish(audio_fails=True)
    assert report["state"] == "COMPLETE"
    assert report["speaking_participations"] == 0
    assert report["vocab_mastery"]["cow"]["exposure_count"] == 0
    assert driver.state()["voice_mode"] == "OFFLINE_FALLBACK"


def test_t08_optional_speech_skip(driver):
    """跳过口语不会卡关，剧情结果不受影响。"""
    driver.reach_task("optional_say_cow")
    assert driver.state()["state"] == "OPTIONAL_SPEAK"
    driver.send("SKIP")
    assert driver.state()["current_task"]["task_id"] == "free_explore"
    report = driver.finish()
    assert report["video_game_task_complete"]
    assert report["speaking_participations"] == 0


def test_t09_pause_blocks_audio_and_late_receipts(client, driver):
    """暂停取消未播放音频；旧回执与重听请求都不能继续课程。"""
    driver.send("START")
    audio_id = driver.state()["active_audio_id"]
    driver.send("PAUSE")
    assert driver.send("AUDIO_FINISHED", command_id=audio_id)["result"] == "ignored_inactive"
    assert driver.send("REPLAY")["result"] == "ignored_inactive"
    commands = client.get("/v1/voice/actions", params={"session_id": driver.session_id}).json()
    assert all(command["type"] == "STOP_AUDIO" for command in commands)
    driver.send("RESUME")
    assert driver.state()["active_audio_id"] != audio_id
    assert driver.finish()["state"] == "COMPLETE"


def test_t10_exit_and_new_app_resume(client, driver, tmp_path):
    """重建应用实例后保留已确认进度，重发旧点击不重复奖励。"""
    driver.reach_task("find_cow")
    payload = driver.event_payload("ENTITY_INTERACTED", entity_type="minecraft:cow")
    client.post("/v1/game/events", json=payload).raise_for_status()
    driver.send("EXIT")
    with TestClient(create_app(tmp_path / "progress.sqlite3", api_token="")) as restarted:
        restored = MockLessonClient(restarted, tmp_path / "world.sqlite3", driver.session_id)
        assert restored.state()["current_task"]["task_id"] == "find_pig"
        assert restarted.post("/v1/game/events", json=payload).json()["duplicate"]
        restored.send("RESUME")
        assert restored.finish()["state"] == "COMPLETE"


def test_t11_mock_full_lesson_and_transfer(driver):
    """无需游戏和麦克风，完整运行首课且出现跨场景理解证据。"""
    report = driver.finish()
    assert report["state"] == "COMPLETE"
    assert report["video_game_task_complete"]
    assert report["vocab_mastery"]["cow"]["transfer_correct"] == 2
    assert report["vocab_mastery"]["cow"]["status"] == "UNDERSTANDS"
    assert not report["vocab_mastery"]["cow"]["stable_mastery"]
    assert len(report["completed_tasks"]) == 9


def test_t12_dangerous_action_rejected(driver):
    """即使绕过上游模型构造，适配器边界也重新拒绝原始命令。"""
    unsafe = Command.model_construct(
        command_id=new_id(),
        session_id=driver.session_id,
        task_id="find_cow",
        audience="game",
        type="RUN_COMMAND",
        target_id="kill @e",
    )
    with pytest.raises(ValidationError):
        driver.game.execute(unsafe)
