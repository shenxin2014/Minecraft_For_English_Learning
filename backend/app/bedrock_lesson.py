"""M3 的受限动作、视觉、控制与伴随音频接口，不接受原始 Minecraft 命令。"""

import math
from typing import Literal

from fastapi import FastAPI
from pydantic import Field

from .bedrock import BedrockBridge
from .bedrock_presence import presence_matches
from .models import Command, Event, Identifier, Model, utc_now
from .requests import GameEvent, VoiceEvent
from .responses import AckResponse, EventResponse, SessionView
from .service import LessonService, require_game_binding, session_view


class LessonGameEvent(GameEvent):
    """M3 允许已执行视觉动作的回执与玩家的实际选择意图。"""

    provider: Literal["bedrock.m3"]
    transcript: None = None


class LessonControl(Event):
    """游戏内操作可发控制意图，不能发语音或学习评分事件。"""

    kind: Literal["START", "CONTINUE", "HELP", "REPLAY", "SKIP", "PAUSE", "RESUME", "EXIT"]
    provider: Literal["bedrock.m3"]
    command_id: None = None
    entity_type: None = None
    transcript: None = None


class LessonEnvelope(Model):
    """使用共享 game 序号可靠投递 M3 的游戏内事件。"""

    bridge_id: Identifier
    event: LessonGameEvent | LessonControl


class Presence(Model):
    """游戏定期报告当前场景是否可见；未知或断线均视为不可见。"""

    bridge_id: Identifier
    task_id: Identifier
    visual_id: Identifier | None
    visible: bool


class CompanionView(Model):
    """伴随页读取权威状态与可见性代次，避免自己创建游戏证据。"""

    session: SessionView
    visible: bool
    epoch: int


class LessonActions(Model):
    """同一个数据库快照提供动作与校验它们所需的上下文。"""

    session: SessionView
    commands: list[Command]


class LessonAck(Model):
    """动作 ACK 必须携带不可变世界绑定。"""

    bridge_id: Identifier
    session_id: Identifier
    success: bool = True


class CompanionAudio(Model):
    """实际媒体结束回执附带播放开始时的可见性代次。"""

    event: VoiceEvent
    visibility_epoch: int = Field(ge=0)


class LatencySample(Model):
    """只记录从原始事件到对应动作执行完成的同机耗时。"""

    bridge_id: Identifier
    command_id: Identifier
    elapsed_ms: float = Field(ge=0, le=60000, allow_inf_nan=False)


