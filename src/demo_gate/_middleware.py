"""アクセスゲートの Middleware 本体。"""

from __future__ import annotations

from typing import Awaitable, Callable, Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from ._service import COOKIE_NAME, gate_enabled, issue_cookie_value, ttl_for, verify_cookie

GATE_PATH = "/demo-gate.html"

_DEFAULT_PUBLIC_PREFIXES = (
    "/api/demo-auth",  # パッケージ同梱の認証エンドポイント
)
_DEFAULT_PUBLIC_EXACT = (GATE_PATH, "/favicon.ico")


class DemoAccessGateMiddleware(BaseHTTPMiddleware):
    """合言葉ゲート Middleware (環境変数 `DEMO_ACCESS_KEY` 未設定時は素通し)."""

    def __init__(
        self,
        app,
        *,
        extra_public_prefixes: Iterable[str] = (),
        extra_public_exact: Iterable[str] = (),
    ) -> None:
        super().__init__(app)
        self._public_prefixes = tuple(_DEFAULT_PUBLIC_PREFIXES) + tuple(extra_public_prefixes)
        self._public_exact = set(_DEFAULT_PUBLIC_EXACT) | set(extra_public_exact)

    def _is_public(self, path: str) -> bool:
        if path in self._public_exact:
            return True
        return any(path.startswith(p) for p in self._public_prefixes)

    @staticmethod
    def _looks_like_api(request: Request) -> bool:
        if request.url.path.startswith("/api/"):
            return True
        accept = request.headers.get("accept", "")
        return "application/json" in accept and "text/html" not in accept

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not gate_enabled():
            return await call_next(request)
        if self._is_public(request.url.path):
            return await call_next(request)
        if verify_cookie(request.cookies.get(COOKIE_NAME)):
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        if self._looks_like_api(request):
            return JSONResponse(
                {"detail": "demo_access required", "gate": GATE_PATH}, status_code=401
            )
        return RedirectResponse(url=GATE_PATH, status_code=302)


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
