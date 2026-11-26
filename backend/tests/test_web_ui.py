"""M1 验收：本地资源、真实 WAV 格式、播放恢复和安全边界。"""

import json
import wave
from array import array
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.main import PROJECT_ROOT, create_app


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/js/app.js",
        "/js/audio.js",
        "/assets/styles.css",
        "/assets/layout.css",
        "/assets/cow.svg",
        "/assets/pig.svg",
        "/assets/farm.svg",
        "/assets/meadow.svg",
        "/assets/orchard.svg",
        "/assets/lily.svg",
    ],
)
def test_local_teaching_assets_are_served(client, path):
    """核心页面、动物和场景素材可由本地后端直接提供。"""
    response = client.get(path)
    assert response.status_code == 200
    assert len(response.content) > 100


def test_all_lesson_audio_is_real_pcm_and_not_silent(client):
    """每个课程提示都有实际 PCM 音频，检查长度、采样规格和非静音信号。"""
    manifest = client.get("/assets/audio/manifest.json").json()
    lesson = json.loads((PROJECT_ROOT / "lessons/lesson_farm_01.json").read_text("utf-8"))
    assert {task["prompt_id"] for task in lesson["tasks"]} <= manifest["clips"].keys()
    for clip in manifest["clips"]:
        response = client.get(f"/assets/audio/{clip}.wav")
        assert response.status_code == 200
        with wave.open(BytesIO(response.content)) as audio:
            assert audio.getnchannels() == 1
            assert audio.getsampwidth() == 2
            assert audio.getframerate() == 22050
            assert 0.5 < audio.getnframes() / audio.getframerate() < 8
            samples = array("h", audio.readframes(audio.getnframes()))
            assert max(abs(sample) for sample in samples) > 500


def test_audio_supports_browser_range_requests(client):
    """浏览器可以按字节读取本地 WAV，避免媒体加载兼容问题。"""
    response = client.get("/assets/audio/look_cow_en.wav", headers={"Range": "bytes=0-127"})
    assert response.status_code == 206
    assert len(response.content) == 128
    assert response.content.startswith(b"RIFF")


def test_static_page_does_not_bypass_api_token(tmp_path):
    """本机先显示口令入口，但页面可见不等于业务 API 已解锁。"""
    with TestClient(create_app(tmp_path / "secured.sqlite3", api_token="test-only")) as client:
        assert client.get("/").status_code == 200
        assert client.get("/assets/audio/welcome_en.wav").status_code == 200
        assert client.get("/health").status_code == 401
        assert client.post("/v1/sessions", json={"event_id": "test-create"}).status_code == 401


@pytest.mark.parametrize("control", ["HELP", "REPLAY"])
def test_interrupted_hint_or_replay_resumes_with_new_playback(driver, control):
    """暂停 H1 或重听中的音频后恢复，必须签发新播放标识且保留提示归因。"""
    driver.reach_task("find_cow")
    driver.send(control)
    old_audio = driver.state()["active_audio_id"]
    driver.send("PAUSE")
    driver.send("RESUME")
    state = driver.state()
    assert state["active_audio_id"] != old_audio
    assert state["active_audio_id"] is not None
    assert state["hint_level"] == 1
    assert not state["audio_finished"]
    assert driver.send("AUDIO_FINISHED", command_id=old_audio)["result"] == "ignored_audio"


def test_repeated_exit_does_not_destroy_resume_point(driver):
    """多次退出不能把恢复目标覆盖成 EXITED，导致下一次无法继续。"""
    driver.reach_task("find_cow")
    driver.send("EXIT")
    driver.send("EXIT")
    driver.send("RESUME")
    assert driver.state()["state"] == "AWAITING_GAME_ACTION"
    assert driver.state()["current_task"]["task_id"] == "find_cow"


def test_missing_audio_is_not_replaced_with_html(client):
    """音频路径错误明确返回 404，让播放器进入失败回退而非假装成功。"""
    assert client.get("/assets/audio/unknown.wav").status_code == 404
