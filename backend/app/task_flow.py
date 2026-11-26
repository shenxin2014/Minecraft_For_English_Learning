"""处理任务进入、确认和推进，不负责事件传输或数据库操作。"""

from .actions import game_command, play_prompt, prepare_visual, stop_audio
from .models import Command, Session


def begin_task(session: Session, commands: list[Command]) -> None:
    """重置本步骤证据并签发视觉准备与音频命令。"""
    session.state = "INTRODUCING"
    session.hint_level = 0
    session.attempts = 0
    session.visual_ready = False
    session.layout_ready = False
    session.operation_blocked = False
    session.active_visual_id = None
    visual = prepare_visual(session)
    if visual:
        commands.append(visual)
    commands.append(play_prompt(session))


def finish_task(session: Session, commands: list[Command], *, skipped: bool = False) -> None:
    """关闭当前步骤；只有经过验证的成功才触发奖励。"""
    if skipped:
        session.skipped_tasks.append(session.task.task_id)
    else:
        verify_task(session, commands)
    commands.append(stop_audio(session))
    if session.task_index == len(session.lesson.tasks) - 1:
        session.state = "COMPLETE"
        return
    session.task_index += 1
    begin_task(session, commands)


def verify_task(session: Session, commands: list[Command]) -> None:
    """把剧情结果和学习结果分开保存，成功动作只在此生成。"""
    session.state = "VERIFIED"
    session.completed_tasks.append(session.task.task_id)
    if session.task.story_goal:
        session.video_game_task_complete = True
    for reward in session.task.success_actions:
        commands.append(game_command(session, reward.type, reward.target_id))


def settle_introduction(session: Session) -> None:
    """音频和所需视觉证据齐备后进入适合当前任务的等待状态。"""
    if not session.audio_finished:
        return
    if session.task.target and not session.visual_ready:
        return
    if session.task.type == "OPTIONAL_SPEAK":
        session.state = "OPTIONAL_SPEAK"
    else:
        session.state = "AWAITING_GAME_ACTION"
