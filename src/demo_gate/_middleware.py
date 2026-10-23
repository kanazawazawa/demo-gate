"""アクセスゲートの Middleware 本体。"""

from __future__ import annotations

from typing import Iterable

from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ._service import COOKIE_NAME, gate_enabled, issue_cookie_value, ttl_for, verify_cookie

GATE_PATH = "/demo-gate.html"

_DEFAULT_PUBLIC_EXACT = (
    GATE_PATH,
    "/favicon.ico",
    "/api/demo-auth",
    "/api/demo-auth/status",
    "/api/demo-auth/logout",
)


class DemoAccessGateMiddleware:
    """合言葉ゲート Middleware (環境変数 `DEMO_ACCESS_KEY` 未設定時は素通し)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        extra_public_prefixes: Iterable[str] = (),
        extra_public_exact: Iterable[str] = (),
    ) -> None:
        self.app = app
        self._public_prefixes = tuple(extra_public_prefixes)
        self._public_exact = set(_DEFAULT_PUBLIC_EXACT) | set(extra_public_exact)

    def _is_public(self, path: str) -> bool:
        if path in self._public_exact:
            return True
        return any(path.startswith(p) for p in self._public_prefixes)

    @staticmethod
    def _looks_like_api(request: HTTPConnection) -> bool:
        if request.scope["path"].startswith("/api/"):
            return True
        accept = request.headers.get("accept", "")
        return "application/json" in accept and "text/html" not in accept

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or not gate_enabled():
            await self.app(scope, receive, send)
            return
        if self._is_public(scope["path"]):
            await self.app(scope, receive, send)
            return

        request = HTTPConnection(scope)
        if not verify_cookie(request.cookies.get(COOKIE_NAME)):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            if self._looks_like_api(request):
                response = JSONResponse(
                    {"detail": "demo_access required", "gate": GATE_PATH}, status_code=401
                )
            else:
                response = RedirectResponse(url=GATE_PATH, status_code=302)
            await response(scope, receive, send)
            return

        async def send_with_cache_control(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_cache_control)


def current_role(request: Request) -> str | None:
    """リクエストの Cookie からロールを取り出す (未認可は None)。"""
    return verify_cookie(request.cookies.get(COOKIE_NAME))


def set_auth_cookie(response: Response, role: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=issue_cookie_value(role),
        max_age=ttl_for(role),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")
