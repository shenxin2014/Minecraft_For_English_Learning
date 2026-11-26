"""确定性教学状态机：只消费已验证事件并返回白名单动作。"""

from . import controls
from .actions import game_command
from .exposure_engine import record_correct_choice, record_exposure, record_wrong_choice
from .models import Command, Event, Session
from .task_flow import finish_task, settle_introduction


class LessonEngine:
    """协调单职责事件处理函数，不依赖数据库、网络或 AI SDK。"""

    def __init__(self) -> None:
        """建立显式事件分发表，避免一个巨大分支处理全部课程逻辑。"""
        self.handlers = {
            "START": controls.start,
            "PAUSE": controls.pause,
            "RESUME": controls.resume,
            "EXIT": controls.exit_session,
            "SKIP": controls.skip,
            "CONTINUE": controls.continue_task,
            "HELP": controls.request_help,
            "REPLAY": controls.replay,
            "TIMEOUT": controls.operational_help,
            "OPERATIONAL_HELP": controls.operational_help,
            "OPERATION_READY": controls.operation_ready,
            "ENTITY_INTERACTED": self.entity_interacted,
            "VISUAL_READY": self.visual_ready,
            "LAYOUT_READY": self.visual_ready,
            "AUDIO_FINISHED": self.audio_finished,
            "AUDIO_FAILED": self.audio_failed,
            "SPEECH_RECOGNIZED": self.speech_recognized,
            "SPEECH_UNAVAILABLE": self.speech_unavailable,
        }

    def apply(self, session: Session, event: Event) -> tuple[str, list[Command]]:
        """执行一次有效状态转移；暂停、退出和完成状态禁止普通事件。"""
        commands: list[Command] = []
        if session.state == "COMPLETE":
            return "ignored_complete", commands
        if session.state in {"PAUSED", "EXITED"} and event.kind not in {"RESUME", "EXIT"}:
            return "ignored_inactive", commands
        if session.state == "READY" and event.kind not in {"START", "PAUSE", "EXIT"}:
            return "ignored_not_started", commands
        reason = self.handlers[event.kind](session, event, commands)
        return reason, commands

    def entity_interacted(self, session: Session, event: Event, commands: list[Command]) -> str:
        """仅让当前听力任务的游戏选择影响课程与理解记录。"""
        if session.task.type != "LISTEN_FIND":
            return "ignored_task_type"
        if session.state not in {"AWAITING_GAME_ACTION", "HINTING"}:
            return "ignored_state"
        if session.operation_blocked:
            return "ignored_operational_block"
        if event.entity_type != f"minecraft:{session.task.target}":
            record_wrong_choice(session)
            commands.append(game_command(session, "PLAY_FEEDBACK", "try_again"))
            return "wrong_target"
        record_correct_choice(session)
        commands.append(game_command(session, "PLAY_FEEDBACK", "correct"))
        finish_task(session, commands)
        return "accepted"

    def visual_ready(self, session: Session, event: Event, commands: list[Command]) -> str:
        """绑定当前视觉命令的回执，防止旧布局冒充当前随机布局。"""
        if not event.command_id or event.command_id != session.active_visual_id:
            return "ignored_visual"
        if event.kind == "LAYOUT_READY" and session.task.randomize_positions:
            session.layout_ready = True
        session.visual_ready = True
        record_exposure(session)
        if session.state == "INTRODUCING":
            settle_introduction(session)
        return "accepted"

    def audio_finished(self, session: Session, event: Event, commands: list[Command]) -> str:
        """消费当前播放回执；重复回执不能增加呈现次数。"""
        if not event.command_id or event.command_id != session.active_audio_id:
            return "ignored_audio"
        if session.audio_finished:
            return "ignored_audio"
        session.audio_finished = True
        record_exposure(session)
        if session.state in {"INTRODUCING", "HINTING"}:
            settle_introduction(session)
        return "accepted"

    def audio_failed(self, session: Session, event: Event, commands: list[Command]) -> str:
        """播放失败时启用有提示路径，不计输入机会且允许继续或跳过。"""
        if not event.command_id or event.command_id != session.active_audio_id:
            return "ignored_audio"
        if session.audio_finished:
            return "ignored_audio"
        session.active_audio_id = None
        session.voice_mode = "OFFLINE_FALLBACK"
        session.hint_level = max(1, session.hint_level)
        session.state = (
            "OPTIONAL_SPEAK" if session.task.type == "OPTIONAL_SPEAK" else "AWAITING_GAME_ACTION"
        )
        commands.append(game_command(session, "SHOW_TITLE", "audio_unavailable"))
        return "accepted"

    def speech_recognized(self, session: Session, event: Event, commands: list[Command]) -> str:
        """只记录自愿口语参与，不从转录内容判断发音或听力掌握。"""
        if session.state != "OPTIONAL_SPEAK":
            return "ignored_state"
        if not event.transcript or not event.transcript.strip():
            return "ignored_empty_speech"
        session.speaking_participations += 1
        finish_task(session, commands)
        return "accepted"

    def speech_unavailable(self, session: Session, event: Event, commands: list[Command]) -> str:
        """标记实时服务不可用，保留缓存语音与非口语通道。"""
        session.voice_mode = "OFFLINE_FALLBACK"
        return "accepted"
