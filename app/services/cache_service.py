"""Redis backed caching with a safe in-memory fallback.

Frequently accessed data (trek lists/details, dashboards) is cached here with an
expiry so API response times stay low.  If Redis is unavailable the module falls
back to a process-local TTL cache so the demo always runs on a local machine.
"""
import json
import threading
import time
from typing import Any, Callable, Iterable, Optional

from flask import current_app

try:  # redis is a hard requirement of the project, but we degrade gracefully
    import redis
except ImportError:  # pragma: no cover
    redis = None


class _MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def setex(self, key: str, ttl: int, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.time() + ttl, value)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at < time.time():
                del self._data[key]
                return None
            return value

    def delete(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._data.pop(key, None)

    def scan_prefix(self, prefix: str) -> list[str]:
        now = time.time()
        with self._lock:
            return [k for k, (exp, _) in self._data.items() if k.startswith(prefix) and exp > now]

    def incr(self, key: str, ttl: int = 60) -> int:
        with self._lock:
            value = int((self._data.get(key) or (time.time() + ttl, 0))[1]) + 1
            self._data[key] = (time.time() + ttl, value)
            return value


class CacheService:
    """Thin wrapper that hides whether Redis or the fallback is being used."""

    def __init__(self) -> None:
        self._client = None
        self._memory = _MemoryCache()
        self._backend = "memory"

    # ------------------------------------------------------------------ setup
    def init_app(self, app) -> None:
        url = app.config.get("REDIS_URL")
        self._ttl = int(app.config.get("CACHE_TTL_SECONDS", 60))
        self._prefix = app.config.get("CACHE_PREFIX", "tma")
        if redis and url:
            try:
                client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1,
                                        socket_timeout=1)
                client.ping()
                self._client = client
                self._backend = "redis"
            except Exception as exc:  # pragma: no cover - environment dependent
                print(f"[cache] Redis unavailable ({exc}); using in-memory fallback.")
                self._client = None
                self._backend = "memory"
        else:
            self._client = None
            self._backend = "memory"

    @property
    def backend(self) -> str:
        return self._backend

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    # --------------------------------------------------------------- primitives
    def get(self, key: str) -> Any:
        full = self._key(key)
        if self._client:
            try:
                raw = self._client.get(full)
                return json.loads(raw) if raw else None
            except Exception:
                return None
        return self._memory.get(full)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        full = self._key(key)
        ttl = ttl or getattr(self, "_ttl", 60)
        if self._client:
            try:
                self._client.setex(full, ttl, json.dumps(value, default=str))
                return
            except Exception:
                pass
        self._memory.setex(full, ttl, value)

    def delete_keys(self, *keys: str) -> None:
        if self._client:
            try:
                self._client.delete(*[self._key(k) for k in keys])
                return
            except Exception:
                pass
        self._memory.delete(*[self._key(k) for k in keys])

    def invalidate_prefix(self, prefix: str) -> None:
        """Remove every cached key under ``prefix`` (used after writes)."""
        full_prefix = self._key(prefix)
        if self._client:
            try:
                iterator = self._client.scan_iter(match=f"{full_prefix}*", count=200)
                removed = 0
                for key in iterator:
                    self._client.delete(key)
                    removed += 1
                return
            except Exception:
                pass
        self._memory.delete(*self._memory.scan_prefix(full_prefix))

    # ----------------------------------------------------------------- helpers
    def memoize(self, key: str, producer: Callable[[], Any], ttl: Optional[int] = None,
                force_refresh: bool = False) -> Any:
        """Return cached value for ``key`` or compute+store it."""
        if not force_refresh:
            cached = self.get(key)
            if cached is not None:
                return cached
        value = producer()
        if value is not None:
            self.set(key, value, ttl)
        return value

    def rate_limited(self, bucket: str, limit: int, window_seconds: int = 60) -> bool:
        """Simple fixed-window limiter; returns True when the action is allowed."""
        key = f"rl:{bucket}"
        attempts = 0
        if self._client:
            try:
                full = self._key(key)
                attempts = self._client.incr(full)
                if attempts == 1:
                    self._client.expire(full, window_seconds)
                return attempts <= limit
            except Exception:
                pass
        attempts = self._memory.incr(key, window_seconds)
        return attempts <= limit


cache = CacheService()
