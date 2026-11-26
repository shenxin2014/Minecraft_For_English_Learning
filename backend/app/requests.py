"""按通道收紧事件模型，使接口文档与运行时权限保持一致。"""

from typing import Literal, Self

from pydantic import AliasChoices, Field, model_validator

from .models import Event


class StartEvent(Event):
    """课程开始接口只接受 START 事件。"""

    kind: Literal["START"]


class ControlEvent(Event):
    """描述孩子或家长主动发出的课程控制意图。"""

    kind: Literal[
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
    ]


class GameEvent(Event):
    """限定游戏适配器输入，并兼容规格示例的 event_type 字段。"""

    kind: Literal["VISUAL_READY", "LAYOUT_READY", "ENTITY_INTERACTED"] = Field(
        validation_alias=AliasChoices("kind", "event_type"),
    )

    @model_validator(mode="after")
    def require_game_evidence(self) -> Self:
        """实体选择需要目标类型，视觉确认需要对应的命令标识。"""
        if self.kind == "ENTITY_INTERACTED" and self.entity_type is None:
            raise ValueError("实体交互必须包含 entity_type")
        if self.kind in {"VISUAL_READY", "LAYOUT_READY"} and self.command_id is None:
            raise ValueError("视觉确认必须包含 command_id")
        return self


class VoiceEvent(Event):
    """限定播放回执和可选口语输入，不能携带游戏选择事件。"""

    kind: Literal["AUDIO_FINISHED", "AUDIO_FAILED", "SPEECH_RECOGNIZED", "SPEECH_UNAVAILABLE"]

    @model_validator(mode="after")
    def require_audio_reference(self) -> Self:
        """播放成功或失败必须绑定当前播放命令。"""
        if self.kind in {"AUDIO_FINISHED", "AUDIO_FAILED"} and self.command_id is None:
            raise ValueError("音频回执必须包含 command_id")
        return self
