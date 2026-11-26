"""运行不连接 Minecraft 或云端服务的完整课程 HTTP 演示。"""

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.mock_client import MockLessonClient


def run_demo(base_url: str | None, audio_fails: bool) -> dict:
    """选择进程内或本机 HTTP 服务，在临时模拟世界完成首课。"""
    with TemporaryDirectory(prefix="farm-demo-") as directory:
        root = Path(directory)
        if base_url:
            headers = {"X-API-Token": os.getenv("API_TOKEN", "")}
            client = httpx.Client(base_url=base_url, headers=headers, timeout=10)
        else:
            client = TestClient(create_app(root / "progress.sqlite3", api_token=""))
        with client:
            driver = MockLessonClient(client, root / "world.sqlite3")
            return driver.finish(audio_fails=audio_fails)


def main() -> None:
    """解析演示选项并打印可审查的最终学习观察报告。"""
    parser = argparse.ArgumentParser(description="离线课程模拟演示（不播放真实音频）")
    parser.add_argument("--base-url", help="可选：连接已启动的本地后端")
    parser.add_argument("--audio-fails", action="store_true", help="模拟所有音频播放失败")
    args = parser.parse_args()
    report = run_demo(args.base_url, args.audio_fails)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
