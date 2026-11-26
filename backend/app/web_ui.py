"""提供本地教学页面和打包素材，不引入远程资源或前端构建依赖。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def register_web_ui(app: FastAPI, frontend_root: Path) -> None:
    """将同源 HTML、模块脚本、插画与音频绑定到现有后端。"""
    app.mount("/assets", StaticFiles(directory=frontend_root / "assets"), name="assets")
    app.mount("/js", StaticFiles(directory=frontend_root / "js"), name="javascript")

    @app.get("/", include_in_schema=False)
    def lesson_page() -> FileResponse:
        """显示首课入口，教学状态始终从后端读取。"""
        return FileResponse(frontend_root / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/bedrock", include_in_schema=False)
    def bedrock_companion() -> FileResponse:
        """提供真实游戏的语音伴随页，不展示可替代游戏的动物按钮。"""
        return FileResponse(frontend_root / "bedrock.html", headers={"Cache-Control": "no-store"})


def is_local_page(path: str, method: str) -> bool:
    """允许本机先加载登录页面与素材，API 仍按令牌配置校验。"""
    if method not in {"GET", "HEAD"}:
        return False
    return path in {"/", "/bedrock"} or path.startswith(("/assets/", "/js/"))
