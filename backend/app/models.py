"""课程、状态及事件的数据模型；所有外部输入采用严格字段白名单。"""

from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]
TaskType = Literal["OBSERVE", "LISTEN_FIND", "OPTIONAL_SPEAK", "EXPLORE"]
State = Literal[
    "READY",
    "INTRODUCING",
    "AWAITING_GAME_ACTION",
    "HINTING",
    "VERIFIED",
    "OPTIONAL_SPEAK",
    "COMPLETE",
    "PAUSED",
    "EXITED",
]
GameAction = Literal[
    "PLAY_FEEDBACK",
    "SHOW_HINT",
    "HIGHLIGHT_ENTITY",
    "UNLOCK_GATE",
    "GRANT_COSMETIC",
    "SHOW_TITLE",
]
EventKind = Literal[
    "START",
    "CONTINUE",
    "HELP",
    "REPLAY",
    "SKIP",
    "PAUSE",
    "RESUME",
    "EXIT",
    "TIMEOUT",
    "OPERATIONAL_HELP",
    "OPERATION_READY",
    "VISUAL_READY",
    "LAYOUT_READY",
    "ENTITY_INTERACTED",
    "AUDIO_FINISHED",
    "AUDIO_FAILED",
    "SPEECH_RECOGNIZED",
    "SPEECH_UNAVAILABLE",
]
HINT_STEPS = ["REPEAT_AUDIO", "PLAY_ANIMAL_SOUND", "HIGHLIGHT_TARGET", "SHOW_ROUTE"]


def utc_now() -> datetime:
    """生成统一的服务端 UTC 时间，不依赖电脑时区。"""
    return datetime.now(UTC)


def new_id() -> str:
    """生成协议使用的匿名唯一标识。"""
    return str(uuid4())


class Model(BaseModel):
    """拒绝未知字段，防止原始命令等意外输入穿透协议。"""

    model_config = ConfigDict(extra="forbid")


class Reward(Model):
    """描述经课程审核的单个游戏动作。"""

    type: GameAction
    target_id: Identifier


class Task(Model):
    """描述一个教学步骤，避免将游戏完成等同于学习掌握。"""

    task_id: Identifier
    type: TaskType
    prompt_id: Identifier
    target: Literal["cow", "pig"] | None = None
    context: Identifier
    randomize_positions: bool = False
    visual_anchor_required: bool = False
    hint_steps: list[str] = Field(default_factory=lambda: HINT_STEPS.copy())
    success_actions: list[Reward] = Field(default_factory=list)
    story_goal: bool = False

    @model_validator(mode="after")
    def validate_teaching_rules(self) -> Self:
        """检查提示顺序、听力目标及独立辨认所需的随机布局。"""
        if self.hint_steps != HINT_STEPS:
            raise ValueError(f"{self.task_id}: hint_steps 必须按 H1–H4 排列")
        if self.type == "LISTEN_FIND" and (not self.target or not self.randomize_positions):
            raise ValueError(f"{self.task_id}: 听力任务需要目标和随机布局")
        if self.visual_anchor_required and not self.target:
            raise ValueError(f"{self.task_id}: 视觉锚点需要目标")
        if self.story_goal and self.type != "LISTEN_FIND":
            raise ValueError(f"{self.task_id}: 剧情目标必须由游戏辨认任务确认")
        return self


class Lesson(Model):
    """保存可验证的完整课次，阈值仅为可配置实验参数。"""

    lesson_id: Identifier
    version: str
    language_level: Literal["BEGINNER_ZERO"] = "BEGINNER_ZERO"
    speaking_policy: Literal["OPTIONAL"] = "OPTIONAL"
    target_vocabulary: list[Literal["cow", "pig"]]
    known_patterns: list[str]
    independent_threshold: int = Field(default=3, ge=2)
    tasks: list[Task] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_tasks(self) -> Self:
        """防止任务覆盖和课程外词汇混入首课。"""
        identifiers = [task.task_id for task in self.tasks]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("task_id 必须唯一")
        if set(self.target_vocabulary) != {"cow", "pig"}:
            raise ValueError("首课目标词必须是 cow 和 pig")
        return self


