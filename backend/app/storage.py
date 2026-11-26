"""使用 SQLite 事务原子保存状态、去重结果和待执行命令。"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import Command, Session, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY, snapshot TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    kind TEXT NOT NULL, task_id TEXT NOT NULL,
    previous_state TEXT NOT NULL, next_state TEXT NOT NULL,
    received_at TEXT NOT NULL, response TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS commands (
    position INTEGER PRIMARY KEY AUTOINCREMENT,
    command_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    task_id TEXT NOT NULL, audience TEXT NOT NULL, type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS commands_session ON commands(session_id, audience, status);
CREATE TABLE IF NOT EXISTS bedrock_bindings (
    bridge_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE REFERENCES sessions(session_id)
);
CREATE TABLE IF NOT EXISTS bedrock_probes (
    bridge_id TEXT PRIMARY KEY REFERENCES bedrock_bindings(bridge_id),
    received_at TEXT NOT NULL, runtime TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bedrock_presence (
    bridge_id TEXT PRIMARY KEY REFERENCES bedrock_bindings(bridge_id),
    task_id TEXT NOT NULL, visual_id TEXT, visible INTEGER NOT NULL,
    epoch INTEGER NOT NULL, received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bedrock_latency (
    command_id TEXT PRIMARY KEY REFERENCES commands(command_id),
    bridge_id TEXT NOT NULL REFERENCES bedrock_bindings(bridge_id),
    elapsed_ms REAL NOT NULL
);
"""


class Database:
    """按请求建立连接；写事务串行化同一会话的并发状态更新。"""

    def __init__(self, path: Path) -> None:
        """创建数据库目录与初始结构，不依赖工作目录。"""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """为一次读写操作提供独立连接并确保释放文件句柄。"""
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator["Store"]:
        """把状态、事件收据和命令队列作为一个原子提交单元。"""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield Store(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise


class Store:
    """封装事务内的持久化操作，不包含教学判断。"""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """复用外层事务提供的连接。"""
        self.connection = connection

    def get_session(self, session_id: str) -> Session:
        """读取课次快照，不存在时由 API 层转换成 404。"""
        row = self.connection.execute(
            "SELECT snapshot FROM sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return Session.model_validate_json(row["snapshot"])

    def save_session(self, session: Session) -> None:
        """持久化包含课程版本和当前步骤的完整快照。"""
        self.connection.execute(
            "INSERT INTO sessions VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET snapshot=excluded.snapshot",
            (session.session_id, session.model_dump_json()),
        )

    def previous_response(self, event_id: str, fingerprint: str) -> dict | None:
        """返回同一请求的原始结果，拒绝复用事件 ID 提交不同内容。"""
        row = self.connection.execute(
            "SELECT fingerprint, response FROM events WHERE event_id=?",
            (event_id,),
        ).fetchone()
        if row is None:
            return None
        if row["fingerprint"] != fingerprint:
            raise ValueError("event_id 已用于不同请求")
        return json.loads(row["response"])

    def record_event(
        self,
        event_id: str,
        fingerprint: str,
        session: Session,
        kind: str,
        task_id: str,
        previous_state: str,
        response: dict,
    ) -> None:
        """仅保存必要元数据和结果，不落盘转录文本或原始请求。"""
        self.connection.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                fingerprint,
                session.session_id,
                kind,
                task_id,
                previous_state,
                session.state,
                utc_now().isoformat(),
                json.dumps(response),
            ),
        )

    def add_commands(self, commands: list[Command]) -> None:
        """将引擎动作放入同一事务的持久化发件箱。"""
        self.connection.executemany(
            "INSERT INTO commands(command_id, session_id, task_id, audience, type, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    item.command_id,
                    item.session_id,
                    item.task_id,
                    item.audience,
                    item.type,
                    item.model_dump_json(),
                )
                for item in commands
            ],
        )

    def cancel_audio(self, command_id: str | None) -> None:
        """取消被重播或暂停替代的音频，防止旧音频重新排队。"""
        if command_id:
            self.connection.execute(
                "UPDATE commands SET status='cancelled' WHERE command_id=? AND status='pending'",
                (command_id,),
            )

    def cancel_task_hints(self, session_id: str, task_id: str) -> None:
        """任务切换后取消过时提示，但保留已经确认的剧情奖励。"""
        self.connection.execute(
            "UPDATE commands SET status='cancelled' WHERE session_id=? AND task_id=? "
            "AND status='pending' AND type IN "
            "('SHOW_HINT', 'HIGHLIGHT_ENTITY', 'SHOW_TITLE', 'PLAY_FEEDBACK')",
            (session_id, task_id),
        )

    def pending_commands(self, session: Session, audience: str) -> list[Command]:
        """按签发顺序返回未确认动作，暂停时仅允许停止音频。"""
        rows = self.connection.execute(
            "SELECT payload FROM commands WHERE session_id=? AND audience=? "
            "AND status='pending' ORDER BY position",
            (session.session_id, audience),
        ).fetchall()
        commands = [Command.model_validate_json(row["payload"]) for row in rows]
        if session.state in {"PAUSED", "EXITED"}:
            return [item for item in commands if item.type == "STOP_AUDIO"]
        return commands

    def acknowledge(self, command_id: str, session_id: str, audience: str, success: bool) -> str:
        """确认命令归属；重复确认无副作用，失败时保留待执行状态。"""
        row = self.connection.execute(
            "SELECT status FROM commands WHERE command_id=? AND session_id=? AND audience=?",
            (command_id, session_id, audience),
        ).fetchone()
        if row is None:
            raise KeyError(command_id)
        if row["status"] != "pending" or not success:
            return row["status"]
        self.connection.execute(
            "UPDATE commands SET status='acked' WHERE command_id=?",
            (command_id,),
        )
        return "acked"
