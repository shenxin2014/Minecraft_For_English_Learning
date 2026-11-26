"""为每个验收场景提供独立数据库和 HTTP 客户端。"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.mock_client import MockLessonClient


@pytest.fixture
def client(tmp_path):
    """避免测试污染本地开发进度。"""
    with TestClient(create_app(tmp_path / "progress.sqlite3", api_token="")) as http:
        yield http


@pytest.fixture
def driver(client, tmp_path):
    """创建匿名会话及持久化模拟游戏适配器。"""
    return MockLessonClient(client, tmp_path / "world.sqlite3")