class LessonBridge(BedrockBridge):
    """扩展 M2 世界绑定，所有写操作仍通过服务端状态和事务验证。"""

    def presence(self, body: Presence) -> dict:
        """断线间隙、不可见或场景变化会递增代次，使旧播放失效。"""
        context = self.context(body.bridge_id)
        with self.service.database.transaction() as store:
            session = store.get_session(context["session"]["session_id"])
            if (body.task_id, body.visual_id) != (session.task.task_id, session.active_visual_id):
                raise ValueError("心跳属于旧场景")
            row = store.connection.execute(
                "SELECT * FROM bedrock_presence WHERE bridge_id=?",
                (body.bridge_id,),
            ).fetchone()
            same = presence_matches(row, session) and body.visible
            epoch = row["epoch"] if row else 0
            if not same:
                epoch += 1
            store.connection.execute(
                "INSERT OR REPLACE INTO bedrock_presence VALUES (?, ?, ?, ?, ?, ?)",
                (
                    body.bridge_id,
                    body.task_id,
                    body.visual_id,
                    body.visible,
                    epoch,
                    utc_now().isoformat(),
                ),
            )
        return {"epoch": epoch, "visible": body.visible}

    def companion(self, bridge_id: str) -> dict:
        """让伴随页只读取绑定课次和当前有效的视觉租约。"""
        context = self.context(bridge_id)
        with self.service.database.transaction() as store:
            session = store.get_session(context["session"]["session_id"])
            row = store.connection.execute(
                "SELECT * FROM bedrock_presence WHERE bridge_id=?",
                (bridge_id,),
            ).fetchone()
            return {
                "session": session_view(session),
                "visible": presence_matches(row, session),
                "epoch": row["epoch"] if row else 0,
            }

    def actions(self, bridge_id: str) -> dict:
        """原子读取当前任务和有效动作；暂停时游戏动作不出队。"""
        context = self.context(bridge_id)
        with self.service.database.transaction() as store:
            session = store.get_session(context["session"]["session_id"])
            require_game_binding(store, session.session_id, "game", bridge_id)
            commands = store.pending_commands(session, "game")
            return {"session": session_view(session), "commands": commands}

    def acknowledge(self, command_id: str, body: LessonAck) -> dict:
        """在同一事务内核对世界、课次和游戏通道，再确认传输结果。"""
        with self.service.database.transaction() as store:
            require_game_binding(store, body.session_id, "game", body.bridge_id)
            status = store.acknowledge(command_id, body.session_id, "game", body.success)
            return {"command_id": command_id, "status": status}

    def sample(self, body: LatencySample) -> dict:
        """只接收当前世界已经 ACK 的游戏动作样本，重复上报不重复统计。"""
        session_id = self.context(body.bridge_id)["session"]["session_id"]
        with self.service.database.transaction() as store:
            row = store.connection.execute(
                "SELECT status FROM commands WHERE command_id=? AND session_id=? "
                "AND audience='game' AND type='PLAY_FEEDBACK'",
                (body.command_id, session_id),
            ).fetchone()
            if row is None or row[0] != "acked":
                raise ValueError("只能记录已执行并确认的游戏动作")
            store.connection.execute(
                "INSERT OR IGNORE INTO bedrock_latency VALUES (?, ?, ?)",
                (body.command_id, body.bridge_id, body.elapsed_ms),
            )
        return {"recorded": True}

    def metrics(self, bridge_id: str) -> dict:
        """返回最近课次的实报样本，不将候选包的数字冒充验证通过。"""
        self.context(bridge_id)
        with self.service.database.connect() as connection:
            values = [
                row[0]
                for row in connection.execute(
                    "SELECT elapsed_ms FROM bedrock_latency WHERE bridge_id=? ORDER BY elapsed_ms",
                    (bridge_id,),
                )
            ]
        return {
            "samples": len(values),
            "p95_ms": values[math.ceil(len(values) * 0.95) - 1] if values else None,
            "target_ms": 800,
            "runtime_verified": False,
        }


def register_lesson_bridge(app: FastAPI, service: LessonService) -> None:
    """注册 BDS 凭据专用动作接口与操作员凭据专用音频接口。"""
    bridge = LessonBridge(service)

    @app.post("/v1/bds/lesson/events", response_model=EventResponse)
    def event(body: LessonEnvelope) -> dict:
        """执行显式受限的游戏输入，复用 game 通道幂等游标。"""
        return service.handle_event(body.event, "game", bridge_id=body.bridge_id)

    @app.post("/v1/bds/lesson/presence")
    def presence(body: Presence) -> dict:
        """更新短期视觉租约，不修改学习成绩。"""
        return bridge.presence(body)

    @app.get("/v1/bds/lesson/actions/{bridge_id}", response_model=LessonActions)
    def actions(bridge_id: str) -> dict:
        """BDS 拉取白名单游戏动作。"""
        return bridge.actions(bridge_id)

    @app.post("/v1/bds/lesson/ack/{command_id}", response_model=AckResponse)
    def acknowledge(command_id: str, body: LessonAck) -> dict:
        """确认指定课次的已执行动作。"""
        return bridge.acknowledge(command_id, body)

    @app.post("/v1/bds/lesson/latency")
    def sample(body: LatencySample) -> dict:
        """保存去重后的本机耗时样本。"""
        return bridge.sample(body)

    register_companion_routes(app, bridge)


def register_companion_routes(app: FastAPI, bridge: LessonBridge) -> None:
    """伴随页使用操作员 API 权限，不向浏览器公开 BDS 秘密。"""

    @app.get("/v1/bedrock/companion/{bridge_id}", response_model=CompanionView)
    def companion(bridge_id: str) -> dict:
        """返回音频播放前需要核对的最新状态。"""
        return bridge.companion(bridge_id)

    @app.post("/v1/bedrock/audio", response_model=EventResponse)
    def audio(body: CompanionAudio) -> dict:
        """核对可见性代次后接收媒体回执；客户端不能伪造游戏事件。"""
        return bridge.service.handle_event(
            body.event, "voice", visibility_epoch=body.visibility_epoch
        )

    @app.get("/v1/bedrock/metrics/{bridge_id}")
    def metrics(bridge_id: str) -> dict:
        """操作员读取 P95 样本，空样本不返回零耗时。"""
        return bridge.metrics(bridge_id)
