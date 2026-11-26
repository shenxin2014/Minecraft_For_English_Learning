"""实现家长和孩子主动控制课程的行为。"""

from .actions import game_command, play_prompt, stop_audio
from .models import Command, Event, Session
from .task_flow import begin_task, finish_task


def start(session: Session, event: Event, commands: list[Command]) -> str:
    """仅从准备状态开始课程，重复开始不重置进度。"""
    if session.state != "READY":
        return "ignored_state"
    begin_task(session, commands)
    return "accepted"


def pause(session: Session, event: Event, commands: list[Command]) -> str:
    """保存暂停前状态并停止音频。"""
    session.resume_state = session.state
    session.resume_audio = bool(session.active_audio_id and not session.audio_finished)
    session.state = "PAUSED"
    commands.append(stop_audio(session))
    return "accepted"


def resume(session: Session, event: Event, commands: list[Command]) -> str:
    """恢复暂停或退出的课次，不重做已确认任务、不重复发奖励。"""
    if session.state not in {"PAUSED", "EXITED"} or not session.resume_state:
        return "ignored_state"
    session.state = session.resume_state
    session.resume_state = None
    if session.state == "INTRODUCING" or session.resume_audio:
        commands.append(play_prompt(session))
    session.resume_audio = False
    return "accepted"


def exit_session(session: Session, event: Event, commands: list[Command]) -> str:
    """保留可恢复位置并退出，不把未完成任务记为成功。"""
    if session.state == "EXITED":
        return "ignored_state"
    if session.state != "PAUSED":
        session.resume_state = session.state
        session.resume_audio = bool(session.active_audio_id and not session.audio_finished)
    session.state = "EXITED"
    commands.append(stop_audio(session))
    return "accepted"


def skip(session: Session, event: Event, commands: list[Command]) -> str:
    """跳过任务且不给该任务奖励，不惩罚沉默或拒绝作答。"""
    finish_task(session, commands, skipped=True)
    return "accepted"


def continue_task(session: Session, event: Event, commands: list[Command]) -> str:
    """允许观察和自由探索结束，不提供绕过听力验证的入口。"""
    if session.task.type not in {"OBSERVE", "EXPLORE"}:
        return "ignored_state"
    if session.state != "AWAITING_GAME_ACTION":
        return "ignored_state"
    finish_task(session, commands)
    return "accepted"


def request_help(session: Session, event: Event, commands: list[Command]) -> str:
    """逐级提供提示；H1–H4 的完成均不再计为独立正确。"""
    if session.task.type != "LISTEN_FIND" or session.state == "INTRODUCING":
        return "ignored_state"
    session.hint_level = min(4, session.hint_level + 1)
    session.state = "HINTING"
    if session.hint_level == 1:
        commands.append(play_prompt(session))
    else:
        commands.append(game_command(session, "SHOW_HINT", session.task.target))
    return "accepted"


def replay(session: Session, event: Event, commands: list[Command]) -> str:
    """重播时保留最高提示级别，避免重播后被错误记为 H0。"""
    session.replay_requests += 1
    if session.task.type == "LISTEN_FIND":
        session.hint_level = max(1, session.hint_level)
    commands.append(play_prompt(session))
    return "accepted"


def operational_help(session: Session, event: Event, commands: list[Command]) -> str:
    """记录操作障碍而不增加英语错误，也不自动提升语言提示。"""
    if not session.operation_blocked:
        session.operational_blocks += 1
    session.operation_blocked = True
    commands.append(game_command(session, "SHOW_TITLE", "check_controls"))
    return "accepted"


def operation_ready(session: Session, event: Event, commands: list[Command]) -> str:
    """在键鼠或路径问题解决后恢复接受游戏选择。"""
    session.operation_blocked = False
    return "accepted"
