"""管理输入机会与理解证据，避免把播放、猜中或操作困难计作掌握。"""

from .models import Session


def record_exposure(session: Session) -> None:
    """仅在同一次播放完成且目标可见时记录一次输入机会。"""
    if not session.task.target or session.exposure_recorded:
        return
    if not session.audio_finished or not session.visual_ready:
        return
    word = session.words[session.task.target]
    word.exposure_count += 1
    if word.status == "UNSEEN":
        word.status = "INTRODUCED"
    session.exposure_recorded = True


def record_wrong_choice(session: Session) -> None:
    """记录实际误选；卡路等操作问题由独立事件处理。"""
    session.attempts += 1
    session.words[session.task.target].wrong_choices += 1


def record_correct_choice(session: Session) -> None:
    """按首次选择、提示历史和已确认的随机布局归因正确结果。"""
    word = session.words[session.task.target]
    if word.status not in {"UNDERSTANDS", "RETENTION_CHECK"}:
        word.status = "PRACTICING"
    if session.hint_level > 0:
        word.assisted_correct += 1
        return
    if session.attempts > 0 or not session.layout_ready:
        word.unconfirmed_correct += 1
        return
    word.independent_correct += 1
    if word.independent_contexts and session.task.context not in word.independent_contexts:
        word.transfer_correct += 1
    if session.task.context not in word.independent_contexts:
        word.independent_contexts.append(session.task.context)
    if word.independent_correct >= session.lesson.independent_threshold:
        word.status = "UNDERSTANDS"
    # 跨日期复核属于 M5；首课绝不把当日表现标成稳定掌握。
