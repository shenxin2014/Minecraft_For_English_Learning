"""游戏动作适配接口与不依赖 Minecraft 的持久化模拟实现。"""

import sqlite3
from pathlib import Path
from typing import Protocol

from .models import Command


class GameAdapter(Protocol):
    """约束游戏适配器只执行经过验证的协议动作。"""

    def execute(self, command: Command) -> bool:
        """执行一次动作；返回是否产生了新的模拟效果。"""
        ...


class MockGameAdapter:
    """用独立 SQLite 表模拟场景效果及适配器重启后的命令去重。"""

    def __init__(self, path: Path) -> None:
        """创建模拟效果记录，使重复奖励测试跨进程仍有效。"""
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS effects (command_id TEXT PRIMARY KEY, payload TEXT)",
            )

    def execute(self, command: Command) -> bool:
        """再次校验边界，再将效果与去重标识原子写入模拟世界。"""
        command = Command.model_validate(command.model_dump())
        if command.audience != "game":
            raise ValueError("GameAdapter 不执行语音动作")
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO effects VALUES (?, ?)",
                (command.command_id, command.model_dump_json()),
            )
            return cursor.rowcount == 1
