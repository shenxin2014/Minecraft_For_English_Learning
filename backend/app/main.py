"""FastAPI 入口：HTTP 路由只校验边界并调用应用服务。"""

import os
from pathlib import Path
from secrets import compare_digest
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .bedrock import register_bedrock_routes
from .bedrock_lesson import register_lesson_bridge
from .bedrock_security import bridge_access_error, is_bridge_request
from .models import Ack, Command, CreateSession, Event
from .requests import ControlEvent, GameEvent, StartEvent, VoiceEvent
from .responses import AckResponse, EventResponse, HealthResponse, ProgressResponse, SessionView
from .service import LessonService, session_view
from .storage import Database
from .web_ui import is_local_page, register_web_ui

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTROL_KINDS = {
    "CONTINUE",
    "HELP",
    "REPLAY",
    "SKIP",
    "PAUSE",
    "RESUME",
    "EXIT",
    "TIMEOUT",
    "OPERATIONAL_HELP",
    "OPERATION_READY",
}
GAME_KINDS = {"VISUAL_READY", "LAYOUT_READY", "ENTITY_INTERACTED"}
VOICE_KINDS = {"AUDIO_FINISHED", "AUDIO_FAILED", "SPEECH_RECOGNIZED", "SPEECH_UNAVAILABLE"}


def require_channel(event: Event, allowed: set[str]) -> None:
    """限制各输入通道的事件权限，语音端不能伪装游戏点击。"""
    if event.kind not in allowed:
        raise HTTPException(422, "事件不属于此通道")
    if event.kind == "ENTITY_INTERACTED" and event.entity_type is None:
        raise HTTPException(422, "实体交互必须包含 entity_type")


def require_session_path(event: Event, session_id: str) -> None:
    """拒绝 URL 和请求正文指向不同会话的控制请求。"""
    if event.session_id != session_id:
        raise HTTPException(422, "路径与正文的 session_id 不一致")


def create_app(
    database_path: Path | None = None,
    lessons_dir: Path | None = None,
    api_token: str | None = None,
    bds_token: str | None = None,
    bds_hosts: set[str] | None = None,
) -> FastAPI:
    """创建隔离的应用实例，测试可注入临时数据库和课程目录。"""
    if os.getenv("MOCK_MODE", "true").lower() != "true":
        raise RuntimeError("默认适配模式需保持 MOCK_MODE=true；BDS 候选通道通过独立绑定启用")
    database_path = database_path or Path(
        os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "progress.sqlite3")),
    )
    service = LessonService(Database(database_path), lessons_dir or PROJECT_ROOT / "lessons")
    app = FastAPI(title="Minecraft AI English — Farm", version="0.4.0")
    app.state.service = service
    app.state.bds_token = bds_token if bds_token is not None else os.getenv("BDS_TOKEN", "")
    app.state.bds_hosts = (
        bds_hosts
        if bds_hosts is not None
        else set(
            os.getenv("BDS_ALLOWED_HOSTS", "127.0.0.1,::1").split(","),
        )
    )
    configure_security(app, api_token if api_token is not None else os.getenv("API_TOKEN", ""))
    configure_errors(app)
    register_session_routes(app, service)
    register_event_routes(app, service)
    register_action_routes(app, service)
    register_bedrock_routes(app, service)
    register_lesson_bridge(app, service)
    register_web_ui(app, PROJECT_ROOT / "frontend")
    return app


def configure_security(app: FastAPI, api_token: str) -> None:
    """无令牌时仅接受本机连接；配置令牌时所有业务请求必须认证。"""

    @app.middleware("http")
    async def check_access(request: Request, call_next):
        """在解析事件前检查请求来源或服务端共享令牌。"""
        host = request.client.host if request.client else ""
        if is_bridge_request(request.url.path):
            denied = bridge_access_error(request, app.state.bds_token, app.state.bds_hosts)
            return denied if denied is not None else await call_next(request)
        local = host in {"127.0.0.1", "::1", "testclient"}
        if local and is_local_page(request.url.path, request.method):
            return await call_next(request)
        if api_token:
            supplied = request.headers.get("x-api-token", "")
            if not compare_digest(supplied.encode(), api_token.encode()):
                return JSONResponse({"detail": "需要有效的 X-API-Token"}, status_code=401)
        elif not local:
            return JSONResponse({"detail": "未配置令牌，仅允许本机访问"}, status_code=403)
        return await call_next(request)


