"""簡易ブルートフォース抑制: ログイン試行を検証前に数える。"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_FAIL_WINDOW_SEC = 60
_FAIL_THRESHOLD = 3
_BLOCK_SEC = 300
_attempt_log: dict[str, list[float]] = {}
_blocked_until: dict[str, float] = {}
_lock = threading.Lock()


def _normalize_ip(ip: str) -> str:
    return ip or "-"


def allow_attempt(ip: str) -> bool:
    """試行枠を確保する。認証成功まで同 IP の並列試行も数える。"""
    ip = _normalize_ip(ip)
    with _lock:
        now = time.monotonic()
        if _blocked_until.get(ip, 0) > now:
            return False
        log = [
            timestamp
            for timestamp in _attempt_log.get(ip, [])
            if now - timestamp < _FAIL_WINDOW_SEC
        ]
        log.append(now)
        if len(log) >= _FAIL_THRESHOLD:
            _blocked_until[ip] = now + _BLOCK_SEC
            _attempt_log.pop(ip, None)
            logger.warning("demo-gate: blocked %s for %ss (rate limit)", ip, _BLOCK_SEC)
        else:
            _attempt_log[ip] = log
        return True


def register_success(ip: str) -> None:
    ip = _normalize_ip(ip)
    with _lock:
        _attempt_log.pop(ip, None)
        _blocked_until.pop(ip, None)
