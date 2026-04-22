"""demo-gate: FastAPI 向け合言葉ゲートパッケージ。

使い方:

    from fastapi import FastAPI
    from demo_gate import attach_demo_gate

    app = FastAPI()
    attach_demo_gate(app)

環境変数 ``DEMO_ACCESS_KEY`` が未設定ならゲートは素通し。
設定時のみ Cookie ベースの認証を有効化する。
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Iterable

from fastapi import FastAPI

from ._middleware import (
    DemoAccessGateMiddleware,
    clear_auth_cookie,
    current_role,
    set_auth_cookie,
)
from ._routes import build_router
from ._service import (
    COOKIE_NAME,
    ROLE_GUEST,
    ROLE_INTERNAL,
    gate_enabled,
    verify_cookie,
    verify_static_key,
)

logger = logging.getLogger(__name__)

__all__ = [
    "COOKIE_NAME",
    "DemoAccessGateMiddleware",
    "ROLE_GUEST",
    "ROLE_INTERNAL",
    "attach_demo_gate",
    "clear_auth_cookie",
    "current_role",
    "gate_enabled",
    "set_auth_cookie",
    "verify_cookie",
    "verify_static_key",
]


def attach_demo_gate(
    app: FastAPI,
    *,
    extra_verifier: Callable[[str], Awaitable[str | None]] | None = None,
    extra_public_prefixes: Iterable[str] = (),
    extra_public_exact: Iterable[str] = (),
) -> None:
    """``FastAPI`` アプリに合言葉ゲートを追加する。

    - 認証 API (``/api/demo-auth``) とゲート画面 (``/demo-gate.html``) を登録
    - Middleware を登録し未認可リクエストを 302/401 で制限
    - ``DEMO_ACCESS_KEY`` 未設定時は素通し (middleware 内で no-op)

    Parameters
    ----------
    extra_verifier:
        静的キーで一致しなかった時に呼ばれる非同期フック。
        ロール名 (``"internal"`` / ``"guest"``) または ``None`` を返す。
        DB に保存した一時キーを検証する用途などに使う。
    extra_public_prefixes:
        ゲート前に公開しておきたいパスプレフィックス。
    extra_public_exact:
        ゲート前に公開しておきたい完全一致パス。
    """
    app.include_router(build_router(extra_verifier=extra_verifier))
    app.add_middleware(
        DemoAccessGateMiddleware,
        extra_public_prefixes=tuple(extra_public_prefixes),
        extra_public_exact=tuple(extra_public_exact),
    )
    logger.info("demo-gate: %s", "enabled" if gate_enabled() else "disabled")
