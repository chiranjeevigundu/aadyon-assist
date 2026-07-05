"""In-memory fixed-window rate limiter for the auth endpoints.

Single-instance only (the counters live in this process). That's fine for the
family-and-friends deployment; when the API runs as more than one replica, swap the
backing store for Redis behind the same `hit()` signature. Thread-safe because
FastAPI runs sync route handlers on a worker threadpool.
"""
import threading
import time

_lock = threading.Lock()
# key -> (window_start_epoch, count)
_hits: dict[str, tuple[float, int]] = {}


def hit(key: str, limit: int, window_seconds: int) -> bool:
    """Record one hit for `key`; return True if still within `limit` for the current
    window, False if the limit is exceeded (caller should 429)."""
    now = time.time()
    with _lock:
        start, count = _hits.get(key, (now, 0))
        if now - start >= window_seconds:
            start, count = now, 0  # window rolled over
        count += 1
        _hits[key] = (start, count)
        return count <= limit


def reset() -> None:
    """Clear all counters — for tests."""
    with _lock:
        _hits.clear()
