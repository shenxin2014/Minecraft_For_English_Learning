"""BDS 事件入口：绑定匿名课次，记录网络探针，不伪造视觉或播放证据。"""

from typing import Literal

from fastapi import FastAPI
from pydantic import Field

from .models import Identifier, Model, utc_now
from .requests import GameEvent
from .responses import EventResponse, SessionView
from .service import LessonService, session_view


class BindingRequest(Model):
    """由本机操作员将一个新课次交给指定 BDS 世界。"""

    bridge_id: Identifier
    session_id: Identifier


class BridgeContext(Model):
    """提供事件归属上下文；不表示场景已呈现或音频已播放。"""

    bridge_id: Identifier
    session: SessionView


class BedrockInteraction(GameEvent):
    """仅允许成功的原生实体交互，禁止上报虚构视觉和布局完成。"""

    kind: Literal["ENTITY_INTERACTED"]
    provider: Literal["bedrock.playerInteractWithEntityAfterEvent"]
    command_id: None = None
    transcript: None = None


class BedrockEnvelope(Model):
    """固定桥接身份与事件，重试必须完整复用相同正文。"""

    bridge_id: Identifier
    event: BedrockInteraction


class ProbeRequest(Model):
    """记录配置版本声明；版本是否真实兼容仍由 BDS 加载日志证明。"""

    bridge_id: Identifier
    pack_version: Literal["0.3.0", "0.4.0"]
    runtime_profile: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")


class ProbeResult(Model):
    """HTTP 到达记录与真实交互证据分别报告，避免探针冒充实机验收。"""

    bridge_id: Identifier
    http_received: bool
    received_at: str | None
    interaction_receipts: int
    gameplay_verified: Literal[False] = False


class BedrockBridge:
    """维护持久化世界绑定及兼容性探针，教学逻辑仍由 LessonService 执行。"""

    def __init__(self, service: LessonService) -> None:
        """共享课程数据库，使绑定在进程重启后保持有效。"""
        self.service = service

    def bind(self, request: BindingRequest) -> dict:
        """只绑定尚未开始的新课次；重试可读取同一个既有绑定。"""
        with self.service.database.transaction() as store:
            session = store.get_session(request.session_id)
            rows = store.connection.execute(
                "SELECT * FROM bedrock_bindings WHERE bridge_id=? OR session_id=?",
                (request.bridge_id, request.session_id),
            ).fetchall()
            if rows:
                if len(rows) != 1 or dict(rows[0]) != request.model_dump():
                    raise ValueError("桥接或课次已绑定；新课次请使用新的 bridge_id")
            else:
                if session.state != "READY" or session.sequences:
                    raise ValueError("BDS 必须绑定尚未开始的新课次")
                store.connection.execute(
                    "INSERT INTO bedrock_bindings VALUES (?, ?)",
                    (request.bridge_id, request.session_id),
                )
        return self.context(request.bridge_id)

    def context(self, bridge_id: str) -> dict:
        """从服务端读取当前课次，禁止 BDS 自行推断下一任务。"""
        with self.service.database.connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM bedrock_bindings WHERE bridge_id=?",
                (bridge_id,),
            ).fetchone()
        if row is None:
            raise KeyError(bridge_id)
        return {"bridge_id": bridge_id, "session": session_view(self.service.get_session(row[0]))}

    def probe(self, request: ProbeRequest) -> dict:
        """保存 HTTP 收到请求的时间，探针不生成任何学习事件。"""
        self.context(request.bridge_id)
        with self.service.database.transaction() as store:
            store.connection.execute(
                "INSERT INTO bedrock_probes VALUES (?, ?, ?) ON CONFLICT(bridge_id) "
                "DO UPDATE SET received_at=excluded.received_at, runtime=excluded.runtime",
                (request.bridge_id, utc_now().isoformat(), request.model_dump_json()),
            )
        return self.status(request.bridge_id)

    def status(self, bridge_id: str) -> dict:
        """返回网络证据和交互收据数，不将收到请求自动标记成实机通过。"""
        session_id = self.context(bridge_id)["session"]["session_id"]
        with self.service.database.connect() as connection:
            probe = connection.execute(
                "SELECT received_at FROM bedrock_probes WHERE bridge_id=?",
                (bridge_id,),
            ).fetchone()
            rows = connection.execute(
                "SELECT response FROM events WHERE session_id=? AND kind='ENTITY_INTERACTED'",
                (session_id,),
            ).fetchall()
        return {
            "bridge_id": bridge_id,
            "http_received": probe is not None,
            "received_at": probe[0] if probe else None,
            "interaction_receipts": len(rows),
        }


def register_bedrock_routes(app: FastAPI, service: LessonService) -> None:
    """注册独立 BDS 通道，使用主应用的专用令牌和网络来源限制。"""
    bridge = BedrockBridge(service)

    @app.post("/v1/bds/bindings", response_model=BridgeContext)
    def bind(body: BindingRequest) -> dict:
        """操作员创建持久绑定，不允许游戏端改绑。"""
        return bridge.bind(body)

    @app.get("/v1/bds/context/{bridge_id}", response_model=BridgeContext)
    def context(bridge_id: str) -> dict:
        """游戏端恢复上下文和已处理事件序号。"""
        return bridge.context(bridge_id)

    @app.post("/v1/bds/events", response_model=EventResponse)
    def event(body: BedrockEnvelope) -> dict:
        """把受限的标准化交互交给原有幂等课程引擎。"""
        return service.handle_event(body.event, "game", bridge_id=body.bridge_id)

    @app.post("/v1/bds/probe", response_model=ProbeResult)
    def probe(body: ProbeRequest) -> dict:
        """网络探针仅记录到达，不替代实体交互测试。"""
        return bridge.probe(body)

    @app.get("/v1/bds/status/{bridge_id}", response_model=ProbeResult)
    def status(bridge_id: str) -> dict:
        """供本机操作员读取网络诊断结果。"""
        return bridge.status(bridge_id)
