from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol


class CacheLike(Protocol):
    name: str

    def clear(self) -> None: ...

    def snapshot(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class RegisteredCache:
    name: str
    group: str
    cache: CacheLike


class CacheRegistry:
    def __init__(self) -> None:
        self._lock = RLock()
        self._items: dict[str, RegisteredCache] = {}

    def register(self, name: str, cache: CacheLike, *, group: str) -> None:
        with self._lock:
            self._items[name] = RegisteredCache(name=name, group=group, cache=cache)

    def summary(self) -> dict[str, object]:
        with self._lock:
            registered = sorted(self._items.values(), key=lambda value: value.name)

        items = []
        for item in registered:
            snapshot = dict(item.cache.snapshot())
            snapshot["name"] = item.name
            snapshot["group"] = item.group
            items.append(snapshot)
        return {"total": len(items), "items": items}

    def clear(self, group: str | None = None) -> list[str]:
        with self._lock:
            registered = [
                item for item in self._items.values() if group is None or item.group == group
            ]

        cleared: list[str] = []
        for item in registered:
            item.cache.clear()
            cleared.append(item.name)
        return sorted(cleared)
