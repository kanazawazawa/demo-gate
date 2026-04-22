"""HMAC 署名ベースの Cookie 発行・検証、キー照合、TTL 管理。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

ROLE_INTERNAL = "internal"
ROLE_GUEST = "guest"
COOKIE_NAME = "demo_access"

_DEFAULT_INTERNAL_TTL = 7 * 24 * 60 * 60
_DEFAULT_GUEST_TTL = 24 * 60 * 60

# ロール → (環境変数名, デフォルト秒数)
_TTL_CONFIG: dict[str, tuple[str, int]] = {
    ROLE_INTERNAL: ("DEMO_INTERNAL_TTL_HOURS", _DEFAULT_INTERNAL_TTL),
    ROLE_GUEST: ("DEMO_GUEST_TTL_HOURS", _DEFAULT_GUEST_TTL),
}


def ttl_for(role: str) -> int:
    env_name, default = _TTL_CONFIG.get(role, _TTL_CONFIG[ROLE_INTERNAL])
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(float(raw) * 3600))
    except ValueError:
        return default


def access_key_internal() -> str:
    return os.environ.get("DEMO_ACCESS_KEY", "").strip()


def access_key_guest() -> str:
    return os.environ.get("DEMO_ACCESS_KEY_GUEST", "").strip()


def gate_enabled() -> bool:
    return bool(access_key_internal() or access_key_guest())


def _session_secret() -> bytes:
    explicit = os.environ.get("DEMO_SESSION_SECRET", "").strip()
    if explicit:
        return explicit.encode("utf-8")
    seed = "demo-gate:" + access_key_internal() + "|" + access_key_guest()
    return hashlib.sha256(seed.encode("utf-8")).digest()


def _sign(payload: bytes) -> str:
    mac = hmac.new(_session_secret(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")


def issue_cookie_value(role: str) -> str:
    """``<issued_at>.<role>.<signature>`` 形式の Cookie 値を発行する。"""
    issued = str(int(time.time()))
    payload = f"{issued}.{role}"
    sig = _sign(payload.encode("ascii"))
    return f"{payload}.{sig}"


def verify_cookie(value: str | None) -> str | None:
    """Cookie を検証。有効ならロール名、ダメなら ``None``。"""
    if not value:
        return None
    parts = value.split(".")
    if len(parts) != 3:
        return None
    issued_s, role, sig = parts
    try:
        issued = int(issued_s)
    except ValueError:
        return None
    if role not in _TTL_CONFIG:
        return None
    if time.time() - issued > ttl_for(role):
        return None
    expected = _sign(f"{issued_s}.{role}".encode("ascii"))
    if not hmac.compare_digest(expected, sig):
        return None
    return role


def verify_static_key(submitted: str) -> str | None:
    """環境変数のキーと照合する (動的キーはここでは扱わない)。"""
    submitted_b = (submitted or "").encode("utf-8")
    internal = access_key_internal()
    guest = access_key_guest()
    if internal and hmac.compare_digest(internal.encode("utf-8"), submitted_b):
        return ROLE_INTERNAL
    if guest and hmac.compare_digest(guest.encode("utf-8"), submitted_b):
        return ROLE_GUEST
    return None