def configure_errors(app: FastAPI) -> None:
    """将预期的资源缺失和请求冲突转换为稳定 HTTP 错误。"""

    @app.exception_handler(KeyError)
    async def missing_resource(request: Request, error: KeyError) -> JSONResponse:
        """隐藏内部查找细节，只报告资源不存在。"""
        return JSONResponse({"detail": "会话、课程或命令不存在"}, status_code=404)

    @app.exception_handler(ValueError)
    async def conflicting_request(request: Request, error: ValueError) -> JSONResponse:
        """说明事件 ID 被不同请求复用，提醒客户端生成新 ID。"""
        return JSONResponse({"detail": str(error)}, status_code=409)


def register_session_routes(app: FastAPI, service: LessonService) -> None:
    """注册会话读取、创建、控制与学习汇总接口。"""

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict:
        """报告离线适配器状态，不声称真实游戏或语音已连接。"""
        return {"status": "ok", "mock_mode": True, "game": "mock", "speech": "mock"}

    @app.post("/v1/sessions", status_code=201, response_model=SessionView)
    def create_session(body: CreateSession) -> dict:
        """创建或幂等返回已有匿名会话。"""
        return service.create_session(body)

    @app.get("/v1/sessions/{session_id}", response_model=SessionView)
    def get_session(session_id: str) -> dict:
        """读取当前任务与状态，供断线后的客户端恢复。"""
        return session_view(service.get_session(session_id))

    @app.post("/v1/sessions/{session_id}/start", response_model=EventResponse)
    def start_session(session_id: str, body: StartEvent) -> dict:
        """开始课次，沿用控制通道的单调递增序列。"""
        require_session_path(body, session_id)
        require_channel(body, {"START"})
        return service.handle_event(body, "control")

    @app.post("/v1/sessions/{session_id}/control", response_model=EventResponse)
    def control_session(session_id: str, body: ControlEvent) -> dict:
        """执行暂停、重听、帮助、跳过等明确的用户操作。"""
        require_session_path(body, session_id)
        require_channel(body, CONTROL_KINDS)
        return service.handle_event(body, "control")

    @app.get("/v1/progress/{session_id}", response_model=ProgressResponse)
    def get_progress(session_id: str) -> dict:
        """返回剧情与学习分离的基础观察报告。"""
        return service.progress(session_id)


def register_event_routes(app: FastAPI, service: LessonService) -> None:
    """注册游戏和语音输入，禁止通道之间越权。"""

    @app.post("/v1/game/events", response_model=EventResponse)
    def game_event(body: GameEvent) -> dict:
        """接收适配器标准化后的视觉和实体事件。"""
        require_channel(body, GAME_KINDS)
        return service.handle_event(body, "game")

    @app.post("/v1/voice/events", response_model=EventResponse)
    def voice_event(body: VoiceEvent) -> dict:
        """接收播放与可选口语事件，转录文本不持久化。"""
        require_channel(body, VOICE_KINDS)
        return service.handle_event(body, "voice")


def register_action_routes(app: FastAPI, service: LessonService) -> None:
    """注册游戏和语音动作的轮询与确认协议。"""

    @app.get("/v1/{audience}/actions", response_model=list[Command])
    def get_actions(audience: Literal["game", "voice"], session_id: str) -> list[dict]:
        """返回有序待执行命令，客户端按 command_id 去重。"""
        return service.pending_commands(session_id, audience)

    @app.post("/v1/{audience}/actions/{command_id}/ack", response_model=AckResponse)
    def acknowledge(audience: Literal["game", "voice"], command_id: str, body: Ack) -> dict:
        """确认动作传输结果；不会凭确认请求给课程加分。"""
        return service.acknowledge(command_id, body.session_id, audience, body.success)


app = create_app()
