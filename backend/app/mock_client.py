"""通过公开 HTTP 接口驱动模拟课程，供演示和端到端测试复用。"""

from pathlib import Path
from typing import Any

from .game_adapter import MockGameAdapter
from .models import Command, new_id

GAME_EVENTS = {"VISUAL_READY", "LAYOUT_READY", "ENTITY_INTERACTED"}
VOICE_EVENTS = {"AUDIO_FINISHED", "AUDIO_FAILED", "SPEECH_RECOGNIZED", "SPEECH_UNAVAILABLE"}


class MockLessonClient:
    """模拟孩子操作与设备回执；所有状态变化仍必须经过后端 API。"""

    def __init__(self, http_client: Any, world_path: Path, session_id: str | None = None) -> None:
        """绑定 HTTP 客户端和模拟世界，可恢复指定的已有会话。"""
        self.http = http_client
        self.game = MockGameAdapter(world_path)
        if session_id:
            self.session_id = session_id
        else:
            response = self.http.post("/v1/sessions", json={"event_id": new_id()})
            response.raise_for_status()
            self.session_id = response.json()["session_id"]

    def state(self) -> dict:
        """读取最新状态，避免在客户端缓存教学判断。"""
        response = self.http.get(f"/v1/sessions/{self.session_id}")
        response.raise_for_status()
        return response.json()

    def event_payload(self, kind: str, **fields: Any) -> dict:
        """根据服务端游标生成当前通道的下一条模拟事件。"""
        state = self.state()
        channel = self.channel(kind)
        return {
            "event_id": new_id(),
            "session_id": self.session_id,
            "player_id": state["player_id"],
            "task_id": state["current_task"]["task_id"],
            "kind": kind,
            "sequence": state["sequences"].get(channel, 0) + 1,
            **fields,
        }

    def channel(self, kind: str) -> str:
        """选择事件的可信来源通道。"""
        if kind in GAME_EVENTS:
            return "game"
        if kind in VOICE_EVENTS:
            return "voice"
        return "control"

    def send(self, kind: str, **fields: Any) -> dict:
        """发送一个模拟事件并暴露后端处理结果。"""
        payload = self.event_payload(kind, **fields)
        channel = self.channel(kind)
        path = f"/v1/{channel}/events"
        if channel == "control":
            suffix = "start" if kind == "START" else "control"
            path = f"/v1/sessions/{self.session_id}/{suffix}"
        response = self.http.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def pump_commands(self, *, audio_fails: bool = False) -> None:
        """模拟执行动作并回传视觉或播放结果，不播放真实音频。"""
        for audience in ("game", "voice"):
            response = self.http.get(
                f"/v1/{audience}/actions", params={"session_id": self.session_id}
            )
            response.raise_for_status()
            for raw in response.json():
                self.execute_command(Command.model_validate(raw), audio_fails=audio_fails)

    def execute_command(self, command: Command, *, audio_fails: bool) -> None:
        """保持执行、确认、结果回执的明确顺序，支持服务端重复投递。"""
        if command.audience == "game":
            self.game.execute(command)
        response = self.http.post(
            f"/v1/{command.audience}/actions/{command.command_id}/ack",
            json={"session_id": self.session_id},
        )
        response.raise_for_status()
        if command.command_id == self.state()["active_visual_id"]:
            kind = "LAYOUT_READY" if command.randomize_positions else "VISUAL_READY"
            self.send(kind, command_id=command.command_id)
        if command.type == "PLAY_AUDIO":
            kind = "AUDIO_FAILED" if audio_fails else "AUDIO_FINISHED"
            self.send(kind, command_id=command.command_id)

    def advance(self, *, audio_fails: bool = False) -> None:
        """执行当前任务的最简非口语路径。"""
        self.pump_commands(audio_fails=audio_fails)
        state = self.state()
        task = state["current_task"]
        if task["type"] == "LISTEN_FIND":
            self.send("ENTITY_INTERACTED", entity_type=f"minecraft:{task['target']}")
        elif task["type"] == "OPTIONAL_SPEAK":
            self.send("SKIP")
        else:
            self.send("CONTINUE")

    def reach_task(self, task_id: str) -> None:
        """完成前置步骤，供验收场景定位到指定任务。"""
        if self.state()["state"] == "READY":
            self.send("START")
        for _ in range(30):
            if self.state()["current_task"]["task_id"] == task_id:
                self.pump_commands()
                return
            self.advance()
        raise RuntimeError(f"未能到达任务 {task_id}")

    def finish(self, *, audio_fails: bool = False) -> dict:
        """在有界循环中完成首课，异常时明确报错而非无限等待。"""
        if self.state()["state"] == "READY":
            self.send("START")
        for _ in range(30):
            if self.state()["state"] == "COMPLETE":
                self.pump_commands(audio_fails=audio_fails)
                response = self.http.get(f"/v1/progress/{self.session_id}")
                response.raise_for_status()
                return response.json()
            self.advance(audio_fails=audio_fails)
        raise RuntimeError("课程未在预期步骤内结束")
