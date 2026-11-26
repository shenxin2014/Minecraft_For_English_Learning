"""将课程意图转换为受限动作，不直接调用 Minecraft 或语音服务。"""

from .models import Command, GameAction, Session


def game_command(session: Session, kind: GameAction, target: str | None = None) -> Command:
    """构造当前任务的一个游戏白名单动作。"""
    return Command(
        session_id=session.session_id,
        task_id=session.task.task_id,
        audience="game",
        type=kind,
        target_id=target,
        hint_level=session.hint_level,
    )


def play_prompt(session: Session, audio_id: str | None = None) -> Command:
    """签发新播放标识，让迟到的旧播放回执不能推进课程。"""
    command = Command(
        session_id=session.session_id,
        task_id=session.task.task_id,
        audience="voice",
        type="PLAY_AUDIO",
        audio_id=audio_id or session.task.prompt_id,
        hint_level=session.hint_level,
    )
    session.active_audio_id = command.command_id
    session.audio_finished = False
    session.exposure_recorded = False
    return command


def stop_audio(session: Session) -> Command:
    """通知播放器停止当前音频；终止和暂停后仍允许拉取此命令。"""
    session.active_audio_id = None
    return Command(
        session_id=session.session_id,
        task_id=session.task.task_id,
        audience="voice",
        type="STOP_AUDIO",
    )


def prepare_visual(session: Session) -> Command | None:
    """请求目标可见或布局随机化，实际完成必须由适配器回执确认。"""
    if not session.task.target:
        return None
    kind = "SHOW_HINT" if session.task.randomize_positions else "HIGHLIGHT_ENTITY"
    command = game_command(session, kind, session.task.target)
    command.randomize_positions = session.task.randomize_positions
    session.active_visual_id = command.command_id
    return command