class WordProgress(Model):
    """记录学习证据，不从呈现次数推断掌握。"""

    status: Literal["UNSEEN", "INTRODUCED", "PRACTICING", "UNDERSTANDS", "RETENTION_CHECK"] = (
        "UNSEEN"
    )
    exposure_count: int = 0
    independent_correct: int = 0
    assisted_correct: int = 0
    unconfirmed_correct: int = 0
    transfer_correct: int = 0
    wrong_choices: int = 0
    independent_contexts: list[str] = Field(default_factory=list)
    stable_mastery: bool = False


class Session(Model):
    """保存可恢复的课次快照，课程副本保证重启后使用同一版本。"""

    session_id: Identifier = Field(default_factory=new_id)
    player_id: Identifier
    lesson: Lesson
    state: State = "READY"
    resume_state: State | None = None
    resume_audio: bool = False
    task_index: int = 0
    hint_level: int = 0
    attempts: int = 0
    active_audio_id: str | None = None
    active_visual_id: str | None = None
    audio_finished: bool = False
    visual_ready: bool = False
    layout_ready: bool = False
    exposure_recorded: bool = False
    operation_blocked: bool = False
    operational_blocks: int = 0
    replay_requests: int = 0
    speaking_participations: int = 0
    voice_mode: Literal["PREGENERATED", "OFFLINE_FALLBACK"] = "PREGENERATED"
    video_game_task_complete: bool = False
    completed_tasks: list[str] = Field(default_factory=list)
    skipped_tasks: list[str] = Field(default_factory=list)
    sequences: dict[str, int] = Field(default_factory=dict)
    words: dict[str, WordProgress] = Field(default_factory=dict)
    updated_at: AwareDatetime = Field(default_factory=utc_now)

    @property
    def task(self) -> Task:
        """返回当前步骤；结束时保留最后一步以方便报告。"""
        return self.lesson.tasks[self.task_index]


class Event(Model):
    """统一内部事件结构；文本只参与即时判断，不进入数据库日志。"""

    event_id: Identifier
    session_id: Identifier
    player_id: Identifier
    task_id: Identifier
    kind: EventKind
    sequence: int = Field(ge=1)
    occurred_at: AwareDatetime | None = None
    entity_type: Literal["minecraft:cow", "minecraft:pig"] | None = None
    command_id: Identifier | None = None
    transcript: str | None = Field(default=None, max_length=500)
    provider: str | None = Field(default=None, max_length=50)


class CreateSession(Model):
    """创建匿名本地会话，event_id 支持客户端安全重试。"""

    event_id: Identifier
    player_id: Identifier = "local_player_01"
    lesson_id: Identifier = "farm_01"


class Ack(Model):
    """确认命令执行结果，失败命令保留供再次拉取。"""

    session_id: Identifier
    success: bool = True


class Command(Model):
    """描述指定接收方的可重试动作，接收方必须按 command_id 去重。"""

    command_id: Identifier = Field(default_factory=new_id)
    session_id: Identifier
    task_id: Identifier
    audience: Literal["game", "voice"]
    type: Literal[
        "PLAY_FEEDBACK",
        "SHOW_HINT",
        "HIGHLIGHT_ENTITY",
        "UNLOCK_GATE",
        "GRANT_COSMETIC",
        "SHOW_TITLE",
        "PLAY_AUDIO",
        "STOP_AUDIO",
    ]
    target_id: str | None = None
    audio_id: str | None = None
    hint_level: int = 0
    randomize_positions: bool = False
    caused_by_event_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_audience(self) -> Self:
        """隔离语音动作与游戏白名单，禁止跨通道执行。"""
        voice_action = self.type in {"PLAY_AUDIO", "STOP_AUDIO"}
        if voice_action != (self.audience == "voice"):
            raise ValueError("动作与接收方不匹配")
        return self
