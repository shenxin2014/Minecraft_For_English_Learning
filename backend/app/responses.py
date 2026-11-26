"""显式 HTTP 响应模型，保证导出的 OpenAPI 包含可用的数据契约。"""

from typing import Literal

from .models import Identifier, Model, State, Task, WordProgress


class SessionView(Model):
    """公开课次状态，包含客户端重连需要的任务及事件游标。"""

    session_id: Identifier
    player_id: Identifier
    lesson_id: Identifier
    lesson_version: str
    state: State
    current_task: Task
    hint_level: int
    voice_mode: Literal["PREGENERATED", "OFFLINE_FALLBACK"]
    sequences: dict[str, int]
    active_audio_id: str | None
    active_visual_id: str | None
    video_game_task_complete: bool
    task_index: int = 0
    total_tasks: int = 10
    audio_finished: bool = False
    visual_ready: bool = False
    layout_ready: bool = False
    operation_blocked: bool = False


class EventResponse(Model):
    """返回事件处理原因及处理时的会话状态，重复请求沿用原结果。"""

    result: str
    duplicate: bool
    session: SessionView


class ProgressResponse(Model):
    """描述探索性的学习观察结果，区分剧情、理解与口语参与。"""

    session_id: Identifier
    state: State
    video_game_task_complete: bool
    vocab_mastery: dict[str, WordProgress]
    completed_tasks: list[str]
    skipped_tasks: list[str]
    operational_blocks: int
    replay_requests: int
    speaking_participations: int
    note: str


class AckResponse(Model):
    """报告命令的传输状态，不表示教学任务是否正确完成。"""

    command_id: Identifier
    status: Literal["pending", "acked", "cancelled"]


class HealthResponse(Model):
    """报告默认离线适配模式；真实 BDS 状态由各绑定的探针和租约单独报告。"""

    status: Literal["ok"]
    mock_mode: Literal[True]
    game: Literal["mock"]
    speech: Literal["mock"]
