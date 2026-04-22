"""認証エンドポイント + ゲート HTML 配信。"""

from __future__ import annotations

import asyncio
import html as _html
import logging
import os
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.responses import HTMLResponse, JSONResponse

from ._middleware import clear_auth_cookie, current_role, set_auth_cookie
from ._ratelimit import is_blocked, register_failure, register_success
from ._service import gate_enabled, verify_static_key

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"
_DEFAULT_CONTACT = "管理者"

# タイミング攻撃・ブルートフォース緩和のための意図的な遅延
_BLOCKED_DELAY_SEC = 0.5
_LOGIN_DELAY_SEC = 0.3


def _render_gate_html() -> str:
    contact = os.environ.get("DEMO_GATE_CONTACT", "").strip() or _DEFAULT_CONTACT
    template = (_STATIC_DIR / "demo-gate.html").read_text(encoding="utf-8")
    return template.replace("{{CONTACT}}", _html.escape(contact))


def _client_ip(request: Request) -> str:
    return (request.client.host if request.client else "") or "-"


class DemoAuthRequest(BaseModel):
    key: str


def build_router(
    extra_verifier: Callable[[str], Awaitable[str | None]] | None = None,
) -> APIRouter:
    """ゲート関連のエンドポイントを束ねた ``APIRouter`` を返す。

    登録されるエンドポイント:

    - ``GET  /api/demo-auth/status`` : ゲート有効状態 + 現在のロール
    - ``POST /api/demo-auth``        : 合言葉検証 + Cookie 発行
    - ``POST /api/demo-auth/logout`` : Cookie クリア
    - ``GET  /demo-gate.html``       : パッケージ同梱のゲート画面を配信
    """

    router = APIRouter()

    @router.get("/api/demo-auth/status")
    async def demo_auth_status(request: Request) -> dict:
        return {"enabled": gate_enabled(), "role": current_role(request)}

    @router.post("/api/demo-auth")
    async def demo_auth_login(req: DemoAuthRequest, request: Request) -> JSONResponse:
        if not gate_enabled():
            return JSONResponse({"ok": True, "enabled": False})

        ip = _client_ip(request)
        if is_blocked(ip):
            await asyncio.sleep(_BLOCKED_DELAY_SEC)
            return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=401)

        await asyncio.sleep(_LOGIN_DELAY_SEC)
        submitted = req.key or ""
        role = verify_static_key(submitted)
        if not role and extra_verifier is not None:
            try:
                role = await extra_verifier(submitted)
            except Exception:
                logger.exception("demo-gate extra_verifier failed")
                role = None
        if not role:
            register_failure(ip)
            return JSONResponse({"ok": False, "detail": "unauthorized"}, status_code=401)

        register_success(ip)
        resp = JSONResponse({"ok": True, "role": role})
        set_auth_cookie(resp, role)
        return resp

    @router.post("/api/demo-auth/logout")
    async def demo_auth_logout() -> JSONResponse:
        resp = JSONResponse({"ok": True})
        clear_auth_cookie(resp)
        return resp

    @router.get("/demo-gate.html")
    async def demo_gate_page() -> HTMLResponse:
        return HTMLResponse(_render_gate_html())

    return router
