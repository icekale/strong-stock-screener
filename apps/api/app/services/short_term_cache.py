from __future__ import annotations

from threading import RLock
from time import monotonic
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class TtlCache(Generic[T]):
    def __init__(self, ttl_seconds: float = 90) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, T]] = {}
        self._lock = RLock()

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        with self._lock:
            now = monotonic()
            cached = self._items.get(key)
            if cached is not None:
                expires_at, value = cached
                if expires_at > now:
                    return value
            value = factory()
            self._items[key] = (monotonic() + self.ttl_seconds, value)
            return value

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
