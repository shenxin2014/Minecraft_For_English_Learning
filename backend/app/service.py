"""应用服务：校验事件归属，并协调引擎与事务存储。"""

import hashlib
import json
from datetime import timedelta
from pathlib import Path

from .bedrock_presence import voice_visibility_error
from .lesson_engine import LessonEngine
from .models import CreateSession, Event, Lesson, Session, WordProgress, utc_now
from .storage import Database, Store


def fingerprint(source: str, payload: dict) -> str:
    """生成请求摘要用于检测 ID 冲突，数据库不保存原始语音文本。"""
    encoded = json.dumps([source, payload], sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def session_view(session: Session) -> dict:
    """向客户端提供恢复课程必需的公开状态，不暴露完整内部快照。"""
    return {
        "session_id": session.session_id,
        "player_id": session.player_id,
        "lesson_id": session.lesson.lesson_id,
        "lesson_version": session.lesson.version,
        "state": session.state,
        "current_task": session.task.model_dump(mode="json"),
        "hint_level": session.hint_level,
        "voice_mode": session.voice_mode,
        "sequences": session.sequences,
        "active_audio_id": session.active_audio_id,
        "active_visual_id": session.active_visual_id,
        "video_game_task_complete": session.video_game_task_complete,
        "task_index": session.task_index,
        "total_tasks": len(session.lesson.tasks),
        "audio_finished": session.audio_finished,
        "visual_ready": session.visual_ready,
        "layout_ready": session.layout_ready,
        "operation_blocked": session.operation_blocked,
    }


def invalid_event_reason(session: Session, event: Event, source: str) -> str | None:
    """检查归属、时序和时间范围；无效事件不能改变课程或序列游标。"""
    if event.player_id != session.player_id:
        return "ignored_player"
    if event.task_id != session.task.task_id:
        return "ignored_task"
    if event.sequence <= session.sequences.get(source, 0):
        return "ignored_sequence"
    if event.occurred_at and event.occurred_at > utc_now() + timedelta(minutes=5):
        return "ignored_future_time"
    return None


class LessonService:
    """向 HTTP 层提供小型用例方法，保证教学变更事务一致。"""

    def __init__(self, database: Database, lessons_dir: Path) -> None:
        """加载经过校验且 ID 唯一的课程目录。"""
        self.database = database
        self.engine = LessonEngine()
        self.lessons: dict[str, Lesson] = {}
        for path in sorted(lessons_dir.glob("lesson_*.json")):
            lesson = Lesson.model_validate_json(path.read_text(encoding="utf-8"))
            if lesson.lesson_id in self.lessons:
                raise ValueError(f"重复 lesson_id: {lesson.lesson_id}")
            self.lessons[lesson.lesson_id] = lesson
        if not self.lessons:
            raise ValueError("未找到课程配置")

    def create_session(self, request: CreateSession) -> dict:
        """幂等创建会话，保存课程副本以保证后续恢复一致。"""
        digest = fingerprint("create", request.model_dump(mode="json"))
        with self.database.transaction() as store:
            previous = store.previous_response(request.event_id, digest)
            if previous:
                return previous
            lesson = self.lessons[request.lesson_id]
            session = Session(player_id=request.player_id, lesson=lesson.model_copy(deep=True))
            session.words = {word: WordProgress() for word in lesson.target_vocabulary}
            response = session_view(session)
            store.save_session(session)
            store.record_event(
                request.event_id,
                digest,
                session,
                "CREATE",
                session.task.task_id,
                "READY",
                response,
            )
            return response

    def get_session(self, session_id: str) -> Session:
        """读取最新持久化状态，不依赖进程内缓存。"""
        with self.database.connect() as connection:
            return Store(connection).get_session(session_id)

    def handle_event(
        self,
        event: Event,
        source: str,
        bridge_id: str | None = None,
        visibility_epoch: int | None = None,
    ) -> dict:
        """在一个事务内完成去重、引擎执行、动作入队与响应保存。"""
        digest = fingerprint(source, event.model_dump(mode="json"))
        if visibility_epoch is not None:
            digest = fingerprint(
                source,
                {
                    "event": event.model_dump(mode="json"),
                    "visibility_epoch": visibility_epoch,
                },
            )
        with self.database.transaction() as store:
            require_game_binding(store, event.session_id, source, bridge_id)
            previous = store.previous_response(event.event_id, digest)
            if previous:
                return {**previous, "duplicate": True}
            session = store.get_session(event.session_id)
            old_state = session.state
            reason = voice_visibility_error(store, session, event, source, visibility_epoch)
            if reason is None:
                reason = self.apply_event(store, session, event, source)
            response = {"result": reason, "duplicate": False, "session": session_view(session)}
            store.save_session(session)
            store.record_event(
                event.event_id,
                digest,
                session,
                event.kind,
                event.task_id,
                old_state,
                response,
            )
            return response

    def apply_event(self, store: Store, session: Session, event: Event, source: str) -> str:
        """执行已归属当前任务的事件，并取消被新状态替代的瞬时命令。"""
        invalid = invalid_event_reason(session, event, source)
        if invalid:
            return invalid
        old_audio = session.active_audio_id
        old_task = session.task.task_id
        reason, commands = self.engine.apply(session, event)
        for command in commands:
            command.caused_by_event_id = event.event_id
        session.sequences[source] = event.sequence
        session.updated_at = utc_now()
        if old_audio != session.active_audio_id:
            store.cancel_audio(old_audio)
        if old_task != session.task.task_id or session.state == "COMPLETE":
            store.cancel_task_hints(session.session_id, old_task)
        store.add_commands(commands)
        return reason

    def pending_commands(self, session_id: str, audience: str) -> list[dict]:
        """拉取待执行命令；拉取不表示执行成功。"""
        with self.database.connect() as connection:
            store = Store(connection)
            if audience == "game":
                require_game_binding(store, session_id, "game", None)
            commands = store.pending_commands(store.get_session(session_id), audience)
            return [command.model_dump(mode="json") for command in commands]

    def acknowledge(self, command_id: str, session_id: str, audience: str, success: bool) -> dict:
        """把动作执行确认与教学正确性判断分开。"""
        with self.database.transaction() as store:
            if audience == "game":
                require_game_binding(store, session_id, "game", None)
            status = store.acknowledge(command_id, session_id, audience, success)
            return {"command_id": command_id, "status": status}

    def progress(self, session_id: str) -> dict:
        """返回最小学习观察报告，不生成未经跨日验证的掌握结论。"""
        session = self.get_session(session_id)
        return {
            "session_id": session.session_id,
            "state": session.state,
            "video_game_task_complete": session.video_game_task_complete,
            "vocab_mastery": {word: result.model_dump() for word, result in session.words.items()},
            "completed_tasks": session.completed_tasks,
            "skipped_tasks": session.skipped_tasks,
            "operational_blocks": session.operational_blocks,
            "replay_requests": session.replay_requests,
            "speaking_participations": session.speaking_participations,
            "note": "首课观察结果；稳定掌握需跨日期复核。",
        }


def require_game_binding(store: Store, session_id: str, source: str, bridge_id: str | None) -> None:
    """在事件事务内隔离 BDS 与 Mock，避免两种场景共同影响一个课次。"""
    if source != "game":
        return
    row = store.connection.execute(
        "SELECT bridge_id FROM bedrock_bindings WHERE session_id=?",
        (session_id,),
    ).fetchone()
    expected = row["bridge_id"] if row else None
    if expected != bridge_id:
        raise ValueError("游戏来源与课次绑定不一致")
    if bridge_id is not None:
        probe = store.connection.execute(
            "SELECT bridge_id FROM bedrock_probes WHERE bridge_id=?",
            (bridge_id,),
        ).fetchone()
        if probe is None:
            raise ValueError("请先完成 BDS HTTP 探针，再发送交互事件")
