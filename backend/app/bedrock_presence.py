"""维护游戏可见性租约，使浏览器的播放完成不能替代游戏视觉证据。"""

from datetime import datetime, timedelta

from .models import Event, Session, utc_now
from .storage import Store

PRESENCE_TTL = timedelta(seconds=1.5)


def fresh_presence(row) -> bool:
    """只接受最近一个短租约内的正向可见性心跳。"""
    return bool(
        row
        and row["visible"]
        and utc_now()
        - datetime.fromisoformat(
            row["received_at"],
        )
        <= PRESENCE_TTL
    )


def presence_matches(row, session: Session) -> bool:
    """要求心跳属于当前任务和视觉命令，拒绝旧场景延续可见性。"""
    return bool(
        fresh_presence(row)
        and row["task_id"] == session.task.task_id
        and row["visual_id"] == session.active_visual_id
    )


def voice_visibility_error(
    store: Store,
    session: Session,
    event: Event,
    source: str,
    epoch: int | None,
) -> str | None:
    """BDS 绑定课次只接受持续可见期间开始并结束的播放回执。"""
    if source != "voice" or event.kind != "AUDIO_FINISHED":
        return None
    binding = store.connection.execute(
        "SELECT bridge_id FROM bedrock_bindings WHERE session_id=?",
        (session.session_id,),
    ).fetchone()
    if binding is None:
        return None
    row = store.connection.execute(
        "SELECT * FROM bedrock_presence WHERE bridge_id=?",
        (binding[0],),
    ).fetchone()
    if not presence_matches(row, session) or row["epoch"] != epoch:
        return "ignored_bds_visibility"
    return None
