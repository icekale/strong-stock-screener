from __future__ import annotations

from threading import Event
from time import sleep

from app.services.short_term_cache import TtlCache


def test_get_or_refresh_returns_stale_value_while_refreshing_in_background() -> None:
    cache = TtlCache[str](ttl_seconds=0.01)
    refresh_started = Event()
    release_refresh = Event()
    values = iter(["fresh-1", "fresh-2"])

    assert cache.get_or_refresh("key", lambda: next(values)) == "fresh-1"
    sleep(0.02)

    def slow_factory() -> str:
        refresh_started.set()
        release_refresh.wait(timeout=1)
        return next(values)

    assert cache.get_or_refresh("key", slow_factory) == "fresh-1"
    assert refresh_started.wait(timeout=1)

    release_refresh.set()
    for _ in range(100):
        if cache.get_or_refresh("key", lambda: "unused") == "fresh-2":
            break
        sleep(0.01)

    assert cache.get_or_refresh("key", lambda: "unused") == "fresh-2"
