from __future__ import annotations

from threading import Event, RLock, Thread
from time import monotonic
from typing import Callable, Generic, TypeVar, cast

T = TypeVar("T")
_MISSING = object()


class TtlCache(Generic[T]):
    def __init__(self, ttl_seconds: float = 90, *, name: str = "cache") -> None:
        self.name = name
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, T]] = {}
        self._refreshing: dict[str, int] = {}
        self._filling: dict[str, Event] = {}
        self._lock = RLock()
        self._generation = 0
        self._hits = 0
        self._misses = 0
        self._stale_hits = 0
        self._refresh_count = 0
        self._refresh_error_count = 0
        self._last_refresh_started_at: float | None = None
        self._last_refresh_finished_at: float | None = None
        self._last_error: str | None = None

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        return self._get_fresh_or_fill(key, factory)

    def get_or_refresh(self, key: str, factory: Callable[[], T]) -> T:
        refresh_generation = 0
        should_refresh = False
        stale_value: object = _MISSING
        with self._lock:
            now = monotonic()
            cached = self._items.get(key)
            if cached is not None:
                expires_at, value = cached
                if expires_at > now:
                    self._hits += 1
                    return value
                self._stale_hits += 1
                if key not in self._refreshing:
                    refresh_generation = self._generation
                    self._refreshing[key] = refresh_generation
                    self._last_refresh_started_at = monotonic()
                    should_refresh = True
                stale_value = value

        if should_refresh:
            Thread(
                target=self._refresh,
                args=(key, factory, refresh_generation),
                name=f"cache-refresh-{self.name}",
                daemon=True,
            ).start()

        if stale_value is not _MISSING:
            return cast(T, stale_value)

        return self._get_fresh_or_fill(key, factory)

    def get_if_fresh(self, key: str) -> T | None:
        with self._lock:
            now = monotonic()
            cached = self._items.get(key)
            if cached is None:
                return None
            expires_at, value = cached
            if expires_at <= now:
                return None
            self._hits += 1
            return value

    def clear(self) -> None:
        with self._lock:
            self._generation += 1
            self._items.clear()
            self._refreshing.clear()
            self._filling.clear()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            now = monotonic()
            fresh_count = sum(1 for expires_at, _ in self._items.values() if expires_at > now)
            oldest_expires_in = min(
                (expires_at - now for expires_at, _ in self._items.values()),
                default=None,
            )
            return {
                "name": self.name,
                "ttl_seconds": self.ttl_seconds,
                "size": len(self._items),
                "fresh_count": fresh_count,
                "refreshing_count": len(self._refreshing),
                "hits": self._hits,
                "misses": self._misses,
                "stale_hits": self._stale_hits,
                "refresh_count": self._refresh_count,
                "refresh_error_count": self._refresh_error_count,
                "last_refresh_started_at": self._last_refresh_started_at,
                "last_refresh_finished_at": self._last_refresh_finished_at,
                "last_error": self._last_error,
                "oldest_expires_in_seconds": oldest_expires_in,
            }

    def _get_fresh_or_fill(self, key: str, factory: Callable[[], T]) -> T:
        while True:
            with self._lock:
                now = monotonic()
                cached = self._items.get(key)
                if cached is not None:
                    expires_at, value = cached
                    if expires_at > now:
                        self._hits += 1
                        return value

                self._misses += 1
                fill_event = self._filling.get(key)
                if fill_event is None:
                    fill_event = Event()
                    self._filling[key] = fill_event
                    fill_generation = self._generation
                    self._last_refresh_started_at = monotonic()
                    is_owner = True
                else:
                    is_owner = False

            if not is_owner:
                fill_event.wait()
                continue

            try:
                value = factory()
            except Exception as exc:
                with self._lock:
                    self._refresh_error_count += 1
                    self._last_refresh_finished_at = monotonic()
                    self._last_error = str(exc)
                raise
            else:
                with self._lock:
                    if self._generation == fill_generation:
                        self._items[key] = (monotonic() + self.ttl_seconds, value)
                    self._refresh_count += 1
                    self._last_refresh_finished_at = monotonic()
                    self._last_error = None
                return value
            finally:
                with self._lock:
                    if self._filling.get(key) is fill_event:
                        del self._filling[key]
                fill_event.set()

    def _refresh(self, key: str, factory: Callable[[], T], generation: int) -> None:
        try:
            value = factory()
            with self._lock:
                if self._generation == generation:
                    self._items[key] = (monotonic() + self.ttl_seconds, value)
                self._refresh_count += 1
                self._last_refresh_finished_at = monotonic()
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._refresh_error_count += 1
                self._last_refresh_finished_at = monotonic()
                self._last_error = str(exc)
        finally:
            with self._lock:
                if self._refreshing.get(key) == generation:
                    del self._refreshing[key]
