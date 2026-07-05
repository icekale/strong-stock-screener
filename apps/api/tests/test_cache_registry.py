from __future__ import annotations

from app.services.cache_registry import CacheRegistry
from app.services.short_term_cache import TtlCache


class SharedSnapshotCache:
    name = "shared"

    def __init__(self) -> None:
        self.snapshot_data: dict[str, object] = {"size": 1}

    def clear(self) -> None:
        self.snapshot_data["size"] = 0

    def snapshot(self) -> dict[str, object]:
        return self.snapshot_data


def test_cache_registry_summarizes_registered_caches() -> None:
    registry = CacheRegistry()
    cache = TtlCache[str](ttl_seconds=30, name="market")
    cache.get_or_set("a", lambda: "value")

    registry.register("market", cache, group="home")
    summary = registry.summary()

    assert summary["total"] == 1
    assert summary["items"][0]["name"] == "market"
    assert summary["items"][0]["group"] == "home"
    assert summary["items"][0]["size"] == 1


def test_cache_registry_summary_does_not_mutate_cache_snapshot() -> None:
    registry = CacheRegistry()
    cache = SharedSnapshotCache()

    registry.register("shared", cache, group="home")
    summary = registry.summary()

    assert summary["items"][0]["name"] == "shared"
    assert summary["items"][0]["group"] == "home"
    assert cache.snapshot_data == {"size": 1}


def test_cache_registry_summary_returns_items_sorted_by_name() -> None:
    registry = CacheRegistry()
    beta_cache = TtlCache[str](ttl_seconds=30, name="beta")
    alpha_cache = TtlCache[str](ttl_seconds=30, name="alpha")

    registry.register("beta", beta_cache, group="home")
    registry.register("alpha", alpha_cache, group="home")
    summary = registry.summary()

    assert [item["name"] for item in summary["items"]] == ["alpha", "beta"]


def test_cache_registry_clears_one_group() -> None:
    registry = CacheRegistry()
    alpha_cache = TtlCache[str](ttl_seconds=30, name="alpha")
    beta_cache = TtlCache[str](ttl_seconds=30, name="beta")
    stock_cache = TtlCache[str](ttl_seconds=30, name="stock")
    alpha_cache.get_or_set("a", lambda: "alpha")
    beta_cache.get_or_set("a", lambda: "beta")
    stock_cache.get_or_set("a", lambda: "stock")

    registry.register("beta", beta_cache, group="home")
    registry.register("stock", stock_cache, group="stock")
    registry.register("alpha", alpha_cache, group="home")
    cleared = registry.clear("home")

    assert cleared == ["alpha", "beta"]
    assert alpha_cache.snapshot()["size"] == 0
    assert beta_cache.snapshot()["size"] == 0
    assert stock_cache.snapshot()["size"] == 1


def test_cache_registry_clear_without_group_clears_all_registered_caches() -> None:
    registry = CacheRegistry()
    alpha_cache = TtlCache[str](ttl_seconds=30, name="alpha")
    beta_cache = TtlCache[str](ttl_seconds=30, name="beta")
    stock_cache = TtlCache[str](ttl_seconds=30, name="stock")
    alpha_cache.get_or_set("a", lambda: "alpha")
    beta_cache.get_or_set("a", lambda: "beta")
    stock_cache.get_or_set("a", lambda: "stock")

    registry.register("beta", beta_cache, group="home")
    registry.register("stock", stock_cache, group="stock")
    registry.register("alpha", alpha_cache, group="home")
    cleared = registry.clear()

    assert cleared == ["alpha", "beta", "stock"]
    assert alpha_cache.snapshot()["size"] == 0
    assert beta_cache.snapshot()["size"] == 0
    assert stock_cache.snapshot()["size"] == 0
