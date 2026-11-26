"""将 BDS 凭据限制到事件通道，同时限制实际 TCP 来源。"""

from secrets import compare_digest

from fastapi import Request
from fastapi.responses import JSONResponse


def is_bridge_request(path: str) -> bool:
    """只将游戏端必需的三个接口交给 BDS 令牌认证。"""
    return path in {"/v1/bds/events", "/v1/bds/probe"} or path.startswith(
        ("/v1/bds/context/", "/v1/bds/lesson/"),
    )


def bridge_access_error(request: Request, token: str, hosts: set[str]) -> JSONResponse | None:
    """拒绝未启用、网络来源不符或凭据错误的请求，不信任转发头。"""
    if not token:
        return JSONResponse({"detail": "BDS 通道未启用"}, status_code=503)
    host = request.client.host if request.client else ""
    if host not in hosts:
        return JSONResponse({"detail": "BDS 来源不在白名单"}, status_code=403)
    supplied = request.headers.get("x-bds-token", "")
    if not compare_digest(supplied.encode(), token.encode()):
        return JSONResponse({"detail": "需要有效的 X-BDS-Token"}, status_code=401)
    return None
