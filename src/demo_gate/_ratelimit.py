"""簡易ブルートフォース抑制: 直近 N 秒で M 回失敗したら同 IP を一時ブロック。"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_FAIL_WINDOW_SEC = 60
_FAIL_THRESHOLD = 3
_BLOCK_SEC = 300
_fail_log: dict[str, list[float]] = {}
_blocked_until: dict[str, float] = {}


def _normalize_ip(ip: str) -> str:
    return ip or "-"


def register_failure(ip: str) -> None:
    """失敗を記録し、閾値を超えたらブロック状態にする。"""
    ip = _normalize_ip(ip)
    now = time.time()
    if _blocked_until.get(ip, 0) > now:
        return
    log = [t for t in _fail_log.setdefault(ip, []) if now - t < _FAIL_WINDOW_SEC]
    log.append(now)
    if len(log) >= _FAIL_THRESHOLD:
        _blocked_until[ip] = now + _BLOCK_SEC
        _fail_log[ip] = []
        logger.warning("demo-gate: blocked %s for %ss (brute-force suspect)", ip, _BLOCK_SEC)
    else:
        _fail_log[ip] = log


def is_blocked(ip: str) -> bool:
    return _blocked_until.get(_normalize_ip(ip), 0) > time.time()


def register_success(ip: str) -> None:
    _fail_log.pop(_normalize_ip(ip), None)
