"""短 TTL 进程内缓存（热点只读接口，无 Redis 时可用）。"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Tuple

_store: Dict[str, Tuple[float, Any]] = {}


def get_or_set(key: str, ttl_seconds: float, factory: Callable[[], Any]) -> Any:
    if ttl_seconds <= 0:
        return factory()
    now = time.monotonic()
    hit = _store.get(key)
    if hit is not None:
        expires_at, value = hit
        if expires_at > now:
            return value
    value = factory()
    _store[key] = (now + ttl_seconds, value)
    return value


def bump(prefix: str) -> None:
    """按 key 前缀失效（导数完成后可调用）。"""
    keys = [k for k in _store if k.startswith(prefix)]
    for k in keys:
        _store.pop(k, None)
